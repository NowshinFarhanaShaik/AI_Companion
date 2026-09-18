import pytest

from ai.types import AIRateLimitError
from tutor.services import create_conversation

pytestmark = pytest.mark.django_db


def test_an_unmapped_ai_error_becomes_a_503(api, user, project, monkeypatch):
    def fail(**kwargs):
        raise AIRateLimitError("quota exhausted")

    monkeypatch.setattr("tutor.services.answer_question", fail)
    conversation = create_conversation(user=user, project=project)
    response = api(user).post(f"/conversations/{conversation.id}/messages", {"text": "Hi?"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is unavailable right now. Please try again in a moment.",
        "code": "ai_unavailable",
    }
