import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from ninja_jwt.tokens import RefreshToken


class ApiClient:
    """django.test.Client with a Bearer token and JSON bodies. Paths may omit the /api prefix."""

    def __init__(self, user=None):
        self.client = Client()
        self.headers = {}
        if user is not None:
            access = RefreshToken.for_user(user).access_token
            self.headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}

    @staticmethod
    def _url(path: str) -> str:
        return path if path.startswith("/api/") else f"/api{path}"

    def get(self, path, **params):
        return self.client.get(self._url(path), params, **self.headers)

    def post(self, path, data=None):
        return self.client.post(
            self._url(path), data=json.dumps(data or {}), content_type="application/json", **self.headers
        )

    def patch(self, path, data=None):
        return self.client.patch(
            self._url(path), data=json.dumps(data or {}), content_type="application/json", **self.headers
        )

    def delete(self, path):
        return self.client.delete(self._url(path), **self.headers)

    def upload(self, path, field, filename, content: bytes, content_type="application/pdf"):
        upload = SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(self._url(path), {field: upload}, **self.headers)


def make_pdf_bytes(pages: list[str]) -> bytes:
    """Builds a real PDF, one page per string. An empty string gives a blank page, which exercises OCR."""
    import pymupdf

    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def make_material(project, *, title="Notes", status="ready", page_count=3):
    import uuid

    from django.core.files.base import ContentFile

    from materials.models import Material

    material = Material(project=project, title=title, status=status, page_count=page_count, file_hash=uuid.uuid4().hex)
    material.file.save("notes.pdf", ContentFile(make_pdf_bytes(["sample page"])), save=False)
    material.save()
    return material


def make_chunk(project, material, text, *, page=1, index=0):
    from ai.testing import fake_embedding
    from materials.models import Chunk

    return Chunk.objects.create(
        project=project, material=material, page_number=page, index=index, text=text,
        token_count=len(text) // 4, embedding=fake_embedding(text),
    )


def make_concept(project, name, *, chunks=(), importance=3, mastery=0.3, evidence_count=0):
    from django.apps import apps

    from materials.models import ChunkConcept, Concept, normalize_concept_name

    concept = Concept.objects.create(
        project=project, name=name, normalized_name=normalize_concept_name(name),
        description=f"About {name}", importance=importance,
    )
    ChunkConcept.objects.bulk_create([ChunkConcept(chunk=chunk, concept=concept) for chunk in chunks])
    if apps.is_installed("learning"):
        from learning.models import ConceptMastery

        ConceptMastery.objects.create(project=project, concept=concept, score=mastery, evidence_count=evidence_count)
    return concept
