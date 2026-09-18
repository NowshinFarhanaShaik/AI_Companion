# AI Study Companion Implementation Plan — Overview and Interface Contract

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy the AI Study Companion prototype so that one user can complete the full learning loop (Space → Project → PDF → Tutor with citations and refusal → adaptive quiz → mastery → growth → recommendation) and an administrator can inspect the platform.

**Architecture:** A Django Ninja API with business logic in per-app `services.py` modules, a Postgres database that also holds embeddings (pgvector) and the background job queue, an `ai/` module that hides the Gemini provider and logs every call, and a React single-page frontend. Every query is scoped through `for_user(user)` so isolation is enforced in one place.

**Tech Stack:** Python 3.12, Django 5, Django Ninja, django-ninja-jwt, PostgreSQL 16 with pgvector, PyMuPDF, google-genai, pytest; React 18, Vite, TypeScript, Tailwind CSS v4, TanStack Query, React Router, Recharts.

**Spec:** `docs/superpowers/specs/2026-09-17-ai-study-companion-design.md`

## Plan files (execute in this order)

| File | Phase | Tasks |
|---|---|---|
| `01-foundation.md` | Scaffold, auth, Spaces, Projects, frontend shell | 1–5 |
| `02-ai-jobs-materials.md` | `ai/` core, events and job queue, document pipeline, retrieval, Materials UI | 6–11 |
| `03-tutor.md` | Tutor context, evidence gate, citations, tools, Tutor UI | 12–16 |
| `04-assessment.md` | Adaptive selection, question generation, grading, Quiz UI. Also creates the `learning` app with `ConceptMastery` and `MasterySnapshot`, which selection reads | 17–21 |
| `05-learning.md` | Extends the `learning` app: mastery updates, growth, recommendations, learner memory, workflows, dashboards | 22–28 |
| `06-insights-admin.md` | Project and global analytics, admin API and UI | 29–33 |
| `07-evals-hardening.md` | Eval suite, injection tests, rate limits, seed data | 34–38 |
| `08-deploy-docs.md` | Dockerfile, Supabase, Render, Vercel, documentation, demo video | 39–43 |

Each phase ends with working, tested software. If time runs out, stop after a completed phase and jump to `08-deploy-docs.md`.

## Global Constraints

- Python is invoked as `python3.12`. The virtual environment lives at `backend/.venv`. All backend commands run from `backend/` with the environment active.
- Local database: Homebrew PostgreSQL 16 on `localhost:5432`, database `studycompanion`, with `CREATE EXTENSION vector`. Docker is not installed locally.
- Embedding dimension is `768` everywhere (`settings.EMBEDDING_DIM`).
- Tests never call a real AI API. `AI_PROVIDER=fake` in test settings, and the `fake_ai` fixture is autouse.
- Every model owned by a Project has a `project` foreign key and `OWNER_PATH = "project__owner"`. Every read or write in a view, service, AI tool or job handler starts from `Model.objects.for_user(user)` or from an object already loaded that way.
- Two models have a different `OWNER_PATH`: `tutor.Citation` uses `"message__project__owner"` (it has no `project` field), and `events.LearningEvent` and `ai.AICallLog` use `"user"` (their `project` is nullable).
- Code that uses an app or model from a later phase imports it inside the function with `try: ... except ImportError:` and degrades quietly. `apps.is_installed("learning")` alone is not enough, because the `learning` app exists from Phase 4 while `LearnerMemory`, `learning.memory` and `learning.recommendations` arrive in Phase 5.
- An object owned by another user returns HTTP 404, never 403.
- AI output is parsed into a Pydantic model before anything is saved. Text from documents and users goes into delimited data blocks, never into the system prompt.
- Secrets come only from environment variables. `.env` is git-ignored and `.env.example` is committed.
- **Free-tier budget:** about 500 generation requests a day on Flash-Lite and about 20 on Flash. Both tiers default to Flash-Lite. A Tutor message costs 2 to 4 requests and a quiz question 2, so keep manual testing short, run `run_evals` once or twice only, and set `TUTOR_TOOLS_ENABLED=false` in `.env` if the quota runs low.
- Model names are settings (`AI_MODEL_FAST`, `AI_MODEL_STRONG`, `AI_MODEL_EMBED`). Before Task 6, confirm the current Gemini model IDs and free-tier limits in Google AI Studio or with the context7 docs tool, and put the confirmed IDs in `.env`.
- Commit after every task with a conventional message (`feat:`, `test:`, `fix:`, `docs:`, `chore:`). End each commit message with the Co-Authored-By line the coding assistant currently uses.
- **Prompt log:** the submission requires the actual development prompts. At the end of every phase, append the prompts that materially shaped that phase to `docs/PROMPTS.md` under the matching heading (architecture, frontend, backend, database, AI, debugging, testing, documentation).
- **Django Ninja 1.7 deprecates tuple responses.** Wherever this plan shows `return 201, body` or `return 204, None`, write `return Status(201, body)` or `return Status(204, None)` with `from ninja import Status`. The test suite must run with no deprecation warnings.
- Django Ninja has built-in throttling (`ninja.throttling`). Prefer it over a hand-written rate limiter in Phase 7.
- If an import or API in this plan does not match the installed library version, check the library documentation with the context7 tool, fix the code, and note the change in the commit message. Do not work around it by removing a test.

