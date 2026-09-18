from pydantic import BaseModel, Field, field_validator

from ai.client import generate_structured
from ai.types import AIError, AIInvalidOutputError
from assessment.prompts import SYSTEM_GRADING, build_grading_prompt
from common.errors import ServiceError
from materials.models import Material

MAX_GRADING_CHUNKS = 3
MAX_ANSWER_CHARS = 4000


class GradedAnswer(BaseModel):
    score: float
    understood: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    feedback: str

    @field_validator("score")
    @classmethod
    def _clamp(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


def grade_mcq(question, selected_option) -> tuple[float, dict]:
    if selected_option is None or not 0 <= selected_option < len(question.options):
        raise ServiceError("Choose one of the options.", status=400, code="invalid_option")
    correct = selected_option == question.correct_option
    explanation = question.rubric.get("explanation", "")
    right_answer = question.options[question.correct_option]
    if correct:
        text = f"Correct. {explanation}".strip()
    else:
        text = f"Not quite. The correct answer is \"{right_answer}\". {explanation}".strip()
    feedback = {
        "understood": [question.concept.name] if correct else [],
        "missing": [] if correct else [question.concept.name],
        "misconceptions": [],
        "feedback": text,
    }
    return (1.0 if correct else 0.0), feedback


def grade_open(*, question, answer_text: str, user) -> tuple[float, dict]:
    answer = (answer_text or "").strip()
    if not answer:
        raise ServiceError("Write an answer before submitting.", status=400, code="empty_answer")
    answer = answer[:MAX_ANSWER_CHARS]

    chunks = []
    if question.source_chunk_id:
        chunks.append(question.source_chunk)
    extra = (
        question.concept.chunks.filter(project=question.project, material__status=Material.Status.READY)
        .exclude(id=question.source_chunk_id)
        .order_by("page_number", "index")[: MAX_GRADING_CHUNKS - len(chunks)]
    )
    chunks.extend(extra)

    try:
        graded = generate_structured(
            feature="grading",
            prompt=build_grading_prompt(question=question, chunks=chunks, answer_text=answer),
            schema=GradedAnswer,
            system=SYSTEM_GRADING,
            tier="strong",
            user=user,
            project=question.project,
            retrieved_chunk_ids=[str(chunk.id) for chunk in chunks],
        )
    except AIInvalidOutputError as exc:
        raise ServiceError(
            "Your answer could not be graded. Please submit it again.", status=502, code="grading_failed"
        ) from exc
    except AIError as exc:
        raise ServiceError(
            "The AI service is unavailable right now. Please try again.", status=503, code="ai_unavailable"
        ) from exc

    return graded.score, graded.model_dump(exclude={"score"})
