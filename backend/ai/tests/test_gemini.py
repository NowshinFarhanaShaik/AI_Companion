from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from ai.gemini import GeminiProvider, map_error
from ai.types import AIError, AIProviderError, AIRateLimitError, AITimeoutError, ToolSpec


class SearchArgs(BaseModel):
    query: str
    limit: int = 5


class NoArgs(BaseModel):
    pass


class StubModels:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.requests = response, error, []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return self.response

    def embed_content(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


def provider_with(models: StubModels) -> GeminiProvider:
    return GeminiProvider(client=SimpleNamespace(models=models))


def usage(prompt=11, output=7):
    return SimpleNamespace(prompt_token_count=prompt, candidates_token_count=output)


TOOLS = [ToolSpec("search_materials", "Search", SearchArgs), ToolSpec("get_progress", "Progress", NoArgs)]


def test_generate_returns_text_and_token_counts():
    models = StubModels(SimpleNamespace(text="hi", usage_metadata=usage()))
    result = provider_with(models).generate(model="m", system="be brief", prompt="hello")
    assert (result.text, result.input_tokens, result.output_tokens) == ("hi", 11, 7)
    assert models.requests[0]["model"] == "m"
    assert models.requests[0]["config"].system_instruction == "be brief"


def test_generate_structured_requests_json_for_the_schema():
    models = StubModels(SimpleNamespace(text='{"query": "x"}', usage_metadata=usage()))
    provider_with(models).generate_structured(model="m", system="", prompt="p", schema=SearchArgs)
    config = models.requests[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is SearchArgs


def test_embed_returns_vectors_and_asks_for_the_configured_dimension(settings):
    response = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2]), SimpleNamespace(values=[0.3, 0.4])])
    models = StubModels(response)
    result = provider_with(models).embed(model="e", texts=["a", "b"], task_type="RETRIEVAL_DOCUMENT")
    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]
    config = models.requests[0]["config"]
    assert (config.output_dimensionality, config.task_type) == (settings.EMBEDDING_DIM, "RETRIEVAL_DOCUMENT")


def test_tool_calls_are_extracted_with_the_raw_turn():
    raw_turn = object()
    call = SimpleNamespace(name="search_materials", args={"query": "osmosis"})
    response = SimpleNamespace(
        text=None, usage_metadata=usage(), function_calls=[call], candidates=[SimpleNamespace(content=raw_turn)]
    )
    models = StubModels(response)
    turn = provider_with(models).generate_with_tools(
        model="m", system="s", transcript=[{"role": "user", "text": "hi"}], tools=TOOLS
    )
    assert (turn.tool_calls[0].name, turn.tool_calls[0].args) == ("search_materials", {"query": "osmosis"})
    assert turn.raw is raw_turn and turn.text is None
    declared = models.requests[0]["config"].tools[0].function_declarations
    assert [d.name for d in declared] == ["search_materials", "get_progress"]
    assert declared[0].parameters_json_schema["required"] == ["query"]


def test_a_turn_without_tool_calls_returns_text():
    response = SimpleNamespace(text="done", usage_metadata=usage(), function_calls=None, candidates=[])
    turn = provider_with(StubModels(response)).generate_with_tools(
        model="m", system="s", transcript=[{"role": "user", "text": "hi"}], tools=TOOLS
    )
    assert (turn.text, turn.tool_calls) == ("done", [])


def test_transcript_replays_the_raw_turn_and_sends_tool_results_as_user():
    from google.genai import types

    raw_turn = types.Content(role="model", parts=[types.Part.from_function_call(name="get_progress", args={})])
    response = SimpleNamespace(text="ok", usage_metadata=usage(), function_calls=None, candidates=[])
    models = StubModels(response)
    provider_with(models).generate_with_tools(
        model="m", system="s", tools=TOOLS,
        transcript=[
            {"role": "user", "text": "How am I doing?"},
            {"role": "model", "text": None, "tool_calls": [{"name": "get_progress", "args": {}}], "raw": raw_turn},
            {"role": "tool", "name": "get_progress", "result": {"average_mastery": 0.4}},
        ],
    )
    contents = models.requests[0]["contents"]
    assert contents[1] is raw_turn
    assert [content.role for content in contents] == ["user", "model", "user"]
    assert contents[2].parts[0].function_response.response == {"average_mastery": 0.4}


@pytest.mark.parametrize(
    "code, expected",
    [(429, AIRateLimitError), (500, AIProviderError), (503, AIProviderError), (400, AIError), (403, AIError)],
)
def test_api_errors_are_mapped(code, expected):
    error = map_error(SimpleNamespace(code=code, message="boom"))
    assert type(error) is expected
    assert error.retryable is (code in (429, 500, 503))


def test_timeouts_are_mapped():
    assert isinstance(map_error(TimeoutError("slow")), AITimeoutError)


def test_provider_wraps_sdk_errors():
    class FakeAPIError(Exception):
        code = 429
        message = "quota"

    with pytest.raises(AIRateLimitError):
        provider_with(StubModels(error=FakeAPIError())).generate(model="m", system="", prompt="p")
