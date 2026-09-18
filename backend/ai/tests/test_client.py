import pytest
from pydantic import BaseModel, Field

from ai import client
from ai.models import AICallLog
from ai.types import AIInvalidOutputError, AIProviderError, AIRateLimitError, ToolCall, ToolSpec

pytestmark = pytest.mark.django_db


class Answer(BaseModel):
    value: int = Field(ge=0, le=10)


class NoArgs(BaseModel):
    pass


def test_generate_text_logs_the_call(fake_ai, user, project):
    fake_ai.queue_text("hello")
    text = client.generate_text(feature="summary", prompt="Say hello", user=user, project=project, trace_id="t-1")
    assert text == "hello"
    log = AICallLog.objects.get()
    assert (log.feature, log.status, log.provider, log.trace_id) == ("summary", "ok", "fake", "t-1")
    assert log.user == user and log.project == project
    assert log.model and log.latency_ms >= 0 and log.retries == 0


def test_tier_selects_the_model(fake_ai, settings):
    settings.AI_MODELS = {"fast": "m-fast", "strong": "m-strong", "embed": "m-embed"}
    client.generate_text(feature="tutor", prompt="x", tier="strong")
    assert fake_ai.calls[-1]["model"] == "m-strong"


def test_generate_structured_returns_a_validated_model(fake_ai):
    fake_ai.queue_structured({"value": 7})
    assert client.generate_structured(feature="grading", prompt="x", schema=Answer) == Answer(value=7)


def test_generate_structured_accepts_fenced_json(fake_ai):
    fake_ai.queue_structured('```json\n{"value": 3}\n```')
    assert client.generate_structured(feature="grading", prompt="x", schema=Answer).value == 3


def test_invalid_output_gets_one_repair_retry(fake_ai):
    fake_ai.queue_structured({"value": 99})
    fake_ai.queue_structured({"value": 4})
    assert client.generate_structured(feature="quiz_gen", prompt="x", schema=Answer).value == 4
    calls = fake_ai.calls_to("generate_structured")
    assert len(calls) == 2
    assert "not valid" in calls[1]["prompt"]
    assert list(AICallLog.objects.order_by("created_at").values_list("retries", flat=True)) == [0, 1]


def test_invalid_output_twice_raises_and_logs_an_error(fake_ai):
    fake_ai.queue_structured({"value": 99})
    fake_ai.queue_structured("not json at all")
    with pytest.raises(AIInvalidOutputError):
        client.generate_structured(feature="quiz_gen", prompt="x", schema=Answer)
    last = AICallLog.objects.order_by("created_at").last()
    assert (last.status, last.error_type) == ("error", "AIInvalidOutputError")


def test_retryable_errors_are_retried_then_succeed(fake_ai):
    fake_ai.queue_error(AIRateLimitError("429"))
    fake_ai.queue_text("ok")
    assert client.generate_text(feature="summary", prompt="x") == "ok"
    log = AICallLog.objects.get()
    assert (log.status, log.retries) == ("ok", 1)


def test_retries_are_capped_and_the_failure_is_logged(fake_ai, settings):
    settings.AI_MAX_RETRIES = 2
    for _ in range(3):
        fake_ai.queue_error(AIProviderError("503"))
    with pytest.raises(AIProviderError):
        client.generate_text(feature="summary", prompt="x")
    log = AICallLog.objects.get()
    assert (log.status, log.error_type, log.retries) == ("error", "AIProviderError", 2)
    assert "503" in log.error_message


def test_non_retryable_errors_are_raised_at_once(fake_ai):
    from ai.types import AIError

    fake_ai.queue_error(AIError("bad key"))
    with pytest.raises(AIError):
        client.generate_text(feature="summary", prompt="x")
    assert len(fake_ai.calls) == 1
    assert AICallLog.objects.get().retries == 0


def test_unexpected_exceptions_become_provider_errors(fake_ai):
    for _ in range(3):
        fake_ai.queue_error(RuntimeError("boom"))
    with pytest.raises(AIProviderError):
        client.generate_text(feature="summary", prompt="x")


def test_embed_texts_batches_and_checks_dimensions(fake_ai, settings):
    settings.AI_EMBED_BATCH_SIZE = 2
    vectors = client.embed_texts(["one apple", "two pears", "three plums"])
    assert len(vectors) == 3 and all(len(v) == 768 for v in vectors)
    assert len(fake_ai.calls_to("embed")) == 2
    assert AICallLog.objects.filter(feature="embed").count() == 2


def test_embed_rejects_wrong_dimension(fake_ai):
    fake_ai.set_embedding("bad", [0.1, 0.2])
    with pytest.raises(AIInvalidOutputError):
        client.embed_texts(["bad"])
    assert AICallLog.objects.get().status == "error"


def test_embed_query_uses_the_query_task_type(fake_ai):
    client.embed_query("what is osmosis")
    assert fake_ai.calls[-1]["task_type"] == "RETRIEVAL_QUERY"


def test_embed_empty_list_makes_no_call(fake_ai):
    assert client.embed_texts([]) == []
    assert fake_ai.calls == []


def test_tool_turn_returns_tool_calls_and_logs(fake_ai):
    fake_ai.queue_tool_turn(tool_calls=[ToolCall(name="get_progress", args={})])
    turn = client.tool_turn(
        feature="tutor", system="s", transcript=[{"role": "user", "text": "hi"}],
        tools=[ToolSpec(name="get_progress", description="d", args_schema=NoArgs)],
    )
    assert turn.tool_calls[0].name == "get_progress"
    assert AICallLog.objects.filter(feature="tutor").count() == 1


def test_cost_is_estimated_from_the_price_table(fake_ai, settings):
    settings.AI_MODELS = {"fast": "priced", "strong": "priced", "embed": "priced"}
    settings.AI_PRICES = {"priced": (1_000_000.0, 0.0)}
    client.generate_text(feature="summary", prompt="x" * 400)
    assert AICallLog.objects.get().estimated_cost_usd == 100
