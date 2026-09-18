from ai.evals.harness import (
    EvalCase,
    SuiteResult,
    evaluate_thresholds,
    page_hit,
    rate,
    recall_at_k,
    within_tolerance,
)


def test_rate_is_share_of_true_flags():
    assert rate([True, True, False, False]) == 0.5
    assert rate([]) == 0.0


def test_recall_at_k_is_share_of_expected_pages_retrieved():
    assert recall_at_k([1, 2, 2, 5], [2]) == 1.0
    assert recall_at_k([1, 5], [2, 5]) == 0.5
    assert recall_at_k([], [2]) == 0.0
    assert recall_at_k([1], []) == 0.0


def test_page_hit_needs_one_expected_page():
    assert page_hit([3, 4], [4]) is True
    assert page_hit([3], [4]) is False
    assert page_hit([], [4]) is False


def test_within_tolerance_is_inclusive():
    assert within_tolerance(0.7, 0.9) is True
    assert within_tolerance(0.69, 0.9) is False
    assert within_tolerance(0.2, 0.0, tolerance=0.2) is True


def test_evaluate_thresholds_only_checks_known_metrics():
    thresholds = {"recall_at_6": 0.75, "answer_rate": 0.75}
    assert evaluate_thresholds({"recall_at_6": 0.8, "extra": 0.0}, thresholds) is True
    assert evaluate_thresholds({"recall_at_6": 0.5}, thresholds) is False


def test_suite_result_serialises_cases():
    result = SuiteResult(
        suite="retrieval",
        metrics={"recall_at_6": 1.0},
        cases=[EvalCase(id="a1", kind="answerable", passed=True, detail={"pages": [1]})],
    )
    assert result.case_results() == [
        {"id": "a1", "kind": "answerable", "passed": True, "detail": {"pages": [1]}}
    ]
