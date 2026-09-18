from django.http import Http404
from ninja import NinjaAPI
from ninja.errors import Throttled

from accounts.api import router as accounts_router
from accounts.auth import JWTAuth
from ai.types import AIError
from assessment.api import router as assessment_router
from common.errors import ServiceError
from insights.admin_api import router as admin_router
from insights.api import router as insights_router
from learning.api import router as learning_router
from materials.api import router as materials_router
from tutor.api import router as tutor_router
from workspace.api import router as workspace_router

api = NinjaAPI(title="AI Study Companion", version="0.1.0", auth=JWTAuth())


@api.exception_handler(ServiceError)
def handle_service_error(request, exc: ServiceError):
    return api.create_response(request, {"detail": exc.message, "code": exc.code}, status=exc.status)


@api.exception_handler(Http404)
def handle_not_found(request, exc: Http404):
    return api.create_response(request, {"detail": "Not found", "code": "not_found"}, status=404)


# Services map AI failures themselves; this keeps any path that forgets from becoming a 500.
@api.exception_handler(AIError)
def handle_ai_error(request, exc: AIError):
    detail = "The AI service is unavailable right now. Please try again in a moment."
    return api.create_response(request, {"detail": detail, "code": "ai_unavailable"}, status=503)


@api.exception_handler(Throttled)
def handle_throttled(request, exc: Throttled):
    detail = "Too many requests. Please wait a moment and try again."
    return api.create_response(request, {"detail": detail, "code": "rate_limited"}, status=429)


@api.get("/health", auth=None, tags=["system"])
def health(request):
    return {"status": "ok"}


api.add_router("", accounts_router)
api.add_router("", workspace_router)
api.add_router("", materials_router)
api.add_router("", tutor_router)
api.add_router("", assessment_router)
api.add_router("", learning_router)
api.add_router("", insights_router)
api.add_router("/admin", admin_router)
