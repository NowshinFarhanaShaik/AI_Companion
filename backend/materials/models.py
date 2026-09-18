import re
import uuid

from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from common.models import BaseModel
from common.scoping import OwnedQuerySet


def material_upload_path(instance, filename: str) -> str:
    # The stored name never contains user input.
    return f"materials/{instance.project_id}/{uuid.uuid4().hex}.pdf"


def normalize_concept_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", name.lower())).strip()


class Material(BaseModel):
    OWNER_PATH = "project__owner"

    class Status(models.TextChoices):
        QUEUED = "queued"
        PROCESSING = "processing"
        READY = "ready"
        FAILED = "failed"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=material_upload_path, max_length=500)
    file_hash = models.CharField(max_length=64)
    page_count = models.IntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True)
    error_message = models.TextField(blank=True, default="")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["project", "file_hash"], name="unique_file_per_project")]


class Chunk(BaseModel):
    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="chunks")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="chunks")
    page_number = models.IntegerField()
    index = models.IntegerField()
    text = models.TextField()
    token_count = models.IntegerField(default=0)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["material_id", "index"]
        indexes = [
            models.Index(fields=["project", "material"]),
            HnswIndex(
                name="chunk_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]


class Concept(BaseModel):
    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="concepts")
    name = models.CharField(max_length=160)
    normalized_name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    importance = models.IntegerField(default=3)
    chunks = models.ManyToManyField(Chunk, through="ChunkConcept", related_name="concepts")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-importance", "name"]
        constraints = [models.UniqueConstraint(fields=["project", "normalized_name"], name="unique_concept_per_project")]

    def __str__(self) -> str:
        return self.name


class ChunkConcept(models.Model):
    chunk = models.ForeignKey(Chunk, on_delete=models.CASCADE)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["chunk", "concept"], name="unique_chunk_concept")]
