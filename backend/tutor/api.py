from uuid import UUID

from ninja import Router, Status
from ninja.pagination import paginate

from common.scoping import get_owned_or_404
from common.throttling import ScopedThrottle
from tutor import services
from tutor.models import Conversation
from tutor.schemas import ConversationIn, ConversationOut, MessageIn, MessageOut
from workspace.models import Project

router = Router(tags=["tutor"])


@router.get("/projects/{uuid:project_id}/conversations", response=list[ConversationOut])
@paginate
def list_conversations(request, project_id: UUID):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return Conversation.objects.for_user(request.auth).filter(project=project)


@router.post("/projects/{uuid:project_id}/conversations", response={201: ConversationOut})
def create_conversation(request, project_id: UUID, payload: ConversationIn):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return Status(201, services.create_conversation(user=request.auth, project=project, title=payload.title))


@router.get("/conversations/{uuid:conversation_id}/messages", response=list[MessageOut])
@paginate
def list_messages(request, conversation_id: UUID):
    conversation = get_owned_or_404(Conversation, request.auth, id=conversation_id)
    return conversation.messages.prefetch_related("citations__material")


@router.post(
    "/conversations/{uuid:conversation_id}/messages", response={201: MessageOut}, throttle=ScopedThrottle("tutor")
)
def post_message(request, conversation_id: UUID, payload: MessageIn):
    conversation = get_owned_or_404(Conversation, request.auth, id=conversation_id)
    return Status(201, services.answer_question(user=request.auth, conversation=conversation, text=payload.text))
