# FEED-066 — AI Observability

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-065B integrerade `plan_enrichment()` i `EnrichmentService`. Det innebär att
varje enrichment-anrop nu har en fullständig `EnrichmentPlan` med `model`,
`model_strategy`, `target_fields` och `use_rag` — men inget av detta loggas eller
persisteras.

`ask_claude()` returnerar sedan länge `input_tokens`, `output_tokens` och
`total_tokens`. `EnrichmentService` sparar bara `total_tokens` i `AnalysisResult`.
Resten försvinner.

Resultatet är att det idag är omöjligt att svara på:

- Vilken modell användes för en specifik enrichment?
- Vilken model strategy valdes?
- Vilka target fields skickades?
- Hämtades RAG-context?
- Hur många input- vs output-tokens förbrukades?
- Vad failade och varför?

## Problem

Token usage finns delvis. Plan-metadata beräknas men loggas inte. `print()` används
i `core/ai.py` för retry-loggar. Det finns ingen strukturerad observability per
AI-request.

Krav AI-05 i REQUIREMENTS.md:

```txt
Kostnadsestimat görs före körning och faktisk kostnad loggas efter körning.
```

Det är omöjligt att uppfylla utan att först ha strukturerad post-request-metadata.

## Mål

Introducera en tunn, intern observability-struktur som fångar metadata för varje
AI-request i `EnrichmentService`:

- Vilken modell och strategi valdes.
- Vilka fält enrichades.
- Om RAG användes.
- Input- och output-tokens separat.
- Status: success eller error.
- Feltyp vid error.

Första passet loggar metadata strukturerat. Persistens i DB är en designfråga —
se nedan.

## Scope

Följande ingår i FEED-066:

- Ny fil `backend/app/core/observability.py` med:
  - `AIRequestMetadata`-dataclass (frozen).
  - `log_ai_request(metadata: AIRequestMetadata) -> None` — loggar via Python
    `logging`-modulen som strukturerad dict.
- `EnrichmentService.enrich_product()` ska bygga `AIRequestMetadata` efter
  `ask_claude()`-anropet och anropa `log_ai_request()`.
- Felpath: vid exception i AI-delen av enrichment-flödet (`ask_claude()`,
  JSON-extract eller Pydantic-validering) ska `AIRequestMetadata` byggas med
  `status="error"` och `error_type=type(exc).__name__` och loggas innan
  undantaget propageras vidare.
- Ersätt `print()` med `logging.getLogger(__name__).warning()` i `core/ai.py`.
- Tester i `backend/tests/test_enrichment_service.py` som verifierar att
  `log_ai_request()` anropas vid success.
- Inga riktiga AI-anrop i tester.

## Out of Scope

Följande ingår inte i FEED-066:

- Persistens av `AIRequestMetadata` i databas — se Designbeslut nedan.
- Nya kolumner i `AnalysisResult` — se Designbeslut nedan.
- Faktisk kostnadsberäkning (token-priser är inte definierade i koden).
- Sentry-integration (FEED-028/041).
- Prometheus metrics (FEED-031).
- Job-level summary för bulk enrichment.
- Observability för `ask_claude_vision()` — det görs i ett separat pass.
- Frontend.
- API endpoint-ändringar.
- Databasmigrationer.
- Modellrouting.
- Promptändringar.

## AIRequestMetadata — Designbeslut

`AIRequestMetadata` är en frozen dataclass med följande fält:

| Fält | Typ | Källa |
|---|---|---|
| `sku_id` | `str` | `enrich_product(sku_id, ...)` |
| `prompt_name` | `str` | `PROMPT_NAME` konstanten |
| `prompt_version` | `str` | `get_version(PROMPT_NAME)` |
| `model` | `str` | `plan.model` |
| `model_strategy` | `str` | `plan.model_strategy` |
| `target_fields` | `list[str]` | `plan.target_fields` |
| `use_rag` | `bool` | `plan.use_rag` |
| `input_tokens` | `int` | `ai_response["input_tokens"]` |
| `output_tokens` | `int` | `ai_response["output_tokens"]` |
| `total_tokens` | `int` | `ai_response["total_tokens"]` |
| `status` | `Literal["success", "error"]` | bestäms av pipeline |
| `error_type` | `str \| None` | `type(exc).__name__` vid fel, annars `None` |

