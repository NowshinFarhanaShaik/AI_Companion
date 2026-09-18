import pytest
from django.test import Client

from common.testing import make_chunk, make_material
from tutor.models import Citation, Conversation, Message

pytestmark = pytest.mark.django_db


def test_create_conversation(api, user, project):
    response = api(user).post(
        f"/api/projects/{project.id}/conversations", {"title": "Cell biology"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Cell biology"
    assert body["project_id"] == str(project.id)
    assert Conversation.objects.filter(project=project).count() == 1


def test_list_conversations_returns_only_this_project(api, user, project, other_project):
    Conversation.objects.create(project=project, title="Mine")
    Conversation.objects.create(project=other_project, title="Theirs")

    response = api(user).get(f"/api/projects/{project.id}/conversations")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert [item["title"] for item in body["items"]] == ["Mine"]


def test_other_user_cannot_list_or_create_conversations(api, other_user, project):
    client = api(other_user)

    assert client.get(f"/api/projects/{project.id}/conversations").status_code == 404
    assert (
        client.post(f"/api/projects/{project.id}/conversations", {"title": "x"}).status_code
        == 404
    )
    assert Conversation.objects.count() == 0


def test_list_messages_in_order_with_citations(api, user, project):
    material = make_material(project, title="Biology Notes")
    chunk = make_chunk(project, material, "Chloroplasts capture light.", page=4)
    conversation = Conversation.objects.create(project=project, title="Cells")
    Message.objects.create(
        conversation=conversation, project=project, role=Message.Role.USER, content="What do chloroplasts do?"
    )
    answer = Message.objects.create(
        conversation=conversation,
        project=project,
        role=Message.Role.ASSISTANT,
        content="They capture light.",
        grounded=True,
    )
    Citation.objects.create(
        message=answer, chunk=chunk, material=material, page_number=4, snippet="Chloroplasts capture light."
    )

    response = api(user).get(f"/api/conversations/{conversation.id}/messages")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["role"] for item in items] == ["user", "assistant"]
    assert items[0]["grounded"] is None
    assert items[0]["citations"] == []
    citation = items[1]["citations"][0]
    assert citation["material_id"] == str(material.id)
    assert citation["material_title"] == "Biology Notes"
    assert citation["page_number"] == 4
    assert citation["snippet"] == "Chloroplasts capture light."


def test_other_user_cannot_read_messages(api, other_user, project):
    conversation = Conversation.objects.create(project=project, title="Private")

    response = api(other_user).get(f"/api/conversations/{conversation.id}/messages")

    assert response.status_code == 404


def test_unauthenticated_request_is_rejected(project):
    response = Client().get(f"/api/projects/{project.id}/conversations")

    assert response.status_code == 401


def test_scoped_managers_hide_other_users_rows(user, other_user, project):
    material = make_material(project)
    chunk = make_chunk(project, material, "text")
    conversation = Conversation.objects.create(project=project)
    message = Message.objects.create(
        conversation=conversation, project=project, role=Message.Role.ASSISTANT, content="a", grounded=True
    )
    Citation.objects.create(message=message, chunk=chunk, material=material, page_number=1, snippet="text")

    assert Conversation.objects.for_user(user).count() == 1
    assert Message.objects.for_user(user).count() == 1
    assert Citation.objects.for_user(user).count() == 1
    assert Conversation.objects.for_user(other_user).count() == 0
    assert Message.objects.for_user(other_user).count() == 0
    assert Citation.objects.for_user(other_user).count() == 0


def test_citation_survives_chunk_deletion(project):
    material = make_material(project)
    chunk = make_chunk(project, material, "text", page=2)
    conversation = Conversation.objects.create(project=project)
    message = Message.objects.create(
        conversation=conversation, project=project, role=Message.Role.ASSISTANT, content="a", grounded=True
    )
    citation = Citation.objects.create(
        message=message, chunk=chunk, material=material, page_number=2, snippet="text"
    )

    chunk.delete()
    citation.refresh_from_db()

    assert citation.chunk is None
    assert citation.page_number == 2
