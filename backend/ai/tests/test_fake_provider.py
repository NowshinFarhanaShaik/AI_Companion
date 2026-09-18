import math

from ai.testing import fake_embedding


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_fake_embedding_is_deterministic_and_normalised():
    vector = fake_embedding("Photosynthesis happens in chloroplasts")
    assert vector == fake_embedding("Photosynthesis happens in chloroplasts")
    assert len(vector) == 768
    assert math.isclose(sum(v * v for v in vector), 1.0, rel_tol=1e-6)


def test_related_texts_are_closer_than_unrelated_texts():
    chunk = fake_embedding("Photosynthesis converts light energy into glucose inside chloroplasts")
    related = fake_embedding("What is photosynthesis?")
    unrelated = fake_embedding("Who won the football league in 1998?")
    assert cosine(chunk, related) > 0.3
    assert cosine(chunk, unrelated) < 0.05


def test_empty_text_never_gives_a_zero_vector():
    assert any(fake_embedding(""))
