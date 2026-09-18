# AI Study Companion

An AI-powered learning workspace: upload your own material, learn it with a grounded AI Tutor, get tested with an adaptive quiz, track concept mastery and growth, and get a concrete recommendation on what to study next.

Built for the AI Study Companion challenge (Candidate: **Nowshin Farhana**).

---

## Table of Contents

- [Overview](#overview)
- [Core Learning Loop](#core-learning-loop)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the App](#running-the-app)
- [Testing](#testing)
- [AI Evaluation](#ai-evaluation)
- [Admin Dashboard](#admin-dashboard)
- [Deployment](#deployment)
- [AI Usage Documentation](#ai-usage-documentation)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)

---

## Overview

The product answers three questions continuously as a user learns:

1. **What am I learning?** — Spaces, Projects, goals, materials, concepts.
2. **How well am I learning it?** — quizzes, assessments, Tutor interactions, mastery evidence.
3. **What should I do next?** — growth analysis converted into a concrete recommendation.

Learning should not be a set of disconnected AI features bolted onto a CRUD app. Every part of this system — retrieval, the Tutor, the quiz, mastery, recommendations — reads and writes the same underlying Project context.

## Core Learning Loop

```
Create Space → Create Project → Add Material → Process & Understand
    → Learn with AI Tutor → Take Adaptive Quiz → Evaluate Understanding
    → Update Concept Mastery → Analyze Growth → Recommend Next Action
    → Continue Learning
```

## Features

### Learner-facing

| Feature | Description |
|---|---|
| **Auth** | JWT-based sign-up / sign-in |
| **Spaces & Projects** | Hierarchical organization with per-Project data isolation |
| **Materials** | PDF upload, processed asynchronously (OCR → extraction → concept extraction → embeddings) |
| **AI Tutor** | Project-scoped chat, grounded in retrieved material, with source citations |
| **Unsupported-question handling** | Explicitly declines to answer when the material lacks sufficient evidence, rather than fabricating |
| **Adaptive Quiz** | Multiple-choice and open-ended questions; selection driven by mastery, recent mistakes, and difficulty — not a fixed ladder |
| **Open-ended grading** | AI-evaluated for understanding, accuracy, and relevance, with qualitative feedback, not just a score |
| **Concept Mastery** | Per-concept mastery estimate that updates as evidence accumulates |
| **Growth Analysis** | Tracks concepts as improving, stable, or needing attention over time |
| **Recommendations** | Concrete, specific "what to do next" generated from mastery, mistakes, and the learning goal |
| **Analytics** | Project-level and global rollups of activity, performance, and concept trends |
| **Persistent context** | Relevant learning context (goal, history, mistakes) carried across sessions without resending full history to every AI request |

### Admin-facing

| Feature | Description |
|---|---|
| **Overview** | Platform-wide stats |
| **Users** | Searchable user list; drill into any user's full learning journey |
| **Activity** | Filterable event log (user, Space, Project, type, time) |
| **AI Usage** | Token usage and estimated cost per model, per time window |
| **Evals** | Stored results from the automated AI quality suite, per run, with git commit |
| **Jobs** | Background job queue summary — processed, pending, failed |

## Architecture

```
Frontend (React + Vite)
        │
        ▼
API Layer (Django + django-ninja)
        │
        ▼
Business Logic
 ├── Learning (workspace, materials, learning)
 ├── AI (tutor, assessment, ai)
 ├── Analytics & Admin (insights)
 └── Events (background jobs)
        │
        ▼
Data & Knowledge
 ├── PostgreSQL (Supabase) — core relational data
 ├── pgvector — chunk embeddings for retrieval
 └── Local / S3 storage — uploaded materials
        │
        ▼
Background Processing (Postgres-backed job queue + worker)
        │
        ▼
AI / External Services (Gemini — generation, embeddings)
        │
        ▼
Observability (AI usage logs, eval runs, job status)
```

**Key decisions:**

- **django-ninja** over DRF for a faster, typed, OpenAPI-native API layer.
- **pgvector** for retrieval rather than a separate vector database — one less moving part, transactional consistency with the rest of the app's data, and sufficient for prototype scale.
- **Postgres-backed job queue** instead of Celery/Redis — fewer infrastructure dependencies to deploy and operate for a 3–4 day prototype, while still providing async processing, retries, and recovery of stuck jobs.
- **Gemini Flash-Lite** as the default model for both "fast" and "strong" tiers — the free tier gives enough quota (~500 req/day) to develop and demo without cost; `AI_MODEL_STRONG` is swappable via environment variable for a paid key.

## Tech Stack

**Backend:** Django 5, django-ninja, django-ninja-jwt, psycopg 3, pgvector, PyMuPDF, google-genai, pydantic, gunicorn, whitenoise, sentry-sdk, pytest + pytest-django

**Frontend:** React 19, TypeScript, Vite, TanStack Query, React Router, Recharts, Tailwind CSS, Vitest + Testing Library

**Data:** PostgreSQL with the `pgvector` extension (Supabase)

**AI:** Google Gemini (generation, structured output, embeddings)

## Project Structure

```
farhana_task/
├── backend/
│   ├── accounts/       # auth, users
│   ├── workspace/      # Spaces, Projects
│   ├── materials/      # uploads, chunks, embeddings, pgvector migration
│   ├── tutor/          # AI Tutor, retrieval, citations
│   ├── assessment/     # quiz, grading
│   ├── learning/       # mastery, growth
│   ├── insights/       # recommendations, analytics, admin API
│   ├── events/         # background job queue + worker
│   ├── ai/             # AI provider abstraction, evals
│   ├── common/         # shared utilities
│   └── config/         # Django settings, root API router
├── frontend/
│   └── src/
│       ├── api/
│       ├── auth/
│       ├── features/   # Spaces, Projects, Tutor, Quiz, Analytics, Admin
│       └── components/
└── docs/
    ├── PROMPTS.md       # development prompts used with AI tools
    └── EVALUATION.md    # eval suite results, generated by run_evals
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 20+
- PostgreSQL with the **pgvector** extension (a hosted option like [Supabase](https://supabase.com) or [Neon](https://neon.tech) works well and ships pgvector pre-enabled)
- A [Gemini API key](https://aistudio.google.com/)

### Setup

```bash
git clone <repo-url>
cd farhana_task

# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

Copy the example env files and fill in real values:

```bash
cp .env.example .env                     # project root
cp frontend/.env.example frontend/.env
```

## Environment Variables

Root `.env` (loaded by the backend):

| Variable | Description |
|---|---|
| `DJANGO_DEBUG` | `true` for local dev |
| `DJANGO_SECRET_KEY` | set a real value outside DEBUG |
| `ALLOWED_HOSTS` / `CORS_ALLOWED_ORIGINS` | comma-separated hosts/origins |
| `DATABASE_URL` | Postgres connection string (must support pgvector) |
| `AI_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | your Gemini API key |
| `AI_MODEL_FAST` / `AI_MODEL_STRONG` / `AI_MODEL_EMBED` | model names per tier |
| `TUTOR_MIN_SIMILARITY` | retrieval similarity threshold |
| `DEMO_PASSWORD` / `ADMIN_PASSWORD` | required when `DJANGO_DEBUG=false`, used by `seed_demo` |
| `STORAGE_BACKEND`, `S3_*` | production file storage (optional locally) |
| `SENTRY_DSN` | optional error tracking |

`frontend/.env`:

| Variable | Description |
|---|---|
| `VITE_API_URL` | backend base URL, e.g. `http://localhost:8000` |

**Never commit `.env` with real secrets.** Only `.env.example` should be in the repository.

## Running the App

Four processes, each in its own terminal:

```bash
# 1. Backend
cd backend && source venv/bin/activate
python manage.py migrate
python manage.py createcachetable
python manage.py seed_demo
python manage.py runserver 8000

# 2. Background worker (required for material processing, uploads)
cd backend && source venv/bin/activate
python manage.py run_worker

# 3. Frontend
cd frontend
npm run dev
```

Open **http://localhost:5173**.

**Seeded accounts** (created by `seed_demo`; local defaults apply only when `DJANGO_DEBUG=true`):

- Learner — `demo@example.com` / `demo12345`
- Admin — `admin@example.com` / `admin12345`

API docs: **http://localhost:8000/api/docs**
Django admin: **http://localhost:8000/django-admin/**

## Testing

```bash
cd backend && source venv/bin/activate
pytest
```

Covers authentication, Project-level data isolation, core business logic, grounded Tutor behavior, unsupported-question refusal, structured quiz output, mastery updates, and background job handling.

```bash
cd frontend
npm test
```

## AI Evaluation

```bash
cd backend && source venv/bin/activate
python manage.py run_evals --fake                            # offline smoke test, no API calls
python manage.py run_evals --fresh --suite retrieval          # real run, one suite
python manage.py run_evals --markdown ../docs/EVALUATION.md   # full run, all suites
```

Each real run stores an `EvalRun` (metrics, per-case results, git commit) visible under **Admin → Evals**. Suites and minimum thresholds:

| Suite | Metric | Minimum |
|---|---|---|
| Retrieval | recall@6 | 0.75 |
| Tutor | answer rate / citation hit rate | 0.75 / 0.70 |
| Tutor | refusal accuracy | 0.80 |
| Grading | agreement with hand-labelled scores (±0.2) | 0.60 |
| Structured output | schema validity | 0.90 |
| Recommendations | rule pass rate | 1.00 |

See [`docs/EVALUATION.md`](docs/EVALUATION.md) for the full methodology and latest results.

## Admin Dashboard

Log in as `admin@example.com` and open **Platform Admin** for platform-wide visibility: users, activity, AI usage/cost, AI evaluation results, and background job health.

## Deployment

The app is deployed at: **`<add your live URL here>`**

Deployment notes:
- Backend served via `gunicorn` behind `whitenoise` for static files.
- `STORAGE_BACKEND=s3` for production file storage (materials, media).
- `DEMO_PASSWORD` / `ADMIN_PASSWORD` must be set explicitly in production (`seed_demo` refuses local defaults when `DJANGO_DEBUG=false`).
- `SENTRY_DSN` optional for error tracking.

## AI Usage Documentation

**AI used to build this product:** *(fill in your actual tools, e.g. Claude Code / GitHub Copilot / ChatGPT, and what they were used for — architecture drafting, debugging, boilerplate, etc.)*

**AI used by the product itself:**
- **Tutor** — grounded Q&A over Project material via Gemini, with retrieval-based citation.
- **Quiz generation** — structured question generation, validated against a schema before persisting.
- **Open-ended grading** — qualitative evaluation of learner answers.
- **Recommendations** — rule-informed synthesis of mastery, mistakes, and goals into a next action.
- **Embeddings** — `gemini-embedding-001` for chunk and query vectors used in retrieval.

Full development prompts are in [`docs/PROMPTS.md`](docs/PROMPTS.md), organized by architecture, frontend, backend, database, AI, debugging, testing, and documentation.

## Known Limitations

- Gemini free-tier rate limits constrain both real-time usage and eval run frequency (`EVAL_SLEEP_SECONDS` throttles eval runs to stay under quota).
- `AI_MODEL_STRONG` defaults to the same lightweight model as `AI_MODEL_FAST`; a paid key is needed to point it at a stronger model.
- Background job queue is Postgres-backed rather than a dedicated broker — sufficient for prototype scale, not built for high job throughput.
- *(add any others specific to your implementation — retrieval quality on scanned/complex PDFs, quiz difficulty calibration, etc.)*

## Future Improvements

- Streaming Tutor responses.
- Richer document understanding (tables, diagrams).
- Provider abstraction beyond Gemini.
- Automated regression evaluation on every deploy.
- Improved background job retry/backoff strategy.

---

## License

*(add your license here)*
