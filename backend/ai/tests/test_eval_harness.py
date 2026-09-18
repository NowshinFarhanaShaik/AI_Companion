import pytest

from ai.evals.fake_mode import ScriptedFakeProvider, use_provider
from ai.evals.harness import EVAL_PROJECT_NAME, load_golden, setup_eval_project
from events.models import Job

pytestmark = pytest.mark.django_db


def test_load_golden_returns_three_groups():
    golden = load_golden()
    assert set(golden) == {"answerable", "unanswerable", "grading"}


def test_setup_processes_the_fixture_and_is_reusable():
    with use_provider(ScriptedFakeProvider()):
        ctx = setup_eval_project()
        assert ctx.project.name == EVAL_PROJECT_NAME
        assert ctx.material.status == "ready"
        pages = set(ctx.project.chunks.values_list("page_number", flat=True))
        assert pages == {1, 2, 3, 4, 5, 6}
        chunk_count = ctx.project.chunks.count()

        again = setup_eval_project()

    assert again.project.id == ctx.project.id
    assert again.material.id == ctx.material.id
    assert again.project.chunks.count() == chunk_count
    assert not Job.objects.filter(type="process_material", status=Job.Status.QUEUED).exists()


def test_fresh_rebuilds_the_project():
    with use_provider(ScriptedFakeProvider()):
        first = setup_eval_project()
        second = setup_eval_project(fresh=True)
    assert second.project.id != first.project.id
