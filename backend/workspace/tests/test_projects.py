import pytest

pytestmark = pytest.mark.django_db


def test_create_project_in_space(api, user, space):
    response = api(user).post(
        f"/spaces/{space.id}/projects",
        {"name": "Photosynthesis", "description": "Unit 4", "learning_goal": "Pass the test"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["space_id"] == str(space.id)
    assert body["space_name"] == "Biology"
    assert body["learning_goal"] == "Pass the test"


def test_project_requires_learning_goal(api, user, space):
    response = api(user).post(f"/spaces/{space.id}/projects", {"name": "P", "description": "d", "learning_goal": ""})
    assert response.status_code == 422


def test_list_projects_in_space(api, user, space, project):
    body = api(user).get(f"/spaces/{space.id}/projects").json()
    assert [item["id"] for item in body["items"]] == [str(project.id)]


def test_get_update_delete_project(api, user, project):
    client = api(user)
    assert client.get(f"/projects/{project.id}").json()["name"] == "Photosynthesis"
    assert client.patch(f"/projects/{project.id}", {"learning_goal": "Ace it"}).json()["learning_goal"] == "Ace it"
    assert client.delete(f"/projects/{project.id}").status_code == 204
    assert client.get(f"/projects/{project.id}").status_code == 404


def test_touch_project_sets_last_activity(project):
    from workspace.services import touch_project

    assert project.last_activity_at is None
    touch_project(project)
    project.refresh_from_db()
    assert project.last_activity_at is not None


def test_creating_space_and_project_emits_events(user, space, project):
    from events.models import LearningEvent

    types = set(LearningEvent.objects.for_user(user).values_list("type", flat=True))
    assert {"space.created", "project.created"} <= types
    assert LearningEvent.objects.get(type="project.created").space == space
