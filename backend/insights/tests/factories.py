from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from ai.models import AICallLog
from assessment.models import Attempt, Question, QuizSession
from events.models import LearningEvent


def make_event(user, *, project=None, space=None, type="tutor.message_sent", days_ago=0, payload=None):
    event = LearningEvent.objects.create(
        user=user, project=project, space=space, type=type, payload=payload or {}
    )
    if days_ago:
        # created_at is auto_now_add, so it can only be moved with update().
        LearningEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        event.refresh_from_db()
    return event


def make_ai_call(user, *, project=None, feature="tutor", model="fake-fast", status="ok",
                 latency_ms=200, input_tokens=100, output_tokens=50, cost="0.001",
                 error_type="", minutes_ago=0):
    log = AICallLog.objects.create(
        user=user, project=project, feature=feature, provider="fake", model=model,
        latency_ms=latency_ms, input_tokens=input_tokens, output_tokens=output_tokens,
        estimated_cost_usd=Decimal(cost), status=status, error_type=error_type,
        retries=0, retrieved_chunk_ids=[], trace_id="",
    )
    if minutes_ago:
        AICallLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        log.refresh_from_db()
    return log


def make_session(project, concept, scores, *, completed=True, days_ago=0):
    """A quiz session with one answered MCQ per score in `scores`."""
    when = timezone.now() - timedelta(days=days_ago)
    session = QuizSession.objects.create(
        project=project,
        status=QuizSession.Status.COMPLETED if completed else QuizSession.Status.ACTIVE,
        target_question_count=max(len(scores), 1),
        completed_at=when if completed else None,
    )
    for score in scores:
        question = Question.objects.create(
            project=project, session=session, concept=concept, type=Question.Type.MCQ,
            difficulty=1, body="Which one?", options=["a", "b", "c", "d"], correct_option=0,
            rubric={},
        )
        Attempt.objects.create(
            question=question, project=project, selected_option=0, answer_text="",
            score=score, feedback={}, evaluated_at=when,
        )
    return session
