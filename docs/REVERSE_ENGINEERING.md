# Reverse Engineering: FeedPilot

Detta dokument ar arbetsytan for att forsta FeedPilot bakifran: vilka delar som finns, vilket ansvar varje fil har, hur filerna kopplas ihop, vilka monster som aterkommer och vilka risker som syns i koden.

Formatet ar medvetet praktiskt:

- **Ansvar**: vad filen ar till for.
- **Kopplingar**: vilka filer den anropar eller anropas av.
- **Monster**: arkitekturmonster eller kodstil som upprepas.
- **Risker / fragor**: saker att verifiera innan produktion eller storre refaktorering.

Status: forsta pass. Centrala filer ar analyserade djupare. Resterande filer ar katalogiserade sa att vi kan ga igenom dem en i taget.

---

## 1. Systemoversikt

FeedPilot ar en AI-driven produktdata-plattform for e-handel. Systemet tar emot produktfeeds, normaliserar data, bedomer kvalitet, enrichar produktfalt med Claude, skapar embeddings med OpenAI och visar resultat i ett Next.js-granssnitt.

High-level runtime:

```txt
Browser
  |
  v
Next.js frontend (:3000)
  |
  v
FastAPI backend (:8010 -> container :8000)
  |
  +--> PostgreSQL + pgvector (:5433 -> container :5432)
  |
  +--> Redis (:6380 -> container :6379)
          |
          v
      ARQ worker
```

Huvuddelar:

- `frontend/`: Next.js App Router, UI, API-klient och typer.
- `backend/app/api/`: FastAPI routes.
- `backend/app/services/`: business logic och orkestrering.
- `backend/app/repositories/`: SQLAlchemy-fragor.
- `backend/app/models/`: ORM-tabeller.
- `backend/app/schemas/`: Pydantic-kontrakt.
- `backend/app/workers/`: ARQ bakgrundsjobb.
- `backend/app/prompts/`: versionerade AI-prompter.
- `backend/app/ingestion/`: feed-import, schema-detektering, mapping och validering.

---

## 2. Arkitektur (High-level)

Dokumenterad avsikt i `CLAUDE.md`:

```txt
API -> Service -> Repository -> Model/Database
```

Ny AI-princip:

```txt
AI ska styras av kod, inte av prompt.
```

Det betyder:

- prompten får beskriva uppgiften
- kod måste äga schema, validering och tillåtna värden
- kod måste bestämma workflow state, scoring, risknivåer och persistence
- prompttext får aldrig vara den enda säkerhetsgränsen
- AI-output ska behandlas som osäker extern input tills den är parsad och validerad
- web search, bildanalys, RAG och modellval måste aktiveras explicit i backend-logik eller konfiguration
- prompten får aldrig vara mekanismen som "tillåter" eller "förbjuder" ett verktyg

Målbild:

FeedPilot ska vara ett AI-drivet enrichment-system, inte en enkel prompt-wrapper.

Det betyder att kvalitet, kostnad och tillförlitlighet ska komma från:

- arkitektur
- datamodell
- canonical schema
- fältmetadata
- explicit verktygsstyrning
- input-minimering
- kodvalidering
- observability

inte från att prompten hoppas på rätt beteende.

Bakgrundsjobb anvander samma service-lager:

```txt
Worker -> Service -> Repository -> Model/Database
```

AI-flode:

```txt
Product ORM
  -> CanonicalProduct
  -> RAG context via pgvector
  -> Claude prompt
  -> JSON parsing
  -> AnalysisResult
```

Målflöde för enrichment:

```txt
user starts enrichment intent
  -> backend preflight
  -> show product count, fields, tools, model strategy, token estimate, cost estimate
  -> user confirms
  -> queue/batch execution
  -> per-product field plan
  -> minimal model input
  -> AI call
  -> parse
  -> validate
  -> store
  -> log tokens/cost/model/tools/status
```

Pipeline-regel:

```txt
extract -> normalize -> enrich -> validate -> store
```

Feed-ingestion:

```txt
CSV/XLSX upload
  -> connector
  -> FieldMapper
  -> CanonicalProduct
  -> normalize_row
  -> validate_row
  -> Product
```

Observerad drift fran avsedd arkitektur:

- Vissa API-routes gor direkta `db.query(...)` trots att `CLAUDE.md` sager att queries ska ligga i repositories.
- Vissa services gor direkta queries, framfor allt dar repository-lager saknas eller ar ofullstandigt.
- `create_tables()` anvands pa startup trots att dokumentation namner migrations/Alembic.

---

## 3. Mappstruktur & Ansvar

```txt
feedpilot/
  backend/
    app/
      api/             HTTP endpoints
      core/            config, DB, AI-klienter, image/embedding helpers
      ingestion/       feed connectors, mapping, normalisering, validering
      models/          SQLAlchemy ORM
      prompts/         prompt manager och promptversioner
      repositories/    databasfragor
      schemas/         Pydantic/API-kontrakt
      services/        business logic
      workers/         ARQ settings och tasks
    tests/             backend tester
  frontend/
    app/               Next.js routes/pages
    components/        UI/layout-komponenter
    lib/               API-klient och typer
    __tests__/         frontend tester
  docs/                produkt-, arkitektur- och reverse engineering-dokument
  tests/fixtures/      extra produktfeed fixtures
```

---

## 4. Dataflode

### CSV/XLSX till produkt

```txt
frontend UploadModal / page
  -> frontend/lib/api.ts
  -> POST /api/v1/ingest/csv eller /xlsx
  -> backend/app/api/ingest.py
  -> IngestionService
  -> csv_connector.py / xlsx_connector.py
  -> FieldMapper + schema_registry
  -> CanonicalProduct
  -> normalizer.py
  -> validators.py
  -> Product model
  -> PostgreSQL
```

### Produkt till enrichment

```txt
Product detail page / bulk action
  -> frontend/lib/api.ts
  -> /api/v1/products/{sku_id}/enrich eller /api/v1/enrich/{sku_id}
  -> EnrichmentService
  -> ProductRepository.get_by_sku
  -> CanonicalProduct
  -> ProductRepository.semantic_search
  -> core/embeddings.py + pgvector
  -> core/ai.py ask_claude
  -> prompt_manager.py + v2_enrichment.py
  -> AnalysisResult model
```

### Bulk enrichment

```txt
POST /api/v1/enrich/bulk
  -> create Job
  -> enqueue ARQ job in Redis
  -> worker settings
  -> enrich_bulk_task
  -> EnrichmentService.enrich_product per product
  -> update Job progress
```

### Image analysis

```txt
Image upload or URL
  -> /api/v1/images/*
  -> ImageAnalysisService
  -> core/image.py prepare image
  -> core/ai.py ask_claude_vision
  -> v4_image_analysis.py prompt
  -> ImageAnalysis schema response
```

---

## 5. Backend-analys

### Fil: `docker-compose.yml`

**Ansvar**

Startar lokal infrastruktur:

- `backend`: FastAPI via Uvicorn.
- `postgres`: PostgreSQL med pgvector.
- `redis`: job queue for ARQ.
- `worker`: ARQ worker som kor backend-kod.

**Kopplingar**

- `backend` och `worker` byggs fran `backend/Dockerfile`.
- `backend` startar `app.main:app`.
- `worker` startar `app.workers.settings.WorkerSettings`.
- Bada laser miljovariabler fran `backend/.env`.

**Monster**

Samma kodbas kor tva processroller:

```txt
API-process:    uvicorn app.main:app
Worker-process: arq app.workers.settings.WorkerSettings
```

Detta ar skalen till service-lagret: business logic maste kunna ateranvandas fran bade API och worker.

**Risker / fragor**

- Frontend ar inte med i Compose.
- `backend` beror bara pa `postgres`, men endpoints som koar jobb behover aven `redis`.
- `platform: linux/arm64` ar bra for Apple Silicon men kan vara fel i annan miljö.

### Fil: `backend/Dockerfile`

**Ansvar**

Bygger Python-miljon for bade API och worker.

**Kopplingar**

- Anvands av `docker-compose.yml` for `backend` och `worker`.
- Installerar `requirements-dev.txt`, inte bara `requirements.txt`.
- Kopierar hela backend-katalogen till `/app`.

**Monster**

En image, flera commands. Compose bestammer processroll.

**Risker / fragor**

- Dev dependencies hamnar i runtime-image.
- `--platform=linux/arm64` ar hardcoded.
- `ffmpeg`, `libavif-dev` och `libdav1d-dev` finns for image/AVIF-stod.

