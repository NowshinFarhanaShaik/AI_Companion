"""Operational reads for staff, plus the one admin write: retrying a failed job."""
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Aggregate, Avg, Count, F, FloatField, Max, Min, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ai.models import AICallLog, EvalRun
from common.errors import ServiceError
from events.models import Job
from insights.queries import optional_round

SLOWEST_CALLS = 20
RECENT_FAILURES = 20

# Health thresholds
BACKLOG_AMBER_SECONDS = 5 * 60
BACKLOG_RED_SECONDS = 30 * 60
FAILED_JOBS_RED = 5
AI_ERROR_MIN_CALLS = 5                        # do not alarm on one failed call out of two
AI_ERROR_AMBER = 0.2
AI_ERROR_RED = 0.5
SEVERITY = {"green": 0, "amber": 1, "red": 2}


class Percentile(Aggregate):
    """PERCENTILE_CONT computed by Postgres.

    Chosen over loading latencies into Python: the API container has 512 MB of
    RAM and AICallLog grows with every AI call, so the database does the sort
    and returns one number. Postgres is the only database this project targets.
    """

    function = "PERCENTILE_CONT"
    name = "Percentile"
    output_field = FloatField()
    template = "%(function)s(%(percentile)s) WITHIN GROUP (ORDER BY %(expressions)s)"

    def __init__(self, expression, percentile: float, **extra):
        super().__init__(expression, percentile=float(percentile), **extra)


def ai_usage(days: int = 7) -> dict:
    days = max(1, min(days, 90))
    calls = AICallLog.objects.filter(created_at__gte=timezone.now() - timedelta(days=days))
    error = AICallLog.Status.ERROR
    ok = AICallLog.Status.OK
    aggregates = dict(
        calls=Count("id"),
        errors=Count("id", filter=Q(status=error)),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        cost=Sum("estimated_cost_usd"),
        average_latency=Avg("latency_ms"),
    )

    def shape(row):
        return {
            "calls": row["calls"],
            "errors": row["errors"],
            "input_tokens": row["input_tokens"] or 0,
            "output_tokens": row["output_tokens"] or 0,
            "estimated_cost_usd": round(float(row["cost"] or 0), 6),
            "average_latency_ms": optional_round(row["average_latency"], 2),
        }

    totals_row = calls.order_by().aggregate(**aggregates)
    totals = shape(totals_row)
    totals["error_rate"] = round(totals["errors"] / totals["calls"], 4) if totals["calls"] else 0.0
    totals.pop("average_latency_ms")

    # Failed calls return fast or time out, so they would distort the latency picture.
    latency = calls.filter(status=ok).order_by().aggregate(
        p50=Percentile("latency_ms", 0.5), p95=Percentile("latency_ms", 0.95), average=Avg("latency_ms")
    )

    def grouped(field):
        rows = calls.order_by().values(field).annotate(**aggregates).order_by("-calls", field)
        return [{field: row[field], **shape(row)} for row in rows]

    row_fields = ("id", "created_at", "feature", "model", "status", "error_type", "latency_ms",
                  "retries", "input_tokens", "output_tokens", "trace_id")
    named = dict(user_email=F("user__email"), project_name=F("project__name"))

    return {
        "days": days,
        "totals": totals,
        "latency": {"p50_ms": optional_round(latency["p50"], 2), "p95_ms": optional_round(latency["p95"], 2),
                    "average_ms": optional_round(latency["average"], 2)},
        "by_feature": grouped("feature"),
        "by_model": grouped("model"),
        "slowest": list(calls.order_by("-latency_ms").values(*row_fields, **named)[:SLOWEST_CALLS]),
        "recent_failures": list(
            calls.filter(status=error).order_by("-created_at").values(*row_fields, **named)[:RECENT_FAILURES]
        ),
    }


def eval_runs(limit: int = 20):
    return EvalRun.objects.order_by("-created_at")[:limit]


def jobs(*, status=None, type=None):
    queryset = Job.objects.order_by("-created_at")
    if status:
        queryset = queryset.filter(status=status)
    if type:
        queryset = queryset.filter(type=type)
    return queryset


def jobs_summary() -> dict:
    counted = dict(Job.objects.order_by().values("status").annotate(n=Count("id")).values_list("status", "n"))
    by_type = list(Job.objects.order_by().values("type").annotate(count=Count("id")).order_by("-count", "type"))
    return {
        "by_status": {status: counted.get(status, 0) for status in Job.Status.values},
        "by_type": by_type,
    }


