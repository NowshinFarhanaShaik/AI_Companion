# Phase 6 — Analytics and Admin Dashboard (Tasks 29–33)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the learner project and global analytics, and give staff a platform-level dashboard for users, activity, AI usage, evals, background jobs and system health.

**Spec:** `docs/superpowers/specs/2026-09-17-ai-study-companion-design.md` (sections 4, 10, 11, 12, 13, 15)

**Contract:** `00-overview.md`

**Depends on:** Phases 1–5 (all models exist; `learning.growth.concept_trends`, `StaffJWTAuth`, `ServiceError`, the `api`/`admin_user` fixtures, `make_concept`, the UI primitives and Recharts from Task 28).

## Execution order and cut guide

This phase is first on the cut list. Task numbers are fixed, but execute in this order so that the most valuable pieces land first:

1. **Task 29** — analytics API (PRD must-have: project and global analytics)
2. **Task 32** — analytics UI
3. **Task 30** — admin core API (overview, users, user journey, activity)
4. **Task 33 Part A** — admin layout and the Overview, Users, User detail and Activity pages
5. **Task 31** — admin operations API (AI usage, evals, jobs, health)
6. **Task 33 Part B** — AI usage, Evals, Jobs and Health pages

**What can be dropped, in order:** Task 33 Part B, then Task 31, then the global analytics page of Task 32 (keep the project tab). If Task 31 is dropped, register `Job`, `EvalRun` and `AICallLog` in Django Admin as the fallback so staff can still inspect them:

```python
# backend/insights/admin.py  (fallback only)
from django.contrib import admin
from ai.models import AICallLog, EvalRun
from events.models import Job

admin.site.register([Job, EvalRun, AICallLog])
```

## Rules for this phase

- `insights` has **no models**. All reads live in `insights/queries.py` (learner analytics) and `insights/admin_queries.py` (platform-wide). Views stay thin.
- Learner queries start from a scoped queryset: `Project.objects.for_user(user)`, `QuizSession.objects.for_user(user)` and so on. `LearningEvent` and `AICallLog` have a direct `user` foreign key and a nullable `project`, so they are scoped with `filter(user=user)`.
- Admin queries are deliberately unscoped. They are reachable only through `Router(auth=StaffJWTAuth())`.
- Grouped queries always call `.order_by()` before `.values(...)`. A model `Meta.ordering` would otherwise be added to `GROUP BY` and split the groups.
- Never aggregate across two multi-valued joins in one `annotate` (it multiplies rows and corrupts `Sum`/`Avg`). Use one grouped query per relation, or a `Subquery`.
- Tests pass full paths that start with `/api/`.

---

### Task 29: Analytics API (project and global)

**Files:**
- Create: `backend/insights/` via `startapp` (then delete `insights/tests.py`, `insights/models.py` stays empty)
- Create: `backend/insights/queries.py`, `backend/insights/schemas.py`, `backend/insights/api.py`
- Create: `backend/insights/tests/__init__.py`, `backend/insights/tests/conftest.py`, `backend/insights/tests/factories.py`, `backend/insights/tests/test_analytics.py`
- Modify: `backend/config/settings.py` (`LOCAL_APPS`), `backend/config/api.py` (mount router)

**Interfaces:**
- Consumes: `get_owned_or_404(model, user, **lookup)`, `OwnedQuerySet.for_user`, `learning.growth.concept_trends(project, *, days=14) -> list[Trend]`, models `LearningEvent`, `AICallLog`, `QuizSession`, `Question`, `Attempt`, `ConceptMastery`, `Material`, `Project`, `Space`; fixtures `user`, `other_user`, `space`, `project`, `other_project`, `api`; helper `make_concept`.
- Produces:
  - `insights.queries.activity_summary(events, *, days=14) -> dict`
  - `insights.queries.quiz_summary(sessions, attempts) -> dict`
  - `insights.queries.mastery_summary(masteries) -> dict`
  - `insights.queries.ai_summary(calls) -> dict`
  - `insights.queries.project_breakdown(projects) -> list[dict]`
  - `insights.queries.project_analytics(user, project) -> dict`
  - `insights.queries.global_analytics(user) -> dict`
  - `GET /api/projects/{project_id}/analytics` → `ProjectAnalyticsOut`
  - `GET /api/analytics/global` → `GlobalAnalyticsOut`
  - Test factories `make_event`, `make_ai_call`, `make_session` in `insights/tests/factories.py` (reused by Tasks 30 and 31)

- [ ] **Step 1: Register the app**

```bash
cd backend && source .venv/bin/activate
python manage.py startapp insights
rm insights/tests.py
mkdir insights/tests && touch insights/tests/__init__.py
```

In `config/settings.py` add `"insights"` to `LOCAL_APPS`.

- [ ] **Step 2: Write the test factories**

`backend/insights/tests/factories.py`:

```python
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from ai.models import AICallLog
from assessment.models import Attempt, Question, QuizSession
from events.models import LearningEvent


def make_event(user, *, project=None, space=None, type="tutor.message_sent", days_ago=0, payload=None):
    event = LearningEvent.objects.create(
        user=user, project=project, space=space, type=type, payload=payload or {}
    )
    if days_ago:
        # created_at is auto_now_add, so it can only be moved with update().
        LearningEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        event.refresh_from_db()
    return event


def make_ai_call(user, *, project=None, feature="tutor", model="fake-fast", status="ok",
                 latency_ms=200, input_tokens=100, output_tokens=50, cost="0.001",
                 error_type="", minutes_ago=0):
    log = AICallLog.objects.create(
        user=user, project=project, feature=feature, provider="fake", model=model,
        latency_ms=latency_ms, input_tokens=input_tokens, output_tokens=output_tokens,
        estimated_cost_usd=Decimal(cost), status=status, error_type=error_type,
        retries=0, retrieved_chunk_ids=[], trace_id="",
    )
    if minutes_ago:
        AICallLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        log.refresh_from_db()
    return log


def make_session(project, concept, scores, *, completed=True, days_ago=0):
    """A quiz session with one answered MCQ per score in `scores`."""
    when = timezone.now() - timedelta(days=days_ago)
    session = QuizSession.objects.create(
        project=project,
        status=QuizSession.Status.COMPLETED if completed else QuizSession.Status.ACTIVE,
        target_question_count=max(len(scores), 1),
        completed_at=when if completed else None,
    )
    for score in scores:
        question = Question.objects.create(
            project=project, session=session, concept=concept, type=Question.Type.MCQ,
            difficulty=1, body="Which one?", options=["a", "b", "c", "d"], correct_option=0,
            rubric={},
        )
        Attempt.objects.create(
            question=question, project=project, selected_option=0, answer_text="",
            score=score, feedback={}, evaluated_at=when,
        )
    return session
```

`backend/insights/tests/conftest.py`:

```python
import pytest

from events.models import LearningEvent


@pytest.fixture(autouse=True)
def clean_events(db, project, other_project):
    """The shared fixtures may emit events (space.created, project.created).

    Analytics tests assert exact counts, so start every test from zero events.
    """
    LearningEvent.objects.all().delete()
```

- [ ] **Step 3: Write the failing tests**

`backend/insights/tests/test_analytics.py`:

```python
import pytest
from django.utils import timezone

from common.testing import make_concept
from insights.tests.factories import make_ai_call, make_event, make_session
from learning.growth import Trend
from workspace.models import Project, Space

pytestmark = pytest.mark.django_db


def url(project):
    return f"/api/projects/{project.id}/analytics"


def test_project_activity_counts_only_the_window_and_the_owner(api, user, other_user, project, other_project):
    for _ in range(3):
        make_event(user, project=project, type="tutor.message_sent")
    make_event(user, project=project, type="quiz.completed", days_ago=2)
    make_event(user, project=project, type="quiz.completed", days_ago=20)   # outside 14 days
    for _ in range(5):
        make_event(other_user, project=other_project)

    body = api(user).get(url(project)).json()

    activity = body["activity"]
    assert activity["total"] == 4
    assert len(activity["per_day"]) == 14
    today = timezone.localdate().isoformat()
    assert {d["day"]: d["count"] for d in activity["per_day"]}[today] == 3
    assert activity["by_type"][0] == {"type": "tutor.message_sent", "count": 3}


def test_project_quiz_performance(api, user, project):
    concept = make_concept(project, "Photosynthesis")
    make_session(project, concept, [1.0, 0.5], days_ago=1)
    make_session(project, concept, [0.0])
    make_session(project, concept, [], completed=False)

    quiz = api(user).get(url(project)).json()["quiz"]

    assert quiz["sessions_started"] == 3
    assert quiz["sessions_completed"] == 2
    assert quiz["questions_answered"] == 3
    assert quiz["average_score"] == pytest.approx(0.5)
    assert [s["average_score"] for s in quiz["per_session"]] == [pytest.approx(0.75), pytest.approx(0.0)]
    assert [s["answered"] for s in quiz["per_session"]] == [2, 1]


def test_project_mastery_bands(api, user, project):
    make_concept(project, "A", mastery=0.2)
    make_concept(project, "B", mastery=0.5)
    make_concept(project, "C", mastery=0.9)

    mastery = api(user).get(url(project)).json()["mastery"]

    assert (mastery["low"], mastery["medium"], mastery["high"]) == (1, 1, 1)
    assert mastery["concepts"] == 3
    assert mastery["average"] == pytest.approx(0.5333, abs=1e-3)


def test_project_trends_reuse_growth_module(api, user, project, monkeypatch):
    a = make_concept(project, "A", mastery=0.8)
    b = make_concept(project, "B", mastery=0.3)
    fake = [
        Trend(concept=a, score=0.8, delta=0.2, label="improving", evidence_count=4),
        Trend(concept=b, score=0.3, delta=-0.1, label="needs_attention", evidence_count=3),
    ]
    monkeypatch.setattr("insights.queries.concept_trends", lambda project, days=14: fake)

    body = api(user).get(url(project)).json()

    assert [t["name"] for t in body["trends"]] == ["A", "B"]
    assert body["trends"][0]["label"] == "improving"
    assert body["trend_counts"] == {"improving": 1, "needs_attention": 1}


def test_project_ai_activity_is_isolated(api, user, other_user, project, other_project):
    make_ai_call(user, project=project, feature="tutor")
    make_ai_call(user, project=project, feature="tutor")
    make_ai_call(user, project=project, feature="grading", status="error", error_type="AITimeoutError")
    for _ in range(4):
        make_ai_call(other_user, project=other_project)

    ai = api(user).get(url(project)).json()["ai"]

    assert ai["calls"] == 3
    assert ai["errors"] == 1
    assert ai["input_tokens"] == 300
    assert ai["estimated_cost_usd"] == pytest.approx(0.003)
    tutor = next(row for row in ai["by_feature"] if row["feature"] == "tutor")
    assert tutor["calls"] == 2


def test_other_users_project_analytics_is_404(api, user, other_project):
    assert api(user).get(url(other_project)).status_code == 404


def test_global_analytics_aggregates_only_my_projects(api, user, other_user, space, project, other_project):
    space2 = Space.objects.create(owner=user, name="Second space", description="")
    project2 = Project.objects.create(space=space2, owner=user, name="Second project",
                                      description="", learning_goal="")
    make_event(user, project=project)
    make_event(user, project=project2)
    make_event(user, project=project2)
    make_event(other_user, project=other_project)
    make_concept(project, "A", mastery=0.2)
    make_concept(project2, "B", mastery=0.8)
    make_ai_call(user, project=project2)
    make_ai_call(other_user, project=other_project)

    body = api(user).get("/api/analytics/global").json()

    assert body["activity"]["total"] == 3
    assert body["ai"]["calls"] == 1
    assert body["mastery"]["concepts"] == 2
    rows = {row["name"]: row for row in body["projects"]}
    assert set(rows) == {project.name, "Second project"}
    assert rows["Second project"]["events"] == 2
    assert rows["Second project"]["average_mastery"] == pytest.approx(0.8)
    spaces = {row["name"]: row for row in body["spaces"]}
    assert set(spaces) == {space.name, "Second space"}
    assert spaces["Second space"]["projects"] == 1
    assert spaces["Second space"]["events"] == 2


def test_analytics_query_counts_stay_flat(api, user, project, django_assert_max_num_queries):
    concept = make_concept(project, "A")
    make_concept(project, "B")
    make_concept(project, "C")
    for _ in range(4):
        make_session(project, concept, [1.0, 0.0])
    for _ in range(10):
        make_event(user, project=project)
        make_ai_call(user, project=project)
    client = api(user)

    # If this fails because of concept_trends, that function is querying per concept.
    # Fix it there (one snapshots query, grouped in Python). Do not raise the bound.
    with django_assert_max_num_queries(18):
        assert client.get(url(project)).status_code == 200
    with django_assert_max_num_queries(18):
        assert client.get("/api/analytics/global").status_code == 200
```

