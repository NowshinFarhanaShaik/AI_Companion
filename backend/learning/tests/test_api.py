import pytest
from pytest import approx

from common.testing import make_chunk, make_concept, make_material
from events.services import emit
from learning.dashboards import weighted_progress
from learning.models import Recommendation
from learning.recommendations import generate_recommendation
from learning.tests.factories import make_attempt, make_session, make_snapshot
from workspace.services import touch_project

pytestmark = pytest.mark.django_db


def _weak_project(project):
    material = make_material(project, title="Biology Notes", status="ready")
    chunk = make_chunk(project, material, "Chloroplast text", page=4)
    concept = make_concept(project, "Chloroplast", chunks=(chunk,), importance=5, mastery=0.35, evidence_count=3)
    make_snapshot(project, concept, 0.45, days_ago=3, evidence_count=2)
    make_snapshot(project, concept, 0.35, days_ago=0, evidence_count=3)
    return concept


# ---- progress number -----------------------------------------------------------------------------

def test_weighted_progress_uses_importance_as_the_weight():
    # (0.8 * 5 + 0.2 * 1) / (5 + 1) = 0.7
    assert weighted_progress([(0.8, 5), (0.2, 1)]) == approx(0.7)


def test_weighted_progress_is_zero_without_concepts():
    assert weighted_progress([]) == 0.0


# ---- mastery and growth --------------------------------------------------------------------------

def test_mastery_lists_concepts_strongest_first(api, user, project):
    make_concept(project, "Weak", mastery=0.2, evidence_count=1)
    make_concept(project, "Strong", mastery=0.9, evidence_count=4, importance=5)

    response = api(user).get(f"/api/projects/{project.id}/mastery")

    assert response.status_code == 200
    body = response.json()
    assert [row["name"] for row in body] == ["Strong", "Weak"]
    assert body[0]["score"] == approx(0.9)
    assert body[0]["importance"] == 5
    assert body[0]["evidence_count"] == 4


def test_growth_returns_trends_and_series(api, user, project):
    concept = _weak_project(project)

    response = api(user).get(f"/api/projects/{project.id}/growth")

    assert response.status_code == 200
    body = response.json()
    [trend] = body["trends"]
    assert trend["concept_id"] == str(concept.id)
    assert trend["label"] == "needs_attention"
    assert trend["delta"] == approx(-0.10)
    [series] = body["series"]
    assert series["name"] == "Chloroplast"
    assert [round(p["score"], 2) for p in series["points"]] == [0.45, 0.35]


# ---- recommendations -----------------------------------------------------------------------------

def test_recommendations_list_and_complete(api, user, project):
    rec = generate_recommendation(project)          # upload_material
    client = api(user)

    listed = client.get(f"/api/projects/{project.id}/recommendations", status="active")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    item = listed.json()["items"][0]
    assert item["id"] == str(rec.id)
    assert item["action_type"] == "upload_material"
    assert item["project_id"] == str(project.id)
    assert item["concept_id"] is None

    done = client.post(f"/api/recommendations/{rec.id}/complete")
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert client.get(f"/api/projects/{project.id}/recommendations", status="active").json()["count"] == 0
    assert Recommendation.objects.get(id=rec.id).status == "done"


# ---- project dashboard ---------------------------------------------------------------------------

