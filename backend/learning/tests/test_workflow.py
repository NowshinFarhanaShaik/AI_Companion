import uuid

import pytest

from common.testing import make_chunk, make_concept, make_material
from events.models import Job
from events.registry import get_job_handler
from events.services import emit, enqueue
from events.testing import run_all_jobs
from learning.models import ConceptMastery, LearnerMemory, MasterySnapshot, Recommendation
from learning.tests.factories import make_attempt, make_session

pytestmark = pytest.mark.django_db


def test_answering_a_question_updates_mastery_before_any_job_runs(user, project):
    """The next question of the same session is selected from mastery, so the update cannot wait for the worker."""
    concept = make_concept(project, "Calvin cycle", mastery=0.3)
    session = make_session(project)
    attempt = make_attempt(project, concept, score=1.0, difficulty=2, session=session)

    emit(
        type="question.answered", user=user, project=project,
        payload={"session_id": str(session.id), "attempt_id": str(attempt.id)},
        idempotency_key=f"question-answered:{attempt.question_id}",
    )

    mastery = ConceptMastery.objects.get(project=project, concept=concept)
    assert mastery.score > 0.3 and mastery.evidence_count == 1
    assert MasterySnapshot.objects.filter(attempt=attempt).count() == 1
    assert Job.objects.filter(type="update_mastery").count() == 0


def test_the_completion_job_does_not_apply_an_attempt_twice(user, project):
    concept = make_concept(project, "Calvin cycle", mastery=0.3)
    session = make_session(project)
    attempt = make_attempt(project, concept, score=1.0, difficulty=2, session=session)
    emit(type="question.answered", user=user, project=project, payload={"attempt_id": str(attempt.id)})
    after_answer = ConceptMastery.objects.get(project=project, concept=concept).score

    emit(type="quiz.completed", user=user, project=project, payload={"session_id": str(session.id)},
         idempotency_key=f"quiz-completed:{session.id}")
    run_all_jobs()

    mastery = ConceptMastery.objects.get(project=project, concept=concept)
    assert mastery.score == after_answer and mastery.evidence_count == 1
    assert MasterySnapshot.objects.filter(attempt=attempt).count() == 1


def test_an_answer_event_for_another_users_attempt_is_ignored(user, other_user, other_project):
    concept = make_concept(other_project, "Cold War", mastery=0.3)
    attempt = make_attempt(other_project, concept, score=1.0, difficulty=2)

    emit(type="question.answered", user=user, payload={"attempt_id": str(attempt.id)})

    assert ConceptMastery.objects.get(project=other_project, concept=concept).evidence_count == 0


def _completed_quiz(project, *, scores=(0.0, 0.0, 0.0)):
    material = make_material(project, title="Biology Notes", status="ready")
    chunk = make_chunk(project, material, "Chloroplast text", page=2)
    concept = make_concept(project, "Chloroplast", chunks=(chunk,))
    session = make_session(project, status="completed", target=len(scores))
    for score in scores:
        make_attempt(project, concept, score=score, difficulty=1, session=session)
    return session, concept


def _emit_quiz_completed(user, project, session):
    return emit(
        type="quiz.completed",
        user=user,
        project=project,
        payload={"session_id": str(session.id)},
        idempotency_key=f"quiz-completed:{session.id}",
    )


def test_completed_quiz_updates_mastery_and_creates_one_recommendation(user, project):
    session, concept = _completed_quiz(project)

    _emit_quiz_completed(user, project, session)
    processed = run_all_jobs()

    assert processed == 3          # update_mastery, detect_weakness, generate_recommendation
    assert MasterySnapshot.objects.filter(project=project).count() == 3
    mastery = ConceptMastery.objects.get(project=project, concept=concept)
    assert mastery.evidence_count == 3
    assert mastery.consecutive_misses == 3
    assert mastery.score < 0.3
    assert LearnerMemory.objects.filter(project=project, kind="repeated_mistake", concept=concept).count() == 1
    active = Recommendation.objects.filter(project=project, status="active")
    assert active.count() == 1
    assert active.first().action_type == "ask_tutor"
    assert set(Job.objects.values_list("status", flat=True)) == {"succeeded"}


def test_duplicate_event_and_re_run_jobs_do_not_double_apply(user, project):
    session, concept = _completed_quiz(project)
    _emit_quiz_completed(user, project, session)
    run_all_jobs()
    score_after_first_run = ConceptMastery.objects.get(project=project, concept=concept).score

    # The same event again: emit returns None and no new job appears.
    assert _emit_quiz_completed(user, project, session) is None
    assert run_all_jobs() == 0

    # A retried job (for example after a worker crash) runs the handlers a second time.
    for job_type in ("update_mastery", "detect_weakness", "generate_recommendation"):
        job = Job.objects.get(type=job_type)
        get_job_handler(job_type)(job)

    mastery = ConceptMastery.objects.get(project=project, concept=concept)
    assert mastery.score == score_after_first_run
    assert mastery.evidence_count == 3
    assert MasterySnapshot.objects.filter(project=project).count() == 3
    assert LearnerMemory.objects.filter(project=project, kind="repeated_mistake").count() == 1
    assert Recommendation.objects.filter(project=project).count() == 1


def test_quiz_completed_enqueues_with_an_idempotency_key(user, project):
    session, _ = _completed_quiz(project)

    _emit_quiz_completed(user, project, session)

    job = Job.objects.get(type="update_mastery")
    assert job.idempotency_key == f"update-mastery:{session.id}"
    assert job.payload == {
        "user_id": str(user.id),
        "project_id": str(project.id),
        "session_id": str(session.id),
    }


def test_material_processed_generates_a_recommendation(user, project):
    material = make_material(project, title="Biology Notes", status="ready")
    chunk = make_chunk(project, material, "Chloroplast text", page=2)
    make_concept(project, "Chloroplast", chunks=(chunk,))

    emit(
        type="material.processed",
        user=user,
        project=project,
        payload={"material_id": str(material.id)},
        idempotency_key=f"material-processed:{material.id}",
    )
    job = Job.objects.get(type="generate_recommendation")
    assert job.idempotency_key == f"recommend:material:{material.id}"
    run_all_jobs()

    rec = Recommendation.objects.get(project=project, status="active")
    assert rec.action_type == "take_quiz"


def test_jobs_exit_quietly_when_the_project_is_gone(user):
    payload = {"user_id": str(user.id), "project_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4())}
    for job_type in ("update_mastery", "detect_weakness", "generate_recommendation"):
        job = enqueue(job_type, payload, idempotency_key=f"gone:{job_type}")
        get_job_handler(job_type)(job)        # must not raise

    assert Recommendation.objects.count() == 0


def test_a_job_cannot_touch_another_users_project(other_user, project):
    # The payload names `other_user` but a project that belongs to `user`.
    session, _ = _completed_quiz(project, scores=(1.0,))
    payload = {"user_id": str(other_user.id), "project_id": str(project.id), "session_id": str(session.id)}

    job = enqueue("update_mastery", payload, idempotency_key="cross-user")
    get_job_handler("update_mastery")(job)

    assert MasterySnapshot.objects.count() == 0
