import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from ai.evals.build_fixture import ensure_fixture_pdf
from materials.services import create_material
from workspace.models import Project, Space
from workspace.services import create_project, create_space

DEMO_EMAIL = "demo@example.com"
ADMIN_EMAIL = "admin@example.com"
SPACE_NAME = "Biology"
PROJECT_NAME = "Photosynthesis and respiration"


class Command(BaseCommand):
    help = "Create the demo learner, the admin and a sample project with the notes PDF. Safe to run again."

    def handle(self, *args, **options):
        demo_password = os.environ.get("DEMO_PASSWORD")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not (demo_password and admin_password):
            if not settings.DEBUG:
                raise CommandError("Set DEMO_PASSWORD and ADMIN_PASSWORD before seeding a non-debug environment.")
            demo_password = demo_password or "demo12345"
            admin_password = admin_password or "admin12345"
            self.stdout.write("DEBUG is on, so local default passwords are used.")

        demo = self._user(DEMO_EMAIL, demo_password, "Demo Learner", staff=False)
        self._user(ADMIN_EMAIL, admin_password, "Platform Admin", staff=True)

        space = Space.objects.for_user(demo).filter(name=SPACE_NAME).first() or create_space(
            user=demo, name=SPACE_NAME, description="Cell biology for the first-year exam"
        )
        project = Project.objects.for_user(demo).filter(space=space, name=PROJECT_NAME).first() or create_project(
            user=demo, space=space, name=PROJECT_NAME, description="How cells capture and release energy",
            learning_goal="Explain both processes and how they depend on each other",
        )
        if not project.materials.exists():
            pdf = ensure_fixture_pdf()
            upload = SimpleUploadedFile("Photosynthesis Notes.pdf", pdf.read_bytes(), content_type="application/pdf")
            create_material(user=demo, project=project, uploaded_file=upload)
            self.stdout.write("Uploaded the sample PDF; the worker will process it.")
        self.stdout.write(self.style.SUCCESS(f"Seeded {DEMO_EMAIL} and {ADMIN_EMAIL}."))

    def _user(self, email: str, password: str, name: str, *, staff: bool):
        # An existing account keeps its password, so re-seeding production never resets one.
        User = get_user_model()
        user = User.objects.filter(email=email).first() or User.objects.create_user(
            email=email, password=password, name=name
        )
        if user.is_staff != staff:
            user.is_staff = staff
            user.save(update_fields=["is_staff"])
        return user
