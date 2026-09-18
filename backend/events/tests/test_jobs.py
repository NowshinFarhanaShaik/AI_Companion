import pytest
from django.db import transaction

from events.models import Job
from events.services import enqueue

pytestmark = pytest.mark.django_db


def test_enqueue_creates_a_queued_job():
    job = enqueue("test_job", {"user_id": "u"})
    assert (job.status, job.attempts, job.max_attempts) == ("queued", 0, 4)
    assert job.run_after is not None


def test_enqueue_with_the_same_key_returns_the_existing_job():
    first = enqueue("test_job", {"a": 1}, idempotency_key="same")
    second = enqueue("test_job", {"a": 2}, idempotency_key="same")
    assert first.id == second.id
    assert Job.objects.count() == 1
    assert second.payload == {"a": 1}


def test_a_duplicate_key_does_not_break_the_outer_transaction():
    with transaction.atomic():
        enqueue("test_job", {}, idempotency_key="outer")
        enqueue("test_job", {}, idempotency_key="outer")
        assert Job.objects.count() == 1
