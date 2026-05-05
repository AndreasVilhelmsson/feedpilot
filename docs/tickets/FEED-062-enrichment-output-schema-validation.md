# FEED-062 — Enrichment Output Schema Validation

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FeedPilot ska vara ett AI-drivet enrichment-system, inte en prompt-baserad wrapper.

Den viktigaste regeln:

```txt
AI måste styras av kod, inte prompt.
```

I nuvarande enrichment-flöde:

```txt
EnrichmentService
  -> ask_claude()
  -> _extract_json()
  -> parsed dict
  -> AnalysisResult persistence
```

Problemet är att `parsed` används direkt:

```python
overall_score=parsed.get("overall_score")
issues=parsed.get("issues")
enriched_fields=parsed.get("enriched_fields")
return_risk=parsed.get("return_risk")
action_items=parsed.get("action_items")
```

Det betyder att prompten beskriver förväntat format, men kod validerar inte hela output-kontraktet innan persistence.

## Problem

AI-output är extern, opålitlig input.

Prompten säger vad Claude ska returnera, men Claude kan ändå returnera:

- fel enum
- fel typ
- saknade fält
- out-of-range score
- invalid issue-lista
- invalid enriched field-shape
- markdown eller extra text
- trunkerad JSON

Kod måste stoppa eller normalisera detta innan något sparas.

## Mål

Inför kodstyrd validering av AI enrichment-output före `AnalysisResult` sparas.

Första versionen ska vara smal:

- validera output-shape
- stoppa invalid output
- bevara befintligt API-beteende så mycket som möjligt
- lägga tester utan riktiga AI-anrop

## Berörda filer

Claude Code ska ändra en fil i taget.

Rekommenderad filordning:

1. `backend/app/schemas/enrich.py`
2. `backend/app/services/enrichment_service.py`
3. `backend/tests/test_enrichment_service.py`

Tillåtna efter separat godkännande:

- `backend/app/schemas/__init__.py`
- `backend/tests/conftest.py`

Inte tillåtet i denna ticket:

- preflight
- model/tool planner
- RAG refactor
- repository refactor
- frontend changes

## Nuvarande relevanta filer

### `backend/app/schemas/enrich.py`

Har redan:

- `EnrichedField`
- `EnrichIssue`
- `EnrichResponse`
- `BulkEnrichRequest`
- `BulkEnrichResponse`

Men dessa används främst som API-response schemas, inte som intern AI-output validation före persistence.

### `backend/app/services/enrichment_service.py`

Nuvarande kritisk punkt:

```python
parsed: dict = _extract_json(raw_text)

analysis = AnalysisResult(
    overall_score=parsed.get("overall_score"),
    issues=parsed.get("issues"),
    enriched_fields=parsed.get("enriched_fields"),
    return_risk=parsed.get("return_risk"),
    action_items=parsed.get("action_items"),
)
```

Här ska validering in mellan `_extract_json()` och `AnalysisResult`.

## Krav

### 1. Skapa intern AI-output schema

I `backend/app/schemas/enrich.py`, skapa en modell för parsed AI output.

Föreslaget namn:

```python
class EnrichmentAIOutput(BaseModel):
    ...
```

Den ska validera minst:

- `overall_score`: int, 0-100, optional eller default enligt beslut
- `enriched_fields`: dict[str, EnrichedField], default `{}`
- `issues`: list[EnrichIssue], default `[]`
- `return_risk`: `"high" | "medium" | "low"` eller `None`
- `return_risk_reason`: str | None
- `action_items`: list[str], default `[]`

Viktig regel:

Om output är strukturellt ogiltig ska valideringen faila. Den ska inte tyst acceptera uppenbart fel shape.

### 2. Använd schema i `EnrichmentService`

I `enrich_product()`:

1. extrahera JSON
2. validera med `EnrichmentAIOutput`
3. använd validerad data för persistence och response

Mental modell:

```python
parsed = _extract_json(raw_text)
validated = EnrichmentAIOutput.model_validate(parsed)

analysis = AnalysisResult(
    overall_score=validated.overall_score,
    issues=[issue.model_dump() for issue in validated.issues],
    enriched_fields={...},
    return_risk=validated.return_risk,
    action_items=validated.action_items,
)
```

Service ska inte spara raw `parsed` direkt.

### 3. Felhantering

Om AI-output inte validerar:

- kasta ett tydligt fel från service-lagret
- DB ska inte få ny `AnalysisResult`
- felet får bubbla till route som 500 i denna ticket

Det är okej att använda Pydantic `ValidationError` i första versionen.

