# FEED-067 — API Endpoint Coverage

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-060 till FEED-066 har fokuserat på service-lagret: field metadata, minimal
payload, enrichment planner, planner-integration och AI observability. Alla dessa
lager har tester som körs isolerade med SQLite och mockade AI-anrop.

Det saknas tester som verifierar att FastAPI-lagren faktiskt svarar korrekt på HTTP-
requests — det vill säga att routing, dependency injection, request-validering och
HTTP-statuskoder fungerar som förväntat.

Befintliga API-tester är minimala:

- `test_health.py` täcker `/api/v1/health` och `/` — fungerar och ska behållas.
- `test_analyze.py` täcker `/api/v1/analyze` via `conftest.py`-fixture.
- Övriga endpoints (`/enrich`, `/catalog`, `/products`, `/jobs`, `/stats`) saknar
  täckning.

## Problem

Utan API-tester kan en felaktig route-signatur, en saknad dependency eller ett
felaktigt HTTP-statuskod gå oupptäckt tills den når frontend eller produktion.

EXECUTION_PLAN.md:

```txt
4. Lägg endpoint-tester för /catalog, /products/{sku_id}, /jobs/{job_id}.
```

STATUS.md:

```txt
Ej aktivt täckt: enrichment API endpoints, products/catalog endpoints, jobs.
```

## Mål

Introducera första riktiga API endpoint-tester för enrichment-flödet med
FastAPI `TestClient`. Fokus på HTTP-lagret — routing, statuskoder, request-
validering och error handling — inte på AI-logiken, som redan är testad i
service-lagret.

## Scope

Följande ingår i FEED-067:

- Ny fil `backend/tests/test_api_enrich.py` med tester för:
  - `POST /api/v1/enrich/preflight` — happy path + validering
  - `POST /api/v1/enrich/{sku_id}` — happy path, 404, 500
- `EnrichmentService` och `PreflightService` overrideas via FastAPI
  dependency injection — inga riktiga AI-anrop.
- `get_db` overrideas med SQLite in-memory — inga anrop mot PostgreSQL.
- Testerna använder `TestClient` från `fastapi.testclient`.
- `test_health.py` lämnas oförändrad.
- Inga riktiga Anthropic-anrop.

## Out of Scope

Följande ingår inte i FEED-067:

- `POST /api/v1/enrich/bulk` — kräver ARQ/Redis (`create_pool`), ut scope.
- `/catalog`, `/products`, `/jobs`, `/stats` — egna tickets.
- Frontend.
- Databasmigrationer.
- Stora route-refactors.
- Autentisering.
- conftest.py-ändringar om inte nödvändigt.

## Designbeslut

### Dependency override-mönster

FastAPI stödjer `app.dependency_overrides` för att ersätta `Depends()`-
beroenden i tester utan att ändra produktionskod. Det är det mönster som
redan används i `conftest.py` för `get_analyze_service`.

För FEED-067 används samma mönster:

```python
from app.services.enrichment_service import get_enrichment_service
from app.services.preflight_service import get_preflight_service
from app.core.database import get_db

app.dependency_overrides[get_enrichment_service] = lambda: mock_enrichment_service
app.dependency_overrides[get_preflight_service] = lambda: mock_preflight_service
app.dependency_overrides[get_db] = lambda: mock_db_session
```

Overrides rensas med `app.dependency_overrides.clear()` i fixture teardown.

### get_db override

`enrich_preflight` och `enrich_product` tar `Depends(get_db)` som skickas
vidare till service-metoden. Eftersom service-lagret är mockat används `db`
aldrig på riktigt. Men FastAPI löser dependency-trädet och anropar `get_db`
oavsett — vilket annars försöker nå PostgreSQL.

Lösning: override `get_db` med en SQLite in-memory session per test.
Det är samma setup som används i `test_enrichment_service.py`.

```python
@pytest.fixture
def sqlite_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()
```

Alternativet är en `MagicMock()` för `db`, men SQLite ger bättre felsignaler
om koden faktiskt försöker göra DB-anrop när det inte borde.

### conftest.py

Befintlig `conftest.py` behöver inte ändras. Alla fixtures för FEED-067
definieras lokalt i `test_api_enrich.py`. Om Codex anser att delade fixtures
är motiverade kan en minimalt utökad `conftest.py` ingå som valfritt steg.

### EnrichResponse-mock

`enrich_product`-routen returnerar `EnrichResponse(**result)`. En mock av
`EnrichmentService.enrich_product()` måste returnera en dict som passar
`EnrichResponse`. Använd en minimal giltig dict med alla required fields från
`EnrichResponse`-schemat. Extra fält från service-lagret, t.ex.
`enrichment_priority` och `missing_fields`, behöver inte ingå i endpoint-testets
mock eftersom `EnrichResponse` inte exponerar dem.

```python
MOCK_ENRICH_RESULT = {
    "sku_id": "SKU-001",
    "analysis_id": 1,
    "overall_score": 72,
    "enriched_fields": {},
    "issues": [],
    "return_risk": "low",
    "return_risk_reason": "Complete data.",
    "action_items": [],
    "prompt_version": "2.0.0",
    "total_tokens": 500,
}
```

### PreflightResponse-mock

`enrich_preflight` returnerar en `PreflightResponse`. Mocken ska returnera en
giltig `PreflightResponse`-instans med fälten:

```python
PreflightResponse(
    product_count=2,
    estimated_ai_calls=2,
    estimated_input_tokens=1600,
    estimated_output_tokens=2400,
    estimated_total_tokens=4000,
    estimated_cost_usd=0.02,
    fields_to_enrich={"brand": 1},
    tool_plan={"rag": True, "web_search": False, "image_analysis": False},
    requires_confirmation=True,
)
```

## Berörda filer

Claude Code arbetar en fil i taget.

Rekommenderad filordning:

1. `backend/tests/test_api_enrich.py` (ny fil) — alla HTTP-tester för
   `/enrich/preflight` och `/enrich/{sku_id}`.

Inte tillåtet utan separat godkännande:

- Ändringar i `backend/app/api/enrich.py`.
- Ändringar i `backend/app/main.py`.
- Ändringar i `backend/tests/conftest.py` (om inte Codex bedömer det nödvändigt).
- Frontend.

## Acceptance Criteria

- `backend/tests/test_api_enrich.py` finns med minst 5 tester.
- `POST /api/v1/enrich/preflight` returnerar 200 med giltig body vid happy path.
- `POST /api/v1/enrich/preflight` returnerar 422 vid saknat request body.
- `POST /api/v1/enrich/{sku_id}` returnerar 200 med giltig body vid happy path.
- `POST /api/v1/enrich/{sku_id}` returnerar 404 när produkten saknas.
- `POST /api/v1/enrich/{sku_id}` returnerar 500 vid okänt fel.
- Inga riktiga AI-anrop görs.
- Inga anrop mot PostgreSQL eller Redis görs.
- Befintliga backend-tester fortsätter passera utan regression.

## Testkrav

Skapa:

```txt
backend/tests/test_api_enrich.py
```

### Test 1: POST /enrich/preflight — 200 happy path

Given:
- `PreflightService.compute_preflight()` mockad att returnera giltig
  `PreflightResponse`.
- `get_db` overridad med SQLite in-memory.

Expect:
- HTTP 200.
- Response-body innehåller `product_count` och `requires_confirmation`.

### Test 2: POST /enrich/preflight — 422 saknat body

Given:
- Ingen request body.

Expect:
- HTTP 422.

### Test 3: POST /enrich/{sku_id} — 200 happy path

Given:
- `EnrichmentService.enrich_product()` mockad att returnera `MOCK_ENRICH_RESULT`.
- `get_db` overridad med SQLite in-memory.

Expect:
- HTTP 200.
- Response-body innehåller `sku_id` och `overall_score`.

### Test 4: POST /enrich/{sku_id} — 404 produkt saknas

Given:
- `EnrichmentService.enrich_product()` kastar `ValueError("Produkt... hittades inte")`.

Expect:
- HTTP 404.

### Test 5: POST /enrich/{sku_id} — 500 oväntat fel

Given:
- `EnrichmentService.enrich_product()` kastar `RuntimeError("Unexpected error")`.

Expect:
- HTTP 500.

## Codex Review Notes

- Granska att `app.dependency_overrides` rensas korrekt efter varje test —
  läckage mellan tester är en vanlig källa till flaky tests.
- Granska att `get_db` override inte lämnar öppna SQLite-connections efter testet.
- Verifiera att `test_health.py` inte påverkas av ändringar i conftest.
- Kör minst:

```bash
docker compose exec backend pytest tests/test_api_enrich.py -v
docker compose exec backend pytest tests/
```

## Risker

- `app.main.app` importerar alla routers på modulnivå, inklusive `enrich_bulk`
  som importerar `arq`. Om `arq` saknas i testmiljön failar importen. Verifiera
  att `arq` finns i Docker-imagen — det borde det, men risk att nämna.
- `EnrichResponse`-schemat kan ha required fields som inte är uppenbara utan att
  läsa `schemas/enrich.py`. Läs schemat innan mock-dicten definieras.
- `dependency_overrides` är globalt på `app`-instansen. Om ett test failar mitt i
  en `with`-block eller fixture-setup kan override sitta kvar och påverka nästa
  test. Använd `yield`-fixture med `app.dependency_overrides.clear()` i teardown.
- `create_pool` i `enrich_bulk`-routen körs inte i FEED-067 tests, men om
  `app.main` importeras och routen registreras finns risk för indirekt failure om
  Redis-konfigurationen fattas. I praktiken används TestClient utan att köa ARQ-jobb.

## Definition of Done

- Claude Code har arbetat en fil i taget.
- `test_api_enrich.py` finns med minst 5 tester.
- Inga riktiga AI-anrop eller DB-anrop mot PostgreSQL.
- Befintliga backend-tester passerar utan regression.
- Codex har reviewat diffen.
- Ticketen markeras Done när testerna passerar och Codex-review är klar.

## Codex Review

Godkänd.

Verifierat:

- `backend/tests/test_api_enrich.py` finns med 5 HTTP-level tester.
- `POST /api/v1/enrich/preflight` täcks för 200 och 422.
- `POST /api/v1/enrich/{sku_id}` täcks för 200, 404 och 500.
- `get_enrichment_service`, `get_preflight_service` och `get_db` overrideas via
  `app.dependency_overrides`.
- Overrides rensas i fixture teardown.
- Ingen produktionskod ändrades.
- Inga riktiga AI-, PostgreSQL- eller Redis-anrop görs i testerna.

Testresultat:

```bash
docker compose exec backend pytest tests/test_api_enrich.py -v
```

Resultat: 5 passed, 2 kända FastAPI on_event-varningar.

```bash
docker compose exec backend pytest tests/
```

Resultat: 49 passed, 2 kända FastAPI on_event-varningar.