- [ ] **Step 4: Run the tests and see them fail**

Run: `pytest insights/tests/test_analytics.py -v`
Expected: every test FAILS with a 404 response (`KeyError: 'activity'` or `assert 404 == 200`), because the routes do not exist yet.

- [ ] **Step 5: Write the schemas**

`backend/insights/schemas.py`:

```python
from datetime import date, datetime
from uuid import UUID

from ninja import Schema


class DayCount(Schema):
    day: date
    count: int


class TypeCount(Schema):
    type: str
    count: int


class ActivityOut(Schema):
    total: int
    per_day: list[DayCount]
    by_type: list[TypeCount]


class SessionScore(Schema):
    session_id: UUID
    project_id: UUID
    completed_at: datetime | None
    average_score: float | None
    answered: int


class QuizOut(Schema):
    sessions_started: int
    sessions_completed: int
    questions_answered: int
    average_score: float | None
    per_session: list[SessionScore]


class MasteryOut(Schema):
    concepts: int
    average: float | None
    low: int
    medium: int
    high: int


class TrendOut(Schema):
    concept_id: UUID
    name: str
    score: float
    delta: float
    label: str
    evidence_count: int


class AIFeatureRow(Schema):
    feature: str
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    errors: int


class AIActivityOut(Schema):
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    errors: int
    by_feature: list[AIFeatureRow]


class ProjectAnalyticsOut(Schema):
    project_id: UUID
    activity: ActivityOut
    quiz: QuizOut
    mastery: MasteryOut
    trends: list[TrendOut]
    trend_counts: dict[str, int]
    ai: AIActivityOut


class ProjectBreakdownRow(Schema):
    project_id: UUID
    name: str
    space_id: UUID
    space_name: str
    last_activity_at: datetime | None
    events: int
    materials: int
    concepts: int
    average_mastery: float | None
    questions_answered: int
    average_score: float | None


class SpaceBreakdownRow(Schema):
    space_id: UUID
    name: str
    projects: int
    events: int
    average_mastery: float | None


class GlobalAnalyticsOut(Schema):
    activity: ActivityOut
    quiz: QuizOut
    mastery: MasteryOut
    ai: AIActivityOut
    spaces: list[SpaceBreakdownRow]
    projects: list[ProjectBreakdownRow]
```

- [ ] **Step 6: Write the queries**

`backend/insights/queries.py`:

```python
"""Learner-facing analytics. Every function receives querysets that are already scoped.

Rules: call .order_by() before a grouped .values(); never aggregate over two
multi-valued joins in one annotate().
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from ai.models import AICallLog
from assessment.models import Attempt, QuizSession
from events.models import LearningEvent
from learning.growth import concept_trends
from learning.models import ConceptMastery
from materials.models import Material
from workspace.models import Project, Space

ACTIVITY_WINDOW_DAYS = 14
LOW_BAND = 0.4      # below: low
HIGH_BAND = 0.7     # above: high
MAX_SESSIONS_IN_CHART = 30


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _opt(value):
    return round(float(value), 4) if value is not None else None


def activity_summary(events, *, days: int = ACTIVITY_WINDOW_DAYS) -> dict:
    start_day = timezone.localdate() - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(start_day, time.min))
    windowed = events.filter(created_at__gte=start)
    counts = dict(
        windowed.order_by()
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count")
    )
    per_day = [
        {"day": start_day + timedelta(days=i), "count": counts.get(start_day + timedelta(days=i), 0)}
        for i in range(days)
    ]
    by_type = list(
        windowed.order_by().values("type").annotate(count=Count("id")).order_by("-count", "type")
    )
    return {"total": sum(counts.values()), "per_day": per_day, "by_type": by_type}


def quiz_summary(sessions, attempts) -> dict:
    completed = QuizSession.Status.COMPLETED
    totals = sessions.order_by().aggregate(
        started=Count("id"), completed=Count("id", filter=Q(status=completed))
    )
    answers = attempts.order_by().aggregate(answered=Count("id"), average=Avg("score"))
    recent = list(
        sessions.filter(status=completed)
        .order_by()
        .annotate(average_score=Avg("questions__attempt__score"), answered=Count("questions__attempt"))
        .order_by("-completed_at")
        .values("id", "project_id", "completed_at", "average_score", "answered")[:MAX_SESSIONS_IN_CHART]
    )
    per_session = [
        {
            "session_id": row["id"],
            "project_id": row["project_id"],
            "completed_at": row["completed_at"],
            "average_score": _opt(row["average_score"]),
            "answered": row["answered"],
        }
        for row in reversed(recent)      # oldest first, for the chart
    ]
    return {
        "sessions_started": totals["started"],
        "sessions_completed": totals["completed"],
        "questions_answered": answers["answered"],
        "average_score": _opt(answers["average"]),
        "per_session": per_session,
    }


def mastery_summary(masteries) -> dict:
    row = masteries.order_by().aggregate(
        concepts=Count("id"),
        average=Avg("score"),
        low=Count("id", filter=Q(score__lt=LOW_BAND)),
        medium=Count("id", filter=Q(score__gte=LOW_BAND, score__lte=HIGH_BAND)),
        high=Count("id", filter=Q(score__gt=HIGH_BAND)),
    )
    row["average"] = _opt(row["average"])
    return row


def ai_summary(calls) -> dict:
    error = AICallLog.Status.ERROR
    aggregates = dict(
        calls=Count("id"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        cost=Sum("estimated_cost_usd"),
        errors=Count("id", filter=Q(status=error)),
    )

    def shape(row):
        return {
            "calls": row["calls"],
            "input_tokens": row["input_tokens"] or 0,
            "output_tokens": row["output_tokens"] or 0,
            "estimated_cost_usd": round(_num(row["cost"]), 6),
            "errors": row["errors"],
        }

    totals = shape(calls.order_by().aggregate(**aggregates))
    by_feature = [
        {"feature": row["feature"], **shape(row)}
        for row in calls.order_by().values("feature").annotate(**aggregates).order_by("-calls", "feature")
    ]
    return {**totals, "by_feature": by_feature}


def project_breakdown(projects) -> list[dict]:
    """One row per project. `projects` must already be scoped by the caller.

    The grouped queries filter on the ids of that scoped queryset, so they
    cannot reach a project the caller was not allowed to see.
    """
    rows = list(
        projects.order_by(F("last_activity_at").desc(nulls_last=True), "name")
        .values("id", "name", "space_id", "space__name", "last_activity_at")
    )
    ids = [row["id"] for row in rows]

    def grouped(model, **aggregates):
        query = model.objects.filter(project_id__in=ids).order_by().values("project_id").annotate(**aggregates)
        return {row["project_id"]: row for row in query}

    events = grouped(LearningEvent, n=Count("id"))
    materials = grouped(Material, n=Count("id"))
    mastery = grouped(ConceptMastery, n=Count("id"), avg=Avg("score"))
    answers = grouped(Attempt, n=Count("id"), avg=Avg("score"))

    return [
        {
            "project_id": row["id"],
            "name": row["name"],
            "space_id": row["space_id"],
            "space_name": row["space__name"],
            "last_activity_at": row["last_activity_at"],
            "events": events.get(row["id"], {}).get("n", 0),
            "materials": materials.get(row["id"], {}).get("n", 0),
            "concepts": mastery.get(row["id"], {}).get("n", 0),
            "average_mastery": _opt(mastery.get(row["id"], {}).get("avg")),
            "questions_answered": answers.get(row["id"], {}).get("n", 0),
            "average_score": _opt(answers.get(row["id"], {}).get("avg")),
        }
        for row in rows
    ]


def space_breakdown(spaces, project_rows: list[dict]) -> list[dict]:
    by_space = defaultdict(list)
    for row in project_rows:
        by_space[row["space_id"]].append(row)
    result = []
    for space in spaces.order_by("name").values("id", "name"):
        rows = by_space.get(space["id"], [])
        concepts = sum(r["concepts"] for r in rows)
        weighted = sum((r["average_mastery"] or 0) * r["concepts"] for r in rows)
        result.append(
            {
                "space_id": space["id"],
                "name": space["name"],
                "projects": len(rows),
                "events": sum(r["events"] for r in rows),
                "average_mastery": round(weighted / concepts, 4) if concepts else None,
            }
        )
    return result


def project_analytics(user, project) -> dict:
    """`project` must have been loaded with get_owned_or_404(Project, user, ...)."""
    trends = [
        {
            "concept_id": t.concept.id,
            "name": t.concept.name,
            "score": t.score,
            "delta": t.delta,
            "label": t.label,
            "evidence_count": t.evidence_count,
        }
        for t in concept_trends(project)
    ]
    return {
        "project_id": project.id,
        "activity": activity_summary(LearningEvent.objects.filter(user=user, project=project)),
        "quiz": quiz_summary(
            QuizSession.objects.for_user(user).filter(project=project),
            Attempt.objects.for_user(user).filter(project=project),
        ),
        "mastery": mastery_summary(ConceptMastery.objects.for_user(user).filter(project=project)),
        "trends": trends,
        "trend_counts": dict(Counter(t["label"] for t in trends)),
        "ai": ai_summary(AICallLog.objects.filter(user=user, project=project)),
    }


def global_analytics(user) -> dict:
    project_rows = project_breakdown(Project.objects.for_user(user))
    return {
        "activity": activity_summary(LearningEvent.objects.filter(user=user)),
        "quiz": quiz_summary(QuizSession.objects.for_user(user), Attempt.objects.for_user(user)),
        "mastery": mastery_summary(ConceptMastery.objects.for_user(user)),
        "ai": ai_summary(AICallLog.objects.filter(user=user)),
        "spaces": space_breakdown(Space.objects.for_user(user), project_rows),
        "projects": project_rows,
    }
```

- [ ] **Step 7: Write the API and mount it**

`backend/insights/api.py`:

```python
from uuid import UUID

from ninja import Router

from common.scoping import get_owned_or_404
from insights import queries
from insights.schemas import GlobalAnalyticsOut, ProjectAnalyticsOut
from workspace.models import Project

router = Router(tags=["analytics"])


@router.get("/projects/{uuid:project_id}/analytics", response=ProjectAnalyticsOut)
def project_analytics(request, project_id: UUID):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return queries.project_analytics(request.auth, project)


@router.get("/analytics/global", response=GlobalAnalyticsOut)
def global_analytics(request):
    return queries.global_analytics(request.auth)
```

In `backend/config/api.py` add next to the other routers:

```python
from insights.api import router as insights_router

api.add_router("", insights_router)
```

- [ ] **Step 8: Run the tests and see them pass**

Run: `pytest insights/tests/test_analytics.py -v`
Expected: 8 passed.

- [ ] **Step 9: Commit**

```bash
git add backend/insights backend/config/settings.py backend/config/api.py
git commit -m "feat: project and global analytics API"
```

---

### Task 30: Admin core API (overview, users, user journey, activity)

**Files:**
- Create: `backend/insights/admin_queries.py`, `backend/insights/admin_schemas.py`, `backend/insights/admin_api.py`
- Create: `backend/insights/tests/test_admin_core.py`
- Modify: `backend/config/api.py` (mount at `/admin`)

**Interfaces:**
- Consumes: `accounts.auth.StaffJWTAuth`, fixtures `admin_user`, `user`, `other_user`, `project`, `other_project`, `api`; factories from Task 29; `insights.queries.project_breakdown`, `ai_summary`, `activity_summary`.
- Produces:
  - `insights.admin_queries.overview() -> dict`
  - `insights.admin_queries.users(q: str = "") -> QuerySet[User]` (annotated with `project_count`, `last_activity`, `ai_calls`, `ai_cost`)
  - `insights.admin_queries.user_detail(user_id) -> dict` (raises `Http404`)
  - `insights.admin_queries.activity(*, user_id=None, space_id=None, project_id=None, type=None, date_from=None, date_to=None) -> QuerySet[LearningEvent]`
  - `insights.admin_api.router` — `Router(auth=StaffJWTAuth(), tags=["admin"])`, mounted at `/api/admin`
  - `GET /api/admin/overview`, `GET /api/admin/users?q=&limit=&offset=`, `GET /api/admin/users/{user_id}`, `GET /api/admin/activity?...`

- [ ] **Step 1: Write the failing tests**

`backend/insights/tests/test_admin_core.py`:

