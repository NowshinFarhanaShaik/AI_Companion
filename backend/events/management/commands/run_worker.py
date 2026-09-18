import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from events.worker import recover_stuck_jobs, run_once

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs background jobs from the Postgres queue."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process the queue until it is empty, then exit.")

    def handle(self, *args, **options):
        self.running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        self.stdout.write("Worker started")
        last_recovery = 0.0
        while self.running:
            close_old_connections()
            try:
                if time.monotonic() - last_recovery > 60:
                    recovered = recover_stuck_jobs()
                    if recovered:
                        logger.warning("Recovered %s stuck jobs", recovered)
                    last_recovery = time.monotonic()
                worked = run_once()
            except Exception:
                logger.exception("Worker loop error")
                worked = False
            if not worked:
                if options["once"]:
                    break
                time.sleep(settings.JOB_POLL_SECONDS)
        self.stdout.write("Worker stopped")

    def _stop(self, *args):
        self.running = False