### 4. Tester

Skapa ny testfil:

```txt
backend/tests/test_enrichment_service.py
```

Testerna ska inte göra riktiga AI-anrop.

Mocka:

- `ask_claude`
- `get_prompt` om nödvändigt
- `ProductRepository.semantic_search`

Minst dessa tester:

#### Test 1: valid AI-output sparas

Given:

- Product finns i DB.
- `ask_claude` returnerar valid JSON.

Expect:

- `AnalysisResult` skapas.
- `overall_score` sparas.
- `return_risk` sparas.
- `issues` sparas som list.
- `enriched_fields` sparas som dict.

#### Test 2: invalid return_risk stoppas

Given:

```json
{"return_risk": "extreme"}
```

Expect:

- service kastar valideringsfel
- ingen `AnalysisResult` sparas

#### Test 3: invalid overall_score stoppas

Given:

```json
{"overall_score": 999}
```

Expect:

- service kastar valideringsfel
- ingen `AnalysisResult` sparas

#### Test 4: invalid enriched_fields shape stoppas

Given:

```json
{"enriched_fields": ["not", "a", "dict"]}
```

Expect:

- service kastar valideringsfel
- ingen `AnalysisResult` sparas

### 5. Test DB

Testerna kan använda SQLite in-memory på samma sätt som `test_ingest.py`.

Viktigt:

- skapa `Product` i DB innan `enrich_product`
- använd fake repository eller riktig `ProductRepository` med mocked `semantic_search`
- inga OpenAI/Anthropic-anrop

## Acceptance Criteria

- AI-output valideras med Pydantic/schema innan persistence.
- Invalid `return_risk` stoppas.
- Invalid `overall_score` stoppas.
- Invalid `enriched_fields` shape stoppas.
- Valid output sparas som tidigare.
- Minst 4 enrichment service-tester finns.
- Backendtester passerar:

```bash
docker compose exec backend pytest tests/
```

## Testkrav

Codex ska köra:

```bash
docker compose exec backend pytest tests/
```

Efteråt ska backend baseline öka från:

```txt
16 tests
```

till minst:

```txt
20 tests
```

## Risker

- `EnrichResponse` och intern AI-output är inte exakt samma sak. Blanda inte ihop API-response med raw AI-output om det skapar otydlighet.
- För hård validering kan bryta befintliga AI-svar. Det är acceptabelt om svaret faktiskt är ogiltigt, men bra felmeddelanden behövs.
- Service har redan DB commit. Säkerställ att invalid output inte skapar partiella writes.
- RAG/semantic search kan trigga OpenAI embeddings om inte mockat. Tester måste undvika externa API-anrop.

## Out of Scope

Detta ska inte göras i FEED-062:

- preflight
- kostnadsestimat
- dynamiskt modellval
- web search/tool planner
- frontend UI
- repository-layer cleanup
- Alembic/migrations

## Definition of Done

- Claude Code har arbetat en fil i taget.
- Intern AI-output validering finns.
- Tester för valid och invalid AI-output finns.
- Inga riktiga AI-anrop görs i testerna.
- Codex har reviewat diffen.
- Codex har kört backendtesterna i Docker.
- Ticketen markeras Done först när testerna passerar eller blocker är dokumenterad.

## Codex Review — 2026-04-29

Resultat: Godkänd.

Ändringar:

- `backend/app/schemas/enrich.py` har ny intern valideringsmodell `EnrichmentAIOutput`.
- `EnrichmentAIOutput` återanvänder befintliga `EnrichedField` och `EnrichIssue`.
- `backend/app/services/enrichment_service.py` validerar parsed AI-output före `AnalysisResult` skapas.
- Persistence och response byggs nu från validerad output, inte raw `parsed` dict.
- `backend/tests/test_enrichment_service.py` har 4 service-level tester.

Verifierade riskscenarion:

- Valid AI-output skapar `AnalysisResult`.
- `return_risk: "extreme"` kastar `ValidationError` och sparar inget.
- `overall_score: 999` kastar `ValidationError` och sparar inget.
- `enriched_fields` som lista kastar `ValidationError` och sparar inget.

Verifiering:

```bash
docker compose exec backend pytest tests/
# 20 passed, 2 FastAPI on_event deprecation warnings
```

Notering:

- `EnrichmentAIOutput` använder `extra="ignore"`. Det är acceptabelt i första passet, men kan skärpas till `extra="forbid"` senare om vi vill upptäcka oväntade AI-fält.
- API endpoint-tester för enrichment är fortfarande inte täckta; denna ticket täcker service-lagret.
