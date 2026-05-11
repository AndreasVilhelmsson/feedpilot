# FEED-069B — CatalogRepository Extraction

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-069 lade regressionsskydd runt `/api/v1/catalog`. Baslinjen efter FEED-069:

```bash
docker compose exec backend pytest tests/  # 56 passed, 2 kända on_event-varningar
```

FEED-068 klassade `backend/app/api/catalog.py` som **HIGH-risk** (Fynd 1):

- Direkt `db.query(Product, AnalysisResult)` med subquery och multi-join i route-filen.
- `_determine_status()` — statusderivering av business logic-karaktär — lever i API-lagret.
- Ingen `CatalogRepository`.
- Föreslagen åtgärd: skapa `CatalogRepository` med `get_catalog_page()`, flytta
  `_determine_status()` dit, ge API-routen noll direkta DB-anrop.

FEED-069B genomför den refaktorn. Testskyddet från FEED-069 är regressionsnätet.

## Problem

`catalog.py` bryter mot layering-regeln att API-lagret inte ska göra `db.query`:

```python
# catalog.py rad 84–122 — allt detta tillhör repository-lagret:
latest_ar_sq = (
    db.query(
        AnalysisResult.product_id,
        func.max(AnalysisResult.id).label("latest_id"),
    )
    .group_by(AnalysisResult.product_id)
    .subquery()
)
query = (
    db.query(Product, AnalysisResult)
    .outerjoin(latest_ar_sq, ...)
    .outerjoin(AnalysisResult, ...)
)
# + search filter, status filter, count, offset/limit
```

`_determine_status()` är pure logic (tar `AnalysisResult | None`, returnerar sträng) som
lever i fel lager.

Utan refaktorn är `catalog.py` svår att testa isolerat och omöjlig att byta
datalagerkimplementation utan att röra routing-koden.

## Mål

1. Skapa `backend/app/repositories/catalog_repository.py` med klassen `CatalogRepository`.
2. Flytta subquery, join, search-filter, status-filter och pagination till repository.
3. Flytta `_determine_status()` till repository (som private static method).
4. `api/catalog.py` ska innehålla noll direkta `db.query`-anrop efter refaktorn.
5. Endpoint `/api/v1/catalog` returnerar identisk response som före refaktorn.
6. Alla 7 tester i `test_api_catalog.py` passerar utan modifiering.

## Scope

- Ny fil: `backend/app/repositories/catalog_repository.py`.
- Uppdaterad fil: `backend/app/api/catalog.py` — ta bort `db.query`, injicera
  `CatalogRepository` via `Depends()`, returnera `CatalogResponse` från repo-resultat.
- Inga ändringar i:
  - `backend/app/schemas/catalog.py`
  - `backend/app/models/product.py`
  - `backend/app/models/analysis_result.py`
  - `backend/tests/test_api_catalog.py`
  - `backend/tests/conftest.py`
  - Övriga routes eller services.

## Out of Scope

- DB-migrationer.
- Nya endpoints.
- Frontend.
- Auth/multi-tenant.
- Refaktor av den identiska subquery som finns i `product_repository.py::get_unenriched()`
  och `stats_repository.py` — DRY-cleanup är ett separat ärende.
- Unit-tester för `CatalogRepository` isolerat — testskyddet ges av `test_api_catalog.py`
  via HTTP-layer (räcker för detta steg).

## Designbeslut

### Repositories metodsignatur

Repository exponerar en enda publik metod:

```python
def get_page(
    self,
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: str,
    search: str,
) -> tuple[int, list[CatalogProduct]]:
    ...
```

Returnerar `(total, products)`. API-routen ansvarar bara för att linda in resultatet
i `CatalogResponse(total=total, page=page, page_size=page_size, products=products)`.

Keyword-only argument (`*`) efter `db` för att förhindra att anropsordning råkar
matcha fel param vid framtida utbyggnad.

### `_determine_status()` placering

Flytta från `api/catalog.py` till `CatalogRepository` som en private `@staticmethod`:

```python
@staticmethod
def _determine_status(ar: AnalysisResult | None) -> str:
    if ar is None:
        return "needs_review"
    if ar.return_risk == "high":
        return "return_risk"
    return "enriched"
```

**Motivering:** metoden behövs under rad-mappningen inuti `get_page()`. Det är enklare
och mer kohesivt att ha den som private metod i samma klass än som fristående funktion
i `api/`. Den är deterministisk och ren — om Codex önskar en isolerad unit-test kan det
läggas till utan att påverka scope.

**Alternativ som avfärdas:**
- Separat `CatalogService` bara för `_determine_status` — overkill för en trivial funktion.
- Behålla den i `api/catalog.py` — fortfarande fel lager.

