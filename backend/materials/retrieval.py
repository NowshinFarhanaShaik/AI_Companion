from dataclasses import dataclass

from pgvector.django import CosineDistance

from ai.client import embed_query
from materials.models import Chunk, Material


@dataclass
class RetrievedChunk:
    chunk: Chunk
    similarity: float


def search_chunks_by_vector(*, project, vector: list[float], k: int = 6) -> list[RetrievedChunk]:
    # The project filter is the isolation boundary for every AI feature that reads study material.
    chunks = (
        Chunk.objects.filter(project=project, material__status=Material.Status.READY)
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")
        .select_related("material")[:k]
    )
    return [RetrievedChunk(chunk=chunk, similarity=round(1.0 - float(chunk.distance), 4)) for chunk in chunks]


def search_chunks(*, project, query: str, k: int = 6, user=None) -> list[RetrievedChunk]:
    vector = embed_query(query, user=user, project=project)
    return search_chunks_by_vector(project=project, vector=vector, k=k)
