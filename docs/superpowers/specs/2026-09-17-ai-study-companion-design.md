# AI Study Companion — Design Spec

- **Date:** 2026-09-17
- **Source:** `Project_Requirements.pdf` (PRD v3.0, Candidate Challenge Edition)
- **Deadline:** 2026-09-18 (prototype, deployed, documented)
- **Status:** Approved design

## 1. Goal and scope

Build a deployed prototype in which one user can complete the full learning loop without losing context:

Space → Project → PDF upload → async processing → Tutor (grounded answer with citation, refusal when unsupported) → adaptive quiz (multiple-choice and open-ended) → mastery → growth → analytics → recommendation → continue learning.

An administrator can inspect users, projects, activity, AI usage, AI evaluation, background jobs and system health.

**Strategy:** a thin version of every must-have, with depth in four areas the PRD weights most:

1. Grounding, citations and unsupported-question refusal
2. Project-level data isolation (API, retrieval, AI tools, background jobs)
3. Mastery model and adaptive question selection
4. AI observability and evaluation

**Out of scope for the prototype:** collaboration, notifications, voice, flashcards, non-PDF formats, email verification, password reset, multi-worker scaling, streaming Tutor responses (listed as a stretch item in section 12).

## 2. Tech stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React 18, Vite, TypeScript | Known stack, fast builds, typed API client |
| UI | Tailwind CSS v4, a small set of own UI primitives in `components/ui/`, Recharts | Dashboards without hand-written CSS and without a component CLI to set up |
| Data fetching | TanStack Query | Caching, loading states, conditional polling |
| Backend | Python 3.12, Django 5 | Auth, ORM, migrations, admin built in |
| API | Django Ninja | Pydantic validates API input and AI structured output |
| Auth | JWT access and refresh tokens (`django-ninja-jwt`) | Works across the Vercel and Render domains |
| Database | PostgreSQL 16 with pgvector | Relational data and embeddings in one store, so retrieval isolation is a `WHERE` clause |
| Background jobs | Postgres-backed queue (own `Job` table, `SELECT … FOR UPDATE SKIP LOCKED`) | No free host offers a worker process or Redis; jobs survive container sleep and restarts |
| PDF | PyMuPDF, page by page | Low memory, accurate page numbers |
| OCR | Gemini vision for pages with little extractable text | No system OCR dependency |
| LLM and embeddings | Google Gemini (free tier) behind an `ai/` provider interface | One key for generation, embeddings and vision; provider is swappable |
| File storage | Django storage abstraction: local disk in development, Supabase Storage (S3-compatible) in production | Free hosts have ephemeral disks |
| Error tracking | Sentry (optional, enabled by env var) | Free tier |
| Deployment | Render free web service (API and worker in one container), Supabase (Postgres, pgvector, storage), Vercel (frontend) | Entirely free |

Node.js is used only as frontend build tooling.

**Simplification to document:** Celery and Redis were the first choice. They were replaced with a Postgres queue to stay on free hosting. At scale the queue would move to Celery/Redis or a managed queue, and the worker would run as its own service.

## 3. Architecture

```
React (Vite, TS) ──JWT──▶ Django Ninja API ──▶ services.py (business logic)
                                                   │
                     ┌─────────────────────────────┼──────────────────────┐
                     ▼                             ▼                      ▼
           Postgres + pgvector               ai/ module             Job table
           (app data, chunks,                (Gemini behind         ▲
            embeddings, events,               an interface,         │ `manage.py run_worker`
            jobs, AI call logs)               logs every call)      │ polls and runs handlers
```

### 3.1 Structural rules

1. **Scoped access.** Every model owned by a Project carries `project_id`. Every query goes through a `for_user(user)` manager method. API views, vector retrieval, AI tools and job handlers all use it.
2. **Thin views.** Business logic lives in `services.py` per app. The API, AI tools and job handlers call the same service functions, so an AI tool cannot skip a check the API applies.
3. **Concept as the link.** Chunk ↔ Concept ↔ Question ↔ ConceptMastery ↔ Recommendation. A quiz result can therefore lead back to a page in the learner's material.
4. **LLM for language, code for decisions.** Question selection, mastery updates, growth labels and recommendation targeting are deterministic code. The LLM writes questions, grades free-text answers, answers Tutor questions and phrases recommendations.

