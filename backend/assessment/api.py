from uuid import UUID

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from ninja import Router, Status

from assessment import services
from assessment.models import Question, QuizSession
from assessment.schemas import AnswerIn, AnswerOut, NextOut, SessionOut, StartSessionIn
from common.scoping import get_owned_or_404
from common.throttling import ScopedThrottle
from workspace.models import Project

router = Router(tags=["quiz"])

_QUESTIONS = Question.objects.select_related("concept", "attempt").order_by("created_at")


def _session(user, session_id) -> QuizSession:
    sessions = QuizSession.objects.for_user(user).prefetch_related(Prefetch("questions", queryset=_QUESTIONS))
    return get_object_or_404(sessions, id=session_id)


@router.post("/projects/{uuid:project_id}/quiz-sessions", response={201: SessionOut})
def start_quiz_session(request, project_id: UUID, data: StartSessionIn):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    session = services.start_session(user=request.auth, project=project, target_question_count=data.target_question_count)
    return Status(201, _session(request.auth, session.id))


@router.get("/quiz-sessions/{uuid:session_id}", response=SessionOut)
def get_quiz_session(request, session_id: UUID):
    return _session(request.auth, session_id)


@router.post("/quiz-sessions/{uuid:session_id}/next", response=NextOut, throttle=ScopedThrottle("quiz"))
def next_quiz_question(request, session_id: UUID):
    session = get_owned_or_404(QuizSession, request.auth, id=session_id)
    question = services.next_question(user=request.auth, session=session)
    return {"question": question, "completed": question is None}


@router.post("/questions/{uuid:question_id}/answer", response=AnswerOut, throttle=ScopedThrottle("quiz"))
def answer_question(request, question_id: UUID, data: AnswerIn):
    question = get_owned_or_404(Question, request.auth, id=question_id)
    services.submit_answer(
        user=request.auth, question=question, selected_option=data.selected_option, answer_text=data.answer_text
    )
    question = _QUESTIONS.select_related("session").get(id=question_id)
    return {"question": question, "session_completed": question.session.status == QuizSession.Status.COMPLETED}