Om `ask_claude()` kastar innan ett `ai_response` finns ska tokenfälten sättas till
`0`. Om `ask_claude()` returnerar tokens men JSON-extract eller Pydantic-validering
failar ska de returnerade tokenvärdena loggas tillsammans med `status="error"`.

## log_ai_request() — Designbeslut

```python
def log_ai_request(metadata: AIRequestMetadata) -> None:
    logger.info("ai_request", extra={"metadata": dataclasses.asdict(metadata)})
```

Loggar med `logging.getLogger(__name__)` och `logger.info()`. Ingen extern
dependency. `extra`-dict gör det kompatibelt med strukturerade loggformaten
(JSON-formatters) utan att kräva dem nu.

## Persistens — Designbeslut (Öppen fråga för Codex)

`AnalysisResult` saknar `input_tokens`, `output_tokens`, `model`, `model_strategy`,
`target_fields` och `use_rag`. Dessa är värdefulla att ha persisterade.

Problem: Projektet använder `create_tables()` (SQLAlchemy `create_all`) på startup,
inte Alembic. Att lägga nya kolumner i `AnalysisResult` fungerar för nya tabeller
men kräver `ALTER TABLE` för befintliga. I Docker dev fungerar det med
`DROP + CREATE`, men i produktion är det en destructiv migrering.

**Rekommendation för FEED-066:** Logga endast. Persistens och Alembic-migrering
specificeras i en separat ticket (FEED-069 eller liknande) som hanterar hela
DB-migrations-spåret samlat.

**Alternativ om Codex anser att persistens ska in nu:**
Lägg till kolumnerna i `AnalysisResult` men scope till `input_tokens` och
`output_tokens` (enkla int-kolumner utan FK-konsekvenser). `model` och
`target_fields` hör hemma i separat ticket.

## Berörda filer

Claude Code arbetar en fil i taget.

Rekommenderad filordning:

1. `backend/app/core/observability.py` (ny fil) — `AIRequestMetadata` och
   `log_ai_request()`.
2. `backend/app/core/ai.py` (ändring) — ersätt `print()` med
   `logging.getLogger(__name__).warning()`.
3. `backend/app/services/enrichment_service.py` (ändring) — bygg och logga
   `AIRequestMetadata` i `enrich_product()`. Importera `observability` som modul
   eller patcha service-modulens importväg i testerna så mocken faktiskt fångar
   anropet.
4. `backend/tests/test_enrichment_service.py` (ändring) — tester för success path.

Integration i `backend/app/services/enrichment_service.py` ska godkännas av Codex
innan det steget startar.

Inte tillåtet utan separat godkännande:

- Ändringar i `backend/app/models/analysis_result.py`.
- Databasmigrationer.
- Frontend.
- Andra AI-flöden än `enrich_product()`.

## Acceptance Criteria

- `AIRequestMetadata` finns i `backend/app/core/observability.py`.
- `log_ai_request()` finns och loggar via Python `logging`.
- `EnrichmentService.enrich_product()` anropar `log_ai_request()` vid success.
- `EnrichmentService.enrich_product()` anropar `log_ai_request()` med
  `status="error"` och `error_type` satt vid exception i AI/parse/validation-delen,
  sedan propageras undantaget.
- `print()` i `core/ai.py` är ersatt med `logging.warning()`.
- `AIRequestMetadata` innehåller separata `input_tokens` och `output_tokens`.
- `plan.model`, `plan.model_strategy`, `plan.target_fields` och `plan.use_rag`
  finns i metadata.
- Befintliga backend-tester fortsätter passera.
- Inga riktiga AI-anrop i tester.