## Learner contribution points

The project owner is building this to learn. Three small functions carry real design decisions. When a task reaches one, create the file with the signature, docstring and tests from the plan, then ask the owner to write the body (5–10 lines). The plan contains a reference implementation to fall back on if they prefer.

| Function | File | Task | Decision it carries |
|---|---|---|---|
| `compute_priority` | `backend/assessment/selection.py` | 17 | How weakness, uncertainty, mistakes and staleness trade off when choosing what to practise |
| `compute_new_score` | `backend/learning/mastery.py` | 22 | How fast mastery moves on new evidence |
| `label_trend` | `backend/learning/growth.py` | 23 | When a concept counts as improving or needing attention |

## Repository layout

```
backend/
  manage.py  requirements.txt  pytest.ini  conftest.py  Dockerfile  start.sh
  config/        settings.py  urls.py  api.py  wsgi.py  asgi.py
  common/        models.py  scoping.py  errors.py  testing.py
  accounts/      models.py  api.py  schemas.py  auth.py  tests/
  workspace/     models.py  api.py  schemas.py  services.py  tests/
  materials/     models.py  api.py  schemas.py  services.py  pipeline.py  chunking.py  retrieval.py  tests/
  tutor/         models.py  api.py  schemas.py  services.py  context.py  tools.py  prompts.py  tests/
  assessment/    models.py  api.py  schemas.py  services.py  selection.py  generation.py  grading.py  prompts.py  tests/
  learning/      models.py  api.py  schemas.py  mastery.py  growth.py  recommendations.py  memory.py  handlers.py  tests/
  events/        models.py  services.py  registry.py  worker.py  testing.py  management/commands/run_worker.py  tests/
  ai/            models.py  types.py  provider.py  gemini.py  testing.py  client.py  pricing.py  evals/  management/commands/run_evals.py  tests/
  insights/      api.py  admin_api.py  schemas.py  queries.py  tests/
frontend/
  index.html  package.json  vite.config.ts  tsconfig.json
  src/  main.tsx  routes.tsx  index.css
        api/  auth/  components/ui/  components/layout/  components/shared/  features/
docs/
  ARCHITECTURE.md  AI_USAGE.md  PROMPTS.md  EVALUATION.md  LIMITATIONS.md  FUTURE.md
.env.example  README.md
```

---

# Interface contract

Every phase file relies on the names below. A task implementer sees only their own task, so these names are binding. If a task needs to change one, change it here in the same commit.

## C1. Common (`backend/common/`)

```python
# common/models.py
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: abstract = True

# common/scoping.py
class OwnedQuerySet(models.QuerySet):
    def for_user(self, user): return self.filter(**{self.model.OWNER_PATH: user})
def get_owned_or_404(model, user, **lookup):  # raises django.http.Http404
    ...

# common/errors.py
class ServiceError(Exception):
    def __init__(self, message: str, *, status: int = 400, code: str = "error"): ...
```

`ServiceError` exposes `.message`, `.status` and `.code`. `config/api.py` registers a handler that turns it into `{"detail", "code"}` with that status, and one for `Http404`.

