from collections import defaultdict
from typing import Callable

_job_handlers: dict[str, Callable] = {}
_event_handlers: dict[str, list[Callable]] = defaultdict(list)


def job_handler(job_type: str):
    def register(fn):
        _job_handlers[job_type] = fn
        return fn

    return register


def on_event(event_type: str):
    def register(fn):
        if fn not in _event_handlers[event_type]:
            _event_handlers[event_type].append(fn)
        return fn

    return register


def get_job_handler(job_type: str):
    return _job_handlers.get(job_type)


def dispatch_event(event) -> None:
    for handler in list(_event_handlers.get(event.type, [])):
        handler(event)
