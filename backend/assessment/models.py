from django.db import models

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class QuizSession(BaseModel):
    OWNER_PATH = "project__owner"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="quiz_sessions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    target_question_count = models.PositiveSmallIntegerField(default=5)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]


class Question(BaseModel):
    OWNER_PATH = "project__owner"

    class Type(models.TextChoices):
        MCQ = "mcq", "Multiple choice"
        OPEN = "open", "Open-ended"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="questions")
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name="questions")
    concept = models.ForeignKey("materials.Concept", on_delete=models.CASCADE, related_name="questions")
    type = models.CharField(max_length=8, choices=Type.choices)
    difficulty = models.PositiveSmallIntegerField()
    body = models.TextField()
    options = models.JSONField(default=list, blank=True)          # mcq only: list of 4 strings
    correct_option = models.PositiveSmallIntegerField(null=True, blank=True)   # mcq only: index into options
    rubric = models.JSONField(default=dict, blank=True)           # mcq: {"explanation"}; open: {"key_points"}
    source_chunk = models.ForeignKey(
        "materials.Chunk", null=True, blank=True, on_delete=models.SET_NULL, related_name="questions"
    )

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]


class Attempt(BaseModel):
    OWNER_PATH = "project__owner"

    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name="attempt")
    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="attempts")
    answer_text = models.TextField(blank=True, default="")
    selected_option = models.PositiveSmallIntegerField(null=True, blank=True)
    score = models.FloatField()
    feedback = models.JSONField(default=dict, blank=True)   # understood, missing, misconceptions, feedback
    evaluated_at = models.DateTimeField()

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["project", "created_at"])]
