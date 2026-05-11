# FEED-069 — Catalog API Test Coverage Före Repository Refactor

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-068 identifierade `backend/app/api/catalog.py` som det **HIGH-risk**-fynd med störst
brott mot layering och lägst testsäkerhet:

- Direkt `db.query(Product, AnalysisResult)` med subquery och multi-join i route-filen.
- `_determine_status()` — business logic för statusderivering — lever i API-lagret.
- Noll endpoint-testtäckning.
- Föreslagen framtida refaktor: skapa `CatalogRepository` och `CatalogService`
  i en separat uppföljning, exempelvis `FEED-069B`.

FEED-069 är steget **före** den refaktorn. Ingen query flyttas ännu. Målet är att
lägga testskydd runt nuvarande beteende, så att en uppföljande CatalogRepository-ticket kan
göras med regressionsdetektering.

## Problem

Utan tester kan refaktorn i nästa ticket oavsiktligt:
- Bryta pagineringslogiken.
- Ändra statusmappningen (ingen `AnalysisResult` → `needs_review`, inte `not_enriched`).
- Ändra filterlogiken för `?status=return_risk`.
- Ändra söklogiken för `?search=`.

Beteendet är inte dokumenterat utom i koden. Tester är dokumentation.

## Mål

Skapa `backend/tests/test_api_catalog.py` med minst 5 HTTP-level tester för
`GET /api/v1/catalog`. Testerna ska:

- Verifiera nuvarande statuskartläggning (`_determine_status`-logiken) konkret.
- Verifiera att filterparametrar fungerar.
- Ge regressionsdetektering inför CatalogRepository-refaktorn.

## Scope

- Ny fil: `backend/tests/test_api_catalog.py`.
- Testa nuvarande `/api/v1/catalog`-beteende via FastAPI `TestClient`.
- SQLite in-memory databas via `get_db`-override.
- Testdata skapas direkt som ORM-objekt: `Product` + `AnalysisResult`.
- **Ingen mock av catalog-route-logiken** — testerna ska låsa in nuvarande `db.query`-beteende.
- Ingen produktionskod ändras.
- Ingen `CatalogRepository`.
- Ingen ändring i `catalog.py`, `conftest.py` eller befintliga tester.

## Out of Scope

- CatalogRepository — separat uppföljning, exempelvis `FEED-069B`.
- `catalog.py`-refaktor.
- Frontend.
- Autentisering.
- Komplex edge-case-täckning bortom de 5–7 föreslagna testerna.

## Designbeslut

### Varför INTE mocka catalog-logiken?

I FEED-067 (enrich-tester) mockades `EnrichmentService` och `PreflightService` helt —
syftet var att testa HTTP-lagret (routing, statuskoder, request-validering) isolerat
från AI-logiken.

FEED-069 har ett annat syfte: vi vill låsa in den **befintliga query-logiken** i
`catalog.py` innan vi refaktorerar den. Om vi mockar bort `db.query(Product, AnalysisResult)`
testar vi ingenting av det som faktiskt ska skyddas.

Lösning: override `get_db` med SQLite, skapa riktiga ORM-rader, låt route-koden köra
sin fulla query mot SQLite. Beteende lås in = regressionsdetektering finns.

### `get_db` override med SQLite in-memory

Samma mönster som `test_api_enrich.py` och `test_enrichment_service.py`:

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

`Base` importeras från `app.models.product`. `AnalysisResult` importeras explicit för
att säkerställa att tabellen registreras i `Base.metadata` innan `create_all()` kallas.

### Testdata-fixtures

Testdata skapas via ORM-objekt direkt i SQLite. Grund-fixture med tre produkter:

```python
@pytest.fixture
def seeded_db(sqlite_db):
    # Produkt utan enrichment
    p1 = Product(sku_id="SKU-001", title="Skor A")
    # Produkt med enrichment, low risk
    p2 = Product(sku_id="SKU-002", title="Jacka B")
    # Produkt med enrichment, high risk
    p3 = Product(sku_id="SKU-003", title="Väska C")
    sqlite_db.add_all([p1, p2, p3])
    sqlite_db.flush()  # Hämtar product.id utan att committa

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p2.id, sku_id="SKU-002",
            return_risk="low", overall_score=75,
            prompt_version="2.0.0", total_tokens=400,
        ),
        AnalysisResult(
            product_id=p3.id, sku_id="SKU-003",
            return_risk="high", overall_score=30,
            prompt_version="2.0.0", total_tokens=400,
        ),
    ])
    sqlite_db.commit()
    return sqlite_db
```

### Catalog client fixture

