"""The only module other apps import for AI work: retries, output validation, and one AICallLog row per call.

Do not call these functions inside a long transaction.atomic() block. A network call would hold a database
connection open, and a rollback would erase the log row of a failed call.
"""
import logging
import random
import re
import time
from typing import Callable, TypeVar

from django.conf import settings
from pydantic import BaseModel, ValidationError

from ai.models import AICallLog
from ai.pricing import estimate_cost
from ai.provider import get_provider
from ai.types import AIError, AIInvalidOutputError, AIProviderError, ToolSpec, ToolTurn

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

OCR_PROMPT = (
    "Transcribe all text in this page image exactly as written. Describe any table as rows of text and any "
    "diagram in one sentence. Reply with the transcription only."
)


def _backoff(retry_number: int) -> float:
    base = settings.AI_BACKOFF_BASE_SECONDS
    return min(base * 2 ** (retry_number - 1) + random.uniform(0, base), 30.0)


def _call(*, feature: str, model: str, fn: Callable, user=None, project=None, trace_id=None,
          retrieved_chunk_ids=None, base_retries: int = 0):
    """Run one provider call with retries. Returns (result, log) and always writes exactly one log row."""
    provider = get_provider()
    started = time.monotonic()
    retries, result, error = 0, None, None
    while True:
        try:
            result, error = fn(provider), None
            break
        except AIError as exc:
            error = exc
        except Exception as exc:
            logger.exception("Unexpected AI provider error in %s", feature)
            error = AIProviderError(str(exc))
        if not error.retryable or retries >= settings.AI_MAX_RETRIES:
            break
        retries += 1
        time.sleep(_backoff(retries))

    input_tokens = getattr(result, "input_tokens", 0)
    output_tokens = getattr(result, "output_tokens", 0)
    log = AICallLog.objects.create(
        user=user,
        project=project,
        feature=feature,
        provider=provider.name,
        model=model,
        latency_ms=int((time.monotonic() - started) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost(model, input_tokens, output_tokens),
        status=AICallLog.Status.ERROR if error else AICallLog.Status.OK,
        error_type=type(error).__name__ if error else "",
        error_message=str(error)[:2000] if error else "",
        retries=base_retries + retries,
        retrieved_chunk_ids=[str(chunk_id) for chunk_id in (retrieved_chunk_ids or [])],
        trace_id=trace_id or "",
    )
    if error:
        raise error
    return result, log


def _mark_invalid(log: AICallLog, message: str) -> None:
    log.status = AICallLog.Status.ERROR
    log.error_type = AIInvalidOutputError.__name__
    log.error_message = message[:2000]
    log.save(update_fields=["status", "error_type", "error_message"])


def _strip_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    return (match.group(1) if match else text).strip()


def generate_text(*, feature: str, prompt: str, system: str = "", tier: str = "fast",
                  user=None, project=None, trace_id: str | None = None) -> str:
    model = settings.AI_MODELS[tier]
    result, _ = _call(
        feature=feature, model=model, user=user, project=project, trace_id=trace_id,
        fn=lambda p: p.generate(model=model, system=system, prompt=prompt),
    )
    return result.text.strip()


def generate_structured(*, feature: str, prompt: str, schema: type[T], system: str = "", tier: str = "fast",
                        user=None, project=None, retrieved_chunk_ids: list[str] | None = None,
                        trace_id: str | None = None) -> T:
    model = settings.AI_MODELS[tier]

    def run(current_prompt: str, base_retries: int):
        return _call(
            feature=feature, model=model, user=user, project=project, trace_id=trace_id,
            retrieved_chunk_ids=retrieved_chunk_ids, base_retries=base_retries,
            fn=lambda p: p.generate_structured(model=model, system=system, prompt=current_prompt, schema=schema),
        )

    result, _ = run(prompt, 0)
    try:
        return schema.model_validate_json(_strip_fences(result.text))
    except ValidationError as first_error:
        repair_prompt = (
            f"{prompt}\n\nYour previous reply was not valid for the required JSON schema.\n"
            f"Validation errors:\n{first_error}\n\nReply again with only valid JSON that fixes these errors."
        )
    result, log = run(repair_prompt, 1)
    try:
        return schema.model_validate_json(_strip_fences(result.text))
    except ValidationError as second_error:
        _mark_invalid(log, str(second_error))
        raise AIInvalidOutputError(f"{feature}: the model returned invalid structured output twice") from second_error


def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT", user=None, project=None) -> list[list[float]]:
    model = settings.AI_MODELS["embed"]
    size = settings.AI_EMBED_BATCH_SIZE
    vectors: list[list[float]] = []
    for start in range(0, len(texts), size):
        batch = texts[start:start + size]
        result, log = _call(
            feature="embed", model=model, user=user, project=project,
            fn=lambda p, batch=batch: p.embed(model=model, texts=batch, task_type=task_type),
        )
        if len(result.vectors) != len(batch) or any(len(v) != settings.EMBEDDING_DIM for v in result.vectors):
            _mark_invalid(log, "Embedding count or dimension mismatch")
            raise AIInvalidOutputError("The embedding model returned an unexpected shape")
        vectors.extend(result.vectors)
    return vectors


def embed_query(text: str, *, user=None, project=None) -> list[float]:
    return embed_texts([text], task_type="RETRIEVAL_QUERY", user=user, project=project)[0]


def ocr_image(png_bytes: bytes, *, user=None, project=None) -> str:
    model = settings.AI_MODELS["fast"]
    result, _ = _call(
        feature="ocr", model=model, user=user, project=project,
        fn=lambda p: p.describe_image(model=model, image_png=png_bytes, prompt=OCR_PROMPT),
    )
    return result.text.strip()


def tool_turn(*, feature: str, system: str, transcript: list[dict], tools: list[ToolSpec], tier: str = "strong",
              user=None, project=None, trace_id: str | None = None) -> ToolTurn:
    model = settings.AI_MODELS[tier]
    result, _ = _call(
        feature=feature, model=model, user=user, project=project, trace_id=trace_id,
        fn=lambda p: p.generate_with_tools(model=model, system=system, transcript=transcript, tools=tools),
    )
    return result
