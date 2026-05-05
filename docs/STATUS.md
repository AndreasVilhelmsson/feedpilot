# FeedPilot — Status

## Verifierat nuläge — 2026-05-01

Det tidigare statusläget beskriver främst vad som är byggt. Efter reverse engineering och testkörning behöver vi skilja på:

- **Byggt**: funktioner/filer finns.
- **Verifierat**: tester/lint passerar.
- **Reviewat**: arkitektur och kod har granskats mot önskad riktning.
- **Önskat läge**: AI-drivet enrichment-system styrt av kod, inte prompt.

### Samlad bedömning

| Område | Nuläge | Bedömning |
|---|---|---|
| Backend features | Många centrala flöden finns: ingest, enrichment, RAG, image analysis, jobs, variants | Byggt, men ojämnt reviewat |
| Frontend features | Dashboard, catalog, processing, product detail och tester finns | Delvis verifierat |
| Tester | Backend 24 tester passerar i Docker; frontend 7 tester passerar enligt FEED-060 baseline | Testtäckning är bättre men fortfarande låg jämfört med feature-yta |
| Lint | Frontend lint passerar efter fix | Verifierat |
| Backend lokal miljö | `pytest` lokalt failar utan backend deps (`fastapi` saknas) | Miljö behöver dokumenteras/fixas |
| Docker runtime | API, postgres, redis och worker kör | Verifierat via `docker compose ps` |
| AI-arkitektur | Prompt manager och AI core finns | Behöver flyttas mot kodstyrd enrichment |
| Preflight/kostnadskontroll | Backend preflight finns som första pass via FEED-063 | Frontend UI och confirmation enforcement återstår |
| Observability | Token usage finns delvis, men kostnad/model/tool logging saknas | Viktigt gap |
| DB/migrations | `create_tables()` på startup | Inte produktionsmoget |
| Layering | Dokumenterad strikt layering, men vissa routes/services gör DB queries direkt | Arkitekturdrift |

### Verifierade kommandon

Frontend:

```bash
cd frontend
npm run lint
npm test -- --runInBand
```

Resultat:

- `npm run lint`: passerar utan errors.
- `npm test -- --runInBand`: 2 test suites, 7 tests, alla passerar.
- Notering: processing-tester loggar avsiktliga `console.error` från simulerade API-fel.

Backend:

```bash
docker compose exec backend pytest tests/
```

Resultat:

- 24 tester passerar.
- 2 warnings: `@app.on_event("startup")` är deprecated i FastAPI.

Lokal backend:

```bash
cd backend
pytest tests/
```

Resultat:

- failar innan testkörning eftersom lokal Python-miljö saknar `fastapi`.
- Docker är just nu den fungerande verifieringsmiljön.

### Viktig testobservation

`backend/tests/test_ingest.py` innehåller nu riktiga service-level tester enligt FEED-061.

Aktivt insamlade backendtester:

- `test_analyze.py`
- `test_health.py`
- `test_image_analysis_service.py`
- `test_ingest.py`
- `test_enrichment_service.py`
- `test_enrichment_preflight.py`

Ej aktivt täckt:

- field mapping
- canonical schema edge cases
- enrichment API endpoints
- RAG/semantic search
- ARQ job flow
- products/catalog endpoints
- variants
- stats
- apply accepted fields
- image upload endpoint

### Fixar gjorda under statusgenomgången

- Fixade frontend lint i `frontend/app/processing/page.tsx` genom att ta bort oanvända callback-parametrar.
- Uppdaterade `backend/tests/test_image_analysis_service.py` efter att AVIF-konvertering flyttats till `app.core.image`.
- FEED-061 lade till ingestion service-tester.
- FEED-062 lade till Pydantic-validering av AI-output före persistence.
- FEED-063 lade till backend preflight för bulk enrichment.
- Backendtester passerar nu i Docker: 24 tester, 2 kända FastAPI-varningar.

### Nuläge vs önskat AI-läge

Önskat läge:

```txt
AI-drivet enrichment-system
kodstyrt fältval
kodstyrt modellval
kodstyrd verktygsaktivering
preflight före kostnad
minimal input
validerad output
observability per produkt/request
extract -> normalize -> enrich -> validate -> store
```

Nuvarande läge:

- AI-anrop är centraliserade i `core/ai.py`.
- Promptversioner finns.
- Enrichment parsear JSON och validerar AI-output med Pydantic innan `AnalysisResult` sparas.
- Vissa AI-flöden utanför enrichment kan fortfarande returnera eller spara lös `dict`-shape.
- Bulk enrichment kan köas via ARQ.
- Preflight med token-/kostnadsestimat finns för bulk enrichment som backend-first första pass.
- Modellval är inte dynamiskt per uppgift.
- Verktygsval är inte en tydlig backend-plan per fält.
- Input-minimering finns inte som generell mekanism.
- Observability är ofullständig.

### Prioriterad nästa-steg-plan

#### Fas 1 — Stabilisera verifiering

1. Skapa fungerande lokal backend testmiljö eller fortsätt dokumentera Docker som primär testväg.
2. Utöka ingestion-tester till mapper/normalizer/validator där det ger riskreduktion.
3. Lägg tester för `FieldMapper`, `CanonicalProduct`, `normalize_row` och `validate_row`.
4. Lägg endpoint-tester för `/catalog`, `/products/{sku_id}`, `/jobs/{job_id}`.
5. Lägg service-tester för `EnrichmentService` utan riktiga AI-anrop.

#### Fas 2 — AI-output måste styras av kod

1. Skärp AI-output-regler vid behov, t.ex. required fields eller `extra="forbid"`.
2. Lägg tester för tom AI-output, okända fält och trunkerad JSON.
3. Gå igenom övriga AI-flöden så de inte sparar lös dict-shape utan validering.

