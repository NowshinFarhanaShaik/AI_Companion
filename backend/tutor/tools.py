"""The only way the Tutor model can act on the application.

Every tool has a Pydantic argument schema that forbids unknown fields, and the user and Project are bound by
the server from the request. The model never supplies an ID, so it cannot reach another Project.
"""
import logging
from dataclasses import dataclass, field
from typing import Literal

from django.apps import apps
from django.conf import settings
from django.db.models import Avg
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai.client import tool_turn
from ai.types import AIError, ToolSpec
from common.prompt_safety import escape_data
from materials.models import Material
from materials.retrieval import RetrievedChunk, search_chunks
from tutor.prompts import TOOL_SYSTEM_PROMPT, build_tool_prompt
from workspace.models import Project

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 3
MAX_NOTES_PER_REQUEST = 2
SEARCH_K = 4
RESULT_TEXT_CHARS = 1200


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchMaterialsArgs(_Args):
    query: str = Field(min_length=2, max_length=300, description="What to look for in the learner's materials")


class NoArgs(_Args):
    pass


class SaveLearningNoteArgs(_Args):
    # "goal" is deliberately absent: the model may record observations, not rewrite the learner's goal.
    kind: Literal["preference", "strength", "weakness", "note"]
    content: str = Field(min_length=3, max_length=500, description="One sentence, in the third person")


@dataclass
class ToolState:
    found: dict[str, RetrievedChunk] = field(default_factory=dict)
    notes_saved: int = 0
    log: list[dict] = field(default_factory=list)


def _search_materials(args, *, user, project, state) -> dict:
    results = []
    for retrieved in search_chunks(project=project, query=args.query, k=SEARCH_K, user=user):
        if retrieved.similarity < settings.TUTOR_MIN_SIMILARITY:
            continue
        chunk = retrieved.chunk
        state.found.setdefault(str(chunk.id), retrieved)
        results.append({
            "chunk_id": str(chunk.id),
            "source": chunk.material.title,
            "page": chunk.page_number,
            "similarity": round(retrieved.similarity, 3),
            "text": escape_data(chunk.text[:RESULT_TEXT_CHARS]),
        })
    return {"results": results}


def _masteries(user, project):
    from learning.models import ConceptMastery

    return ConceptMastery.objects.for_user(user).filter(project=project)


def _get_weak_concepts(args, *, user, project, state) -> dict:
    if not apps.is_installed("learning"):
        return {"concepts": []}
    weakest = _masteries(user, project).select_related("concept").order_by("score", "concept__name")[:5]
    return {
        "concepts": [
            {"name": m.concept.name, "mastery": round(float(m.score), 2), "evidence_count": m.evidence_count}
            for m in weakest
        ]
    }


def _get_progress(args, *, user, project, state) -> dict:
    materials = Material.objects.for_user(user).filter(project=project)
    progress = {
        "ready_materials": materials.filter(status=Material.Status.READY).count(),
        "concept_count": 0,
        "average_mastery": None,
        "recent_quizzes": [],
    }
    if apps.is_installed("learning"):
        masteries = _masteries(user, project)
        average = masteries.aggregate(value=Avg("score"))["value"]
        progress["concept_count"] = masteries.count()
        progress["average_mastery"] = round(float(average), 2) if average is not None else None
    if apps.is_installed("assessment"):
        from assessment.models import QuizSession

        sessions = (
            QuizSession.objects.for_user(user)
            .filter(project=project, status=QuizSession.Status.COMPLETED)
            .annotate(average_score=Avg("questions__attempt__score"))
            .order_by("-completed_at")[:3]
        )
        progress["recent_quizzes"] = [
            {
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "average_score": round(float(session.average_score), 2) if session.average_score is not None else None,
            }
            for session in sessions
        ]
    return progress


def _save_learning_note(args, *, user, project, state) -> dict:
    if state.notes_saved >= MAX_NOTES_PER_REQUEST:
        return {"error": "note limit reached for this request"}
    try:
        from learning.memory import record_memory
    except ImportError:
        return {"error": "learning notes are not available"}
    record_memory(project=project, kind=args.kind, content=args.content, salience=0.5)
    state.notes_saved += 1
    return {"saved": True}


_TOOLS = {
    "search_materials": (
        "Search the learner's uploaded materials in the current project for more evidence.",
        SearchMaterialsArgs, _search_materials,
    ),
    "get_weak_concepts": (
        "List the concepts in the current project where the learner's mastery is lowest.",
        NoArgs, _get_weak_concepts,
    ),
    "get_progress": (
        "Summarise the learner's progress in the current project: materials, mastery and recent quizzes.",
        NoArgs, _get_progress,
    ),
    "save_learning_note": (
        "Remember a lasting preference, strength or weakness that the learner stated themselves.",
        SaveLearningNoteArgs, _save_learning_note,
    ),
}
TOOLS = [ToolSpec(name=name, description=description, args_schema=schema) for name, (description, schema, _) in _TOOLS.items()]


def execute_tool(name: str, args, *, user, project, state: ToolState | None = None) -> dict:
    """Runs one tool call. Failures come back as {"error": ...} results for the model, never as exceptions."""
    if name not in _TOOLS:
        return {"error": f"unknown tool '{name}'"}
    if not Project.objects.for_user(user).filter(id=project.id).exists():
        return {"error": "project not found"}
    _, schema, handler = _TOOLS[name]
    try:
        parsed = schema.model_validate(args)
    except ValidationError as exc:
        return {"error": "invalid arguments", "details": [error["msg"] for error in exc.errors()]}
    return handler(parsed, user=user, project=project, state=state or ToolState())


def run_tool_rounds(*, user, project, ctx, evidence, trace_id) -> ToolState:
    """Lets the model gather more evidence or learner state before the final answer."""
    state = ToolState()
    if not settings.TUTOR_TOOLS_ENABLED:
        return state
    transcript = [{"role": "user", "text": build_tool_prompt(ctx, evidence)}]
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            turn = tool_turn(
                feature="tutor", system=TOOL_SYSTEM_PROMPT, transcript=transcript, tools=TOOLS,
                user=user, project=project, trace_id=trace_id,
            )
            if not turn.tool_calls:
                break
            transcript.append({
                "role": "model",
                "text": turn.text,
                "tool_calls": [{"name": call.name, "args": call.args} for call in turn.tool_calls],
                "raw": turn.raw,
            })
            for call in turn.tool_calls:
                result = execute_tool(call.name, call.args, user=user, project=project, state=state)
                state.log.append({"name": call.name, "args": call.args, "ok": "error" not in result})
                transcript.append({"role": "tool", "name": call.name, "result": result})
    except AIError as exc:
        # Tools only enrich the answer, so the Tutor carries on with the evidence it already has.
        logger.warning("tutor tool phase failed trace_id=%s project=%s error=%r", trace_id, project.id, exc)
    return state
