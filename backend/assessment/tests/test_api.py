import pytest

from assessment.models import Question, QuizSession
from common.testing import make_chunk, make_concept, make_material

pytestmark = pytest.mark.django_db

MCQ = {
    "body": "Which process stores light energy as glucose?",
    "options": ["Photosynthesis", "Respiration", "Fermentation", "Transpiration"],
    "correct_option": 0,
    "explanation": "Photosynthesis stores light energy as glucose.",
}


@pytest.fixture
def ready_project(project):
    material = make_material(project, status="ready")
    chunk = make_chunk(project, material, "Photosynthesis stores light energy as glucose.", page=1)
    make_concept(project, "Photosynthesis", chunks=[chunk], mastery=0.3)
    return project


def start(client, project, count=2):
    return client.post(f"/api/projects/{project.id}/quiz-sessions", {"target_question_count": count})


def test_full_quiz_flow(api, user, ready_project, fake_ai):
    client = api(user)

    response = start(client, ready_project)
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "active"
    assert session["questions"] == []
    assert session["summary"] is None

    fake_ai.queue_structured(MCQ)
    response = client.post(f"/api/quiz-sessions/{session['id']}/next")
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is False
    question = body["question"]
    assert question["concept_name"] == "Photosynthesis"
    assert question["answered"] is False
    assert len(question["options"]) == 4

    stored = Question.objects.get(id=question["id"])
    response = client.post(f"/api/questions/{question['id']}/answer", {"selected_option": stored.correct_option})
    assert response.status_code == 200
    answered = response.json()
    assert answered["session_completed"] is False
    assert answered["question"]["answered"] is True
    assert answered["question"]["attempt"]["score"] == 1.0
    assert answered["question"]["correct_option"] == stored.correct_option
    assert answered["question"]["explanation"] == MCQ["explanation"]

    fake_ai.queue_structured({**MCQ, "body": "A second question about photosynthesis?"})
    second = client.post(f"/api/quiz-sessions/{session['id']}/next").json()["question"]
    response = client.post(f"/api/questions/{second['id']}/answer", {"selected_option": 0})
    assert response.json()["session_completed"] is True

    done = client.post(f"/api/quiz-sessions/{session['id']}/next").json()
    assert done == {"question": None, "completed": True}

    detail = client.get(f"/api/quiz-sessions/{session['id']}").json()
    assert detail["status"] == "completed"
    assert detail["answered_count"] == 2
    assert len(detail["questions"]) == 2
    assert detail["summary"]["answered_count"] == 2
    assert 0.0 <= detail["summary"]["average_score"] <= 1.0
    assert detail["summary"]["by_concept"][0]["concept_name"] == "Photosynthesis"
    assert detail["summary"]["by_concept"][0]["question_count"] == 2


def test_an_unanswered_question_never_reveals_the_answer(api, user, ready_project, fake_ai):
    client = api(user)
    session = start(client, ready_project).json()
    fake_ai.queue_structured(MCQ)
    question = client.post(f"/api/quiz-sessions/{session['id']}/next").json()["question"]

    assert "rubric" not in question
    assert question["correct_option"] is None
    assert question["explanation"] is None
    assert question["key_points"] is None
    assert question["attempt"] is None

    listed = client.get(f"/api/quiz-sessions/{session['id']}").json()["questions"][0]
    assert "rubric" not in listed
    assert listed["correct_option"] is None
    assert listed["explanation"] is None


def test_an_open_question_reveals_key_points_only_after_answering(api, user, ready_project, fake_ai):
    client = api(user)
    session = QuizSession.objects.create(project=ready_project, target_question_count=1)
    concept = ready_project.concepts.get()
    question = Question.objects.create(
        project=ready_project, session=session, concept=concept, type="open", difficulty=3,
        body="Explain photosynthesis.", rubric={"key_points": ["light", "glucose"]},
    )
    assert client.get(f"/api/quiz-sessions/{session.id}").json()["questions"][0]["key_points"] is None

    fake_ai.queue_structured({"score": 0.5, "understood": ["light"], "missing": ["glucose"],
                              "misconceptions": [], "feedback": "Half way there."})
    response = client.post(f"/api/questions/{question.id}/answer", {"answer_text": "Plants use light."})

    assert response.status_code == 200
    body = response.json()
    assert body["session_completed"] is True
    assert body["question"]["key_points"] == ["light", "glucose"]
    assert body["question"]["attempt"]["feedback"]["missing"] == ["glucose"]
    assert body["question"]["attempt"]["answer_text"] == "Plants use light."


def test_starting_without_concepts_returns_400(api, user, project):
    response = start(api(user), project)
    assert response.status_code == 400
    assert response.json()["code"] == "no_concepts"


def test_answering_twice_returns_409(api, user, ready_project, fake_ai):
    client = api(user)
    session = start(client, ready_project).json()
    fake_ai.queue_structured(MCQ)
    question = client.post(f"/api/quiz-sessions/{session['id']}/next").json()["question"]
    client.post(f"/api/questions/{question['id']}/answer", {"selected_option": 0})
    response = client.post(f"/api/questions/{question['id']}/answer", {"selected_option": 1})
    assert response.status_code == 409
    assert response.json()["code"] == "already_answered"


def test_target_question_count_is_validated(api, user, ready_project):
    assert start(api(user), ready_project, count=0).status_code == 422
    assert start(api(user), ready_project, count=11).status_code == 422


def test_generation_failure_returns_502_with_a_code(api, user, ready_project, fake_ai):
    client = api(user)
    session = start(client, ready_project).json()
    bad = {**MCQ, "options": ["only", "three", "options"]}
    fake_ai.queue_structured(bad)
    fake_ai.queue_structured(bad)
    response = client.post(f"/api/quiz-sessions/{session['id']}/next")
    assert response.status_code == 502
    assert response.json()["code"] == "quiz_generation_failed"


def test_other_users_get_404_everywhere(api, user, other_user, ready_project, fake_ai):
    owner = api(user)
    session = start(owner, ready_project).json()
    fake_ai.queue_structured(MCQ)
    question = owner.post(f"/api/quiz-sessions/{session['id']}/next").json()["question"]

    intruder = api(other_user)
    assert start(intruder, ready_project).status_code == 404
    assert intruder.get(f"/api/quiz-sessions/{session['id']}").status_code == 404
    assert intruder.post(f"/api/quiz-sessions/{session['id']}/next").status_code == 404
    assert intruder.post(f"/api/questions/{question['id']}/answer", {"selected_option": 0}).status_code == 404
    assert Question.objects.get(id=question["id"]).session.questions.filter(attempt__isnull=False).count() == 0


def test_quiz_endpoints_require_authentication(client, ready_project):
    response = client.post(f"/api/projects/{ready_project.id}/quiz-sessions", {}, content_type="application/json")
    assert response.status_code == 401
