import pytest

from common.testing import make_chunk, make_concept, make_material
from events.models import Job

pytestmark = pytest.mark.django_db


def test_list_materials_with_counts(api, user, project):
    material = make_material(project, title="Notes")
    make_chunk(project, material, "first chunk", page=1)
    make_chunk(project, material, "second chunk", page=2, index=1)
    body = api(user).get(f"/projects/{project.id}/materials").json()
    assert body["count"] == 1
    assert (body["items"][0]["title"], body["items"][0]["chunk_count"]) == ("Notes", 2)


def test_get_and_delete_material(api, user, project):
    material = make_material(project)
    client = api(user)
    assert client.get(f"/materials/{material.id}").json()["status"] == "ready"
    assert client.delete(f"/materials/{material.id}").status_code == 204
    assert client.get(f"/materials/{material.id}").status_code == 404


def test_file_endpoint_streams_the_pdf(api, user, project):
    material = make_material(project)
    response = api(user).get(f"/materials/{material.id}/file")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content).startswith(b"%PDF")


def test_retry_requeues_a_failed_material(api, user, project):
    material = make_material(project, status="failed")
    response = api(user).post(f"/materials/{material.id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert Job.objects.filter(type="process_material", payload__material_id=str(material.id)).count() == 1


def test_retry_is_refused_unless_failed(api, user, project):
    material = make_material(project, status="ready")
    response = api(user).post(f"/materials/{material.id}/retry")
    assert response.status_code == 409
    assert response.json()["code"] == "not_failed"


def test_list_concepts(api, user, project):
    material = make_material(project)
    chunk = make_chunk(project, material, "Chlorophyll absorbs light", page=4)
    make_concept(project, "Chlorophyll", chunks=[chunk], importance=5)
    body = api(user).get(f"/projects/{project.id}/concepts").json()
    assert body["items"][0]["name"] == "Chlorophyll"
    assert body["items"][0]["pages"] == [4]


@pytest.mark.parametrize("path", ["", "/file"])
def test_another_users_material_is_404(api, user, other_project, path):
    material = make_material(other_project)
    assert api(user).get(f"/materials/{material.id}{path}").status_code == 404


def test_another_users_material_cannot_be_deleted_or_retried(api, user, other_project):
    material = make_material(other_project, status="failed")
    assert api(user).delete(f"/materials/{material.id}").status_code == 404
    assert api(user).post(f"/materials/{material.id}/retry").status_code == 404
    assert Job.objects.count() == 0


def test_another_users_project_lists_are_404(api, user, other_project):
    assert api(user).get(f"/projects/{other_project.id}/materials").status_code == 404
    assert api(user).get(f"/projects/{other_project.id}/concepts").status_code == 404