@transaction.atomic
def retry_failed_job(job_id) -> Job:
    """Put a failed job back on the queue.

    Handlers are idempotent (spec section 9), so running one again is safe.
    The row lock stops two admins from retrying the same job twice.
    """
    job = get_object_or_404(Job.objects.select_for_update(), pk=job_id)
    if job.status != Job.Status.FAILED:
        raise ServiceError("Only failed jobs can be retried.", status=409, code="job_not_failed")
    job.status = Job.Status.QUEUED
    job.attempts = 0
    job.run_after = timezone.now()
    job.locked_at = None
    job.finished_at = None
    job.save(update_fields=["status", "attempts", "run_after", "locked_at", "finished_at", "updated_at"])
    return job


def _check(key, label, status, value, detail=""):
    return {"key": key, "label": label, "status": status, "value": str(value), "detail": detail}


def _database_checks() -> list[dict]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = cursor.fetchone()
    except Exception as exc:                       # the health endpoint must answer, not crash
        return [
            _check("database", "Database", "red", "unreachable", type(exc).__name__),
            _check("pgvector", "pgvector extension", "red", "unknown", "database unreachable"),
        ]
    vector = (
        _check("pgvector", "pgvector extension", "green", row[0])
        if row
        else _check("pgvector", "pgvector extension", "red", "missing", "run CREATE EXTENSION vector")
    )
    return [_check("database", "Database", "green", "reachable"), vector]


def _job_checks(now) -> list[dict]:
    stuck_after = timedelta(seconds=settings.JOB_STUCK_AFTER_SECONDS)
    row = Job.objects.order_by().aggregate(
        queued=Count("id", filter=Q(status=Job.Status.QUEUED)),
        oldest_due=Min("run_after", filter=Q(status=Job.Status.QUEUED, run_after__lte=now)),
        stuck=Count("id", filter=Q(status=Job.Status.RUNNING, locked_at__lt=now - stuck_after)),
        failed=Count("id", filter=Q(status=Job.Status.FAILED, updated_at__gte=now - timedelta(hours=24))),
    )
    waiting = int((now - row["oldest_due"]).total_seconds()) if row["oldest_due"] else 0
    backlog = "red" if waiting > BACKLOG_RED_SECONDS else "amber" if waiting > BACKLOG_AMBER_SECONDS else "green"
    failed = "red" if row["failed"] >= FAILED_JOBS_RED else "amber" if row["failed"] else "green"
    return [
        _check("queue_backlog", "Job queue", backlog, f"{row['queued']} queued",
               f"oldest due job has waited {waiting}s; is run_worker running?" if waiting else ""),
        _check("stuck_jobs", "Stuck jobs", "amber" if row["stuck"] else "green", row["stuck"],
               f"running for more than {stuck_after}; the worker re-queues them" if row["stuck"] else ""),
        _check("failed_jobs_24h", "Failed jobs (24 h)", failed, row["failed"]),
    ]


def _ai_checks(now) -> list[dict]:
    row = AICallLog.objects.order_by().aggregate(
        calls=Count("id", filter=Q(created_at__gte=now - timedelta(hours=1))),
        errors=Count("id", filter=Q(created_at__gte=now - timedelta(hours=1), status=AICallLog.Status.ERROR)),
        last_ok=Max("created_at", filter=Q(status=AICallLog.Status.OK)),
    )
    rate = row["errors"] / row["calls"] if row["calls"] else 0.0
    if row["calls"] < AI_ERROR_MIN_CALLS:
        # Too few calls for a rate to mean much, but any failure is still worth a look.
        status = "amber" if row["errors"] else "green"
    else:
        status = "red" if rate > AI_ERROR_RED else "amber" if rate > AI_ERROR_AMBER else "green"
    return [
        _check("ai_error_rate_1h", "AI error rate (1 h)", status, f"{rate:.0%}",
               f"{row['errors']} of {row['calls']} calls failed"),
        _check("last_ai_success", "Last successful AI call", "green",
               row["last_ok"].isoformat() if row["last_ok"] else "never"),
    ]


def system_health() -> dict:
    now = timezone.now()
    checks = _database_checks()
    if checks[0]["status"] == "green":
        checks += _job_checks(now) + _ai_checks(now)
    worst = max(checks, key=lambda check: SEVERITY[check["status"]])["status"]
    return {"status": worst, "checked_at": now, "checks": checks}
