import pytest

from conftest import PASSWORD
from tutor.models import Message
from tutor.services import create_conversation

pytestmark = pytest.mark.django_db


def test_sign_in_is_limited_per_client(api, user):
    for _ in range(10):
        assert api().post("/auth/token", {"email": user.email, "password": "wrong-password"}).status_code == 401

    response = api().post("/auth/token", {"email": user.email, "password": PASSWORD})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert int(response["Retry-After"]) > 0


def test_tutor_messages_are_limited_per_user(api, user, other_user, project, other_project):
    mine = create_conversation(user=user, project=project)
    theirs = create_conversation(user=other_user, project=other_project)
    for _ in range(10):
        assert api(user).post(f"/conversations/{mine.id}/messages", {"text": "What is osmosis?"}).status_code == 201

    assert api(user).post(f"/conversations/{mine.id}/messages", {"text": "One more?"}).status_code == 429
    assert Message.objects.filter(conversation=mine).count() == 20
    assert api(other_user).post(f"/conversations/{theirs.id}/messages", {"text": "Hi?"}).status_code == 201
