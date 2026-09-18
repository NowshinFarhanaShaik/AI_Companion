from django.conf import settings
from django.db import models

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class Space(BaseModel):
    OWNER_PATH = "owner"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="spaces")
    name = models.CharField(max_length=120)
    description = models.TextField()
    color = models.CharField(max_length=16, blank=True, default="")
    icon = models.CharField(max_length=8, blank=True, default="")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Project(BaseModel):
    OWNER_PATH = "owner"

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="projects")
    # Denormalised from space.owner so every Project-owned model can scope with one join.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=160)
    description = models.TextField()
    learning_goal = models.TextField()
    last_activity_at = models.DateTimeField(null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "-last_activity_at"])]

    def __str__(self) -> str:
        return self.name
