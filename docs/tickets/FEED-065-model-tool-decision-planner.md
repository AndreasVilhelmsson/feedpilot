# FEED-065 — Model/Tool Decision Planner

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-064 gjorde AI-input kodstyrd och minimal. `build_enrichment_payload()` avgör nu
vilka canonical fields som skickas till Claude baserat på `missing_fields` och
`FIELD_REGISTRY`.

`FieldMeta.complexity` finns sedan FEED-064 men är kopplad till ingen beslutspunkt —
dokumentet definierar det som "forward-compatible förberedelse för FEED-065".

Nästa steg är att göra model- och verktygsstrategi kodstyrd på samma sätt. Idag
avgörs det inte av en explicit plan: `enrichment_service.py` anropar alltid
`ask_claude()` med samma modell och hämtar alltid RAG-context före anropet. Web search
och image analysis aktiveras inte baserat på task-typ. Det finns ingen plan per
enrichment-task.

## Problem

Systemet saknar en backend-driven plan som avgör:

- Vilka av de saknade fälten som faktiskt är enrichable.
- Vilken komplexitetsnivå enrichment-tasken har.
- Vilken modell som ska användas.
- Om RAG-kontext ska hämtas.
- Om web search ska aktiveras (flagga; implementation är out of scope nu).
- Om image analysis ska aktiveras (flagga; implementation är out of scope nu).

Utan denna plan är det omöjligt att:

- Välja billigare modell för enkla tasks.
- Styra verktygsanvändning per task utan att ändra prompt.
- Följa principen i CLAUDE.md: "AI behavior must be controlled by code, not by prompts alone."

## Mål

Inför en deterministisk enrichment planner i backend-kod som returnerar en
`EnrichmentPlan` baserat på `missing_fields` och `FIELD_REGISTRY`. Planen är
deterministisk — samma input ger alltid samma output. Ingen AI-anrop krävs för
att beräkna planen.

```txt
missing_fields → enrichment_planner → EnrichmentPlan → enrichment pipeline
```

## Arkitekturregel

Valet av modell, verktyg och RAG-strategi är en produktregel, inte en promptregel.
Prompten får guida tone och format. Koden bestämmer vilken modell som används och
vilka verktyg som aktiveras.

## Scope

Följande ingår i FEED-065:

- Ny fil `backend/app/services/enrichment_planner.py` med:
  - `EnrichmentPlan`-dataclass med fälten definierade nedan.
  - `plan_enrichment(missing_fields: list[str]) -> EnrichmentPlan` — den enda
    publika funktionen.
- `plan_enrichment()` använder `FIELD_REGISTRY` och `FieldMeta.complexity` för
  alla beslut.
- Okända och icke-enrichable missing_fields filtreras bort tyst — endast fält som
  finns i `FIELD_REGISTRY` och har `is_enrichable=True` läggs i `target_fields`.
- Ny fil `backend/tests/test_enrichment_planner.py` med tester för
  low / medium / high complexity, okända fält, och tom lista.
- Inga riktiga AI-anrop i tester.

## Out of Scope

Följande ingår inte i FEED-065:

- Faktisk web search implementation.
- Faktisk image analysis implementation.
- Observability/loggmodell (FEED-066).
- Billing eller kostnadspersistens.
- Frontend.
- API endpoint-ändringar.
- Queue-ändringar.
- Integration av planner i `EnrichmentService` — det görs i ett separat godkänt steg.
- Ändringar i `core/ai.py` (om de inte uttryckligen godkänns).
- Stora refactors av befintlig enrichment-pipeline.

## EnrichmentPlan — Designbeslut

`EnrichmentPlan` är en frozen dataclass med följande fält:

| Fält | Typ | Beskrivning |
|---|---|---|
| `target_fields` | `list[str]` | Enrichable fält ur `missing_fields` (filtrerade via FIELD_REGISTRY) |
| `complexity` | `Literal["low", "medium", "high"]` | Högsta complexity bland `target_fields`; `"low"` om listan är tom |
| `model_strategy` | `Literal["cheap", "standard", "strong"]` | Strateginivå för framtida modellval |
| `model` | `str` | Modell-ID som ska användas för enrichment-anropet |
| `use_rag` | `bool` | Om RAG-kontext ska hämtas och inkluderas i payload |
| `use_web_search` | `bool` | Om web search ska aktiveras (alltid `False` i detta pass) |
| `use_image_analysis` | `bool` | Om image analysis ska aktiveras (alltid `False` i detta pass) |