```python
import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from common.testing import make_concept
from insights.tests.factories import make_ai_call, make_event, make_session

pytestmark = pytest.mark.django_db

ADMIN_GETS = ["/api/admin/overview", "/api/admin/users", "/api/admin/activity"]


@pytest.mark.parametrize("path", ADMIN_GETS)
def test_non_staff_token_gets_401(api, user, path):
    assert api(user).get(path).status_code == 401


@pytest.mark.parametrize("path", ADMIN_GETS)
def test_anonymous_gets_401(path):
    assert Client().get(path).status_code == 401


def test_non_staff_cannot_read_a_user_journey(api, user, other_user):
    assert api(user).get(f"/api/admin/users/{other_user.id}").status_code == 401


def test_overview_counts_the_whole_platform(api, admin_user, user, other_user, project, other_project):
    make_event(user, project=project)
    make_event(user, project=project, days_ago=3)
    make_event(other_user, project=other_project, days_ago=10)    # outside 7 days
    concept = make_concept(project, "A")
    make_session(project, concept, [1.0])

    body = api(admin_user).get("/api/admin/overview").json()

    assert body["users"] == 3
    assert body["spaces"] == 2
    assert body["projects"] == 2
    assert body["quiz_sessions"] == 1
    assert body["questions_answered"] == 1
    assert body["active_users_7d"] == 1
    assert body["events"]["total"] == 3
    assert len(body["events"]["per_day"]) == 14


def test_users_list_has_per_user_numbers(api, admin_user, user, other_user, project, other_project):
    make_event(user, project=project)
    make_ai_call(user, project=project, cost="0.002")
    make_ai_call(user, project=project, cost="0.003")

    body = api(admin_user).get("/api/admin/users").json()

    assert body["count"] == 3
    rows = {row["email"]: row for row in body["items"]}
    assert rows[user.email]["project_count"] == 1
    assert rows[user.email]["ai_calls"] == 2
    assert rows[user.email]["ai_cost_usd"] == pytest.approx(0.005)
    assert rows[user.email]["last_activity"] is not None
    assert rows[other_user.email]["ai_calls"] == 0
    assert rows[other_user.email]["last_activity"] is None
    assert rows[admin_user.email]["is_staff"] is True


def test_users_list_search(api, admin_user, user, other_user):
    body = api(admin_user).get("/api/admin/users", q=other_user.email[:5]).json()
    assert other_user.email in [row["email"] for row in body["items"]]
    assert body["count"] < 3 or user.email[:5] == other_user.email[:5]


def test_user_detail_shows_the_learning_journey(api, admin_user, user, other_user, space, project, other_project):
    concept = make_concept(project, "A", mastery=0.6)
    make_session(project, concept, [1.0, 0.0])
    make_event(user, project=project, type="quiz.completed")
    make_event(other_user, project=other_project)
    make_ai_call(user, project=project, feature="tutor")

    body = api(admin_user).get(f"/api/admin/users/{user.id}").json()

    assert body["user"]["email"] == user.email
    assert [s["name"] for s in body["spaces"]] == [space.name]
    assert body["spaces"][0]["project_count"] == 1
    assert [p["name"] for p in body["projects"]] == [project.name]
    assert body["projects"][0]["average_mastery"] == pytest.approx(0.6)
    assert [e["type"] for e in body["recent_activity"]] == ["quiz.completed"]
    assert body["assessments"][0]["average_score"] == pytest.approx(0.5)
    assert body["assessments"][0]["project_name"] == project.name
    assert body["ai"]["calls"] == 1


def test_user_detail_unknown_id_is_404(api, admin_user):
    assert api(admin_user).get(f"/api/admin/users/{uuid.uuid4()}").status_code == 404


def test_activity_filters(api, admin_user, user, other_user, space, project, other_project):
    make_event(user, project=project, type="quiz.completed")
    make_event(user, project=project, type="tutor.message_sent", days_ago=5)
    make_event(user, space=space, type="space.created", days_ago=5)
    make_event(other_user, project=other_project, type="quiz.completed")
    client = api(admin_user)

    def types(**params):
        body = client.get("/api/admin/activity", **params).json()
        return body["count"], sorted(item["type"] for item in body["items"])

    assert types()[0] == 4
    assert types(user_id=str(user.id))[0] == 3
    assert types(project_id=str(project.id)) == (2, ["quiz.completed", "tutor.message_sent"])
    # The space filter matches events on the space and events on its projects.
    assert types(space_id=str(space.id))[0] == 3
    assert types(type="quiz.completed")[0] == 2
    today = timezone.localdate().isoformat()
    assert types(date_from=today)[0] == 2
    assert types(date_to=(timezone.localdate() - timedelta(days=1)).isoformat())[0] == 2


def test_activity_rows_name_the_user_project_and_space(api, admin_user, user, space, project):
    make_event(user, project=project, type="quiz.completed", payload={"score": 0.8})

    item = api(admin_user).get("/api/admin/activity").json()["items"][0]

    assert item["user_email"] == user.email
    assert item["project_name"] == project.name
    assert item["space_name"] == space.name
    assert item["payload"] == {"score": 0.8}


def test_admin_core_query_counts_stay_flat(api, admin_user, user, project, django_assert_max_num_queries):
    concept = make_concept(project, "A")
    for _ in range(5):
        make_session(project, concept, [1.0])
        make_event(user, project=project)
        make_ai_call(user, project=project)
    client = api(admin_user)

    with django_assert_max_num_queries(14):
        assert client.get("/api/admin/overview").status_code == 200
    with django_assert_max_num_queries(4):       # auth, count, page
        assert client.get("/api/admin/users").status_code == 200
    with django_assert_max_num_queries(4):
        assert client.get("/api/admin/activity").status_code == 200
    with django_assert_max_num_queries(16):
        assert client.get(f"/api/admin/users/{user.id}").status_code == 200
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `pytest insights/tests/test_admin_core.py -v`
Expected: FAIL. The 401 tests fail with `assert 404 == 401` and the rest with 404 responses, because `/api/admin/*` is not mounted.

- [ ] **Step 3: Write the admin schemas**

`backend/insights/admin_schemas.py`:

```python
from datetime import date, datetime
from typing import Any
from uuid import UUID

from ninja import Schema

from insights.schemas import ActivityOut, AIActivityOut, ProjectBreakdownRow


class MaterialStatusCount(Schema):
    status: str
    count: int


class OverviewOut(Schema):
    users: int
    spaces: int
    projects: int
    materials: int
    materials_by_status: list[MaterialStatusCount]
    quiz_sessions: int
    questions_answered: int
    active_users_7d: int
    events: ActivityOut


class AdminUserRow(Schema):
    id: UUID
    email: str
    name: str
    is_staff: bool
    is_active: bool
    project_count: int
    last_activity: datetime | None
    ai_calls: int
    ai_cost_usd: float

    @staticmethod
    def resolve_project_count(obj):
        return obj.project_count or 0

    @staticmethod
    def resolve_ai_calls(obj):
        return obj.ai_calls or 0

    @staticmethod
    def resolve_ai_cost_usd(obj):
        return round(float(obj.ai_cost or 0), 6)


class AdminUserSummary(Schema):
    id: UUID
    email: str
    name: str
    is_staff: bool
    is_active: bool
    joined_at: datetime | None


class AdminSpaceRow(Schema):
    id: UUID
    name: str
    project_count: int


class AdminEventRow(Schema):
    id: UUID
    created_at: datetime
    type: str
    project_id: UUID | None
    project_name: str | None
    payload: dict[str, Any]


class AdminAssessmentRow(Schema):
    id: UUID
    project_id: UUID
    project_name: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    average_score: float | None
    answered: int


class AdminUserDetailOut(Schema):
    user: AdminUserSummary
    spaces: list[AdminSpaceRow]
    projects: list[ProjectBreakdownRow]
    recent_activity: list[AdminEventRow]
    assessments: list[AdminAssessmentRow]
    ai: AIActivityOut


class ActivityFilters(Schema):
    user_id: UUID | None = None
    space_id: UUID | None = None
    project_id: UUID | None = None
    type: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class ActivityRowOut(Schema):
    id: UUID
    created_at: datetime
    type: str
    payload: dict[str, Any]
    user_id: UUID
    user_email: str
    project_id: UUID | None
    project_name: str | None
    space_id: UUID | None
    space_name: str | None

    @staticmethod
    def resolve_user_email(obj):
        return obj.user.email

    @staticmethod
    def resolve_project_name(obj):
        return obj.project.name if obj.project_id else None

    @staticmethod
    def resolve_space_id(obj):
        if obj.space_id:
            return obj.space_id
        return obj.project.space_id if obj.project_id else None

    @staticmethod
    def resolve_space_name(obj):
        if obj.space_id:
            return obj.space.name
        return obj.project.space.name if obj.project_id else None
```

- [ ] **Step 4: Write the admin queries**

`backend/insights/admin_queries.py`:

```python
"""Platform-wide reads for staff. Deliberately NOT scoped with for_user().

These functions must only be called from insights/admin_api.py, whose router
uses StaffJWTAuth.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DateTimeField, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.http import Http404
from django.utils import timezone

from ai.models import AICallLog
from assessment.models import Attempt, QuizSession
from events.models import LearningEvent
from insights.queries import _opt, activity_summary, ai_summary, project_breakdown
from materials.models import Material
from workspace.models import Project, Space

RECENT_EVENTS = 20
RECENT_ASSESSMENTS = 10


def overview() -> dict:
    User = get_user_model()
    week_ago = timezone.now() - timedelta(days=7)
    by_status = list(
        Material.objects.order_by().values("status").annotate(count=Count("id")).order_by("status")
    )
    return {
        "users": User.objects.count(),
        "spaces": Space.objects.count(),
        "projects": Project.objects.count(),
        "materials": sum(row["count"] for row in by_status),
        "materials_by_status": by_status,
        "quiz_sessions": QuizSession.objects.count(),
        "questions_answered": Attempt.objects.count(),
        "active_users_7d": LearningEvent.objects.filter(created_at__gte=week_ago)
        .order_by().values("user_id").distinct().count(),
        "events": activity_summary(LearningEvent.objects.all()),
    }


def users(q: str = ""):
    """Annotated with Subqueries: joining projects, events and AI calls in one
    annotate() would multiply rows and inflate the sums."""
    User = get_user_model()
    project_count = (
        Project.objects.filter(owner=OuterRef("pk")).order_by().values("owner")
        .annotate(n=Count("id")).values("n")
    )
    last_event = (
        LearningEvent.objects.filter(user=OuterRef("pk")).order_by("-created_at").values("created_at")[:1]
    )
    ai = AICallLog.objects.filter(user=OuterRef("pk")).order_by().values("user")
    queryset = User.objects.annotate(
        project_count=Subquery(project_count, output_field=IntegerField()),
        last_activity=Subquery(last_event, output_field=DateTimeField()),
        ai_calls=Subquery(ai.annotate(n=Count("id")).values("n"), output_field=IntegerField()),
        ai_cost=Subquery(ai.annotate(s=Sum("estimated_cost_usd")).values("s")),
    ).order_by("email")
    if q:
        queryset = queryset.filter(Q(email__icontains=q) | Q(name__icontains=q))
    return queryset


def user_detail(user_id) -> dict:
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise Http404("User not found")

    spaces = list(
        Space.objects.filter(owner=user).order_by()
        .annotate(project_count=Count("projects")).order_by("name")
        .values("id", "name", "project_count")
    )
    recent = list(
        LearningEvent.objects.filter(user=user).order_by("-created_at")
        .values("id", "created_at", "type", "project_id", "payload", project_name=F("project__name"))
        [:RECENT_EVENTS]
    )
    assessments = [
        {**row, "average_score": _opt(row["average_score"])}
        for row in QuizSession.objects.filter(project__owner=user).order_by()
        .annotate(average_score=Avg("questions__attempt__score"), answered=Count("questions__attempt"))
        .order_by("-created_at")
        .values("id", "project_id", "status", "created_at", "completed_at", "average_score",
                "answered", project_name=F("project__name"))[:RECENT_ASSESSMENTS]
    ]
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_staff": user.is_staff,
            "is_active": user.is_active,
            "joined_at": user.created_at,
        },
        "spaces": spaces,
        "projects": project_breakdown(Project.objects.filter(owner=user)),
        "recent_activity": recent,
        "assessments": assessments,
        "ai": ai_summary(AICallLog.objects.filter(user=user)),
    }


def activity(*, user_id=None, space_id=None, project_id=None, type=None, date_from=None, date_to=None):
    events = LearningEvent.objects.select_related("user", "space", "project__space").order_by("-created_at")
    if user_id:
        events = events.filter(user_id=user_id)
    if project_id:
        events = events.filter(project_id=project_id)
    if space_id:
        # Most events carry a project, not a space, so match both.
        events = events.filter(Q(space_id=space_id) | Q(project__space_id=space_id))
    if type:
        events = events.filter(type=type)
    if date_from:
        events = events.filter(created_at__date__gte=date_from)
    if date_to:
        events = events.filter(created_at__date__lte=date_to)
    return events
```

- [ ] **Step 5: Write the admin router and mount it**

`backend/insights/admin_api.py`:

```python
from uuid import UUID

from ninja import Query, Router
from ninja.pagination import paginate

from accounts.auth import StaffJWTAuth
from insights import admin_queries
from insights.admin_schemas import (
    ActivityFilters,
    ActivityRowOut,
    AdminUserDetailOut,
    AdminUserRow,
    OverviewOut,
)

router = Router(auth=StaffJWTAuth(), tags=["admin"])


@router.get("/overview", response=OverviewOut)
def overview(request):
    return admin_queries.overview()


@router.get("/users", response=list[AdminUserRow])
@paginate
def users(request, q: str = ""):
    return admin_queries.users(q)


@router.get("/users/{uuid:user_id}", response=AdminUserDetailOut)
def user_detail(request, user_id: UUID):
    return admin_queries.user_detail(user_id)


@router.get("/activity", response=list[ActivityRowOut])
@paginate
def activity(request, filters: ActivityFilters = Query(...)):
    return admin_queries.activity(**filters.dict())
```

In `backend/config/api.py`:

```python
from insights.admin_api import router as admin_router

api.add_router("/admin", admin_router)
```

This is `/api/admin/...`. It does not collide with Django's own `/admin/` site, which is mounted in `config/urls.py` outside `/api/`.

- [ ] **Step 6: Run the tests and see them pass**

Run: `pytest insights/tests/test_admin_core.py -v`
Expected: all pass (15 with the parametrised cases).

- [ ] **Step 7: Commit**

```bash
git add backend/insights backend/config/api.py
git commit -m "feat: admin API for overview, users, learning journey and activity"
```

---

### Task 31: Admin operations API (AI usage, evals, jobs, health)

**Files:**
- Create: `backend/insights/admin_ops.py` (queries and the one write action), `backend/insights/tests/test_admin_ops.py`
- Modify: `backend/insights/admin_schemas.py` (append), `backend/insights/admin_api.py` (append)

**Interfaces:**
- Consumes: `ai.models.AICallLog`, `ai.models.EvalRun`, `events.models.Job`, `common.errors.ServiceError`, the `/api/admin` router from Task 30, factories from Task 29.
- Produces:
  - `insights.admin_ops.ai_usage(days: int = 7) -> dict`
  - `insights.admin_ops.eval_runs(limit: int = 20) -> QuerySet[EvalRun]`
  - `insights.admin_ops.jobs(*, status=None, type=None) -> QuerySet[Job]`
  - `insights.admin_ops.jobs_summary() -> dict`
  - `insights.admin_ops.retry_failed_job(job_id) -> Job` (raises `Http404`, or `ServiceError(status=409, code="job_not_failed")`)
  - `insights.admin_ops.system_health() -> dict`
  - `GET /api/admin/ai-usage?days=7`, `GET /api/admin/evals`, `GET /api/admin/jobs?status=&type=`, `GET /api/admin/jobs/summary`, `POST /api/admin/jobs/{job_id}/retry`, `GET /api/admin/health`

`@paginate` fixes the list response to `{"items", "count"}`, so the counts by status are served by the separate `GET /admin/jobs/summary` endpoint.

- [ ] **Step 1: Write the failing tests**

`backend/insights/tests/test_admin_ops.py`:

```python
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
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `pytest insights/tests/test_admin_ops.py -v`
Expected: FAIL with 404 responses (`assert 404 == 401`, `KeyError: 'totals'`), because the routes do not exist.

- [ ] **Step 3: Append the schemas**

Append to `backend/insights/admin_schemas.py`:

```python
class AIUsageTotals(Schema):
    calls: int
    errors: int
    error_rate: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class AILatency(Schema):
    p50_ms: float | None
    p95_ms: float | None
    average_ms: float | None


class AIGroupRow(Schema):
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    average_latency_ms: float | None


class AIFeatureUsageRow(AIGroupRow):
    feature: str


class AIModelUsageRow(AIGroupRow):
    model: str


class AICallRow(Schema):
    id: UUID
    created_at: datetime
    feature: str
    model: str
    status: str
    error_type: str
    latency_ms: int
    retries: int
    input_tokens: int
    output_tokens: int
    trace_id: str
    user_email: str | None
    project_name: str | None


class AIUsageOut(Schema):
    days: int
    totals: AIUsageTotals
    latency: AILatency
    by_feature: list[AIFeatureUsageRow]
    by_model: list[AIModelUsageRow]
    slowest: list[AICallRow]
    recent_failures: list[AICallRow]


class EvalRunOut(Schema):
    id: UUID
    created_at: datetime
    suite: str
    git_sha: str
    passed: bool
    metrics: dict[str, Any]
    case_results: Any
    case_count: int

    @staticmethod
    def resolve_case_count(obj):
        return len(obj.case_results) if isinstance(obj.case_results, (list, dict)) else 0


class JobFilters(Schema):
    status: str | None = None
    type: str | None = None


class JobRowOut(Schema):
    id: UUID
    type: str
    status: str
    attempts: int
    max_attempts: int
    run_after: datetime | None
    locked_at: datetime | None
    last_error: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class JobTypeCount(Schema):
    type: str
    count: int


class JobsSummaryOut(Schema):
    by_status: dict[str, int]
    by_type: list[JobTypeCount]


class HealthCheck(Schema):
    key: str
    label: str
    status: str          # green | amber | red
    value: str
    detail: str


class HealthOut(Schema):
    status: str          # the worst check
    checked_at: datetime
    checks: list[HealthCheck]
```

- [ ] **Step 4: Write the operations module**

`backend/insights/admin_ops.py`:

```python
"""Operational reads for staff, plus the one admin write: retrying a failed job."""
from datetime import timedelta

from django.db import connection, transaction
from django.db.models import Aggregate, Avg, Count, F, FloatField, Max, Min, Q, Sum
from django.http import Http404
from django.utils import timezone

from ai.models import AICallLog, EvalRun
from common.errors import ServiceError
from events.models import Job

SLOWEST_CALLS = 20
RECENT_FAILURES = 20
STUCK_AFTER = timedelta(minutes=10)          # matches the worker's stuck-job recovery

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


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _opt(value):
    return round(float(value), 2) if value is not None else None


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
            "estimated_cost_usd": round(_num(row["cost"]), 6),
            "average_latency_ms": _opt(row["average_latency"]),
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
        "latency": {"p50_ms": _opt(latency["p50"]), "p95_ms": _opt(latency["p95"]),
                    "average_ms": _opt(latency["average"])},
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
    job = Job.objects.select_for_update().filter(pk=job_id).first()
    if job is None:
        raise Http404("Job not found")
    if job.status != Job.Status.FAILED:
        raise ServiceError("Only failed jobs can be retried.", status=409, code="job_not_failed")
    job.status = Job.Status.QUEUED
    job.attempts = 0
    job.run_after = timezone.now()
    job.locked_at = None
    job.save(update_fields=["status", "attempts", "run_after", "locked_at", "updated_at"])
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
    row = Job.objects.order_by().aggregate(
        queued=Count("id", filter=Q(status=Job.Status.QUEUED)),
        oldest_due=Min("run_after", filter=Q(status=Job.Status.QUEUED, run_after__lte=now)),
        stuck=Count("id", filter=Q(status=Job.Status.RUNNING, locked_at__lt=now - STUCK_AFTER)),
        failed=Count("id", filter=Q(status=Job.Status.FAILED, updated_at__gte=now - timedelta(hours=24))),
    )
    waiting = int((now - row["oldest_due"]).total_seconds()) if row["oldest_due"] else 0
    backlog = "red" if waiting > BACKLOG_RED_SECONDS else "amber" if waiting > BACKLOG_AMBER_SECONDS else "green"
    failed = "red" if row["failed"] >= FAILED_JOBS_RED else "amber" if row["failed"] else "green"
    return [
        _check("queue_backlog", "Job queue", backlog, f"{row['queued']} queued",
               f"oldest due job has waited {waiting}s; is run_worker running?" if waiting else ""),
        _check("stuck_jobs", "Stuck jobs", "amber" if row["stuck"] else "green", row["stuck"],
               "running for more than 10 minutes" if row["stuck"] else ""),
        _check("failed_jobs_24h", "Failed jobs (24 h)", failed, row["failed"]),
    ]


def _ai_checks(now) -> list[dict]:
    row = AICallLog.objects.order_by().aggregate(
        calls=Count("id", filter=Q(created_at__gte=now - timedelta(hours=1))),
        errors=Count("id", filter=Q(created_at__gte=now - timedelta(hours=1), status=AICallLog.Status.ERROR)),
        last_ok=Max("created_at", filter=Q(status=AICallLog.Status.OK)),
    )
    rate = row["errors"] / row["calls"] if row["calls"] else 0.0
    status = "green"
    if row["calls"] >= AI_ERROR_MIN_CALLS:
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
```

- [ ] **Step 5: Append the routes**

Append to `backend/insights/admin_api.py` (and extend the two import lines at the top):

```python
from insights import admin_ops
from insights.admin_schemas import AIUsageOut, EvalRunOut, HealthOut, JobFilters, JobRowOut, JobsSummaryOut


@router.get("/ai-usage", response=AIUsageOut)
def ai_usage(request, days: int = 7):
    return admin_ops.ai_usage(days)


@router.get("/evals", response=list[EvalRunOut])
def evals(request):
    return list(admin_ops.eval_runs())


@router.get("/jobs/summary", response=JobsSummaryOut)
def jobs_summary(request):
    return admin_ops.jobs_summary()


@router.get("/jobs", response=list[JobRowOut])
@paginate
def jobs(request, filters: JobFilters = Query(...)):
    return admin_ops.jobs(**filters.dict())


@router.post("/jobs/{uuid:job_id}/retry", response=JobRowOut)
def retry_job(request, job_id: UUID):
    return admin_ops.retry_failed_job(job_id)


@router.get("/health", response=HealthOut)
def health(request):
    return admin_ops.system_health()
```

- [ ] **Step 6: Run the tests and see them pass**

Run: `pytest insights/tests/test_admin_ops.py -v`
Expected: all pass (18 with the parametrised cases).

If `test_retry_refuses_jobs_that_did_not_fail` gets a 500 instead of 409, the `ServiceError` exception handler from Task 2 is not registered on `api` in `config/api.py`. Register it there; do not catch the error in the view.

- [ ] **Step 7: Run the whole backend suite and commit**

Run: `pytest -q`
Expected: all pass.

```bash
git add backend/insights
git commit -m "feat: admin API for AI usage, evals, jobs and system health"
```

---

### Task 32: Analytics UI (project tab and global page)

**Files:**
- Modify: `frontend/src/api/types.ts` (append), `frontend/src/routes.tsx`, `frontend/src/features/projects/tabs.ts`, `frontend/src/components/layout/nav.ts` (created in Task 4)
- Create: `frontend/src/api/analytics.ts`
- Create: `frontend/src/components/shared/SimpleTable.tsx`, `frontend/src/components/shared/StatTile.tsx`
- Create: `frontend/src/features/analytics/charts.tsx`, `frontend/src/features/analytics/AnalyticsPanels.tsx`, `frontend/src/features/analytics/ProjectAnalyticsPage.tsx`, `frontend/src/features/analytics/GlobalAnalyticsPage.tsx`

**Interfaces:**
- Consumes: `api.get`, `useProjectId()`, `Card`, `Badge`, `Spinner`, `PageHeader`, `EmptyState`, `ErrorState`, `MasteryBar` (named exports, contract C8); `GET /api/projects/{id}/analytics`, `GET /api/analytics/global`.
- Produces:
  - Types `ProjectAnalytics`, `GlobalAnalytics` and their parts in `src/api/types.ts`
  - `useProjectAnalytics(projectId: string)`, `useGlobalAnalytics()`
  - `SimpleTable<T>({ columns, rows, rowKey, onRowClick? })`, `Column<T>`; `StatTile({ label, value, hint? })` — both reused by Task 33
  - Project tab `analytics`, route `/analytics`

- [ ] **Step 1: Make sure Recharts is installed**

```bash
cd frontend
grep -q '"recharts"' package.json || npm install recharts
```

- [ ] **Step 2: Append the types**

Append to `frontend/src/api/types.ts`:

```ts
// ---- analytics ----
export type DayCount = { day: string; count: number }
export type TypeCount = { type: string; count: number }
export type ActivitySummary = { total: number; per_day: DayCount[]; by_type: TypeCount[] }
export type SessionScore = {
  session_id: string
  project_id: string
  completed_at: string | null
  average_score: number | null
  answered: number
}
export type QuizSummary = {
  sessions_started: number
  sessions_completed: number
  questions_answered: number
  average_score: number | null
  per_session: SessionScore[]
}
export type MasterySummary = { concepts: number; average: number | null; low: number; medium: number; high: number }
export type ConceptTrend = {
  concept_id: string
  name: string
  score: number
  delta: number
  label: string
  evidence_count: number
}
export type AIFeatureRow = {
  feature: string
  calls: number
  input_tokens: number
  output_tokens: number
  estimated_cost_usd: number
  errors: number
}
export type AIActivity = Omit<AIFeatureRow, "feature"> & { by_feature: AIFeatureRow[] }
export type ProjectAnalytics = {
  project_id: string
  activity: ActivitySummary
  quiz: QuizSummary
  mastery: MasterySummary
  trends: ConceptTrend[]
  trend_counts: Record<string, number>
  ai: AIActivity
}
export type ProjectBreakdownRow = {
  project_id: string
  name: string
  space_id: string
  space_name: string
  last_activity_at: string | null
  events: number
  materials: number
  concepts: number
  average_mastery: number | null
  questions_answered: number
  average_score: number | null
}
export type SpaceBreakdownRow = {
  space_id: string
  name: string
  projects: number
  events: number
  average_mastery: number | null
}
export type GlobalAnalytics = {
  activity: ActivitySummary
  quiz: QuizSummary
  mastery: MasterySummary
  ai: AIActivity
  spaces: SpaceBreakdownRow[]
  projects: ProjectBreakdownRow[]
}
```

- [ ] **Step 3: Write the hooks**

`frontend/src/api/analytics.ts`:

```ts
import { useQuery } from "@tanstack/react-query"
import { api } from "./client"
import type { GlobalAnalytics, ProjectAnalytics } from "./types"

export function useProjectAnalytics(projectId: string) {
  return useQuery({
    queryKey: ["analytics", "project", projectId],
    queryFn: () => api.get<ProjectAnalytics>(`/projects/${projectId}/analytics`),
  })
}

export function useGlobalAnalytics() {
  return useQuery({
    queryKey: ["analytics", "global"],
    queryFn: () => api.get<GlobalAnalytics>("/analytics/global"),
  })
}
```

- [ ] **Step 4: Write the shared table and stat tile**

`frontend/src/components/shared/SimpleTable.tsx`:

```tsx
import type { ReactNode } from "react"

export type Column<T> = { header: string; cell: (row: T) => ReactNode; align?: "left" | "right" }

export function SimpleTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
}: {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  onRowClick?: (row: T) => void
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
            {columns.map((column) => (
              <th key={column.header} className={`px-3 py-2 font-medium ${column.align === "right" ? "text-right" : "text-left"}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`border-b border-gray-100 ${onRowClick ? "cursor-pointer hover:bg-gray-50" : ""}`}
            >
              {columns.map((column) => (
                <td key={column.header} className={`px-3 py-2 ${column.align === "right" ? "text-right tabular-nums" : ""}`}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

`frontend/src/components/shared/StatTile.tsx`:

```tsx
export function StatTile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-gray-900">{value}</div>
      {hint ? <div className="mt-1 text-xs text-gray-500">{hint}</div> : null}
    </div>
  )
}
```

- [ ] **Step 5: Write the charts**

`frontend/src/features/analytics/charts.tsx`:

```tsx
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { DayCount, SessionScore } from "../../api/types"

const INK = "#4f46e5"
const GRID = "#e5e7eb"

export function ActivityChart({ data }: { data: DayCount[] }) {
  const rows = data.map((d) => ({ day: d.day.slice(5), events: d.count }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 11 }} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip />
        <Bar dataKey="events" fill={INK} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function QuizScoreChart({ data }: { data: SessionScore[] }) {
  const rows = data.map((s, index) => ({
    label: s.completed_at ? s.completed_at.slice(5, 10) : `#${index + 1}`,
    score: s.average_score === null ? null : Math.round(s.average_score * 100),
  }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} />
        <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip formatter={(value) => [`${value}%`, "Average score"]} />
        <Line type="monotone" dataKey="score" stroke={INK} strokeWidth={2} dot={{ r: 3 }} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 6: Write the panels both pages share**

`frontend/src/features/analytics/AnalyticsPanels.tsx`:

```tsx
import type { AIActivity, ActivitySummary, MasterySummary, QuizSummary } from "../../api/types"
import { EmptyState } from "../../components/shared/EmptyState"
import { SimpleTable } from "../../components/shared/SimpleTable"
import { StatTile } from "../../components/shared/StatTile"
import { Card } from "../../components/ui/Card"
import { ActivityChart, QuizScoreChart } from "./charts"

export const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value * 100)}%`)
export const usd = (value: number) => `$${value.toFixed(4)}`

export function SummaryTiles({
  activity,
  quiz,
  mastery,
  ai,
}: {
  activity: ActivitySummary
  quiz: QuizSummary
  mastery: MasterySummary
  ai: AIActivity
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatTile label="Activity (14 days)" value={activity.total} hint="learning events" />
      <StatTile
        label="Average quiz score"
        value={percent(quiz.average_score)}
        hint={`${quiz.questions_answered} answers in ${quiz.sessions_completed} quizzes`}
      />
      <StatTile
        label="Average mastery"
        value={percent(mastery.average)}
        hint={`${mastery.high} strong · ${mastery.medium} developing · ${mastery.low} weak`}
      />
      <StatTile label="AI calls" value={ai.calls} hint={`${usd(ai.estimated_cost_usd)} estimated · ${ai.errors} failed`} />
    </div>
  )
}

export function ActivityPanel({ activity }: { activity: ActivitySummary }) {
  return (
    <Card title="Learning activity per day">
      {activity.total === 0 ? (
        <EmptyState title="No activity in the last 14 days" description="Ask the Tutor a question or take a quiz." />
      ) : (
        <>
          <ActivityChart data={activity.per_day} />
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            {activity.by_type.map((row) => (
              <li key={row.type}>
                <span className="font-medium text-gray-900">{row.count}</span> {row.type}
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

export function QuizPanel({ quiz }: { quiz: QuizSummary }) {
  return (
    <Card title="Quiz score per session">
      {quiz.per_session.length === 0 ? (
        <EmptyState title="No completed quizzes yet" description="Finish a quiz to see your score trend." />
      ) : (
        <QuizScoreChart data={quiz.per_session} />
      )}
    </Card>
  )
}

export function AIUsagePanel({ ai }: { ai: AIActivity }) {
  return (
    <Card title="AI activity by feature">
      {ai.by_feature.length === 0 ? (
        <EmptyState title="No AI calls yet" />
      ) : (
        <SimpleTable
          rows={ai.by_feature}
          rowKey={(row) => row.feature}
          columns={[
            { header: "Feature", cell: (row) => row.feature },
            { header: "Calls", align: "right", cell: (row) => row.calls },
            { header: "Failed", align: "right", cell: (row) => row.errors },
            { header: "Tokens in", align: "right", cell: (row) => row.input_tokens.toLocaleString() },
            { header: "Tokens out", align: "right", cell: (row) => row.output_tokens.toLocaleString() },
            { header: "Est. cost", align: "right", cell: (row) => usd(row.estimated_cost_usd) },
          ]}
        />
      )}
    </Card>
  )
}
```

- [ ] **Step 7: Write the project analytics page**

`frontend/src/features/analytics/ProjectAnalyticsPage.tsx`:

```tsx
import { useProjectAnalytics } from "../../api/analytics"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { MasteryBar } from "../../components/shared/MasteryBar"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"
import { useProjectId } from "../projects/useProjectId"
import { AIUsagePanel, ActivityPanel, QuizPanel, SummaryTiles } from "./AnalyticsPanels"

export function ProjectAnalyticsPage() {
  const projectId = useProjectId()
  const { data, isLoading, error, refetch } = useProjectAnalytics(projectId)

  if (isLoading) return <Spinner className="mx-auto mt-16" />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <SummaryTiles activity={data.activity} quiz={data.quiz} mastery={data.mastery} ai={data.ai} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ActivityPanel activity={data.activity} />
        <QuizPanel quiz={data.quiz} />
      </div>
      <Card title="Concept trends">
        {data.trends.length === 0 ? (
          <EmptyState title="No concepts yet" description="Upload a PDF so concepts can be extracted." />
        ) : (
          <div className="space-y-2">
            {data.trends.map((trend) => (
              <MasteryBar key={trend.concept_id} label={trend.name} value={trend.score} trend={trend.label} />
            ))}
          </div>
        )}
      </Card>
      <AIUsagePanel ai={data.ai} />
    </div>
  )
}
```

- [ ] **Step 8: Write the global analytics page**

`frontend/src/features/analytics/GlobalAnalyticsPage.tsx`:

```tsx
import { useNavigate } from "react-router-dom"
import { useGlobalAnalytics } from "../../api/analytics"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { PageHeader } from "../../components/shared/PageHeader"
import { SimpleTable } from "../../components/shared/SimpleTable"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"
import { AIUsagePanel, ActivityPanel, QuizPanel, SummaryTiles, percent } from "./AnalyticsPanels"

export function GlobalAnalyticsPage() {
  const navigate = useNavigate()
  const { data, isLoading, error, refetch } = useGlobalAnalytics()

  if (isLoading) return <Spinner className="mx-auto mt-16" />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <PageHeader title="Analytics" subtitle="Learning activity across all your Spaces and Projects" />
      <SummaryTiles activity={data.activity} quiz={data.quiz} mastery={data.mastery} ai={data.ai} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ActivityPanel activity={data.activity} />
        <QuizPanel quiz={data.quiz} />
      </div>
      <Card title="Spaces">
        {data.spaces.length === 0 ? (
          <EmptyState title="No Spaces yet" />
        ) : (
          <SimpleTable
            rows={data.spaces}
            rowKey={(row) => row.space_id}
            onRowClick={(row) => navigate(`/spaces/${row.space_id}`)}
            columns={[
              { header: "Space", cell: (row) => row.name },
              { header: "Projects", align: "right", cell: (row) => row.projects },
              { header: "Events", align: "right", cell: (row) => row.events },
              { header: "Avg. mastery", align: "right", cell: (row) => percent(row.average_mastery) },
            ]}
          />
        )}
      </Card>
      <Card title="Projects">
        {data.projects.length === 0 ? (
          <EmptyState title="No Projects yet" />
        ) : (
          <SimpleTable
            rows={data.projects}
            rowKey={(row) => row.project_id}
            onRowClick={(row) => navigate(`/projects/${row.project_id}/analytics`)}
            columns={[
              { header: "Project", cell: (row) => row.name },
              { header: "Space", cell: (row) => row.space_name },
              { header: "Materials", align: "right", cell: (row) => row.materials },
              { header: "Concepts", align: "right", cell: (row) => row.concepts },
              { header: "Avg. mastery", align: "right", cell: (row) => percent(row.average_mastery) },
              { header: "Answers", align: "right", cell: (row) => row.questions_answered },
              { header: "Avg. score", align: "right", cell: (row) => percent(row.average_score) },
              { header: "Events", align: "right", cell: (row) => row.events },
              {
                header: "Last active",
                cell: (row) => (row.last_activity_at ? new Date(row.last_activity_at).toLocaleDateString() : "—"),
              },
            ]}
          />
        )}
      </Card>
      <AIUsagePanel ai={data.ai} />
    </div>
  )
}
```

- [ ] **Step 9: Register the tab, the route and the nav link**

In `frontend/src/features/projects/tabs.ts` append to `projectTabs` (it must be the last tab, after `growth`):

```ts
  { path: "analytics", label: "Analytics" },
```

In `frontend/src/routes.tsx` add the imports, the child route inside the `ProjectLayout` children, and the top-level route next to the other authenticated routes (inside the same `RequireAuth` / app layout wrapper that `/` uses):

```tsx
import { GlobalAnalyticsPage } from "./features/analytics/GlobalAnalyticsPage"
import { ProjectAnalyticsPage } from "./features/analytics/ProjectAnalyticsPage"

// inside the ProjectLayout children array
{ path: "analytics", element: <ProjectAnalyticsPage /> },

// next to the "/" and "/spaces/:id" routes
{ path: "analytics", element: <GlobalAnalyticsPage /> },
```

The top navigation is data-driven. In `frontend/src/components/layout/nav.ts` (Phase 1) add the item after "Spaces"; `AppLayout` renders it with the shared styles:

```ts
export const navItems: NavItem[] = [
  { to: "/", label: "Home" },
  { to: "/spaces", label: "Spaces" },
  { to: "/analytics", label: "Analytics" },
];
```

- [ ] **Step 10: Build and check by hand**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

Manual check with the API, worker and frontend running (contract C9):
1. Open a project that has a processed PDF, at least one Tutor message and one completed quiz. Open the **Analytics** tab.
2. The four tiles show non-zero activity, a quiz score, a mastery percentage and an AI call count.
3. The bar chart has 14 bars with today's bar non-zero. The line chart has one point per completed quiz.
4. Concept trends list every concept with a bar and a trend badge. The AI table lists `tutor`, `quiz_gen` and `grading` rows.
5. Open a brand-new empty project: every card shows its empty state and nothing crashes.
6. Click **Analytics** in the top nav: the Spaces and Projects tables list only your own data, and clicking a project row opens that project's Analytics tab.
7. Stop the API and reload the page: the error state appears with a working retry button.

- [ ] **Step 11: Commit**

```bash
git add frontend
git commit -m "feat: project and global analytics pages"
```

---

### Task 33: Admin dashboard UI

Part A needs Task 30. Part B needs Task 31. Each part ends with its own commit, so Part B can be dropped.

**Files:**
- Confirm (create only if missing): `frontend/src/auth/RequireAdmin.tsx`
- Modify: `frontend/src/api/types.ts` (append), `frontend/src/routes.tsx`, `frontend/src/components/layout/nav.ts`
- Create: `frontend/src/api/admin.ts`, `frontend/src/components/shared/Pager.tsx`
- Create (Part A): `frontend/src/features/admin/adminNav.ts`, `AdminLayout.tsx`, `AdminOverviewPage.tsx`, `AdminUsersPage.tsx`, `AdminUserDetailPage.tsx`, `AdminActivityPage.tsx`
- Create (Part B): `frontend/src/features/admin/AdminAIUsagePage.tsx`, `AdminEvalsPage.tsx`, `AdminJobsPage.tsx`, `AdminHealthPage.tsx`

**Interfaces:**
- Consumes: `useAuth()` (the `User` type has `is_staff: boolean`), `api`, `Paginated<T>`, `ApiError`, `SimpleTable`, `StatTile`, `ActivityChart`, `percent`, `usd`, `StatusBadge`, `Badge`, `Button`, `Input`, `Card`, `Spinner`, `PageHeader`, `EmptyState`, `ErrorState`; every `/api/admin/*` endpoint from Tasks 30 and 31.
- Produces: hooks `useAdminOverview`, `useAdminUsers`, `useAdminUser`, `useAdminActivity`, `useAdminAIUsage`, `useAdminEvals`, `useAdminJobs`, `useAdminJobsSummary`, `useRetryJob`, `useAdminHealth`; `Pager({ count, limit, offset, onChange })`; routes under `/admin`.

#### Part A — layout, overview, users, user journey, activity

- [ ] **Step 1: Confirm the admin guard**

Open `frontend/src/auth/RequireAdmin.tsx`. It must behave like this. If the file is missing, create it with exactly this content:

```tsx
import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { Spinner } from "../components/ui/Spinner"
import { useAuth } from "./AuthProvider"

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner className="mx-auto mt-16" />
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_staff) return <Navigate to="/" replace />
  return <>{children}</>
}
```

The guard is a convenience for the UI only. The real control is `StaffJWTAuth` on the API, which Task 30 tests.

- [ ] **Step 2: Append the Part A types**

Append to `frontend/src/api/types.ts`:

```ts
// ---- admin (core) ----
export type AdminOverview = {
  users: number
  spaces: number
  projects: number
  materials: number
  materials_by_status: { status: string; count: number }[]
  quiz_sessions: number
  questions_answered: number
  active_users_7d: number
  events: ActivitySummary
}
export type AdminUserRow = {
  id: string
  email: string
  name: string
  is_staff: boolean
  is_active: boolean
  project_count: number
  last_activity: string | null
  ai_calls: number
  ai_cost_usd: number
}
export type AdminEventRow = {
  id: string
  created_at: string
  type: string
  project_id: string | null
  project_name: string | null
  payload: Record<string, unknown>
}
export type AdminAssessmentRow = {
  id: string
  project_id: string
  project_name: string
  status: string
  created_at: string
  completed_at: string | null
  average_score: number | null
  answered: number
}
export type AdminUserDetail = {
  user: { id: string; email: string; name: string; is_staff: boolean; is_active: boolean; joined_at: string | null }
  spaces: { id: string; name: string; project_count: number }[]
  projects: ProjectBreakdownRow[]
  recent_activity: AdminEventRow[]
  assessments: AdminAssessmentRow[]
  ai: AIActivity
}
export type AdminActivityRow = {
  id: string
  created_at: string
  type: string
  payload: Record<string, unknown>
  user_id: string
  user_email: string
  project_id: string | null
  project_name: string | null
  space_id: string | null
  space_name: string | null
}
export type AdminActivityFilters = {
  user_id?: string
  space_id?: string
  project_id?: string
  type?: string
  date_from?: string
  date_to?: string
  limit: number
  offset: number
}
```

- [ ] **Step 3: Write the Part A hooks**

`frontend/src/api/admin.ts`:

```ts
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { api, type Paginated } from "./client"
import type {
  AdminActivityFilters,
  AdminActivityRow,
  AdminOverview,
  AdminUserDetail,
  AdminUserRow,
} from "./types"

export function useAdminOverview() {
  return useQuery({ queryKey: ["admin", "overview"], queryFn: () => api.get<AdminOverview>("/admin/overview") })
}

export function useAdminUsers(params: { q?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ["admin", "users", params],
    queryFn: () => api.get<Paginated<AdminUserRow>>("/admin/users", { ...params, q: params.q || undefined }),
    placeholderData: keepPreviousData,
  })
}

export function useAdminUser(userId: string | undefined) {
  return useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
    enabled: Boolean(userId),
  })
}

export function useAdminActivity(filters: AdminActivityFilters) {
  return useQuery({
    queryKey: ["admin", "activity", filters],
    queryFn: () => api.get<Paginated<AdminActivityRow>>("/admin/activity", filters),
    placeholderData: keepPreviousData,
  })
}
```

- [ ] **Step 4: Write the pager**

`frontend/src/components/shared/Pager.tsx`:

```tsx
import { Button } from "../ui/Button"

export function Pager({
  count,
  limit,
  offset,
  onChange,
}: {
  count: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}) {
  if (count <= limit) return null
  const first = offset + 1
  const last = Math.min(offset + limit, count)
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-gray-600">
      <span>
        {first}–{last} of {count}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={last >= count} onClick={() => onChange(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Write the admin layout**

`frontend/src/features/admin/adminNav.ts`:

```ts
// Part B appends its four entries. Dropping Part B means not adding them.
export const adminNav: { path: string; label: string }[] = [
  { path: "", label: "Overview" },
  { path: "users", label: "Users" },
  { path: "activity", label: "Activity" },
]
```

`frontend/src/features/admin/AdminLayout.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom"
import { PageHeader } from "../../components/shared/PageHeader"
import { adminNav } from "./adminNav"

export function AdminLayout() {
  return (
    <div className="space-y-4">
      <PageHeader title="Admin" subtitle="Platform-wide view of users, learning activity, AI and system health" />
      <nav className="flex flex-wrap gap-1 border-b border-gray-200">
        {adminNav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === ""}
            className={({ isActive }) =>
              `-mb-px border-b-2 px-3 py-2 text-sm ${
                isActive ? "border-indigo-600 font-medium text-indigo-700" : "border-transparent text-gray-600 hover:text-gray-900"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
}
```

- [ ] **Step 6: Write the overview page**

`frontend/src/features/admin/AdminOverviewPage.tsx`:

```tsx
import { useAdminOverview } from "../../api/admin"
import { ErrorState } from "../../components/shared/ErrorState"
import { StatTile } from "../../components/shared/StatTile"
import { StatusBadge } from "../../components/shared/StatusBadge"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"
import { ActivityPanel } from "../analytics/AnalyticsPanels"

export function AdminOverviewPage() {
  const { data, isLoading, error, refetch } = useAdminOverview()
  if (isLoading) return <Spinner className="mx-auto mt-16" />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Users" value={data.users} hint={`${data.active_users_7d} active in 7 days`} />
        <StatTile label="Spaces" value={data.spaces} />
        <StatTile label="Projects" value={data.projects} />
        <StatTile label="Materials" value={data.materials} />
        <StatTile label="Quiz sessions" value={data.quiz_sessions} />
        <StatTile label="Questions answered" value={data.questions_answered} />
        <StatTile label="Events (14 days)" value={data.events.total} />
      </div>
      <Card title="Materials by status">
        <div className="flex flex-wrap gap-3 text-sm">
          {data.materials_by_status.length === 0 ? (
            <span className="text-gray-500">No materials uploaded yet.</span>
          ) : (
            data.materials_by_status.map((row) => (
              <span key={row.status} className="flex items-center gap-2">
                <StatusBadge status={row.status} /> {row.count}
              </span>
            ))
          )}
        </div>
      </Card>
      <ActivityPanel activity={data.events} />
    </div>
  )
}
```

- [ ] **Step 7: Write the users page**

`frontend/src/features/admin/AdminUsersPage.tsx`:

```tsx
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAdminUsers } from "../../api/admin"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { Pager } from "../../components/shared/Pager"
import { SimpleTable } from "../../components/shared/SimpleTable"
import { Badge } from "../../components/ui/Badge"
import { Card } from "../../components/ui/Card"
import { Input } from "../../components/ui/Input"
import { Spinner } from "../../components/ui/Spinner"
import { usd } from "../analytics/AnalyticsPanels"

const LIMIT = 25

export function AdminUsersPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState("")
  const [offset, setOffset] = useState(0)
  const { data, isLoading, error, refetch } = useAdminUsers({ q, limit: LIMIT, offset })

  return (
    <Card title="Users">
      <div className="mb-3 max-w-sm">
        <Input
          placeholder="Search by email or name"
          value={q}
          onChange={(event) => {
            setQ(event.target.value)
            setOffset(0)
          }}
        />
      </div>
      {isLoading ? (
        <Spinner className="mx-auto my-8" />
      ) : error || !data ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data.items.length === 0 ? (
        <EmptyState title="No users match" />
      ) : (
        <>
          <SimpleTable
            rows={data.items}
            rowKey={(row) => row.id}
            onRowClick={(row) => navigate(`/admin/users/${row.id}`)}
            columns={[
              {
                header: "User",
                cell: (row) => (
                  <div>
                    <div className="font-medium text-gray-900">{row.name || row.email}</div>
                    <div className="text-xs text-gray-500">{row.email}</div>
                  </div>
                ),
              },
              {
                header: "Role",
                cell: (row) =>
                  row.is_staff ? <Badge tone="blue">admin</Badge> : row.is_active ? <Badge>learner</Badge> : <Badge tone="red">disabled</Badge>,
              },
              { header: "Projects", align: "right", cell: (row) => row.project_count },
              { header: "AI calls", align: "right", cell: (row) => row.ai_calls },
              { header: "AI cost", align: "right", cell: (row) => usd(row.ai_cost_usd) },
              {
                header: "Last activity",
                cell: (row) => (row.last_activity ? new Date(row.last_activity).toLocaleString() : "never"),
              },
            ]}
          />
          <Pager count={data.count} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </Card>
  )
}
```

- [ ] **Step 8: Write the user journey page**

`frontend/src/features/admin/AdminUserDetailPage.tsx`:

```tsx
import { Link, useParams } from "react-router-dom"
import { useAdminUser } from "../../api/admin"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { SimpleTable } from "../../components/shared/SimpleTable"
import { StatTile } from "../../components/shared/StatTile"
import { StatusBadge } from "../../components/shared/StatusBadge"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"
import { AIUsagePanel, percent, usd } from "../analytics/AnalyticsPanels"

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
  const { data, isLoading, error, refetch } = useAdminUser(userId)

  if (isLoading) return <Spinner className="mx-auto mt-16" />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{data.user.name || data.user.email}</h2>
          <p className="text-sm text-gray-500">
            {data.user.email}
            {data.user.joined_at ? ` · joined ${new Date(data.user.joined_at).toLocaleDateString()}` : ""}
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link className="text-indigo-700 hover:underline" to={`/admin/activity?user_id=${data.user.id}`}>
            All activity
          </Link>
          <Link className="text-indigo-700 hover:underline" to="/admin/users">
            Back to users
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Spaces" value={data.spaces.length} hint={data.spaces.map((s) => s.name).join(", ")} />
        <StatTile label="Projects" value={data.projects.length} />
        <StatTile label="AI calls" value={data.ai.calls} hint={`${data.ai.errors} failed`} />
        <StatTile label="AI cost" value={usd(data.ai.estimated_cost_usd)} />
      </div>

      <Card title="Projects and progress">
        {data.projects.length === 0 ? (
          <EmptyState title="No projects yet" />
        ) : (
          <SimpleTable
            rows={data.projects}
            rowKey={(row) => row.project_id}
            columns={[
              { header: "Project", cell: (row) => row.name },
              { header: "Space", cell: (row) => row.space_name },
              { header: "Materials", align: "right", cell: (row) => row.materials },
              { header: "Concepts", align: "right", cell: (row) => row.concepts },
              { header: "Avg. mastery", align: "right", cell: (row) => percent(row.average_mastery) },
              { header: "Answers", align: "right", cell: (row) => row.questions_answered },
              { header: "Avg. score", align: "right", cell: (row) => percent(row.average_score) },
            ]}
          />
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Recent assessments">
          {data.assessments.length === 0 ? (
            <EmptyState title="No quizzes yet" />
          ) : (
            <SimpleTable
              rows={data.assessments}
              rowKey={(row) => row.id}
              columns={[
                { header: "Project", cell: (row) => row.project_name },
                { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
                { header: "Answered", align: "right", cell: (row) => row.answered },
                { header: "Score", align: "right", cell: (row) => percent(row.average_score) },
                { header: "Started", cell: (row) => new Date(row.created_at).toLocaleString() },
              ]}
            />
          )}
        </Card>
        <Card title="Recent activity">
          {data.recent_activity.length === 0 ? (
            <EmptyState title="No activity yet" />
          ) : (
            <SimpleTable
              rows={data.recent_activity}
              rowKey={(row) => row.id}
              columns={[
                { header: "When", cell: (row) => new Date(row.created_at).toLocaleString() },
                { header: "Event", cell: (row) => <code className="text-xs">{row.type}</code> },
                { header: "Project", cell: (row) => row.project_name ?? "—" },
              ]}
            />
          )}
        </Card>
      </div>

      <AIUsagePanel ai={data.ai} />
    </div>
  )
}
```

- [ ] **Step 9: Write the activity page (filters live in the URL)**

`frontend/src/features/admin/AdminActivityPage.tsx`:

```tsx
import { useSearchParams } from "react-router-dom"
import { useAdminActivity, useAdminUser, useAdminUsers } from "../../api/admin"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { Pager } from "../../components/shared/Pager"
import { SimpleTable } from "../../components/shared/SimpleTable"
import { Button } from "../../components/ui/Button"
import { Card } from "../../components/ui/Card"
import { Input } from "../../components/ui/Input"
import { Spinner } from "../../components/ui/Spinner"

const LIMIT = 50
const FILTER_KEYS = ["user_id", "space_id", "project_id", "type", "date_from", "date_to"] as const
// Spec section 9.
const EVENT_TYPES = [
  "space.created",
  "project.created",
  "material.uploaded",
  "material.processed",
  "material.failed",
  "tutor.message_sent",
  "quiz.started",
  "question.answered",
  "quiz.completed",
  "mastery.updated",
  "recommendation.created",
  "recommendation.completed",
]
const selectClass = "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"

export function AdminActivityPage() {
  const [params, setParams] = useSearchParams()
  const value = (key: string) => params.get(key) ?? ""
  const offset = Number(params.get("offset") ?? 0)

  const filters = {
    user_id: value("user_id") || undefined,
    space_id: value("space_id") || undefined,
    project_id: value("project_id") || undefined,
    type: value("type") || undefined,
    date_from: value("date_from") || undefined,
    date_to: value("date_to") || undefined,
    limit: LIMIT,
    offset,
  }
  const activity = useAdminActivity(filters)
  const users = useAdminUsers({ limit: 100, offset: 0 })
  // Space and Project choices come from the selected user's journey.
  const selectedUser = useAdminUser(filters.user_id)

  function update(key: string, next: string) {
    const copy = new URLSearchParams(params)
    if (next) copy.set(key, next)
    else copy.delete(key)
    if (key === "user_id") {
      copy.delete("space_id")
      copy.delete("project_id")
    }
    if (key !== "offset") copy.delete("offset")
    setParams(copy, { replace: true })
  }

  const hasFilters = FILTER_KEYS.some((key) => params.has(key))
  const spaces = selectedUser.data?.spaces ?? []
  const projects = (selectedUser.data?.projects ?? []).filter(
    (project) => !filters.space_id || project.space_id === filters.space_id,
  )

  return (
    <Card
      title="Platform activity"
      actions={
        hasFilters ? (
          <Button variant="ghost" size="sm" onClick={() => setParams({}, { replace: true })}>
            Clear filters
          </Button>
        ) : undefined
      }
    >
      <div className="mb-4 grid gap-3 md:grid-cols-3 lg:grid-cols-6">
        <label className="text-xs text-gray-600">
          User
          <select className={selectClass} value={value("user_id")} onChange={(e) => update("user_id", e.target.value)}>
            <option value="">All users</option>
            {(users.data?.items ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.email}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-gray-600">
          Space
          <select
            className={selectClass}
            value={value("space_id")}
            disabled={!filters.user_id}
            onChange={(e) => update("space_id", e.target.value)}
          >
            <option value="">{filters.user_id ? "All spaces" : "Pick a user first"}</option>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-gray-600">
          Project
          <select
            className={selectClass}
            value={value("project_id")}
            disabled={!filters.user_id}
            onChange={(e) => update("project_id", e.target.value)}
          >
            <option value="">{filters.user_id ? "All projects" : "Pick a user first"}</option>
            {projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-gray-600">
          Activity type
          <select className={selectClass} value={value("type")} onChange={(e) => update("type", e.target.value)}>
            <option value="">All types</option>
            {EVENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <Input label="From" type="date" value={value("date_from")} onChange={(e) => update("date_from", e.target.value)} />
        <Input label="To" type="date" value={value("date_to")} onChange={(e) => update("date_to", e.target.value)} />
      </div>

      {activity.isLoading ? (
        <Spinner className="mx-auto my-8" />
      ) : activity.error || !activity.data ? (
        <ErrorState error={activity.error} onRetry={() => activity.refetch()} />
      ) : activity.data.items.length === 0 ? (
        <EmptyState title="No activity matches these filters" />
      ) : (
        <>
          <SimpleTable
            rows={activity.data.items}
            rowKey={(row) => row.id}
            columns={[
              { header: "When", cell: (row) => new Date(row.created_at).toLocaleString() },
              { header: "User", cell: (row) => row.user_email },
              { header: "Event", cell: (row) => <code className="text-xs">{row.type}</code> },
              { header: "Space", cell: (row) => row.space_name ?? "—" },
              { header: "Project", cell: (row) => row.project_name ?? "—" },
              {
                header: "Details",
                cell: (row) => (
                  <code className="block max-w-xs truncate text-xs text-gray-500" title={JSON.stringify(row.payload)}>
                    {JSON.stringify(row.payload)}
                  </code>
                ),
              },
            ]}
          />
          <Pager count={activity.data.count} limit={LIMIT} offset={offset} onChange={(next) => update("offset", String(next))} />
        </>
      )}
    </Card>
  )
}
```

`update("offset", "0")` stores `offset=0`, which reads back as `0`, so paging to the first page works.

- [ ] **Step 10: Register the admin routes and the nav link**

In `frontend/src/routes.tsx` add the imports and one route next to the other authenticated top-level routes (inside the same app layout wrapper that `/` uses, so the top nav stays visible):

```tsx
import { RequireAdmin } from "./auth/RequireAdmin"
import { AdminActivityPage } from "./features/admin/AdminActivityPage"
import { AdminLayout } from "./features/admin/AdminLayout"
import { AdminOverviewPage } from "./features/admin/AdminOverviewPage"
import { AdminUserDetailPage } from "./features/admin/AdminUserDetailPage"
import { AdminUsersPage } from "./features/admin/AdminUsersPage"

{
  path: "admin",
  element: (
    <RequireAdmin>
      <AdminLayout />
    </RequireAdmin>
  ),
  children: [
    { index: true, element: <AdminOverviewPage /> },
    { path: "users", element: <AdminUsersPage /> },
    { path: "users/:userId", element: <AdminUserDetailPage /> },
    { path: "activity", element: <AdminActivityPage /> },
  ],
},
```

Add the item to `navItems` in `frontend/src/components/layout/nav.ts`, after "Analytics". `AppLayout` already hides `staffOnly` items from everyone else:

```ts
  { to: "/admin", label: "Admin", staffOnly: true },
```

- [ ] **Step 11: Build and check Part A by hand**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

Create a staff user (the prompt asks for email, name and password):

```bash
cd backend && source .venv/bin/activate
python manage.py createsuperuser
```

Manual check:
1. Log in as a normal user. There is no **Admin** link. Typing `/admin` in the address bar redirects to `/`. In the browser dev tools, `fetch` to `/api/admin/overview` with that user's token returns 401.
2. Log out, log in as the staff user. The **Admin** link appears.
3. **Overview** shows platform counts that match what you created, and the 14-day chart.
4. **Users** lists every account with project count, AI calls, AI cost and last activity. Search narrows the list. Clicking a row opens the journey.
5. The **journey page** shows that user's spaces, projects with mastery and scores, recent assessments, recent activity and AI usage by feature. "All activity" opens the activity page pre-filtered to that user.
6. **Activity**: choose a user, then a space, then a project, then an activity type, then a date range. The table narrows each time, the URL query string changes, and reloading the page keeps the filters. "Clear filters" resets them.

- [ ] **Step 12: Commit Part A**

```bash
git add frontend
git commit -m "feat: admin dashboard with overview, users, learning journey and activity"
```

#### Part B — AI usage, evals, jobs, health (needs Task 31)

- [ ] **Step 13: Append the Part B types**

Append to `frontend/src/api/types.ts`:

```ts
// ---- admin (operations) ----
export type AIGroupRow = {
  calls: number
  errors: number
  input_tokens: number
  output_tokens: number
  estimated_cost_usd: number
  average_latency_ms: number | null
}
export type AICallRow = {
  id: string
  created_at: string
  feature: string
  model: string
  status: string
  error_type: string
  latency_ms: number
  retries: number
  input_tokens: number
  output_tokens: number
  trace_id: string
  user_email: string | null
  project_name: string | null
}
export type AdminAIUsage = {
  days: number
  totals: Omit<AIGroupRow, "average_latency_ms"> & { error_rate: number }
  latency: { p50_ms: number | null; p95_ms: number | null; average_ms: number | null }
  by_feature: (AIGroupRow & { feature: string })[]
  by_model: (AIGroupRow & { model: string })[]
  slowest: AICallRow[]
  recent_failures: AICallRow[]
}
export type AdminEvalRun = {
  id: string
  created_at: string
  suite: string
  git_sha: string
  passed: boolean
  metrics: Record<string, unknown>
  case_results: unknown
  case_count: number
}
export type AdminJob = {
  id: string
  type: string
  status: string
  attempts: number
  max_attempts: number
  run_after: string | null
  locked_at: string | null
  last_error: string
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}
export type AdminJobsSummary = { by_status: Record<string, number>; by_type: { type: string; count: number }[] }
export type HealthStatus = "green" | "amber" | "red"
export type AdminHealth = {
  status: HealthStatus
  checked_at: string
  checks: { key: string; label: string; status: HealthStatus; value: string; detail: string }[]
}
```

- [ ] **Step 14: Append the Part B hooks**

Append to `frontend/src/api/admin.ts` (add `useMutation`, `useQueryClient` and the new types to the existing imports):

```ts
export function useAdminAIUsage(days: number) {
  return useQuery({
    queryKey: ["admin", "ai-usage", days],
    queryFn: () => api.get<AdminAIUsage>("/admin/ai-usage", { days }),
    placeholderData: keepPreviousData,
  })
}

export function useAdminEvals() {
  return useQuery({ queryKey: ["admin", "evals"], queryFn: () => api.get<AdminEvalRun[]>("/admin/evals") })
}

export function useAdminJobs(params: { status?: string; type?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ["admin", "jobs", "list", params],
    queryFn: () =>
      api.get<Paginated<AdminJob>>("/admin/jobs", {
        ...params,
        status: params.status || undefined,
        type: params.type || undefined,
      }),
    placeholderData: keepPreviousData,
    refetchInterval: 5000,
  })
}

export function useAdminJobsSummary() {
  return useQuery({
    queryKey: ["admin", "jobs", "summary"],
    queryFn: () => api.get<AdminJobsSummary>("/admin/jobs/summary"),
    refetchInterval: 5000,
  })
}

export function useRetryJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => api.post<AdminJob>(`/admin/jobs/${jobId}/retry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] }),
  })
}

export function useAdminHealth() {
  return useQuery({
    queryKey: ["admin", "health"],
    queryFn: () => api.get<AdminHealth>("/admin/health"),
    refetchInterval: 15000,
  })
}
```

- [ ] **Step 15: Write the AI usage page**

`frontend/src/features/admin/AdminAIUsagePage.tsx`:

```tsx
import { useState } from "react"
import { useAdminAIUsage } from "../../api/admin"
import type { AICallRow, AIGroupRow } from "../../api/types"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { SimpleTable, type Column } from "../../components/shared/SimpleTable"
import { StatTile } from "../../components/shared/StatTile"
import { Badge } from "../../components/ui/Badge"
import { Button } from "../../components/ui/Button"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"
import { usd } from "../analytics/AnalyticsPanels"

const WINDOWS = [1, 7, 30]
const ms = (value: number | null) => (value === null ? "—" : `${Math.round(value)} ms`)

function groupColumns<T extends AIGroupRow>(header: string, name: (row: T) => string): Column<T>[] {
  return [
    { header, cell: name },
    { header: "Calls", align: "right", cell: (row) => row.calls },
    { header: "Failed", align: "right", cell: (row) => row.errors },
    { header: "Avg. latency", align: "right", cell: (row) => ms(row.average_latency_ms) },
    { header: "Tokens in", align: "right", cell: (row) => row.input_tokens.toLocaleString() },
    { header: "Tokens out", align: "right", cell: (row) => row.output_tokens.toLocaleString() },
    { header: "Est. cost", align: "right", cell: (row) => usd(row.estimated_cost_usd) },
  ]
}

const callColumns: Column<AICallRow>[] = [
  { header: "When", cell: (row) => new Date(row.created_at).toLocaleString() },
  { header: "Feature", cell: (row) => row.feature },
  { header: "Model", cell: (row) => <code className="text-xs">{row.model}</code> },
  {
    header: "Result",
    cell: (row) => (row.status === "ok" ? <Badge tone="green">ok</Badge> : <Badge tone="red">{row.error_type || "error"}</Badge>),
  },
  { header: "Latency", align: "right", cell: (row) => ms(row.latency_ms) },
  { header: "Retries", align: "right", cell: (row) => row.retries },
  { header: "User", cell: (row) => row.user_email ?? "—" },
  { header: "Project", cell: (row) => row.project_name ?? "—" },
]

export function AdminAIUsagePage() {
  const [days, setDays] = useState(7)
  const { data, isLoading, error, refetch } = useAdminAIUsage(days)

  if (isLoading) return <Spinner className="mx-auto mt-16" />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {WINDOWS.map((option) => (
          <Button key={option} size="sm" variant={option === days ? "primary" : "secondary"} onClick={() => setDays(option)}>
            {option === 1 ? "24 hours" : `${option} days`}
          </Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="AI calls" value={data.totals.calls} />
        <StatTile label="Error rate" value={`${(data.totals.error_rate * 100).toFixed(1)}%`} hint={`${data.totals.errors} failed`} />
        <StatTile label="Latency p50" value={ms(data.latency.p50_ms)} hint="successful calls" />
        <StatTile label="Latency p95" value={ms(data.latency.p95_ms)} hint="successful calls" />
        <StatTile
          label="Estimated cost"
          value={usd(data.totals.estimated_cost_usd)}
          hint={`${(data.totals.input_tokens + data.totals.output_tokens).toLocaleString()} tokens`}
        />
      </div>
      {data.totals.calls === 0 ? (
        <EmptyState title="No AI calls in this window" />
      ) : (
        <>
          <Card title="By feature">
            <SimpleTable rows={data.by_feature} rowKey={(row) => row.feature} columns={groupColumns("Feature", (row) => row.feature)} />
          </Card>
          <Card title="By model">
            <SimpleTable rows={data.by_model} rowKey={(row) => row.model} columns={groupColumns("Model", (row) => row.model)} />
          </Card>
          <Card title="Slowest calls">
            <SimpleTable rows={data.slowest} rowKey={(row) => row.id} columns={callColumns} />
          </Card>
          <Card title="Most recent failures">
            {data.recent_failures.length === 0 ? (
              <EmptyState title="No failed calls in this window" />
            ) : (
              <SimpleTable rows={data.recent_failures} rowKey={(row) => row.id} columns={callColumns} />
            )}
          </Card>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 16: Write the evals page**

`frontend/src/features/admin/AdminEvalsPage.tsx`:

```tsx
import { useAdminEvals } from "../../api/admin"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { Badge } from "../../components/ui/Badge"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"

function formatMetric(value: unknown) {
  if (typeof value === "number") return value <= 1 ? `${(value * 100).toFixed(1)}%` : String(value)
  return String(value)
}

export function AdminEvalsPage() {
  const { data, isLoading, error, refetch } = useAdminEvals()

  if (isLoading) return <Spinner className="mx-auto mt-16" />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />
  if (data.length === 0)
    return <EmptyState title="No eval runs yet" description="Run `python manage.py run_evals` to record one." />

  return (
    <div className="space-y-3">
      {data.map((run) => (
        <Card
          key={run.id}
          title={`${run.suite} · ${new Date(run.created_at).toLocaleString()}`}
          actions={run.passed ? <Badge tone="green">passed</Badge> : <Badge tone="red">failed</Badge>}
        >
          <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            {Object.entries(run.metrics).map(([name, value]) => (
              <div key={name}>
                <dt className="text-xs uppercase tracking-wide text-gray-500">{name.replaceAll("_", " ")}</dt>
                <dd className="font-medium tabular-nums text-gray-900">{formatMetric(value)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-gray-500">
            {run.case_count} cases · commit <code>{run.git_sha || "unknown"}</code>
          </p>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-indigo-700">Case results</summary>
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-gray-50 p-2">{JSON.stringify(run.case_results, null, 2)}</pre>
          </details>
        </Card>
      ))}
    </div>
  )
}
```

- [ ] **Step 17: Write the jobs page**

`frontend/src/features/admin/AdminJobsPage.tsx`:

```tsx
import { useState } from "react"
import { useAdminJobs, useAdminJobsSummary, useRetryJob } from "../../api/admin"
import { EmptyState } from "../../components/shared/EmptyState"
import { ErrorState } from "../../components/shared/ErrorState"
import { Pager } from "../../components/shared/Pager"
import { SimpleTable } from "../../components/shared/SimpleTable"
import { StatTile } from "../../components/shared/StatTile"
import { StatusBadge } from "../../components/shared/StatusBadge"
import { Button } from "../../components/ui/Button"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"

const LIMIT = 25
const STATUSES = ["queued", "running", "succeeded", "failed"]
const selectClass = "rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"

export function AdminJobsPage() {
  const [status, setStatus] = useState("")
  const [type, setType] = useState("")
  const [offset, setOffset] = useState(0)
  const summary = useAdminJobsSummary()
  const jobs = useAdminJobs({ status, type, limit: LIMIT, offset })
  const retry = useRetryJob()

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {STATUSES.map((name) => (
          <StatTile key={name} label={name} value={summary.data?.by_status[name] ?? "—"} />
        ))}
      </div>
      <Card title="Background jobs">
        <div className="mb-3 flex flex-wrap gap-2">
          <select
            className={selectClass}
            value={status}
            onChange={(event) => {
              setStatus(event.target.value)
              setOffset(0)
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={type}
            onChange={(event) => {
              setType(event.target.value)
              setOffset(0)
            }}
          >
            <option value="">All types</option>
            {(summary.data?.by_type ?? []).map((row) => (
              <option key={row.type} value={row.type}>
                {row.type} ({row.count})
              </option>
            ))}
          </select>
        </div>
        {retry.error ? <ErrorState error={retry.error} /> : null}
        {jobs.isLoading ? (
          <Spinner className="mx-auto my-8" />
        ) : jobs.error || !jobs.data ? (
          <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} />
        ) : jobs.data.items.length === 0 ? (
          <EmptyState title="No jobs match" />
        ) : (
          <>
            <SimpleTable
              rows={jobs.data.items}
              rowKey={(row) => row.id}
              columns={[
                { header: "Created", cell: (row) => new Date(row.created_at).toLocaleString() },
                { header: "Type", cell: (row) => <code className="text-xs">{row.type}</code> },
                { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
                { header: "Attempts", align: "right", cell: (row) => `${row.attempts}/${row.max_attempts}` },
                {
                  header: "Last error",
                  cell: (row) => (
                    <span className="block max-w-sm truncate text-xs text-red-700" title={row.last_error}>
                      {row.last_error || "—"}
                    </span>
                  ),
                },
                {
                  header: "",
                  align: "right",
                  cell: (row) =>
                    row.status === "failed" ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={retry.isPending && retry.variables === row.id}
                        onClick={() => retry.mutate(row.id)}
                      >
                        Retry
                      </Button>
                    ) : null,
                },
              ]}
            />
            <Pager count={jobs.data.count} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </div>
  )
}
```

- [ ] **Step 18: Write the health page**

`frontend/src/features/admin/AdminHealthPage.tsx`:

```tsx
import { useAdminHealth } from "../../api/admin"
import type { HealthStatus } from "../../api/types"
import { ErrorState } from "../../components/shared/ErrorState"
import { Card } from "../../components/ui/Card"
import { Spinner } from "../../components/ui/Spinner"

const DOT: Record<HealthStatus, string> = { green: "bg-green-500", amber: "bg-amber-500", red: "bg-red-500" }
const HEADLINE: Record<HealthStatus, string> = {
  green: "All systems normal",
  amber: "Degraded — needs a look",
  red: "Problem — act now",
}

export function AdminHealthPage() {
  const { data, isLoading, error, refetch } = useAdminHealth()

  if (isLoading) return <Spinner className="mx-auto mt-16" />
  // If the API itself is down, this error state is the health signal.
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-3">
          <span className={`h-4 w-4 rounded-full ${DOT[data.status]}`} aria-hidden />
          <div>
            <div className="text-lg font-semibold text-gray-900">{HEADLINE[data.status]}</div>
            <div className="text-xs text-gray-500">
              Checked {new Date(data.checked_at).toLocaleTimeString()} · refreshes every 15 seconds
            </div>
          </div>
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data.checks.map((check) => (
          <Card key={check.key}>
            <div className="flex items-start gap-3">
              <span className={`mt-1.5 h-3 w-3 shrink-0 rounded-full ${DOT[check.status]}`} aria-label={check.status} />
              <div className="min-w-0">
                <div className="text-sm text-gray-600">{check.label}</div>
                <div className="truncate font-medium text-gray-900" title={check.value}>
                  {check.value}
                </div>
                {check.detail ? <div className="mt-1 text-xs text-gray-500">{check.detail}</div> : null}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 19: Register the Part B navigation and routes**

Append to the `adminNav` array in `frontend/src/features/admin/adminNav.ts`:

```ts
  { path: "ai-usage", label: "AI usage" },
  { path: "evals", label: "Evals" },
  { path: "jobs", label: "Jobs" },
  { path: "health", label: "Health" },
```

In `frontend/src/routes.tsx` add the imports and append to the `admin` route's `children`:

```tsx
import { AdminAIUsagePage } from "./features/admin/AdminAIUsagePage"
import { AdminEvalsPage } from "./features/admin/AdminEvalsPage"
import { AdminHealthPage } from "./features/admin/AdminHealthPage"
import { AdminJobsPage } from "./features/admin/AdminJobsPage"

    { path: "ai-usage", element: <AdminAIUsagePage /> },
    { path: "evals", element: <AdminEvalsPage /> },
    { path: "jobs", element: <AdminJobsPage /> },
    { path: "health", element: <AdminHealthPage /> },
```

- [ ] **Step 20: Build and check Part B by hand**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

Manual check, logged in as the staff user:
1. **AI usage**: tiles show calls, error rate, p50 and p95. Switching between 24 hours, 7 days and 30 days changes the numbers. "By feature" lists `tutor`, `embed`, `concepts`, `quiz_gen`, `grading`. "Slowest calls" is sorted by latency, and each row names the user and project.
2. **Evals**: before any run, the empty state names the command. After Phase 7's `python manage.py run_evals`, each run shows its metrics and a pass or fail badge.
3. **Jobs**: stop the worker, upload a PDF, and watch a `queued` row appear within 5 seconds. Start the worker and watch it turn `succeeded`.
4. **Retry**: force a failure by setting `GEMINI_API_KEY` to a wrong value, restarting the worker and uploading a PDF. After the retries run out the job shows `failed` with its error. Restore the key, restart the worker, click **Retry**: the row goes to `queued`, then `succeeded`.
5. **Health**: all green on a quiet system. With the worker stopped and a job queued for more than 5 minutes, "Job queue" turns amber and the headline changes.

- [ ] **Step 21: Commit Part B**

```bash
git add frontend
git commit -m "feat: admin pages for AI usage, evals, jobs and system health"
```

---

### Phase 6 wrap-up

- [ ] **Step 1: Run everything**

```bash
cd backend && source .venv/bin/activate && pytest -q
cd ../frontend && npm run build
```

Expected: all backend tests pass, and the frontend builds with no TypeScript errors.

- [ ] **Step 2: Update the prompt log**

Append to `docs/PROMPTS.md` the prompts that materially shaped this phase, under the matching headings: **backend** (analytics aggregation, admin queries, the percentile decision), **database** (grouped queries and the join-multiplication rule), **frontend** (analytics and admin pages), **testing** (isolation and query-count tests), **debugging** (anything that needed a fix).

- [ ] **Step 3: Commit**

```bash
git add docs/PROMPTS.md
git commit -m "docs: prompt log for analytics and admin phase"
```

