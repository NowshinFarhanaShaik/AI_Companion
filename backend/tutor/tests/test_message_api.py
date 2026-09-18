import pytest

from ai.types import AIError
from common.testing import make_material
from tutor.models import Conversation, Message
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


def test_post_message_returns_the_answer_with_citations(api, user, project, conversation, fake_ai):
    material = make_material(project, title="Biology Notes")
    chunk = chunk_with_vector(project, material, "Chloroplasts capture light energy.", 0, page=4)
    fake_ai.set_embedding(QUESTION, unit_vector(0))
    fake_ai.queue_structured(
        {"grounded": True, "answer": "They capture light.", "cited_chunk_ids": [str(chunk.id)], "follow_up": None}
    )

    response = api(user).post(f"/api/conversations/{conversation.id}/messages", {"text": QUESTION})

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "assistant"
    assert body["grounded"] is True
    assert body["content"] == "They capture light."
    assert body["citations"] == [
        {
            "id": body["citations"][0]["id"],
            "chunk_id": str(chunk.id),
            "material_id": str(material.id),
            "material_title": "Biology Notes",
            "page_number": 4,
            "snippet": "Chloroplasts capture light energy.",
        }
    ]


def test_post_message_returns_a_refusal_for_an_unsupported_question(api, user, conversation, fake_ai):
    response = api(user).post(
        f"/api/conversations/{conversation.id}/messages", {"text": "Who won the 1998 World Cup?"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["grounded"] is False
    assert body["refusal_reason"] == "no_relevant_material"
    assert body["citations"] == []


def test_other_user_cannot_post_to_the_conversation(api, other_user, conversation):
    response = api(other_user).post(f"/api/conversations/{conversation.id}/messages", {"text": QUESTION})

    assert response.status_code == 404
    assert Message.objects.count() == 0


def test_empty_text_is_a_validation_error(api, user, conversation):
    response = api(user).post(f"/api/conversations/{conversation.id}/messages", {"text": ""})

    assert response.status_code == 422


def test_whitespace_text_is_rejected_by_the_service(api, user, conversation):
    response = api(user).post(f"/api/conversations/{conversation.id}/messages", {"text": "   "})

    assert response.status_code == 400
    assert response.json()["code"] == "empty_message"


def test_ai_failure_returns_503_with_a_code(api, user, conversation, fake_ai):
    fake_ai.queue_error(AIError("provider down"))

    response = api(user).post(f"/api/conversations/{conversation.id}/messages", {"text": QUESTION})

    assert response.status_code == 503
    assert response.json()["code"] == "ai_unavailable"
    assert Message.objects.count() == 0
