import logging

import pymupdf
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from ai import client as ai
from ai.types import AIRateLimitError, AITimeoutError
from events.registry import job_handler
from events.services import emit
from events.worker import PermanentJobError
from materials.chunking import chunk_page_text
from materials.models import Chunk, ChunkConcept, Concept, Material, normalize_concept_name
from materials.prompts import CONCEPT_SYSTEM, ExtractedConcepts, build_concept_prompt

logger = logging.getLogger(__name__)


def _extract_pages(material: Material, user) -> list[tuple[int, str]]:
    """Returns (page_number, text) pairs. Pages with almost no text layer go to vision OCR."""
    with material.file.open("rb") as handle:
        content = handle.read()
    pages: list[tuple[int, str]] = []
    ocr_used = 0
    with pymupdf.open(stream=content, filetype="pdf") as document:
        for number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if len(text) < settings.OCR_MIN_CHARS and ocr_used < settings.MAX_OCR_PAGES:
                image = page.get_pixmap(dpi=120).tobytes("png")
                text = ai.ocr_image(image, user=user, project=material.project)
                ocr_used += 1
            pages.append((number, text))
    return pages


def _save_results(material: Material, chunk_rows: list[tuple[int, str]], vectors, extracted: ExtractedConcepts) -> None:
    project = material.project
    with transaction.atomic():
        # Replacing the material's chunks is what makes a re-run safe.
        Chunk.objects.filter(material=material).delete()
        chunks = Chunk.objects.bulk_create(
            Chunk(
                project=project, material=material, page_number=page_number, index=index, text=text,
                token_count=len(text) // 4, embedding=vectors[index],
            )
            for index, (page_number, text) in enumerate(chunk_rows)
        )
        for item in extracted.concepts[: settings.MAX_CONCEPTS_PER_MATERIAL]:
            valid_indexes = sorted({i for i in item.chunk_indexes if 0 <= i < len(chunks)})
            normalized = normalize_concept_name(item.name)
            if not valid_indexes or not normalized:
                continue
            concept, _ = Concept.objects.get_or_create(
                project=project, normalized_name=normalized,
                defaults={"name": item.name.strip(), "description": item.description, "importance": item.importance},
            )
            ChunkConcept.objects.bulk_create(
                [ChunkConcept(chunk=chunks[i], concept=concept) for i in valid_indexes], ignore_conflicts=True
            )
            if apps.is_installed("learning"):
                from learning.models import ConceptMastery

                ConceptMastery.objects.get_or_create(project=project, concept=concept, defaults={"score": 0.3})
        material.status = Material.Status.READY
        material.error_message = ""
        material.save(update_fields=["status", "error_message", "updated_at"])


def _user_message(exc: Exception) -> str:
    if isinstance(exc, PermanentJobError):
        return str(exc)
    if isinstance(exc, (AIRateLimitError, AITimeoutError)):
        return "The AI service is busy right now. Please retry in a few minutes."
    return "We couldn't process this document. Please try again."


def process_material(material_id, *, user_id=None, job=None) -> None:
    """Runs the pipeline for one material.

    Jobs pass user_id from their payload and the material is loaded through the scoped manager, so a forged
    payload cannot touch another user's file. Trusted in-process callers (the eval harness, seed data) may
    omit user_id; the material's own Project owner is then used.
    """
    materials = Material.objects.select_related("project__owner")
    if user_id is None:
        material = materials.filter(id=material_id).first()
        user = material.project.owner if material else None
    else:
        user = get_user_model().objects.filter(id=user_id, is_active=True).first()
        material = materials.for_user(user).filter(id=material_id).first() if user else None
    if material is None:
        logger.info("process_material: material %s is gone or not owned by user %s", material_id, user_id)
        return

    # AI calls run outside any transaction: no connection is held during network calls, and a failed
    # attempt keeps its AICallLog rows.
    Material.objects.filter(id=material.id).update(status=Material.Status.PROCESSING)
    event_key = f"{material.id}:{job.id if job else 'direct'}"
    try:
        pages = _extract_pages(material, user)
        chunk_rows = [(number, chunk) for number, text in pages for chunk in chunk_page_text(text)]
        if not chunk_rows:
            raise PermanentJobError("We couldn't find any readable text in this PDF.")
        texts = [text for _, text in chunk_rows]
        vectors = ai.embed_texts(texts, user=user, project=material.project)
        extracted = ai.generate_structured(
            feature="concepts", tier="fast", schema=ExtractedConcepts,
            system=CONCEPT_SYSTEM.format(max_concepts=settings.MAX_CONCEPTS_PER_MATERIAL),
            prompt=build_concept_prompt(texts), user=user, project=material.project,
        )
        _save_results(material, chunk_rows, vectors, extracted)
    except Exception as exc:
        final = isinstance(exc, PermanentJobError) or job is None or job.attempts >= job.max_attempts
        if final:
            Material.objects.filter(id=material.id).update(
                status=Material.Status.FAILED, error_message=_user_message(exc)
            )
            emit(
                type="material.failed", user=user, project=material.project,
                payload={"material_id": str(material.id), "error": type(exc).__name__},
                idempotency_key=f"material-failed:{event_key}",
            )
        else:
            Material.objects.filter(id=material.id).update(status=Material.Status.QUEUED)
        raise

    emit(
        type="material.processed", user=user, project=material.project,
        payload={"material_id": str(material.id), "title": material.title, "chunks": len(chunk_rows)},
        idempotency_key=f"material-processed:{event_key}",
    )


@job_handler("process_material")
def handle_process_material(job) -> None:
    process_material(job.payload["material_id"], user_id=job.payload["user_id"], job=job)