### Returtyp: `CatalogProduct` från repository

`get_page()` returnerar `list[CatalogProduct]` (Pydantic schema). Detta skapar en
schema→repository-koppling. Alternativet — returnera `list[tuple[Product, AnalysisResult|None]]`
och låta route-koden bygga `CatalogProduct` — förflyttar bara mappningslogiken tillbaka
till API-lagret.

Avvägning: i detta projekts storlek är `CatalogProduct`-schemat stabilt. Koppling
accepteras. Om schemat ändras påverkas repository-koden, vilket är tydligare än en
dold koppling via ORM-typer.

### DI-factory för CatalogRepository

Följer befintligt mönster (`get_stats_repository`, `get_product_repository`):

```python
def get_catalog_repository() -> CatalogRepository:
    return CatalogRepository()
```

I `api/catalog.py`:

```python
def get_catalog(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status_filter: str = Query(default="all", alias="status"),
    search: str = Query(default=""),
    repo: CatalogRepository = Depends(get_catalog_repository),
    db: Session = Depends(get_db),
) -> CatalogResponse:
    total, products = repo.get_page(
        db, page=page, page_size=page_size,
        status_filter=status_filter, search=search,
    )
    return CatalogResponse(total=total, page=page, page_size=page_size, products=products)
```

`get_db` behålls som `Depends` i routen — sessionens livstid styrs fortfarande av
FastAPI dependency injection, inte av repository.

### Varför `get_db` stannar i routen (inte injiceras i repository)

Alternativet är att låta repository ta `db: Session = Depends(get_db)` internt. Det
bryter dock FastAPI:s dependency-träd och gör `get_db`-overrides i tester svårare.
Befintlig konvention: alla repositories tar `db: Session` som metodparameter, inte via
`Depends()`.

### Behåll `status`-aliaset i route-signaturen

`Query(..., alias="status")` mappar det externa query-parameternamnet `?status=` till
Python-variabeln `status_filter`. Aliaset måste bevaras exakt i `catalog.py` — annars
ändras API-kontraktet.

### Testpåverkan

`test_api_catalog.py` overridar bara `get_db`. Efter refaktorn behövs ingen extra
override eftersom `CatalogRepository` inte har en service-instans som injiceras
oberoende av `db`. Testen kör den riktiga `CatalogRepository.get_page()` mot SQLite —
detta är korrekt, det är precis det testskyddet är till för.

## Berörda filer

Ny fil:
```
backend/app/repositories/catalog_repository.py
```

Uppdaterad fil:
```
backend/app/api/catalog.py
```

Oförändrade filer (läses som referens):
```
backend/app/schemas/catalog.py
backend/app/models/product.py
backend/app/models/analysis_result.py
backend/tests/test_api_catalog.py
backend/app/repositories/stats_repository.py   (mönsterreferens)
backend/app/repositories/product_repository.py (mönsterreferens)
```

## Acceptance Criteria

- `backend/app/repositories/catalog_repository.py` finns med `CatalogRepository`-klassen.
- `CatalogRepository.get_page()` finns med korrekt signatur.
- `_determine_status()` finns som `@staticmethod` i `CatalogRepository`.
- `get_catalog_repository()` DI-factory finns.
- `api/catalog.py` innehåller ingen direkt `db.query`.
- `api/catalog.py` injicerar `CatalogRepository` via `Depends(get_catalog_repository)`.
- `?status=return_risk`, `?status=enriched`, `?status=needs_review` och `?status=all`
  filtrerar korrekt (samma beteende som före refaktorn).
- `?search=` filtrerar på titel och SKU (samma beteende som före refaktorn).
- Pagination (`page`, `page_size`) ger samma resultat som före refaktorn.
- Alla 7 tester i `test_api_catalog.py` passerar utan modifiering av testfilen.
- Fullständig backend baseline passerar:
  ```bash
  docker compose exec backend pytest tests/
  ```
  Förväntat: 56 passed, 2 kända on_event-varningar.
- Ingen produktionskod utanför `catalog.py` och `catalog_repository.py` ändras.

## Testkrav

Inga nya testfiler i FEED-069B. Befintlig `test_api_catalog.py` är regressionsnätet.

Verifiera i Docker:

```bash
# Kör bara catalog-tester:
docker compose exec backend pytest tests/test_api_catalog.py -v

# Kör full baseline:
docker compose exec backend pytest tests/
```

Alla 7 catalog-tester ska passera. Inga regressioner i övriga tester.

## Codex Review Notes

