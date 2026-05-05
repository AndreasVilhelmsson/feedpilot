# FeedPilot — Execution Plan

## Var vi är nu

FeedPilot är en fungerande MVP-prototyp byggd till stor del med Claude Code.

Det finns mycket kod på plats:

- FastAPI backend
- Next.js frontend
- CSV/XLSX ingest
- canonical schema
- AI enrichment
- image analysis
- RAG/pgvector
- ARQ worker
- dashboard/catalog/product detail UI

Men koden är inte tillräckligt reviewad, testad eller arkitekturstyrd för att betraktas som stabil produkt.

Aktuell ticket-status styrs av `docs/tickets/`, som är single source of truth för scope, acceptance criteria och Codex review. FEED-060 till FEED-063 är reviewade och markerade Done där.

Viktig skillnad:

```txt
Byggt != verifierat != produktionsklart
```

## Önskat läge

FeedPilot ska vara ett AI-drivet enrichment-system, inte en prompt-baserad wrapper.

Det önskade systemet ska ha:

- kodstyrt fältval
- kodstyrt modellval
- kodstyrd verktygsaktivering
- preflight före dyra/bulk-körningar
- token- och kostnadsestimat innan jobb startar
- minimal input till modellen
- validerad AI-output innan store/UI
- observability per produkt/request
- tydlig pipeline: `extract -> normalize -> enrich -> validate -> store`
- tillräcklig testtäckning för att refaktorera säkert

## Rekommenderad rollfördelning

### Claude Code

Claude Code bör vara primär **implementation agent**.

Använd Claude Code för:

- skapa/ändra kod
- implementera tickets
- skriva första versionen av tester
- göra fokuserade refactors
- följa instruktioner i `CLAUDE.md`

Claude Code ska arbeta en ticket i taget och hålla diffar små.

### Codex

Codex bör vara primär **review, test och architecture control agent**.

Använd Codex för:

- reverse engineering
- statusbedömning
- arkitekturreview
- testkörning
- hitta regressionsrisker
- granska Claude Codes diffar
- skriva acceptance criteria
- verifiera att implementationen följer principen "AI styrs av kod, inte prompt"

Codex kan göra små kirurgiska fixar när de blockerar verifiering, till exempel lintfel eller utdaterade tester.

### Varför inte tvärtom?

Det går att låta Codex skriva kod och Claude reviewa, men nuvarande repo är redan starkt påverkat av Claude Code. Det är bättre att skapa en tydlig separation:

```txt
Claude Code = bygger
Codex       = kontrollerar, testar, granskar, styr arkitektur
```

Det minskar risken att samma agent både skapar och godkänner sin egen arkitektur.

## Arbetsflöde per ticket

1. Codex definierar ticket:
   - problem
   - önskat beteende
   - berörda filer
   - acceptance criteria
   - testkrav

2. Claude Code implementerar:
   - små diffar
   - en tydlig ändring i taget
   - tester först eller tillsammans med implementationen

3. Codex reviewar:
   - kör relevanta tester
   - granskar arkitekturlager
   - granskar risker
   - kontrollerar att AI-regler styrs av kod

4. User beslutar:
   - godkänn
   - begär ändring
   - pausa ticket

## Beslutat nästa steg

Innan auth, multi-tenant eller nya produktfeatures bör vi köra en stabiliseringsfas.

Namn:

```txt
Sprint 1.5 — Stabilisering och AI Control
```

Mål:

```txt
Göra nuvarande MVP reviewbar, testbar och redo för kodstyrd AI-enrichment.
```

## Sprint 1.5 tickets

### FEED-060 — Test baseline och verifieringskommando

Status: Done. Se `docs/tickets/FEED-060-test-baseline.md`.

Problem:

Backendtester går i Docker men lokal `pytest` saknar dependencies. Status blir otydlig.

Mål:

Ett tydligt verifieringskommando för backend och frontend.

Acceptance criteria:

- Dokumentera primär testväg.
- Backend tests körs reproducerbart.
- Frontend lint/test körs reproducerbart.
- Statusdokumentet visar aktuellt verifieringsläge.

Testkrav:

```bash
docker compose exec backend pytest tests/
cd frontend && npm run lint
cd frontend && npm test -- --runInBand
```

### FEED-061 — Ingestion test coverage

Status: Done. Se `docs/tickets/FEED-061-ingestion-test-coverage.md`.

Problem:

`backend/tests/test_ingest.py` var tom. Ingestion är central och behövde aktiv testtäckning.

Mål:

Säkra CSV/XLSX ingest, field mapping, normalization och validation.

Acceptance criteria:

- `test_ingest.py` innehåller riktiga tests.
- CSV fixture importerar produkter.
- Duplicate SKU/update-beteende testas.
- Dålig CSV ger kontrollerat fel eller warnings.
- Shopify/WooCommerce/Google/Akeneo detection testas där fixtures finns.

Berörda filer:

- `backend/tests/test_ingest.py`
- `backend/app/services/ingestion_service.py`
- `backend/app/ingestion/mapping/field_mapper.py`
- `backend/app/ingestion/normalizer.py`
- `backend/app/ingestion/validators.py`

### FEED-062 — Enrichment output schema validation

Status: Done. Se `docs/tickets/FEED-062-enrichment-output-schema-validation.md`.

Problem:

AI-output styrs delvis av prompt och lös dict-shape.

Mål:

Kod ska validera enrichment-output innan den sparas.

