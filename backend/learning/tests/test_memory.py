import pytest
from datetime import timedelta

from django.utils import timezone

from ai.testing import fake_embedding
from ai.types import AIError
from common.testing import make_concept
from learning.memory import detect_repeated_mistakes, record_memory, relevant_memories
from learning.models import ConceptMastery, LearnerMemory
from learning.tests.factories import make_attempt

pytestmark = pytest.mark.django_db


def test_record_memory_stores_an_embedding(project):
    memory = record_memory(project=project, kind="preference", content="Prefers short worked examples")

    assert memory.project_id == project.id
    assert memory.kind == "preference"
    assert memory.salience == 0.5
    assert memory.embedding is not None
    assert len(memory.embedding) == 768


def test_record_memory_survives_an_embedding_failure(project, fake_ai):
    fake_ai.queue_error(AIError("embedding service down"))

    memory = record_memory(project=project, kind="note", content="Struggles with the light reactions")

    assert memory.pk is not None
    assert memory.embedding is None


def test_record_memory_rejects_an_unknown_kind(project):
    with pytest.raises(ValueError):
        record_memory(project=project, kind="secret", content="x")


def test_relevant_memories_orders_by_similarity(project):
    record_memory(project=project, kind="note", content="mitochondria produce ATP energy")
    wanted = record_memory(project=project, kind="weakness", content="photosynthesis converts light energy in chloroplasts")

    found = relevant_memories(project=project, vector=fake_embedding("how does photosynthesis use light"), k=1)

    assert [m.id for m in found] == [wanted.id]


def test_relevant_memories_is_project_scoped_and_skips_null_embeddings(project, other_project):
    record_memory(project=other_project, kind="note", content="photosynthesis converts light energy")
    LearnerMemory.objects.create(project=project, kind="note", content="photosynthesis without a vector", embedding=None)
    mine = record_memory(project=project, kind="note", content="photosynthesis converts light energy")

    found = relevant_memories(project=project, vector=fake_embedding("photosynthesis light"), k=5)

    assert [m.id for m in found] == [mine.id]


def test_three_consecutive_misses_write_a_repeated_mistake_memory(project):
    concept = make_concept(project, "Light reactions")
    ConceptMastery.objects.filter(project=project, concept=concept).update(consecutive_misses=3)

    memory = detect_repeated_mistakes(project, concept)

    assert memory.kind == "repeated_mistake"
    assert memory.concept_id == concept.id
    assert memory.salience == 0.9
    assert "Light reactions" in memory.content


def test_two_consecutive_misses_write_nothing(project):
    concept = make_concept(project, "Light reactions")
    ConceptMastery.objects.filter(project=project, concept=concept).update(consecutive_misses=2)

    assert detect_repeated_mistakes(project, concept) is None
    assert LearnerMemory.objects.count() == 0


def test_same_misconception_in_two_attempts_writes_a_memory(project):
    concept = make_concept(project, "Light reactions")
    make_attempt(project, concept, score=0.4, qtype="open",
                 misconceptions=["Thinks oxygen comes from carbon dioxide"])
    make_attempt(project, concept, score=0.6, qtype="open",
                 misconceptions=["  thinks OXYGEN comes from carbon dioxide ", "Other"])

    memory = detect_repeated_mistakes(project, concept)

    assert memory is not None
    assert "oxygen comes from carbon dioxide" in memory.content.lower()


def test_a_misconception_seen_once_writes_nothing(project):
    concept = make_concept(project, "Light reactions")
    make_attempt(project, concept, score=0.4, qtype="open", misconceptions=["Confuses ATP with ADP"])

    assert detect_repeated_mistakes(project, concept) is None


def test_no_duplicate_memory_within_seven_days(project):
    concept = make_concept(project, "Light reactions")
    ConceptMastery.objects.filter(project=project, concept=concept).update(consecutive_misses=4)

    first = detect_repeated_mistakes(project, concept)
    second = detect_repeated_mistakes(project, concept)

    assert first is not None
    assert second is None
    assert LearnerMemory.objects.filter(kind="repeated_mistake").count() == 1


def test_a_new_memory_is_written_after_seven_days(project):
    concept = make_concept(project, "Light reactions")
    ConceptMastery.objects.filter(project=project, concept=concept).update(consecutive_misses=4)
    first = detect_repeated_mistakes(project, concept)
    LearnerMemory.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(days=8))

    second = detect_repeated_mistakes(project, concept)

    assert second is not None
    assert LearnerMemory.objects.filter(kind="repeated_mistake").count() == 2
