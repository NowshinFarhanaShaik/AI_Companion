from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class AIError(Exception):
    retryable = False


class AIRateLimitError(AIError):
    retryable = True


class AITimeoutError(AIError):
    retryable = True


class AIProviderError(AIError):
    retryable = True


class AIInvalidOutputError(AIError):
    pass


@dataclass
class RawResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class RawEmbedResult:
    vectors: list[list[float]]
    input_tokens: int = 0


@dataclass
class ToolSpec:
    name: str
    description: str
    args_schema: type[BaseModel]


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class ToolTurn:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    # The provider's own model turn. It must be sent back unchanged on the next round:
    # Gemini rejects a rebuilt function-call turn because it lacks the thought signature.
    raw: Any = None
