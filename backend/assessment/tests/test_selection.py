from datetime import timedelta

import pytest
from django.utils import timezone

from assessment.models import Attempt, Question, QuizSession
from assessment.selection import (
    Selection,
    compute_priority,
    difficulty_for,
    eligible_concepts,
    question_type_for,
    recent_miss_rate,
    select_next,
)
from common.testing import make_chunk, make_concept, make_material
from learning.models import ConceptMastery

pytestmark = pytest.mark.django_db

BASE = dict(mastery=0.5, evidence_count=3, recent_miss_rate=0.0, days_since_practiced=0.0, asked_in_session=False)


def priority(**overrides):
    return compute_priority(**{**BASE, **overrides})


# ---------- compute_priority (pure function) ----------

def test_priority_matches_the_spec_formula():
    # Spec §7.1. If the project owner deliberately chooses other weights, change this test and the spec together.
    value = compute_priority(
        mastery=0.5, evidence_count=1, recent_miss_rate=0.4, days_since_practiced=7.0, asked_in_session=False
    )
    # 0.40*0.5 + 0.20*(1/2) + 0.25*0.4 + 0.15*(7/14) = 0.475
    assert value == pytest.approx(0.475)


def test_weak_concept_beats_strong_concept():
    assert priority(mastery=0.2) > priority(mastery=0.9)


def test_uncertain_concept_beats_well_evidenced_concept_at_equal_mastery():
    assert priority(evidence_count=0) > priority(evidence_count=10)


def test_recent_mistakes_raise_priority():
    assert priority(recent_miss_rate=0.8) > priority(recent_miss_rate=0.0)


def test_stale_concept_beats_fresh_concept():
    assert priority(days_since_practiced=10.0) > priority(days_since_practiced=0.0)


def test_never_practised_counts_as_fully_stale_and_staleness_is_capped():
    assert priority(days_since_practiced=None) == pytest.approx(priority(days_since_practiced=14.0))
    assert priority(days_since_practiced=60.0) == pytest.approx(priority(days_since_practiced=14.0))


def test_asked_in_session_penalty_is_point_three():
    assert priority(asked_in_session=False) - priority(asked_in_session=True) == pytest.approx(0.30)


# ---------- difficulty and type rules ----------

@pytest.mark.parametrize(
    "score, misses, expected",
    [(0.2, 0, 1), (0.39, 0, 1), (0.4, 0, 2), (0.7, 0, 2), (0.71, 0, 3), (0.9, 2, 2), (0.5, 2, 1), (0.2, 3, 1)],
)
def test_difficulty_bands_and_consecutive_miss_reduction(score, misses, expected):
    assert difficulty_for(score, misses) == expected


@pytest.mark.parametrize(
    "difficulty, number, expected",
    [(1, 1, "mcq"), (2, 2, "mcq"), (1, 3, "open"), (3, 1, "open"), (2, 6, "open"), (2, 4, "mcq")],
)
def test_question_type_rule(difficulty, number, expected):
    assert question_type_for(difficulty, number) == expected


# ---------- database-backed helpers ----------

def _concept(project, material, name, *, mastery=0.5, evidence_count=3, importance=3,
             practiced_days_ago=0, consecutive_misses=0):
    chunk = make_chunk(project, material, f"{name} is explained here in detail.", page=1,
                       index=material.chunks.count())
    concept = make_concept(project, name, chunks=[chunk], importance=importance,
                           mastery=mastery, evidence_count=evidence_count)
    last = None if practiced_days_ago is None else timezone.now() - timedelta(days=practiced_days_ago)
    ConceptMastery.objects.filter(concept=concept).update(
        last_practiced_at=last, consecutive_misses=consecutive_misses
    )
    return concept


def _question(project, session, concept):
    return Question.objects.create(
        project=project, session=session, concept=concept, type=Question.Type.MCQ, difficulty=1,
        body="Which one?", options=["a", "b", "c", "d"], correct_option=0,
    )


