import pytest

from events.models import LearningEvent


@pytest.fixture(autouse=True)
def clean_events(db, project, other_project):
    """The shared fixtures may emit events (space.created, project.created).

    Analytics tests assert exact counts, so start every test from zero events.
    """
    LearningEvent.objects.all().delete()
