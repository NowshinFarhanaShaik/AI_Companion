from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class ConceptMastery(BaseModel):
    """Current estimated mastery of one concept in one project. An estimate, not a measurement."""

    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="masteries")
    concept = models.ForeignKey("materials.Concept", on_delete=models.CASCADE, related_name="masteries")
    score = models.FloatField(default=0.3)
    evidence_count = models.PositiveIntegerField(default=0)
    last_practiced_at = models.DateTimeField(null=True, blank=True)
    consecutive_misses = models.PositiveIntegerField(default=0)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "concept"], name="uniq_mastery_project_concept"),
        ]

    def __str__(self):
        return f"{self.concept_id}: {self.score:.2f}"


class MasterySnapshot(BaseModel):
    """One row per mastery update. Growth analysis is a query over these rows."""

    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="snapshots")
    concept = models.ForeignKey("materials.Concept", on_delete=models.CASCADE, related_name="snapshots")
    score = models.FloatField()
    evidence_count = models.PositiveIntegerField(default=0)
    # Idempotency key for mastery updates: one snapshot per attempt, enforced by the one-to-one.
    attempt = models.OneToOneField(
        "assessment.Attempt", null=True, blank=True, on_delete=models.SET_NULL, related_name="snapshot"
    )

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["project", "concept", "created_at"])]


class LearnerMemory(BaseModel):
    class Kind(models.TextChoices):
        GOAL = "goal"
        PREFERENCE = "preference"
        STRENGTH = "strength"
        WEAKNESS = "weakness"
        REPEATED_MISTAKE = "repeated_mistake"
        NOTE = "note"

    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="memories")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    content = models.TextField()
    concept = models.ForeignKey(
        "materials.Concept", null=True, blank=True, on_delete=models.SET_NULL, related_name="memories"
    )
    salience = models.FloatField(default=0.5)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM, null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["project", "kind", "created_at"])]

    def __str__(self):
        return f"{self.kind}: {self.content[:60]}"


class Recommendation(BaseModel):
    """The next useful action for a project. At most one is active at a time."""

    class ActionType(models.TextChoices):
        REVIEW_MATERIAL = "review_material"
        TAKE_QUIZ = "take_quiz"
        ASK_TUTOR = "ask_tutor"
        UPLOAD_MATERIAL = "upload_material"

    class Status(models.TextChoices):
        ACTIVE = "active"
        DONE = "done"
        SUPERSEDED = "superseded"

    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="recommendations")
    concept = models.ForeignKey(
        "materials.Concept", null=True, blank=True, on_delete=models.SET_NULL, related_name="recommendations"
    )
    action_type = models.CharField(max_length=32, choices=ActionType.choices)
    text = models.TextField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    dedupe_key = models.CharField(max_length=200)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["project", "status", "created_at"])]

    def __str__(self):
        return f"{self.action_type} ({self.status})"
