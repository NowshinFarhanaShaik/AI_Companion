import uuid

import pytest

from workspace.models import Project, Space

pytestmark = pytest.mark.django_db


def test_for_user_only_returns_owned_rows(user, space, project, other_space, other_project):
    assert list(Space.objects.for_user(user)) == [space]
    assert list(Project.objects.for_user(user)) == [project]


def test_lists_never_include_another_users_data(api, user, space, other_space, other_project):
    items = api(user).get("/spaces").json()["items"]
    assert [item["id"] for item in items] == [str(space.id)]


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_another_users_space_is_404(api, user, other_space, method):
    call = getattr(api(user), method)
    path = f"/spaces/{other_space.id}"
    response = call(path, {"name": "hacked"}) if method == "patch" else call(path)
    assert response.status_code == 404
    other_space.refresh_from_db()
    assert other_space.name == "History"


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_another_users_project_is_404(api, user, other_project, method):
    call = getattr(api(user), method)
    path = f"/projects/{other_project.id}"
    response = call(path, {"name": "hacked"}) if method == "patch" else call(path)
    assert response.status_code == 404
    assert Project.objects.filter(id=other_project.id, name="Cold War").exists()


def test_cannot_create_project_in_another_users_space(api, user, other_space):
    response = api(user).post(
        f"/spaces/{other_space.id}/projects", {"name": "X", "description": "d", "learning_goal": "g"}
    )
    assert response.status_code == 404
    assert other_space.projects.count() == 0


def test_cannot_list_projects_of_another_users_space(api, user, other_space):
    assert api(user).get(f"/spaces/{other_space.id}/projects").status_code == 404


def test_unknown_id_and_foreign_id_look_the_same(api, user, other_project):
    unknown = api(user).get(f"/projects/{uuid.uuid4()}")
    foreign = api(user).get(f"/projects/{other_project.id}")
    assert unknown.status_code == foreign.status_code == 404
    assert unknown.json() == foreign.json()


def test_endpoints_require_authentication(api, space):
    assert api().get("/spaces").status_code == 401
    assert api().get(f"/spaces/{space.id}").status_code == 401
