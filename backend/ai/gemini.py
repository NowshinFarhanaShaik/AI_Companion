"""Google Gemini implementation of ai.provider.Provider. The only module that imports the google-genai SDK."""
from django.conf import settings
from google import genai
from google.genai import types

from ai.types import (
    AIError, AIProviderError, AIRateLimitError, AITimeoutError, RawEmbedResult, RawResult, ToolCall, ToolSpec, ToolTurn,
)


def map_error(exc) -> AIError:
    if isinstance(exc, AIError):
        return exc
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        return AITimeoutError(str(exc))
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    if code == 429:
        return AIRateLimitError(message)
    if isinstance(code, int) and 400 <= code < 500:
        return AIError(message)  # bad request, bad key or blocked content: a retry cannot help
    return AIProviderError(message)


def _usage(response) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    return getattr(usage, "prompt_token_count", 0) or 0, getattr(usage, "candidates_token_count", 0) or 0


def _contents(transcript: list[dict]) -> list:
    contents = []
    for entry in transcript:
        if entry["role"] == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=entry["text"])]))
        elif entry["role"] == "model":
            contents.append(entry["raw"])
        else:
            # The API rejects role "tool" here; a function response travels as a user turn.
            part = types.Part.from_function_response(name=entry["name"], response=entry["result"])
            contents.append(types.Content(role="user", parts=[part]))
    return contents


class GeminiProvider:
    name = "gemini"

    def __init__(self, client=None):
        if client is None:
            if not settings.GEMINI_API_KEY:
                raise AIError("GEMINI_API_KEY is not set")
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=settings.AI_TIMEOUT_SECONDS * 1000),
            )
        self.client = client

    def _generate(self, *, model, contents, config):
        try:
            return self.client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as exc:
            raise map_error(exc) from exc

    def _text_result(self, *, model, contents, config) -> RawResult:
        response = self._generate(model=model, contents=contents, config=config)
        input_tokens, output_tokens = _usage(response)
        return RawResult(text=response.text or "", input_tokens=input_tokens, output_tokens=output_tokens)

    def generate(self, *, model, system, prompt, temperature=0.3) -> RawResult:
        config = types.GenerateContentConfig(system_instruction=system or None, temperature=temperature)
        return self._text_result(model=model, contents=prompt, config=config)

    def generate_structured(self, *, model, system, prompt, schema, temperature=0.2) -> RawResult:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )
        return self._text_result(model=model, contents=prompt, config=config)

    def describe_image(self, *, model, image_png, prompt) -> RawResult:
        contents = [types.Part.from_bytes(data=image_png, mime_type="image/png"), prompt]
        return self._text_result(model=model, contents=contents, config=types.GenerateContentConfig(temperature=0.0))

    def embed(self, *, model, texts, task_type) -> RawEmbedResult:
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=settings.EMBEDDING_DIM)
        try:
            response = self.client.models.embed_content(model=model, contents=list(texts), config=config)
        except Exception as exc:
            raise map_error(exc) from exc
        # The embedding endpoint reports no usage, so tokens are estimated at four characters each.
        return RawEmbedResult(
            vectors=[list(item.values) for item in response.embeddings],
            input_tokens=sum(len(text) // 4 for text in texts),
        )

    def generate_with_tools(self, *, model, system, transcript, tools: list[ToolSpec]) -> ToolTurn:
        declarations = [
            types.FunctionDeclaration(
                name=tool.name, description=tool.description,
                parameters_json_schema=tool.args_schema.model_json_schema(),
            )
            for tool in tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=0.2,
            tools=[types.Tool(function_declarations=declarations)],
        )
        response = self._generate(model=model, contents=_contents(transcript), config=config)
        input_tokens, output_tokens = _usage(response)
        calls = [ToolCall(name=call.name, args=dict(call.args or {})) for call in (response.function_calls or [])]
        candidates = response.candidates or []
        return ToolTurn(
            text=None if calls else (response.text or ""),
            tool_calls=calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=candidates[0].content if candidates else None,
        )
