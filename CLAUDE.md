# CLAUDE.md

This file provides **project knowledge** to Claude Code.
Behavior rules and workflow live in `.claude/output-styles/feedpilot.md`.

---

## SESSION STARTUP — MANDATORY PROTOCOL

**Every session, before writing a single line of code, run these commands in order:**

### Step 1 — Orient yourself in the file system

```bash
ls feedpilot/docs/tickets/              # What tickets exist — NEVER create duplicates
ls feedpilot/backend/app/               # Confirm layer structure
ls feedpilot/backend/app/services/      # Existing services
ls feedpilot/backend/app/repositories/  # Existing repositories
ls feedpilot/backend/app/api/           # Existing routes
ls feedpilot/frontend/app/              # Frontend pages
```

### Step 2 — Read these files (in this order)

```
1. feedpilot/docs/STATUS.md      — current verified state, known gaps, test results
2. feedpilot/docs/BACKLOG.md     — all FEED-tickets with status (✅ done / ⬜ open)
3. feedpilot/docs/ROADMAP.md     — sprint plan and what comes next
```

### Step 3 — State your session context

Before anything else, write:
- **Current sprint:** (e.g. Sprint 1.5 / Sprint 2)
- **Next available FEED-number:** (highest existing + 1)
- **Working on:** which FEED-ticket this session
- **Files to be touched:** explicit list
- **Risk level:** low / medium / high

### Rules that follow from the above

- Never create a folder or file without first verifying it doesn't already exist
- Never create a ticket for work that's already marked ✅ in BACKLOG.md
- Never start coding before stating your session context (Step 3)
- The ticket comes first — write the ticket file, wait for review, then implement

---

## Workflow — One file at a time

```
1. Create ticket (docs/tickets/FEED-XXX.md) → wait for review
2. Write test file first (TDD) → wait for review
3. Write implementation file → wait for review
4. Repeat step 3 for each additional file
5. Update docs/STATUS.md and docs/BACKLOG.md when done
```

**Never change more than one file per step. Never skip review.**

---

## Project Overview

FeedPilot is an AI-powered product data enrichment platform. E-commerce merchants upload CSV/XLSX product feeds; the system scores data quality, detects return risk, and enriches product fields using Anthropic Claude.

---

## Stack

- **Backend:** FastAPI + SQLAlchemy 2 + PostgreSQL 15 (pgvector) + ARQ/Redis async jobs
- **Frontend:** Next.js 14 App Router (TypeScript, Tailwind CSS)
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) for enrichment + vision; OpenAI `text-embedding-3-small` for RAG

---

## Running the Project

```bash
# Start all services (backend on :8010, postgres on :5433, redis on :6380)
docker compose up --build

# Frontend (separate, not in Compose)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

Backend API docs: http://localhost:8010/docs

---

## Common Commands

```bash
# Backend tests (always via Docker — local pytest fails without deps)
docker compose exec backend pytest tests/

# Run a single test file
docker compose exec backend pytest tests/test_ingest.py -v

# Frontend lint
cd frontend && npm run lint

# Frontend tests
cd frontend && npm test -- --runInBand

# Apply DB migrations
docker compose exec backend alembic upgrade head

# Tail worker logs
docker compose logs -f worker
```

**Verified baseline:** 71 backend tests pass, 14 frontend tests pass, lint passes.

---

## Key Files (Quick Reference)

| File | Layer | Role |
|---|---|---|
| `backend/app/services/enrichment_service.py` | Service | Core enrichment orchestration |
| `backend/app/services/enrichment_planner.py` | Service | Deterministic model/tool/field planner |
| `backend/app/services/preflight_service.py` | Service | Cost estimation before bulk jobs |
| `backend/app/services/field_metadata.py` | Service | Per-field enrichment metadata registry |
| `backend/app/core/ai.py` | Core | Claude/OpenAI clients, retry logic |
| `backend/app/schemas/canonical.py` | Schema | `CanonicalProduct` — source of truth for AI input |
| `backend/app/workers/tasks.py` | Worker | ARQ bulk enrichment task |
| `backend/app/repositories/product_repository.py` | Repository | pgvector semantic search |
| `backend/app/repositories/catalog_repository.py` | Repository | Paginated catalog queries |
| `backend/app/repositories/stats_repository.py` | Repository | Aggregate stats queries incl. avg_enrichment_score |
| `frontend/lib/api.ts` | Frontend | All API calls (axios instance) |
| `frontend/lib/types.ts` | Frontend | Centralised TypeScript types incl. PreflightResponse |
| `frontend/components/ui/PreflightModal.tsx` | Frontend | Preflight confirmation modal (dumb component) |

---

## Architecture

### Backend Layer Separation

All code in `backend/app/` follows strict layers — never skip them:

| Layer | Path | Responsibility |
|---|---|---|
| API | `api/` | HTTP only — parse request, call service, return response |
| Service | `services/` | All business logic and orchestration |
| Repository | `repositories/` | All SQLAlchemy queries |
| Model | `models/` | ORM definitions (Column-style, not Mapped[]) |
| Schema | `schemas/` | Pydantic v2 response models (use `ConfigDict`) |

FastAPI dependency injection (`Depends()`) wires repositories into services and services into routes.

### Enrichment Pipeline

`POST /api/v1/products/{sku_id}/enrich` → `EnrichmentService.enrich_product()`:

1. Fetch `Product` ORM → convert to `CanonicalProduct` (`schemas/canonical.py`)
2. `plan_enrichment(missing_fields)` → `EnrichmentPlan` (model, tools, target fields, RAG flag)
3. `semantic_search()` via pgvector **only if** `plan.use_rag = True`
4. `build_enrichment_payload()` — minimal input, only relevant fields
5. `ask_claude()` with `enrichment_v2` prompt + user message JSON
6. Parse JSON via `_extract_json()` → validate with `EnrichmentAIOutput` Pydantic schema
7. Persist `AnalysisResult`, log `AIRequestMetadata`

Bulk enrichment: ARQ background task (`workers/tasks.py::enrich_bulk_task`), updates `Job.processed`/`Job.failed` per product.

### AI Client (`core/ai.py`)

- `ask_claude()` — text enrichment; raises `RuntimeError` if `stop_reason == "max_tokens"`
- `ask_claude_vision()` — base64 image + text; same retry logic
- Retry: 4 attempts with delays [2, 5, 10, 20]s on HTTP 529 (overloaded)

### Async Jobs

`Job` model tracks status (`pending → running → completed/failed`), `processed`, `failed`, `total`, `result`, `error`. Poll via `GET /api/v1/jobs/{job_id}`.

### Frontend

All pages are `"use client"` components under `app/`. API calls go through `lib/api.ts` (axios instance at `http://localhost:8010`). Types centralised in `lib/types.ts`.

