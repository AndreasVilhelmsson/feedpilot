# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Startup

At the start of each session, state:
1. Which FEED-ticket you are working on
2. Which files will be touched
3. Estimated risk level (low / medium / high)

---

## Project Overview

FeedPilot is an AI-powered product data enrichment platform. E-commerce merchants upload CSV/XLSX product feeds; the system scores data quality, detects return risk, and enriches product fields using Anthropic Claude.

---

## Stack

- **Backend:** FastAPI + SQLAlchemy 2 + PostgreSQL 15 (pgvector) + ARQ/Redis async jobs
- **Frontend:** Next.js 14 App Router (TypeScript, Tailwind CSS)
- **AI:** Anthropic Claude (`claude-sonnet-4-5`) for enrichment + vision; OpenAI `text-embedding-3-small` for RAG

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

---

## Key Files (Quick Reference)

| File | Layer | Role |
|---|---|---|
| `backend/app/services/enrichment_service.py` | Service | Core enrichment orchestration |
| `backend/app/core/ai.py` | Core | Claude/OpenAI clients, retry logic |
| `backend/app/schemas/canonical.py` | Schema | `CanonicalProduct` — source of truth for AI input |
| `backend/app/workers/tasks.py` | Worker | ARQ bulk enrichment task |
| `backend/app/repositories/product_repository.py` | Repository | pgvector semantic search |
| `frontend/lib/api.ts` | Frontend | All API calls (axios instance) |
| `frontend/lib/types.ts` | Frontend | Centralised TypeScript types |

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

1. Fetch `Product` ORM → convert to `CanonicalProduct` (structured schema in `schemas/canonical.py`)
2. Determine `enrichment_priority` and `max_tokens` from `MAX_TOKENS_BY_PRIORITY` (all levels: 4096)
3. Semantic search via pgvector (`repositories/product_repository.py::semantic_search`) for RAG context
4. Call `ask_claude()` with `enrichment_v2` prompt + user message JSON
5. Parse JSON response via `_extract_json()` (brace-depth scanning — handles truncation)
6. Persist `AnalysisResult`, return structured dict

Bulk enrichment runs as an ARQ background task (`workers/tasks.py::enrich_bulk_task`), updating `Job.processed`/`Job.failed` and `job.result` after each product.

### AI Client (`core/ai.py`)

- `ask_claude()` — text enrichment; raises `RuntimeError` if `stop_reason == "max_tokens"`
- `ask_claude_vision()` — base64 image + text; same retry logic
- Retry: 4 attempts with delays [2, 5, 10, 20]s on HTTP 529 (overloaded)

### Async Jobs

`Job` model tracks status (`pending → running → completed/failed`), `processed`, `failed`, `total`, `result`, `error`. Poll via `GET /api/v1/jobs/{job_id}`.

### Frontend

All pages are `"use client"` components under `app/`. API calls go through `lib/api.ts` (axios instance pointing at `http://localhost:8010`). Types are centralised in `lib/types.ts`.

Design system uses Material Design 3 tokens defined in `tailwind.config.ts`. Primary: `#072078`, background: `#fcf9f5`. Use `material-symbols-outlined` for icons.

### Feed Ingestion

`POST /api/v1/ingest/csv|xlsx` → `IngestionService` auto-detects feed schema (Shopify, WooCommerce, Google Shopping, Akeneo, or generic CSV). Structured sub-fields (brand, color, material, size, gender) land in `Product.attributes` JSON column; remaining fields go to `Product.raw_data`.

---

## AI Control Rule

AI behavior must be controlled by code, not by prompts alone.

Prompts may guide tone, format, and task intent, but application code must own:
- allowed input/output schemas
- parsing and validation
- allowed fields and enum values
- scoring/risk rules that affect product state
- fallback and error handling
- persistence decisions
- user-visible status transitions

Never trust a prompt instruction as a safety boundary. If a rule matters to the product, enforce it in schemas, services, validators, repositories, or tests.

