from uuid import UUID

from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from ninja import File, Router, Status
from ninja.files import UploadedFile
from ninja.pagination import paginate

from common.scoping import get_owned_or_404
from common.throttling import ScopedThrottle
from materials import services
from materials.models import Concept, Material
from materials.schemas import ConceptOut, MaterialOut
from workspace.models import Project

router = Router(tags=["materials"])


def _materials(user):
    return Material.objects.for_user(user).annotate(chunk_count=Count("chunks"))


@router.get("/projects/{uuid:project_id}/materials", response=list[MaterialOut])
@paginate
def list_materials(request, project_id: UUID):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return _materials(request.auth).filter(project=project)


@router.post(
    "/projects/{uuid:project_id}/materials",
    response={201: MaterialOut, 200: MaterialOut},
    throttle=ScopedThrottle("upload"),
)
def upload_material(request, project_id: UUID, file: UploadedFile = File(...)):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    material = services.create_material(user=request.auth, project=project, uploaded_file=file)
    return Status(201 if material.is_new else 200, _materials(request.auth).get(id=material.id))


@router.get("/materials/{uuid:material_id}", response=MaterialOut)
def get_material(request, material_id: UUID):
    return get_object_or_404(_materials(request.auth), id=material_id)


@router.delete("/materials/{uuid:material_id}", response={204: None})
def delete_material(request, material_id: UUID):
    material = get_owned_or_404(Material, request.auth, id=material_id)
    material.file.delete(save=False)
    material.delete()
    return Status(204, None)


@router.post("/materials/{uuid:material_id}/retry", response=MaterialOut)
def retry_material(request, material_id: UUID):
    material = get_owned_or_404(Material, request.auth, id=material_id)
    services.retry_material(user=request.auth, material=material)
    return _materials(request.auth).get(id=material_id)


@router.get("/materials/{uuid:material_id}/file")
def material_file(request, material_id: UUID):
    material = get_owned_or_404(Material, request.auth, id=material_id)
    response = FileResponse(material.file.open("rb"), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{material.id}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/projects/{uuid:project_id}/concepts", response=list[ConceptOut])
@paginate
def list_concepts(request, project_id: UUID):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    return Concept.objects.for_user(request.auth).filter(project=project).prefetch_related("chunks")
