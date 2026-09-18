import random
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ai.client import generate_structured
from ai.types import AIError, AIInvalidOutputError
from assessment.models import Question
from assessment.prompts import SYSTEM_QUIZ, build_generation_prompt
from common.errors import ServiceError
from materials.models import Material

MAX_SOURCE_CHUNKS = 4
PREVIOUS_QUESTIONS_SHOWN = 5

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GeneratedMCQ(BaseModel):
    body: Text
    options: list[Text] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3)
    explanation: Text

    @field_validator("options")
    @classmethod
    def _distinct(cls, options: list[str]) -> list[str]:
        if len({option.lower() for option in options}) != len(options):
            raise ValueError("options must be distinct")
        return options


class GeneratedOpen(BaseModel):
    body: Text
    key_points: list[Text] = Field(min_length=2, max_length=6)


def generate_question(*, project, session, selection, user) -> Question:
    concept = selection.concept
    chunks = list(
        concept.chunks.filter(project=project, material__status=Material.Status.READY)
        .order_by("?")[:MAX_SOURCE_CHUNKS]
    )
    if not chunks:
        raise ServiceError("This concept has no processed material yet.", code="no_source_chunks")

    is_mcq = selection.qtype == Question.Type.MCQ
    previous_bodies = list(
        Question.objects.filter(project=project, concept=concept)
        .order_by("-created_at")
        .values_list("body", flat=True)[:PREVIOUS_QUESTIONS_SHOWN]
    )
    try:
        generated = generate_structured(
            feature="quiz_gen", tier="fast", system=SYSTEM_QUIZ,
            schema=GeneratedMCQ if is_mcq else GeneratedOpen,
            prompt=build_generation_prompt(
                concept=concept, difficulty=selection.difficulty, qtype=selection.qtype, chunks=chunks,
                previous_bodies=previous_bodies, learning_goal=project.learning_goal,
            ),
            user=user, project=project, retrieved_chunk_ids=[str(chunk.id) for chunk in chunks],
        )
    except AIInvalidOutputError as exc:
        raise ServiceError(
            "The question could not be generated. Please try again.", status=502, code="quiz_generation_failed"
        ) from exc
    except AIError as exc:
        raise ServiceError(
            "The AI service is unavailable right now. Please try again.", status=503, code="ai_unavailable"
        ) from exc

    options, correct_option, rubric = [], None, {}
    if is_mcq:
        # Models favour one answer position, so the server decides the order.
        order = random.sample(range(4), 4)
        options = [generated.options[i] for i in order]
        correct_option = order.index(generated.correct_option)
        rubric = {"explanation": generated.explanation}
    else:
        rubric = {"key_points": generated.key_points}

    return Question.objects.create(
        project=project, session=session, concept=concept, type=selection.qtype, difficulty=selection.difficulty,
        body=generated.body, options=options, correct_option=correct_option, rubric=rubric, source_chunk=chunks[0],
    )