Every owned model declares `OWNER_PATH` and `objects = OwnedQuerySet.as_manager()`. `Space.OWNER_PATH = "owner"`, `Project.OWNER_PATH = "owner"`, all others `"project__owner"`.

API errors have the JSON shape `{"detail": "<message>", "code": "<code>"}`.

## C2. Auth and API wiring

- `accounts.User`: custom user with a UUID `id`, `USERNAME_FIELD = "email"`, fields `email` (unique), `name`, `created_at` (there is no `date_joined`), plus Django's `is_staff`, `is_active`. `AUTH_USER_MODEL = "accounts.User"`. Manager: `User.objects.create_user(email=, password=, name=)`.
- Auth endpoints: `POST /api/auth/register` `{name, email, password}` → 201 `{access, refresh, user}`; `POST /api/auth/token` `{email, password}` → `{access, refresh, user}` or 401 `invalid_credentials`; `POST /api/auth/token/refresh` `{refresh}` → `{access}` or 401 `invalid_refresh`; `GET /api/auth/me`.
- `accounts/auth.py`: `JWTAuth` (re-exported from `ninja_jwt.authentication`) and `StaffJWTAuth(JWTAuth)`, which returns `None` unless `user.is_staff`.
- In every view, **`request.auth` is the authenticated `User`**.
- `config/api.py`: `api = NinjaAPI(title="AI Study Companion", auth=JWTAuth())`. Each app exposes `router = Router(tags=[...])` in its `api.py`, mounted with `api.add_router("", router)`. Admin endpoints live in `insights/admin_api.py` with `router = Router(auth=StaffJWTAuth(), tags=["admin"])` mounted at `/admin`.
- All URLs are under `/api/`. Path parameters are UUIDs: `{uuid:project_id}`.
- List endpoints use `@paginate` from `ninja.pagination` (limit/offset). The response shape is `{"items": [...], "count": n}`. Two lists are deliberately not paginated because a page needs every row at once: `GET /projects/{id}/mastery` and `GET /projects/{id}/growth`. `ATOMIC_REQUESTS` stays off, so an `AICallLog` row for a failed call is not rolled back with the request.

## C3. Models

Field names are exactly those in spec section 4. Django details:

