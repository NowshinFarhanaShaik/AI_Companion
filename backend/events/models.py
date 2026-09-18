from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class LearningEvent(BaseModel):
    OWNER_PATH = "user"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    # SET_NULL keeps the activity history for analytics after a Project or Space is deleted.
    project = models.ForeignKey(
        "workspace.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    space = models.ForeignKey("workspace.Space", null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True, null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["project", "-created_at"]),
            models.Index(fields=["type", "-created_at"]),
        ]


class Job(BaseModel):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=4)
    run_after = models.DateTimeField(default=timezone.now)
    locked_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=200, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "run_after"])]
