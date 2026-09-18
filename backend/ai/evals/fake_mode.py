"""Offline provider for `run_evals --fake`: it proves the harness runs, not that the AI is any good."""
import hashlib
import json
import re
from contextlib import contextmanager

from ai.provider import get_provider, set_provider
from ai.testing import FakeProvider

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def scripted_reply(schema_name: str, prompt: str) -> dict:
    digest = hashlib.sha1(prompt.encode()).hexdigest()[:6]
    replies = {
        "ExtractedConcepts": {"concepts": [{"name": f"Concept {digest}", "chunk_indexes": [0, 1, 2]}]},
        "TutorAnswer": {"grounded": True, "answer": "Fake answer.", "cited_chunk_ids": UUID_RE.findall(prompt)[:1]},
        "GeneratedMCQ": {
            "body": f"Fake question {digest}?", "options": ["A", "B", "C", "D"], "correct_option": 0,
            "explanation": "Fake explanation.",
        },
        "GeneratedOpen": {"body": f"Fake question {digest}?", "key_points": ["First point", "Second point"]},
        "GradedAnswer": {"score": 0.5, "feedback": "Fake feedback."},
    }
    return replies[schema_name]


class ScriptedFakeProvider(FakeProvider):
    def generate_structured(self, *, model, system, prompt, schema, temperature=0.2):
        self.queue_structured(scripted_reply(schema.__name__, prompt))
        return super().generate_structured(model=model, system=system, prompt=prompt, schema=schema)


@contextmanager
def use_provider(provider):
    previous = get_provider()
    set_provider(provider)
    try:
        yield provider
    finally:
        set_provider(previous)
