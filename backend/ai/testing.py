import hashlib
import json
import math
import re
from collections import deque

from pydantic import BaseModel

from ai.types import RawEmbedResult, RawResult, ToolCall, ToolTurn

_STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "has", "have", "was", "were", "what", "when",
    "where", "which", "who", "why", "how", "does", "did", "with", "that", "this", "from", "they", "their", "its",
    "into", "about", "than", "then", "them", "these", "those", "will", "would", "could", "should", "your", "our",
}


def fake_embedding(text: str, dim: int = 768) -> list[float]:
    """Deterministic bag-of-words vector: texts that share words are close, unrelated texts are near zero."""
    vector = [0.0] * dim
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) < 3 or word in _STOP_WORDS:
            continue
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % (dim - 1)] += 1.0
    if not any(vector):
        vector[dim - 1] = 1.0  # cosine distance is undefined for a zero vector
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.calls: list[dict] = []
        self._texts: deque[str] = deque()
        self._structured: deque[str] = deque()
        self._tool_turns: deque[ToolTurn] = deque()
        self._errors: deque[Exception] = deque()
        self._embeddings: dict[str, list[float]] = {}

    def queue_text(self, text: str) -> None:
        self._texts.append(text)

    def queue_structured(self, obj) -> None:
        if isinstance(obj, BaseModel):
            self._structured.append(obj.model_dump_json())
        elif isinstance(obj, str):
            self._structured.append(obj)
        else:
            self._structured.append(json.dumps(obj))

    def queue_tool_turn(self, *, text: str | None = None, tool_calls: list[ToolCall] | None = None) -> None:
        self._tool_turns.append(ToolTurn(text=text, tool_calls=tool_calls or []))

    def queue_error(self, exc: Exception) -> None:
        self._errors.append(exc)

    def set_embedding(self, text: str, vector: list[float]) -> None:
        self._embeddings[text] = vector

    def calls_to(self, method: str) -> list[dict]:
        return [call for call in self.calls if call["method"] == method]

    def _record(self, method: str, **details) -> None:
        self.calls.append({"method": method, **details})
        if self._errors:
            raise self._errors.popleft()

    def generate(self, *, model, system, prompt, temperature=0.3) -> RawResult:
        self._record("generate", model=model, system=system, prompt=prompt)
        text = self._texts.popleft() if self._texts else "fake response"
        return RawResult(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)

    def generate_structured(self, *, model, system, prompt, schema, temperature=0.2) -> RawResult:
        self._record("generate_structured", model=model, system=system, prompt=prompt, schema=schema.__name__)
        assert self._structured, "no structured response queued"
        text = self._structured.popleft()
        return RawResult(text=text, input_tokens=len(prompt) // 4, output_tokens=len(text) // 4)

    def embed(self, *, model, texts, task_type) -> RawEmbedResult:
        self._record("embed", model=model, texts=list(texts), task_type=task_type)
        vectors = [self._embeddings.get(text) or fake_embedding(text) for text in texts]
        return RawEmbedResult(vectors=vectors, input_tokens=sum(len(text) // 4 for text in texts))

    def describe_image(self, *, model, image_png, prompt) -> RawResult:
        self._record("describe_image", model=model, prompt=prompt, image_bytes=len(image_png))
        text = self._texts.popleft() if self._texts else "fake response"
        return RawResult(text=text, input_tokens=258, output_tokens=len(text) // 4)

    def generate_with_tools(self, *, model, system, transcript, tools) -> ToolTurn:
        self._record(
            "generate_with_tools", model=model, system=system, transcript=list(transcript),
            tools=[tool.name for tool in tools],
        )
        if self._tool_turns:
            return self._tool_turns.popleft()
        return ToolTurn(text="fake response")
