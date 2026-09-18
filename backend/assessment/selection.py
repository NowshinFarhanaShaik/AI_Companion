"""Adaptive question selection. Deterministic code, no LLM: the evidence decides what to practise."""
import random
from dataclasses import dataclass

from django.utils import timezone

from assessment.models import Attempt, Question
from learning.models import ConceptMastery
from materials.models import Concept, Material

NEW_CONCEPT_SCORE = 0.3
RECENT_WINDOW = 5
MISS_THRESHOLD = 0.5


@dataclass
class Selection:
    concept: Concept
    difficulty: int
    qtype: str


def compute_priority(*, mastery: float, evidence_count: int, recent_miss_rate: float,
                     days_since_practiced: float | None, asked_in_session: bool) -> float:
    """How much this concept deserves the next question. Higher means practise it sooner.

    Inputs:
      mastery               current estimate, 0–1
      evidence_count        how many graded attempts back that estimate
      recent_miss_rate      share of the last five attempts scored below 0.5, 0–1
      days_since_practiced  None when the concept was never practised
      asked_in_session      True when this quiz session already asked about the concept

    Weakness carries the most weight, recent mistakes next, then uncertainty and staleness (spec §7.1).
    The in-session penalty spreads one quiz across several concepts.
    """
    uncertainty = 1.0 / (1 + evidence_count)
    staleness = 1.0 if days_since_practiced is None else min(days_since_practiced / 14.0, 1.0)
    priority = 0.40 * (1.0 - mastery) + 0.20 * uncertainty + 0.25 * recent_miss_rate + 0.15 * staleness
    return priority - 0.30 if asked_in_session else priority


def difficulty_for(score: float, consecutive_misses: int) -> int:
    if score < 0.4:
        difficulty = 1
    elif score <= 0.7:
        difficulty = 2
    else:
        difficulty = 3
    if consecutive_misses >= 2:
        difficulty = max(1, difficulty - 1)
    return difficulty


def question_type_for(difficulty: int, question_number: int) -> str:
    """`question_number` is the 1-based position of the question about to be generated."""
    if difficulty == 3 or question_number % 3 == 0:
        return Question.Type.OPEN
    return Question.Type.MCQ


def recent_miss_rate(concept) -> float:
    scores = list(
        Attempt.objects.filter(question__concept=concept)
        .order_by("-created_at")
        .values_list("score", flat=True)[:RECENT_WINDOW]
    )
    if not scores:
        return 0.0
    return sum(1 for score in scores if score < MISS_THRESHOLD) / len(scores)


def eligible_concepts(project):
    """Concepts that have at least one chunk in a processed material, so a question can be grounded."""
    return (
        Concept.objects.filter(project=project, chunks__material__status=Material.Status.READY)
        .distinct()
    )


def select_next(*, project, session) -> Selection | None:
    concepts = list(eligible_concepts(project))
    if not concepts:
        return None

    masteries = {m.concept_id: m for m in ConceptMastery.objects.filter(project=project)}
    asked_ids = set(session.questions.values_list("concept_id", flat=True))
    now = timezone.now()

    ranked = []
    for concept in concepts:
        mastery = masteries.get(concept.id)
        score = mastery.score if mastery else NEW_CONCEPT_SCORE
        evidence = mastery.evidence_count if mastery else 0
        last = mastery.last_practiced_at if mastery else None
        days = None if last is None else (now - last).total_seconds() / 86400
        value = compute_priority(
            mastery=score,
            evidence_count=evidence,
            recent_miss_rate=recent_miss_rate(concept),
            days_since_practiced=days,
            asked_in_session=concept.id in asked_ids,
        )
        ranked.append((round(value, 6), concept.importance, random.random(), concept))

    _, _, _, chosen = max(ranked, key=lambda row: row[:3])
    chosen_mastery = masteries.get(chosen.id)
    difficulty = difficulty_for(
        chosen_mastery.score if chosen_mastery else NEW_CONCEPT_SCORE,
        chosen_mastery.consecutive_misses if chosen_mastery else 0,
    )
    question_number = session.questions.count() + 1
    return Selection(concept=chosen, difficulty=difficulty, qtype=question_type_for(difficulty, question_number))
