from typing import Literal
from uuid import UUID

from ninja import Router
from ninja.pagination import paginate

from common.scoping import get_owned_or_404
from events.models import LearningEvent
from learning import dashboards
from learning.models import Recommendation
from learning.recommendations import complete_recommendation
from learning.schemas import (
    ActivityOut,
    ConceptMasteryOut,
    GrowthOut,
    HomeOut,
    ProjectDashboardOut,
    RecommendationOut,
    SpaceDashboardOut,
)
from workspace.models import Project, Space

router = Router(tags=["learning"])


@router.get("/home", response=HomeOut)
def home(request):
    return dashboards.home(request.auth)


@router.get("/spaces/{uuid:space_id}/dashboard", response=SpaceDashboardOut)
def space_dashboard(request, space_id: UUID):
    return dashboards.space_dashboard(get_owned_or_404(Space, request.auth, id=space_id), request.auth)


@router.get("/projects/{uuid:project_id}/dashboard", response=ProjectDashboardOut)
def project_dashboard(request, project_id: UUID):
    return dashboards.project_dashboard(get_owned_or_404(Project, request.auth, id=project_id))


# Not paginated: the Growth tab needs every concept at once, and a project has at most a few dozen.
@router.get("/projects/{uuid:project_id}/mastery", response=list[ConceptMasteryOut])
def project_mastery(request, project_id: UUID):
    return dashboards.masteries(get_owned_or_404(Project, request.auth, id=project_id))


@router.get("/projects/{uuid:project_id}/growth", response=GrowthOut)
def project_growth(request, project_id: UUID):
    return dashboards.growth_payload(get_owned_or_404(Project, request.auth, id=project_id))


@router.get("/projects/{uuid:project_id}/recommendations", response=list[RecommendationOut])
@paginate
def project_recommendations(request, project_id: UUID, status: Literal["active", "done", "superseded"] | None = None):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    recommendations = Recommendation.objects.filter(project=project).select_related("project", "concept")
    if status:
        recommendations = recommendations.filter(status=status)
    return recommendations.order_by("-created_at")


@router.post("/recommendations/{uuid:recommendation_id}/complete", response=RecommendationOut)
def complete(request, recommendation_id: UUID):
    recommendation = get_owned_or_404(Recommendation, request.auth, id=recommendation_id)
    complete_recommendation(recommendation)
    return Recommendation.objects.select_related("project", "concept").get(pk=recommendation.pk)


@router.get("/projects/{uuid:project_id}/activity", response=list[ActivityOut])
@paginate
def project_activity(request, project_id: UUID):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return LearningEvent.objects.filter(project=project).order_by("-created_at")