### 3.2 Django apps

| App | Owns |
|---|---|
| `accounts` | `User` (email login, `is_staff` for admin), JWT endpoints |
| `workspace` | `Space`, `Project` |
| `materials` | `Material`, `Chunk`, `Concept`, `ChunkConcept` |
| `tutor` | `Conversation`, `Message`, `Citation` |
| `assessment` | `QuizSession`, `Question`, `Attempt` |
| `learning` | `ConceptMastery`, `MasterySnapshot`, `LearnerMemory`, `Recommendation` |
| `events` | `LearningEvent`, `Job`, worker command, handler registry |
| `ai` | Provider interface, `GeminiProvider`, `FakeProvider`, prompts, tool registry, `AICallLog`, `EvalRun`, eval command |
| `insights` | Read-only analytics and admin endpoints |

## 4. Data model

All tables have `id` (UUID), `created_at`, `updated_at` unless noted.

**workspace**
- `Space`: `owner → User`, `name`, `description`, `color`, `icon`
- `Project`: `space → Space`, `owner → User` (denormalised for scoping), `name`, `description`, `learning_goal`, `last_activity_at`

**materials**
- `Material`: `project`, `title`, `file`, `file_hash` (SHA-256), `page_count`, `status` (`queued | processing | ready | failed`), `error_message`. Unique: (`project`, `file_hash`).
- `Chunk`: `project`, `material`, `page_number`, `index`, `text`, `token_count`, `embedding vector(768)`. HNSW index on `embedding` with cosine distance.
- `Concept`: `project`, `name`, `normalized_name`, `description`, `importance` (1–5). Unique: (`project`, `normalized_name`).
- `ChunkConcept`: `chunk`, `concept`. Unique together.

**tutor**
- `Conversation`: `project`, `title`, `summary` (rolling summary of older messages)
- `Message`: `conversation`, `project`, `role` (`user | assistant`), `content`, `grounded` (bool, null for user messages), `refusal_reason`
- `Citation`: `message`, `chunk`, `material`, `page_number`, `snippet`

**assessment**
- `QuizSession`: `project`, `status` (`active | completed`), `target_question_count`, `completed_at`
- `Question`: `project`, `session`, `concept`, `type` (`mcq | open`), `difficulty` (1–3), `body`, `options` (JSON, mcq only), `correct_option` (mcq only), `rubric` (JSON, open only), `source_chunk`
- `Attempt`: `question` (one-to-one), `project`, `answer_text`, `selected_option`, `score` (0–1), `feedback` (JSON: `understood`, `missing`, `misconceptions`, `feedback`), `evaluated_at`

**learning**
- `ConceptMastery`: `project`, `concept`, `score` (0–1), `evidence_count`, `last_practiced_at`, `consecutive_misses`. Unique: (`project`, `concept`).
- `MasterySnapshot`: `project`, `concept`, `score`, `evidence_count`, `attempt` (one-to-one, nullable; the idempotency key for mastery updates)
- `LearnerMemory`: `project`, `kind` (`goal | preference | strength | weakness | repeated_mistake | note`), `content`, `concept` (nullable), `salience` (0–1), `embedding vector(768)`
- `Recommendation`: `project`, `concept` (nullable), `action_type` (`review_material | take_quiz | ask_tutor | upload_material`), `text`, `reason`, `status` (`active | done | superseded`), `dedupe_key`

**events**
- `LearningEvent`: `user`, `project` (nullable), `space` (nullable), `type`, `payload` (JSON), `idempotency_key` (unique)
- `Job`: `type`, `payload` (JSON, always includes `user_id` and `project_id` where relevant), `status` (`queued | running | succeeded | failed`), `attempts`, `max_attempts` (default 4), `run_after`, `locked_at`, `last_error`, `idempotency_key` (unique)

**ai**
- `AICallLog`: `user`, `project` (nullable), `feature` (`tutor | ocr | concepts | embed | quiz_gen | grading | recommendation | eval | summary`), `provider`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `status` (`ok | error`), `error_type`, `retries`, `retrieved_chunk_ids` (JSON), `trace_id`
- `EvalRun`: `suite`, `git_sha`, `metrics` (JSON), `case_results` (JSON), `passed` (bool)

