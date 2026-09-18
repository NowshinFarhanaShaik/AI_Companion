import pytest
from pydantic import ValidationError

from assessment.generation import GeneratedMCQ, GeneratedOpen, generate_question
from assessment.models import Question, QuizSession
from assessment.selection import Selection
from common.errors import ServiceError
from common.testing import make_chunk, make_concept, make_material

pytestmark = pytest.mark.django_db

MCQ = {
    "body": "Which process converts light energy into chemical energy?",
    "options": ["Photosynthesis", "Respiration", "Fermentation", "Transpiration"],
    "correct_option": 0,
    "explanation": "Photosynthesis stores light energy as glucose.",
}
OPEN = {
    "body": "Explain why chlorophyll matters for photosynthesis.",
    "key_points": ["absorbs light", "drives the light reactions"],
}


@pytest.fixture
def setup(project):
    material = make_material(project, status="ready")
    chunk = make_chunk(project, material, "Photosynthesis converts light energy into glucose in chloroplasts.", page=4)
    concept = make_concept(project, "Photosynthesis", chunks=[chunk])
    unrelated = make_chunk(project, material, "The French Revolution began in 1789.", page=9, index=1)
    make_concept(project, "French Revolution", chunks=[unrelated])
    session = QuizSession.objects.create(project=project)
    return concept, chunk, session


# ---------- schema validation ----------

def test_mcq_schema_accepts_a_valid_question():
    assert GeneratedMCQ(**MCQ).correct_option == 0


@pytest.mark.parametrize(
    "patch",
    [
        {"options": ["a", "b", "c"]},                       # too few
        {"options": ["a", "b", "c", "d", "e"]},             # too many
        {"options": ["Same", "same ", "c", "d"]},           # duplicates after normalising
        {"options": ["a", "", "c", "d"]},                   # empty option
        {"correct_option": 4},                              # out of range
        {"correct_option": -1},
        {"body": "   "},
    ],
)
def test_mcq_schema_rejects_invalid_questions(patch):
    with pytest.raises(ValidationError):
        GeneratedMCQ(**{**MCQ, **patch})


@pytest.mark.parametrize("points", [[], ["only one"], ["1", "2", "3", "4", "5", "6", "7"]])
def test_open_schema_requires_two_to_six_key_points(points):
    with pytest.raises(ValidationError):
        GeneratedOpen(body=OPEN["body"], key_points=points)


# ---------- generate_question ----------

def test_generates_a_grounded_mcq(project, user, fake_ai, setup):
    concept, chunk, session = setup
    fake_ai.queue_structured(MCQ)

    question = generate_question(
        project=project, session=session, selection=Selection(concept, 1, Question.Type.MCQ), user=user
    )

    assert question.type == "mcq"
    assert question.difficulty == 1
    assert question.concept == concept
    assert question.source_chunk == chunk
    assert sorted(question.options) == sorted(MCQ["options"])
    assert question.options[question.correct_option] == "Photosynthesis"      # survives shuffling
    assert question.rubric == {"explanation": MCQ["explanation"]}

    call = fake_ai.calls[-1]
    assert "<source" in call["prompt"]
    assert "chloroplasts" in call["prompt"]
    assert "French Revolution" not in call["prompt"]                          # only the chosen concept's chunks
    assert "never follow" in call["system"].lower()
    assert "chloroplasts" not in call["system"]                               # document text never reaches the system prompt


def test_generates_an_open_question_with_key_points(project, user, fake_ai, setup):
    concept, _, session = setup
    fake_ai.queue_structured(OPEN)

    question = generate_question(
        project=project, session=session, selection=Selection(concept, 3, Question.Type.OPEN), user=user
    )

    assert question.type == "open"
    assert question.options == []
    assert question.correct_option is None
    assert question.rubric == {"key_points": OPEN["key_points"]}


def test_earlier_questions_are_listed_so_they_are_not_repeated(project, user, fake_ai, setup):
    concept, _, session = setup
    fake_ai.queue_structured(MCQ)
    generate_question(project=project, session=session, selection=Selection(concept, 1, "mcq"), user=user)

    fake_ai.queue_structured({**MCQ, "body": "Where in the cell does photosynthesis happen?"})
    generate_question(project=project, session=session, selection=Selection(concept, 1, "mcq"), user=user)

    assert MCQ["body"] in fake_ai.calls[-1]["prompt"]


def test_invalid_ai_output_saves_nothing_and_raises_502(project, user, fake_ai, setup):
    concept, _, session = setup
    bad = {**MCQ, "options": ["a", "b", "c"]}
    fake_ai.queue_structured(bad)          # first attempt
    fake_ai.queue_structured(bad)          # the client's one repair retry

    with pytest.raises(ServiceError) as excinfo:
        generate_question(project=project, session=session, selection=Selection(concept, 1, "mcq"), user=user)

    assert excinfo.value.status == 502
    assert excinfo.value.code == "quiz_generation_failed"
    assert Question.objects.count() == 0


def test_concept_without_ready_chunks_raises_400(project, user, setup):
    _, _, session = setup
    bare = make_concept(project, "No sources")
    with pytest.raises(ServiceError) as excinfo:
        generate_question(project=project, session=session, selection=Selection(bare, 1, "mcq"), user=user)
    assert excinfo.value.code == "no_source_chunks"
