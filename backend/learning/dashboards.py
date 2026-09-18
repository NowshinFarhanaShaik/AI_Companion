"""Read-only queries behind the learning endpoints. Results are shaped by the schemas in learning/schemas.py."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, F
from django.utils import timezone

from assessment.models import Attempt, QuizSession
from events.models import LearningEvent
from learning.growth import concept_trends
from learning.models import ConceptMastery, MasterySnapshot, Recommendation
from learning.recommendations import active_recommendation
from materials.models import Material
from workspace.models import Project

RECENT_ACTIVITY_LIMIT = 8
TOP_CONCEPTS_LIMIT = 5
ATTENTION_LIMIT = 5
RECENT_PROJECTS_LIMIT = 6
SERIES_DAYS = 90
RECENTLY_ACTIVE_FIRST = (F("last_activity_at").desc(nulls_last=True), "-created_at")


def weighted_progress(rows) -> float:
    """Mean mastery weighted by concept importance. `rows` holds (score, importance) pairs."""
    rows = list(rows)
    total_weight = sum(weight for _, weight in rows)
    return round(sum(score * weight for score, weight in rows) / total_weight, 4) if total_weight else 0.0


def masteries(project):
    return ConceptMastery.objects.filter(project=project).select_related("concept").order_by("-score", "concept__name")


def _attention(project) -> list:
    return [trend for trend in concept_trends(project) if trend.label == "needs_attention"]


def growth_payload(project) -> dict:
    since = timezone.now() - timedelta(days=SERIES_DAYS)
    points: dict = defaultdict(list)
    for concept_id, created_at, score in (
        MasterySnapshot.objects.filter(project=project, created_at__gte=since)
        .order_by("created_at")
        .values_list("concept_id", "created_at", "score")
    ):
        points[concept_id].append({"at": created_at, "score": score})
    trends = concept_trends(project)
    return {
        "trends": trends,
        "series": [
            {"concept_id": trend.concept.id, "name": trend.concept.name, "points": points[trend.concept.id]}
            for trend in trends
            if points.get(trend.concept.id)
        ],
    }


def _latest_quiz(project) -> dict | None:
    session = (
        QuizSession.objects.filter(project=project, status=QuizSession.Status.COMPLETED)
        .order_by(F("completed_at").desc(nulls_last=True))
        .first()
    )
    if session is None:
        return None
    stats = Attempt.objects.filter(question__session=session).aggregate(average=Avg("score"), answered=Count("id"))
    return {
        "session_id": session.id,
        "completed_at": session.completed_at,
        "question_count": stats["answered"],
        "average_score": round(stats["average"] or 0.0, 4),
    }


def project_dashboard(project) -> dict:
    rows = list(masteries(project))
    material_counts = dict.fromkeys(Material.Status.values, 0)
    material_counts.update(
        Material.objects.filter(project=project).values("status").annotate(n=Count("id")).values_list("status", "n")
    )
    return {
        "project_id": project.id,
        "name": project.name,
        "learning_goal": project.learning_goal,
        "overall_progress": weighted_progress((m.score, m.concept.importance) for m in rows),
        "concept_count": len(rows),
        "top_concepts": rows[:TOP_CONCEPTS_LIMIT],
        "attention_concepts": _attention(project)[:ATTENTION_LIMIT],
        "recent_activity": LearningEvent.objects.filter(project=project).order_by("-created_at")[:RECENT_ACTIVITY_LIMIT],
        "latest_quiz": _latest_quiz(project),
        "material_counts": material_counts,
        "recommendation": active_recommendation(project),
    }


def _summaries(projects) -> tuple[list[dict], dict]:
    """Per-project progress and attention for a small list of projects. Returns (summaries, attention by id)."""
    pairs: dict = defaultdict(list)
    for project_id, score, importance in ConceptMastery.objects.filter(project__in=projects).values_list(
        "project_id", "score", "concept__importance"
    ):
        pairs[project_id].append((score, importance))
    attention = {project.id: _attention(project) for project in projects}
    summaries = [
        {
            "id": project.id,
            "name": project.name,
            "space_id": project.space_id,
            "space_name": project.space.name,
            "overall_progress": weighted_progress(pairs[project.id]),
            "concept_count": len(pairs[project.id]),
            "attention_count": len(attention[project.id]),
            "last_activity_at": project.last_activity_at,
        }
        for project in projects
    ]
    return summaries, attention


def space_dashboard(space, user) -> dict:
    projects = list(
        Project.objects.for_user(user).filter(space=space).select_related("space").order_by(*RECENTLY_ACTIVE_FIRST)
    )
    summaries, _ = _summaries(projects)
    return {
        "space_id": space.id,
        "name": space.name,
        "project_count": len(projects),
        "overall_progress": weighted_progress(
            ConceptMastery.objects.filter(project__in=projects).values_list("score", "concept__importance")
        ),
        "projects": summaries,
        "recent_activity": LearningEvent.objects.filter(user=user, project__in=projects)
        .order_by("-created_at")[:RECENT_ACTIVITY_LIMIT],
    }


def home(user) -> dict:
    recent = list(
        Project.objects.for_user(user).select_related("space").order_by(*RECENTLY_ACTIVE_FIRST)[:RECENT_PROJECTS_LIMIT]
    )
    summaries, attention = _summaries(recent)
    areas = sorted(
        (
            {
                "project_id": project.id,
                "project_name": project.name,
                "concept_id": trend.concept.id,
                "concept_name": trend.concept.name,
                "score": trend.score,
                "label": trend.label,
            }
            for project in recent
            for trend in attention[project.id]
        ),
        key=lambda area: area["score"],
    )
    # Prefer the next step for the project the learner was last in; otherwise the newest one anywhere.
    next_action = (active_recommendation(recent[0]) if recent else None) or (
        Recommendation.objects.for_user(user)
        .filter(status=Recommendation.Status.ACTIVE)
        .select_related("project", "concept")
        .order_by("-created_at")
        .first()
    )
    return {
        "continue_learning": summaries[0] if summaries else None,
        "recent_projects": summaries,
        "overall_progress": weighted_progress(
            ConceptMastery.objects.for_user(user).values_list("score", "concept__importance")
        ),
        "attention_areas": areas[:ATTENTION_LIMIT],
        "next_action": next_action,
    }