## 5. Document pipeline

One job type, `process_material`, with idempotency key `process-material:{material_id}`.

1. **Upload** (`POST /projects/{id}/materials`): validate that the file is a PDF (content type and magic bytes) and at most 20 MB and 200 pages. Compute `file_hash`. A duplicate hash within the project returns the existing material. Create `Material(status=queued)`, emit `material.uploaded`, enqueue the job.
2. **Extract:** open with PyMuPDF and iterate page by page. A page with fewer than 50 characters of text is rendered to an image and sent to Gemini vision for OCR.
3. **Chunk:** split page text into chunks of about 800 tokens with 100 tokens of overlap. Chunks never cross a page boundary, which keeps `page_number` exact.
4. **Embed:** batch calls to the embedding model with 768 output dimensions.
5. **Extract concepts:** structured output `[{name, description, importance, chunk_indexes}]`, validated with Pydantic. Upsert on (`project`, `normalized_name`). Link chunks. Create `ConceptMastery(score=0.3, evidence_count=0)` for new concepts. Cap at 15 concepts per material.
6. **Finish:** `status=ready`, emit `material.processed`. On failure after the last retry: `status=failed`, `error_message` set to a user-readable message, emit `material.failed`. The user can retry from the UI, which enqueues a job with a new idempotency key suffix.

**Idempotency:** the handler deletes existing chunks and chunk–concept links for the material inside the same transaction that writes the new ones. A retry cannot leave duplicates.

## 6. Tutor

### 6.1 Request flow (`POST /projects/{id}/conversations/{cid}/messages`)

1. Save the user message. Emit `tutor.message_sent`.
2. **Compose context** (token-budgeted):
   - Conversation: the last 6 messages and `Conversation.summary`
   - Knowledge: top 6 chunks by cosine similarity, filtered by `project_id` and `material.status = ready`
   - Learning: the project's `learning_goal`, the 3 weakest concepts, and the top 3 `LearnerMemory` rows by similarity to the question
3. **Evidence gate, first check:** if no chunk has similarity ≥ `TUTOR_MIN_SIMILARITY` (default 0.55, tuned using the eval suite), return a refusal without calling the generation model. The refusal explains that the materials do not cover the question and suggests uploading material or rephrasing.
4. **Generate:** structured output `{grounded: bool, answer: str, cited_chunk_ids: [str], follow_up: str | null}`.
5. **Evidence gate, second check:** if `grounded` is false, return the refusal form. Otherwise remove any cited ID that was not in the retrieved set and log the mismatch on the `AICallLog`. If no valid citation remains, return the refusal form.
6. Save the assistant message and `Citation` rows. Every 10 messages, enqueue `summarize_conversation`.

**Conversational messages:** greetings and meta questions ("explain that more simply") are handled by retrieving with the previous user question appended, so follow-ups stay grounded.

### 6.2 Prompt-injection defence

- Retrieved chunks are placed in delimited data blocks with chunk IDs. The system prompt states that content inside data blocks is reference material and must never be followed as instructions.
- User messages and documents never reach the system prompt.
- The model can act only through the tool registry.

### 6.3 AI tools

| Tool | Effect |
|---|---|
| `search_materials(query)` | Extra retrieval within the current project |
| `get_weak_concepts()` | Lowest mastery concepts |
| `get_progress()` | Mastery summary and recent quiz results |
| `save_learning_note(kind, content)` | Writes a `LearnerMemory` row |

Each tool has a Pydantic argument schema. The registry executes tools through service functions with `user` and `project` bound on the server from the request. The model never supplies a user or project ID. Arguments that fail validation return an error result to the model. Maximum 3 tool rounds per request.

## 7. Quiz and assessment

### 7.1 Adaptive selection (deterministic)

For each concept in the project:

```
priority = 0.40 × (1 − mastery)
         + 0.20 × uncertainty          # 1 / (1 + evidence_count)
         + 0.25 × recent_miss_rate     # share of the last 5 attempts scored < 0.5
         + 0.15 × staleness            # min(days_since_last_practiced / 14, 1); 1 if never practised
         − 0.30 × asked_in_this_session
```