## plan_enrichment() — Designbeslut

Funktionssignatur:

```python
def plan_enrichment(missing_fields: list[str]) -> EnrichmentPlan:
    ...
```

### Steg 1 — Filtrera target_fields

Iterera `missing_fields`. Inkludera ett fält i `target_fields` om och endast om:

1. Det finns i `FIELD_REGISTRY`.
2. `is_enrichable=True`.

Okända fält ignoreras tyst (ingen exception).

### Steg 2 — Bestäm complexity

Använd `FieldMeta.complexity` för varje fält i `target_fields`.
Välj den högsta nivån i prioritetsordning: `"high"` > `"medium"` > `"low"`.
Om `target_fields` är tom, sätt `complexity="low"`.

```python
_COMPLEXITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
```

### Steg 3 — Välj modellstrategi och modell

Initialt mappas complexity till modellstrategi enligt:

| Complexity | model_strategy |
|---|---|
| `"low"` | `"cheap"` |
| `"medium"` | `"standard"` |
| `"high"` | `"strong"` |

I detta första pass ska `model` fortfarande vara dagens befintliga textmodell:

```python
DEFAULT_TEXT_MODEL = "claude-sonnet-4-6"
```

Motivering: `core/ai.py` är fortfarande hårdkodad till `claude-sonnet-4-6`, och
FEED-065 ska inte introducera nya otestade Anthropic model-ID:n. Plannern får däremot
returnera `model_strategy`, så en senare integration/config-ticket kan mappa `"cheap"`
till en verifierad billigare modell.

Modellnamnen ska definieras som modulnivå-konstanter — aldrig hårdkodas i
`plan_enrichment()` direkt — så att ett framtida config-lager kan byta dem utan
att ändra logiken.

### Steg 4 — Sätt verktygsflags

```python
use_rag = len(target_fields) > 0          # RAG ger värde om det finns fält att enricha
use_web_search = False                    # ej implementerat i detta pass
use_image_analysis = False                # ej implementerat i detta pass
```

## Berörda filer

Claude Code ska arbeta en fil i taget.

Rekommenderad filordning:

1. `backend/app/services/enrichment_planner.py` (ny fil) — `EnrichmentPlan`-dataclass
   och `plan_enrichment()`.
2. `backend/tests/test_enrichment_planner.py` (ny fil) — tester för alla scenarios.

Integration i `backend/app/services/enrichment_service.py` ska göras i ett separat
godkänt steg efter att planner-kontraktet är reviewat.

Inte tillåtet i denna ticket utan separat godkännande:

- Ändringar i `backend/app/core/ai.py`.
- Ändringar i `backend/app/api/enrich.py`.
- Frontend.
- Databasmigrationer.

## Acceptance Criteria

- `plan_enrichment()` finns i `backend/app/services/enrichment_planner.py`.
- Funktionen använder `FIELD_REGISTRY` och `FieldMeta.complexity` — inga hårdkodade
  fältnamn i planner-logiken.
- `EnrichmentPlan` är en frozen dataclass med alla sju fält definierade ovan.
- `plan_enrichment(["brand"])` returnerar `complexity="low"`, `model_strategy="cheap"`,
  `model="claude-sonnet-4-6"`,
  `use_rag=True`, `use_web_search=False`, `use_image_analysis=False`.
- `plan_enrichment(["description"])` returnerar `complexity="high"`,
  `model_strategy="strong"`, `model="claude-sonnet-4-6"`.
- `plan_enrichment(["brand", "description"])` returnerar `complexity="high"`
  (worst-case vinner).
- `plan_enrichment(["nonexistent"])` returnerar `target_fields=[]`, `complexity="low"`,
  `use_rag=False`.
- `plan_enrichment([])` returnerar `target_fields=[]`, `complexity="low"`,
  `use_rag=False`.
- Inga riktiga AI-anrop i tester.
- Befintliga 32 backend-tester fortsätter passera.

## Tester

Skapa:

```txt
backend/tests/test_enrichment_planner.py
```

### Test 1: low complexity plan

Given `missing_fields=["brand"]` (complexity="low" i registry).

Expect:
- `plan.target_fields == ["brand"]`
- `plan.complexity == "low"`
- `plan.model_strategy == "cheap"`
- `plan.model == "claude-sonnet-4-6"`
- `plan.use_rag is True`
- `plan.use_web_search is False`
- `plan.use_image_analysis is False`

### Test 2: high complexity vinner vid mix

