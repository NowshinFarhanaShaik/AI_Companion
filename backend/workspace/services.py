from django.db import transaction
from django.utils import timezone

from common.errors import ServiceError
from events.services import emit
from workspace.models import Project, Space


def create_space(*, user, name, description="", color="", icon="") -> Space:
    with transaction.atomic():
        space = Space.objects.create(
            owner=user, name=name.strip(), description=description.strip(), color=color, icon=icon
        )
        emit(type="space.created", user=user, space=space, payload={"name": space.name},
             idempotency_key=f"space-created:{space.id}")
    return space


def create_project(*, user, space, name, description="", learning_goal="") -> Project:
    if space.owner_id != user.id:
        raise ServiceError("Space not found", status=404, code="not_found")
    with transaction.atomic():
        project = Project.objects.create(
            space=space,
            owner=user,
            name=name.strip(),
            description=description.strip(),
            learning_goal=learning_goal.strip(),
        )
        emit(type="project.created", user=user, project=project, payload={"name": project.name},
             idempotency_key=f"project-created:{project.id}")
    return project


def touch_project(project) -> None:
    Project.objects.filter(id=project.id).update(last_activity_at=timezone.now())