Design system: Material Design 3 tokens in `tailwind.config.ts`. Primary: `#072078`, background: `#fcf9f5`. Icons: `material-symbols-outlined`.

### Feed Ingestion

`POST /api/v1/ingest/csv|xlsx` → `IngestionService` auto-detects feed schema (Shopify, WooCommerce, Google Shopping, Akeneo, or generic CSV). Structured sub-fields land in `Product.attributes`; remaining fields go to `Product.raw_data`.

---

## AI Control Rule

AI behavior must be controlled by code, not by prompts alone. Application code must own:
- allowed input/output schemas
- parsing and validation
- allowed fields and enum values
- scoring/risk rules that affect product state
- fallback and error handling
- persistence decisions
- user-visible status transitions

Every bulk enrichment must follow: **preflight → confirm → queue → validate → store**

Enrichment pipeline: `extract → normalize → enrich → validate → store`

Never send a full Product ORM to Claude — always use `CanonicalProduct`.

---

## Common Mistakes in This Codebase (DO NOT Repeat)

- Do NOT use `Mapped[]` in ORM models — use Column-style only
- Do NOT call `semantic_search` outside `EnrichmentService`
- Do NOT set `max_tokens` below 4096 — all priority levels use 4096
- Do NOT write to `job.result` before all products are processed
- Do NOT send full Product ORM to Claude — always use `CanonicalProduct`
- Do NOT query the DB directly from a service — use repositories
- Do NOT put business logic in API routes
- Docker ARM64: never install packages requiring native compilation without checking ARM64 compatibility first
- Do NOT trust AI output without validating against Pydantic schemas first
- Do NOT hardcode model ID in service layer — model comes from `EnrichmentPlan.model`

---

## Sprint Status (read BACKLOG.md for full detail)

- **Sprint 1 — MVP Frontend:** ✅ Done (FEED-001–013, some gaps: FEED-009, FEED-013)
- **Sprint 1.5 — Stabilisering:** ✅ Done (FEED-060–070)
- **Sprint 2 — Auth + CI/CD:** 🔄 In progress (FEED-071–073 done, FEED-014+ not started)
- **Sprint 3 — Multi-tenant:** ⬜ Not started
- **Next ticket number: FEED-074**

### Senaste session — 2026-05-15
- FEED-071: `avg_enrichment_score` tillagd i hela stats-kedjan, dashboard visar riktiga data
- FEED-072: Enrichment quality investigation — Hypotes A bekräftad, pipeline fungerar korrekt, testdatan är skev (inte ett pipeline-fel)
- FEED-073: Preflight modal + progressbar implementerad och testad
- ADR-006: TDD + en-fil-i-taget workflow dokumenterat
- **Nästa prioritet: Auth — FEED-014 (JWT + login page)**

---

## Code Review Workflow (Claude Code ↔ Codex)

**Claude Code** — implementation, tests, architecture adherence
**Codex (ChatGPT)** — code review, critique, alternative approaches

When preparing a diff for Codex review (`/codex-review`), always include:
- The relevant Pydantic schema from `schemas/`
- The layer this file belongs to (API / Service / Repository / Model / Schema)
- The ARQ task signature if async is involved
- Any enrichment pipeline step being modified

---

## Key Environment Variables (Backend)

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=postgresql://feedpilot:feedpilot@postgres:5432/feedpilot
REDIS_URL=redis://redis:6379
```

---

## Definition of Done (Checklist)

- [ ] Ticket created and reviewed before any code was written
- [ ] Tests written before or alongside implementation (TDD)
- [ ] Layer separation respected (no logic in API, no DB in Service)
- [ ] Error handling: HTTP exceptions in API, `RuntimeError` in Service
- [ ] ARQ job: `processed`/`failed`/`total` updated atomically
- [ ] AI output validated via Pydantic before persistence
- [ ] Token usage logged per enrichment call
- [ ] `CanonicalProduct` used as AI input (not raw ORM)
- [ ] Minimal diff — no unrelated changes
- [ ] `docker compose exec backend pytest tests/` passes
- [ ] `cd frontend && npm run lint && npm test -- --runInBand` passes
- [ ] `docs/STATUS.md` and `docs/BACKLOG.md` updated
