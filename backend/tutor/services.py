import logging
import uuid
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction

from ai.client import generate_structured
from ai.types import AIError
from common.errors import ServiceError
from common.scoping import get_owned_or_404
from events.services import emit, enqueue
from materials.models import Chunk
from tutor.context import compose_context
from tutor.models import Citation, Conversation, Message
from tutor.prompts import SYSTEM_PROMPT, build_prompt
from tutor.schemas import TutorAnswer
from tutor.tools import run_tool_rounds
from workspace.models import Project
from workspace.services import touch_project

logger = logging.getLogger(__name__)

SUMMARY_EVERY = 10
SNIPPET_CHARS = 240
TITLE_CHARS = 60
MAX_EVIDENCE = 10

REFUSAL_TEXT = {
    "no_relevant_material": (
        "I couldn't find anything in this project's materials that covers that question, "
        "so I won't guess. Try rephrasing it, or upload material that covers this topic."
    ),
    "model_insufficient_evidence": (
        "Your materials touch on this topic but don't contain enough to answer reliably. "
        "Upload material that covers it, or ask about something in your current documents."
    ),
    "no_valid_citation": (
        "I couldn't support an answer to that with a passage from your materials, "
        "so I'd rather not answer. Try rephrasing the question or adding material on this topic."
    ),
}


@dataclass
class Reply:
    content: str
    grounded: bool = False
    refusal_reason: str = ""
    cited_chunks: list[Chunk] = field(default_factory=list)


def _refusal(reason: str, content: str = "") -> Reply:
    return Reply(content=content or REFUSAL_TEXT[reason], refusal_reason=reason)


def create_conversation(*, user, project, title="") -> Conversation:
    project = get_owned_or_404(Project, user, id=project.id)
    return Conversation.objects.create(project=project, title=title.strip()[:200])


def _generate(*, user, project, ctx, evidence, trace_id) -> Reply:
    answer = generate_structured(
        feature="tutor", tier="strong", schema=TutorAnswer, system=SYSTEM_PROMPT,
        prompt=build_prompt(ctx, evidence), user=user, project=project, trace_id=trace_id,
        retrieved_chunk_ids=[str(retrieved.chunk.id) for retrieved in evidence],
    )
    if not answer.grounded:
        return _refusal("model_insufficient_evidence", answer.answer.strip())

    # A model can cite a source it was never shown, so only chunks from the evidence set count.
    shown = {str(retrieved.chunk.id): retrieved.chunk for retrieved in evidence}
    cited = list(dict.fromkeys(cited_id for cited_id in answer.cited_chunk_ids if cited_id in shown))
    dropped = [cited_id for cited_id in answer.cited_chunk_ids if cited_id not in shown]
    if dropped:
        logger.warning("tutor citation mismatch trace_id=%s project=%s dropped=%s", trace_id, project.id, dropped)
    if not cited:
        return _refusal("no_valid_citation")

    content = answer.answer.strip()
    if answer.follow_up:
        content = f"{content}\n\n{answer.follow_up.strip()}"
    return Reply(content=content, grounded=True, cited_chunks=[shown[cited_id] for cited_id in cited])


def _save_exchange(*, user, conversation, text: str, reply: Reply) -> Message:
    project = conversation.project
    with transaction.atomic():
        user_message = Message.objects.create(
            conversation=conversation, project=project, role=Message.Role.USER, content=text
        )
        assistant = Message.objects.create(
            conversation=conversation, project=project, role=Message.Role.ASSISTANT, content=reply.content,
            grounded=reply.grounded, refusal_reason=reply.refusal_reason,
        )
        Citation.objects.bulk_create(
            Citation(
                message=assistant, chunk=chunk, material_id=chunk.material_id,
                page_number=chunk.page_number, snippet=chunk.text[:SNIPPET_CHARS],
            )
            for chunk in reply.cited_chunks
        )
        conversation.title = conversation.title or text[:TITLE_CHARS]
        conversation.save(update_fields=["title", "updated_at"])
        touch_project(project)
        emit(
            type="tutor.message_sent", user=user, project=project,
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(assistant.id),
                "grounded": reply.grounded,
                "refusal_reason": reply.refusal_reason,
                "citation_count": len(reply.cited_chunks),
            },
            idempotency_key=f"tutor-message:{user_message.id}",
        )
        message_count = conversation.messages.count()
        if message_count % SUMMARY_EVERY == 0:
            enqueue(
                "summarize_conversation",
                {"user_id": str(user.id), "project_id": str(project.id), "conversation_id": str(conversation.id)},
                idempotency_key=f"summarize:{conversation.id}:{message_count}",
            )
    return assistant


def answer_question(*, user, conversation, text: str) -> Message:
    text = (text or "").strip()
    if not text:
        raise ServiceError("Message cannot be empty.", status=400, code="empty_message")
    conversation = get_owned_or_404(Conversation, user, id=conversation.id)
    project = conversation.project
    trace_id = uuid.uuid4().hex

    # AI calls stay outside the transaction, so a failed call still leaves its AICallLog row.
    try:
        ctx = compose_context(user=user, conversation=conversation, question=text)
        evidence = [retrieved for retrieved in ctx.chunks if retrieved.similarity >= settings.TUTOR_MIN_SIMILARITY]
        if not evidence:
            # First evidence check: nothing relevant, so no generation model is called at all.
            reply = _refusal("no_relevant_material")
        else:
            found = run_tool_rounds(user=user, project=project, ctx=ctx, evidence=evidence, trace_id=trace_id).found
            seen = {str(retrieved.chunk.id) for retrieved in evidence}
            evidence = (evidence + [r for chunk_id, r in found.items() if chunk_id not in seen])[:MAX_EVIDENCE]
            reply = _generate(user=user, project=project, ctx=ctx, evidence=evidence, trace_id=trace_id)
    except AIError as exc:
        logger.warning("tutor ai failure trace_id=%s project=%s error=%r", trace_id, project.id, exc)
        raise ServiceError(
            "The AI service is unavailable right now. Please try again in a moment.", status=503, code="ai_unavailable"
        ) from exc

    assistant = _save_exchange(user=user, conversation=conversation, text=text, reply=reply)
    return Message.objects.prefetch_related("citations__material").get(id=assistant.id)
