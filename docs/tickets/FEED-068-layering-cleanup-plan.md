# FEED-068 — Layering Cleanup Plan

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

Sprint 1.5 (FEED-060–FEED-067) har stabiliserat AI control, testbaseline och endpoint
coverage. Backend baseline: 49 tester passerar i Docker, 2 kända FastAPI on_event-varningar.

CLAUDE.md och AGENTS.md kräver strikt layering:

```
API     → HTTP only
Service → business logic
Repo    → DB access
Model   → ORM definitions
Schema  → Pydantic
```

Under Sprint 1.5 visade reverse engineering och kodanalys att flera filer bryter mot
dessa regler. Problemet är känt (STATUS.md: "Layering — Dokumenterad strikt layering,
men vissa routes/services gör DB queries direkt — Arkitekturdrift"), men var exakt och
hur allvarligt är inte systematiskt kartlagt.

## Problem

Utan en konkret karta över layering-brotten kan vi inte refaktorera säkert. Att flytta
queries till repositories utan testskydd är en hög-risk-åtgärd. Att refaktorera utan
prioritering riskerar att vi börjar i fel ände.

Dessutom:
- Flera routes gör komplexa DB-joins direkt, utan repository och utan tester.
- Flera services gör direkta DB-queries trots att repositories finns.
- Repositories saknas helt för `Job`, `AnalysisResult` och `ProductEmbedding`.
- Print-statements lever kvar i api/enrich.py, workers/tasks.py och repositories.
- `create_tables()` på startup är dokumenterat som inte produktionsmoget men inte adresserat.

## Mål

Skapa ett konkret kartläggningsdokument med:
- Alla konstaterade layering-brott, filprecisa.
- Riskbedömning per fynd.
- Rekommenderad prioriteringsordning.
- Föreslagna framtida tickets per fynd.

**Ingen produktionskod ändras i FEED-068.**

## Scope

- Analysera och dokumentera layering-brott i `backend/app/api/`, `backend/app/services/`,
  `backend/app/repositories/`.
- Skapa tabell med fynd: fil, lager, problemtyp, risk, rekommenderad åtgärd, föreslagen
  framtida ticket.
- Uppdatera `docs/` med plan.
- Dokumentera saknade repositories.
- Dokumentera kvarvarande `print()`-anrop som inte täcktes av FEED-066.
- Dokumentera `create_tables()`-spåret som separat framtida ticket.

## Out of Scope

- Flytta queries till repositories.
- Skapa nya repositories.
- Ändra API-routes eller services.
- Ändra DB-modeller.
- Alembic/migrations.
- Frontend.
- Auth/multi-tenant.
- Inga nya produktionstester (analyskommandon accepteras).

## Layering-regler (referens)

Från CLAUDE.md och AGENTS.md:

| Lager | Tillåts | Förbjuds |
|---|---|---|
| API (`api/`) | HTTP, parse request, anropa service, returnera response | `db.query`, business logic, ORM-instantiering |
| Service (`services/`) | Business logic, anropa repositories | `db.query` direkt, ORM-queries |
| Repository (`repositories/`) | `db.query`, SQLAlchemy expressions | Business logic, AI-anrop |
| Model (`models/`) | ORM Column-style definition | Mapped[], business logic |
| Schema (`schemas/`) | Pydantic v2, ConfigDict | ORM-koppling |

## Analysmetod

Körda kommandon som underlag för kartläggningen nedan:

```bash
rg -n "db\.query|Session|Depends\(get_db\)" backend/app/api backend/app/services backend/app/repositories
rg -n "ProductRepository\(|AnalysisResult|Job\(" backend/app/api backend/app/services
rg -n "print\(" backend/app
rg -n "TODO|FIXME|direct query|create_tables" backend/app docs
```

## Fynd — Kartläggning

### Fynd 1: `api/catalog.py` — komplex join + business logic i route

| Fält | Värde |
|---|---|
| Fil | `backend/app/api/catalog.py` |
| Lager | API |
| Rad | 84–122 |
| Problemtyp | Direkt `db.query(Product, AnalysisResult)` med subquery och multi-join i route. Business-logikfunktion `_determine_status()` i route-filen. |
| Risk | **HIGH** |
| Testtäckning | Ingen |
| Orsak | Ingen `CatalogRepository` finns. Multi-join med subquery är komplex och svår att testa isolerat. `_determine_status()` är pure business logic som lever i fel lager. |
| Rekommenderad åtgärd | Skapa `CatalogRepository` med `get_catalog_page()`. Flytta `_determine_status()` till service eller repository. Lägg API-test med mock av service. |
| Föreslagen ticket | FEED-069 — Catalog repository extraction |

### Fynd 2: `api/products.py` — privata query-helpers + direkt DB-mutation

| Fält | Värde |
|---|---|
| Fil | `backend/app/api/products.py` |
| Lager | API |
| Rad | 33–49, 163–179 |
| Problemtyp | `_get_product_or_404()` (rad 34) och `_latest_analysis()` (rad 45) är privata helpers med `db.query` i route-filen. `apply_fields()` (rad 163) innehåller `_COLUMN_FIELDS`-logik och gör `db.commit()` direkt. |
| Risk | **HIGH** |
| Testtäckning | Ingen |
| Orsak | `ProductRepository` finns men används inte här. `AnalysisResultRepository` saknas. |
| Rekommenderad åtgärd | Flytta `_get_product_or_404` och `_latest_analysis` till `ProductRepository`. Skapa `AnalysisResultRepository`. Flytta `apply_fields`-logik till en service. |
| Föreslagen ticket | FEED-070 — Products route repository extraction |

### Fynd 3: `api/enrich.py` (enrich_bulk) — repository-instantiering + job-skapande i route

| Fält | Värde |
|---|---|
| Fil | `backend/app/api/enrich.py` |
| Lager | API |
| Rad | 72–113 |
| Problemtyp | `ProductRepository()` instantieras direkt i route (rad 72). `Job(...)` ORM-objekt skapas och `db.add(job); db.commit()` körs i route (rad 88–95). `create_pool` / ARQ-logik i route. Kandidatantal räknas i route. `print()` kvar (rad 74). |
| Risk | **HIGH** |
| Testtäckning | Ingen (`enrich_bulk` är explicit out of scope för FEED-067) |
| Orsak | Ingen `JobRepository` finns. Ingen `BulkEnrichService` finns. |
| Rekommenderad åtgärd | Skapa `JobRepository`. Flytta job-skapande och enqueueing till en `BulkEnrichService`. Route ska bara anropa service och returnera. Ta bort `print()`. |
| Föreslagen ticket | FEED-071 — BulkEnrichService + JobRepository extraction |

### Fynd 4: `api/jobs.py` — direkt db.query utan repository

| Fält | Värde |
|---|---|
| Fil | `backend/app/api/jobs.py` |
| Lager | API |
| Rad | 33, 64 |
| Problemtyp | `db.query(Job)` direkt i `list_jobs()` och `get_job()`. Ingen `JobRepository`. |
| Risk | **MEDIUM** |
| Testtäckning | Ingen |
| Orsak | `Job`-modellen har ingen dedikerad repository. |
| Rekommenderad åtgärd | Skapa `JobRepository` (kan ingå i FEED-071). Flytta queries dit. |
| Föreslagen ticket | FEED-071 (se ovan) |

### Fynd 5: `api/variants.py` — direkt Product-query i variants route

| Fält | Värde |
|---|---|
| Fil | `backend/app/api/variants.py` |
| Lager | API |
| Rad | 78, 232 |
| Problemtyp | `db.query(Product).filter_by(sku_id=...)` i `ingest_variants()` (rad 78) och `get_variants_by_sku()` (rad 232). Produkt-lookup sker i route-filen, inte via repository. |
| Risk | **MEDIUM** |
| Testtäckning | Ingen |
| Orsak | `ProductRepository.get_by_sku()` finns men injiceras inte i variants route. |
| Rekommenderad åtgärd | Injectera `ProductRepository` via `Depends()` i varianter route. Ersätt direkt query med `repo.get_by_sku()`. |
| Föreslagen ticket | FEED-072 — Variants route repository injection |

### Fynd 6: `services/ingestion_service.py` — direkt db.query i service

| Fält | Värde |
|---|---|
| Fil | `backend/app/services/ingestion_service.py` |
| Lager | Service |
| Rad | 133 |
| Problemtyp | `db.query(Product).filter_by(sku_id=...)` direkt i service-metoden för att kolla duplikat. |
| Risk | **MEDIUM** |
| Testtäckning | Täckt av FEED-061 service-tester (isolation via SQLite) |
| Orsak | `ProductRepository.get_by_sku()` finns men används inte här. |
| Rekommenderad åtgärd | Injicera/anropa `ProductRepository.get_by_sku()` i `ingest_feed()`. |
| Föreslagen ticket | FEED-073 — IngestionService repository usage |

### Fynd 7: `services/variant_enrichment_service.py` — cross-model db.query i service

| Fält | Värde |
|---|---|
| Fil | `backend/app/services/variant_enrichment_service.py` |
| Lager | Service |
| Rad | 130 |
| Problemtyp | `db.query(Product).filter_by(id=variant.product_id)` i `enrich_variant()` för att hämta förälderprodukten. |
| Risk | **MEDIUM** |
| Testtäckning | Ingen |
| Orsak | `ProductRepository` finns men injiceras inte i `VariantEnrichmentService`. |
| Rekommenderad åtgärd | Injicera `ProductRepository` i `VariantEnrichmentService`. Ersätt direkt query med repository-anrop. |
| Föreslagen ticket | FEED-072 (kan ingå i variants cleanup) |

### Fynd 8: `services/embedding_service.py` — direkt db.query utan repository

| Fält | Värde |
|---|---|
| Fil | `backend/app/services/embedding_service.py` |
| Lager | Service |
| Rad | 93, 127 |
| Problemtyp | `db.query(ProductEmbedding).filter_by(...).delete()` (rad 93) och `db.query(Product).limit(limit).all()` (rad 127) i service. Ingen `EmbeddingRepository`. |
| Risk | **MEDIUM** |
| Testtäckning | Ingen |
| Orsak | Ingen `EmbeddingRepository` existerar. Embeddinglogik är blandad: hämta produkter, radera gamla embeddings, skapa nya. |
| Rekommenderad åtgärd | Skapa `EmbeddingRepository`. Flytta delete/query-operationer dit. |
| Föreslagen ticket | FEED-074 — EmbeddingRepository extraction |

### Fynd 9: `services/enrichment_service.py` — direkt AnalysisResult-instantiering

| Fält | Värde |
|---|---|
| Fil | `backend/app/services/enrichment_service.py` |
| Lager | Service |
| Rad | 288 |
| Problemtyp | `AnalysisResult(...)` skapas och `db.add()` körs direkt i `enrich_product()`. Ingen `AnalysisResultRepository`. |
| Risk | **MEDIUM** |
| Testtäckning | Täckt av FEED-062/065B service-tester (SQLite isolation) |
| Orsak | Ingen `AnalysisResultRepository` existerar. |
| Rekommenderad åtgärd | Skapa `AnalysisResultRepository.save()`. Flytta `db.add(AnalysisResult(...))` dit. |
| Föreslagen ticket | FEED-075 — AnalysisResultRepository extraction |

### Fynd 10: Kvarvarande `print()`-anrop (ej täckta av FEED-066)

| Fil | Rad | Innehåll | Risk |
|---|---|---|---|
| `backend/app/api/enrich.py` | 74 | `print(f"[enrich_bulk] pre-flight: ...")` | LOW — täcks av FEED-071 |
| `backend/app/workers/tasks.py` | 61, 66 | `print(f"[enrich] ✓/✗ ...")` | LOW — separata ARQ-worker tickets |
| `backend/app/repositories/product_repository.py` | 90 | `print(...)` i semantic search | LOW |

FEED-066 ersatte `print()` i `core/ai.py`. Kvarvarande `print()` bör ersättas med
`logger.info/warning` i respektive framtida ticket.

### Fynd 11: `create_tables()` på startup

| Fält | Värde |
|---|---|
| Fil | `backend/app/core/database.py`, `backend/app/main.py` |
| Lager | Core/startup |
| Problemtyp | `create_tables()` (`Base.metadata.create_all()`) körs synkront på startup. Ingen Alembic migrations. |
| Risk | **HIGH (produktion)** |
| Nuläge | Accepterat för dev/MVP. Dokumenterat som "Inte produktionsmoget" i STATUS.md. |
| Rekommenderad åtgärd | Migrera till Alembic. Skapar separat track. |
| Föreslagen ticket | FEED-076 — Alembic migrations (separat spår, bör vänta tills multi-tenant är beslutat) |

## Saknade repositories (sammanfattning)

| Repository | Används av | Prioritet |
|---|---|---|
| `JobRepository` | `api/jobs.py`, `api/enrich.py` | HIGH — jobs centrala för ARQ-flödet |
| `AnalysisResultRepository` | `api/products.py`, `api/catalog.py`, `services/enrichment_service.py` | HIGH — central för enrichment |
| `EmbeddingRepository` | `services/embedding_service.py` | MEDIUM |
| `CatalogRepository` | `api/catalog.py` | HIGH — complex query, no coverage |

## Berörda filer

Analyserade filer (ingen ändras i FEED-068):

```
backend/app/api/catalog.py
backend/app/api/products.py
backend/app/api/enrich.py
backend/app/api/jobs.py
backend/app/api/variants.py
backend/app/services/ingestion_service.py
backend/app/services/variant_enrichment_service.py
backend/app/services/embedding_service.py
backend/app/services/enrichment_service.py
backend/app/repositories/product_repository.py
backend/app/core/database.py
backend/app/main.py
backend/app/workers/tasks.py
```

## Acceptance Criteria

- `docs/tickets/FEED-068-layering-cleanup-plan.md` finns med samtliga fynd.
- Varje fynd har: fil, lager, radnummer, problemtyp, risk, testtäckning, rekommenderad
  åtgärd och föreslagen ticket.
- Saknade repositories är listade.
- Kvarvarande `print()`-anrop är dokumenterade.
- `create_tables()`-spåret är dokumenterat som separat ticket.
- Ingen produktionskod är ändrad.
- Befintliga 49 backend-tester passerar utan regression.

## Testkrav / verifiering

Inga nya tester i FEED-068. Verifiera att befintliga tester fortfarande passerar:

```bash
docker compose exec backend pytest tests/
```

Förväntat resultat: 49 passed, 2 kända FastAPI on_event-varningar.

## Codex Review Notes

- Granska att alla fynd är filprecisa (radnummer stämmer).
- Verifiera att riskklassificeringen är rimlig mot AGENTS.md FeedPilot-Specific Code Smells.
- Kontrollera att prioriteringsordningen för framtida tickets är logisk:
  - Repositories med högst täckningsgap bör komma före de med befintlig service-testtäckning.
  - `create_tables()`-spåret bör vänta tills multi-tenant-beslutet är taget.
- Flagga om något HIGH-fynd saknas i analysen.
- Flagga om föreslagen ticket-indelning är för grov (t.ex. FEED-071 är stor — bör eventuellt
  delas i `JobRepository` och `BulkEnrichService`).

## Risker

- Analysen är baserad på statisk kodläsning och grep-output. Det kan finnas ytterligare
  indirekt DB-access via helper-funktioner som inte visas direkt i grep-resultaten.
- `api/catalog.py` är den komplexaste route-filen. Refaktor kräver testskydd INNAN
  flytten — annars är regressionsrisken hög.
- `services/enrichment_service.py` har service-tester (FEED-062, FEED-065B). Trots det
  finns `AnalysisResult`-instantiering direkt i servicen — refaktor här är lägre risk
  än i otestade routes.
- `create_tables()` ska INTE ersättas med Alembic förrän multi-tenant-arkitekturen är
  beslutad — schema-design påverkas av tenant-isolering.
- Ticket-indelning (FEED-069–076) är preliminär. Codex bör justera scope och prioritet
  i respektive ticket innan Claude Code börjar implementera.

## Prioriterad ticket-plan

| Prio | Ticket | Motivation |
|---|---|---|
| 1 | FEED-069 — CatalogRepository | Störst brott, ingen testtäckning, komplex query |
| 2 | FEED-070 — Products route repo extraction | `_get_product_or_404` + `_latest_analysis` + apply_fields — central route, ingen testtäckning |
| 3 | FEED-071 — JobRepository + BulkEnrichService | Job-skapande i API-lagret är HIGH-risk, blockar observability |
| 4 | FEED-072 — Variants route + service cleanup | Lägre risk, men direkt query i route |
| 5 | FEED-073 — IngestionService repo usage | Har viss testtäckning, lägre prioritet |
| 6 | FEED-074 — EmbeddingRepository | Minimal affärspåverkan tills search används mer |
| 7 | FEED-075 — AnalysisResultRepository | Service har tester, refaktor är säkrare |
| 8 | FEED-076 — Alembic migrations | Separat spår, väntar på multi-tenant-beslut |

## Definition of Done

- Kartläggningsdokument finns och är Codex-reviewat.
- Alla fynd är filprecisa med radnummer.
- Prioriterad ticket-plan är godkänd av Codex.
- Inga produktionskodändringar.
- 49 backend-tester passerar.
- Ticketen markeras Done när Codex-review är klar och ticket-planen är godkänd.

## Codex Review

Godkänd.

Verifierat:

- Fynden är filprecisa och stöds av `rg`-underlag.
- HIGH-risk-fynden i `api/catalog.py`, `api/products.py`, `api/enrich.py` och
  `create_tables()`-spåret är rimligt prioriterade.
- Saknade repositories är dokumenterade.
- Kvarvarande `print()`-anrop är dokumenterade.
- Ingen produktionskod ändrades.
- Ticket-planen FEED-069 till FEED-076 är rimlig som preliminär ordning.

Notering:

- `FEED-071 — JobRepository + BulkEnrichService` är sannolikt stor nog att delas i
  två implementationstickets när den skrivs.
- `FEED-076 — Alembic migrations` bör fortsatt vänta tills multi-tenant-strategin är
  beslutad.

Testresultat:

```bash
docker compose exec backend pytest tests/
```

Resultat: 49 passed, 2 kända FastAPI on_event-varningar.