### Fil: `backend/app/main.py`

**Ansvar**

Backendens entrypoint/bootstrap. Skapar FastAPI-appen, satter CORS, skapar tabeller pa startup och inkluderar alla routers.

**Kopplingar**

Importerar:

- `get_settings()` fran `core/config.py`.
- `create_tables()` fran `core/database.py`.
- alla routers fran `api/`.

Anropas av:

- Uvicorn-kommandot i `docker-compose.yml`.
- Dockerfile default CMD.

**Monster**

Central router-registrering:

```python
app.include_router(health_router, prefix="/api/v1")
```

Alla API-moduler ager sin egen path-prefix, till exempel `prefix="/products"` i `api/products.py`.

**Risker / fragor**

- `@app.on_event("startup")` ar legacy-stil i nyare FastAPI; lifespan ar modernare.
- `create_tables()` pa startup passar lokal dev men inte robust migrationsflode.
- CORS tillater bara localhost:3000 och 127.0.0.1:3000.

### Fil: `backend/app/core/config.py`

**Ansvar**

Laddar applikationskonfiguration med Pydantic Settings.

**Kopplingar**

Anvands av:

- `main.py` for app name/version/debug.
- `database.py` for `database_url`.
- `ai.py` och `embeddings.py` for API-nycklar.
- `workers/settings.py` for Redis host/port.

**Monster**

`@lru_cache` gor settings till singleton per process.

**Risker / fragor**

- Default `database_url` ar tom sträng. Appen failar sent om `.env` saknas.
- `REDIS_URL` namns i docs, men koden anvander `redis_host` och `redis_port`.

### Fil: `backend/app/core/database.py`

**Ansvar**

Skapar SQLAlchemy engine, session factory, FastAPI DB dependency och tabeller.

**Kopplingar**

- Importerar `Base` fran `models/product.py`.
- Importerar alla andra modeller inuti `create_tables()` sa de registreras pa samma metadata.
- `get_db()` anvands i API-routes.
- `SessionLocal` anvands i ARQ worker tasks.

**Monster**

Gemensam DB-session-factory for API och worker:

```txt
FastAPI request -> get_db()
Worker task     -> SessionLocal()
```

**Risker / fragor**

- `Base` definieras i `models/product.py`, vilket gor product-modellen till metadata-rot.
- Inga migrations i detta flode.
- `CREATE EXTENSION IF NOT EXISTS vector` kraver ratt DB-privilegier.

### Fil: `backend/app/core/ai.py`

**Ansvar**

Wrapper runt Anthropic Claude API for text och vision.

**Kopplingar**

- Anvander `get_settings()` for `anthropic_api_key`.
- Anvander `prepare_image_for_vision()` fran `core/image.py`.
- Anvands av enrichment, variant enrichment och image analysis services.

**Monster**

AI-klientlogik ar centraliserad. Services skickar prompt/system och far tillbaka `answer` + token usage.

**Risker / fragor**

- Modellen ar hardcodad till `claude-sonnet-4-6`.
- Retry hanterar specifikt HTTP 529.
- Vision-funktionen kontrollerar inte `stop_reason == "max_tokens"` pa samma satt som text-funktionen.

### Fil: `backend/app/core/embeddings.py`

**Ansvar**

Skapar embeddings via OpenAI.

**Kopplingar**

- Anvands av `ProductRepository.semantic_search`.
- Anvands indirekt av RAG/enrichment.

**Monster**

Embedding-skapande ar avskilt fran repository men anropas inifran repository for semantic search.

**Risker / fragor**

- Om API-nyckel saknas faller RAG/enrichment som beror pa semantic search.

### Fil: `backend/app/core/image.py`

**Ansvar**

Forbereder produktbilder for Claude Vision: format, storlek och kompatibilitet.

**Kopplingar**

- Anvands av `core/ai.py::ask_claude_vision`.
- Beror pa Pillow, AVIF-plugin och ffmpeg-relaterade bibliotek.

**Monster**

Image preprocessing ligger i core, inte i service, vilket haller vision-service renare.

### Fil: `backend/app/api/ingest.py`

**Ansvar**

HTTP endpoints for CSV/XLSX-uppladdning.

**Kopplingar**

- Anvander `IngestionService`.
- Anvander `get_db`.
- Returnerar `IngestResponse`.

**Monster**

Route gor HTTP-validering: filstorlek, filtyp, exception mapping. Business logic skickas till service.

### Fil: `backend/app/services/ingestion_service.py`

**Ansvar**

Orkestrerar hela feed-ingestion pipeline.

**Kopplingar**

- Connectors: `csv_connector.py`, `xlsx_connector.py`.
- Mapping: `FieldMapper`.
- Schema: `CanonicalProduct`.
- Normalisering: `normalize_row`.
- Validering: `validate_row`.
- Modell: `Product`.

**Monster**

Pipeline-monster:

```txt
read -> map -> normalize -> validate -> upsert
```

**Risker / fragor**

- Service gor direkta `db.query(Product)` trots repository-regeln.
- `filename` parameter finns i `_run_pipeline()` men anvands inte for logik.

### Fil: `backend/app/services/enrichment_service.py`

**Ansvar**

Orkestrerar enrichment for en eller flera produkter.

**Kopplingar**

- Repository: `ProductRepository`.
- AI: `ask_claude`.
- Prompts: `prompt_manager.py`.
- Schema: `CanonicalProduct`.
- Model: `AnalysisResult`.

**Monster**

Service ar hjartat av AI-flodet:

```txt
Product -> CanonicalProduct -> RAG -> Claude -> JSON -> AnalysisResult
```

**Risker / fragor**

- Persisterar `AnalysisResult` direkt i service. Det bryter strikt repository-monster, men ar pragmatiskt just nu.
- RAG semantic search kraver fungerande embeddings; annars kan enrichment faila.

### Fil: `backend/app/repositories/product_repository.py`

**Ansvar**

Databasfragor for produkter och semantic search.

**Kopplingar**

- Anvander `Product`.
- Anvander `AnalysisResult` i `get_unenriched`.
- Anvander `create_embedding()`.
- Anvands av `EnrichmentService` och bulk endpoints.

**Monster**

Repository kapslar vanliga product queries och pgvector search.

**Risker / fragor**

- `semantic_search()` bygger SQL med f-string. `chunk_type` bor parameteriseras.
- `print()` debug-logg bor ersattas med logging.

### Fil: `backend/app/workers/settings.py`

**Ansvar**

Konfigurerar ARQ worker: Redis och vilka task-funktioner som ar tillatna.

**Kopplingar**

- Startas av Compose-kommandot `arq app.workers.settings.WorkerSettings`.
- Importerar `enrich_bulk_task` och `embed_all_task`.
- Laser Redis host/port fran config.

### Fil: `backend/app/workers/tasks.py`

**Ansvar**

Bakgrundsjobb for bulk enrichment och embedding-skapande.

**Kopplingar**

- Anvander `SessionLocal`.
- Uppdaterar `Job`.
- Anvander `ProductRepository`, `EnrichmentService` och `EmbeddingService`.

**Monster**

Worker skapar egen DB-session, uppdaterar job state stegvis och stanger session i `finally`.

**Risker / fragor**

- Om `Job` inte hittas blir `job.status = ...` ett fel.
- `print()` med specialtecken finns i worker logs.

---

## 6. Frontend-analys

### Fil: `frontend/app/layout.tsx`

**Ansvar**

Root layout for Next.js appen. Satter HTML-sprak, metadata, global CSS och permanent sidebar.

**Kopplingar**

- Importerar `globals.css`.
- Importerar `Sidebar`.
- Wrappar alla pages under `app/`.

**Monster**

Dashboard-app-layout: sidebar till vanster, scrollande main-yta.

**Risker / fragor**

- `ml-64` for main ar hardcoded till sidebar-bredd. Mobilresponsivitet behover verifieras.

### Fil: `frontend/lib/api.ts`

**Ansvar**

Central Axios-klient och API-helper-funktioner.

**Kopplingar**

- Anvands av frontend pages/components for backend requests.
- `NEXT_PUBLIC_BACKEND_URL` styr backend-basurl.

**Monster**

En central API-klient for hela frontend.

**Risker / fragor**

- Vissa helpers pekar pa `/api/v1/products`, men backendens list-endpoint verkar vara `/api/v1/catalog`.
- Blanda generiska `get/post/patch` med named helpers kan skapa inkonsekvent anvandning.

