# FEED-061 — Ingestion Test Coverage

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

Ingestion är ett kärnflöde i FeedPilot:

```txt
CSV/XLSX
  -> connector
  -> FieldMapper
  -> CanonicalProduct
  -> normalize_row
  -> validate_row
  -> Product
  -> database
```

Men `backend/tests/test_ingest.py` är tom. Det betyder att en av appens viktigaste pipelines inte har aktiv testtäckning.

Vi behöver börja med service-nivåtester för ingestion innan vi refaktorerar AI/enrichment-flöden.

## Problem

Nuvarande testbaseline säger att backendtester passerar, men det betyder inte att ingestion är verifierat.

Risker utan ingestion-tester:

- CSV parsing kan gå sönder utan att vi märker det.
- Field mapping kan mappa fel fält till canonical schema.
- Missing SKU kan orsaka felaktig DB-state.
- Duplicate SKU/update-beteende kan regressera.
- Quality warnings kan försvinna.

## Mål

Lägg till riktiga tester för `IngestionService` med befintliga fixtures.

Första versionen ska testa service-lagret, inte hela HTTP-route-lagret.

Varför service-lagret först:

- snabbare
- mindre flakigt
- lättare att isolera DB och pipeline
- täcker det viktigaste affärsflödet

## Berörda filer

Claude Code får bara ändra en fil i taget.

Primär fil för denna ticket:

- `backend/tests/test_ingest.py`

Tillåtna efter separat godkännande:

- `backend/tests/conftest.py`
- `backend/tests/fixtures/*.csv`
- `backend/app/services/ingestion_service.py`

Inga produktionskodfiler ska ändras i första passet.

## Nuvarande fixtures

Tillgängliga filer:

- `backend/tests/fixtures/test_feed.csv`
- `backend/tests/fixtures/test_bad.csv`
- `backend/tests/fixtures/new_products.csv`
- `backend/tests/fixtures/test_feed.xlsx`

Relevant innehåll:

### `test_feed.csv`

```csv
sku,title,description,category,price,color,size,brand
SHOE-001,Skor,Fina skor.,Kläder,299.00,svart,,
SHOE-002,Ecco Derby Herrskor i Svart Läder — Storlek 42,Klassisk derby-sko i äkta kalvskinn med lädersula. Tillgänglig i storlek 40-46.,Skor > Herrskor > Derby,1299.00,svart,42,Ecco
JACK-042,Fjällräven Kånken Laptop 15 Ryggsäck — Mörkgrön 23L,Den klassiska Kånken-ryggsäcken med dedikerat laptopfack för 15-tums datorer. Tillverkad i Vinylon F.,Väskor > Ryggsäckar,1095.00,mörkgrön,,Fjällräven
```

### `test_bad.csv`

```csv
sku,title,description,category,price
,Skor utan SKU,En beskrivning,Kläder,299
SHOE-001,Skor med SKU,En beskrivning,Kläder,299
```

## Krav

### 1. Skapa service-tester i `backend/tests/test_ingest.py`

Testerna ska importera:

```python
from app.models.product import Base, Product
from app.services.ingestion_service import IngestionService
```

Testerna bör använda en isolerad SQLite in-memory DB för service-lagret.

Rekommenderat fixture-mönster:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
```

Varje test ska ha ren DB.

### 2. Test: CSV skapar produkter

Scenario:

- Läs `test_feed.csv`.
- Kör `IngestionService().ingest_csv(contents, "auto", db)`.

Förväntningar:

- `total == 3`
- `created == 3`
- `updated == 0`
- `skipped == 0`
- `detected_source == "generic_csv"`
- DB innehåller 3 `Product`
- `SHOE-002` har `attributes["brand"] == "Ecco"`
- `SHOE-002` har `attributes["size"] == "42"`
- `SHOE-002.price == 1299.00`

### 3. Test: CSV med saknad SKU skippar dålig rad

Scenario:

- Läs `test_bad.csv`.
- Kör `ingest_csv`.

Förväntningar:

- `total == 2`
- `created == 1`
- `skipped == 1`
- warnings innehåller `sku_id`
- DB innehåller bara en produkt
- produkten har `sku_id == "SHOE-001"`

### 4. Test: duplicate SKU uppdaterar befintlig produkt

Scenario:

1. Kör `test_feed.csv` en gång.
2. Kör samma `test_feed.csv` igen.

Förväntningar efter andra körningen:

- `created == 0`
- `updated == 3`
- DB innehåller fortfarande 3 produkter

### 5. Test: new_products.csv importerar extra canonical fields

Scenario:

- Läs `new_products.csv`.
- Kör `ingest_csv`.

Förväntningar:

- `created == 10`
- `detected_source == "generic_csv"`
- `JACKET-001.attributes["brand"] == "Hugo Boss"`
- `JACKET-001.attributes["material"] == "Wool"`
- `JACKET-001.attributes["gender"] == "Male"` om gender stöds via canonical/extra attributes.

Om gender inte mappas som canonical field i nuvarande implementation, dokumentera det i testkommentar eller justera förväntan till faktisk behavior. Testet ska inte kräva produktionskodändring i första passet.

## Acceptance Criteria

- `backend/tests/test_ingest.py` är inte längre tom.
- Minst 4 ingestion service-tester finns.
- Testerna använder isolerad DB per test.
- Testerna kräver inga riktiga externa tjänster.
- Testerna gör inga riktiga AI-anrop.
- Backend testkommandot passerar:

```bash
docker compose exec backend pytest tests/
```

## Testkrav

Codex ska köra:

```bash
docker compose exec backend pytest tests/
```

Efteråt ska baseline för backend öka från:

```txt
12 tests
```

till minst:

```txt
16 tests
```

## Risker

- SQLite beter sig inte exakt som PostgreSQL JSON/SQLAlchemy i alla lägen.
- `Base.metadata` innehåller flera modeller om fler imports sker; håll testet minimalt.
- IngestionService gör direkta `db.query(Product)` trots repository-regeln. Ticketen ska testa nuvarande behavior, inte refaktorera den.
- Om testet kräver produktionskodändring är scope för stort. Stoppa och be om review.

## Out of Scope

Detta ska inte göras i FEED-061 första pass:

- API endpoint-tester för `/api/v1/ingest/*`
- refaktor av IngestionService till repository
- nya fixtures
- ändringar i production ingestion logic
- Excel/XLSX-test om det kräver extra setup

## Definition of Done

- Claude Code har bara ändrat tillåtna filer.
- `backend/tests/test_ingest.py` innehåller riktiga tester.
- Codex har reviewat testerna.
- Codex har kört backendtesterna i Docker.
- Ticketen markeras Done först när testerna passerar eller blocker är dokumenterad.

## Codex Review — 2026-04-29

Resultat: Godkänd.

Ändringar:

- `backend/tests/test_ingest.py` innehåller nu 4 service-level tester för `IngestionService`.
- Testerna använder SQLite in-memory DB per test.
- Testerna täcker CSV import, missing SKU skip, duplicate SKU update och extra/canonical attributes från `new_products.csv`.
- Codex gjorde en liten review-fix i en testkommentar för att hålla kodfilen ASCII.

Verifiering:

```bash
docker compose exec backend pytest tests/
# 16 passed, 2 FastAPI on_event deprecation warnings
```

Notering:

- Varningarna är kända och blockerar inte.
- API endpoint-tester för `/api/v1/ingest/*` är fortfarande out of scope och bör tas senare.
