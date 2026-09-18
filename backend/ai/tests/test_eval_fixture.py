import json
from pathlib import Path

import pymupdf

from ai.evals.build_fixture import PAGES, build_fixture_pdf

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden.json"

KEYWORDS = ["stomata", "photolysis", "RuBisCO", "CAM plants", "Glycolysis", "ethanol"]


def test_fixture_pdf_has_six_pages_with_distinct_facts():
    doc = pymupdf.open(stream=build_fixture_pdf(), filetype="pdf")
    assert doc.page_count == 6
    for page, keyword in zip(doc, KEYWORDS):
        assert keyword in page.get_text("text")


def test_every_page_is_about_120_words():
    for _title, body in PAGES:
        assert 100 <= len(body.split()) <= 150


def test_golden_dataset_shape():
    golden = json.loads(GOLDEN.read_text())
    assert len(golden["answerable"]) == 8
    assert len(golden["unanswerable"]) == 5
    assert len(golden["grading"]) == 5
    for item in golden["answerable"]:
        assert item["question"]
        assert item["expected_pages"]
        assert all(1 <= page <= 6 for page in item["expected_pages"])
    for item in golden["grading"]:
        assert 0.0 <= item["expected_score"] <= 1.0
        assert item["key_points"]
    kinds = {item["kind"] for item in golden["grading"]}
    assert kinds == {"strong", "partial", "wrong", "off_topic", "injection"}
