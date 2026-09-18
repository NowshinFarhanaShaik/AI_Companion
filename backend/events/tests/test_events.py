import pytest

from events.models import Job, LearningEvent
from events.registry import on_event
from events.services import emit, enqueue

pytestmark = pytest.mark.django_db


def test_emit_stores_the_event_and_fills_the_space_from_the_project(user, project):
    event = emit(type="test.happened", user=user, project=project, payload={"n": 1})
    assert event.type == "test.happened"
    assert event.project == project and event.payload == {"n": 1}
    assert event.space == project.space


def test_duplicate_idempotency_key_is_ignored(user):
    first = emit(type="test.once", user=user, idempotency_key="k-1")
    second = emit(type="test.once", user=user, idempotency_key="k-1")
    assert first is not None and second is None
    assert LearningEvent.objects.filter(type="test.once").count() == 1


def test_events_without_a_key_are_never_deduplicated(user):
    emit(type="test.many", user=user)
    emit(type="test.many", user=user)
    assert LearningEvent.objects.filter(type="test.many").count() == 2


def test_handlers_run_and_can_enqueue_jobs(user):
    @on_event("test.dispatch")
    def handler(event):
        enqueue("test_job", {"user_id": str(event.user_id)}, idempotency_key=f"job:{event.id}")

    emit(type="test.dispatch", user=user)
    assert Job.objects.filter(type="test_job").count() == 1


def test_duplicate_event_does_not_run_handlers_again(user):
    seen = []

    @on_event("test.dedupe")
    def handler(event):
        seen.append(event.id)

    emit(type="test.dedupe", user=user, idempotency_key="k-2")
    emit(type="test.dedupe", user=user, idempotency_key="k-2")
    assert len(seen) == 1


def test_a_failing_handler_rolls_the_event_back(user):
    @on_event("test.rollback")
    def handler(event):
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError):
        emit(type="test.rollback", user=user)
    assert LearningEvent.objects.filter(type="test.rollback").count() == 0


def test_for_user_scopes_events(user, other_user):
    emit(type="test.scope", user=user)
    emit(type="test.scope", user=other_user)
    assert LearningEvent.objects.for_user(user).filter(type="test.scope").count() == 1
