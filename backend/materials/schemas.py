from datetime import datetime
from uuid import UUID

from ninja import Schema


class MaterialOut(Schema):
    id: UUID
    project_id: UUID
    title: str
    status: str
    error_message: str
    page_count: int
    chunk_count: int = 0
    created_at: datetime


class ConceptOut(Schema):
    id: UUID
    name: str
    description: str
    importance: int
    pages: list[int] = []

    @staticmethod
    def resolve_pages(obj) -> list[int]:
        return sorted({chunk.page_number for chunk in obj.chunks.all()})
