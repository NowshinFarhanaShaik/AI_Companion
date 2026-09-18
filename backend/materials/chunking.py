import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _pieces(text: str, max_chars: int) -> list[str]:
    """Sentences, with any sentence longer than max_chars cut into max_chars slices."""
    pieces: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        while len(sentence) > max_chars:
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if sentence:
            pieces.append(sentence)
    return pieces


def chunk_page_text(text: str, *, max_chars: int = 3200, overlap: int = 400) -> list[str]:
    """Split one page into chunks of at most max_chars, ending on sentence boundaries where possible.

    Chunks never cross a page, so each keeps an exact page number for citations.
    About four characters make one token, so 3200 characters is roughly 800 tokens.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for piece in _pieces(text, max_chars):
        candidate = f"{current} {piece}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        chunks.append(current)
        tail = current[-overlap:] if overlap else ""
        if " " in tail:
            tail = tail[tail.index(" ") + 1:]  # start the overlap on a word boundary
        current = f"{tail} {piece}".strip()
        if len(current) > max_chars:
            current = piece
    if current:
        chunks.append(current)
    return chunks