### Fil: `frontend/lib/types.ts`

**Ansvar**

Delade TypeScript-typer for API-responses och UI-data.

**Kopplingar**

- Anvands av pages och komponenter.
- Speglar Pydantic schemas i backend.

**Monster**

Frontend har explicit kontraktslager, men det ar manuellt synkat.

**Risker / fragor**

- Risk for drift mellan Pydantic schemas och TS interfaces.
- `JobResponse.status` accepterar flera statusnamn som tyder pa historisk API-drift.

---

## 7. Workers & Async-floden

ARQ anvands for langa jobb:

- bulk enrichment
- embedding generation

Job lifecycle:

```txt
queued -> running -> completed
queued -> running -> failed
```

Viktiga filer:

- `backend/app/api/enrich.py`: skapar och koar enrichment-jobb.
- `backend/app/api/embeddings.py`: skapar embedding-jobb.
- `backend/app/api/jobs.py`: listar/hamtar status.
- `backend/app/models/job.py`: job-tabellen.
- `backend/app/schemas/job.py`: API-kontrakt.
- `backend/app/workers/settings.py`: ARQ config.
- `backend/app/workers/tasks.py`: faktiska jobb.

---

## 8. AI/Prompt-system

AI-systemet ar versionerat via promptfiler, men FeedPilot ska inte byggas som en prompt-baserad wrapper.

Målet är ett AI-drivet enrichment-system där backend-kod styr:

- vilka produkter som körs
- vilka fält som berikas
- vilken modell som används
- vilka verktyg som aktiveras
- vilken input modellen får
- hur output valideras
- vad som får sparas
- hur kostnad och kvalitet följs upp

Viktig arkitekturregel:

```txt
AI måste styras av kod, inte prompt.
```

Promptfilerna får ge Claude instruktioner om roll, format och uppgift. Men om en regel påverkar produktens beteende måste den finnas i kod:

- Pydantic schemas
- service-validering
- domänregler
- enum-värden
- parsing
- tester
- persistence-logik

Exempel:

```txt
Dåligt:
  "Prompten säger att Claude bara ska returnera high|medium|low."

Bättre:
  Pydantic/schema validerar att return_risk är high|medium|low.
```

### Preflight före enrichment

Innan en större eller dyr enrichment startar ska backend göra en preflight.

Preflight ska beräkna och visa:

- antal produkter
- vilka fält som kommer bearbetas
- vilka verktyg som krävs, till exempel RAG, web search eller bildanalys
- modellstrategi per fält eller fälttyp
- uppskattad input-tokenförbrukning
- uppskattad output-tokenförbrukning
- uppskattad kostnad
- batchstorlek eller köstrategi

Först efter användarens bekräftelse ska jobbet köas eller köras.

Varför:

- undviker oväntade kostnader
- gör bulk-körningar kontrollerbara
- gör det möjligt att avbryta innan dyra AI-anrop
- tvingar systemet att planera innan det genererar

### Batch/kö som standard

Enrichment ska köras i begränsade batchar eller via kö.

Systemet ska inte skicka ett obegränsat antal produkter direkt till AI-flödet.

Kod ska kontrollera:

- batch size
- concurrency
- retry
- partial failure
- job status
- progress
- failed count
- total count

Detta passar redan projektets ARQ-inriktning, men nuvarande bulkflöde behöver kompletteras med preflight och tydligare kostnads-/fältplan.

### Fältmetadata styr enrichment

För varje canonical field bör systemet veta:

- om fältet kan berikas
- vilken input som är relevant
- om fältet kräver extern information
- om fältet kräver bildanalys
- om fältet kan genereras med billig modell
- om fältet kräver starkare modell
- om fältet får skrivas tillbaka automatiskt eller kräver review

Exempel på önskad mental modell:

```txt
canonical field: description
  complexity: high
  model: strong
  tools: optional RAG
  input: title, brand, category, material, target audience
  requires_review: true

canonical field: color
  complexity: low
  model: cheap
  tools: image_analysis if image exists
  input: title, attributes, image result
  requires_review: false or configurable
```

### Input-minimering

Den största kostnadsdrivaren i AI-system är ofta input-tokens.

Därför ska modellen inte få hela produktobjektet som default.

Kod ska bygga en minimal payload per uppgift:

```txt
Dåligt:
  skicka Product.raw_data + alla attributes + all historik till modellen

Bättre:
  skicka bara de fält som behövs för just description-enrichment
```

Det kräver:

- canonical schema
- field relevance metadata
- task planner
- token estimator
- tester som skyddar mot regressions där payload växer okontrollerat

### Dynamiskt modellval

Modellval ska ske i backend-logik, inte i prompten.

Enkla uppgifter bör använda billigare/snabbare modeller:

- korta attribut
- enklare title cleanup
- keyword extraction
- formatnormalisering

Mer avancerade uppgifter kan använda starkare modeller:

- produktbeskrivningar
- komplex return risk analysis
- multimodal bedömning
- högvärdesprodukter där precision är viktig

Kod/config ska äga routingregeln.

Prompten kan säga vad modellen ska göra efter att kod redan valt modell.

### Explicit verktygsstyrning

Verktyg ska aldrig aktiveras via promptinstruktioner som:

```txt
"Använd web search om det behövs."
```

Det är för svagt.

Backend ska bestämma:

- web search allowed: yes/no
- image analysis allowed: yes/no
- RAG context allowed: yes/no
- external lookup required: yes/no
- max calls per product
- max cost per product/job

Språkmodeller är inte deterministiska och kan ignorera instruktioner. Därför måste verktygsstyrning vara kod/config, inte prompt.

### Observability

Varje AI-request bör logga:

- product id / sku
- job id
- fält som bearbetades
- modell
- verktyg
- input tokens
- output tokens
- uppskattad kostnad
- faktisk kostnad om tillgänglig
- status
- felorsak
- latency
- promptversion

Utan detta kan systemet se ut att fungera men ändå:

- generera dålig data
- bli för dyrt
- använda fel modell
- skicka för mycket input
- missa valideringsfel

### Pipeline-regel

Enrichment-pipelinen ska struktureras som:

```txt
extract -> normalize -> enrich -> validate -> store
```

Tolkning:

- `extract`: hämta rätt produkt-/fältdata
- `normalize`: mappa till canonical schema och rena input
- `enrich`: kör AI med minimal task payload
- `validate`: kontrollera schema, enums, affärsregler och confidence
- `store`: spara bara validerat resultat med metadata

Viktiga filer:

- `backend/app/core/ai.py`: Claude text/vision client.
- `backend/app/core/embeddings.py`: OpenAI embedding client.
- `backend/app/prompts/prompt_manager.py`: valjer prompt och version.
- `backend/app/prompts/versions/v1_feedfixer.py`: tidig feed/prompt.
- `backend/app/prompts/versions/v2_enrichment.py`: produkt-enrichment.
- `backend/app/prompts/versions/v3_variant_seo.py`: variant/SEO enrichment.
- `backend/app/prompts/versions/v4_image_analysis.py`: bildanalys.

Monster:

```txt
Service -> prompt_manager -> versionerad prompt -> core/ai -> parsed JSON
```

Risk:

- AI-output ar opalitligt; kod maste alltid parsea defensivt.
- Promptversioner lagras i `AnalysisResult`, vilket ar bra for spårbarhet.
- Promptinstruktioner är inte säkerhetsgränser. De måste backas upp av kodvalidering.

---

## 9. Kvalitetsbedomning

Styrkor:

- Tydlig avsedd lagerarkitektur.
- Bra separering mellan ingestion, enrichment, image analysis och jobs.
- Canonical schema ar en bra stabiliserande mittpunkt.
- Promptversioner och token usage sparas.
- Tester finns for ingestion, health, analyze och image service.

Svagheter / drift:

- API-routes och services blandar ibland in direkta DB-fragor.
- Ingen synlig migrationsstruktur trots docs.
- Frontend och backend kontrakt synkas manuellt.
- Debug `print()` finns i produktkod.
- Semantic search SQL bor hardas.

---

## 10. Problem & Risker

Prioriterade risker:

1. **Databas-migrationsrisk**: `create_tables()` pa startup racker inte for schema-andringar i produktion.
2. **Arkitekturdrift**: routes gor DB queries direkt trots dokumenterade regler.
3. **RAG-koppling**: enrichment kan bli beroende av embeddings som kanske inte finns.
4. **Kontraktsdrift**: Pydantic schemas och TypeScript interfaces kan glida isar.
5. **SQL-sakerhet/robusthet**: f-string SQL i semantic search.
6. **Operabilitet**: `print()` istallet for logging och svag Redis readiness.
7. **Promptstyrning utan kodgrindar**: vissa AI-flöden litar på promptformat och lös dict-shape istället för hårda domänscheman.