- **Viktigast:** Granska att exakt samma `latest_ar_sq` subquery + outerjoin-logik finns
  i `catalog_repository.py` som i nuvarande `catalog.py`. En tyst avvikelse i join-logiken
  kan ge felaktiga statusvärden utan att ett test märker det (om testerna råkar sakna
  ett specifikt kantfall).
- Granska att `?status=needs_review`-filtret (`AnalysisResult.id.is_(None)`) är bevarat
  i repository — det är lätt att missa när man porterar koden.
- Granska att `status` query-param-aliaset (`alias="status"`) är bevarat i uppdaterad
  `catalog.py`. Om det försvinner returnerar endpointen alltid `status_filter="all"`.
- Kontrollera att `get_db`-override i `test_api_catalog.py` täcker `CatalogRepository`
  utan att någon extra override behöver läggas till. Om testen failar med en
  PostgreSQL-anslutning trots att `get_db` är overridad — undersök om repository
  skapar en ny session internt.
- Notera att identisk `latest_ar_sq`-subquery nu finns på tre ställen:
  `product_repository.py::get_unenriched()`, `stats_repository.py` och den nya
  `catalog_repository.py`. Flagga detta men kräv inte DRY-cleanup i FEED-069B.
- Kontrollera att `_determine_status` som `@staticmethod` är identisk med nuvarande
  funktion i `catalog.py` rad 25–40 — inga hemliga logikändringar.
- Kör `pytest tests/test_api_catalog.py -v` och verifiera att alla 7 tester är gröna.
  Om något test failar är det en regressionsindikator, inte ett testproblem.

## Risker

### 1. Subquery-logiken skiljer sig subtilt

`latest_ar_sq` subquery och `outerjoin`-kedjan är komplex. En stavfel i kolumnnamn
eller join-condition ger tysta fel — produkter kan försvinna eller statusvärden bli fel.
Regressionstesterna täcker inte alla permutationer av data.

**Mitigation:** Kopiera subquery-koden ordagrant från `catalog.py` som första steg.
Verifiera att alla 7 tester passerar innan något ytterligare ändras.

### 2. `status`-aliaset kan försvinna i omskrivningen

`Query(..., alias="status")` är lätt att missa när route-signaturen skrivs om. Om det
försvinner accepterar endpointen inte längre `?status=return_risk` som filterparameter.

**Mitigation:** Codex ska explicit kontrollera alias-parametern i review.

### 3. `test_api_catalog.py` kör mot den riktiga `CatalogRepository`

Det är korrekt och avsiktligt — testerna ska köra verklig kod. Men det innebär att om
`CatalogRepository.get_page()` har en bug som inte täcks av de 7 testerna, hittas den
inte av FEED-069B:s testsvit.

**Mitigation:** Befintliga 7 tester täcker alla statusvärden, statusfilter, sökning och
pagination. Det räcker för att detektera regressioner i den porterade logiken.

### 4. Schema→repository-koppling

`CatalogRepository.get_page()` returnerar `list[CatalogProduct]`. Om `CatalogProduct`
byter namn eller fält påverkas repository utan att felmeddelandet pekar mot repository.

**Mitigation:** Accepterad avvägning i detta skede. Antecknad för framtida ADR om
lagerkopplingar i FeedPilot.

## Definition of Done

- Claude Code har arbetat en fil i taget (katalogrepository → catalog.py).
- `catalog_repository.py` finns och innehåller `CatalogRepository` + DI-factory.
- `catalog.py` innehåller inga direkta `db.query`-anrop.
- Alla 7 tester i `test_api_catalog.py` passerar utan ändring av testfilen.
- 56 backend-tester passerar utan regression.
- Codex har reviewat diffen för båda filerna.
- Ticketen markeras Done när testresultat och Codex-review är klara.

## Codex Review

Godkänd.

Verifierat:

- `backend/app/repositories/catalog_repository.py` finns med `CatalogRepository` och
  `get_catalog_repository()`.
- `CatalogRepository.get_page()` innehåller porterad latest-analysis subquery,
  outerjoin, search-filter, status-filter, count och pagination.
- `_determine_status()` finns som private `@staticmethod` med samma logik som tidigare.
- `backend/app/api/catalog.py` innehåller inga direkta `db.query`-anrop.
- `status_filter` behåller `alias="status"`.
- `get_db` stannar i route-signaturen och testernas override täcker repository-anropet.
- Ingen testfil behövde ändras efter refaktorn.

Testresultat:

```bash
docker compose exec backend pytest tests/test_api_catalog.py -v
```

Resultat: 7 passed, 2 kända FastAPI on_event-varningar.

```bash
docker compose exec backend pytest tests/
```

Resultat: 56 passed, 2 kända FastAPI on_event-varningar.
