import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from events.models import Job
from materials.models import Material
from workspace.models import Project, Space

pytestmark = pytest.mark.django_db


@pytest.fixture
def passwords(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "demo-pass-123")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")


def test_seed_creates_users_and_a_project_with_a_queued_pdf(passwords):
    call_command("seed_demo")

    User = get_user_model()
    demo, admin = User.objects.get(email="demo@example.com"), User.objects.get(email="admin@example.com")
    assert demo.check_password("demo-pass-123") and not demo.is_staff
    assert admin.check_password("admin-pass-123") and admin.is_staff
    project = Project.objects.for_user(demo).get()
    assert project.learning_goal
    material = Material.objects.get(project=project)
    assert (material.title, material.status, material.page_count) == ("Photosynthesis Notes", "queued", 6)
    assert Job.objects.filter(type="process_material").count() == 1


def test_seed_is_idempotent_and_keeps_changed_passwords(passwords):
    call_command("seed_demo")
    demo = get_user_model().objects.get(email="demo@example.com")
    demo.set_password("changed-by-user")
    demo.save()

    call_command("seed_demo")

    demo.refresh_from_db()
    assert demo.check_password("changed-by-user")
    assert (Space.objects.count(), Project.objects.count(), Material.objects.count()) == (1, 1, 1)
    assert Job.objects.filter(type="process_material").count() == 1


def test_seed_refuses_without_passwords_outside_debug(monkeypatch, settings):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        call_command("seed_demo")
    assert not get_user_model().objects.exists()


def test_seed_uses_local_defaults_in_debug(monkeypatch, settings):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    settings.DEBUG = True
    call_command("seed_demo")
    assert get_user_model().objects.get(email="demo@example.com").check_password("demo12345")
