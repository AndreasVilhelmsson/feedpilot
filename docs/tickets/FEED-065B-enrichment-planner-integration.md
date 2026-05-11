# FEED-065B — Integrera enrichment planner i EnrichmentService

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-065 lade till `backend/app/services/enrichment_planner.py` med en deterministisk
`plan_enrichment()` och ett `EnrichmentPlan`-objekt. Plannern använder
`FIELD_REGISTRY` och `FieldMeta.complexity` för att avgöra:

- vilka saknade fält som faktiskt är enrichable
- task complexity
- model strategy
- om RAG ska användas
- framtida tool-flaggor

Det var medvetet out of scope i FEED-065 att koppla plannern till
`EnrichmentService`. Därför kör `enrichment_service.py` fortfarande pipeline-logik
utan att läsa plan-resultatet.

## Problem

Plannern finns men används inte i enrichment-flödet. Det betyder att backend ännu inte
har en faktisk beslutspunkt mellan:

```txt
missing_fields -> plan_enrichment() -> enrichment pipeline
```

Utan integration är FEED-065 bara förberedande kod. Nästa steg är att använda planen i
den befintliga pipelinen utan att ändra AI-klienten, API-schema eller promptkontrakt.

## Mål

`EnrichmentService.enrich_product()` ska skapa en `EnrichmentPlan` och använda den för
att styra:

- vilka missing fields som skickas vidare till payload-buildern
- om RAG-context ska hämtas

Detta ska vara en smal integration. Modellbyte och observability kommer senare.

## Scope

Följande ingår:

- Importera och använda `plan_enrichment()` i `backend/app/services/enrichment_service.py`.
- Efter `missing_fields = canonical.missing_core_fields()`, skapa:

```python
plan = plan_enrichment(missing_fields)
```

- Använd `plan.target_fields` som enrichment target-lista när user message byggs.
- Hämta RAG-context endast om `plan.use_rag` är `True`.
- Om `plan.use_rag` är `False`, sätt `rag_context = []` och anropa inte
  `semantic_search()`.
- Behåll dagens `ask_claude()`-anrop oförändrat.
- Lägg till fokuserade tester i `backend/tests/test_enrichment_service.py`.

## Out of Scope

Följande ingår inte:

- Ändringar i `backend/app/core/ai.py`.
- Att skicka `plan.model` till `ask_claude()`.
- Faktiskt modellbyte.
- Web search implementation.
- Image analysis integration.
- API endpoint-ändringar.
- Databasmigrationer.
- Observability, token/cost-logg eller ny loggmodell. Det hör till FEED-066.
- Frontend.
- Stora refactors av `EnrichmentService`.

## Designbeslut

`plan.model` och `plan.model_strategy` får gärna beräknas, men ska inte användas för att
ändra Claude-anropet i denna ticket. Orsaken är att `ask_claude()` i `app.core.ai`
fortfarande äger konkret model-ID och saknar ett säkert, testat model-argument.

Den här ticketen ska därför bara koppla in de delar av planen som är säkra att använda
nu:

```txt
target_fields
use_rag
```

## Rekommenderad implementation

I `backend/app/services/enrichment_service.py`:

```python
from app.services.enrichment_planner import plan_enrichment
```

I `enrich_product()`:

```python
missing_fields = canonical.missing_core_fields()
plan = plan_enrichment(missing_fields)
priority = canonical.enrichment_priority()
max_tokens = MAX_TOKENS_BY_PRIORITY[priority]

if plan.use_rag:
    rag_query = " ".join(filter(None, [product.title, product.category]))
    rag_context = self._repo.semantic_search(
        query=rag_query,
        db=db,
        limit=RAG_CONTEXT_LIMIT,
    )
else:
    rag_context = []

user_message = _build_user_message(canonical, rag_context, plan.target_fields)
```

Ingen annan pipeline-logik ska ändras.

## Acceptance Criteria

- `EnrichmentService.enrich_product()` anropar `plan_enrichment(missing_fields)`.
- `_build_user_message()` får `plan.target_fields`, inte rå `missing_fields`.
- `semantic_search()` anropas när planen har `use_rag=True`.
- `semantic_search()` anropas inte när planen har `use_rag=False`.
- `ask_claude()`-anropet är oförändrat i signatur: `prompt`, `system`, `max_tokens`.
- Inga ändringar görs i `app.core.ai`.
- Inga API- eller frontendändringar görs.
- Backendtester passerar.

## Testkrav

Uppdatera:

```txt
backend/tests/test_enrichment_service.py
```

Lägg till tester som verifierar:

1. När en enrichable field saknas, t.ex. `brand`, anropas `semantic_search()` och
   payloadens `missing_fields` är planner-filtrerade target fields.
2. När inga core fields saknas, eller när planner-resultatet saknar target fields,
   anropas inte `semantic_search()` och payloadens `rag_context` är `[]`.
3. `ask_claude()` mockas i alla tester. Inga riktiga AI-anrop.

Använd befintlig SQLite-fixture och befintliga mock-mönster i
`test_enrichment_service.py`.

## Codex Review Notes

- Granska att integrationen inte smyger in modellbyte eller `core/ai.py`-ändringar.
- Granska särskilt att `missing_fields` i payloaden kommer från `plan.target_fields`.
- Kör minst:

```bash
docker compose exec backend pytest tests/test_enrichment_planner.py tests/test_enrichment_service.py
docker compose exec backend pytest tests/
```

## Codex Review

Godkänd.

Verifierat:

- `EnrichmentService.enrich_product()` anropar `plan_enrichment(missing_fields)`.
- `semantic_search()` styrs av `plan.use_rag`.
- `_build_user_message()` får `plan.target_fields`.
- `ask_claude()`-signaturen är oförändrad.
- Ingen ändring gjordes i `app.core.ai`, API, frontend eller databasmodeller.

Testresultat:

```bash
docker compose exec backend pytest tests/test_enrichment_planner.py tests/test_enrichment_service.py
```

Resultat: 15 passed, 2 kända FastAPI on_event-varningar.

```bash
docker compose exec backend pytest tests/
```

Resultat: 42 passed, 2 kända FastAPI on_event-varningar.
