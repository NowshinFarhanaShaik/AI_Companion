import uuid

import pytest

from ai.evals.fake_mode import ScriptedFakeProvider, scripted_reply, use_provider
from ai.provider import get_provider
from assessment.generation import GeneratedMCQ, GeneratedOpen
from assessment.grading import GradedAnswer
from materials.prompts import ExtractedConcepts
from tutor.schemas import TutorAnswer


@pytest.mark.parametrize("schema", [ExtractedConcepts, TutorAnswer, GeneratedMCQ, GeneratedOpen, GradedAnswer])
def test_scripted_reply_is_valid_for_every_app_schema(schema):
    schema.model_validate(scripted_reply(schema.__name__, "prompt"))


def test_tutor_reply_cites_the_first_chunk_in_the_prompt():
    chunk_id = str(uuid.uuid4())
    reply = scripted_reply("TutorAnswer", f'<chunk id="{chunk_id}">text</chunk>')
    assert reply["cited_chunk_ids"] == [chunk_id]


def test_use_provider_restores_the_previous_provider(fake_ai):
    with use_provider(ScriptedFakeProvider()) as scripted:
        assert get_provider() is scripted
    assert get_provider() is fake_ai
