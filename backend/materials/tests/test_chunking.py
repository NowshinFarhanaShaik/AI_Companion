from materials.chunking import chunk_page_text


def test_short_text_is_one_chunk():
    assert chunk_page_text("Photosynthesis makes glucose.") == ["Photosynthesis makes glucose."]


def test_blank_text_gives_no_chunks():
    assert chunk_page_text("   \n\n ") == []


def test_long_text_is_split_below_the_limit_with_overlap():
    sentences = [f"Sentence number {n} explains one fact about plant cells." for n in range(120)]
    chunks = chunk_page_text(" ".join(sentences), max_chars=800, overlap=150)
    assert len(chunks) > 3
    assert all(len(chunk) <= 800 for chunk in chunks)
    for left, right in zip(chunks, chunks[1:]):
        assert left[-60:] in right  # neighbouring chunks share text


def test_every_sentence_survives_chunking():
    sentences = [f"Fact {n} is unique." for n in range(200)]
    joined = " ".join(chunk_page_text(" ".join(sentences), max_chars=500, overlap=80))
    assert all(sentence in joined for sentence in sentences)


def test_a_sentence_longer_than_the_limit_is_hard_split():
    chunks = chunk_page_text("x" * 2500, max_chars=1000, overlap=100)
    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert sum(len(chunk) for chunk in chunks) >= 2500


def test_whitespace_is_normalised():
    assert chunk_page_text("Line one\n\n\nline   two") == ["Line one line two"]
