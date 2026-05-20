# FEED-070 — Products API Test Coverage Före Repository Extraction

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-068 identifierade `backend/app/api/products.py` som **HIGH-risk** (Fynd 2):

- `_get_product_or_404()` (rad 33–40) — privat helper med `db.query(Product)` i route-filen.
- `_latest_analysis()` (rad 43–49) — privat helper med `db.query(AnalysisResult)` i route-filen.
- `apply_fields()` (rad 156–179) — innehåller `_COLUMN_FIELDS`-logik och `db.commit()` direkt i API-lagret.
- `ProductRepository` finns men används inte i denna fil.
- `AnalysisResultRepository` saknas.
- Noll endpoint-testtäckning.

FEED-069/FEED-069B etablerade mönstret: lägg regressionsskydd innan refaktor.
FEED-070 följer samma mönster för products-endpoints.

Baslinjen efter FEED-069B:
```bash
docker compose exec backend pytest tests/  # 56 passed, 2 kända on_event-varningar
```

## Problem

Utan tester kan en framtida repository extraction i `products.py` oavsiktligt:
- Bryta `_get_product_or_404`-logiken (404-beteende vid saknad produkt).
- Ändra `_latest_analysis`-sorteringen (desc på `id` — senaste först).
- Ändra `apply_fields` fält-splittningslogik (`title`/`description`/`category` → direkt,
  övriga → attributes JSON).
- Ändra `EnrichResponse`-mappningen från service-result dict.

## Mål

Skapa `backend/tests/test_api_products.py` med minst 7 HTTP-level tester som skyddar
nuvarande beteende i `products.py` innan repository extraction.

## Scope

- Ny fil: `backend/tests/test_api_products.py`.
- Testa nuvarande endpoint-beteende via FastAPI `TestClient`.
- SQLite in-memory databas via `get_db`-override.
- Testdata skapas som ORM-objekt: `Product` + `AnalysisResult`.
- `EnrichmentService` mockas för `/enrich`-testerna — inga riktiga AI-anrop.
- Ingen mock av `GET`- och `PATCH`-route-logiken — de ska köra mot riktig SQLite.
- Ingen produktionskod ändras.
- Ingen repository extraction.
- Ingen ändring i `products.py`, `conftest.py` eller befintliga testfiler.

## Out of Scope

- Repository extraction av `_get_product_or_404` / `_latest_analysis` — separat ticket.
- `save_image_url` (`PATCH /{sku_id}/image`) — kan ingå som bonus men är inte del av
  minst-5-kravet.
- Övriga endpoints.
- Frontend.
- Auth/multi-tenant.

## Designbeslut

### SQLite-fixture med StaticPool

FastAPI `TestClient` kör requests i en annan tråd än pytest-fixturen. Löses med samma
fix som `test_api_catalog.py`:

```python
from sqlalchemy.pool import StaticPool

@pytest.fixture
def sqlite_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()
```

### Testdata-fixture

Två produkter: en utan enrichment, en med två enrichment-rader så att
`_latest_analysis()`-sorteringen på `AnalysisResult.id.desc()` skyddas:

```python
@pytest.fixture
def seeded_db(sqlite_db):
    p1 = Product(sku_id="SKU-001", title="Skor A", description="Bra skor.")
    p2 = Product(sku_id="SKU-002", title="Jacka B")
    sqlite_db.add_all([p1, p2])
    sqlite_db.flush()

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p2.id,
            sku_id="SKU-002",
            return_risk="high",
            overall_score=30,
            prompt_version="1.0.0",
            total_tokens=200,
            action_items=["Äldre analys"],
            issues=[],
            enriched_fields={},
        ),
        AnalysisResult(
            product_id=p2.id,
            sku_id="SKU-002",
            return_risk="low",
            overall_score=75,
            prompt_version="2.0.0",
            total_tokens=400,
            action_items=["Komplettera beskrivning"],
            issues=[],
            enriched_fields={},
        )
    ])
    sqlite_db.commit()
    return sqlite_db
```

