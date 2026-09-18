import pytest
from pytest import approx

from common.testing import make_concept
from events.models import LearningEvent
from learning.mastery import apply_attempt, compute_new_score
from learning.models import ConceptMastery, MasterySnapshot
from learning.tests.factories import make_attempt

pytestmark = pytest.mark.django_db


# ---- compute_new_score: pure maths ---------------------------------------------------------

def test_first_correct_answer_moves_mastery_halfway():
    # alpha = max(0.15, 0.5 / (1 + 0)) = 0.5; weight(2) = 1.0; 0.3 + 0.5 * 1.0 * (1.0 - 0.3)
    assert compute_new_score(old=0.3, score=1.0, difficulty=2, evidence_count=0) == approx(0.65)


def test_hard_question_counts_more():
    # 0.3 + 0.5 * 1.2 * 0.7
    assert compute_new_score(old=0.3, score=1.0, difficulty=3, evidence_count=0) == approx(0.72)


def test_easy_question_counts_less():
    # 0.3 + 0.5 * 0.8 * 0.7
    assert compute_new_score(old=0.3, score=1.0, difficulty=1, evidence_count=0) == approx(0.58)


def test_alpha_shrinks_with_evidence():
    # alpha = 0.5 / (1 + 0.3 * 2) = 0.3125; 0.6 + 0.3125 * (0 - 0.6)
    assert compute_new_score(old=0.6, score=0.0, difficulty=2, evidence_count=2) == approx(0.4125)


def test_alpha_has_a_floor_of_point_15():
    # 0.5 / (1 + 0.3 * 10) = 0.125, so the floor 0.15 applies; 0.5 + 0.15 * 0.5
    assert compute_new_score(old=0.5, score=1.0, difficulty=2, evidence_count=10) == approx(0.575)


def test_partial_credit():
    # 0.4 + 0.5 * 1.0 * (0.5 - 0.4)
    assert compute_new_score(old=0.4, score=0.5, difficulty=2, evidence_count=0) == approx(0.45)


def test_unknown_difficulty_uses_weight_one():
    assert compute_new_score(old=0.3, score=1.0, difficulty=9, evidence_count=0) == approx(0.65)


def test_result_is_clamped_to_zero_and_one():
    assert compute_new_score(old=0.9, score=1.5, difficulty=3, evidence_count=0) == 1.0
    assert compute_new_score(old=0.1, score=-1.0, difficulty=3, evidence_count=0) == 0.0


# ---- apply_attempt: persistence and idempotency ---------------------------------------------

def test_apply_attempt_updates_mastery_and_writes_snapshot(project):
    concept = make_concept(project, "Photosynthesis")
    attempt = make_attempt(project, concept, score=1.0, difficulty=2)

    mastery = apply_attempt(attempt)

    assert mastery.score == approx(0.65)
    assert mastery.evidence_count == 1
    assert mastery.consecutive_misses == 0
    assert mastery.last_practiced_at is not None
    snapshot = MasterySnapshot.objects.get(attempt=attempt)
    assert snapshot.project_id == project.id
    assert snapshot.concept_id == concept.id
    assert snapshot.score == approx(0.65)
    assert snapshot.evidence_count == 1


def test_apply_attempt_twice_changes_mastery_once(project):
    concept = make_concept(project, "Photosynthesis")
    attempt = make_attempt(project, concept, score=1.0, difficulty=2)

    apply_attempt(attempt)
    mastery = apply_attempt(attempt)

    assert mastery.score == approx(0.65)
    assert mastery.evidence_count == 1
    assert MasterySnapshot.objects.filter(attempt=attempt).count() == 1
    assert LearningEvent.objects.filter(type="mastery.updated").count() == 1


def test_consecutive_misses_increment_then_reset(project):
    concept = make_concept(project, "Chloroplast")
    apply_attempt(make_attempt(project, concept, score=0.0))
    mastery = apply_attempt(make_attempt(project, concept, score=0.4))
    assert mastery.consecutive_misses == 2

    mastery = apply_attempt(make_attempt(project, concept, score=0.5))
    assert mastery.consecutive_misses == 0
    assert mastery.evidence_count == 3


def test_second_attempt_uses_the_reduced_alpha(project):
    concept = make_concept(project, "Stomata")
    apply_attempt(make_attempt(project, concept, score=1.0, difficulty=2))      # 0.3 -> 0.65
    mastery = apply_attempt(make_attempt(project, concept, score=1.0, difficulty=2))
    # alpha = 0.5 / 1.3; 0.65 + (0.5 / 1.3) * 0.35
    assert mastery.score == approx(0.65 + (0.5 / 1.3) * 0.35)


def test_apply_attempt_creates_missing_mastery_row(project):
    concept = make_concept(project, "Calvin cycle")
    ConceptMastery.objects.filter(project=project, concept=concept).delete()

    mastery = apply_attempt(make_attempt(project, concept, score=1.0, difficulty=2))

    assert mastery.score == approx(0.65)
    assert ConceptMastery.objects.filter(project=project, concept=concept).count() == 1


def test_apply_attempt_emits_mastery_updated_event(project):
    concept = make_concept(project, "Photosynthesis")
    attempt = make_attempt(project, concept, score=1.0, difficulty=2)

    apply_attempt(attempt)

    event = LearningEvent.objects.get(type="mastery.updated")
    assert event.idempotency_key == f"mastery:{attempt.id}"
    assert event.project_id == project.id
    assert event.user_id == project.owner_id
    assert event.payload["concept_id"] == str(concept.id)
    assert event.payload["new_score"] == approx(0.65)
