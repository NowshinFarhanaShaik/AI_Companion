import uuid

import pytest

from ai.types import AIError, AITimeoutError
from common.errors import ServiceError
from common.testing import make_material
from events.models import Job, LearningEvent
from events.testing import run_all_jobs
from tutor import services
from tutor.models import Citation, Conversation, Message
from tutor.services import answer_question
from tutor.tests.helpers import chunk_with_vector, unit_vector

pytestmark = pytest.mark.django_db

QUESTION = "What do chloroplasts do?"


@pytest.fixture(autouse=True)
def tutor_settings(settings):
    settings.TUTOR_MIN_SIMILARITY = 0.5
    settings.TUTOR_TOOLS_ENABLED = False


@pytest.fixture
def conversation(project):
    return Conversation.objects.create(project=project)


@pytest.fixture
def evidence(project, fake_ai):
    """One chunk that matches QUESTION exactly and one that does not match at all."""
    material = make_material(project, title="Biology Notes")
    relevant = chunk_with_vector(project, material, "Chloroplasts capture light energy.", 0, page=4)
    unrelated = chunk_with_vector(project, material, "The French Revolution began in 1789.", 1, page=9, index=1)
    fake_ai.set_embedding(QUESTION, unit_vector(0))
    return relevant, unrelated


def generation_calls(fake_ai):
    return [call for call in fake_ai.calls if call["method"] != "embed"]


def test_refuses_without_calling_the_model_when_nothing_is_relevant(user, project, conversation, fake_ai):
    material = make_material(project)
    chunk_with_vector(project, material, "The French Revolution began in 1789.", 1)
    fake_ai.set_embedding(QUESTION, unit_vector(0))

    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.role == Message.Role.ASSISTANT
    assert message.grounded is False
    assert message.refusal_reason == "no_relevant_material"
    assert message.citations.count() == 0
    assert generation_calls(fake_ai) == []


def test_refuses_when_the_project_has_no_material(user, conversation, fake_ai):
    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.grounded is False
    assert message.refusal_reason == "no_relevant_material"
    assert generation_calls(fake_ai) == []


def test_grounded_answer_saves_both_messages_and_a_citation(user, conversation, evidence, fake_ai):
    relevant, _ = evidence
    fake_ai.queue_structured(
        {
            "grounded": True,
            "answer": "Chloroplasts capture light energy.",
            "cited_chunk_ids": [str(relevant.id)],
            "follow_up": "Where in the cell are they found?",
        }
    )

    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.grounded is True
    assert message.refusal_reason == ""
    assert "Chloroplasts capture light energy." in message.content
    assert "Where in the cell are they found?" in message.content
    citation = message.citations.get()
    assert citation.chunk_id == relevant.id
    assert citation.material_id == relevant.material_id
    assert citation.page_number == 4
    assert citation.snippet == "Chloroplasts capture light energy."
    roles = list(conversation.messages.values_list("role", flat=True))
    assert roles == ["user", "assistant"]


def test_only_chunks_above_the_threshold_are_sent_to_the_model(user, conversation, evidence, fake_ai):
    relevant, unrelated = evidence
    fake_ai.queue_structured(
        {"grounded": True, "answer": "ok", "cited_chunk_ids": [str(relevant.id)], "follow_up": None}
    )

    answer_question(user=user, conversation=conversation, text=QUESTION)

    call = generation_calls(fake_ai)[0]
    assert call["method"] == "generate_structured"
    assert str(relevant.id) in call["prompt"]
    assert str(unrelated.id) not in call["prompt"]
    assert "French Revolution" not in call["prompt"]


def test_refuses_when_the_model_reports_insufficient_evidence(user, conversation, evidence, fake_ai):
    fake_ai.queue_structured(
        {
            "grounded": False,
            "answer": "The notes mention chloroplasts but do not explain the Calvin cycle.",
            "cited_chunk_ids": [],
            "follow_up": None,
        }
    )

    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.grounded is False
    assert message.refusal_reason == "model_insufficient_evidence"
    assert "do not explain the Calvin cycle" in message.content
    assert Citation.objects.count() == 0


def test_a_citation_outside_the_retrieved_set_is_dropped(user, conversation, evidence, fake_ai):
    relevant, unrelated = evidence
    fake_ai.queue_structured(
        {
            "grounded": True,
            "answer": "Chloroplasts capture light energy.",
            "cited_chunk_ids": [str(relevant.id), str(unrelated.id), str(uuid.uuid4()), "not-a-uuid"],
            "follow_up": None,
        }
    )

    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.grounded is True
    assert [c.chunk_id for c in message.citations.all()] == [relevant.id]


