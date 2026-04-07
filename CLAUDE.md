# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FeedPilot is an AI-powered product data enrichment platform. E-commerce merchants upload CSV/XLSX product feeds; the system scores data quality, detects return risk, and enriches product fields using Anthropic Claude.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2 + PostgreSQL 15 (pgvector) + ARQ/Redis async jobs
- **Frontend:** Next.js 14 App Router (TypeScript, Tailwind CSS)
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) for enrichment + vision; OpenAI `text-embedding-3-small` for RAG

## Running the project

```bash
# Start all services (backend on :8010, postgres on :5433, redis on :6380)
docker compose up --build

# Frontend (separate, not in Compose)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

Backend API docs: http://localhost:8010/docs

## Common commands

```bash
# Backend tests (from repo root)
docker compose exec backend pytest tests/

# Run a single test file
docker compose exec backend pytest tests/test_ingest.py -v

# Frontend lint
cd frontend && npm run lint

# Apply DB migrations
docker compose exec backend alembic upgrade head

# Tail worker logs
docker compose logs -f worker
```

## Architecture

### Backend layer separation

All code in `backend/app/` follows strict layers — never skip them:

| Layer | Path | Responsibility |
|---|---|---|
| API | `api/` | HTTP only — parse request, call service, return response |
| Service | `services/` | All business logic and orchestration |
| Repository | `repositories/` | All SQLAlchemy queries |
| Model | `models/` | ORM definitions (Column-style, not Mapped[]) |
| Schema | `schemas/` | Pydantic v2 response models (use `ConfigDict`) |

FastAPI dependency injection (`Depends()`) wires repositories into services and services into routes.

### Enrichment pipeline

`POST /api/v1/products/{sku_id}/enrich` → `EnrichmentService.enrich_product()`:

1. Fetch `Product` ORM → convert to `CanonicalProduct` (structured schema in `schemas/canonical.py`)
2. Determine `enrichment_priority` and `max_tokens` from `MAX_TOKENS_BY_PRIORITY` (all levels: 4096)
3. Semantic search via pgvector (`repositories/product_repository.py::semantic_search`) for RAG context
4. Call `ask_claude()` with `enrichment_v2` prompt + user message JSON
5. Parse JSON response via `_extract_json()` (brace-depth scanning — handles truncation)
6. Persist `AnalysisResult`, return structured dict

Bulk enrichment runs as an ARQ background task (`workers/tasks.py::enrich_bulk_task`), updating `Job.processed`/`Job.failed` and `job.result` after each product.

### AI client (`core/ai.py`)

- `ask_claude()` — text enrichment; raises `RuntimeError` if `stop_reason == "max_tokens"`
- `ask_claude_vision()` — base64 image + text; same retry logic
- Retry: 4 attempts with delays [2, 5, 10, 20]s on HTTP 529 (overloaded)

### Async jobs

`Job` model tracks status (`pending → running → completed/failed`), `processed`, `failed`, `total`, `result`, `error`. Poll via `GET /api/v1/jobs/{job_id}`.

### Frontend

All pages are `"use client"` components under `app/`. API calls go through `lib/api.ts` (axios instance pointing at `http://localhost:8010`). Types are centralised in `lib/types.ts`.

Design system uses Material Design 3 tokens defined in `tailwind.config.ts`. Primary: `#072078`, background: `#fcf9f5`. Use `material-symbols-outlined` for icons.

### Feed ingestion

`POST /api/v1/ingest/csv|xlsx` → `IngestionService` auto-detects feed schema (Shopify, WooCommerce, Google Shopping, Akeneo, or generic CSV). Structured sub-fields (brand, color, material, size, gender) land in `Product.attributes` JSON column; remaining fields go to `Product.raw_data`.

## Key environment variables (backend)

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=postgresql://feedpilot:feedpilot@postgres:5432/feedpilot
REDIS_URL=redis://redis:6379
```
## Role: Claude Code (Implementation Agent)

You are responsible for writing and modifying code in this repository.

Your goal:
- produce clean, production-ready code
- follow architecture strictly
- keep changes minimal and precise

---

## Mandatory First Step

Before ANY change:
- read this file completely
- understand project structure
- respect all constraints

---

## Core Principles

- Follow existing patterns (DO NOT invent new ones)
- Prefer minimal diffs
- Do not break existing functionality
- Keep code simple and readable

---

## Architecture (STRICT)

Layer separation must ALWAYS be respected:

| Layer | Responsibility |
|------|----------------|
| API | HTTP only |
| Service | business logic |
| Repository | database access |
| Model | ORM |
| Schema | API response models |

### NEVER:
- put logic in API routes
- query DB in services
- mix schemas and ORM models

---

## Backend Rules

- Use FastAPI patterns
- Use dependency injection (`Depends`)
- Keep services pure (no HTTP, no DB direct)
- Repositories handle ALL queries
- Always handle errors properly

---

## Enrichment Flow Rules

When working with enrichment:

- Always go through `EnrichmentService`
- Respect:
  - priority logic
  - token limits
  - retry handling
- Ensure `_extract_json()` safety
- Never assume valid AI output

---

## Async Jobs (ARQ)

- Maintain job state integrity
- Update:
  - processed
  - failed
  - total
- Handle partial failures safely

---

## Frontend Rules

- Use existing API layer (`lib/api.ts`)
- Follow TypeScript strictly
- No `any` unless unavoidable
- Keep components consistent with design system

---

## Testing Rules

- Add/update tests when needed
- Do NOT skip tests silently
- Ensure new logic is testable

---

## What NOT to do

- Do NOT refactor unrelated code
- Do NOT introduce new architecture patterns
- Do NOT rename things unnecessarily
- Do NOT over-engineer

---

## Definition of Done

Code is complete when:

- follows architecture
- minimal diff
- handles errors properly
- testable and stable
- no obvious edge cases missing

---

## Output Style

- clean code
- clear naming
- no unnecessary comments
- production-ready