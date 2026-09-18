from django.db import IntegrityError, transaction
from django.utils import timezone

from assessment.generation import generate_question
from assessment.grading import grade_mcq, grade_open
from assessment.models import Attempt, Question, QuizSession
from assessment.selection import eligible_concepts, select_next
from common.errors import ServiceError
from events.services import emit
from workspace.services import touch_project

MIN_QUESTIONS = 1
MAX_QUESTIONS = 10


def _no_concepts() -> ServiceError:
    return ServiceError(
        "Upload a PDF and wait for it to finish processing before starting a quiz.", status=400, code="no_concepts"
    )


@transaction.atomic
def start_session(*, user, project, target_question_count: int = 5) -> QuizSession:
    if not eligible_concepts(project).exists():
        raise _no_concepts()
    count = max(MIN_QUESTIONS, min(MAX_QUESTIONS, target_question_count))
    session = QuizSession.objects.create(project=project, target_question_count=count)
    emit(
        type="quiz.started",
        user=user,
        project=project,
        payload={"session_id": str(session.id), "target_question_count": count},
        idempotency_key=f"quiz-started:{session.id}",
    )
    touch_project(project)
    return session


def next_question(*, user, session) -> Question | None:
    """Returns the current unanswered question if there is one; otherwise selects and generates the next.

    Calling it twice without answering returns the same question and makes no second AI call.
    """
    if session.status == QuizSession.Status.COMPLETED:
        return None
    pending = session.questions.filter(attempt__isnull=True).order_by("created_at").first()
    if pending is not None:
        return pending
    if session.questions.count() >= session.target_question_count:
        return None
    selection = select_next(project=session.project, session=session)
    if selection is None:
        raise _no_concepts()
    return generate_question(project=session.project, session=session, selection=selection, user=user)


def _already_answered() -> ServiceError:
    return ServiceError("This question has already been answered.", status=409, code="already_answered")


def submit_answer(*, user, question, selected_option: int | None = None, answer_text: str = "") -> Attempt:
    if Attempt.objects.filter(question=question).exists():
        raise _already_answered()

    # Grading may call the AI provider, so it runs before the database transaction opens.
    if question.type == Question.Type.MCQ:
        score, feedback = grade_mcq(question, selected_option)
        answer_text = ""
    else:
        score, feedback = grade_open(question=question, answer_text=answer_text, user=user)
        selected_option = None

    session = question.session
    project = question.project
    with transaction.atomic():
        try:
            with transaction.atomic():
                attempt = Attempt.objects.create(
                    question=question,
                    project=project,
                    answer_text=(answer_text or "").strip(),
                    selected_option=selected_option,
                    score=score,
                    feedback=feedback,
                    evaluated_at=timezone.now(),
                )
        except IntegrityError as exc:                     # a concurrent submit won the one-to-one
            raise _already_answered() from exc

        emit(
            type="question.answered",
            user=user,
            project=project,
            payload={
                "session_id": str(session.id),
                "question_id": str(question.id),
                "attempt_id": str(attempt.id),
                "concept_id": str(question.concept_id),
                "score": score,
            },
            idempotency_key=f"question-answered:{question.id}",
        )

        answered = Attempt.objects.filter(question__session=session).count()
        if answered >= session.target_question_count and session.status != QuizSession.Status.COMPLETED:
            session.status = QuizSession.Status.COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at", "updated_at"])
            emit(
                type="quiz.completed",
                user=user,
                project=project,
                payload={"session_id": str(session.id), "answered": answered},
                idempotency_key=f"quiz-completed:{session.id}",
            )
        touch_project(project)
    return attempt