FeedPilot is an AI-driven enrichment system, not a prompt-based wrapper. Features such as web search, image analysis, model choice, RAG usage, and field selection must be activated explicitly by backend code/configuration. Do not rely on prompt text to make the model decide whether a tool is allowed or required.

Every large or bulk enrichment must follow this control flow:

1. **Preflight:** calculate product count, fields to process, estimated input/output tokens, estimated cost, required tools, and selected model strategy.
2. **User confirmation:** do not start the expensive run until the user confirms the preflight.
3. **Queue/batch execution:** process products in bounded batches or via ARQ.
4. **Per-product planning:** code decides fields, model, tools, and minimal input payload from field metadata.
5. **Validation:** parse and validate AI output before storing or exposing it.
6. **Observability:** log tokens, cost, model, tools, status, and errors per product/request.

The enrichment pipeline must be:

```
extract → normalize → enrich → validate → store
```

Minimize model input. Never send an entire product object by default. Send only fields relevant to the specific enrichment task, derived from canonical schema metadata and field complexity.

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

---

## Code Review Workflow (Claude Code ↔ Codex)

**Claude Code** — implementation, tests, architecture adherence  
**Codex (ChatGPT)** — code review, critique, alternative approaches

When preparing a diff for Codex review, always include:
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

## Implementation Workflow (MANDATORY)

Always work one file at a time. Never write multiple files in one step.

For each file, before writing any code:
1. State which file you are about to change and why
2. Explain the file's responsibility in the architecture
3. Explain how it connects to adjacent files (what calls it, what it calls)
4. Explain which pattern you are following and why
5. **Wait for explicit approval before writing code**

After writing the file:
6. Summarize what changed and what to verify
7. Ask if you should proceed to the next file

If a task requires multiple files, start by listing all files in order with a one-line reason for each. Then work through them one at a time, waiting for approval between each step.

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
  - token limits (4096 for all levels)
  - retry handling
- Ensure `_extract_json()` safety
- Never assume valid AI output
- Enforce AI output contracts in code, not only in prompt text
- Validate parsed AI fields against Pydantic/domain schemas before persistence
- Do not let Claude decide workflow state, database writes, allowed field names, or trust boundaries without code-side checks
- Add or preserve preflight before large/bulk enrichment runs
- Use backend field metadata to decide which fields, tools, and model are needed
- Minimize input tokens by sending only relevant canonical fields
- Log token usage, estimated/actual cost, selected model, tools used, and per-product outcome

---

## Async Jobs (ARQ)

- Maintain job state integrity
- Update atomically: `processed`, `failed`, `total`
- Handle partial failures safely
- Do NOT write to `job.result` before the full run is complete

---

## Frontend Rules

- Use existing API layer (`lib/api.ts`)
- Follow TypeScript strictly
- No `any` unless unavoidable
- Keep components consistent with design system (MD3 tokens, `#072078` primary)

---

## Testing Rules

- Add/update tests when needed
- Do NOT skip tests silently
- Ensure new logic is testable

---

## What NOT to Do

- Do NOT refactor unrelated code
- Do NOT introduce new architecture patterns
- Do NOT rename things unnecessarily
- Do NOT over-engineer

---

## Definition of Done (Checklist)

Code is complete when ALL of these are true:

- [ ] Layer separation respected (no logic in API, no DB in Service)
- [ ] Error handling: HTTP exceptions in API, `RuntimeError` in Service
- [ ] ARQ job: `processed`/`failed`/`total` updated atomically
- [ ] AI output validated via Pydantic before persistence
- [ ] Token usage logged per enrichment call
- [ ] `CanonicalProduct` used as AI input (not raw ORM)
- [ ] Minimal diff — no unrelated changes
- [ ] Test added/updated for new logic
- [ ] No obvious edge cases missing

---

## Output Style

- clean code
- clear naming
- no unnecessary comments
- production-ready