def test_project_dashboard_summarises_the_learning_state(api, user, project):
    concept = _weak_project(project)
    make_concept(project, "Stomata", importance=1, mastery=0.85, evidence_count=2)
    make_material(project, title="Queued", status="queued")
    session = make_session(project, status="completed", target=2)
    make_attempt(project, concept, score=1.0, session=session)
    make_attempt(project, concept, score=0.5, session=session)
    rec = generate_recommendation(project)
    emit(type="project.created", user=user, project=project, payload={}, idempotency_key=f"pc:{project.id}")

    response = api(user).get(f"/api/projects/{project.id}/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == str(project.id)
    # (0.35 * 5 + 0.85 * 1) / 6
    assert body["overall_progress"] == approx((0.35 * 5 + 0.85) / 6, abs=1e-4)
    assert body["concept_count"] == 2
    assert body["top_concepts"][0]["name"] == "Stomata"
    assert [t["name"] for t in body["attention_concepts"]] == ["Chloroplast"]
    assert body["material_counts"] == {"queued": 1, "processing": 0, "ready": 1, "failed": 0}
    assert body["latest_quiz"]["session_id"] == str(session.id)
    assert body["latest_quiz"]["question_count"] == 2
    assert body["latest_quiz"]["average_score"] == approx(0.75)
    assert body["recommendation"]["id"] == str(rec.id)
    assert "project.created" in [e["type"] for e in body["recent_activity"]]


def test_empty_project_dashboard(api, user, project):
    body = api(user).get(f"/api/projects/{project.id}/dashboard").json()

    assert body["overall_progress"] == 0.0
    assert body["concept_count"] == 0
    assert body["top_concepts"] == []
    assert body["latest_quiz"] is None
    assert body["recommendation"] is None


def test_project_activity_is_paginated_and_newest_first(api, user, project):
    for i in range(3):
        emit(type="tutor.message_sent", user=user, project=project, payload={"n": i}, idempotency_key=f"m:{i}")

    response = api(user).get(f"/api/projects/{project.id}/activity", limit=2)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4  # the three messages plus project.created
    assert [e["payload"]["n"] for e in body["items"]] == [2, 1]


# ---- space dashboard and home ----------------------------------------------------------------------

def test_space_dashboard_aggregates_its_projects(api, user, space, project):
    _weak_project(project)

    response = api(user).get(f"/api/spaces/{space.id}/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["space_id"] == str(space.id)
    assert body["project_count"] == 1
    assert body["overall_progress"] == approx(0.35)
    [summary] = body["projects"]
    assert summary["id"] == str(project.id)
    assert summary["attention_count"] == 1
    assert summary["concept_count"] == 1


def test_home_shows_only_the_users_own_learning(api, user, project, other_project):
    _weak_project(project)
    make_concept(other_project, "Foreign", mastery=0.1, evidence_count=3)
    touch_project(project)
    rec = generate_recommendation(project)
    generate_recommendation(other_project)

    response = api(user).get("/api/home")

    assert response.status_code == 200
    body = response.json()
    assert body["continue_learning"]["id"] == str(project.id)
    assert [p["id"] for p in body["recent_projects"]] == [str(project.id)]
    assert body["overall_progress"] == approx(0.35)
    assert [a["concept_name"] for a in body["attention_areas"]] == ["Chloroplast"]
    assert body["attention_areas"][0]["project_id"] == str(project.id)
    assert body["next_action"]["id"] == str(rec.id)


def test_home_for_a_new_user_is_empty(api, other_user):
    # other_user owns other_project only when that fixture is requested; here they own nothing.
    body = api(other_user).get("/api/home").json()

    assert body["continue_learning"] is None
    assert body["recent_projects"] == []
    assert body["attention_areas"] == []
    assert body["next_action"] is None
    assert body["overall_progress"] == 0.0


# ---- isolation and auth ----------------------------------------------------------------------------

@pytest.mark.parametrize("suffix", ["mastery", "growth", "recommendations", "dashboard", "activity"])
def test_another_users_project_is_a_404(api, user, other_project, suffix):
    response = api(user).get(f"/api/projects/{other_project.id}/{suffix}")
    assert response.status_code == 404


def test_another_users_space_dashboard_is_a_404(api, user, other_space):
    assert api(user).get(f"/api/spaces/{other_space.id}/dashboard").status_code == 404


def test_another_users_recommendation_cannot_be_completed(api, user, other_project):
    rec = generate_recommendation(other_project)

    response = api(user).post(f"/api/recommendations/{rec.id}/complete")

    assert response.status_code == 404
    assert Recommendation.objects.get(id=rec.id).status == "active"


@pytest.mark.parametrize("path", ["/api/home", "/api/projects/{pid}/dashboard", "/api/projects/{pid}/mastery"])
def test_endpoints_require_a_token(client, project, path):
    response = client.get(path.format(pid=project.id))
    assert response.status_code == 401