### En kombinerad client-fixture med service-mock

`enrich_product`-routen injicerar `get_enrichment_service`. För GET- och PATCH-tester
anropas aldrig service-mocken. Att ha en enda `products_client`-fixture med mock alltid
aktiv är enklare än separata fixtures:

```python
@pytest.fixture
def mock_enrichment_service():
    return MagicMock(spec=EnrichmentService)

@pytest.fixture
def products_client(seeded_db, mock_enrichment_service):
    app.dependency_overrides[get_db] = lambda: seeded_db
    app.dependency_overrides[get_enrichment_service] = lambda: mock_enrichment_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

### Mock result dict för enrich-tester

`enrich_product`-routen mappar service-resultatet via:

```python
EnrichResponse(
    sku_id=result["sku_id"],
    analysis_id=result["analysis_id"],
    overall_score=result.get("overall_score"),
    return_risk=result.get("return_risk"),
    enrichment_priority=result.get("enrichment_priority", "medium"),
    total_tokens=result.get("total_tokens"),
)
```

Mock-dict måste ha dessa nycklar (lägg märke: `schemas/product_detail.py::EnrichResponse`,
INTE `schemas/enrich.py::EnrichResponse` — de är olika):

```python
MOCK_ENRICH_RESULT = {
    "sku_id": "SKU-001",
    "analysis_id": 1,
    "overall_score": 72,
    "return_risk": "low",
    "enrichment_priority": "medium",
    "total_tokens": 500,
}
```

### `enrich_product` — 404 via service kräver en befintlig produkt

`enrich_product`-routen anropar `_get_product_or_404` INNAN service:

```python
_get_product_or_404(sku_id, db)   # raises 404 om produkt saknas
result = service.enrich_product(sku_id, db)  # når hit bara om produkt finns
```

Test 5 (404 från service ValueError) behöver därför en existerande produkt i seeded_db
och en service-mock som kastar `ValueError`. Testet verifierar att service-ValueError
mappar till 404 (inte att produkten saknas).

### GET- och PATCH-tester körs mot verklig SQLite-kod

Precis som i `test_api_catalog.py`: GET-testerna ska inte mocka bort `_get_product_or_404`
och `_latest_analysis`. Dessa testerna ska låsa in nuvarande query-beteende inför
repository extraction.

### `apply_fields` korrekt HTTP-metod och route

Endpointen är `PATCH /api/v1/products/{sku_id}/fields` (inte POST, inte `/apply`).
Request body: `{"fields": {"title": "Nytt värde"}}`. Testerna ska följa faktisk route-signatur.

## Berörda filer

Ny fil:
```
backend/tests/test_api_products.py
```

Läses (ej ändras):
```
backend/app/api/products.py
backend/app/schemas/product_detail.py
backend/app/models/product.py
backend/app/models/analysis_result.py
backend/tests/conftest.py
backend/tests/test_api_catalog.py   (mönsterreferens — SQLite + StaticPool)
backend/tests/test_api_enrich.py    (mönsterreferens — service mock)
```

## Acceptance Criteria

- `backend/tests/test_api_products.py` finns med minst 7 tester.
- `GET /api/v1/products/{sku_id}` returnerar 200 för befintlig produkt.
- `GET /api/v1/products/{sku_id}` inkluderar `overall_score` och `enriched_at` från
  senaste `AnalysisResult` om sådan finns.
- `GET /api/v1/products/{sku_id}` returnerar 200 med `overall_score=None` när ingen
  `AnalysisResult` finns.
- `GET /api/v1/products/{sku_id}` returnerar 404 för saknad produkt.
- `POST /api/v1/products/{sku_id}/enrich` returnerar 200 med mockad `EnrichmentService`.
- `POST /api/v1/products/{sku_id}/enrich` returnerar 404 när service kastar `ValueError`.
- `PATCH /api/v1/products/{sku_id}/fields` returnerar 200 och `updated_fields` stämmer.
- `PATCH /api/v1/products/{sku_id}/fields` returnerar 404 för saknad produkt.
- Inga riktiga AI-anrop görs.
- Inga PostgreSQL-anrop görs.
- Ingen produktionskod ändras.
- Befintliga backend-tester fortsätter passera:
  ```bash
  docker compose exec backend pytest tests/
  ```
  Förväntat: 56 passed (+ ny fil), 2 kända on_event-varningar.

## Testkrav

### Test 1: `GET /api/v1/products/{sku_id}` — 200 för befintlig produkt utan enrichment

Given:
- `Product(sku_id="SKU-001", title="Skor A")` i seeded_db.

Expect:
- HTTP 200.
- `sku_id == "SKU-001"`.
- `title == "Skor A"`.
- `overall_score is None`.
- `enriched_at is None`.

### Test 2: `GET /api/v1/products/{sku_id}` — senaste AnalysisResult visas

Given:
- `Product(sku_id="SKU-002")` med två `AnalysisResult`-rader.
- Äldre rad: `return_risk="high"`, `overall_score=30`.
- Nyare rad: `return_risk="low"`, `overall_score=75`.

Expect:
- HTTP 200.
- `overall_score == 75`.
- `return_risk == "low"`.
- `enriched_at` är en sträng (ISO-format).

### Test 3: `GET /api/v1/products/{sku_id}` — 404 för saknad produkt

Given:
- Ingen produkt med `sku_id="SKU-MISSING"` i databasen.

Expect:
- HTTP 404.

### Test 4: `POST /api/v1/products/{sku_id}/enrich` — 200 med mockad service

Given:
- `Product(sku_id="SKU-001")` i seeded_db.
- `mock_enrichment_service.enrich_product.return_value = MOCK_ENRICH_RESULT`.

Expect:
- HTTP 200.
- `sku_id == "SKU-001"`.
- `analysis_id == 1`.
- `enrichment_priority == "medium"`.

### Test 5: `POST /api/v1/products/{sku_id}/enrich` — 404 när service kastar ValueError

Given:
- `Product(sku_id="SKU-001")` i seeded_db (produkten måste finnas — se designbeslut).
- `mock_enrichment_service.enrich_product.side_effect = ValueError("Produkt hittades inte")`.

Expect:
- HTTP 404.

### Test 6: `PATCH /api/v1/products/{sku_id}/fields` — 200 och fält tillämpas

Given:
- `Product(sku_id="SKU-001", title="Gammalt")` i seeded_db.
- Request body: `{"fields": {"title": "Nytt"}}`.

Expect:
- HTTP 200.
- `sku_id == "SKU-001"`.
- `"title" in updated_fields`.

### Test 7: `PATCH /api/v1/products/{sku_id}/fields` — 404 för saknad produkt

Given:
- Ingen produkt med `sku_id="SKU-MISSING"`.
- Request body: `{"fields": {"title": "x"}}`.

Expect:
- HTTP 404.

### Bonus Test 8 (valfri): `PATCH /api/v1/products/{sku_id}/image` — 200 för befintlig produkt

Given:
- `Product(sku_id="SKU-001")` i seeded_db.
- Request body: `{"image_url": "https://example.com/img.jpg"}`.

Expect:
- HTTP 200.
- `image_url == "https://example.com/img.jpg"`.

## Codex Review Notes

- **Viktigast:** Verifiera att testerna INTE mockar `_get_product_or_404` eller
  `_latest_analysis`. Dessa helpers är precis det som ska skyddas inför repository
  extraction. Om de är mockade ger testerna falskt skydd.
- Kontrollera att `products_client`-fixture rensar `app.dependency_overrides` i teardown
  även om test failar mitt i.
- Kontrollera att `StaticPool` + `check_same_thread=False` används — annars repas
  threading-felet från FEED-069.
- Verifiera att `MOCK_ENRICH_RESULT` matchar nycklar som `enrich_product`-routen
  faktiskt läser:
  - `result["sku_id"]` (required key — KeyError om saknas)
  - `result["analysis_id"]` (required key)
  - `result.get("overall_score")`, `result.get("return_risk")`, `result.get("total_tokens")` (optional via `.get()`)
  - `result.get("enrichment_priority", "medium")` (optional med default)
- Kontrollera att test 5 (404 från service ValueError) har en befintlig produkt i
  seeded_db — utan det ger `_get_product_or_404` en 404 av fel orsak.
- Verifiera att `PATCH /fields` route-path är korrekt: `/api/v1/products/{sku_id}/fields`
  (inte `/apply`).
- Kör mot baseline: `docker compose exec backend pytest tests/test_api_products.py -v`
  och sedan `docker compose exec backend pytest tests/` för regressionscheck.

## Risker

### 1. `func` import är oanvänd i products.py

`from sqlalchemy import func` importeras men används inte i nuvarande `products.py`.
Risk: LOW — inga konsekvenser för testerna.

### 2. `_latest_analysis` ordning beror på `AnalysisResult.id`

`_latest_analysis()` sorterar på `AnalysisResult.id.desc()`. Om SQLite ger samma
ordning som PostgreSQL vid auto-increment-id:n stämmer testerna. FEED-070 ska skapa
två `AnalysisResult`-rader för samma produkt och verifiera att den nyare raden vinner.

### 3. `apply_fields` muterar seeded_db-sessionen

`apply_fields()` anropar `db.commit()` på `seeded_db`-sessionen. Efterföljande tester
som delar samma `seeded_db` ser den uppdaterade datan. Om `seeded_db` är function-
scoped (default) är detta OK — varje test får en ny session.

**Mitigation:** Bekräfta att `seeded_db` och `products_client` är function-scoped
(default pytest scope), vilket ger ren databas per test.

### 4. `EnrichResponse` schema-kollision

`schemas/product_detail.py` och `schemas/enrich.py` definierar båda en klass som
heter `EnrichResponse` men med olika fält. Testerna för `products.py` ska referera
till `schemas/product_detail.py::EnrichResponse` — men det behövs inte explicit i
testfilen (vi verifierar bara HTTP-responsen via `response.json()`).

## Definition of Done

- Claude Code har arbetat en fil.
- `test_api_products.py` finns med minst 7 tester.
- Inga riktiga AI-anrop eller PostgreSQL-anrop görs.
- Befintliga backend-tester passerar utan regression.
- Codex har reviewat och godkänt.
- Ticketen markeras Done när testerna passerar och Codex-review är klar.

## Codex Review

Godkänd.

Verifierat:

- `backend/tests/test_api_products.py` finns med 7 HTTP-level tester.
- GET `/api/v1/products/{sku_id}` täcks för befintlig produkt, senaste
  `AnalysisResult` och 404.
- POST `/api/v1/products/{sku_id}/enrich` täcks för 200 med mockad service och
  service-`ValueError` till 404.
- PATCH `/api/v1/products/{sku_id}/fields` täcks för 200 och 404.
- Testerna mockar inte `_get_product_or_404` eller `_latest_analysis`.
- Test 2 skapar två `AnalysisResult`-rader och verifierar att nyaste id vinner.
- SQLite-fixturen använder `StaticPool` och `check_same_thread=False`.
- Ingen produktionskod ändrades.

Testresultat:

```bash
docker compose exec backend pytest tests/test_api_products.py -v
```

Resultat: 7 passed, 2 kända FastAPI on_event-varningar.

```bash
docker compose exec backend pytest tests/
```

Resultat: 63 passed, 2 kända FastAPI on_event-varningar.
