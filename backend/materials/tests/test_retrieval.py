import pytest

from ai.models import AICallLog
from common.testing import make_chunk, make_material
from materials.retrieval import search_chunks

pytestmark = pytest.mark.django_db


def test_the_most_relevant_chunk_comes_first(project):
    material = make_material(project)
    make_chunk(project, material, "Mitochondria release energy through cellular respiration", page=7)
    target = make_chunk(
        project, material, "Photosynthesis converts light energy into glucose in chloroplasts", page=2, index=1
    )
    results = search_chunks(project=project, query="How does photosynthesis make glucose?")
    assert results[0].chunk == target
    assert results[0].similarity > results[1].similarity
    assert 0 < results[0].similarity <= 1


def test_unrelated_questions_score_low(project):
    make_chunk(project, make_material(project), "Photosynthesis converts light energy into glucose in chloroplasts")
    results = search_chunks(project=project, query="Who won the football league in 1998?")
    assert results[0].similarity < 0.1


def test_chunks_from_another_users_project_are_never_returned(project, other_project):
    make_chunk(other_project, make_material(other_project), "Photosynthesis converts light energy into glucose")
    assert search_chunks(project=project, query="photosynthesis glucose") == []


def test_another_project_of_the_same_user_is_also_isolated(user, space, project):
    from workspace.services import create_project

    sibling = create_project(user=user, space=space, name="Sibling", description="d", learning_goal="g")
    make_chunk(sibling, make_material(sibling), "Photosynthesis converts light energy into glucose")
    assert search_chunks(project=project, query="photosynthesis glucose") == []


def test_only_ready_materials_are_searched(project):
    make_chunk(project, make_material(project, status="processing"), "Photosynthesis converts light into glucose")
    assert search_chunks(project=project, query="photosynthesis glucose") == []


def test_k_limits_the_results(project):
    material = make_material(project)
    for n in range(8):
        make_chunk(project, material, f"Photosynthesis fact number {n}", index=n)
    assert len(search_chunks(project=project, query="photosynthesis", k=3)) == 3


def test_the_query_embedding_call_is_logged_against_the_project(project, user):
    search_chunks(project=project, query="photosynthesis", user=user)
    log = AICallLog.objects.get(feature="embed")
    assert log.project == project and log.user == user
