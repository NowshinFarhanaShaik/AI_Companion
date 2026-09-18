"""Learner-facing analytics. Every function receives querysets that are already scoped.

Rules: call .order_by() before a grouped .values(); never aggregate over two
multi-valued joins in one annotate().
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from ai.models import AICallLog
from assessment.models import Attempt, QuizSession
from events.models import LearningEvent
from learning.growth import concept_trends
from learning.models import ConceptMastery
from materials.models import Material
from workspace.models import Project, Space

ACTIVITY_WINDOW_DAYS = 14
LOW_BAND = 0.4      # below: low
HIGH_BAND = 0.7     # above: high
MAX_SESSIONS_IN_CHART = 30


def optional_round(value, ndigits: int = 4):
    return round(float(value), ndigits) if value is not None else None


def activity_summary(events, *, days: int = ACTIVITY_WINDOW_DAYS) -> dict:
    start_day = timezone.localdate() - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(start_day, time.min))
    windowed = events.filter(created_at__gte=start)
    counts = dict(
        windowed.order_by()
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count")
    )
    per_day = [
        {"day": start_day + timedelta(days=i), "count": counts.get(start_day + timedelta(days=i), 0)}
        for i in range(days)
    ]
    by_type = list(
        windowed.order_by().values("type").annotate(count=Count("id")).order_by("-count", "type")
    )
    return {"total": sum(counts.values()), "per_day": per_day, "by_type": by_type}


def quiz_summary(sessions, attempts) -> dict:
    completed = QuizSession.Status.COMPLETED
    totals = sessions.order_by().aggregate(
        started=Count("id"), completed=Count("id", filter=Q(status=completed))
    )
    answers = attempts.order_by().aggregate(answered=Count("id"), average=Avg("score"))
    recent = list(
        sessions.filter(status=completed)
        .order_by()
        .annotate(average_score=Avg("questions__attempt__score"), answered=Count("questions__attempt"))
        .order_by("-completed_at")
        .values("id", "project_id", "completed_at", "average_score", "answered")[:MAX_SESSIONS_IN_CHART]
    )
    per_session = [
        {
            "session_id": row["id"],
            "project_id": row["project_id"],
            "completed_at": row["completed_at"],
            "average_score": optional_round(row["average_score"]),
            "answered": row["answered"],
        }
        for row in reversed(recent)      # oldest first, for the chart
    ]
    return {
        "sessions_started": totals["started"],
        "sessions_completed": totals["completed"],
        "questions_answered": answers["answered"],
        "average_score": optional_round(answers["average"]),
        "per_session": per_session,
    }


def mastery_summary(masteries) -> dict:
    # A concept with no answers only has its starting estimate, so it is not counted as weak or strong.
    practised = Q(evidence_count__gt=0)
    row = masteries.order_by().aggregate(
        concepts=Count("id"),
        average=Avg("score"),
        unpractised=Count("id", filter=~practised),
        low=Count("id", filter=practised & Q(score__lt=LOW_BAND)),
        medium=Count("id", filter=practised & Q(score__gte=LOW_BAND, score__lte=HIGH_BAND)),
        high=Count("id", filter=practised & Q(score__gt=HIGH_BAND)),
    )
    row["average"] = optional_round(row["average"])
    return row


def ai_summary(calls) -> dict:
    error = AICallLog.Status.ERROR
    aggregates = dict(
        calls=Count("id"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        cost=Sum("estimated_cost_usd"),
        errors=Count("id", filter=Q(status=error)),
    )

    def shape(row):
        return {
            "calls": row["calls"],
            "input_tokens": row["input_tokens"] or 0,
            "output_tokens": row["output_tokens"] or 0,
            "estimated_cost_usd": round(float(row["cost"] or 0), 6),
            "errors": row["errors"],
        }

    totals = shape(calls.order_by().aggregate(**aggregates))
    by_feature = [
        {"feature": row["feature"], **shape(row)}
        for row in calls.order_by().values("feature").annotate(**aggregates).order_by("-calls", "feature")
    ]
    return {**totals, "by_feature": by_feature}


def project_breakdown(projects) -> list[dict]:
    """One row per project. `projects` must already be scoped by the caller.

    The grouped queries filter on the ids of that scoped queryset, so they
    cannot reach a project the caller was not allowed to see.
    """
    rows = list(
        projects.order_by(F("last_activity_at").desc(nulls_last=True), "name")
        .values("id", "name", "space_id", "space__name", "last_activity_at")
    )
    ids = [row["id"] for row in rows]

    def grouped(model, **aggregates):
        query = model.objects.filter(project_id__in=ids).order_by().values("project_id").annotate(**aggregates)
        return {row["project_id"]: row for row in query}

    events = grouped(LearningEvent, n=Count("id"))
    materials = grouped(Material, n=Count("id"))
    mastery = grouped(ConceptMastery, n=Count("id"), avg=Avg("score"))
    answers = grouped(Attempt, n=Count("id"), avg=Avg("score"))

    return [
        {
            "project_id": row["id"],
            "name": row["name"],
            "space_id": row["space_id"],
            "space_name": row["space__name"],
            "last_activity_at": row["last_activity_at"],
            "events": events.get(row["id"], {}).get("n", 0),
            "materials": materials.get(row["id"], {}).get("n", 0),
            "concepts": mastery.get(row["id"], {}).get("n", 0),
            "average_mastery": optional_round(mastery.get(row["id"], {}).get("avg")),
            "questions_answered": answers.get(row["id"], {}).get("n", 0),
            "average_score": optional_round(answers.get(row["id"], {}).get("avg")),
        }
        for row in rows
    ]


def space_breakdown(spaces, project_rows: list[dict]) -> list[dict]:
    by_space = defaultdict(list)
    for row in project_rows:
        by_space[row["space_id"]].append(row)
    result = []
    for space in spaces.order_by("name").values("id", "name"):
        rows = by_space.get(space["id"], [])
        concepts = sum(r["concepts"] for r in rows)
        weighted = sum((r["average_mastery"] or 0) * r["concepts"] for r in rows)
        result.append(
            {
                "space_id": space["id"],
                "name": space["name"],
                "projects": len(rows),
                "events": sum(r["events"] for r in rows),
                "average_mastery": round(weighted / concepts, 4) if concepts else None,
            }
        )
    return result


def project_analytics(user, project) -> dict:
    """`project` must have been loaded with get_owned_or_404(Project, user, ...)."""
    trends = concept_trends(project)
    return {
        "project_id": project.id,
        "activity": activity_summary(LearningEvent.objects.for_user(user).filter(project=project)),
        "quiz": quiz_summary(
            QuizSession.objects.for_user(user).filter(project=project),
            Attempt.objects.for_user(user).filter(project=project),
        ),
        "mastery": mastery_summary(ConceptMastery.objects.for_user(user).filter(project=project)),
        "trends": trends,
        "trend_counts": dict(Counter(trend.label for trend in trends)),
        "ai": ai_summary(AICallLog.objects.for_user(user).filter(project=project)),
    }


def global_analytics(user) -> dict:
    project_rows = project_breakdown(Project.objects.for_user(user))
    return {
        "activity": activity_summary(LearningEvent.objects.for_user(user)),
        "quiz": quiz_summary(QuizSession.objects.for_user(user), Attempt.objects.for_user(user)),
        "mastery": mastery_summary(ConceptMastery.objects.for_user(user)),
        "ai": ai_summary(AICallLog.objects.for_user(user)),
        "spaces": space_breakdown(Space.objects.for_user(user), project_rows),
        "projects": project_rows,
    }
