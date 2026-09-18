"""Test helpers for building quiz attempts and mastery snapshots directly in the database."""
from datetime import timedelta

from django.utils import timezone

from assessment.models import Attempt, Question, QuizSession
from learning.models import MasterySnapshot


def make_session(project, *, status="active", target=5):
    return QuizSession.objects.create(
        project=project, status=status, target_question_count=target
    )


def make_attempt(project, concept, *, score, difficulty=2, session=None, qtype="mcq",
                 misconceptions=()):
    """Create a Question and its graded Attempt for `concept`."""
    session = session or make_session(project)
    is_mcq = qtype == "mcq"
    question = Question.objects.create(
        project=project,
        session=session,
        concept=concept,
        type=qtype,
        difficulty=difficulty,
        body=f"Question about {concept.name}?",
        options=["A", "B", "C", "D"] if is_mcq else [],
        correct_option=0 if is_mcq else None,
        rubric={} if is_mcq else {"key_points": ["key point"]},
        source_chunk=None,
    )
    return Attempt.objects.create(
        question=question,
        project=project,
        answer_text="" if is_mcq else "my answer",
        selected_option=0 if is_mcq else None,
        score=score,
        feedback={
            "understood": [],
            "missing": [],
            "misconceptions": list(misconceptions),
            "feedback": "",
        },
        evaluated_at=timezone.now(),
    )


def make_snapshot(project, concept, score, *, days_ago=0, evidence_count=1):
    """Create a MasterySnapshot and backdate it (created_at is auto_now_add, so update it after)."""
    snapshot = MasterySnapshot.objects.create(
        project=project, concept=concept, score=score, evidence_count=evidence_count
    )
    if days_ago:
        backdated = timezone.now() - timedelta(days=days_ago)
        MasterySnapshot.objects.filter(pk=snapshot.pk).update(created_at=backdated)
        snapshot.refresh_from_db()
    return snapshot
