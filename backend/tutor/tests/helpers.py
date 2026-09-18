from django.conf import settings

from common.testing import make_chunk


def unit_vector(i, dim=None):
    """A one-hot vector. Two equal unit vectors have cosine similarity 1.0, two different ones 0.0."""
    dim = dim or settings.EMBEDDING_DIM
    vector = [0.0] * dim
    vector[i] = 1.0
    return vector


def chunk_with_vector(project, material, text, i, *, page=1, index=0):
    chunk = make_chunk(project, material, text, page=page, index=index)
    chunk.embedding = unit_vector(i)
    chunk.save(update_fields=["embedding"])
    return chunk
