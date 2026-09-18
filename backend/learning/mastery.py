from django.db import transaction

from events.services import emit
from learning.models import ConceptMastery, MasterySnapshot

DIFFICULTY_WEIGHT = {1: 0.8, 2: 1.0, 3: 1.2}
MISS_THRESHOLD = 0.5
INITIAL_SCORE = 0.3


def compute_new_score(*, old: float, score: float, difficulty: int, evidence_count: int) -> float:
    """Return the new mastery estimate (0–1) after one graded attempt.

    The estimate moves from `old` towards `score`: fast while there is little evidence, so early answers
    count, and slower as evidence builds, so one lucky guess cannot look like mastery. The learning rate
    never drops below 0.15, so a learner who later forgets a concept is still noticed. Harder questions
    are stronger evidence (spec §8).
    """
    alpha = max(0.15, 0.5 / (1 + 0.3 * evidence_count))
    new = old + alpha * DIFFICULTY_WEIGHT.get(difficulty, 1.0) * (score - old)
    return min(1.0, max(0.0, new))


def apply_attempt(attempt) -> ConceptMastery:
    """Apply one graded attempt to its concept's mastery. Safe to call twice for the same attempt.

    The MasterySnapshot.attempt one-to-one is the idempotency key. The mastery row is locked first,
    so two updates racing on the same concept run one after the other.
    """
    question = attempt.question
    project = attempt.project
    with transaction.atomic():
        mastery, _ = ConceptMastery.objects.select_for_update().get_or_create(
            project=project, concept=question.concept, defaults={"score": INITIAL_SCORE}
        )
        if MasterySnapshot.objects.filter(attempt=attempt).exists():
            return mastery

        old_score = mastery.score
        mastery.score = compute_new_score(
            old=old_score, score=attempt.score, difficulty=question.difficulty, evidence_count=mastery.evidence_count
        )
        mastery.evidence_count += 1
        mastery.last_practiced_at = attempt.evaluated_at
        mastery.consecutive_misses = mastery.consecutive_misses + 1 if attempt.score < MISS_THRESHOLD else 0
        mastery.save()

        MasterySnapshot.objects.create(
            project=project, concept=question.concept, score=mastery.score,
            evidence_count=mastery.evidence_count, attempt=attempt,
        )
        emit(
            type="mastery.updated", user=project.owner, project=project,
            payload={
                "concept_id": str(question.concept_id),
                "concept_name": question.concept.name,
                "attempt_id": str(attempt.id),
                "old_score": round(old_score, 4),
                "new_score": round(mastery.score, 4),
            },
            idempotency_key=f"mastery:{attempt.id}",
        )
    return mastery
