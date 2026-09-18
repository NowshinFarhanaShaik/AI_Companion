"""Platform-wide reads for staff. Deliberately NOT scoped with for_user().

These functions must only be called from insights/admin_api.py, whose router
uses StaffJWTAuth.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DateTimeField, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ai.models import AICallLog
from assessment.models import Attempt, QuizSession
from events.models import LearningEvent
from insights.queries import activity_summary, ai_summary, optional_round, project_breakdown
from materials.models import Material
from workspace.models import Project, Space

RECENT_EVENTS = 20
RECENT_ASSESSMENTS = 10


def overview() -> dict:
    User = get_user_model()
    week_ago = timezone.now() - timedelta(days=7)
    by_status = list(
        Material.objects.order_by().values("status").annotate(count=Count("id")).order_by("status")
    )
    return {
        "users": User.objects.count(),
        "spaces": Space.objects.count(),
        "projects": Project.objects.count(),
        "materials": sum(row["count"] for row in by_status),
        "materials_by_status": by_status,
        "quiz_sessions": QuizSession.objects.count(),
        "questions_answered": Attempt.objects.count(),
        "active_users_7d": LearningEvent.objects.filter(created_at__gte=week_ago)
        .order_by().values("user_id").distinct().count(),
        "events": activity_summary(LearningEvent.objects.all()),
    }


def users(q: str = ""):
    """Annotated with Subqueries: joining projects, events and AI calls in one
    annotate() would multiply rows and inflate the sums."""
    User = get_user_model()
    project_count = (
        Project.objects.filter(owner=OuterRef("pk")).order_by().values("owner")
        .annotate(n=Count("id")).values("n")
    )
    last_event = (
        LearningEvent.objects.filter(user=OuterRef("pk")).order_by("-created_at").values("created_at")[:1]
    )
    ai = AICallLog.objects.filter(user=OuterRef("pk")).order_by().values("user")
    queryset = User.objects.annotate(
        project_count=Subquery(project_count, output_field=IntegerField()),
        last_activity=Subquery(last_event, output_field=DateTimeField()),
        ai_call_count=Subquery(ai.annotate(n=Count("id")).values("n"), output_field=IntegerField()),
        ai_cost=Subquery(ai.annotate(s=Sum("estimated_cost_usd")).values("s")),
    ).order_by("email")
    if q:
        queryset = queryset.filter(Q(email__icontains=q) | Q(name__icontains=q))
    return queryset


def user_detail(user_id) -> dict:
    user = get_object_or_404(get_user_model(), pk=user_id)

    spaces = list(
        Space.objects.filter(owner=user).order_by()
        .annotate(project_count=Count("projects")).order_by("name")
        .values("id", "name", "project_count")
    )
    recent = list(
        LearningEvent.objects.filter(user=user).order_by("-created_at")
        .values("id", "created_at", "type", "project_id", "payload", project_name=F("project__name"))
        [:RECENT_EVENTS]
    )
    assessments = [
        {**row, "average_score": optional_round(row["average_score"])}
        for row in QuizSession.objects.filter(project__owner=user).order_by()
        .annotate(average_score=Avg("questions__attempt__score"), answered=Count("questions__attempt"))
        .order_by("-created_at")
        .values("id", "project_id", "status", "created_at", "completed_at", "average_score",
                "answered", project_name=F("project__name"))[:RECENT_ASSESSMENTS]
    ]
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_staff": user.is_staff,
            "is_active": user.is_active,
            "joined_at": user.created_at,
        },
        "spaces": spaces,
        "projects": project_breakdown(Project.objects.filter(owner=user)),
        "recent_activity": recent,
        "assessments": assessments,
        "ai": ai_summary(AICallLog.objects.filter(user=user)),
    }


def activity(*, user_id=None, space_id=None, project_id=None, type=None, date_from=None, date_to=None):
    events = LearningEvent.objects.select_related("user", "space", "project__space").order_by("-created_at")
    if user_id:
        events = events.filter(user_id=user_id)
    if project_id:
        events = events.filter(project_id=project_id)
    if space_id:
        # Most events carry a project, not a space, so match both.
        events = events.filter(Q(space_id=space_id) | Q(project__space_id=space_id))
    if type:
        events = events.filter(type=type)
    if date_from:
        events = events.filter(created_at__date__gte=date_from)
    if date_to:
        events = events.filter(created_at__date__lte=date_to)
    return events
