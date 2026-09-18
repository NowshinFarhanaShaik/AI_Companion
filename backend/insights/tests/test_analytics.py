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


def test_project_mastery_bands_count_only_practised_concepts(api, user, project):
    make_concept(project, "A", mastery=0.2, evidence_count=1)
    make_concept(project, "B", mastery=0.5, evidence_count=2)
    make_concept(project, "C", mastery=0.9, evidence_count=3)
    make_concept(project, "D", mastery=0.3)  # never answered: only the starting estimate

    mastery = api(user).get(url(project)).json()["mastery"]

    assert (mastery["low"], mastery["medium"], mastery["high"], mastery["unpractised"]) == (1, 1, 1, 1)
    assert mastery["concepts"] == 4
    assert mastery["average"] == pytest.approx(0.475)


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
