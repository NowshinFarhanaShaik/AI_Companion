"""Learning workflows: quiz.completed -> update_mastery -> detect_weakness -> generate_recommendation.

Event handlers run inside the emitter's transaction and only enqueue jobs, with one exception noted below.
Each job reloads its project through the scoped manager as the payload's user, so a job can never act on a
project that user does not own, and every step is safe to run twice.
"""
import logging

from django.contrib.auth import get_user_model

from assessment.models import Attempt
from events.registry import job_handler, on_event
from events.services import enqueue
from learning.mastery import apply_attempt
from learning.memory import detect_repeated_mistakes
from learning.recommendations import generate_recommendation
from materials.models import Concept
from workspace.models import Project

logger = logging.getLogger(__name__)


def _attempts(user):
    return Attempt.objects.for_user(user).select_related("question__concept", "project")


@on_event("question.answered")
def on_question_answered(event):
    # The one handler that does work directly: the next question of the same quiz is chosen from mastery,
    # so waiting for the worker would make the quiz adapt one question late. The update is arithmetic only,
    # and update_mastery re-applies it later as a no-op safety net.
    attempt = _attempts(event.user).filter(id=event.payload.get("attempt_id")).first()
    if attempt is not None:
        apply_attempt(attempt)


@on_event("quiz.completed")
def on_quiz_completed(event):
    session_id = event.payload["session_id"]
    enqueue(
        "update_mastery",
        {"user_id": str(event.user_id), "project_id": str(event.project_id), "session_id": session_id},
        idempotency_key=f"update-mastery:{session_id}",
    )


@on_event("material.processed")
def on_material_processed(event):
    enqueue(
        "generate_recommendation",
        {"user_id": str(event.user_id), "project_id": str(event.project_id)},
        idempotency_key=f"recommend:material:{event.payload['material_id']}",
    )


def _load_project(job):
    user = get_user_model().objects.filter(id=job.payload["user_id"], is_active=True).first()
    project = Project.objects.for_user(user).filter(id=job.payload["project_id"]).first() if user else None
    if project is None:
        logger.info("%s job %s: the project is gone or not owned by the payload's user", job.type, job.id)
    return project


@job_handler("update_mastery")
def update_mastery_job(job):
    project = _load_project(job)
    if project is None:
        return
    session_id = job.payload["session_id"]
    for attempt in _attempts(project.owner).filter(question__session_id=session_id).order_by("evaluated_at"):
        apply_attempt(attempt)
    enqueue("detect_weakness", job.payload, idempotency_key=f"detect-weakness:{session_id}")


@job_handler("detect_weakness")
def detect_weakness_job(job):
    project = _load_project(job)
    if project is None:
        return
    session_id = job.payload["session_id"]
    for concept in Concept.objects.filter(project=project, questions__session_id=session_id).distinct():
        detect_repeated_mistakes(project, concept)
    enqueue("generate_recommendation", job.payload, idempotency_key=f"recommend:session:{session_id}")


@job_handler("generate_recommendation")
def generate_recommendation_job(job):
    project = _load_project(job)
    if project is not None:
        generate_recommendation(project)
