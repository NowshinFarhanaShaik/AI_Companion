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
