import pytest

pytestmark = pytest.mark.django_db


def test_create_space(api, user):
    response = api(user).post("/spaces", {"name": "Biology", "description": "Cells", "color": "#16a34a"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Biology"
    assert body["project_count"] == 0


def test_space_requires_name_and_description(api, user):
    assert api(user).post("/spaces", {"name": "", "description": "x"}).status_code == 422
    assert api(user).post("/spaces", {"name": "x", "description": ""}).status_code == 422


def test_list_spaces_is_paginated_and_counts_projects(api, user, space, project):
    body = api(user).get("/spaces").json()
    assert body["count"] == 1
    assert body["items"][0]["id"] == str(space.id)
    assert body["items"][0]["project_count"] == 1


def test_update_and_delete_space(api, user, space):
    client = api(user)
    assert client.patch(f"/spaces/{space.id}", {"name": "Bio"}).json()["name"] == "Bio"
    assert client.delete(f"/spaces/{space.id}").status_code == 204
    assert client.get(f"/spaces/{space.id}").status_code == 404
