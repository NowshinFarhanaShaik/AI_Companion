from dataclasses import dataclass, field

from django.apps import apps

from ai.client import embed_query
from materials.retrieval import RetrievedChunk, search_chunks_by_vector
from tutor.models import Message

HISTORY_LIMIT = 6
RETRIEVAL_K = 6
WEAK_CONCEPT_LIMIT = 3
MEMORY_LIMIT = 3


@dataclass
class TutorContext:
    question: str
    retrieval_query: str
    history: list[Message]
    summary: str
    chunks: list[RetrievedChunk]
    learning_goal: str
    weak_concepts: list[tuple[str, float]] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)


def build_retrieval_query(question: str, history: list[Message]) -> str:
    # A follow-up such as "explain that more simply" names no topic, so the previous question supplies it.
    previous = next((m.content for m in reversed(history) if m.role == Message.Role.USER), "")
    return f"{question}\n{previous[:500]}" if previous else question


def _learning_context(project, vector) -> tuple[list[tuple[str, float]], list[str]]:
    if not apps.is_installed("learning"):
        return [], []
    from learning.models import ConceptMastery

    weakest = (
        ConceptMastery.objects.filter(project=project)
        .select_related("concept")
        .order_by("score", "concept__name")[:WEAK_CONCEPT_LIMIT]
    )
    weak_concepts = [(mastery.concept.name, float(mastery.score)) for mastery in weakest]
    try:
        from learning.memory import relevant_memories
    except ImportError:
        return weak_concepts, []
    memories = relevant_memories(project=project, vector=vector, k=MEMORY_LIMIT)
    return weak_concepts, [f"{memory.kind}: {memory.content}" for memory in memories]


def compose_context(*, user, conversation, question: str) -> TutorContext:
    """Call this before the new user message is saved, so history holds only earlier messages.

    One embedding of the question serves both chunk retrieval and learner-memory retrieval.
    """
    project = conversation.project
    history = list(reversed(conversation.messages.order_by("-created_at")[:HISTORY_LIMIT]))
    retrieval_query = build_retrieval_query(question, history)
    vector = embed_query(retrieval_query, user=user, project=project)
    weak_concepts, memories = _learning_context(project, vector)
    return TutorContext(
        question=question,
        retrieval_query=retrieval_query,
        history=history,
        summary=conversation.summary,
        chunks=search_chunks_by_vector(project=project, vector=vector, k=RETRIEVAL_K),
        learning_goal=project.learning_goal,
        weak_concepts=weak_concepts,
        memories=memories,
    )
