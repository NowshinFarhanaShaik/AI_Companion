from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja.pagination import paginate

from common.scoping import get_owned_or_404
from workspace import services
from workspace.models import Project, Space
from workspace.schemas import ProjectIn, ProjectOut, ProjectPatch, SpaceIn, SpaceOut, SpacePatch

router = Router(tags=["workspace"])


def _spaces(user):
    return Space.objects.for_user(user).annotate(project_count=Count("projects"))


def _apply_patch(instance, data) -> None:
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None:
            setattr(instance, field, value)
    instance.save()


@router.get("/spaces", response=list[SpaceOut])
@paginate
def list_spaces(request):
    return _spaces(request.auth)


@router.post("/spaces", response={201: SpaceOut})
def create_space(request, data: SpaceIn):
    space = services.create_space(user=request.auth, **data.dict())
    return Status(201, space)


@router.get("/spaces/{uuid:space_id}", response=SpaceOut)
def get_space(request, space_id: UUID):
    return get_object_or_404(_spaces(request.auth), id=space_id)


@router.patch("/spaces/{uuid:space_id}", response=SpaceOut)
def update_space(request, space_id: UUID, data: SpacePatch):
    _apply_patch(get_owned_or_404(Space, request.auth, id=space_id), data)
    return _spaces(request.auth).get(id=space_id)


@router.delete("/spaces/{uuid:space_id}", response={204: None})
def delete_space(request, space_id: UUID):
    get_owned_or_404(Space, request.auth, id=space_id).delete()
    return Status(204, None)


@router.get("/spaces/{uuid:space_id}/projects", response=list[ProjectOut])
@paginate
def list_projects(request, space_id: UUID):
    space = get_owned_or_404(Space, request.auth, id=space_id)
    return Project.objects.for_user(request.auth).filter(space=space).select_related("space")


@router.post("/spaces/{uuid:space_id}/projects", response={201: ProjectOut})
def create_project(request, space_id: UUID, data: ProjectIn):
    space = get_owned_or_404(Space, request.auth, id=space_id)
    return Status(201, services.create_project(user=request.auth, space=space, **data.dict()))


@router.get("/projects/{uuid:project_id}", response=ProjectOut)
def get_project(request, project_id: UUID):
    return get_owned_or_404(Project, request.auth, id=project_id)


@router.patch("/projects/{uuid:project_id}", response=ProjectOut)
def update_project(request, project_id: UUID, data: ProjectPatch):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    _apply_patch(project, data)
    return project


@router.delete("/projects/{uuid:project_id}", response={204: None})
def delete_project(request, project_id: UUID):
    get_owned_or_404(Project, request.auth, id=project_id).delete()
    return Status(204, None)