def test_refuses_when_no_valid_citation_remains(user, conversation, evidence, fake_ai):
    fake_ai.queue_structured(
        {
            "grounded": True,
            "answer": "Chloroplasts are made of cheese.",
            "cited_chunk_ids": [str(uuid.uuid4())],
            "follow_up": None,
        }
    )

    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.grounded is False
    assert message.refusal_reason == "no_valid_citation"
    assert "made of cheese" not in message.content
    assert Citation.objects.count() == 0


def test_a_chunk_from_another_project_can_never_be_cited(user, conversation, evidence, other_project, fake_ai):
    foreign = chunk_with_vector(other_project, make_material(other_project), "Chloroplasts capture light energy.", 0)
    fake_ai.queue_structured(
        {"grounded": True, "answer": "ok", "cited_chunk_ids": [str(foreign.id)], "follow_up": None}
    )

    message = answer_question(user=user, conversation=conversation, text=QUESTION)

    assert message.refusal_reason == "no_valid_citation"
    assert Citation.objects.filter(chunk=foreign).count() == 0


def test_embedding_failure_returns_503_and_saves_nothing(user, conversation, evidence, fake_ai):
    fake_ai.queue_error(AIError("provider down"))

    with pytest.raises(ServiceError) as raised:
        answer_question(user=user, conversation=conversation, text=QUESTION)

    assert raised.value.status == 503
    assert raised.value.code == "ai_unavailable"
    assert Message.objects.count() == 0


def test_generation_failure_returns_503_and_saves_nothing(user, conversation, evidence, monkeypatch):
    def fail(**kwargs):
        raise AITimeoutError("timed out")

    monkeypatch.setattr(services, "generate_structured", fail)

    with pytest.raises(ServiceError) as raised:
        answer_question(user=user, conversation=conversation, text=QUESTION)

    assert raised.value.status == 503
    assert raised.value.code == "ai_unavailable"
    assert Message.objects.count() == 0
    assert LearningEvent.objects.filter(type="tutor.message_sent").count() == 0


def test_blank_text_is_rejected(user, conversation):
    with pytest.raises(ServiceError) as raised:
        answer_question(user=user, conversation=conversation, text="   ")

    assert raised.value.status == 400
    assert raised.value.code == "empty_message"


def test_another_users_conversation_cannot_be_used(other_user, conversation):
    from django.http import Http404

    with pytest.raises(Http404):
        answer_question(user=other_user, conversation=conversation, text=QUESTION)


def test_emits_one_event_touches_the_project_and_titles_the_conversation(
    user, project, conversation, evidence, fake_ai
):
    relevant, _ = evidence
    fake_ai.queue_structured(
        {"grounded": True, "answer": "ok", "cited_chunk_ids": [str(relevant.id)], "follow_up": None}
    )

    answer_question(user=user, conversation=conversation, text=QUESTION)

    event = LearningEvent.objects.get(type="tutor.message_sent", project=project)
    user_message = conversation.messages.get(role=Message.Role.USER)
    assert event.idempotency_key == f"tutor-message:{user_message.id}"
    assert event.payload["grounded"] is True
    assert event.payload["citation_count"] == 1
    project.refresh_from_db()
    assert project.last_activity_at is not None
    conversation.refresh_from_db()
    assert conversation.title == QUESTION


def test_every_tenth_message_enqueues_a_summary_job(user, project, conversation, evidence, fake_ai):
    relevant, _ = evidence
    for number in range(8):
        role = Message.Role.USER if number % 2 == 0 else Message.Role.ASSISTANT
        Message.objects.create(conversation=conversation, project=project, role=role, content=f"old {number}")
    fake_ai.set_embedding(f"{QUESTION}\nold 6", unit_vector(0))
    fake_ai.queue_structured(
        {"grounded": True, "answer": "ok", "cited_chunk_ids": [str(relevant.id)], "follow_up": None}
    )

    answer_question(user=user, conversation=conversation, text=QUESTION)

    job = Job.objects.get(type="summarize_conversation")
    assert job.payload == {
        "user_id": str(user.id),
        "project_id": str(project.id),
        "conversation_id": str(conversation.id),
    }

    fake_ai.queue_text("The learner asked about chloroplasts.")
    run_all_jobs()

    conversation.refresh_from_db()
    assert conversation.summary == "The learner asked about chloroplasts."


def test_no_summary_job_before_the_tenth_message(user, conversation, evidence, fake_ai):
    relevant, _ = evidence
    fake_ai.queue_structured(
        {"grounded": True, "answer": "ok", "cited_chunk_ids": [str(relevant.id)], "follow_up": None}
    )

    answer_question(user=user, conversation=conversation, text=QUESTION)

    assert Job.objects.filter(type="summarize_conversation").count() == 0