---

## 11. Forbattringsplan

Kort sikt:

- Dokumentera faktisk arkitektur, inte bara onskad arkitektur.
- Ratta API-helper som pekar pa fel endpoint.
- Ersatt uppenbara `print()` med logger.
- Parameterisera `semantic_search()`.
- Lagg till enklare smoke-test for `/catalog`, `/products/{sku_id}`, `/jobs/{job_id}`.
- Inför kodvalidering för AI-output där prompten idag ensam beskriver formatet.

Medellang sikt:

- Flytta direkta route queries till repositories/services.
- Infor Alembic migrations.
- Generera eller validera frontend types mot backend OpenAPI.
- Gor Redis/worker health tydligare.
- Skapa typed DTO/Pydantic schemas för AI-resultat innan de sparas eller visas.

Lang sikt:

- Separera AI worker queue och data worker queue.
- Lagg till tenant-modell om multi-tenant verkligen ska byggas.
- Infor observability: structured logs, Sentry, request IDs.

---

## 12. Nasta steg

Rekommenderad genomgangsordning, en fil i taget:

1. `backend/app/main.py` - entrypoint/bootstrap.
2. `backend/app/core/config.py` - settings och env.
3. `backend/app/core/database.py` - DB/session/table creation.
4. `backend/app/models/product.py` - basmodell och produktkarnan.
5. `backend/app/schemas/canonical.py` - canonical schema.
6. `backend/app/api/ingest.py` - HTTP ingestion.
7. `backend/app/services/ingestion_service.py` - ingestion pipeline.
8. `backend/app/ingestion/mapping/field_mapper.py` - feed mapping.
9. `backend/app/api/enrich.py` - enrichment endpoints.
10. `backend/app/services/enrichment_service.py` - enrichment pipeline.
11. `backend/app/repositories/product_repository.py` - product queries/RAG.
12. `frontend/app/layout.tsx` - app shell.
13. `frontend/lib/api.ts` - frontend/backend contract.
14. `frontend/app/dashboard/page.tsx` - dashboard flow.
15. `frontend/app/catalog/page.tsx` - catalog flow.
16. `frontend/app/products/[sku_id]/page.tsx` - product detail flow.

---

## Djupdykning 000: Startfilen `backend/app/main.py`

Det här är den naturliga startpunkten för backend.

När Docker Compose startar API-containern körs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Det betyder:

- Python laddar modulen `app.main`
- Uvicorn letar efter variabeln `app`
- `app` måste vara en FastAPI-applikation

Kort sagt:

`backend/app/main.py` är **entrypoint/bootstrap-filen** för API:t.

---

### 1. Filens syfte

```python
"""FeedPilot API entry point."""
```

Den här filens ansvar är att:

- skapa FastAPI-appen
- läsa global konfiguration
- konfigurera CORS
- köra startup-logik
- registrera alla API-routers
- exponera en enkel root endpoint

Den ska inte innehålla business logic.

Bra mental modell:

```txt
main.py
  = kopplar ihop applikationen
  != implementerar feature-logik
```

---

