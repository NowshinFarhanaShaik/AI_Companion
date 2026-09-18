from events.worker import run_once


def run_all_jobs(max_jobs: int = 50) -> int:
    """Run queued jobs now, ignoring run_after, until the queue is empty. Returns how many ran."""
    count = 0
    while count < max_jobs and run_once(ignore_run_after=True):
        count += 1
    return count
