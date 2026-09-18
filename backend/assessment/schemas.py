from collections import defaultdict
from datetime import datetime
from statistics import mean
from uuid import UUID

from ninja import Field, Schema


def _attempt(question):
    # The reverse one-to-one raises an AttributeError subclass when the question is unanswered.
    return getattr(question, "attempt", None)


def _answered(session) -> list:
    return [question for question in session.questions.all() if _attempt(question)]


class StartSessionIn(Schema):
    target_question_count: int = Field(5, ge=1, le=10)


class AnswerIn(Schema):
    selected_option: int | None = None
    answer_text: str = Field("", max_length=4000)


class FeedbackOut(Schema):
    understood: list[str] = []
    missing: list[str] = []
    misconceptions: list[str] = []
    feedback: str = ""


class AttemptOut(Schema):
    id: UUID
    selected_option: int | None
    answer_text: str
    score: float
    feedback: FeedbackOut
    evaluated_at: datetime


class QuestionOut(Schema):
    id: UUID
    session_id: UUID
    concept_id: UUID
    concept_name: str
    type: str
    difficulty: int
    body: str
    options: list[str]
    answered: bool
    attempt: AttemptOut | None
    # Revealed only once the question is answered. The rubric itself is never sent.
    correct_option: int | None
    explanation: str | None
    key_points: list[str] | None

    @staticmethod
    def resolve_concept_name(obj) -> str:
        return obj.concept.name

    @staticmethod
    def resolve_answered(obj) -> bool:
        return _attempt(obj) is not None

    @staticmethod
    def resolve_attempt(obj):
        return _attempt(obj)

    @staticmethod
    def resolve_correct_option(obj):
        return obj.correct_option if _attempt(obj) else None

    @staticmethod
    def resolve_explanation(obj):
        return obj.rubric.get("explanation") if _attempt(obj) else None

    @staticmethod
    def resolve_key_points(obj):
        return obj.rubric.get("key_points") if _attempt(obj) else None


class ConceptSummaryOut(Schema):
    concept_id: UUID
    concept_name: str
    average_score: float
    question_count: int


class SummaryOut(Schema):
    answered_count: int
    average_score: float
    by_concept: list[ConceptSummaryOut]


class SessionOut(Schema):
    """Expects a session whose questions are prefetched with their concept and attempt."""

    id: UUID
    project_id: UUID
    status: str
    target_question_count: int
    answered_count: int
    completed_at: datetime | None
    created_at: datetime
    questions: list[QuestionOut]
    summary: SummaryOut | None

    @staticmethod
    def resolve_answered_count(obj) -> int:
        return len(_answered(obj))

    @staticmethod
    def resolve_questions(obj) -> list:
        return list(obj.questions.all())

    @staticmethod
    def resolve_summary(obj):
        answered = _answered(obj)
        if not answered:
            return None
        scores_by_concept = defaultdict(list)
        for question in answered:
            scores_by_concept[question.concept].append(question.attempt.score)
        return {
            "answered_count": len(answered),
            "average_score": mean(question.attempt.score for question in answered),
            "by_concept": [
                {"concept_id": concept.id, "concept_name": concept.name,
                 "average_score": mean(scores), "question_count": len(scores)}
                for concept, scores in scores_by_concept.items()
            ],
        }


class NextOut(Schema):
    question: QuestionOut | None
    completed: bool


class AnswerOut(Schema):
    question: QuestionOut
    session_completed: bool