| Model | Choices classes | `related_name` values |
|---|---|---|
| `workspace.Space` | — | `owner.spaces` |
| `workspace.Project` | — | `space.projects`, `owner.projects` |
| `materials.Material` | `Material.Status` (`QUEUED`, `PROCESSING`, `READY`, `FAILED`) | `project.materials` |
| `materials.Chunk` | — | `material.chunks`, `project.chunks` |
| `materials.Concept` | — | `project.concepts`; `chunks = ManyToManyField(Chunk, through="ChunkConcept", related_name="concepts")` |
| `tutor.Conversation` | — | `project.conversations` |
| `tutor.Message` | `Message.Role` (`USER`, `ASSISTANT`) | `conversation.messages` |
| `tutor.Citation` | — | `message.citations` |
| `assessment.QuizSession` | `QuizSession.Status` (`ACTIVE`, `COMPLETED`) | `project.quiz_sessions` |
| `assessment.Question` | `Question.Type` (`MCQ = "mcq"`, `OPEN = "open"`) | `session.questions`, `concept.questions` |
| `assessment.Attempt` | — | `question.attempt` (one-to-one), `project.attempts` |
| `learning.ConceptMastery` | — | `project.masteries`, `concept.masteries` |
| `learning.MasterySnapshot` | — | `project.snapshots`, `concept.snapshots`, `attempt.snapshot` |
| `learning.LearnerMemory` | `LearnerMemory.Kind` | `project.memories` |
| `learning.Recommendation` | `Recommendation.ActionType`, `Recommendation.Status` (`ACTIVE`, `DONE`, `SUPERSEDED`) | `project.recommendations` |
| `events.LearningEvent` | — | `user.events`, `project.events` |
| `events.Job` | `Job.Status` (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`) | — |
| `ai.AICallLog` | `AICallLog.Status` (`OK`, `ERROR`) | `user.ai_calls`, `project.ai_calls` |
| `ai.EvalRun` | — | — |

Additional related names: `project.tutor_messages` (`Message.project`), `material.citations`, `chunk.citations`. `Citation.chunk` is nullable with `SET_NULL`, because re-processing a material replaces its chunks; the citation keeps `material`, `page_number` and `snippet`. `Question.source_chunk` is nullable for the same reason. `Attempt.score` is a non-null float.

All choice values are the lowercase strings from the spec. `Chunk.embedding` and `LearnerMemory.embedding` are `pgvector.django.VectorField(dimensions=768)`; `LearnerMemory.embedding` is nullable.

## C4. AI module (`backend/ai/`)

```python
# ai/types.py
class AIError(Exception): retryable = False
class AIRateLimitError(AIError): retryable = True
class AITimeoutError(AIError): retryable = True
class AIProviderError(AIError): retryable = True      # 5xx
class AIInvalidOutputError(AIError): retryable = False

@dataclass
class RawResult:        text: str; input_tokens: int = 0; output_tokens: int = 0
@dataclass
class RawEmbedResult:   vectors: list[list[float]]; input_tokens: int = 0
@dataclass
class ToolSpec:         name: str; description: str; args_schema: type[BaseModel]
@dataclass
class ToolCall:         name: str; args: dict
@dataclass
class ToolTurn:         text: str | None; tool_calls: list[ToolCall]; input_tokens: int = 0; output_tokens: int = 0; raw: Any = None

# ai/provider.py
def get_provider() -> Provider
def set_provider(provider: Provider | None) -> None      # the fake_ai fixture installs the fake with this

# ai/client.py — the only module other apps import for AI work
def generate_text(*, feature: str, prompt: str, system: str = "", tier: str = "fast",
                  user=None, project=None, trace_id: str | None = None) -> str
def generate_structured(*, feature: str, prompt: str, schema: type[T], system: str = "", tier: str = "fast",
                        user=None, project=None, retrieved_chunk_ids: list[str] | None = None,
                        trace_id: str | None = None) -> T
def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT", user=None, project=None) -> list[list[float]]
def embed_query(text: str, *, user=None, project=None) -> list[float]
def ocr_image(png_bytes: bytes, *, user=None, project=None) -> str
def tool_turn(*, feature: str, system: str, transcript: list[dict], tools: list[ToolSpec], tier: str = "strong",
              user=None, project=None, trace_id: str | None = None) -> ToolTurn
```

- `tier` is `"fast"` or `"strong"` and maps to `settings.AI_MODELS`.
- `feature` is one of `tutor | ocr | concepts | embed | quiz_gen | grading | recommendation | eval | summary`.
- Every function writes one `AICallLog` row per call, including failures, and raises an `AIError` subclass on failure.
- `transcript` entries are dicts: `{"role": "user", "text": str}`, `{"role": "model", "text": str | None, "tool_calls": [{"name", "args"}], "raw": ToolTurn.raw}`, `{"role": "tool", "name": str, "result": dict}`. Always pass `raw` back; the Gemini provider replays it unchanged.
- Verified against the live API on 2026-09-17 (google-genai 2.24, `gemini-3.5-flash-lite`): a function response must be sent with `role="user"` (the API rejects `"tool"`), and a model turn that contained function calls must be replayed from `ToolTurn.raw`; a rebuilt turn is rejected for lacking a thought signature. `raw` is therefore required in every `model` transcript entry.
- Provider methods are keyword-only: `generate(*, model, system, prompt, temperature)`, `generate_structured(*, model, system, prompt, schema, temperature)`, `embed(*, model, texts, task_type)`, `describe_image(*, model, image_png, prompt)`, `generate_with_tools(*, model, system, transcript, tools)`.
- Retries: only errors with `retryable = True` are retried (`AIRateLimitError`, `AITimeoutError`, `AIProviderError`), up to `settings.AI_MAX_RETRIES`, sleeping through `time.sleep` (imported as a module, so tests can patch it). A plain `AIError` is raised at once. Invalid structured output gets one repair call, which consumes a second queued fake response and is logged with `retries = 1`. `AICallLog.retries` counts the retries of that call.
- Do not call these functions inside a long `transaction.atomic()` block.

```python
# ai/testing.py
class FakeProvider:
    calls: list[dict]                       # every call: {"method", "model", ...}; "method" is the provider method name
                                            # generate / generate_structured: + "system", "prompt" (+ "schema" name)
                                            # generate_with_tools: + "system", "transcript" (a copy), "tools" (names)
                                            # embed: + "texts", "task_type";  describe_image: + "prompt"
    def calls_to(self, method: str) -> list[dict]
    def queue_text(self, text: str) -> None
    def queue_structured(self, obj: dict | BaseModel) -> None     # returned as JSON text by generate_structured
    def queue_tool_turn(self, *, text: str | None = None, tool_calls: list[ToolCall] | None = None) -> None
    def queue_error(self, exc: Exception) -> None                 # raised by the next call of any kind
    def set_embedding(self, text: str, vector: list[float]) -> None   # applies to document and query embeddings
def fake_embedding(text: str, dim: int = 768) -> list[float]      # deterministic bag-of-words hash, L2-normalised
```

With the fake, texts that share words have a high cosine similarity and unrelated texts score near zero. When a queue is empty, `generate` returns `"fake response"`, `generate_structured` raises `AssertionError("no structured response queued")`, and `generate_with_tools` returns a turn with text `"fake response"` and no tool calls.

## C5. Events and jobs (`backend/events/`)

```python
# events/services.py
def emit(*, type: str, user, project=None, space=None, payload: dict | None = None,
         idempotency_key: str | None = None) -> LearningEvent | None     # None when the key already exists
def enqueue(job_type: str, payload: dict, *, idempotency_key: str | None = None,
            run_after=None, max_attempts: int = 4) -> Job               # returns the existing Job on a duplicate key

# events/registry.py
def job_handler(job_type: str): ...     # decorator; handler signature: (job: Job) -> None
def on_event(event_type: str): ...      # decorator; handler signature: (event: LearningEvent) -> None
def get_job_handler(job_type: str): ...
def dispatch_event(event: LearningEvent) -> None

# events/worker.py
def claim_next_job() -> Job | None
def run_job(job: Job) -> None
def run_once() -> bool                  # True when a job was processed
def recover_stuck_jobs() -> int

# events/testing.py
def run_all_jobs(max_jobs: int = 50) -> int     # runs queued jobs, ignoring run_after; returns the count
```

`emit` calls `dispatch_event` synchronously, inside the caller's transaction, and fills `space` from `project` when only a Project is given. Event handlers only enqueue jobs; they never do slow work. The one exception is `learning.handlers.on_question_answered`, which applies the mastery update directly: it is arithmetic only, and the next question of the same quiz session is selected from it.

`events.worker.PermanentJobError`: a job handler raises it to fail the job without retrying.

Event payloads other phases rely on:

| Event | Payload keys | Idempotency key |
|---|---|---|
| `material.uploaded` | `material_id`, `project_id`, `user_id`, `title` | `material-uploaded:{material_id}` |
| `material.processed` | `material_id`, `title`, `chunks` | `material-processed:{material_id}:{job_id}` |
| `material.failed` | `material_id`, `error` | `material-failed:{material_id}:{job_id}` |
| `tutor.message_sent` | `conversation_id`, `message_id`, `grounded`, `refusal_reason`, `citation_count` | `tutor-message:{user_message_id}` |
| `quiz.started` | `session_id`, `target_question_count` | — |
| `question.answered` | `session_id`, `question_id`, `attempt_id`, `concept_id`, `score` | `question-answered:{question_id}` |
| `quiz.completed` | `session_id`, `answered` | `quiz-completed:{session_id}` |
| `mastery.updated` | `concept_id`, `concept_name`, `attempt_id`, `old_score`, `new_score` | `mastery:{attempt_id}` | Handlers and job handlers are registered in each app's `handlers.py`, imported from that app's `AppConfig.ready()`.

Job payloads always carry `user_id`, and `project_id` where one applies.

## C6. Service signatures

```python
# workspace/services.py
def create_space(*, user, name, description="", color="", icon="") -> Space
def create_project(*, user, space, name, description="", learning_goal="") -> Project
def touch_project(project) -> None                     # sets last_activity_at = now

# materials/services.py
def create_material(*, user, project, uploaded_file) -> Material      # validates, dedupes on file_hash, emits material.uploaded;
                                                                      # the returned instance has .is_new (False for a duplicate)
def retry_material(*, user, material) -> Material
# materials/chunking.py
def chunk_page_text(text: str, *, max_chars: int = 3200, overlap: int = 400) -> list[str]
# materials/pipeline.py
def process_material(material_id, *, user_id=None, job=None) -> None   # job type "process_material"; jobs pass user_id and the
                                                      # material is loaded through for_user; trusted in-process callers may omit it
# materials/retrieval.py
@dataclass
class RetrievedChunk: chunk: Chunk; similarity: float
def search_chunks(*, project, query: str, k: int = 6, user=None) -> list[RetrievedChunk]
def search_chunks_by_vector(*, project, vector: list[float], k: int = 6) -> list[RetrievedChunk]

# tutor/services.py
def create_conversation(*, user, project, title="") -> Conversation
def answer_question(*, user, conversation, text: str) -> Message     # returns the saved assistant message

# assessment/selection.py
@dataclass
class Selection: concept: Concept; difficulty: int; qtype: str
def compute_priority(*, mastery: float, evidence_count: int, recent_miss_rate: float,
                     days_since_practiced: float | None, asked_in_session: bool) -> float
def select_next(*, project, session) -> Selection | None
# assessment/services.py
def start_session(*, user, project, target_question_count: int = 5) -> QuizSession
def next_question(*, user, session) -> Question | None               # None when the session is complete
def submit_answer(*, user, question, selected_option: int | None = None, answer_text: str = "") -> Attempt

# learning/mastery.py
def compute_new_score(*, old: float, score: float, difficulty: int, evidence_count: int) -> float
def apply_attempt(attempt) -> ConceptMastery                         # idempotent per attempt
# learning/growth.py
@dataclass
class Trend: concept: Concept; score: float; delta: float; label: str; evidence_count: int
def label_trend(*, latest: float, earliest: float, snapshot_count: int, evidence_count: int) -> str
def concept_trends(project, *, days: int = 14) -> list[Trend]
# learning/recommendations.py
def generate_recommendation(project) -> Recommendation | None
def active_recommendation(project) -> Recommendation | None
# learning/memory.py
def record_memory(*, project, kind: str, content: str, concept=None, salience: float = 0.5) -> LearnerMemory
def relevant_memories(*, project, vector: list[float], k: int = 3) -> list[LearnerMemory]
```

Trend labels are `improving | stable | needs_attention | not_enough_data`.

Error codes returned as `ServiceError.code`: `email_taken`, `weak_password`, `invalid_credentials`, `invalid_refresh`, `not_found`, `invalid_pdf`, `file_too_large`, `too_many_pages`, `not_failed`, `empty_message`, `ai_unavailable` (503), `no_concepts`, `no_source_chunks`, `invalid_option`, `empty_answer`, `already_answered` (409), `quiz_generation_failed` (502), `grading_failed` (502), `job_not_failed` (409), `rate_limited` (429).

## C7. Test fixtures (`backend/conftest.py` and `backend/common/testing.py`)

```python
# conftest.py fixtures
user, other_user, admin_user          # accounts.User instances; password "pass12345"
space, project                        # owned by `user`
other_space, other_project            # owned by `other_user`
api                                   # factory: api(user) -> ApiClient
fake_ai                               # autouse; installs and returns a FakeProvider

# common/testing.py
class ApiClient:                      # wraps django.test.Client with a Bearer token and JSON bodies;
                                      # a path may start with /api/ or omit it: "/spaces" and "/api/spaces" are the same
    def get(self, path, **params); def post(self, path, data=None); def patch(self, path, data=None)
    def delete(self, path); def upload(self, path, field, filename, content: bytes, content_type)
def make_material(project, *, title="Notes", status="ready", page_count=3) -> Material
def make_chunk(project, material, text, *, page=1, index=0) -> Chunk      # embedding = fake_embedding(text)
def make_concept(project, name, *, chunks=(), importance=3, mastery=0.3, evidence_count=0) -> Concept
                                      # links the chunks through ChunkConcept; creates ConceptMastery once the learning app exists (Phase 4)
def make_pdf_bytes(pages: list[str]) -> bytes                             # builds a real PDF with PyMuPDF
```

Test files live in `backend/<app>/tests/test_<topic>.py`. Run one file with `pytest <app>/tests/test_<topic>.py -v` and everything with `pytest -q`.

## C8. Frontend

```ts
// src/api/client.ts
export class ApiError extends Error { status: number; code?: string }
export const api: {
  get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T>
  post<T>(path: string, body?: unknown): Promise<T>
  patch<T>(path: string, body?: unknown): Promise<T>
  delete<T>(path: string): Promise<T>
  upload<T>(path: string, form: FormData): Promise<T>
}
export type Paginated<T> = { items: T[]; count: number }
// Paths are relative to VITE_API_URL + "/api". Tokens are stored under localStorage keys
// "asc_access" and "asc_refresh". A 401 triggers one silent refresh and one retry.

// src/auth/useAuth.ts   (the AuthProvider component lives in src/auth/AuthProvider.tsx; a file that exports a
//                        component and a hook breaks React fast refresh, and oxlint flags it)
export function useAuth(): { user: User | null; loading: boolean;
  login(email: string, password: string): Promise<void>;
  register(name: string, email: string, password: string): Promise<void>;
  logout(): void }

// src/features/projects/tabs.ts
export const projectTabs: { path: string; label: string }[]      // each phase appends its tab
// src/features/projects/useProjectId.ts
export function useProjectId(): string
```

- `src/api/client.ts` also exports `tokens`, `api.blob(path)` and `openProtectedFile(path, page?)`, which opens a JWT-protected PDF in a new tab at a page. Use it for every link to `/materials/{id}/file`.
- The top navigation is data-driven: `src/components/layout/nav.ts` exports `navItems: { to, label, staffOnly? }[]`, and `AppLayout` renders it. A phase adds a nav link by adding an item. Phase 1 defines Home (`/`) and Spaces (`/spaces`).
- Every component and page is a **named** export, one per file, imported by relative path. A file exports components or hooks, never both. `RequireAdmin` takes `children`. Login and registration share one `AuthPage` with a `mode` prop.
- Frontend checks are `npm run build` and `npm run lint` (oxlint); both must be clean.
- Tutor as built (Phase 3): `tutor/services.py` returns a `Reply(content, grounded, refusal_reason, cited_chunks)` dataclass internally; the tool rounds run only when the first evidence check found something, so an off-topic question costs one embedding call and no generation call. Prompts escape untrusted text with `escape_data` (there is no `neutralise_tags`). The frontend has no `openMaterialPage` wrapper: citation chips call `openProtectedFile` directly.
- Quiz as built (Phase 4): `assessment/schemas.py` uses Ninja resolvers (no `serialize_*` helpers); the API prefetches a session's questions with concept and attempt. The frontend never fetches a question from an effect: `useStartQuiz` creates the session and requests the first question, and later questions come from an explicit "Next question" click. Links styled as buttons use `buttonClasses()` from `components/ui/buttonStyles.ts`, because an `<a>` must not wrap a `<button>`.
- The owner asked the assistant to write all three contribution functions; do not pause for them.
- Learning as built (Phase 5): `learning/dashboards.py` returns models, `Trend` dataclasses and plain aggregates, and `learning/schemas.py` resolvers shape them (no `serialize_*`). Attempts are always graded before they are saved, so `Attempt.score` and `evaluated_at` are never null and no code handles an "ungraded attempt". Processing a material now also queues `generate_recommendation`, so pipeline tests count that job. Frontend: chart pages are lazy routes with a `hydrateFallbackElement`; `MasteryBar` takes `unpractised` to drop severity colour for concepts with no evidence; activity feeds use `components/shared/ActivityList`.
- Insights as built (Phase 6): `insights/queries.py` (learner, scoped with `for_user`, including `LearningEvent` and `AICallLog`), `insights/admin_queries.py` and `insights/admin_ops.py` (staff only, unscoped), one `insights/admin_api.py` router mounted at `/admin`. Mastery bands (`low/medium/high`) count only practised concepts; `unpractised` is reported separately. A failed AI call among fewer than five calls in the hour makes the health check amber. Frontend: shared `components/shared/{chartTheme.ts, ChartTooltip, ChartDataTable, SimpleTable, StatTile, Pager, activityLabels.ts}` and `components/ui/Select`; table links replace clickable rows; every chart and admin page is a lazy route through `lazyPage()` in `routes.tsx`.
- Evals and hardening as built (Phase 7): `ai/evals/{build_fixture, golden.json, harness, fake_mode, suites}.py` and `manage.py run_evals`. `--fake` swaps in `ScriptedFakeProvider` (one valid reply per app schema) inside a rolled-back transaction, so it never saves anything. Suites catch `ServiceError` only, because every service already maps `AIError` to one. Rate limits use Ninja's `AuthRateThrottle` through `common.throttling.ScopedThrottle(scope)`, with rates in `NINJA_DEFAULT_THROTTLE_RATES`, read at import. A throttled request returns 429 with `code: rate_limited` and `Retry-After`. `CACHES` is `DatabaseCache`, so **deploy must run `manage.py createcachetable`**, and Render needs `NUM_PROXIES` set so per-IP limits see the client address. `escape_data` was already applied in every prompt; the Tutor, grading and pipeline injection tests were already in place.
- **Do not call the real Gemini API without the owner's say-so.** Run dev servers for browser checks with `AI_PROVIDER=fake` and seed rows for states that need a model answer.
- `common/prompt_safety.py` exports `escape_data(text)`. Every prompt builder uses it for document and user text inside data blocks.
- `useConcepts(projectId, readyCount)`: the count of ready materials is part of the query key, so concepts refetch when processing finishes.
- Types for API responses live in `src/api/types.ts`, one exported type per backend schema, with the same field names as the backend (snake_case is kept).
- Hooks live in `src/api/<feature>.ts` and are named `use<Thing>` for queries and `use<Verb><Thing>` for mutations. Query keys start with the feature name: `["materials", projectId]`.
- UI primitives in `src/components/ui/`: `Button`, `Card`, `Input`, `Textarea`, `Badge`, `Spinner`. Shared components in `src/components/shared/`: `PageHeader`, `EmptyState`, `ErrorState`, `StatusBadge`, `MasteryBar`.
- Component props:

```ts
Button:      { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md"; loading?: boolean } & ButtonHTMLAttributes
Card:        { title?: string; actions?: ReactNode; className?: string; children: ReactNode }
Input:       { label?: string; error?: string } & InputHTMLAttributes
Textarea:    { label?: string; error?: string } & TextareaHTMLAttributes
Badge:       { tone?: "gray" | "green" | "yellow" | "red" | "blue"; children: ReactNode }
Spinner:     { size?: "sm" | "md"; className?: string }      // renders a <span>, so it is valid inside <p> and <button>
PageHeader:  { title: string; subtitle?: string; actions?: ReactNode }
EmptyState:  { title: string; description?: string; action?: ReactNode }
ErrorState:  { error: unknown; onRetry?: () => void }
StatusBadge: { status: string }                       // maps queued/processing/ready/failed/active/completed/... to a Badge tone
MasteryBar:  { label: string; value: number; trend?: string }     // value is 0–1
```

- Registering a backend app (first task of each phase that adds one): `python manage.py startapp <name>`, delete `<name>/tests.py`, create `<name>/tests/__init__.py`, add `"<name>"` to `LOCAL_APPS` in `config/settings.py`, and mount its router in `config/api.py` with `from <name>.api import router as <name>_router` and `api.add_router("", <name>_router)`.
- Registering a project tab: add `{ path: "<tab>", label: "<Label>" }` to `projectTabs` and `{ path: "<tab>", element: <XPage /> }` to the `ProjectLayout` children in `src/routes.tsx`.
- Pages live in `src/features/<feature>/<Name>Page.tsx`. Project tab pages are child routes of `ProjectLayout` and are registered in `src/routes.tsx` and `projectTabs`.
- Every page renders a loading state (`Spinner`), an empty state and an error state.
- Frontend checks for a task: `npm run build` must pass with no TypeScript errors, followed by the manual check written in the task.

## C9. Running locally

```bash
# terminal 1 — API
cd backend && source .venv/bin/activate && python manage.py runserver 8000
# terminal 2 — worker
cd backend && source .venv/bin/activate && python manage.py run_worker
# terminal 3 — frontend
cd frontend && npm run dev          # http://localhost:5173
```
