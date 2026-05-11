# FeedPilot — Projektöversikt

FeedPilot är en AI-driven plattform för produktdataanrikning. E-handelsmerchandiser laddar upp CSV/XLSX-produktflöden; systemet poängsätter datakvalitet, detekterar returrisker och anrikar produktfält med Claude.

---

## Teknikstack

| Lager | Teknologi |
|---|---|
| Backend | FastAPI · Python 3.11 · SQLAlchemy 2.0 · Pydantic v2 |
| Databas | PostgreSQL 15 + pgvector |
| Jobbkö | Redis 7 + ARQ (async Python) |
| AI | Claude `claude-sonnet-4-6` (text + vision) · OpenAI `text-embedding-3-small` (RAG) |
| Frontend | Next.js 14 App Router · TypeScript · Tailwind CSS (Material Design 3) |
| Infra | Docker Compose (lokalt) · GCP Cloud Run + Cloud SQL (prod) |

---

## Tjänster (docker-compose)

| Tjänst | Port | Syfte |
|---|---|---|
| `backend` | 8010 | FastAPI + uvicorn |
| `postgres` | 5433 | PostgreSQL med pgvector |
| `redis` | 6380 | Jobbkö |
| `worker` | — | ARQ async-worker |

---

## Snabbstart

```bash
cp .env.example .env
# fyll i ANTHROPIC_API_KEY och OPENAI_API_KEY

docker compose up --build

# Frontend (separat)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

- Backend API: http://localhost:8010
- API-dokumentation: http://localhost:8010/docs

---

## Arkitektur

### Backend — 5 strikta lager

| Lager | Sökväg | Ansvar |
|---|---|---|
| API | `api/` | Enbart HTTP — parsar request, anropar service, returnerar response |
| Service | `services/` | All affärslogik och orkestrering |
| Repository | `repositories/` | Alla SQLAlchemy-frågor |
| Model | `models/` | ORM-definitioner (Column-stil, inte `Mapped[]`) |
| Schema | `schemas/` | Pydantic v2-responsmodeller (`ConfigDict`) |

FastAPI dependency injection (`Depends()`) kopplar samman lagren.

### Anrikningspipeline

`POST /api/v1/products/{sku_id}/enrich` → `EnrichmentService.enrich_product()`:

1. Hämta `Product` ORM → konvertera till `CanonicalProduct` (`schemas/canonical.py`)
2. Beräkna `enrichment_priority` och `max_tokens` (4 096 för alla nivåer)
3. pgvector semantisk sökning — hämtar 3 liknande produkter som RAG-kontext
4. Anropa `ask_claude()` med `enrichment_v2`-prompt + RAG-kontext
5. Parsa JSON-svar via `_extract_json()` (brace-depth scanning — klarar trunkering)
6. Persistera `AnalysisResult`, returnera strukturerad dict

Bulkanrikning körs som ARQ-bakgrundsuppgift (`workers/tasks.py::enrich_bulk_task`). Frontend pollar `GET /jobs/{job_id}` var 3:e sekund.

### AI-klient (`core/ai.py`)

- `ask_claude()` — textanrikning; kastar `RuntimeError` om `stop_reason == "max_tokens"`
- `ask_claude_vision()` — base64-bild + text; samma retry-logik
- Retry: 4 försök med fördröjning [2, 5, 10, 20] s vid HTTP 529 (overloaded)

---

## Databasmodeller

| Modell | Syfte |
|---|---|
| `Product` | Kärnproduktpost + bild-URL |
| `AnalysisResult` | Anrikningspoäng, problem, anrikade fält |
| `Embedding` | Vektorbäddar för likhetssökning |
| `Variant` | SKU-varianter (färg, storlek, SEO-fält) |
| `Job` | Async-jobbspårning (pending → running → completed/failed) |
| `CustomerPimConfig` | PIM-integrationskonfiguration (ej aktivt) |

---

## API-endpoints

| Metod | Sökväg | Beskrivning |
|---|---|---|
| `GET` | `/products/{sku_id}` | Produktdetalj + anrikning |
| `POST` | `/products/{sku_id}/enrich` | Starta enskild anrikning |
| `GET` | `/catalog` | Paginerad katalog med filter |
| `POST` | `/enrich/bulk` | Köa bulkanrikning |
| `POST` | `/ingest/csv` | Importera CSV-flöde |
| `POST` | `/ingest/xlsx` | Importera XLSX-flöde |
| `GET` | `/jobs/{job_id}` | Async-jobbstatus |
| `GET` | `/stats` | Anrikningsstatistik |
| `POST` | `/images/analyze-url` | Analysera produktbild via URL |
| `POST` | `/images/analyze-upload/{sku_id}` | Analysera uppladdad bild |
| `GET` | `/health` | Hälsokontroll |

---

## Flödeskällor (auto-detekteras vid inläsning)

Shopify · WooCommerce · Google Shopping · Akeneo · Generisk CSV

Strukturerade delfält (brand, color, material, size, gender) läggs i `Product.attributes` (JSON-kolumn); övriga fält hamnar i `Product.raw_data`.

---

## Frontend-sidor

| Route | Syfte |
|---|---|
| `/` | Landningssida |
| `/dashboard` | Översikt och statistik |
| `/catalog` | Paginerad produktkatalog med filter |
| `/products/[sku_id]` | Produktdetalj, inline anrikningsgranskning, bildanalys |
| `/variants/[sku_id]` | Variantdetalj och SEO-anrikning |
| `/image-analysis` | Fristående bildanalysverktyg |

Designsystem: Material Design 3-tokens, primärfärg `#072078`, bakgrund `#fcf9f5`, ikoner via `material-symbols-outlined`.

