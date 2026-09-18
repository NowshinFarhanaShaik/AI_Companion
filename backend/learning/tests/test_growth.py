import pytest
from pytest import approx

from common.testing import make_concept
from learning.growth import concept_trends, label_trend
from learning.tests.factories import make_snapshot

pytestmark = pytest.mark.django_db


# ---- label_trend: pure rules -----------------------------------------------------------------

def test_fewer_than_two_snapshots_is_not_enough_data():
    assert label_trend(latest=0.2, earliest=0.2, snapshot_count=1, evidence_count=1) == "not_enough_data"
    assert label_trend(latest=0.9, earliest=0.9, snapshot_count=0, evidence_count=0) == "not_enough_data"


def test_rise_above_point_08_is_improving():
    assert label_trend(latest=0.60, earliest=0.50, snapshot_count=2, evidence_count=2) == "improving"


def test_improving_wins_even_when_the_score_is_still_low():
    assert label_trend(latest=0.35, earliest=0.20, snapshot_count=3, evidence_count=3) == "improving"


def test_small_rise_is_stable():
    assert label_trend(latest=0.77, earliest=0.70, snapshot_count=4, evidence_count=4) == "stable"


def test_drop_below_minus_point_05_needs_attention():
    assert label_trend(latest=0.70, earliest=0.80, snapshot_count=2, evidence_count=2) == "needs_attention"


def test_small_drop_on_a_strong_concept_is_stable():
    assert label_trend(latest=0.77, earliest=0.80, snapshot_count=2, evidence_count=2) == "stable"


def test_low_score_with_enough_evidence_needs_attention():
    assert label_trend(latest=0.45, earliest=0.44, snapshot_count=2, evidence_count=2) == "needs_attention"


def test_low_score_with_one_piece_of_evidence_is_stable():
    # Two snapshots can be in the window while evidence_count is still 1 only in theory;
    # the rule must still read evidence_count rather than snapshot_count.
    assert label_trend(latest=0.45, earliest=0.44, snapshot_count=2, evidence_count=1) == "stable"


# ---- concept_trends: database ----------------------------------------------------------------

def test_concept_trends_labels_each_concept(project):
    rising = make_concept(project, "Rising", mastery=0.70, evidence_count=2)
    make_snapshot(project, rising, 0.50, days_ago=5)
    make_snapshot(project, rising, 0.70, days_ago=0, evidence_count=2)

    falling = make_concept(project, "Falling", mastery=0.35, evidence_count=3)
    make_snapshot(project, falling, 0.45, days_ago=4, evidence_count=2)
    make_snapshot(project, falling, 0.35, days_ago=0, evidence_count=3)

    untouched = make_concept(project, "Untouched", mastery=0.30, evidence_count=0)

    trends = {t.concept.id: t for t in concept_trends(project)}

    assert trends[rising.id].label == "improving"
    assert trends[rising.id].delta == approx(0.20)
    assert trends[rising.id].score == approx(0.70)
    assert trends[falling.id].label == "needs_attention"
    assert trends[falling.id].delta == approx(-0.10)
    assert trends[untouched.id].label == "not_enough_data"
    assert trends[untouched.id].delta == 0.0
    assert trends[untouched.id].score == approx(0.30)


def test_snapshots_outside_the_window_are_ignored(project):
    concept = make_concept(project, "Windowed", mastery=0.52, evidence_count=3)
    make_snapshot(project, concept, 0.20, days_ago=20)                   # outside 14 days
    make_snapshot(project, concept, 0.50, days_ago=3, evidence_count=2)
    make_snapshot(project, concept, 0.52, days_ago=0, evidence_count=3)

    [trend] = concept_trends(project)

    # With the old snapshot the delta would be +0.32 (improving). Inside the window it is +0.02.
    assert trend.delta == approx(0.02)
    assert trend.label == "stable"


def test_a_wider_window_includes_older_snapshots(project):
    concept = make_concept(project, "Windowed", mastery=0.52, evidence_count=3)
    make_snapshot(project, concept, 0.20, days_ago=20)
    make_snapshot(project, concept, 0.52, days_ago=0, evidence_count=3)

    [trend] = concept_trends(project, days=30)

    assert trend.label == "improving"


def test_concept_trends_are_sorted_weakest_first_and_project_scoped(project, other_project):
    make_concept(project, "Strong", mastery=0.9, evidence_count=1)
    make_concept(project, "Weak", mastery=0.2, evidence_count=1)
    make_concept(other_project, "Foreign", mastery=0.1, evidence_count=1)

    names = [t.concept.name for t in concept_trends(project)]

    assert names == ["Weak", "Strong"]
