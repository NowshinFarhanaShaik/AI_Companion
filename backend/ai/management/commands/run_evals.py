import subprocess
from contextlib import ExitStack
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from ai.evals.fake_mode import ScriptedFakeProvider, use_provider
from ai.evals.harness import evaluate_thresholds, load_golden, setup_eval_project
from ai.evals.suites import SUITES
from ai.models import EvalRun
from ai.provider import get_provider


def git_sha() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
    except OSError:
        return ""
    return result.stdout.strip()


class Command(BaseCommand):
    help = "Run the AI eval suites and store one EvalRun per suite. A real run spends provider quota."

    def add_arguments(self, parser):
        parser.add_argument("--suite", help=f"Run one suite: {', '.join(SUITES)}")
        parser.add_argument("--fake", action="store_true", help="Offline smoke run: nothing is saved or enforced")
        parser.add_argument("--fresh", action="store_true", help="Reprocess the fixture PDF first")
        parser.add_argument("--markdown", help="Append the results table to this Markdown file")

    def handle(self, *args, suite=None, fake=False, fresh=False, markdown=None, **options):
        if suite and suite not in SUITES:
            raise CommandError(f"Unknown suite '{suite}'. Choose from: {', '.join(SUITES)}")
        with ExitStack() as stack:
            if fake:
                stack.enter_context(use_provider(ScriptedFakeProvider()))
                stack.enter_context(override_settings(EVAL_SLEEP_SECONDS=0))
                # Rolled back at the end, so fake embeddings never reach the reusable eval project.
                stack.enter_context(transaction.atomic())
            rows, failed = self._run([suite] if suite else list(SUITES), fresh=fresh)
            if fake:
                transaction.set_rollback(True)
                provider = "fake"
            else:
                provider = f"{get_provider().name} {settings.AI_MODELS['strong']}"

        if markdown:
            self._append_markdown(Path(markdown), rows, provider)
        if fake:
            self.stdout.write("Fake provider: nothing was saved and thresholds were not enforced.")
        elif failed:
            raise CommandError(f"Below threshold: {', '.join(failed)}")

    def _run(self, names, *, fresh):
        ctx = setup_eval_project(fresh=fresh)
        golden, sha = load_golden(), git_sha()
        rows, failed = [], []
        for name in names:
            self.stdout.write(self.style.MIGRATE_HEADING(name))
            result = SUITES[name](ctx, golden, self.stdout.write)
            passed = evaluate_thresholds(result.metrics, settings.EVAL_THRESHOLDS)
            EvalRun.objects.create(
                suite=name, git_sha=sha, metrics=result.metrics,
                case_results=result.case_results(), passed=passed,
            )
            for metric, value in result.metrics.items():
                threshold = settings.EVAL_THRESHOLDS.get(metric)
                rows.append((name, metric, value, threshold))
                self.stdout.write(f"  {metric} = {value}" + (f" (min {threshold})" if threshold is not None else ""))
            self.stdout.write(self.style.SUCCESS("  passed") if passed else self.style.ERROR("  below threshold"))
            if not passed:
                failed.append(name)
        return rows, failed

    def _append_markdown(self, path: Path, rows, provider: str):
        lines = [
            f"\n### {timezone.now():%Y-%m-%d %H:%M} UTC, commit `{git_sha() or 'unknown'}`, {provider}\n",
            "| Suite | Metric | Value | Minimum |",
            "|---|---|---|---|",
            *(f"| {suite} | {metric} | {value} | {'' if threshold is None else threshold} |"
              for suite, metric, value, threshold in rows),
        ]
        with path.open("a") as handle:
            handle.write("\n".join(lines) + "\n")
