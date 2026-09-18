from django.db import IntegrityError, transaction
from django.utils import timezone

from events.models import Job, LearningEvent
from events.registry import dispatch_event


def emit(*, type: str, user, project=None, space=None, payload: dict | None = None,
         idempotency_key: str | None = None) -> LearningEvent | None:
    """Record a learning event and run its handlers in one transaction. Returns None for a duplicate key.

    Handlers enqueue Job rows. Because the queue is a Postgres table, the event and its jobs commit or
    roll back together (a transactional outbox), and the worker only ever sees committed jobs.
    """
    if space is None and project is not None:
        space = project.space
    with transaction.atomic():
        try:
            with transaction.atomic():  # savepoint: a duplicate key must not poison the outer transaction
                event = LearningEvent.objects.create(
                    type=type, user=user, project=project, space=space,
                    payload=payload or {}, idempotency_key=idempotency_key,
                )
        except IntegrityError:
            return None
        dispatch_event(event)
    return event


def enqueue(job_type: str, payload: dict, *, idempotency_key: str | None = None,
            run_after=None, max_attempts: int = 4) -> Job:
    """Add a job. With an idempotency key, a second call returns the job that already exists."""
    try:
        with transaction.atomic():
            return Job.objects.create(
                type=job_type, payload=payload, idempotency_key=idempotency_key,
                run_after=run_after or timezone.now(), max_attempts=max_attempts,
            )
    except IntegrityError:
        return Job.objects.get(idempotency_key=idempotency_key)