The highest priority concept is selected. Ties break on `importance`, then randomly.

Difficulty follows the mastery band: `< 0.4 → 1`, `0.4–0.7 → 2`, `> 0.7 → 3`. Two consecutive misses on a concept lower the difficulty by one level for the next question on it.

Question type: open-ended when difficulty is 3 or every third question, otherwise multiple-choice. A session has 5 questions by default.

### 7.2 Generation and grading

- **Generation:** structured output grounded in up to 4 chunks of the chosen concept. Multiple-choice validation: exactly 4 options, `correct_option` in range, no duplicate options. Open-ended questions carry a `rubric` with `key_points`. Invalid output triggers one repair retry, then the job fails and the user sees a retry option.
- **Multiple-choice grading:** deterministic, score 1 or 0, with the stored explanation shown.
- **Open-ended grading:** structured output `{score, understood[], missing[], misconceptions[], feedback}`, validated with score clamped to 0–1. The grading prompt receives the rubric and source chunks, and the learner's answer in a data block.
- On the last answer the session is marked completed and `quiz.completed` is emitted with idempotency key `quiz-completed:{session_id}`.

## 8. Mastery, growth and recommendations

**Mastery update** per attempt:

```
alpha  = max(0.15, 0.5 / (1 + 0.3 × evidence_count))
weight = {1: 0.8, 2: 1.0, 3: 1.2}[difficulty]
new    = clamp(old + alpha × weight × (score − old), 0, 1)
```

Each update writes a `MasterySnapshot` and emits `mastery.updated`. Updates are keyed by attempt ID so a retried job does not apply the same attempt twice.

**Growth label** per concept from snapshots in the last 14 days: difference between the latest score and the earliest score in the window. `> +0.08 → improving`, `< −0.05` or (`score < 0.5` and `evidence_count ≥ 2`) `→ needs_attention`, otherwise `stable`. Fewer than 2 snapshots gives `not_enough_data`.

**Recommendations:**
1. Rules pick the target: no ready material → `upload_material`; a repeated mistake pattern → `ask_tutor` on that concept; weakest `needs_attention` concept → `review_material` with its pages, followed by `take_quiz`; nothing weak → `take_quiz` on the stalest concept.
2. `dedupe_key = {action_type}:{concept_id}`. If an active recommendation has the same key, no new one is created. Otherwise the previous active one becomes `superseded`.
3. The LLM phrases the text from a structured brief. If the call fails, a template sentence is used.

**Repeated-mistake workflow:** when `consecutive_misses ≥ 3` or the same misconception appears in 2 graded attempts, write a `LearnerMemory(kind=repeated_mistake)` and trigger a recommendation.

## 9. Events and background jobs

**Event types:** `space.created`, `project.created`, `material.uploaded`, `material.processed`, `material.failed`, `tutor.message_sent`, `quiz.started`, `question.answered`, `quiz.completed`, `mastery.updated`, `recommendation.created`, `recommendation.completed`.

**Emission:** `events.services.emit(type, user, project, payload, idempotency_key)`. A duplicate key is treated as already handled. Handlers registered per event type enqueue `Job` rows in the same database transaction as the event (transactional outbox). Because the queue is a Postgres table, the event and its jobs commit or roll back together, and the worker only ever sees committed jobs.

**Workflows:**
- `material.uploaded → process_material`
- `quiz.completed → update_mastery → detect_weakness → generate_recommendation`
- `material.processed → generate_recommendation`

**Worker** (`manage.py run_worker`):
- Claims one job at a time with `SELECT … FOR UPDATE SKIP LOCKED` where `status = queued` and `run_after ≤ now`.
- On error: `attempts += 1`, `run_after = now + 30s × 2^attempts`, `last_error` saved. After `max_attempts` the status is `failed`.
- Stuck recovery: a `running` job with `locked_at` older than 10 minutes returns to `queued`.
- Handlers re-load `user` and `project` from the payload and use scoped managers, so ownership context is preserved.
- In production the container start script runs the web server and the worker together.

## 10. AI layer, observability and evaluation

**Interface** (`ai/provider.py`): `generate(prompt, system)`, `generate_structured(prompt, schema, system)`, `generate_with_tools(messages, tools)`, `embed(texts)`, `describe_image(image, prompt)`.

