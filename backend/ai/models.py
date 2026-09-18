from django.conf import settings
from django.db import models

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class AICallLog(BaseModel):
    OWNER_PATH = "user"

    class Status(models.TextChoices):
        OK = "ok"
        ERROR = "error"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_calls"
    )
    project = models.ForeignKey(
        "workspace.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_calls"
    )
    feature = models.CharField(max_length=32, db_index=True)
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=64)
    latency_ms = models.IntegerField(default=0)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OK, db_index=True)
    error_type = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    retries = models.IntegerField(default=0)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    trace_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "-created_at"]), models.Index(fields=["user", "-created_at"])]


class EvalRun(BaseModel):
    suite = models.CharField(max_length=64, db_index=True)
    git_sha = models.CharField(max_length=40, blank=True, default="")
    metrics = models.JSONField(default=dict)
    case_results = models.JSONField(default=list)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
