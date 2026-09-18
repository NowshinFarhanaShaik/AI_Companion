from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Job
from events.registry import job_handler
from events.services import enqueue
from events.testing import run_all_jobs
from events.worker import PermanentJobError, claim_next_job, recover_stuck_jobs, run_job, run_once

pytestmark = pytest.mark.django_db


def test_successful_job():
    ran = []

    @job_handler("ok_job")
    def handle(job):
        ran.append(job.payload["n"])

    job = enqueue("ok_job", {"n": 5})
    assert run_once() is True
    job.refresh_from_db()
    assert ran == [5]
    assert (job.status, job.attempts, job.last_error) == ("succeeded", 1, "")
    assert job.finished_at is not None
    assert run_once() is False


def test_failing_job_is_retried_with_backoff(settings):
    settings.JOB_BACKOFF_BASE_SECONDS = 30

    @job_handler("bad_job")
    def handle(job):
        raise RuntimeError("boom")

    job = enqueue("bad_job", {})
    before = timezone.now()
    run_once()
    job.refresh_from_db()
    assert (job.status, job.attempts) == ("queued", 1)
    assert "RuntimeError: boom" in job.last_error
    assert job.run_after >= before + timedelta(seconds=59)  # 30 * 2**1
    assert run_once() is False  # not due yet


def test_job_fails_for_good_after_max_attempts():
    @job_handler("always_bad")
    def handle(job):
        raise RuntimeError("still broken")

    job = enqueue("always_bad", {}, max_attempts=3)
    assert run_all_jobs() == 3
    job.refresh_from_db()
    assert (job.status, job.attempts) == ("failed", 3)
    assert job.finished_at is not None


def test_permanent_error_is_not_retried():
    @job_handler("permanent")
    def handle(job):
        raise PermanentJobError("This file has no readable text.")

    job = enqueue("permanent", {})
    run_once()
    job.refresh_from_db()
    assert (job.status, job.attempts) == ("failed", 1)
    assert "no readable text" in job.last_error


def test_unknown_job_type_fails_without_retry():
    job = enqueue("nobody_handles_this", {})
    run_once()
    job.refresh_from_db()
    assert job.status == "failed"


def test_claim_marks_the_job_running_so_it_cannot_be_claimed_twice():
    enqueue("claim_me", {})
    first = claim_next_job()
    assert first.status == "running" and first.locked_at is not None
    assert claim_next_job() is None


def test_stuck_jobs_are_recovered(settings):
    settings.JOB_STUCK_AFTER_SECONDS = 600
    job = enqueue("stuck", {})
    claimed = claim_next_job()
    Job.objects.filter(id=claimed.id).update(locked_at=timezone.now() - timedelta(seconds=601))
    assert recover_stuck_jobs() == 1
    job.refresh_from_db()
    assert job.status == "queued" and "recovered" in job.last_error


def test_recently_locked_jobs_are_left_alone():
    enqueue("busy", {})
    claim_next_job()
    assert recover_stuck_jobs() == 0


def test_run_job_records_the_error_instead_of_raising():
    @job_handler("explodes")
    def handle(job):
        raise ValueError("x")

    enqueue("explodes", {})
    job = claim_next_job()
    run_job(job)
    assert "ValueError: x" in job.last_error
