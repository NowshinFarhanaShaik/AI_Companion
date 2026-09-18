from django.db import models

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class Conversation(BaseModel):
    OWNER_PATH = "project__owner"

    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=200, blank=True, default="")
    summary = models.TextField(blank=True, default="")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Conversation {self.id}"


class Message(BaseModel):
    OWNER_PATH = "project__owner"

    class Role(models.TextChoices):
        USER = "user"
        ASSISTANT = "assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    project = models.ForeignKey("workspace.Project", on_delete=models.CASCADE, related_name="tutor_messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    grounded = models.BooleanField(null=True, blank=True)
    refusal_reason = models.CharField(max_length=64, blank=True, default="")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]


class Citation(BaseModel):
    OWNER_PATH = "message__project__owner"

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="citations")
    # Re-processing a material replaces its chunks, so the citation keeps its own page and snippet.
    chunk = models.ForeignKey(
        "materials.Chunk", on_delete=models.SET_NULL, null=True, blank=True, related_name="citations"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.CASCADE, related_name="citations")
    page_number = models.PositiveIntegerField()
    snippet = models.TextField(blank=True, default="")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["page_number", "created_at"]