```python
@pytest.fixture
def catalog_client(seeded_db):
    app.dependency_overrides[get_db] = lambda: seeded_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

Ingen service-override behövs — `catalog.py` använder ingen injicerad service.

### Korrekt statusvärde: `needs_review`, inte `not_enriched`

`CatalogProduct`-schemat definierar:

```python
status: Literal["enriched", "needs_review", "return_risk"]
```

`_determine_status()` returnerar `"needs_review"` (inte `"not_enriched"`) när
`ar is None`. Testerna ska använda detta faktiska värde från koden — inte värdet
som nämns i uppgiftsbeskrivningar.

### Pagination

`catalog.py` tar `page` (default 1) och `page_size` (default 10, max 100) som
query-params. Pagination testas via `?page_size=1` med fler än 1 produkt i databasen:
`total` ska vara > 1 men `products`-listan ska ha 1 element.

### SQLite + pgvector-risk

`app.main`-import kan trigga import av modeller som använder pgvector (t.ex.
`ProductEmbedding`). Befintliga enrich-tester (`test_api_enrich.py`) följer samma
mönster med `Base.metadata.create_all()` mot SQLite och passerar i Docker. Samma
mönster används här. Om pgvector-importen ger problem vid `create_all()` hanteras
det i implementationen (t.ex. genom selektiv modell-import).

## Berörda filer

Ny fil:
```
backend/tests/test_api_catalog.py
```

Läses (ej ändras):
```
backend/app/api/catalog.py
backend/app/schemas/catalog.py
backend/app/models/product.py
backend/app/models/analysis_result.py
backend/tests/conftest.py
backend/tests/test_api_enrich.py  (mönsterreferens)
```

## Acceptance Criteria

- `backend/tests/test_api_catalog.py` finns med minst 5 tester.
- `GET /api/v1/catalog` returnerar 200 och korrekt response-struktur.
- Produkt utan `AnalysisResult` får `status == "needs_review"`.
- Produkt med `AnalysisResult` och `return_risk != "high"` får `status == "enriched"`.
- Produkt med `return_risk == "high"` får `status == "return_risk"`.
- `?status=return_risk` returnerar bara produkter med high risk.
- `?search=` filtrerar på titel eller SKU.
- Pagination (`?page_size=`) begränsar antal produkter per sida korrekt.
- Inga riktiga AI-anrop eller PostgreSQL-anrop görs.
- Ingen produktionskod ändras.
- Befintliga backend-tester fortsätter passera:
  `docker compose exec backend pytest tests/` → 49 passed, 2 kända on_event-varningar.

## Testkrav

### Test 1: `GET /api/v1/catalog` — 200 happy path och response-struktur

Given:
- SQLite med minst 1 `Product`.

Expect:
- HTTP 200.
- Response innehåller `total`, `page`, `page_size`, `products`.
- `products` är en lista.

### Test 2: Produkt utan AnalysisResult → status `needs_review`

Given:
- `Product(sku_id="SKU-001")` utan AnalysisResult i databasen.

Expect:
- HTTP 200.
- Produkt finns i `products`.
- `status == "needs_review"`.
- `overall_score` är `null`.

### Test 3: Produkt med AnalysisResult, low risk → status `enriched`

Given:
- `Product(sku_id="SKU-002")` med `AnalysisResult(return_risk="low", overall_score=75)`.

Expect:
- HTTP 200.
- `status == "enriched"`.
- `overall_score == 75`.

### Test 4: Produkt med AnalysisResult, high risk → status `return_risk`

Given:
- `Product(sku_id="SKU-003")` med `AnalysisResult(return_risk="high", overall_score=30)`.

Expect:
- HTTP 200.
- `status == "return_risk"`.

### Test 5: `?status=return_risk` filtrerar korrekt

Given:
- 3 produkter: 1 utan AR, 1 med low risk, 1 med high risk.

Expect:
- HTTP 200.
- `total == 1`.
- Enda produkten i `products` har `status == "return_risk"`.

### Test 6: `?search=` filtrerar på titel

Given:
- Produkt med `title="Skor A"` och en produkt med `title="Jacka B"`.
- `GET /api/v1/catalog?search=Skor`

Expect:
- HTTP 200.
- `total == 1`.
- Produkt med `title` innehållandes "Skor" returneras.

### Test 7: Pagination begränsar svarslistan

Given:
- 3 produkter i databasen.
- `GET /api/v1/catalog?page_size=1`

Expect:
- HTTP 200.
- `len(products) == 1`.
- `total == 3`.
- `page == 1`, `page_size == 1`.

## Codex Review Notes

- **Viktigast:** Verifiera att testerna INTE mockar bort `db.query(Product, AnalysisResult)`.
  Dessa tester ska detektera regressioner i query-logiken, inte HTTP-lagret isolerat.
- Verifiera att `seeded_db.flush()` ger `product.id` korrekt i SQLite innan `AnalysisResult`
  sätts ihop med rätt `product_id`. Felaktig foreign key ger tyst fel om FK inte
  enforces (SQLite enforcar inte FK som default).
- Kontrollera att `app.dependency_overrides.clear()` körs i fixture teardown — även om
  testet failar mitt i.
- Kontrollera att response-schema-assertion inte är för skört: verifiera nycklar, inte
  exakta listor med alla ORM-fält.
- Kör mot baseline: `docker compose exec backend pytest tests/test_api_catalog.py -v`
  och sedan `docker compose exec backend pytest tests/` för regressionscheck.
- Verifiera att pgvector-relaterade imports inte bryter SQLite `create_all()` — om
  de gör det, rapportera som blocker med exakt felmeddelande.
- Kontrollera att `?search=Skor` i test 6 inte är case-sensitive beroende på SQLite
  vs PostgreSQL `ilike`-hantering. SQLite `LIKE` är case-insensitive för ASCII men
  case-sensitive för icke-ASCII. Notera detta om det påverkar testet.

## Risker

### 1. SQLite + `ilike` vs PostgreSQL

`catalog.py` (rad 102–107) använder `.ilike()` för fritextsökning. PostgreSQL:
case-insensitive. SQLite: `LIKE` är case-insensitive för ASCII-tecken men
case-sensitive för icke-ASCII. Testar vi med ASCII-tecken ("Skor", "SKU") fungerar
det. Om testtitlar innehåller icke-ASCII (å/ä/ö) kan SQLite ge annat resultat.

**Mitigation:** Använd ASCII-tecken i testdata och söktermer.

### 2. SQLite + `func.max()` subquery

`catalog.py` (rad 84–91) bygger en subquery med `func.max(AnalysisResult.id)`.
SQLite stödjer `MAX()` men kan bete sig annorlunda vid `outerjoin` med NULL-hantering.
Om ett test failar på detta bör det flaggas som blocker — det är ett tecken på att
SQLite-beteendet avviker från PostgreSQL.

### 3. Foreign key enforcement i SQLite

SQLite enforcar INTE `ForeignKey`-constraints som default. Det betyder att
`AnalysisResult(product_id=999)` inte failar även om produkt 999 inte finns.
Test 5 (statusfilter) kan ge felaktigt grönt resultat om testdata är fel.

**Mitigation:** Säkerställ att `seeded_db.flush()` körs innan `AnalysisResult` skapas
och att `product_id` sätts till faktiskt returnerat `product.id`.

### 4. `app.on_event("startup")` triggas av `with TestClient(app)`

`TestClient` i context-manager-form triggar startup-events. `create_tables()` i
`main.py` gör `CREATE EXTENSION IF NOT EXISTS vector` via PostgreSQL. I Docker-miljö
(med PostgreSQL) fungerar detta. I SQLite-isolation (utan PostgreSQL) kan detta faila.

Befintliga enrich-tester visar att mönstret fungerar i Docker. Risk är LOW för
Docker-körning. Om testerna körs lokalt utan Docker/PostgreSQL kan startup-felet
orsaka att testerna skippar eller crashar.

**Mitigation:** Kör tester via Docker som primary verifieringsväg (per TOOLING.md).

### 5. `needs_review` vs `not_enriched`

Specen (i instruktioner) nämner `status: not_enriched`, men koden och schemat
använder `"needs_review"`. Testerna ska använda `"needs_review"` — rätt värde finns
i `schemas/catalog.py` och `api/catalog.py::_determine_status()`.

## Definition of Done

- Claude Code har arbetat i en fil.
- `test_api_catalog.py` finns med minst 5 tester.
- Inga riktiga AI-anrop eller PostgreSQL-anrop görs.
- Befintliga backend-tester passerar utan regression.
- Codex har reviewat och godkänt.
- Ticketen markeras Done när testerna passerar och Codex-review är klar.

## Codex Review

Godkänd.

Verifierat:

- `backend/tests/test_api_catalog.py` finns med 7 HTTP-level tester.
- Testerna mockar inte bort `catalog.py`-queryn.
- Testerna använder SQLite in-memory med `StaticPool` och `check_same_thread=False`
  för FastAPI `TestClient`.
- Testdata skapas med riktiga `Product` och `AnalysisResult` ORM-rader.
- Statuslogiken för `needs_review`, `enriched` och `return_risk` är täckt.
- `status=return_risk`, `search=Skor` och `page_size=1` är täckta.
- Ingen produktionskod ändrades.

Testresultat:

```bash
docker compose exec backend pytest tests/test_api_catalog.py -v
```

Resultat: 7 passed, 2 kända FastAPI on_event-varningar.

```bash
docker compose exec backend pytest tests/
```

Resultat: 56 passed, 2 kända FastAPI on_event-varningar.
