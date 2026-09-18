# Evaluation

## What is measured

| Suite | Question it answers | Metric | Minimum |
|---|---|---|---|
| `retrieval` | Do the right pages come back for a question? | recall@6 against the expected pages | 0.75 |
| `tutor` | Are answerable questions answered, with a citation on the right page? | answer rate, citation page hit rate | 0.75, 0.70 |
| `tutor` | Are questions the notes cannot answer refused? | refusal accuracy | 0.80 |
| `grading` | Do open-answer scores agree with hand-labelled scores (±0.2)? | grading agreement | 0.60 |
| `structured_output` | Do quiz generations produce a valid question (after at most one repair)? | schema validity, retries | 0.90 |
| `recommendations` | Does the rule engine pick the expected action and concept, and does the phrasing name the concept? | rule pass rate | 1.00 |

## How it works

- **Material.** `backend/ai/evals/fixtures/photosynthesis_notes.pdf` has six pages of original notes. Each page
  has facts no other page has. The real document pipeline processes it. The PDF is committed because every
  build gets a new document ID, and uploads are de-duplicated by file hash.
- **Dataset.** `backend/ai/evals/golden.json` has 8 answerable questions with expected pages and 5 questions
  the notes cannot answer. Some of the 5 are off-topic; others are near misses that name a topic from the notes
  and ask for a detail the notes leave out. It also has 5 graded answers: strong, partial, wrong, off-topic, and
  a prompt-injection attempt that tells the grader to award full marks.
- **Same code as the product.** The suites call `search_chunks`, `answer_question`, `submit_answer`,
  `start_session`/`next_question` and `generate_recommendation`, the same functions the API calls.
- **Stored results.** Each suite writes one `EvalRun` row with its metrics, per-case results and git commit.
  Results appear under Admin → Evals, so a regression after a prompt, model or retrieval change is visible.
  The command exits non-zero when a suite is below its minimum.
- **Recommendation scenarios.** These are built in throwaway projects: no material, one clearly declining
  concept, and all concepts strong. The projects are deleted afterwards.

```bash
cd backend && source .venv/bin/activate
python manage.py run_evals --fake                         # offline smoke run, no API calls, nothing saved
python manage.py run_evals --fresh --suite retrieval      # about 15 calls; use it to tune the threshold
python manage.py run_evals --markdown ../docs/EVALUATION.md   # about 60 calls on the free tier
```

A real run pauses `EVAL_SLEEP_SECONDS` (default 4) between cases to stay under the free tier's per-minute
limit. `--fake` uses a scripted provider inside a rolled-back transaction. It only proves that the harness
runs; its numbers say nothing about quality.

## Choosing the Tutor similarity threshold

The retrieval suite prints the best-chunk similarity for every answerable and every unanswerable question.
`TUTOR_MIN_SIMILARITY` belongs between the lowest answerable value and the highest unanswerable value.
Near-miss questions usually overlap with answerable ones. In that case the threshold stays just below the
lowest answerable value, and the model's `grounded` flag makes the final call. That is why the Tutor has two
evidence checks, not one.

## Limits

- 18 cases on one document make a regression check, not a benchmark.
- One person labelled the expected grading scores.
- Citations are checked at page level, not sentence level.
- LLM output varies from run to run, so compare trends across runs rather than single numbers.

## Results