## Testkrav

Uppdatera:

```txt
backend/tests/test_enrichment_service.py
```

### Test 1: log_ai_request anropas vid success

Given:
- Produkt med enrichable fält (t.ex. brand saknas).
- `ask_claude` mockad.
- `semantic_search` mockad.
- `log_ai_request` mockad på den importväg som `enrichment_service.py` faktiskt
  använder. Om service-filen gör `from app.core import observability`, använd
  `patch("app.services.enrichment_service.observability.log_ai_request")`.

Expect:
- `mock_log.assert_called_once()`.
- Metadata-objektet har `status="success"`.
- `metadata.sku_id` matchar produktens sku_id.
- `metadata.input_tokens` och `metadata.output_tokens` är int.

### Test 2: log_ai_request anropas med status=error vid Pydantic-fel

Given:
- `ask_claude` returnerar ett svar som failar Pydantic-validering.
- `log_ai_request` mockad.

Expect:
- `mock_log.assert_called_once()`.
- Metadata har `status="error"`.
- `metadata.error_type` är inte None.
- Metadata har tokenvärden från det mockade `ask_claude()`-svaret.
- Undantaget propageras (test med `pytest.raises`).

Befintliga fixtures och mock-mönster ska användas.

## Codex Review Notes

- Granska att `print()` i `ai.py` ersätts korrekt utan att retry-logiken bryts.
- Granska att `error_type` sätts och undantaget sedan propageras vidare — metadata
  ska inte svälja exceptions.
- Granska att `log_ai_request()` inte introducerar sidoeffekter som kan påverka
  test-isolation.
- Granska att `AIRequestMetadata` ligger i `core/` och inte i `services/` — det är
  cross-cutting infrastruktur.
- Kör minst:

```bash
docker compose exec backend pytest tests/test_enrichment_service.py -v
docker compose exec backend pytest tests/
```

## Risker

- `enrich_product()` fångar idag inte exceptions internt — felpath för metadata
  kräver att vi lägger ett `try/except` runt AI-anropet, vilket kan påverka
  felhanteringen nedströms. Scope: fånga, bygg metadata, logga, re-raise. Inga
  andra beteendeändringar.
- Python `logging` utan konfigurerad handler producerar ingenting i Docker om
  ingen root logger är konfigurerad. Verifiera att Docker-loggarna fångar
  `INFO`-nivå från backend, eller sätt `logging.basicConfig()` i `main.py`.
- `dataclasses.asdict()` på `AIRequestMetadata` serialiserar `list[str]` korrekt.
  Inget problem förväntat men bör verifieras i testet.

## Definition of Done

- Claude Code har arbetat en fil i taget.
- `observability.py` finns med `AIRequestMetadata` och `log_ai_request()`.
- `ai.py` använder `logging` istället för `print()`.
- `enrichment_service.py` loggar metadata vid success och error.
- Tester verifierar success- och error-path utan riktiga AI-anrop.
- Befintliga backend-tester passerar utan regression.
- Codex har reviewat diffen.
- Ticketen markeras Done när testerna passerar och Codex-review är klar.

## Codex Review

Godkänd.

Verifierat:

- `backend/app/core/observability.py` finns med `AIRequestMetadata` och
  `log_ai_request()`.
- `backend/app/core/ai.py` använder `logging.warning()` istället för `print()` i
  retry-blocken.
- `EnrichmentService.enrich_product()` loggar metadata vid success och vid
  AI/parse/validation-error.
- Exceptions loggas och propageras vidare.
- Ingen DB-persistens, ingen API-ändring och ingen frontendändring gjordes.

Testresultat:

```bash
docker compose exec backend pytest tests/test_enrichment_service.py -v
```

Resultat: 9 passed, 2 kända FastAPI on_event-varningar.

```bash
docker compose exec backend pytest tests/
```

Resultat: 44 passed, 2 kända FastAPI on_event-varningar.
