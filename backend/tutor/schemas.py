from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import BaseModel, Field


class ConversationIn(Schema):
    title: str = Field(default="", max_length=200)


class ConversationOut(Schema):
    id: UUID
    project_id: UUID
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime


class CitationOut(Schema):
    id: UUID
    chunk_id: UUID | None
    material_id: UUID
    material_title: str
    page_number: int
    snippet: str

    @staticmethod
    def resolve_material_title(obj) -> str:
        return obj.material.title


class MessageIn(Schema):
    text: str = Field(min_length=1, max_length=4000)


class MessageOut(Schema):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    grounded: bool | None
    refusal_reason: str
    citations: list[CitationOut]
    created_at: datetime


class TutorAnswer(BaseModel):
    """The structured output the Tutor model must return. It is validated before anything is saved."""

    grounded: bool
    answer: str
    cited_chunk_ids: list[str] = []
    follow_up: str | None = None
