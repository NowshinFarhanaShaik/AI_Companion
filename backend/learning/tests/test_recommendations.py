import pytest
from datetime import timedelta

from django.utils import timezone

from ai.types import AIError
from common.testing import make_chunk, make_concept, make_material
from events.models import LearningEvent
from learning.memory import record_memory
from learning.models import ConceptMastery, Recommendation
from learning.recommendations import (
    active_recommendation,
    complete_recommendation,
    generate_recommendation,
    pick_target,
)
from learning.tests.factories import make_snapshot

pytestmark = pytest.mark.django_db


def _weak_concept(project, name="Chloroplast", page=4):
    """A concept labelled needs_attention: two snapshots in the window, falling, score below 0.5."""
    material = make_material(project, title="Biology Notes", status="ready")
    chunk = make_chunk(project, material, f"{name} is covered on this page", page=page)
    concept = make_concept(project, name, chunks=(chunk,), mastery=0.35, evidence_count=3)
    make_snapshot(project, concept, 0.45, days_ago=3, evidence_count=2)
    make_snapshot(project, concept, 0.35, days_ago=0, evidence_count=3)
    return concept


def _practised(project, concept, *, days_ago):
    ConceptMastery.objects.filter(project=project, concept=concept).update(
        last_practiced_at=timezone.now() - timedelta(days=days_ago)
    )


# ---- rules --------------------------------------------------------------------------------------

def test_no_ready_material_recommends_an_upload(project):
    make_material(project, status="processing")

    rec = generate_recommendation(project)

    assert rec.action_type == "upload_material"
    assert rec.concept is None
    assert rec.dedupe_key == "upload_material:none"
    assert rec.status == "active"


def test_ready_material_without_concepts_recommends_nothing(project):
    make_material(project, status="ready")

    assert pick_target(project) is None
    assert generate_recommendation(project) is None


def test_repeated_mistake_recommends_the_tutor(project):
    concept = _weak_concept(project)
    record_memory(project=project, kind="repeated_mistake", content="Missed 3 in a row", concept=concept)

    rec = generate_recommendation(project)

    assert rec.action_type == "ask_tutor"
    assert rec.concept_id == concept.id
    assert rec.dedupe_key == f"ask_tutor:{concept.id}"


def test_a_completed_tutor_recommendation_is_not_repeated(project):
    concept = _weak_concept(project)
    record_memory(project=project, kind="repeated_mistake", content="Missed 3 in a row", concept=concept)
    complete_recommendation(generate_recommendation(project))

    rec = generate_recommendation(project)

    assert rec.action_type == "review_material"


def test_weakest_needs_attention_concept_recommends_review_with_pages(project):
    concept = _weak_concept(project, page=4)
    make_concept(project, "Strong one", mastery=0.9, evidence_count=1)

    rec = generate_recommendation(project)

    assert rec.action_type == "review_material"
    assert rec.concept_id == concept.id
    assert "Biology Notes" in rec.reason
    assert "p. 4" in rec.reason


def test_review_already_given_is_followed_by_a_quiz(project):
    concept = _weak_concept(project)
    complete_recommendation(generate_recommendation(project))          # review_material -> done

    rec = generate_recommendation(project)

    assert rec.action_type == "take_quiz"
    assert rec.concept_id == concept.id


def test_active_review_is_also_followed_by_a_quiz_and_superseded(project):
    concept = _weak_concept(project)
    review = generate_recommendation(project)

    rec = generate_recommendation(project)

    review.refresh_from_db()
    assert rec.action_type == "take_quiz"
    assert rec.concept_id == concept.id
    assert review.status == "superseded"


def test_nothing_weak_recommends_a_quiz_on_the_stalest_concept(project):
    make_material(project, status="ready")
    recent = make_concept(project, "Recent", mastery=0.8, evidence_count=1)
    old = make_concept(project, "Old", mastery=0.8, evidence_count=1)
    _practised(project, recent, days_ago=1)
    _practised(project, old, days_ago=10)

    rec = generate_recommendation(project)

    assert rec.action_type == "take_quiz"
    assert rec.concept_id == old.id


def test_never_practised_concept_is_the_stalest(project):
    make_material(project, status="ready")
    practised = make_concept(project, "Practised", mastery=0.8, evidence_count=1)
    never = make_concept(project, "Never", mastery=0.3, evidence_count=0)
    _practised(project, practised, days_ago=30)

    rec = generate_recommendation(project)

    assert rec.concept_id == never.id


# ---- dedupe, supersede, phrasing, events ----------------------------------------------------------

def test_same_target_returns_the_active_recommendation(project):
    first = generate_recommendation(project)       # upload_material
    second = generate_recommendation(project)

    assert second.id == first.id
    assert Recommendation.objects.count() == 1
    assert LearningEvent.objects.filter(type="recommendation.created").count() == 1


def test_a_new_target_supersedes_the_previous_active_one(project):
    first = generate_recommendation(project)       # upload_material
    _weak_concept(project)

    second = generate_recommendation(project)

    first.refresh_from_db()
    assert first.status == "superseded"
    assert second.status == "active"
    assert second.action_type == "review_material"
    assert active_recommendation(project).id == second.id
    assert Recommendation.objects.filter(project=project, status="active").count() == 1


def test_llm_text_is_used_when_available(project, fake_ai):
    fake_ai.queue_text("  Upload your first PDF so we can get started.  ")

    rec = generate_recommendation(project)

    assert rec.text == "Upload your first PDF so we can get started."
    call = [c for c in fake_ai.calls if c["method"] == "generate"][-1]
    assert "<brief>" in call["prompt"]


def test_template_text_is_used_when_the_ai_call_fails(project, fake_ai):
    concept = _weak_concept(project, name="Chloroplast")
    fake_ai.queue_error(AIError("provider down"))

    rec = generate_recommendation(project)

    assert rec.action_type == "review_material"
    assert "Chloroplast" in rec.text
    assert rec.text != "fake response"


def test_recommendation_created_event_is_emitted(project):
    rec = generate_recommendation(project)

    event = LearningEvent.objects.get(type="recommendation.created")
    assert event.idempotency_key == f"recommendation-created:{rec.id}"
    assert event.payload["action_type"] == "upload_material"
    assert event.project_id == project.id


def test_complete_recommendation_is_idempotent(project):
    rec = generate_recommendation(project)

    complete_recommendation(rec)
    complete_recommendation(rec)

    rec.refresh_from_db()
    assert rec.status == "done"
    assert active_recommendation(project) is None
    assert LearningEvent.objects.filter(type="recommendation.completed").count() == 1


def test_recommendations_are_project_scoped(project, other_project):
    generate_recommendation(other_project)

    assert active_recommendation(project) is None