Acceptance criteria:

- Pydantic/DTO-schema för enrichment-resultat finns.
- `overall_score`, `return_risk`, `issues`, `enriched_fields`, `action_items` valideras.
- Okända/felaktiga enumvärden hanteras kontrollerat.
- Trunkerad eller invalid JSON ger tydligt fel.
- Inget validerat resultat, ingen persistence.

Berörda filer:

- `backend/app/services/enrichment_service.py`
- `backend/app/schemas/enrich.py`
- eventuellt ny schemafil för AI output
- `backend/tests/`

### FEED-063 — Preflight för bulk enrichment

Status: Done. Se `docs/tickets/FEED-063-bulk-enrichment-preflight.md`.

Problem:

Bulk enrichment kan startas utan kostnads-/tokenkontroll.

Mål:

Backend ska kunna returnera preflight innan jobb köas.

Acceptance criteria:

- Ny preflight endpoint eller service finns.
- Returnerar produktantal.
- Returnerar fält som ska bearbetas.
- Returnerar uppskattade input/output tokens.
- Returnerar uppskattad kostnad.
- Returnerar enkel backend-styrd tool plan.
- Response innehåller `requires_confirmation`.
- Confirmation token/preflight-id enforcement i `/enrich/bulk` är medvetet out of scope för första passet.

Berörda filer:

- `backend/app/api/enrich.py`
- `backend/app/services/enrichment_service.py`
- eventuell ny `preflight_service.py`
- `frontend/app/processing/page.tsx`

### FEED-064 — Field metadata och minimal AI payload

Problem:

Systemet saknar generell mekanism för att avgöra vilka fält som är relevanta för en AI-task.

Mål:

Canonical fields ska ha metadata som styr input, komplexitet, verktyg och modellval.

Acceptance criteria:

- Metadata per canonical field finns i kod.
- Varje enrichment-task bygger minimal payload.
- Hela produktobjektet skickas inte till modellen som default.
- Tester säkerställer att payload bara innehåller relevanta fält.

Berörda filer:

- `backend/app/schemas/canonical.py`
- eventuell ny `field_metadata.py`
- `backend/app/services/enrichment_service.py`
- `backend/tests/`

### FEED-065 — Model/tool decision planner

Problem:

Modellval och verktygsaktivering är inte en tydlig backend-plan per task.

Mål:

Kod ska besluta modell, RAG, web search och image analysis baserat på field metadata.

Acceptance criteria:

- Planner returnerar modellval per task.
- Planner returnerar tillåtna/krävda verktyg.
- Prompten får inte ensam bestämma verktyg.
- Tester täcker enkla, medium och komplexa fält.

Berörda filer:

- eventuell ny `backend/app/services/enrichment_planner.py`
- `backend/app/services/enrichment_service.py`
- `backend/app/core/ai.py`

### FEED-066 — AI observability

Problem:

Token usage finns delvis men inte full observability per produkt/request.

Mål:

Logga och/eller persistera modell, tokens, kostnad, tools, status och fel.

Acceptance criteria:

- Varje AI request har metadata.
- Job result summerar tokens/cost/processed/failed.
- Fel loggas med tydlig typ.
- `print()` ersätts med logger där relevant.

Berörda filer:

- `backend/app/core/ai.py`
- `backend/app/workers/tasks.py`
- `backend/app/services/enrichment_service.py`
- `backend/app/models/job.py` eller separat loggmodell senare

### FEED-067 — API endpoint coverage

Problem:

Flera centrala endpoints saknar testtäckning.

Mål:

Grundläggande endpoint-tester för produktflöden.

Acceptance criteria:

- `/catalog` testas.
- `/products/{sku_id}` testas.
- `/jobs/{job_id}` testas.
- `/stats` testas.
- Felvägar 404/500 täcks där rimligt.

### FEED-068 — Layering cleanup plan

Problem:

Dokumenten kräver strikt layering, men API-routes och services gör ibland direkta DB queries.

Mål:

Identifiera och prioritera layering-fixar utan stor refaktor direkt.

Acceptance criteria:

- Lista över direkta `db.query` utanför repositories.
- Beslut per förekomst: fixa nu, acceptera tillfälligt, eller skapa ticket.
- Inga stora refactors utan testskydd.

## Prioritering

Rekommenderad ordning:

1. FEED-060 — Test baseline
2. FEED-061 — Ingestion tests
3. FEED-062 — Enrichment output schema validation
4. FEED-063 — Preflight
5. FEED-064 — Field metadata/minimal payload
6. FEED-065 — Model/tool planner
7. FEED-066 — Observability
8. FEED-067 — Endpoint coverage
9. FEED-068 — Layering cleanup plan

## Arbetsregel framåt

FEED-060 till FEED-063 är klara. Nästa stora feature bör fortfarande vänta tills FEED-064 till FEED-066 har gett bättre kontroll över payload, model/tool-beslut och observability.

Auth och multi-tenant är viktiga, men de bygger ovanpå en osäker foundation om enrichment-flödet inte är testat och kostnadskontrollerat.

## Definition of Ready för en ticket

En ticket är redo för Claude Code när den har:

- tydligt problem
- berörda filer
- acceptance criteria
- testkrav
- risker
- avgränsning

## Definition of Done

En ticket är klar när:

- implementation är gjord
- relevanta tester finns
- backend/frontend verifiering passerar
- Codex reviewar diffen
- status/backlog uppdateras
