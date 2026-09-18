"""Eval suites (spec §10). They call the services the API calls, so they measure the product, not a copy."""
import time
from datetime import timedelta

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from ai.evals.harness import EvalCase, SuiteResult, page_hit, rate, recall_at_k, within_tolerance
from ai.models import AICallLog
from assessment.models import Question, QuizSession
from assessment.services import next_question, start_session, submit_answer
from common.errors import ServiceError
from learning.models import ConceptMastery, MasterySnapshot
from learning.recommendations import generate_recommendation
from materials.models import Concept, Material, normalize_concept_name
from materials.retrieval import search_chunks
from tutor.services import answer_question, create_conversation
from workspace.services import create_project


def _pause():
    # Keeps a real run under the free tier's requests-per-minute limit.
    time.sleep(settings.EVAL_SLEEP_SECONDS)


def run_retrieval_suite(ctx, golden, out) -> SuiteResult:
    cases, recalls, best = [], [], {"answerable": [], "unanswerable": []}
    for group in best:
        for item in golden[group]:
            results = search_chunks(project=ctx.project, query=item["question"], k=6, user=ctx.user)
            pages = [result.chunk.page_number for result in results]
            top = max((result.similarity for result in results), default=0.0)
            best[group].append(top)
            detail = {"question": item["question"], "pages": pages, "best_similarity": top}
            passed = True
            if group == "answerable":
                recall = recall_at_k(pages, item["expected_pages"])
                recalls.append(recall)
                detail |= {"expected_pages": item["expected_pages"], "recall": recall}
                passed = recall == 1.0
            out(f"  {group:<12} {item['id']:<3} best={top:.3f} pages={pages}")
            cases.append(EvalCase(id=item["id"], kind=group, passed=passed, detail=detail))
            _pause()

    # The Tutor's first evidence gate must sit between these two numbers to be useful.
    lowest_answerable = min(best["answerable"], default=0.0)
    highest_unanswerable = max(best["unanswerable"], default=0.0)
    if lowest_answerable > highest_unanswerable:
        out(f"  groups separate: TUTOR_MIN_SIMILARITY between {highest_unanswerable:.3f} and {lowest_answerable:.3f}")
    else:
        out(f"  groups overlap: keep TUTOR_MIN_SIMILARITY below {lowest_answerable:.3f}; the grounded flag decides")
    metrics = {
        "recall_at_6": round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
        "min_answerable_similarity": round(lowest_answerable, 3),
        "max_unanswerable_similarity": round(highest_unanswerable, 3),
        "suggested_threshold": round((lowest_answerable + highest_unanswerable) / 2, 3),
    }
    return SuiteResult(suite="retrieval", metrics=metrics, cases=cases)


def _ask_tutor(ctx, question: str) -> dict:
    # A new conversation per case, so no earlier answer can leak into the next one.
    conversation = create_conversation(user=ctx.user, project=ctx.project, title="eval")
    try:
        message = answer_question(user=ctx.user, conversation=conversation, text=question)
    except ServiceError as exc:
        return {"grounded": None, "pages": [], "answer": "", "error": exc.code}
    return {
        "grounded": message.grounded,
        "pages": [citation.page_number for citation in message.citations.all()],
        "answer": message.content[:300],
        "error": "",
    }


def run_tutor_suite(ctx, golden, out) -> SuiteResult:
    cases, answered, hits, refused = [], [], [], []
    for item in golden["answerable"]:
        result = _ask_tutor(ctx, item["question"])
        grounded = result["grounded"] is True
        hit = grounded and page_hit(result["pages"], item["expected_pages"])
        answered.append(grounded)
        if grounded:
            hits.append(hit)
        out(f"  answerable   {item['id']:<3} answered={grounded} cited={result['pages']} "
            f"expected={item['expected_pages']}")
        cases.append(EvalCase(id=item["id"], kind="answerable", passed=hit, detail={**item, **result}))
        _pause()

    for item in golden["unanswerable"]:
        result = _ask_tutor(ctx, item["question"])
        # An AI error is not a refusal: only an explicit ungrounded reply counts.
        declined = result["grounded"] is False
        refused.append(declined)
        out(f"  unanswerable {item['id']:<3} refused={declined}")
        cases.append(EvalCase(id=item["id"], kind="unanswerable", passed=declined, detail={**item, **result}))
        _pause()

    metrics = {"answer_rate": rate(answered), "citation_hit_rate": rate(hits), "refusal_accuracy": rate(refused)}
    return SuiteResult(suite="tutor", metrics=metrics, cases=cases)


