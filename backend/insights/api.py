from uuid import UUID

from ninja import Router

from common.scoping import get_owned_or_404
from insights import queries
from insights.schemas import GlobalAnalyticsOut, ProjectAnalyticsOut
from workspace.models import Project

router = Router(tags=["analytics"])


@router.get("/projects/{uuid:project_id}/analytics", response=ProjectAnalyticsOut)
def project_analytics(request, project_id: UUID):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return queries.project_analytics(request.auth, project)


@router.get("/analytics/global", response=GlobalAnalyticsOut)
def global_analytics(request):
    return queries.global_analytics(request.auth)