def _attempt(project, session, concept, score):
    question = _question(project, session, concept)
    return Attempt.objects.create(
        question=question, project=project, selected_option=0, score=score, evaluated_at=timezone.now()
    )


@pytest.fixture
def material(project):
    return make_material(project, status="ready")


@pytest.fixture
def session(project):
    return QuizSession.objects.create(project=project)


def test_recent_miss_rate_uses_only_the_last_five_attempts(project, material, session):
    concept = _concept(project, material, "Enzymes")
    assert recent_miss_rate(concept) == 0.0
    for score in [0.0, 1.0, 1.0, 1.0, 0.2, 0.4]:      # oldest first; the first 0.0 falls outside the window
        _attempt(project, session, concept, score)
    assert recent_miss_rate(concept) == pytest.approx(2 / 5)


def test_select_next_returns_none_without_concepts(project, session):
    assert select_next(project=project, session=session) is None


def test_concepts_without_ready_material_are_not_eligible(project, session):
    queued = make_material(project, title="Pending", status="queued")
    _concept(project, queued, "Unprocessed")
    assert eligible_concepts(project).count() == 0
    assert select_next(project=project, session=session) is None


def test_select_next_prefers_the_weak_concept(project, material, session):
    _concept(project, material, "Strong", mastery=0.9)
    weak = _concept(project, material, "Weak", mastery=0.2)
    selection = select_next(project=project, session=session)
    assert isinstance(selection, Selection)
    assert selection.concept == weak
    assert selection.difficulty == 1
    assert selection.qtype == "mcq"


def test_select_next_prefers_the_stale_concept(project, material, session):
    _concept(project, material, "Fresh", practiced_days_ago=0)
    stale = _concept(project, material, "Stale", practiced_days_ago=20)
    assert select_next(project=project, session=session).concept == stale


def test_select_next_prefers_the_concept_with_recent_mistakes(project, material, session):
    _concept(project, material, "Steady")
    shaky = _concept(project, material, "Shaky")
    earlier = QuizSession.objects.create(project=project, status=QuizSession.Status.COMPLETED)
    for score in [0.0, 0.0, 1.0]:
        _attempt(project, earlier, shaky, score)
    assert select_next(project=project, session=session).concept == shaky


def test_ties_break_on_importance_then_asked_concepts_are_penalised(project, material, session):
    major = _concept(project, material, "Major", importance=5)
    minor = _concept(project, material, "Minor", importance=2)
    assert select_next(project=project, session=session).concept == major
    _question(project, session, major)               # asked in this session
    assert select_next(project=project, session=session).concept == minor


def test_selection_never_crosses_projects(project, other_project, material, session):
    other_material = make_material(other_project, status="ready")
    _concept(other_project, other_material, "Foreign", mastery=0.0)
    mine = _concept(project, material, "Mine", mastery=0.9)
    assert select_next(project=project, session=session).concept == mine


def test_difficulty_and_type_come_from_mastery_and_position(project, material, session):
    expert = _concept(project, material, "Expert topic", mastery=0.85)
    assert select_next(project=project, session=session).difficulty == 3
    assert select_next(project=project, session=session).qtype == "open"          # difficulty 3 is always open

    ConceptMastery.objects.filter(concept=expert).update(consecutive_misses=2)
    assert select_next(project=project, session=session).difficulty == 2          # lowered by one after two misses

    ConceptMastery.objects.filter(concept=expert).update(score=0.5, consecutive_misses=0)
    _question(project, session, expert)
    _question(project, session, expert)
    third = select_next(project=project, session=session)                         # third question of the session
    assert third.difficulty == 2
    assert third.qtype == "open"


def test_a_concept_without_a_mastery_row_is_treated_as_new(project, material, session):
    concept = _concept(project, material, "Orphan")
    ConceptMastery.objects.filter(concept=concept).delete()
    selection = select_next(project=project, session=session)
    assert selection.concept == concept
    assert selection.difficulty == 1
