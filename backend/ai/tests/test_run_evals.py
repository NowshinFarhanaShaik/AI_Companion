from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ai.evals.fake_mode import ScriptedFakeProvider, use_provider
from ai.evals.harness import EVAL_PROJECT_NAME
from ai.evals.suites import SUITES
from ai.models import EvalRun
from workspace.models import Project

pytestmark = pytest.mark.django_db


@pytest.fixture
def scripted():
    with use_provider(ScriptedFakeProvider()) as provider:
        yield provider


def test_run_stores_one_eval_run_per_suite(settings, scripted):
    settings.EVAL_THRESHOLDS = {}
    call_command("run_evals", stdout=StringIO())

    runs = {run.suite: run for run in EvalRun.objects.all()}
    assert set(runs) == set(SUITES)
    assert all(run.passed for run in runs.values())
    assert {"recall_at_6", "suggested_threshold"} <= set(runs["retrieval"].metrics)
    assert {"answer_rate", "citation_hit_rate", "refusal_accuracy"} <= set(runs["tutor"].metrics)
    assert len(runs["tutor"].case_results) == 13
    assert len(runs["grading"].case_results) == 5
    assert len(runs["structured_output"].case_results) == settings.EVAL_QUIZ_GENERATIONS
    assert [case["id"] for case in runs["recommendations"].case_results] == [
        "no_material", "weak_concept", "all_strong"
    ]


def test_recommendation_rules_pass_when_the_text_names_the_target(scripted):
    for _ in range(3):
        scripted.queue_text("Alpha needs another look.")
    call_command("run_evals", suite="recommendations", stdout=StringIO())

    run = EvalRun.objects.get()
    assert run.metrics == {"recommendation_rules": 1.0}
    assert Project.objects.exclude(name=EVAL_PROJECT_NAME).count() == 0


def test_run_below_threshold_fails_after_saving(settings, scripted):
    settings.EVAL_THRESHOLDS = {"recall_at_6": 1.1}
    with pytest.raises(CommandError, match="retrieval"):
        call_command("run_evals", suite="retrieval", stdout=StringIO())
    assert EvalRun.objects.get().passed is False


def test_fake_run_saves_nothing_and_does_not_enforce(settings):
    settings.EVAL_THRESHOLDS = {"recall_at_6": 1.1}
    out = StringIO()
    call_command("run_evals", fake=True, suite="retrieval", stdout=out)

    assert "recall_at_6 = " in out.getvalue()
    assert not EvalRun.objects.exists()
    assert not Project.objects.filter(name=EVAL_PROJECT_NAME).exists()


def test_unknown_suite_is_rejected():
    with pytest.raises(CommandError, match="Unknown suite"):
        call_command("run_evals", suite="nope")


def test_markdown_report_is_appended(tmp_path):
    report = tmp_path / "EVALUATION.md"
    report.write_text("# Evaluation\n")
    call_command("run_evals", fake=True, suite="retrieval", markdown=str(report), stdout=StringIO())

    text = report.read_text()
    assert text.startswith("# Evaluation\n")
    assert ", fake" in text
    assert "| retrieval | recall_at_6 |" in text