**Implementations:** `GeminiProvider`, and `FakeProvider` with scripted responses for tests. The provider is selected by the `AI_PROVIDER` setting.

**Wrapper** (`ai/client.py`), applied to every call:
- 30 second timeout
- Retries on 429 and 5xx with exponential backoff and jitter, maximum 3
- One repair retry when structured output fails validation, with the validation error included
- One `AICallLog` row per call, including failures
- Cost estimate from a per-model price table in settings

**Model tiers:** a fast model for OCR, concept extraction, summaries and recommendation phrasing; a stronger model for the Tutor and open-ended grading. Model names are settings.

**Evaluation** (`manage.py run_evals`), using a fixture PDF and a golden dataset in `ai/evals/`:

| Suite | Metric |
|---|---|
| Tutor | Refusal accuracy on unanswerable questions; answer rate on answerable ones; citation page hit rate |
| Retrieval | Recall@6 against expected pages |
| Grading | Agreement within ±0.2 of hand-labelled scores |
| Structured output | Schema validity rate for quiz generation |
| Recommendations | Rule checks: the target concept is among the weakest; action type is valid for the project state |

Each run stores an `EvalRun` with metrics, per-case results and the git SHA. Thresholds in settings decide `passed`. The admin page lists runs, which shows regressions after a prompt or model change.

## 11. API surface

All routes are under `/api`. All except auth require a JWT. Lists are paginated.

- `POST /auth/register`, `POST /auth/token`, `POST /auth/token/refresh`, `GET /auth/me`
- `GET|POST /spaces`, `GET|PATCH|DELETE /spaces/{id}`, `GET /spaces/{id}/dashboard`
- `GET|POST /spaces/{id}/projects`, `GET|PATCH|DELETE /projects/{id}`, `GET /projects/{id}/dashboard`
- `GET|POST /projects/{id}/materials`, `GET|DELETE /materials/{id}`, `POST /materials/{id}/retry`, `GET /materials/{id}/file`
- `GET /projects/{id}/concepts`
- `GET|POST /projects/{id}/conversations`, `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages`
- `POST /projects/{id}/quiz-sessions`, `GET /quiz-sessions/{id}`, `POST /quiz-sessions/{id}/next`, `POST /questions/{id}/answer`
- `GET /projects/{id}/mastery`, `GET /projects/{id}/growth`, `GET /projects/{id}/recommendations`, `POST /recommendations/{id}/complete`
- `GET /projects/{id}/analytics`, `GET /analytics/global`, `GET /home`, `GET /projects/{id}/activity`
- Admin (staff only): `GET /admin/overview`, `GET /admin/users`, `GET /admin/users/{id}`, `GET /admin/activity` (filters: user, space, project, type, from, to), `GET /admin/ai-usage`, `GET /admin/evals`, `GET /admin/jobs`, `POST /admin/jobs/{id}/retry`, `GET /admin/health`

An object owned by another user returns 404, not 403, so its existence is not revealed.

## 12. Frontend

**Routes**

```
/login  /register
/                     Home: continue learning, recent projects, overall progress, attention areas, next action
/spaces/:id           Space dashboard: projects, activity, progress
/projects/:id         Tabs: Dashboard | Materials | Tutor | Quiz | Growth | Analytics
/analytics            Global analytics
/admin                Overview | Users → user detail | Activity | AI usage | Evals | Jobs | Health
```

**Structure**

```
frontend/src/
  api/          client.ts (fetch wrapper, token refresh), types.ts, one hooks file per feature
  auth/         AuthProvider, RequireAuth, RequireAdmin
  components/   ui/ (own primitives: Button, Card, Input, Textarea, Badge, Spinner), layout/, shared/ (StatusBadge, MasteryBar, EmptyState, ErrorState, PageHeader)
  features/     home, spaces, projects, materials, tutor, quiz, growth, analytics, admin
  routes.tsx
```