def run_grading_suite(ctx, golden, out) -> SuiteResult:
    session = QuizSession.objects.create(project=ctx.project, target_question_count=len(golden["grading"]))
    concept = ctx.project.concepts.first()
    cases = []
    for item in golden["grading"]:
        question = Question.objects.create(
            project=ctx.project, session=session, concept=concept, type=Question.Type.OPEN, difficulty=2,
            body=item["question"], rubric={"key_points": item["key_points"]}, source_chunk=ctx.project.chunks.first(),
        )
        try:
            score, error = submit_answer(user=ctx.user, question=question, answer_text=item["answer"]).score, ""
        except ServiceError as exc:
            score, error = None, exc.code
        agreed = score is not None and within_tolerance(score, item["expected_score"])
        out(f"  grading      {item['id']:<3} {item['kind']:<10} expected={item['expected_score']} got={score}")
        cases.append(EvalCase(
            id=item["id"], kind=item["kind"], passed=agreed,
            detail={"expected_score": item["expected_score"], "score": score, "error": error},
        ))
        _pause()
    return SuiteResult(suite="grading", metrics={"grading_agreement": rate(c.passed for c in cases)}, cases=cases)


def run_structured_output_suite(ctx, golden, out) -> SuiteResult:
    """Generation validates against the schema (with one repair retry), so a returned question is a valid one."""
    started = timezone.now()
    cases = []
    for number in range(1, settings.EVAL_QUIZ_GENERATIONS + 1):
        try:
            session = start_session(user=ctx.user, project=ctx.project, target_question_count=1)
            qtype, error = next_question(user=ctx.user, session=session).type, ""
        except ServiceError as exc:
            qtype, error = None, exc.code
        out(f"  quiz_gen     q{number:<2} type={qtype} {error}")
        cases.append(EvalCase(
            id=f"q{number}", kind="quiz_generation", passed=not error, detail={"type": qtype, "error": error}
        ))
        _pause()

    calls = AICallLog.objects.filter(project=ctx.project, feature="quiz_gen", created_at__gte=started)
    metrics = {
        "schema_validity": rate(case.passed for case in cases),
        "quiz_gen_retries": calls.aggregate(total=Sum("retries"))["total"] or 0,
    }
    return SuiteResult(suite="structured_output", metrics=metrics, cases=cases)


def _scenario_project(ctx, name: str, masteries: list[tuple[str, float, float]]):
    """masteries: (concept, score five days ago, score now), each backed by three answers."""
    project = create_project(user=ctx.user, space=ctx.project.space, name=name, learning_goal="eval")
    if masteries:
        Material.objects.create(project=project, title="Eval notes", status=Material.Status.READY, file_hash="eval")
    for concept_name, earlier, latest in masteries:
        concept = Concept.objects.create(
            project=project, name=concept_name, normalized_name=normalize_concept_name(concept_name)
        )
        ConceptMastery.objects.create(project=project, concept=concept, score=latest, evidence_count=3)
        first = MasterySnapshot.objects.create(project=project, concept=concept, score=earlier, evidence_count=2)
        MasterySnapshot.objects.filter(id=first.id).update(created_at=timezone.now() - timedelta(days=5))
        MasterySnapshot.objects.create(project=project, concept=concept, score=latest, evidence_count=3)
    return project


RECOMMENDATION_SCENARIOS = [
    # (name, masteries, expected action, expected target concept)
    ("no_material", [], "upload_material", None),
    (
        "weak_concept",
        [("Alpha", 0.30, 0.20), ("Beta", 0.50, 0.50), ("Gamma", 0.60, 0.60), ("Delta", 0.80, 0.80)],
        "review_material",
        "Alpha",
    ),
    ("all_strong", [("Alpha", 0.85, 0.85), ("Beta", 0.86, 0.86), ("Gamma", 0.90, 0.90)], "take_quiz", "Alpha"),
]


def run_recommendation_suite(ctx, golden, out) -> SuiteResult:
    """The rules pick the target deterministically; the model only phrases it, so the text must name it."""
    stamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    cases = []
    for scenario, masteries, action, concept_name in RECOMMENDATION_SCENARIOS:
        project = _scenario_project(ctx, f"Eval recommendation {scenario} {stamp}", masteries)
        try:
            rec = generate_recommendation(project)
            problems = []
            if rec.action_type != action:
                problems.append(f"action {rec.action_type}, expected {action}")
            if concept_name and (rec.concept is None or rec.concept.name != concept_name):
                problems.append(f"target {rec.concept}, expected {concept_name}")
            if concept_name and concept_name.lower() not in rec.text.lower():
                problems.append("text does not name the concept")
            detail = {"action_type": rec.action_type, "text": rec.text, "problems": problems}
        finally:
            project.delete()
        out(f"  recommend    {scenario:<13} {'; '.join(problems) or 'ok'}")
        cases.append(EvalCase(id=scenario, kind="recommendation", passed=not problems, detail=detail))
        _pause()
    return SuiteResult(
        suite="recommendations", metrics={"recommendation_rules": rate(c.passed for c in cases)}, cases=cases
    )


SUITES = {
    "retrieval": run_retrieval_suite,
    "tutor": run_tutor_suite,
    "grading": run_grading_suite,
    "structured_output": run_structured_output_suite,
    "recommendations": run_recommendation_suite,
}
