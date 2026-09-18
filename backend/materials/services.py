import hashlib
import time
from pathlib import Path

import pymupdf
from django.conf import settings
from django.db import transaction

from common.errors import ServiceError
from events.services import emit, enqueue
from materials.models import Material
from workspace.services import touch_project


def _job_payload(material: Material, user) -> dict:
    return {"material_id": str(material.id), "project_id": str(material.project_id), "user_id": str(user.id)}


def _page_count(content: bytes) -> int:
    # The extension and content type come from the client, so only the bytes are trusted.
    if b"%PDF-" not in content[:1024]:
        raise ServiceError("This file is not a PDF.", code="invalid_pdf")
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            protected, page_count = document.needs_pass, document.page_count
    except Exception:
        raise ServiceError("This PDF could not be read. It may be damaged.", code="invalid_pdf")
    if protected:
        raise ServiceError("Password-protected PDFs are not supported.", code="invalid_pdf")
    if page_count == 0:
        raise ServiceError("This PDF has no pages.", code="invalid_pdf")
    if page_count > settings.MAX_UPLOAD_PAGES:
        raise ServiceError(f"PDFs can have at most {settings.MAX_UPLOAD_PAGES} pages.", code="too_many_pages")
    return page_count


def create_material(*, user, project, uploaded_file) -> Material:
    """Validates and stores a PDF. The same file in the same Project returns the existing material.

    The returned instance carries `is_new`, so the API can answer 201 or 200.
    """
    if project.owner_id != user.id:
        raise ServiceError("Project not found", status=404, code="not_found")
    if uploaded_file.size > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ServiceError(f"Files can be at most {limit_mb} MB.", code="file_too_large")
    content = uploaded_file.read()
    page_count = _page_count(content)
    file_hash = hashlib.sha256(content).hexdigest()

    existing = Material.objects.for_user(user).filter(project=project, file_hash=file_hash).first()
    if existing:
        existing.is_new = False
        return existing

    uploaded_file.seek(0)
    with transaction.atomic():
        material = Material(
            project=project, title=Path(uploaded_file.name).stem[:255] or "Untitled",
            file_hash=file_hash, page_count=page_count,
        )
        material.file.save(uploaded_file.name, uploaded_file, save=False)
        material.save()
        emit(
            type="material.uploaded", user=user, project=project,
            payload={**_job_payload(material, user), "title": material.title},
            idempotency_key=f"material-uploaded:{material.id}",
        )
        touch_project(project)
    material.is_new = True
    return material


def retry_material(*, user, material) -> Material:
    if material.status != Material.Status.FAILED:
        raise ServiceError("Only failed materials can be retried.", status=409, code="not_failed")
    with transaction.atomic():
        material.status = Material.Status.QUEUED
        material.error_message = ""
        material.save(update_fields=["status", "error_message", "updated_at"])
        enqueue(
            "process_material", _job_payload(material, user),
            idempotency_key=f"process-material:{material.id}:retry:{int(time.time())}",
        )
    return material
