import pytest

from common.testing import make_pdf_bytes
from events.models import Job, LearningEvent
from materials.models import Material

pytestmark = pytest.mark.django_db

PDF = make_pdf_bytes(["Photosynthesis converts light energy into chemical energy.", "Chlorophyll absorbs light."])


def test_upload_creates_a_queued_material_and_a_job(api, user, project):
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "Biology Notes.pdf", PDF)
    assert response.status_code == 201
    body = response.json()
    assert (body["title"], body["status"], body["page_count"]) == ("Biology Notes", "queued", 2)
    material = Material.objects.get(id=body["id"])
    job = Job.objects.get(type="process_material")
    assert job.payload == {"material_id": str(material.id), "project_id": str(project.id), "user_id": str(user.id)}
    assert job.idempotency_key == f"process-material:{material.id}"
    assert LearningEvent.objects.filter(type="material.uploaded", project=project).count() == 1


def test_uploading_the_same_file_twice_returns_the_first_material(api, user, project):
    first = api(user).upload(f"/projects/{project.id}/materials", "file", "a.pdf", PDF)
    second = api(user).upload(f"/projects/{project.id}/materials", "file", "renamed.pdf", PDF)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert Material.objects.count() == 1 and Job.objects.count() == 1


def test_the_same_file_can_live_in_two_projects(api, user, project, space):
    from workspace.services import create_project

    second_project = create_project(user=user, space=space, name="P2", description="d", learning_goal="g")
    api(user).upload(f"/projects/{project.id}/materials", "file", "a.pdf", PDF)
    response = api(user).upload(f"/projects/{second_project.id}/materials", "file", "a.pdf", PDF)
    assert response.status_code == 201


def test_a_file_that_is_not_a_pdf_is_rejected(api, user, project):
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "fake.pdf", b"MZ\x90\x00 not a pdf")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_pdf"
    assert Material.objects.count() == 0


def test_a_corrupt_pdf_is_rejected(api, user, project):
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "bad.pdf", b"%PDF-1.7\nthis is broken")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_pdf"


def test_oversize_files_are_rejected(api, user, project, settings):
    settings.MAX_UPLOAD_BYTES = 100
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "big.pdf", PDF)
    assert response.status_code == 400
    assert response.json()["code"] == "file_too_large"


def test_too_many_pages_are_rejected(api, user, project, settings):
    settings.MAX_UPLOAD_PAGES = 1
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "long.pdf", PDF)
    assert response.status_code == 400
    assert response.json()["code"] == "too_many_pages"


def test_cannot_upload_to_another_users_project(api, user, other_project):
    response = api(user).upload(f"/projects/{other_project.id}/materials", "file", "a.pdf", PDF)
    assert response.status_code == 404
    assert Material.objects.count() == 0


def test_a_password_protected_pdf_is_rejected(api, user, project):
    import pymupdf

    document = pymupdf.open(stream=PDF, filetype="pdf")
    locked = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "locked.pdf", locked)
    assert response.status_code == 400
    assert response.json()["detail"] == "Password-protected PDFs are not supported."


def test_the_stored_path_ignores_the_client_file_name(api, user, project):
    response = api(user).upload(f"/projects/{project.id}/materials", "file", "../../etc/passwd.pdf", PDF)
    material = Material.objects.get(id=response.json()["id"])
    assert material.file.name.startswith(f"materials/{project.id}/")
    assert ".." not in material.file.name and "passwd" not in material.file.name
