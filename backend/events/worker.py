import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from events.models import Job
from events.registry import get_job_handler

logger = logging.getLogger(__name__)


class PermanentJobError(Exception):
    """Raised by a handler when a retry cannot help, for example an unreadable file."""


def claim_next_job(*, ignore_run_after: bool = False) -> Job | None:
    # SKIP LOCKED lets several workers poll the same table without blocking each other.
    with transaction.atomic():
        queued = Job.objects.select_for_update(skip_locked=True).filter(status=Job.Status.QUEUED)
        if not ignore_run_after:
            queued = queued.filter(run_after__lte=timezone.now())
        job = queued.order_by("run_after", "created_at").first()
        if job is None:
            return None
        job.status = Job.Status.RUNNING
        job.locked_at = timezone.now()
        job.attempts += 1
        job.save(update_fields=["status", "locked_at", "attempts", "updated_at"])
        return job


def run_job(job: Job) -> None:
    handler = get_job_handler(job.type)
    try:
        if handler is None:
            raise PermanentJobError(f"No handler is registered for job type '{job.type}'")
        handler(job)
    except Exception as exc:
        logger.exception("Job %s (%s) failed on attempt %s", job.id, job.type, job.attempts)
        job.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        if isinstance(exc, PermanentJobError) or job.attempts >= job.max_attempts:
            job.status = Job.Status.FAILED
            job.finished_at = timezone.now()
        else:
            job.status = Job.Status.QUEUED
            job.run_after = timezone.now() + timedelta(seconds=settings.JOB_BACKOFF_BASE_SECONDS * 2**job.attempts)
    else:
        job.status = Job.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.last_error = ""
    job.locked_at = None
    job.save(update_fields=["status", "finished_at", "run_after", "locked_at", "last_error", "updated_at"])


def run_once(*, ignore_run_after: bool = False) -> bool:
    job = claim_next_job(ignore_run_after=ignore_run_after)
    if job is None:
        return False
    run_job(job)
    return True


def recover_stuck_jobs() -> int:
    """A job left 'running' by a crashed or restarted container returns to the queue. Handlers are idempotent."""
    cutoff = timezone.now() - timedelta(seconds=settings.JOB_STUCK_AFTER_SECONDS)
    return Job.objects.filter(status=Job.Status.RUNNING, locked_at__lt=cutoff).update(
        status=Job.Status.QUEUED, locked_at=None, run_after=timezone.now(),
        last_error="recovered: the worker stopped while this job was running",
    )