**Behaviour**
- Materials: upload with drag and drop; status badges; polling every 3 seconds only while any material is `queued` or `processing`; failed materials show the error and a retry button.
- Tutor: conversation list and chat view; citation chips that open `/materials/{id}/file#page=N` in a new tab; refusals shown in a distinct "not in your materials" style; input disabled while a reply is pending.
- Quiz: one question at a time; multiple-choice as radio cards, open-ended as a textarea; a feedback card with understood and missing points; a session summary with mastery changes.
- Growth: mastery bars, a trend line per concept, trend badges.
- Every view has loading, empty and error states.

**Stretch:** streaming Tutor responses over SSE, where the answer text streams and citations arrive in a final event.

## 13. Security

- Passwords hashed by Django. JWT access tokens last 15 minutes and refresh tokens 7 days.
- Scoped managers on every query. Cross-user access returns 404.
- Upload validation: PDF magic bytes, size and page limits, files served only through an authenticated endpoint.
- CORS restricted to the frontend origin. Rate limit on auth and AI endpoints.
- AI: data blocks for untrusted text, server-bound tool context, Pydantic validation before any AI output is saved.
- Secrets only in environment variables. `.env.example` is committed and `.env` is ignored.

## 14. Error handling

| Failure | Behaviour |
|---|---|
| AI timeout, 429, 5xx | Backoff retries, then a user-visible "try again" error; logged in `AICallLog` |
| Invalid AI output | One repair retry, then failure; nothing is saved |
| Document processing error | Job retries, then `Material.failed` with a readable message and a retry button |
| Retrieval error | Tutor returns an error state, never an ungrounded answer |
| Job crash or container restart | Stuck-job recovery re-queues it; idempotent handlers make the re-run safe |
| Recommendation phrasing fails | Template text is used |

## 15. Testing

pytest with `FakeProvider`, so no test calls the API.

- **Isolation:** user B cannot read or write user A's spaces, projects, materials, conversations or quizzes; retrieval never returns another project's chunks; AI tools cannot reach another project.
- **Tutor:** refusal below the similarity threshold; refusal when `grounded` is false; a citation outside the retrieved set is removed; injected instructions in a chunk do not change tool behaviour.
- **Assessment:** invalid quiz JSON is rejected; grading score is clamped; feedback is stored.
- **Learning:** mastery formula values; snapshot written; the same attempt applied twice changes mastery once; selection prefers weak, uncertain and stale concepts and penalises repeats; recommendation dedupe.
- **Jobs:** success, retry with backoff, failure after max attempts, duplicate idempotency key, stuck-job recovery.
- **Frontend:** light Vitest coverage of the API client token refresh and the quiz flow.

## 16. Deployment and submission

- Local development uses the Homebrew PostgreSQL 16 with the `vector` extension (Docker is not installed on the development machine).
- `Dockerfile` for the API and worker, built by Render, with a start script that runs migrations, the worker and the web server.
- Render free web service; Supabase Postgres with `CREATE EXTENSION vector` and a private storage bucket; Vercel for the frontend with `VITE_API_URL`.
- A management command seeds a demo user, an admin user and a sample project.
- Repository documents: `README.md`, `docs/ARCHITECTURE.md` (diagram and decisions), `docs/AI_USAGE.md` (AI used to build versus AI in the product), `docs/PROMPTS.md` (development prompt log), `docs/EVALUATION.md`, `docs/LIMITATIONS.md`, `docs/FUTURE.md`.
- Demo video following the PRD's sequence.

## 17. Build order and cut list

| Phase | Deliverable | Estimate |
|---|---|---|
| 0 | Scaffold: Django, React, Docker Compose, pgvector, env config | 1h |
| 1 | Auth, Spaces, Projects, scoped managers | 2h |
| 2 | `ai/` module core (provider interface, wrapper, `AICallLog`, `FakeProvider`), job queue, document pipeline, Materials UI | 3.5h |
| 3 | Tutor: retrieval, citations, refusal, tools, Tutor UI | 2.5h |
| 4 | Quiz: selection, generation, grading | 3h |
| 5 | Events, mastery, growth, recommendations, dashboards | 2.5h |
| 6 | Analytics and Admin | 2.5h |
| 7 | Evals, test hardening, error states | 2h |
| 8 | Deploy | 2h |
| 9 | Documentation and demo video | 2h |

**Cut order if behind:** global analytics charts, admin polish, AI tools beyond `search_materials`, streaming. The learning loop, isolation, refusal behaviour and deployment are never cut.
