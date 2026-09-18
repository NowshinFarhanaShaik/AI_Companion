import pytest

from assessment.models import Attempt, Question, QuizSession
from assessment.services import next_question, start_session, submit_answer
from common.errors import ServiceError
from common.testing import make_chunk, make_concept, make_material
from events.models import LearningEvent

pytestmark = pytest.mark.django_db


def queue_mcq(fake_ai, body="Which process stores light energy as glucose?"):
    fake_ai.queue_structured({
        "body": body,
        "options": ["Photosynthesis", "Respiration", "Fermentation", "Transpiration"],
        "correct_option": 0,
        "explanation": "Photosynthesis stores light energy as glucose.",
    })


def structured_calls(fake_ai):
    return [call for call in fake_ai.calls if call["method"] == "generate_structured"]


def events(event_type):
    return LearningEvent.objects.filter(type=event_type)


@pytest.fixture
def ready_project(project):
    material = make_material(project, status="ready")
    chunk = make_chunk(project, material, "Photosynthesis stores light energy as glucose.", page=1)
    make_concept(project, "Photosynthesis", chunks=[chunk], mastery=0.3)
    return project


def test_start_session_requires_processed_concepts(user, project):
    with pytest.raises(ServiceError) as excinfo:
        start_session(user=user, project=project)
    assert excinfo.value.status == 400
    assert excinfo.value.code == "no_concepts"
    assert QuizSession.objects.count() == 0


def test_start_session_emits_quiz_started_and_touches_the_project(user, ready_project):
    before = ready_project.last_activity_at
    session = start_session(user=user, project=ready_project, target_question_count=3)

    assert session.status == "active"
    assert session.target_question_count == 3
    event = events("quiz.started").get()
    assert event.payload["session_id"] == str(session.id)
    ready_project.refresh_from_db()
    assert ready_project.last_activity_at is not None
    assert before is None or ready_project.last_activity_at >= before


def test_target_question_count_is_clamped(user, ready_project):
    assert start_session(user=user, project=ready_project, target_question_count=99).target_question_count == 10
    assert start_session(user=user, project=ready_project, target_question_count=0).target_question_count == 1


def test_next_question_is_idempotent_until_answered(user, ready_project, fake_ai):
    session = start_session(user=user, project=ready_project, target_question_count=2)
    queue_mcq(fake_ai)

    first = next_question(user=user, session=session)
    again = next_question(user=user, session=session)

    assert again.id == first.id
    assert Question.objects.filter(session=session).count() == 1
    assert len(structured_calls(fake_ai)) == 1


def test_submit_answer_saves_an_attempt_and_emits_question_answered(user, ready_project, fake_ai):
    session = start_session(user=user, project=ready_project, target_question_count=2)
    queue_mcq(fake_ai)
    question = next_question(user=user, session=session)

    attempt = submit_answer(user=user, question=question, selected_option=question.correct_option)

    assert attempt.score == 1.0
    assert attempt.selected_option == question.correct_option
    assert attempt.evaluated_at is not None
    assert attempt.feedback["feedback"].startswith("Correct.")
    event = events("question.answered").get()
    assert event.payload["attempt_id"] == str(attempt.id)
    assert event.payload["concept_id"] == str(question.concept_id)
    assert event.payload["score"] == 1.0
    session.refresh_from_db()
    assert session.status == "active"
    assert events("quiz.completed").count() == 0


def test_a_question_cannot_be_answered_twice(user, ready_project, fake_ai):
    session = start_session(user=user, project=ready_project, target_question_count=2)
    queue_mcq(fake_ai)
    question = next_question(user=user, session=session)
    submit_answer(user=user, question=question, selected_option=0)

    with pytest.raises(ServiceError) as excinfo:
        submit_answer(user=user, question=question, selected_option=1)

    assert excinfo.value.status == 409
    assert excinfo.value.code == "already_answered"
    assert Attempt.objects.filter(question=question).count() == 1


def test_an_invalid_answer_saves_nothing(user, ready_project, fake_ai):
    session = start_session(user=user, project=ready_project, target_question_count=2)
    queue_mcq(fake_ai)
    question = next_question(user=user, session=session)
    with pytest.raises(ServiceError):
        submit_answer(user=user, question=question, selected_option=9)
    assert Attempt.objects.count() == 0
    assert events("question.answered").count() == 0


def test_the_last_answer_completes_the_session_and_emits_quiz_completed_once(user, ready_project, fake_ai):
    session = start_session(user=user, project=ready_project, target_question_count=2)

    queue_mcq(fake_ai, body="First question about photosynthesis?")
    first = next_question(user=user, session=session)
    submit_answer(user=user, question=first, selected_option=0)

    queue_mcq(fake_ai, body="Second question about photosynthesis?")
    second = next_question(user=user, session=session)
    assert second.id != first.id
    submit_answer(user=user, question=second, selected_option=1)

    session.refresh_from_db()
    assert session.status == "completed"
    assert session.completed_at is not None
    completed = events("quiz.completed").get()
    assert completed.payload["session_id"] == str(session.id)
    assert completed.idempotency_key == f"quiz-completed:{session.id}"

    with pytest.raises(ServiceError) as excinfo:                 # a retried final submit
        submit_answer(user=user, question=second, selected_option=1)
    assert excinfo.value.code == "already_answered"
    assert events("quiz.completed").count() == 1

    assert next_question(user=user, session=session) is None
    assert Question.objects.filter(session=session).count() == 2
