from django.contrib.auth import get_user_model

from ai.client import generate_text
from events.registry import job_handler
from tutor.context import HISTORY_LIMIT
from tutor.models import Conversation
from tutor.prompts import SUMMARY_SYSTEM_PROMPT, format_history

MAX_MESSAGES = 40
MAX_SUMMARY_CHARS = 2000


@job_handler("summarize_conversation")
def summarize_conversation(job) -> None:
    """Recomputes the summary from stored messages and overwrites it, so a retried job gives the same result."""
    user = get_user_model().objects.filter(id=job.payload["user_id"], is_active=True).first()
    conversation = (
        Conversation.objects.for_user(user).filter(id=job.payload["conversation_id"]).first() if user else None
    )
    if conversation is None:
        return
    # The newest messages go to the model verbatim, so only the older ones need summarising.
    older = list(conversation.messages.order_by("created_at"))[:-HISTORY_LIMIT][-MAX_MESSAGES:]
    if not older:
        return
    summary = generate_text(
        feature="summary", tier="fast", system=SUMMARY_SYSTEM_PROMPT,
        prompt=f"<conversation>\n{format_history(older)}\n</conversation>",
        user=user, project=conversation.project,
    )
    conversation.summary = summary[:MAX_SUMMARY_CHARS]
    conversation.save(update_fields=["summary", "updated_at"])
