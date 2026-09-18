import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from ai.models import EvalRun
from events.models import Job
from insights.tests.factories import make_ai_call

pytestmark = pytest.mark.django_db


def make_job(*, status="queued", type="process_material", attempts=0, last_error="",
             locked_minutes_ago=None, created_minutes_ago=0):
    job = Job.objects.create(type=type, payload={"user_id": "u", "project_id": "p"},
                             status=status, attempts=attempts, last_error=last_error)
    updates = {}
    if locked_minutes_ago is not None:
        updates["locked_at"] = timezone.now() - timedelta(minutes=locked_minutes_ago)
    if created_minutes_ago:
        moved = timezone.now() - timedelta(minutes=created_minutes_ago)
        updates.update(created_at=moved, run_after=moved)
    if updates:
        Job.objects.filter(pk=job.pk).update(**updates)
        job.refresh_from_db()
    return job


@pytest.mark.parametrize("path", ["/api/admin/ai-usage", "/api/admin/evals", "/api/admin/jobs",
                                  "/api/admin/jobs/summary", "/api/admin/health"])
def test_ops_endpoints_need_staff(api, user, path):
    assert api(user).get(path).status_code == 401


def test_ai_usage_totals_groups_and_percentiles(api, admin_user, user, project):
    for latency in range(100, 1001, 100):                       # 100 … 1000
        make_ai_call(user, project=project, feature="tutor", model="m-strong", latency_ms=latency)
    make_ai_call(user, project=project, feature="grading", model="m-fast", latency_ms=50,
                 status="error", error_type="AIRateLimitError")

    body = api(admin_user).get("/api/admin/ai-usage").json()

    assert body["days"] == 7
    assert body["totals"]["calls"] == 11
    assert body["totals"]["errors"] == 1
    assert body["totals"]["error_rate"] == pytest.approx(1 / 11, abs=1e-4)
    # Percentiles are over successful calls only: 100 … 1000.
    assert body["latency"]["p50_ms"] == pytest.approx(550)
    assert body["latency"]["p95_ms"] == pytest.approx(955)
    assert {row["feature"]: row["calls"] for row in body["by_feature"]} == {"tutor": 10, "grading": 1}
    assert {row["model"]: row["calls"] for row in body["by_model"]} == {"m-strong": 10, "m-fast": 1}
    assert body["slowest"][0]["latency_ms"] == 1000
    assert body["slowest"][0]["user_email"] == user.email
    assert [row["error_type"] for row in body["recent_failures"]] == ["AIRateLimitError"]


def test_ai_usage_respects_the_window(api, admin_user, user):
    make_ai_call(user)
    make_ai_call(user, minutes_ago=60 * 24 * 3)

    client = api(admin_user)

    assert client.get("/api/admin/ai-usage", days=1).json()["totals"]["calls"] == 1
    assert client.get("/api/admin/ai-usage", days=7).json()["totals"]["calls"] == 2


def test_ai_usage_with_no_calls(api, admin_user):
    body = api(admin_user).get("/api/admin/ai-usage").json()
    assert body["totals"]["calls"] == 0
    assert body["totals"]["error_rate"] == 0
    assert body["latency"] == {"p50_ms": None, "p95_ms": None, "average_ms": None}


def test_evals_lists_latest_runs_first(api, admin_user):
    EvalRun.objects.create(suite="tutor", git_sha="aaa111", metrics={"refusal_accuracy": 0.9},
                           case_results=[{"id": "q1", "passed": True}], passed=True)
    EvalRun.objects.create(suite="retrieval", git_sha="bbb222", metrics={"recall_at_6": 0.5},
                           case_results=[{"id": "r1", "passed": False}], passed=False)

    items = api(admin_user).get("/api/admin/evals").json()

    assert [run["suite"] for run in items] == ["retrieval", "tutor"]
    assert items[0]["passed"] is False
    assert items[0]["metrics"] == {"recall_at_6": 0.5}
    assert items[0]["case_count"] == 1