#### Fas 3 — Preflight och kostnadskontroll

1. Koppla preflight till frontend-flödet.
2. Lägg senare confirmation token/preflight-id innan ARQ-jobb skapas.
3. Ersätt estimates med faktisk kostnadslogg när FEED-066 finns.

#### Fas 4 — Fältmetadata och input-minimering

1. Lägg metadata per canonical field: relevans, komplexitet, tool requirements, model strategy.
2. Bygg task payload per fält.
3. Förhindra att hela produktobjekt skickas till modellen som default.
4. Lägg tester som kontrollerar att payload bara innehåller relevanta fält.

#### Fas 5 — Observability och drift

1. Ersätt `print()` med strukturerad logging.
2. Logga model, tokens, kostnad, tools, promptversion, latency, status och fel per AI-request.
3. Lägg job-level summary: total tokens, total cost, processed, failed.
4. Flytta från `create_tables()` till Alembic migrations.

### Kort verdict

FeedPilot är byggd tillräckligt långt för att vara en fungerande MVP-prototyp, men inte tillräckligt reviewad eller testad för att betraktas som stabil produkt.

Den största tekniska risken är inte att filer saknas. Det är att många AI-flöden ännu inte är tillräckligt kodstyrda, testade eller observerbara.

Nästa praktiska arbetsläge bör vara:

```txt
1. Testa och stabilisera nuvarande kod.
2. Dokumentera faktiska flöden fil för fil.
3. Refaktorera AI-flöden mot kodstyrd enrichment.
4. Införa preflight/kostnadskontroll innan vidare featurebygge.
```

## Backend (Dag 1–11)

| Dag  | Innehåll                                      | Status |
|------|-----------------------------------------------|--------|
| 1    | Arkitektur + design document                  | ✅     |
| 2    | FastAPI grundstruktur + Docker                | ✅     |
| 3    | Claude API + service layer                    | ✅     |
| 4    | Prompt engineering + versionshantering        | ✅     |
| 5    | CSV ingest + schema detection                 | ✅     |
| 6    | pgvector + embeddings                         | ✅     |
| 7    | RAG pipeline                                  | ✅     |
| 8    | Enrichment med reasoning + confidence         | ✅     |
| 9    | Variant-level SEO + EAN                       | ✅     |
| 10   | Multimodal bildanalys                         | ✅     |
| 11   | ARQ async pipeline + Excel ingest             | ✅     |
| —    | Canonical schema + mapping layer refactor     | ✅     |

---

## Sprint 1 — MVP Frontend (Dag 12)

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-001  | Next.js 14 setup + routing            | ✅     |
| FEED-002  | Shared layout — Sidebar + TopNav      | ✅     |
| FEED-003  | Dashboard med live metrics            | ✅     |
| FEED-004  | Job progress bar (live polling)       | ✅     |
| FEED-005  | Catalog — produktlista med filter     | ✅     |
| FEED-006  | Product Detail enrichment view        | ✅     |
| FEED-007  | Accept/Reject/Edit per fält           | ✅ inkl. inline editing |
| FEED-008  | Enrich Again-knapp                    | ✅     |
| FEED-009  | View History per produkt              | ⬜     |
| FEED-010  | Variant Manager UI                    | ✅     |
| FEED-011  | Image Analysis UI (ImagePanel)        | ✅     |
| FEED-012  | Upload feed modal (CSV + Excel)       | ✅     |
| FEED-013  | Loading skeletons på alla datavyer    | ⬜ delvis |
| FEED-021  | README + arkitekturdiagram            | ✅     |

---

## Sprint 2 — Auth + Roller

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-014  | Auth — JWT + login page               | ⬜     |
| FEED-015  | Roller + behörigheter                 | ⬜     |
| FEED-016  | Skyddade routes i Next.js             | ⬜     |
| FEED-017  | Auth middleware i FastAPI             | ⬜     |
| FEED-025  | Separata ARQ-köer (ai + data)         | ⬜     |
| FEED-026  | Retry med exponential backoff         | ⬜     |
| FEED-027  | Dead letter handling                  | ⬜     |
| FEED-028  | Sentry integration                    | ⬜     |
| FEED-040  | GitHub Actions CI/CD pipeline         | ⬜     |
| FEED-041  | Sentry integration                    | ⬜     |
| FEED-042  | GCP-konto + staging miljö             | ⬜     |
| FEED-043  | Migrera DB till Cloud SQL             | ⬜     |

---

## Sprint 3 — Multi-tenant

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-032  | Multi-tenant schema isolation         | ⬜     |
| FEED-033  | Tenant-modell i databasen             | ⬜     |
| FEED-034  | API-nycklar per tenant                | ⬜     |
| FEED-035  | Onboarding flow för ny kund           | ⬜     |
| FEED-029  | Structured logging (structlog)        | ⬜     |
| FEED-030  | Rate limiting per tenant              | ⬜     |
| FEED-036  | Pytest tester dag 8–11                | ⬜     |
| FEED-037  | Integration tests för API endpoints   | ⬜     |
| FEED-045  | Environment separation (dev/stg/prod) | ⬜     |
| FEED-046  | UptimeRobot monitoring                | ⬜     |

---

## Innan första kund (blocking)

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-032  | Multi-tenant schema isolation         | ⬜     |
| FEED-033  | Tenant-modell                         | ⬜     |
| FEED-034  | API-nycklar                           | ⬜     |
| FEED-039  | Docker production build (ej --reload) | ⬜     |
| FEED-040  | GDPR-policy + Terms of Service        | ⬜     |
| FEED-044  | Produktionsmiljö GCP                  | ⬜     |
| Auth      | JWT + roller (Sprint 2)               | ⬜     |
