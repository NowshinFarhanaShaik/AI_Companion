import pytest
from django.db import IntegrityError, transaction

from common.testing import make_concept
from learning.models import ConceptMastery, MasterySnapshot

pytestmark = pytest.mark.django_db


def test_make_concept_creates_mastery_row(project):
    concept = make_concept(project, "Photosynthesis", mastery=0.6, evidence_count=4)
    mastery = ConceptMastery.objects.get(project=project, concept=concept)
    assert mastery.score == pytest.approx(0.6)
    assert mastery.evidence_count == 4
    assert mastery.consecutive_misses == 0
    assert mastery.last_practiced_at is None


def test_mastery_is_unique_per_project_and_concept(project):
    concept = make_concept(project, "Osmosis")
    with pytest.raises(IntegrityError), transaction.atomic():
        ConceptMastery.objects.create(project=project, concept=concept)


def test_mastery_and_snapshots_are_scoped_to_the_owner(user, other_user, project, other_project):
    mine = make_concept(project, "Mitosis")
    theirs = make_concept(other_project, "Meiosis")
    MasterySnapshot.objects.create(project=project, concept=mine, score=0.3, evidence_count=0)
    MasterySnapshot.objects.create(project=other_project, concept=theirs, score=0.3, evidence_count=0)

    assert list(ConceptMastery.objects.for_user(user).values_list("concept__name", flat=True)) == ["Mitosis"]
    assert MasterySnapshot.objects.for_user(other_user).count() == 1
    assert MasterySnapshot.objects.for_user(other_user).get().concept == theirs
