from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from learning.models import ConceptMastery, MasterySnapshot
from materials.models import Concept


@dataclass
class Trend:
    concept: Concept
    score: float
    delta: float
    label: str
    evidence_count: int


def label_trend(*, latest: float, earliest: float, snapshot_count: int, evidence_count: int) -> str:
    """Label one concept's movement inside the window (spec §8).

    A clear rise wins even when the score is still low, so progress is recognised. A clear drop, or a
    low score backed by at least two answers, needs attention. A single low answer is not yet a signal.
    """
    if snapshot_count < 2:
        return "not_enough_data"
    delta = latest - earliest
    if delta > 0.08:
        return "improving"
    if delta < -0.05 or (latest < 0.5 and evidence_count >= 2):
        return "needs_attention"
    return "stable"


def concept_trends(project, *, days: int = 14) -> list[Trend]:
    """One Trend per concept that has a mastery row, weakest first. Two queries regardless of size."""
    since = timezone.now() - timedelta(days=days)
    scores: dict = defaultdict(list)
    for concept_id, score in (
        MasterySnapshot.objects.filter(project=project, created_at__gte=since)
        .order_by("created_at")
        .values_list("concept_id", "score")
    ):
        scores[concept_id].append(score)

    trends = []
    for mastery in ConceptMastery.objects.filter(project=project).select_related("concept"):
        window = scores.get(mastery.concept_id) or [mastery.score]
        trends.append(Trend(
            concept=mastery.concept,
            score=mastery.score,
            delta=round(window[-1] - window[0], 4),
            label=label_trend(
                latest=window[-1], earliest=window[0],
                snapshot_count=len(scores.get(mastery.concept_id, [])), evidence_count=mastery.evidence_count,
            ),
            evidence_count=mastery.evidence_count,
        ))
    return sorted(trends, key=lambda trend: (trend.score, trend.concept.name))