Given `missing_fields=["brand", "description"]`
(`brand.complexity="low"`, `description.complexity="high"`).

Expect:
- `plan.complexity == "high"`
- `plan.model_strategy == "strong"`
- `plan.model == "claude-sonnet-4-6"`
- Båda fälten finns i `target_fields`

### Test 3: medium complexity plan

Given `missing_fields=["title"]` (complexity="medium" i registry).

Expect:
- `plan.complexity == "medium"`
- `plan.model_strategy == "standard"`
- `plan.model == "claude-sonnet-4-6"`

### Test 4: okänt fält filtreras tyst

Given `missing_fields=["nonexistent_field"]`.

Expect:
- `plan.target_fields == []`
- `plan.complexity == "low"`
- `plan.use_rag is False`

### Test 5: tom lista

Given `missing_fields=[]`.

Expect:
- `plan.target_fields == []`
- `plan.complexity == "low"`
- `plan.use_rag is False`

### Test 6: plan är deterministisk

Kör `plan_enrichment(["brand", "color", "material"])` två gånger.
Expect: identiska `EnrichmentPlan`-instanser.

### Test 7: plan använder FIELD_REGISTRY — inga hårdkodade fältnamn

Verifiera att alla fält i `target_fields` finns i `FIELD_REGISTRY` och har
`is_enrichable=True`. Gör detta dynamiskt — om registryt ändras ska testet
fortfarande vara korrekt.

## Risker

- Modellmappningen introducerar ett implicit kontrakt: om dagens standardmodell ändras
  måste konstanterna uppdateras. Håll dem i modulnivå-konstanter.
- `model_strategy` är ett planeringsvärde, inte faktisk routing ännu. Det är avsiktligt
  tills `core/ai.py` eller config-lagret får stöd för explicit modellval.
- `use_rag=True` som default gör att RAG alltid körs om det finns target_fields.
  Det är korrekt i detta pass men kan behöva ett eget flag i metadata längre fram.
- Planner-resultatet integreras inte i `EnrichmentService` i detta pass. Det är
  avsiktligt — vi vill att Codex reviewar planner-kontraktet innan vi kopplar det.
- `FieldMeta.context_fields` är `list[str]` i en frozen dataclass. Mutabel default är
  skyddad av `field(default_factory=list)` men kan skärpas till `tuple` senare.

## Definition of Done

- Claude Code har arbetat en fil i taget.
- `enrichment_planner.py` finns med `EnrichmentPlan` och `plan_enrichment()`.
- `test_enrichment_planner.py` finns med minst 7 tester.
- Inga riktiga AI-anrop i tester.
- Befintliga 32 backend-tester fortsätter passera utan regression.
- Codex har reviewat diffen.
- Ticketen markeras Done när testerna passerar och Codex-review är klar.

## Codex Review — 2026-05-07

Resultat: Godkänd.

Ändringar:

- `backend/app/services/enrichment_planner.py` har `EnrichmentPlan`, `plan_enrichment()`, `DEFAULT_TEXT_MODEL`, `Complexity` och `ModelStrategy`.
- Planner använder `FIELD_REGISTRY` och `FieldMeta.complexity` för att filtrera target fields och bestämma worst-case complexity.
- Planner returnerar `model_strategy` (`cheap`, `standard`, `strong`) utan att introducera nya otestade Anthropic model-ID:n.
- `model` är fortsatt `claude-sonnet-4-6`, vilket matchar dagens `core/ai.py`.
- Planner sätter `use_rag=True` när det finns target fields och `False` annars.
- `use_web_search` och `use_image_analysis` är backend-styrda flags och `False` i detta pass.
- `backend/tests/test_enrichment_planner.py` har 8 tester för low/medium/high, okända fält, tom input, determinism, registry-filtering och deduplicerad ordning.

Verifierade krav:

- Planner finns i backend-kod, inte prompt.
- Planner är deterministisk.
- Okända fält filtreras tyst.
- Duplicerade fields dedupliceras med första ordning bevarad.
- Inga riktiga AI-anrop görs i testerna.

Verifiering:

```bash
docker compose exec backend pytest tests/
# 40 passed, 2 FastAPI on_event deprecation warnings
```

Notering:

- Planner är ännu inte integrerad i `EnrichmentService`; det var medvetet out of scope för första FEED-065-pass.
- `EnrichmentPlan.target_fields` är en `list[str]` i en frozen dataclass. Det är accepterat i denna ticket, men kan skärpas till tuple senare om strikt immutabilitet behövs.
