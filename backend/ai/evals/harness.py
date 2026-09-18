import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from ai.evals.build_fixture import ensure_fixture_pdf
from events.models import Job
from materials.models import Material
from materials.pipeline import process_material
from materials.services import create_material
from workspace.models import Project, Space
from workspace.services import create_project, create_space

GOLDEN_PATH = Path(__file__).resolve().parent / "golden.json"

EVAL_USER_EMAIL = "eval@studycompanion.local"
EVAL_SPACE_NAME = "AI Evaluation"
EVAL_PROJECT_NAME = "Eval: Photosynthesis notes"


@dataclass
class EvalCase:
    id: str
    kind: str
    passed: bool
    detail: dict = field(default_factory=dict)


@dataclass
class SuiteResult:
    suite: str
    metrics: dict
    cases: list[EvalCase]

    def case_results(self) -> list[dict]:
        return [asdict(case) for case in self.cases]


@dataclass
class EvalContext:
    user: object
    project: Project
    material: Material


def load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text())


def rate(flags) -> float:
    flags = list(flags)
    return round(sum(map(bool, flags)) / len(flags), 3) if flags else 0.0


def recall_at_k(retrieved_pages, expected_pages) -> float:
    expected = set(expected_pages)
    return round(len(expected & set(retrieved_pages)) / len(expected), 3) if expected else 0.0


def page_hit(cited_pages, expected_pages) -> bool:
    return bool(set(cited_pages) & set(expected_pages))


def within_tolerance(actual: float, expected: float, tolerance: float = 0.2) -> bool:
    return abs(actual - expected) <= tolerance + 1e-9


def evaluate_thresholds(metrics: dict, thresholds: dict) -> bool:
    return all(metrics[name] >= minimum for name, minimum in thresholds.items() if name in metrics)


def setup_eval_project(*, fresh: bool = False) -> EvalContext:
    """Reuses the processed eval project between runs, which saves embedding calls.

    The pipeline runs in-process, so a run does not need the worker. Pass fresh=True after a pipeline change.
    """
    User = get_user_model()
    user = User.objects.filter(email=EVAL_USER_EMAIL).first() or User.objects.create_user(
        email=EVAL_USER_EMAIL, password=secrets.token_urlsafe(24), name="Eval Runner"
    )
    projects = Project.objects.for_user(user).filter(name=EVAL_PROJECT_NAME)
    if fresh:
        projects.delete()

    space = Space.objects.for_user(user).filter(name=EVAL_SPACE_NAME).first() or create_space(
        user=user, name=EVAL_SPACE_NAME, description="Used by manage.py run_evals"
    )
    project = projects.first() or create_project(
        user=user, space=space, name=EVAL_PROJECT_NAME,
        learning_goal="Understand photosynthesis and cellular respiration",
    )

    material = project.materials.filter(status=Material.Status.READY).first()
    if material is None:
        project.materials.all().delete()
        pdf = ensure_fixture_pdf()
        upload = SimpleUploadedFile(pdf.name, pdf.read_bytes(), content_type="application/pdf")
        material = create_material(user=user, project=project, uploaded_file=upload)
        # The upload queued a worker job; the pipeline runs here instead, so that job is retired.
        Job.objects.filter(idempotency_key=f"process-material:{material.id}").update(status=Job.Status.SUCCEEDED)
        process_material(material.id)
        material.refresh_from_db()

    return EvalContext(user=user, project=project, material=material)
