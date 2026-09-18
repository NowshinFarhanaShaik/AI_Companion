"""Persistent learner context: store durable facts, retrieve only the ones relevant to a request."""
import logging
from collections import Counter
from datetime import timedelta

from django.utils import timezone
from pgvector.django import CosineDistance

from ai.client import embed_texts
from ai.types import AIError
from assessment.models import Attempt
from learning.models import ConceptMastery, LearnerMemory

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 2000
REPEAT_MISS_THRESHOLD = 3
REPEAT_MISCONCEPTION_THRESHOLD = 2
REPEAT_DEDUPE_DAYS = 7
RECENT_ATTEMPTS_SCANNED = 10


def record_memory(*, project, kind: str, content: str, concept=None, salience: float = 0.5) -> LearnerMemory:
    """Store one memory. An embedding failure is not fatal: the row is kept without a vector."""
    if kind not in LearnerMemory.Kind.values:
        raise ValueError(f"Unknown memory kind: {kind}")
    content = (content or "").strip()[:MAX_CONTENT_CHARS]
    if not content:
        raise ValueError("Memory content is empty")
    try:
        embedding = embed_texts([content], user=project.owner, project=project)[0]
    except AIError as exc:
        logger.warning("Could not embed learner memory for project %s: %s", project.id, exc)
        embedding = None
    return LearnerMemory.objects.create(
        project=project, kind=kind, content=content, concept=concept,
        salience=min(1.0, max(0.0, salience)), embedding=embedding,
    )


def relevant_memories(*, project, vector: list[float], k: int = 3) -> list[LearnerMemory]:
    return list(
        LearnerMemory.objects.filter(project=project, embedding__isnull=False)
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance", "-salience")[:k]
    )


def _repeated_misconception(project, concept) -> str | None:
    """A misconception that appears in at least two recent attempts of the concept, compared case-insensitively."""
    counts: Counter = Counter()
    wording: dict[str, str] = {}
    for feedback in (
        Attempt.objects.filter(project=project, question__concept=concept)
        .order_by("-evaluated_at")
        .values_list("feedback", flat=True)[:RECENT_ATTEMPTS_SCANNED]
    ):
        keys = set()
        for item in feedback.get("misconceptions", []):
            key = " ".join(item.lower().split())
            if key:
                keys.add(key)
                wording.setdefault(key, item.strip())
        counts.update(keys)
    key, count = counts.most_common(1)[0] if counts else (None, 0)
    return wording[key] if count >= REPEAT_MISCONCEPTION_THRESHOLD else None


def detect_repeated_mistakes(project, concept) -> LearnerMemory | None:
    """Record a repeated_mistake memory when a pattern shows, at most once per concept per week."""
    since = timezone.now() - timedelta(days=REPEAT_DEDUPE_DAYS)
    if LearnerMemory.objects.filter(
        project=project, concept=concept, kind=LearnerMemory.Kind.REPEATED_MISTAKE, created_at__gte=since
    ).exists():
        return None

    misconception = _repeated_misconception(project, concept)
    mastery = ConceptMastery.objects.filter(project=project, concept=concept).first()
    misses = mastery.consecutive_misses if mastery else 0
    if misconception:
        content = f"Repeated misconception about {concept.name}: {misconception}"
    elif misses >= REPEAT_MISS_THRESHOLD:
        content = f"Missed {misses} questions in a row on {concept.name}."
    else:
        return None
    return record_memory(
        project=project, kind=LearnerMemory.Kind.REPEATED_MISTAKE, content=content, concept=concept, salience=0.9
    )