### 2. Importerna visar vilka huvuddelar som kopplas ihop

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
```

Det här är framework-lagret.

`FastAPI` skapar själva appen. `CORSMiddleware` styr vilka frontend-domäner som får prata med backend från browsern.

```python
from app.core.config import get_settings
from app.core.database import create_tables
```

Det här kopplar in core-lagret:

- `config.py` äger settings/env
- `database.py` äger DB-init och sessioner

```python
from app.api.health import router as health_router
from app.api.analyze import router as analyze_router
from app.api.ingest import router as ingest_router
...
```

Det här kopplar in API-lagret.

Varje fil i `app/api/` exporterar en `router`. `main.py` samlar ihop dem till en app.

Arkitektursignal:

```txt
api/*.py äger endpoints
main.py äger registreringen av endpoints
```

Det är ett vanligt och bra FastAPI-mönster.

---

### 3. Settings laddas en gång

```python
settings = get_settings()
```

Det här anropar:

```txt
backend/app/core/config.py
```

Där används `@lru_cache`, så settings laddas en gång per process.

Vad `main.py` använder settings till:

```python
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)
```

Det betyder:

- API-namn kommer från config
- version kommer från config
- debug-läge kommer från config

Senior take:

Det är bra att app metadata inte är hårdkodad direkt i `main.py`.

Men:

`settings = get_settings()` körs vid import-time. Det är vanligt i små appar, men kan göra tester och miljöbyten lite mer känsliga om env ändras efter import.

---

### 4. FastAPI-appen skapas

```python
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)
```

Det här är objektet Uvicorn letar efter:

```txt
app.main:app
         ^^^
```

Den här variabeln är alltså själva ASGI-applikationen.

Allt som händer efter detta modifierar appen:

- middleware läggs till
- startup hooks registreras
- routers inkluderas
- root endpoint skapas

---

### 5. CORS konfigureras

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

CORS behövs eftersom frontend och backend kör på olika origins:

```txt
Frontend: http://localhost:3000
Backend:  http://localhost:8010
```

Browsern blockerar annars requests från frontend till backend.

Vad detta tillåter:

- frontend på localhost:3000 får anropa backend
- cookies/auth headers får skickas
- alla HTTP-metoder tillåts
- alla headers tillåts

Senior take:

Det är rimligt för lokal utveckling.

För produktion bör `allow_origins` styras av config/env, inte vara hårdkodat till localhost.

---

### 6. Startup-hook skapar databastabeller

```python
@app.on_event("startup")
async def startup() -> None:
    """Create database tables on startup."""
    create_tables()
```

När FastAPI startar körs `startup()`.

Den anropar:

```txt
backend/app/core/database.py::create_tables()
```

Det gör två viktiga saker:

1. aktiverar pgvector-extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

2. skapar tabeller från SQLAlchemy-modeller:

```python
Base.metadata.create_all(bind=engine)
```

Arkitektursignal:

`main.py` initierar databasen, men detaljerna ligger i `core/database.py`.

Det är bra separation.

Risk:

Det här är ett MVP/dev-mönster.

I produktion är det bättre med migrations, till exempel Alembic, eftersom:

- `create_all()` hanterar inte schemaändringar robust
- man får svagare historik över DB-förändringar
- deploys kan bli oförutsägbara

Extra detalj:

`startup()` är async, men `create_tables()` är synkron. Det går, men blockerar event loop under startup. Det är normalt acceptabelt eftersom det bara sker vid start.

---

### 7. Routers registreras

```python
app.include_router(health_router, prefix="/api/v1")
app.include_router(analyze_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
...
```

Det här är där hela API-ytan byggs.

Varje router har sitt eget lokala prefix.

Exempel:

```python
# app/api/analyze.py
router = APIRouter(prefix="/analyze")
```

När `main.py` inkluderar den med:

```python
app.include_router(analyze_router, prefix="/api/v1")
```

blir slutlig path:

```txt
/api/v1/analyze
```

Samma mönster gäller övriga routes:

| Router | Lokalt prefix | Slutlig baspath |
|---|---:|---:|
| `health_router` | `/health` | `/api/v1/health` |
| `analyze_router` | `/analyze` | `/api/v1/analyze` |
| `ingest_router` | `/ingest` | `/api/v1/ingest` |
| `enrich_router` | `/enrich` | `/api/v1/enrich` |
| `products_router` | `/products` | `/api/v1/products` |
| `catalog_router` | `/catalog` | `/api/v1/catalog` |
| `jobs_router` | `/jobs` | `/api/v1/jobs` |
| `images_router` | `/images` | `/api/v1/images` |
| `variants_router` | `/variants` | `/api/v1/variants` |

Senior take:

Det här är ett rent och läsbart FastAPI-mönster.

En möjlig förbättring är att samla router-registrering i en lista för att minska upprepning, men nuvarande kod är tydlig och helt okej.

---

### 8. Root endpoint

```python
@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple liveness message."""
    return {"message": "FeedPilot API is running"}
```

Detta är inte samma sak som `/api/v1/health`.

Root endpointen finns på:

```txt
GET /
```

Den är mest en enkel sanity check.

Det riktiga health endpointet ligger i:

```txt
backend/app/api/health.py
```

och exponeras som:

```txt
GET /api/v1/health
```

Senior take:

Root endpoint är praktisk i dev.

För riktig drift bör health endpointen vara den som används av load balancers, Docker healthchecks eller monitoring.

---

### 9. Pattern / principer som används

Identifierade patterns:

- **Application Bootstrap**
  - `main.py` skapar och kopplar ihop appen.

- **Router Composition**
  - varje feature har egen routerfil.

- **Core Configuration**
  - settings och DB ligger i `core/`, inte inline i startup-filen.

- **API Version Prefix**
  - alla feature-routes får `/api/v1`.

- **Middleware Registration**
  - cross-cutting HTTP-beteende, som CORS, läggs på appnivå.

---

### 10. Första ärliga bedömningen

Det här är bra:

- startfilen är kort
- route-filer är separerade
- settings hämtas centralt
- DB-init är delegerad till `core/database.py`
- API-versionering finns via `/api/v1`
- CORS är explicit

Men:

- `create_tables()` på startup är inte en långsiktig migrationsstrategi
- CORS-origins är hårdkodade till lokal frontend
- `@app.on_event("startup")` är legacy-stil i nyare FastAPI
- alla routers importeras direkt, vilket gör startup beroende av att alla feature-moduler importerar korrekt

---

### 11. Hur vi går vidare från `main.py`

`main.py` pekar naturligt på tre nästa filer:

1. `backend/app/core/config.py`
   - för att förstå settings och env.

2. `backend/app/core/database.py`
   - för att förstå DB, sessioner och table creation.

3. `backend/app/api/health.py`
   - för att börja med den enklaste registrerade routern.

Rekommenderad nästa fil:

```txt
backend/app/core/config.py
```

Varför?

För att `main.py` allra först gör:

```python
settings = get_settings()
```

Det betyder att konfiguration är nästa beroende i startkedjan.

---

## Djupdykning 001: Analyze-flödet

Det här är första pedagogiska fil-för-fil-genomgången. Målet är inte bara att säga vad filerna gör, utan att förstå hur flödet rör sig genom lagren.

Analyze-flödet är ett bra första exempel eftersom det är litet:

```txt
backend/app/main.py
  -> backend/app/api/analyze.py
  -> backend/app/schemas/analyze.py
  -> backend/app/services/analyze_service.py
  -> backend/app/prompts/prompt_manager.py
  -> backend/app/prompts/versions/v1_feedfixer.py
  -> backend/app/core/ai.py
```

Det visar projektets grundmönster:

```txt
entrypoint -> route -> schema -> service -> prompt manager -> AI core
```

### 1. `backend/app/main.py`

#### Filens syfte

Det här är backendens startfil. När Uvicorn kör:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

så är det den här filen som laddas.

Dess ansvar är att:

- skapa FastAPI-applikationen
- läsa settings
- konfigurera CORS
- skapa databastabeller vid startup
- koppla in alla API-routers
- exponera en enkel root endpoint

Kort sagt:

Detta är **bootstrap-lagret** för backend.

#### Viktig kod

```python
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)
```

Det betyder att `main.py` inte själv äger konfigurationen. Den hämtar den från:

```python
from app.core.config import get_settings
```

#### Arkitektursignal

Det är bra att settings inte är hårdkodade i `main.py`. Startfilen ska vara tunn och främst koppla ihop systemet.

#### Router-kopplingen

Analyze-flödet kopplas in här:

```python
from app.api.analyze import router as analyze_router

app.include_router(analyze_router, prefix="/api/v1")
```

Det betyder att allt som definieras i `api/analyze.py` får prefixet:

```txt
/api/v1
```

Eftersom `api/analyze.py` själv har:

```python
prefix="/analyze"
```

blir den faktiska endpointen:

```txt
POST /api/v1/analyze
```

#### Senior take

Det här är ett bra bootstrap-mönster:

- `main.py` skapar appen
- routes ligger i egna filer
- settings ligger i `core/config.py`
- databas-init ligger i `core/database.py`

Men:

- `create_tables()` på startup är mer MVP/dev än produktionsmönster
- migrations via Alembic vore bättre när schemat börjar ändras ofta

---

### 2. `backend/app/api/analyze.py`

#### Filens syfte

Det här är route-lagret för analyze-funktionen.

Dess ansvar är att:

- definiera HTTP endpointen
- ta emot request body
- låta Pydantic validera input
- hämta service via dependency injection
- anropa service-lagret
- returnera response model
- översätta fel till HTTPException

Kort sagt:

Detta är **HTTP-lagret**, inte business logic-lagret.

#### Viktig kod

```python
router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
)
```

Den här routern kopplas sedan in i `main.py` med `/api/v1`.

Resultatet blir:

```txt
POST /api/v1/analyze
```

#### Endpointen

```python
@router.post(
    "",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analysera en fråga om produktdata",
    description="Skickar en fråga till Claude och returnerar ett strukturerat svar.",
)
async def analyze(
    request: AnalyzeRequest,
    service: AnalyzeService = Depends(get_analyze_service),
) -> AnalyzeResponse:
```

Det här säger flera viktiga saker:

- request body ska matcha `AnalyzeRequest`
- response ska matcha `AnalyzeResponse`
- FastAPI injectar `AnalyzeService`
- endpointen är async

#### Koppling till schema-lagret

```python
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
```

Route-filen definierar inte själv request/response-shape. Det är bra.

Det betyder:

- validering ligger i schema
- HTTP-flödet ligger i route
- use-case ligger i service

#### Koppling till service-lagret

```python
from app.services.analyze_service import AnalyzeService, get_analyze_service
```

Sedan:

```python
result = await service.analyze_question(request.question)
return AnalyzeResponse(**result)
```

Route-filen gör alltså inte AI-anropet själv. Den delegerar.

#### Arkitektursignal

Det här är ett bra tecken:

- route är tunn
- AI-anropet ligger inte i endpointen
- prompten ligger inte i endpointen
- response valideras med Pydantic

#### Svaghet / risk

Felhanteringen är bred:

```python
except Exception as exc:
```

Det betyder att alla fel blir:

```txt
500 AI-anropet misslyckades
```

Det är enkelt, men inte särskilt semantiskt.

Bättre på sikt:

- `PromptNotFoundError` -> 500 med tydlig intern orsak
- AI provider timeout -> 503
- invalid AI response -> 502 eller 500 beroende på strategi
- inputfel ska helst fångas av Pydantic innan service körs

#### Senior take

`api/analyze.py` är en ganska ren route-fil. Den följer projektets önskade arkitektur bättre än flera andra routes i projektet.

Den största kontrollpunkten är inte route-filen, utan att den `await`:ar en service-metod som i sin tur anropar en synkron AI-klient.

---

### 3. `backend/app/schemas/analyze.py`

#### Filens syfte

Det här är schema-lagret för analyze endpointen.

Dess ansvar är att:

- definiera request-kontraktet
- definiera response-kontraktet
- ge FastAPI inputvalidering
- ge OpenAPI-dokumentation
- separera data-shape från route-logik

Kort sagt:

Detta är **API-kontraktslagret** för analyze-funktionen.

#### Request schema

```python
class AnalyzeRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="The question or product data to analyze.",
        examples=["Vilka produkter har högst returgrad?"],
    )
```

Det betyder att klienten måste skicka:

```json
{
  "question": "..."
}
```

Valideringsregler:

- `question` krävs
- minst 10 tecken
- max 2000 tecken

#### Response schema

```python
class AnalyzeResponse(BaseModel):
    answer: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
```

Det betyder att service-resultatet måste innehålla exakt den shape som `AnalyzeResponse` förväntar sig.

#### Arkitektursignal

Det är bra att request/response är tydliga Pydantic-modeller.

Det ger:

- automatisk OpenAPI-dokumentation
- runtime-validering
- tydligare gräns mellan backend och frontend

#### Svaghet / risk

Prompten `feedfixer_v1` instruerar Claude att returnera rå JSON med fält som:

```json
{
  "sku_id": "...",
  "overall_score": 0,
  "issues": []
}
```

Men `AnalyzeResponse` returnerar:

```json
{
  "answer": "...",
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0
}
```

Det betyder att analyze endpointen just nu inte parsear Claudes JSON till ett domänschema. Den returnerar hela Claude-svaret som string i `answer`.

#### Senior take

Det här är viktigt:

Schema-lagret är tekniskt rent, men domänkontraktet är fortfarande ganska generiskt.

Endpointen säger egentligen:

> "Här är Claudes text plus token metadata"

inte:

> "Här är en strukturerad produktdataanalys"

Det är helt okej i MVP-fas, men det bör dokumenteras ärligt.

---

### 4. `backend/app/services/analyze_service.py`

#### Filens syfte

Den här filen är service-lagret för analyze-funktionen.

Dess ansvar är att:

- kapsla use-caset "analysera fråga"
- hämta rätt prompt
- anropa AI-lagret
- returnera resultat till routern
- exponera aktiv promptversion

Kort sagt:

Detta är tänkt att vara **business logic-lagret mellan route och AI/core**.

#### Service importerar två centrala beroenden

```python
from app.core.ai import ask_claude
from app.prompts.prompt_manager import get_prompt, get_version
```

Det betyder att servicen är byggd ovanpå två andra lager:

- `app.core.ai`: själva AI-klienten/integrationen
- `prompt_manager`: promptval och versionering

#### Arkitektursignal

Det här är bra.

Det visar att:

- prompten inte är hårdkodad direkt i route
- AI-anropet inte ligger direkt i route
- prompthantering är separerad från service
- service-lagret är use-case entrypoint

#### Klassen

```python
class AnalyzeService:
    """Handles all business logic for product data analysis."""
```

Docstringen säger att den hanterar all business logic.

Det är riktningen, men just nu är implementationen tunn.

#### Kärnmetoden

```python
async def analyze_question(self, question: str) -> dict[str, str | int]:
    return ask_claude(
        prompt=question,
        system=get_prompt("feedfixer_v1"),
    )
```

Den gör fyra saker:

1. tar emot en fråga
2. hämtar systemprompten `feedfixer_v1`
3. skickar frågan till Claude via `ask_claude`
4. returnerar resultatet

Det här är kärnflödet just nu.

#### Är detta verkligen business logic?

Delvis.

Mer exakt är detta just nu en:

- thin application service
- orchestration wrapper
- use-case entry point

Den innehåller ännu inte mycket domänlogik som:

- preprocessar input
- väljer strategi
- validerar affärsregler
- transformerar AI-resultat
- parsear JSON
- mappar providerfel till domänfel
- loggar use-case metadata

#### Promptversion

```python
def get_active_prompt_version(self) -> str:
    return get_version("feedfixer_v1")
```

Det är en bra idé eftersom promptversioner bör vara spårbara.

Men i huvudflödet används den inte.

Frågor:

- ska promptversion skickas med i response?
- ska den loggas?
- ska den sparas i databas?
- ska den synas i debugging?

#### Dependency injection factory

```python
def get_analyze_service() -> AnalyzeService:
    return AnalyzeService()
```

Den används av FastAPI:

```python
service: AnalyzeService = Depends(get_analyze_service)
```

Det är ett vanligt FastAPI-mönster.

#### Svaghet 1: async metod utan await

Metoden är async:

```python
async def analyze_question(...)
```

men inuti körs:

```python
return ask_claude(...)
```

`ask_claude()` i `core/ai.py` är synkron. Den använder Anthropic-klientens synkrona `client.messages.create(...)` och `time.sleep(...)`.

Det betyder:

- route ser async ut
- service ser async ut
- men AI-anropet blockerar event loop under tiden

#### Senior take

Det här är en riktig kontrollpunkt.

För låg trafik i MVP är det ofta okej.

För produktion finns tre möjliga riktningar:

1. gör hela flödet synkront och var ärlig i signaturerna
2. byt till async Anthropic-klient och `await`
3. lägg AI-anrop bakom worker/job om det kan ta tid

#### Svaghet 2: lös dict som kontrakt

```python
-> dict[str, str | int]
```

Route gör sedan:

```python
return AnalyzeResponse(**result)
```

Det fungerar, men service och route är kopplade via en informell shape.

Risk:

- shape mismatch upptäcks sent
- sämre editorstöd
- sämre intern tydlighet
- svårare att refaktorera

Bättre riktning:

- returnera `AnalyzeResponse`
- eller skapa intern DTO
- eller använd en typed dict

#### Svaghet 3: promptnamn dupliceras

```python
get_prompt("feedfixer_v1")
get_version("feedfixer_v1")
```

Det är liten men tydlig smell.

Bättre:

```python
PROMPT_NAME = "feedfixer_v1"
```

#### Svaghet 4: ingen egen felhantering

Servicen låter alla fel bubbla upp.

Det gör att route bara kan fånga bred `Exception`.

Bättre på sikt:

- `AnalysisFailedError`
- `PromptNotFoundError`
- `AIProviderUnavailableError`
- tydligare timeout/provider mapping

#### Identifierade patterns

- Service Layer Pattern
- Prompt Manager Pattern
- AI Adapter Abstraction
- FastAPI Dependency Injection Factory

#### Samlad senior-bedömning

`AnalyzeService` är en bra riktning, men fortfarande en tunn service.

Det är inte dåligt.

Det betyder:

- strukturen är mogen nog för att växa
- men domänlogiken är ännu inte särskilt mogen
- riktig komplexitet ligger längre ner i `core/ai.py` och `prompt_manager.py`

---

### 5. `backend/app/prompts/prompt_manager.py`

#### Filens syfte

Den här filen är prompt-registret.

Dess ansvar är att:

- samla alla promptversioner på ett ställe
- låta services hämta prompt via namn
- låta services hämta version via namn
- göra prompts spårbara och bytbara

Kort sagt:

Detta är **prompt routing-lagret**.

#### Prompt registry

```python
PROMPT_REGISTRY: dict[str, object] = {
    "feedfixer_v1": v1_feedfixer,
    "enrichment_v2": v2_enrichment,
    "variant_seo_v3": v3_variant_seo,
    "image_analysis_v4": v4_image_analysis,
}
```

AnalyzeService använder:

```python
get_prompt("feedfixer_v1")
get_version("feedfixer_v1")
```

Det betyder att service-lagret inte behöver veta vilken fil prompten ligger i.

#### Arkitektursignal

Det här är ett bra mönster i AI-appar.

Prompts behandlas som versionerade artifacts, inte som inline-text inne i endpoints.

#### Risker / förbättringar

- `dict[str, object]` är svagt typat. Alla promptmoduler förväntas ha `SYSTEM_PROMPT` och `VERSION`, men det är inte typkontrollerat.
- `KeyError` är tekniskt korrekt men kanske inte domänspecifikt nog.
- Registry är hårdkodat. Det är okej i MVP, men kan bli configstyrt senare.

---

### 6. `backend/app/prompts/versions/v1_feedfixer.py`

#### Filens syfte

Det här är första systemprompten för FeedPilot/FeedFixer-analys.

Dess ansvar är att:

- definiera rollen för AI:n
- beskriva analysinstruktioner
- kräva JSON-output
- ge output-format
- ge exempel
- exponera versionsnummer

#### Viktig struktur

```python
VERSION = "1.0.0"

SYSTEM_PROMPT = """
...
"""
```

Prompt manager förväntar sig just dessa två variabler.

#### Vad prompten vill få Claude att göra

Prompten instruerar Claude att analysera:

- produkttitel
- beskrivning
- attribut
- kategori
- returrisk

Den säger också:

```txt
Svara ALLTID med rå JSON.
```

Viktig princip:

Det räcker inte att prompten säger detta.

Om JSON-formatet spelar roll måste kod:

- extrahera JSON
- parsea JSON
- validera fält
- neka okända eller felaktiga värden
- bestämma fallback om svaret är ogiltigt

#### Viktig mismatch

Prompten kräver JSON med domänfält.

Men analyze endpointen returnerar inte domänfälten som strukturerad response.

I stället hamnar hela Claude-outputen i:

```python
answer: str
```

Det betyder att analyze-flödet är mer "AI text wrapper" än riktig strukturerad produktanalys just nu.

#### Senior take

Prompten är mer ambitiös än endpointens kontrakt.

Det är inte ovanligt i tidiga AI-projekt:

- prompten designas för strukturerad output
- men appen returnerar fortfarande raw text

Nästa mognadssteg vore att parsea JSON och returnera ett Pydantic-schema som matchar promptens output.

---

### 7. `backend/app/core/ai.py`

#### Filens syfte

Det här är AI-core-lagret.

Dess ansvar är att:

- skapa Anthropic-klienten
- skicka textpromptar till Claude
- skicka bild + text till Claude Vision
- returnera svar och token usage
- hantera retry för HTTP 529
- upptäcka trunkering via `stop_reason == "max_tokens"` i textflödet

Kort sagt:

Detta är **provider adapter-lagret** mellan FeedPilot och Anthropic.

#### AnalyzeService använder denna funktion

```python
def ask_claude(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 1000,
) -> dict[str, str | int]:
```

Det betyder:

- `prompt` blir user message
- `system` blir system prompt
- `max_tokens` styr maxstorlek på svaret

#### Viktig detalj

Funktionen är synkron:

```python
def ask_claude(...)
```

Den använder:

```python
response = client.messages.create(**kwargs)
```

och:

```python
time.sleep(delay)
```

Det verifierar risken i `AnalyzeService`: async route/service blockerar ändå under AI-anropet.

#### Return shape

```python
return {
    "answer": text,
    "input_tokens": response.usage.input_tokens,
    "output_tokens": response.usage.output_tokens,
    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
}
```

Det matchar `AnalyzeResponse`.

#### Arkitektursignal

Det är bra att Anthropic-anropet är centraliserat.

Det gör det möjligt att senare:

- byta modell på ett ställe
- lägga till logging
- lägga till tracing
- lägga till async-klient
- normalisera providerfel

#### Svagheter / risker

- modellnamnet är hårdkodat
- retries gäller bara 529
- `time.sleep()` blockerar
- vision-funktionen saknar samma `max_tokens` stop check som textfunktionen
- returnerar lös dict snarare än typed response

---

### Slutsats för Analyze-flödet

Analyze-flödet är en bra första studie eftersom det visar projektets tänkta arkitektur i liten skala.

Det som är bra:

- `main.py` är bootstrap
- route är tunn
- request/response schemas finns
- service-lager finns
- prompt manager finns
- AI-provider är kapslad i `core/ai.py`

Det som är svagare:

- service är tunn
- async/sync är inkonsekvent
- prompten kräver JSON men endpointen returnerar raw answer string
- promptnamn dupliceras
- felhantering är för bred
- inga domänspecifika exceptions

Praktisk mental modell:

```txt
main.py
  registrerar routern

api/analyze.py
  tar HTTP-request och returnerar HTTP-response

schemas/analyze.py
  validerar request/response-shape

services/analyze_service.py
  orkestrerar use-caset

prompt_manager.py
  hämtar rätt systemprompt

v1_feedfixer.py
  definierar AI-beteendet

core/ai.py
  pratar med Anthropic
```

Nästa fil att gå igenom om vi följer flödet strikt är:

```txt
backend/app/core/ai.py
```

Den avgör om hela AI-lagret är robust nog, och den förklarar varför `AnalyzeService` just nu blockerar trots async-signatur.

---

## Filkatalog: skapade filer och ansvar

### Root

| Fil | Ansvar | Koppling |
|---|---|---|
| `README.md` | Projektintroduktion, quick start och API/feature-overview. | Mänsklig onboarding. |
| `CLAUDE.md` | Instruktioner for Claude Code och arkitekturregler. | Styr AI-agentens arbetssatt. |
| `AGENTS.md` | Agent-/arbetsregler for kodagent. | Kompletterar Claude/Codex-kontext. |
| `docker-compose.yml` | Lokal runtime for API, DB, Redis och worker. | Startar backend/Dockerfile och ARQ. |
| `feedpilot-ai.code-workspace` | VS Code workspace. | Lokal IDE-konfiguration. |

### Backend konfiguration

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/Dockerfile` | Python image for API/worker. | Anvands av Compose. |
| `backend/requirements.txt` | Runtime dependencies. | Installeras av Dockerfile. |
| `backend/requirements-dev.txt` | Dev/test dependencies. | Installeras av Dockerfile. |
| `backend/pytest.ini` | Pytest-konfiguration. | Backend test runner. |

### Backend app root/core

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/__init__.py` | Markerar Python package. | Importsystem. |
| `backend/app/main.py` | FastAPI app bootstrap. | Router, CORS, startup DB. |
| `backend/app/core/__init__.py` | Markerar core package. | Importsystem. |
| `backend/app/core/config.py` | Env/settings. | Anvands av DB, AI, worker. |
| `backend/app/core/database.py` | Engine/session/table creation. | API + worker DB access. |
| `backend/app/core/ai.py` | Claude text/vision wrapper. | Enrichment/image services. |
| `backend/app/core/embeddings.py` | OpenAI embeddings. | RAG/semantic search. |
| `backend/app/core/image.py` | Image preprocessing. | Claude Vision. |

### Backend API routes

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/api/__init__.py` | Markerar api package. | Importsystem. |
| `backend/app/api/health.py` | Health endpoint. | Drift/smoke test. |
| `backend/app/api/analyze.py` | Tidig/analyserande endpoint. | Analyze service/schema. |
| `backend/app/api/ingest.py` | CSV/XLSX upload endpoints. | IngestionService. |
| `backend/app/api/enrich.py` | Single/bulk enrichment endpoints. | EnrichmentService, ARQ, Job. |
| `backend/app/api/products.py` | Product detail, apply fields, image URL. | Product/AnalysisResult. |
| `backend/app/api/catalog.py` | Paginated catalog. | Product + latest AnalysisResult. |
| `backend/app/api/stats.py` | Dashboard stats. | StatsService. |
| `backend/app/api/jobs.py` | Job list/status endpoints. | Job model. |
| `backend/app/api/embeddings.py` | Embedding job endpoint. | ARQ embed task. |
| `backend/app/api/search.py` | Semantic/RAG search endpoints. | ProductRepository/RAG. |
| `backend/app/api/images.py` | Product image analysis endpoints. | ImageAnalysisService. |
| `backend/app/api/variants.py` | Variant import/enrich/read endpoints. | Variant repository/service. |

### Backend services

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/services/__init__.py` | Markerar services package. | Importsystem. |
| `backend/app/services/analyze_service.py` | Analyslogik for tidig endpoint. | Analyze API/schema. |
| `backend/app/services/ingestion_service.py` | Feed ingestion pipeline. | Connectors, mapper, validators, Product. |
| `backend/app/services/enrichment_service.py` | Product enrichment pipeline. | Claude, prompts, repository, AnalysisResult. |
| `backend/app/services/embedding_service.py` | Skapar product embeddings. | ProductEmbedding, OpenAI. |
| `backend/app/services/rag_service.py` | RAG-relaterad orchestration. | Search/embedding context. |
| `backend/app/services/image_analysis_service.py` | Vision analysis pipeline. | Claude Vision prompt/schema. |
| `backend/app/services/variant_enrichment_service.py` | Variant SEO enrichment. | Variant repository, Claude prompt. |
| `backend/app/services/stats_service.py` | Dashboard stats business logic. | StatsRepository. |

### Backend repositories

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/repositories/__init__.py` | Markerar repositories package. | Importsystem. |
| `backend/app/repositories/product_repository.py` | Product queries och semantic search. | Product, AnalysisResult, embeddings. |
| `backend/app/repositories/variant_repository.py` | Variant queries/import helpers. | ProductVariant. |
| `backend/app/repositories/stats_repository.py` | Aggregatfragor for dashboard. | Product, AnalysisResult. |

### Backend models

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/models/__init__.py` | Markerar models package. | Importsystem. |
| `backend/app/models/product.py` | `Base` + Product ORM. | DB metadata-root. |
| `backend/app/models/analysis_result.py` | AI-resultat per produkt. | Enrichment/Product detail. |
| `backend/app/models/embedding.py` | Product embeddings med pgvector. | RAG/search. |
| `backend/app/models/variant.py` | Product variants. | Variant API/service. |
| `backend/app/models/job.py` | Async job state. | ARQ/API polling. |
| `backend/app/models/customer_pim_config.py` | PIM-konfiguration. | Framtida integration. |

### Backend schemas

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/schemas/__init__.py` | Markerar schemas package. | Importsystem. |
| `backend/app/schemas/canonical.py` | CanonicalProduct mellanlager. | Ingestion/enrichment. |
| `backend/app/schemas/product.py` | Product/ingest API schemas. | Ingest API. |
| `backend/app/schemas/product_detail.py` | Product detail/enrich/apply schemas. | Products API/frontend. |
| `backend/app/schemas/catalog.py` | Catalog response schemas. | Catalog API/frontend. |
| `backend/app/schemas/enrich.py` | Enrichment request/response schemas. | Enrich API. |
| `backend/app/schemas/job.py` | Job status/enqueue schemas. | Jobs/enrich/embedding APIs. |
| `backend/app/schemas/stats.py` | Stats response schemas. | Stats API/frontend. |
| `backend/app/schemas/analyze.py` | Analyze endpoint schemas. | Analyze API. |
| `backend/app/schemas/image_analysis.py` | Vision analysis schemas. | Images API/frontend. |
| `backend/app/schemas/variant.py` | Variant schemas. | Variants API/frontend. |

### Backend ingestion

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/ingestion/__init__.py` | Markerar ingestion package. | Importsystem. |
| `backend/app/ingestion/connectors/__init__.py` | Markerar connectors package. | Importsystem. |
| `backend/app/ingestion/connectors/csv_connector.py` | Laser CSV bytes till headers/rows. | IngestionService. |
| `backend/app/ingestion/connectors/xlsx_connector.py` | Laser Excel till headers/rows. | IngestionService. |
| `backend/app/ingestion/mapping/__init__.py` | Markerar mapping package. | Importsystem. |
| `backend/app/ingestion/mapping/schema_registry.py` | Kanda feed-scheman och alias. | FieldMapper. |
| `backend/app/ingestion/mapping/field_mapper.py` | Detekterar source och mappar rader. | CanonicalProduct. |
| `backend/app/ingestion/normalizer.py` | Normaliserar canonical values. | IngestionService. |
| `backend/app/ingestion/validators.py` | Kvalitetsvalidering/warnings. | IngestionService. |

### Backend prompts

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/prompts/__init__.py` | Markerar prompts package. | Importsystem. |
| `backend/app/prompts/prompt_manager.py` | Prompt lookup och version. | AI services. |
| `backend/app/prompts/versions/__init__.py` | Markerar prompt versions package. | Importsystem. |
| `backend/app/prompts/versions/v1_feedfixer.py` | Tidig feedfixer prompt. | Analyze/feed logic. |
| `backend/app/prompts/versions/v2_enrichment.py` | Product enrichment prompt. | EnrichmentService. |
| `backend/app/prompts/versions/v3_variant_seo.py` | Variant SEO prompt. | VariantEnrichmentService. |
| `backend/app/prompts/versions/v4_image_analysis.py` | Image analysis prompt. | ImageAnalysisService. |

### Backend workers

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/app/workers/__init__.py` | Markerar workers package. | Importsystem. |
| `backend/app/workers/settings.py` | ARQ worker config. | Compose worker command. |
| `backend/app/workers/tasks.py` | ARQ task implementations. | Job model, services. |

### Backend tests/fixtures

| Fil | Ansvar | Koppling |
|---|---|---|
| `backend/tests/__init__.py` | Markerar tests package. | Pytest. |
| `backend/tests/conftest.py` | Test fixtures/config. | Pytest setup. |
| `backend/tests/test_health.py` | Health endpoint test. | API smoke. |
| `backend/tests/test_analyze.py` | Analyze endpoint/service test. | Analyze flow. |
| `backend/tests/test_ingest.py` | Ingestion tests. | CSV/XLSX pipeline. |
| `backend/tests/test_image_analysis_service.py` | Vision service tests. | ImageAnalysisService. |
| `backend/tests/fixtures/create_test_xlsx.py` | Helper for XLSX fixture. | Test data generation. |
| `backend/tests/fixtures/test_feed.csv` | Test CSV feed. | Ingest tests. |
| `backend/tests/fixtures/test_bad.csv` | Bad feed fixture. | Validation tests. |
| `backend/tests/fixtures/new_products.csv` | Extra product fixture. | Ingest/enrichment tests. |
| `backend/tests/fixtures/test_variants.json` | Variant fixture. | Variant tests/manual import. |

### Frontend config

| Fil | Ansvar | Koppling |
|---|---|---|
| `frontend/package.json` | Scripts/dependencies. | npm. |
| `frontend/package-lock.json` | Locked dependency tree. | npm install. |
| `frontend/README.md` | Frontend docs. | Onboarding. |
| `frontend/next.config.mjs` | Next.js config. | Build/runtime. |
| `frontend/postcss.config.mjs` | PostCSS/Tailwind pipeline. | CSS build. |
| `frontend/tailwind.config.ts` | Design tokens/theme. | Tailwind classes. |
| `frontend/tsconfig.json` | TypeScript config. | TS compiler. |
| `frontend/jest.config.ts` | Jest config. | Frontend tests. |
| `frontend/jest.setup.ts` | Jest setup imports. | Testing library. |

### Frontend app/pages

| Fil | Ansvar | Koppling |
|---|---|---|
| `frontend/app/layout.tsx` | Root layout/sidebar shell. | Alla pages. |
| `frontend/app/globals.css` | Global CSS + Tailwind. | Layout/components. |
| `frontend/app/page.tsx` | Root/home route. | Navigation entry. |
| `frontend/app/dashboard/page.tsx` | Dashboard/stats UI. | Stats/jobs/catalog APIs. |
| `frontend/app/catalog/page.tsx` | Catalog list/filter UI. | Catalog API. |
| `frontend/app/products/[sku_id]/page.tsx` | Product detail/enrichment/image UI. | Product/enrich/images APIs. |
| `frontend/app/processing/page.tsx` | Processing/job board UI. | Jobs/enrich bulk APIs. |
| `frontend/app/image-analysis/page.tsx` | Standalone image analysis route. | Images API. |
| `frontend/app/variants/[sku_id]/page.tsx` | Variant route. | Variants API. |

### Frontend components/lib/tests

| Fil | Ansvar | Koppling |
|---|---|---|
| `frontend/lib/api.ts` | Axios API client. | Alla frontend API calls. |
| `frontend/lib/types.ts` | Frontend API/data types. | Pages/components. |
| `frontend/components/layout/Sidebar.tsx` | Permanent navigation. | Root layout. |
| `frontend/components/layout/TopNav.tsx` | Top navigation/header. | Pages/layout use. |
| `frontend/components/ui/Badge.tsx` | Status badge. | Dashboard/catalog/product. |
| `frontend/components/ui/ScoreGauge.tsx` | Score visualization. | Dashboard/product. |
| `frontend/components/ui/SkeletonCard.tsx` | Loading skeleton. | Pages under loading. |
| `frontend/components/ui/UploadModal.tsx` | Feed upload modal. | Dashboard/catalog flows. |
| `frontend/__tests__/dashboard.test.tsx` | Dashboard UI tests. | Jest/RTL. |
| `frontend/__tests__/processing.test.tsx` | Processing page tests. | Jest/RTL. |

### Docs

| Fil | Ansvar | Koppling |
|---|---|---|
| `docs/REVERSE_ENGINEERING.md` | Denna reverse engineering-karta. | Fortsatt analys. |
| `docs/ARCHITECTURE.md` | Arkitektur och produktionstankar. | Beslutsstod. |
| `docs/FEEDPILOT_CONTEXT.md` | Projektkontext. | Onboarding. |
| `docs/BACKLOG.md` | Backlog. | Planering. |
| `docs/ROADMAP.md` | Roadmap. | Produktplan. |
| `docs/STATUS.md` | Status. | Projektuppfoljning. |
| `docs/RULES.md` | Regler. | Kod/arbetsprocess. |
| `docs/Planning.md` | Planeringsanteckningar. | Arbetsprocess. |
| `docs/REQUIREMENTS.md` | Krav. | Produkt/implementation. |
| `docs/TOOLING.md` | Verktyg. | Utvecklingsmiljo. |
| `docs/adr/001-fastapi-over-django.md` | ADR: FastAPI. | Arkitekturbeslut. |
| `docs/adr/002-pgvector-over-pinecone.md` | ADR: pgvector. | Arkitekturbeslut. |
| `docs/adr/003-arq-over-celery.md` | ADR: ARQ. | Arkitekturbeslut. |
| `docs/adr/004-gcp-as-cloud-provider.md` | ADR: GCP. | Arkitekturbeslut. |
| `docs/adr/005-canonical-schema-pattern.md` | ADR: canonical schema. | Arkitekturbeslut. |

### Extra test fixtures

| Fil | Ansvar | Koppling |
|---|---|---|
| `tests/__init__.py` | Markerar test package. | Pytest. |
| `tests/fixtures/home_feed.csv` | Feed fixture. | Manual/test ingest. |
| `tests/fixtures/sports_feed.csv` | Feed fixture. | Manual/test ingest. |
| `tests/fixtures/luxury_feed.csv` | Feed fixture. | Manual/test ingest. |
| `tests/fixtures/new_products.csv` | Feed fixture. | Manual/test ingest. |
