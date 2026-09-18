from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import Field


class SpaceIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    color: str = Field(default="", max_length=16)
    icon: str = Field(default="", max_length=8)


class SpacePatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=8)


class SpaceOut(Schema):
    id: UUID
    name: str
    description: str
    color: str
    icon: str
    project_count: int = 0
    created_at: datetime


class ProjectIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    learning_goal: str = Field(min_length=1, max_length=2000)


class ProjectPatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    learning_goal: str | None = Field(default=None, min_length=1, max_length=2000)


class ProjectOut(Schema):
    id: UUID
    space_id: UUID
    space_name: str
    name: str
    description: str
    learning_goal: str
    last_activity_at: datetime | None
    created_at: datetime

    @staticmethod
    def resolve_space_name(obj) -> str:
        return obj.space.name