---

## Viktiga filer

| Fil | Lager | Roll |
|---|---|---|
| `backend/app/services/enrichment_service.py` | Service | Kärnanrikningsorkestrering |
| `backend/app/core/ai.py` | Core | Claude/OpenAI-klienter, retry-logik |
| `backend/app/schemas/canonical.py` | Schema | `CanonicalProduct` — sanningskälla för AI-input |
| `backend/app/workers/tasks.py` | Worker | ARQ bulk-anrikning |
| `backend/app/repositories/product_repository.py` | Repository | pgvector semantisk sökning |
| `frontend/lib/api.ts` | Frontend | Alla API-anrop (axios-instans) |
| `frontend/lib/types.ts` | Frontend | Centraliserade TypeScript-typer |

---

## Miljövariabler

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=postgresql://feedpilot:feedpilot@postgres:5432/feedpilot
REDIS_HOST=redis
REDIS_PORT=6379
NEXT_PUBLIC_BACKEND_URL=http://localhost:8010
```

---

## Nuläge

**Klart:** Dashboard, katalog, produktdetalj, CSV/XLSX-inläsning, anrikningspipeline, bildanalys (Claude Vision), async-jobbkö.

**Planerat/tomt:** Variantsida, dedikerad bildanalyssida, PIM-integration (`CustomerPimConfig` finns men används ej).

**Kända buggar:**
1. Klick-propagation i anrikningstabellen navigerar bort — fix: `e.stopPropagation()` på tabellrad
2. Dashboardstatistik (Feed Quality Score, AI Confidence Trend, kategorier, senaste aktivitet) är hårdkodad mockdata — behöver nya endpoints: `GET /stats/recent`, `/stats/categories`, `/stats/quality`

---

## Vanliga misstag (undvik)

- Använd INTE `Mapped[]` i ORM-modeller — Column-stil enbart
- Anropa INTE `semantic_search` utanför `EnrichmentService`
- Sätt INTE `max_tokens` under 4096 — alla prioritetsnivåer använder 4096
- Skriv INTE till `job.result` innan alla produkter är processade
- Skicka INTE fullt `Product`-ORM till Claude — använd alltid `CanonicalProduct`
- Fråga INTE databasen direkt från en service — använd repositories
- Lägg INTE affärslogik i API-routes
- Lita INTE på AI-output utan validering mot Pydantic-schemas

---

## Definition of Done

- [ ] Lagerseparation respekterad
- [ ] Felhantering: HTTP-exceptions i API, `RuntimeError` i Service
- [ ] ARQ-jobb: `processed`/`failed`/`total` uppdaterade atomärt
- [ ] AI-output validerat via Pydantic innan persistering
- [ ] Token-användning loggad per anrikningsanrop
- [ ] `CanonicalProduct` använt som AI-input (inte rå ORM)
- [ ] Minimalt diff — inga orelaterade ändringar
- [ ] Test tillagt/uppdaterat för ny logik