def test_jobs_list_filters_and_summary(api, admin_user):
    make_job(status="queued")
    make_job(status="failed", last_error="boom", attempts=4)
    make_job(status="succeeded", type="update_mastery")
    client = api(admin_user)

    assert client.get("/api/admin/jobs").json()["count"] == 3
    failed = client.get("/api/admin/jobs", status="failed").json()
    assert failed["count"] == 1
    assert failed["items"][0]["last_error"] == "boom"
    assert client.get("/api/admin/jobs", type="update_mastery").json()["count"] == 1

    summary = client.get("/api/admin/jobs/summary").json()
    assert summary["by_status"] == {"queued": 1, "running": 0, "succeeded": 1, "failed": 1}
    assert {row["type"]: row["count"] for row in summary["by_type"]} == {
        "process_material": 2, "update_mastery": 1}


def test_retry_resets_a_failed_job(api, admin_user):
    job = make_job(status="failed", attempts=4, last_error="boom", locked_minutes_ago=30)

    response = api(admin_user).post(f"/api/admin/jobs/{job.id}/retry")

    assert response.status_code == 200
    job.refresh_from_db()
    assert job.status == "queued"
    assert job.attempts == 0
    assert job.locked_at is None
    assert job.run_after <= timezone.now()
    assert job.last_error == "boom"          # kept as history until the next failure


@pytest.mark.parametrize("status", ["queued", "running", "succeeded"])
def test_retry_refuses_jobs_that_did_not_fail(api, admin_user, status):
    job = make_job(status=status)

    response = api(admin_user).post(f"/api/admin/jobs/{job.id}/retry")

    assert response.status_code == 409
    assert response.json()["code"] == "job_not_failed"
    job.refresh_from_db()
    assert job.status == status


def test_retry_unknown_job_is_404_and_needs_staff(api, admin_user, user):
    assert api(admin_user).post(f"/api/admin/jobs/{uuid.uuid4()}/retry").status_code == 404
    job = make_job(status="failed")
    assert api(user).post(f"/api/admin/jobs/{job.id}/retry").status_code == 401


def checks(body):
    return {check["key"]: check for check in body["checks"]}


def test_health_is_green_on_a_quiet_system(api, admin_user):
    body = api(admin_user).get("/api/admin/health").json()

    assert body["status"] == "green"
    assert checks(body)["database"]["status"] == "green"
    assert checks(body)["pgvector"]["status"] == "green"
    assert set(checks(body)) == {"database", "pgvector", "queue_backlog", "stuck_jobs",
                                 "failed_jobs_24h", "ai_error_rate_1h", "last_ai_success"}


def test_health_flags_queue_and_ai_problems(api, admin_user, user):
    make_job(status="queued", created_minutes_ago=10)             # waiting > 5 min → amber
    make_job(status="running", locked_minutes_ago=30)             # stuck → amber
    make_job(status="failed")
    for _ in range(4):
        make_ai_call(user, status="error", error_type="AIProviderError")
    make_ai_call(user)                                            # 4 of 5 failed → red

    body = api(admin_user).get("/api/admin/health").json()
    found = checks(body)

    assert found["queue_backlog"]["status"] == "amber"
    assert found["stuck_jobs"]["status"] == "amber"
    assert found["failed_jobs_24h"]["status"] == "amber"
    assert found["ai_error_rate_1h"]["status"] == "red"
    assert body["status"] == "red"                                # the worst check wins


def test_a_failure_among_too_few_calls_is_a_warning_not_ok(api, admin_user, user):
    make_ai_call(user, status="error", error_type="AIProviderError")

    found = checks(api(admin_user).get("/api/admin/health").json())

    assert found["ai_error_rate_1h"]["status"] == "amber"


def test_ops_query_counts_stay_flat(api, admin_user, user, django_assert_max_num_queries):
    for _ in range(10):
        make_ai_call(user)
        make_job(status="failed")
    client = api(admin_user)

    with django_assert_max_num_queries(8):
        assert client.get("/api/admin/ai-usage").status_code == 200
    with django_assert_max_num_queries(4):
        assert client.get("/api/admin/jobs").status_code == 200
    with django_assert_max_num_queries(6):
        assert client.get("/api/admin/health").status_code == 200
