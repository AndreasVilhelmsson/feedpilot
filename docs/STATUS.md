# FeedPilot — Status

## Verifierat nuläge — 2026-05-15

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
| Tester | Backend 71 tester passerar i Docker; frontend 14 tester passerar | Testtäckning är bättre men fortfarande låg jämfört med feature-yta |
| Lint | Frontend lint passerar efter fix | Verifierat |
| Backend lokal miljö | `pytest` lokalt failar utan backend deps (`fastapi` saknas) | Miljö behöver dokumenteras/fixas |
| Docker runtime | API, postgres, redis och worker kör | Verifierat via `docker compose ps` |
| AI-arkitektur | Prompt manager och AI core finns | Behöver flyttas mot kodstyrd enrichment |
| Preflight/kostnadskontroll | Backend preflight finns; frontend preflight-modal och bulk-flöde implementerat via FEED-073 | Verifierat — 14/14 frontend-tester passerar |
| Observability | Enrichment AI-request metadata loggas strukturerat som första pass | Delvis verifierat |
| DB/migrations | `create_tables()` på startup | Inte produktionsmoget |
| Layering | FEED-068 kartlade direkta DB-queries och repository-gap | Plan finns, implementation återstår |

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

- 71 tester passerar.
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
- products endpoints täcks för detail, enrich och apply-fields happy/error paths
- variants
- apply accepted fields
- image upload endpoint

### Fixar gjorda under statusgenomgången

- Fixade frontend lint i `frontend/app/processing/page.tsx` genom att ta bort oanvända callback-parametrar.
- Uppdaterade `backend/tests/test_image_analysis_service.py` efter att AVIF-konvertering flyttats till `app.core.image`.
- FEED-061 lade till ingestion service-tester.
- FEED-062 lade till Pydantic-validering av AI-output före persistence.
- FEED-063 lade till backend preflight för bulk enrichment.
- FEED-064 lade till field metadata och minimal AI-payload för enrichment.
- FEED-065 lade till backend-styrd model/tool planner.
- FEED-065B integrerade plannern i `EnrichmentService` för target fields och RAG-beslut.
- FEED-066 lade till strukturerad AI-request logging för enrichment.
- FEED-067 lade till HTTP-level endpoint-tester för enrichment preflight och single enrichment.
- FEED-069 lade till HTTP-level endpoint-tester för catalog före repository-refaktor.
- FEED-069B flyttade catalog-queryn från API-lagret till `CatalogRepository`.
- FEED-070 lade till HTTP-level endpoint-tester för products före repository-refaktor.
- FEED-071 lade till `avg_enrichment_score` i hela stats-kedjan (repo → service → schema → frontend) och kopplade `FeedQualityScore`-diagrammet till riktiga data.
- FEED-072 investigation avslutad: Hypotes A bekräftad — avg_score 35.6 och return_risk_high 84.6% speglar testdatans kvalitet, inte ett pipeline-fel.
- FEED-073 lade till preflight-modal, tvåstegsflöde för bulk enrichment och progressbar med completed/failed-states i dashboard.
- Backendtester passerar nu i Docker: 71 tester, 2 kända FastAPI-varningar.

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
- Modellstrategi beräknas per uppgift, men konkret modellbyte är inte integrerat ännu.
- RAG-beslut styrs nu av backend-plannern för enrichment. Web search och image analysis är fortfarande inte integrerade.
- Input-minimering finns för enrichment som första pass via field metadata och payload-builder.
- Observability finns som första logging-pass för enrichment. DB-persistens, kostnad
  och job-level summary återstår.

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
3. Ersätt estimates med faktisk kostnadslogg när tokenpriser och persistens finns.

#### Fas 4 — Fältmetadata och input-minimering

1. Utöka metadata när fler enrichment-flöden än core product enrichment använder samma mekanism.
2. Säkerställ att nya AI-flöden använder payload-builder eller motsvarande minimal payload.
3. Koppla framtida modellkonfiguration till planner utan att hårdkoda nya model-ID:n i service-lagret.

#### Fas 5 — Observability och drift

1. Ersätt `print()` med strukturerad logging.
2. Persistera AI-request metadata när migrationsspåret är beslutat.
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
