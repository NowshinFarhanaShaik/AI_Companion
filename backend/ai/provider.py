from typing import Protocol

from django.conf import settings

from ai.types import RawEmbedResult, RawResult, ToolSpec, ToolTurn


class Provider(Protocol):
    name: str

    def generate(self, *, model: str, system: str, prompt: str, temperature: float = 0.3) -> RawResult: ...

    def generate_structured(
        self, *, model: str, system: str, prompt: str, schema: type, temperature: float = 0.2
    ) -> RawResult: ...

    def embed(self, *, model: str, texts: list[str], task_type: str) -> RawEmbedResult: ...

    def describe_image(self, *, model: str, image_png: bytes, prompt: str) -> RawResult: ...

    def generate_with_tools(
        self, *, model: str, system: str, transcript: list[dict], tools: list[ToolSpec]
    ) -> ToolTurn: ...


_provider: Provider | None = None


def get_provider() -> Provider:
    global _provider
    if _provider is None:
        if settings.AI_PROVIDER == "fake":
            from ai.testing import FakeProvider

            _provider = FakeProvider()
        else:
            from ai.gemini import GeminiProvider

            _provider = GeminiProvider()
    return _provider


def set_provider(provider: Provider | None) -> None:
    global _provider
    _provider = provider
