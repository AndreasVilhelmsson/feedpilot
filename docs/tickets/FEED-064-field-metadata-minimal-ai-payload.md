# FEED-064 — Field Metadata och Minimal AI Payload

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FEED-063 införde preflight och etablerade principen att AI-input ska styras av backend-kod.
FEED-064 tar nästa steg: koden ska avgöra exakt vilka fält som skickas till modellen.

Idag byggs Claude-payloaden i `_build_user_message()` i `enrichment_service.py`. Den
skickar alltid samma hårdkodade fältlista till Claude:

```python
"product": {
    "sku_id": canonical.sku_id,
    "title": canonical.title,
    "description": canonical.description,
    "brand": canonical.brand,
    "category": canonical.category,
    "price": canonical.price,
    "color": canonical.color,
    "material": canonical.material,
    "size": canonical.size,
    "gender": canonical.gender,
    "attributes": canonical.extra_attributes,
}
```

Det innebär att:

- Fält som inte är relevanta för den specifika enrichment-tasken ändå skickas.
- Modellen får mer kontext än den behöver.
- Det finns ingen mekanisk koppling mellan `missing_fields` och vilka fält som faktiskt
  skickas i produktobjektet.
- Token-kostnaden kan inte minimeras per task utan att ändra hårdkodad kod.

## Problem

Systemet saknar en generell mekanism för att avgöra vilka fält som är relevanta för
en given enrichment-task. Payload-byggandet är fast och prompt-beroende snarare än
metadata-styrt.

CLAUDE.md-principen är tydlig:

```txt
Minimize model input. Never send an entire product object by default.
Send only fields relevant to the specific enrichment task,
derived from canonical schema metadata and field complexity.
```

## Mål

Inför field metadata och en payload-builder så att backend-kod avgör vilka canonical
fields och context fields som skickas till modellen — baserat på `missing_fields`.

## Arkitekturregel

Valet av vilka fält som ingår i AI-payloaden är en produktregel, inte en promptregel.
Koden ska äga detta beslut.

```txt
missing_fields → field metadata lookup → minimal payload → ask_claude()
```

Prompten får fortfarande guida tone och format. Men koden bestämmer vilka fält modellen
ser.

## Scope

Följande ingår i FEED-064:

- Metadata per canonical field i backend-kod.
- En payload-builder som tar `missing_fields` + `CanonicalProduct` och bygger minimal
  input-dict.
- `EnrichmentService` ska kunna använda payload-builder istället för det nuvarande
  fasta payload-objektet i `_build_user_message()`.
- Tester som verifierar att irrelevanta fält exkluderas och att relevanta context fields
  inkluderas.

## Out of Scope

Följande ingår inte i FEED-064:

- Model/tool planner (FEED-065).
- Dynamiskt modellval per task.
- Web search (planeras i senare ticket).
- Image analysis planner.
- AI observability och kostnadslogg (FEED-066).
- Frontend-ändringar.
- API endpoint-ändringar.
- Stora refactors av befintlig enrichment-pipeline.
- Confirmation token enforcement (hanterades i FEED-063 som out of scope).

## Field Metadata — Designbeslut

Varje canonical field ska ha metadata som beskriver:

| Attribut | Typ | Beskrivning |
|---|---|---|
| `name` | `str` | Fältnamnet som i `CanonicalProduct` |
| `is_enrichable` | `bool` | Om fältet kan enrichas av AI |
| `context_fields` | `list[str]` | Vilka andra fält som är användbara kontext för att enricha detta fält |
| `complexity` | `Literal["low", "medium", "high"]` | Indikator på task-komplexitet (används av FEED-065 senare) |

Exempel på metadata för `description`:

```python
FieldMeta(
    name="description",
    is_enrichable=True,
    context_fields=["title", "brand", "category", "color", "material", "gender"],
    complexity="high",
)
```

Exempel på metadata för `brand`:

```python
FieldMeta(
    name="brand",
    is_enrichable=True,
    context_fields=["title", "category", "extra_attributes"],
    complexity="low",
)
```

Icke-enrichable fält (t.ex. `sku_id`, `raw_data`, `quality_warnings`) ska inte ha
`is_enrichable=True` och ska aldrig läggas till som enrichment-target.

## Payload Builder — Designbeslut

Payload-buildern tar:

- `canonical: CanonicalProduct`
- `missing_fields: list[str]`
- `rag_context: list[dict]`

Den returnerar ett dict med:

- `product`: minimal dict med `sku_id` + exakt de fält som är relevanta kontext för
  de saknade fälten — union av `context_fields` från metadata för alla `missing_fields`.
- `rag_context`: oförändrat från nuvarande implementation.
- `missing_fields`: oförändrat.
- `enrichment_instruction`: oförändrat (styrs av `missing_fields`).

Exempel: om `missing_fields = ["brand"]` och `brand.context_fields = ["title", "category"]`
ska payloaden bara inkludera `sku_id`, `title`, `category` i `product`-dict — inte
`description`, `color`, `material`, `size`, `gender`, `price`, `attributes`.

Viktigt: `sku_id` ska alltid inkluderas för identifiering.

## Berörda filer

Claude Code ska arbeta en fil i taget.

Rekommenderad filordning:

1. `backend/app/services/field_metadata.py` (ny fil) — `FieldMeta`-dataclass och
   `FIELD_REGISTRY` med metadata för alla enrichable canonical fields.
2. `backend/app/services/payload_builder.py` (ny fil) — `build_enrichment_payload()`
   som tar canonical + missing_fields + rag_context och returnerar minimal dict.
3. `backend/tests/test_field_metadata.py` (ny fil) — tester för registry lookup,
   payload builder och att enrichment service använder minimal payload.
4. `backend/app/services/enrichment_service.py` (ändring) — ersätt `_build_user_message()`
   med anrop till `build_enrichment_payload()`.

Tillåtna efter separat godkännande:

- `backend/app/schemas/canonical.py` om vi vill lägga hjälpmetod `context_fields_for()`

Inte tillåtet i denna ticket:

- Ändringar i `backend/app/api/enrich.py`
- Ändringar i `backend/app/core/ai.py`
- Frontend
- Databasmigrationer

## Acceptance Criteria

- Metadata per canonical field finns i `backend/app/services/field_metadata.py`.
- `FIELD_REGISTRY` innehåller metadata för minst alla nuvarande enrichable core fields:
  `title`, `description`, `brand`, `category`, `color`, `material`.
- `build_enrichment_payload()` bygger minimal dict baserat på `missing_fields`.
- Hela produktobjektet skickas inte som default — bara relevanta context fields inkluderas.
- `sku_id` finns alltid med i payload.
- Tester visar att om `missing_fields = ["brand"]` är irrelevanta fält som `description`
  och `material` exkluderade om de inte är definierade som context fields för `brand`.
- Tester visar att rätt context fields inkluderas för varje missing field.
- Tester visar att `EnrichmentService` serialiserar och skickar payloaden från
  `build_enrichment_payload()` till `ask_claude()`.
- Inga riktiga AI-anrop görs i tester.
- `EnrichmentService._build_user_message()` är ersatt av `build_enrichment_payload()`.
- Backendtester passerar:

```bash
docker compose exec backend pytest tests/
```

## Tester

Skapa:

```txt
backend/tests/test_field_metadata.py
```

### Test 1: registry innehåller alla enrichable core fields

Expect:

- `FIELD_REGISTRY` har nycklar för `title`, `description`, `brand`, `category`,
  `color`, `material`.
- Alla har `is_enrichable=True`.

### Test 2: payload exkluderar irrelevanta fält

Given:

- `missing_fields = ["brand"]`
- `brand.context_fields = ["title", "category"]`
- `CanonicalProduct` med alla fält ifyllda.

Expect:

- Payload `product`-dict innehåller `sku_id`, `title`, `category`.
- Payload `product`-dict innehåller INTE `description`, `color`, `material`, `size`,
  `gender`, `price`, `attributes`.

Notering: om implementationen väljer att låta `brand.context_fields` inkludera
`extra_attributes`, ska detta serialiseras under befintlig payload-nyckel `attributes`
för att bevara dagens promptkontrakt. Då ska testet för `brand` uppdateras så att
`attributes` ingår i expected payload.

### Test 3: payload inkluderar union av context fields för flera missing fields

Given:

- `missing_fields = ["description", "brand"]`
- `description.context_fields = ["title", "brand", "category", "color", "material"]`
- `brand.context_fields = ["title", "category"]`

Expect:

- Payload `product`-dict är union: `sku_id`, `title`, `brand`, `category`, `color`,
  `material`.
- Inget duplicerat.

### Test 4: sku_id alltid med även om det inte är i context_fields

Given:

- `missing_fields = ["brand"]`
- Context fields definierar inte `sku_id`.

Expect:

- Payload `product`-dict innehåller `sku_id`.

### Test 5: inga riktiga AI-anrop

Mocka `ask_claude` så testet failar om den anropas.

Expect:

- Payload-buildern kör klart utan AI-call.

### Test 6: EnrichmentService använder minimal payload

Given:

- En produkt där `brand` saknas men `description`, `material`, `price` och `gender`
  har värden.
- `ask_claude` är mockad och fångar prompten som skickas.
- `semantic_search` är mockad.

Expect:

- Prompten innehåller minimal `product`-payload från `build_enrichment_payload()`.
- Irrelevanta fält för `brand` skickas inte.
- Testet gör inget riktigt AI-anrop.

## Risker

- Om `context_fields` definieras för snävt kan modellen sakna viktig kontext och ge
  sämre enrichment-kvalitet. Börja med breda context_fields och snäva in gradvis.
- `_build_user_message()` används på ett ställe idag (i `enrich_product()`). Risken för
  regression är låg om bytet är direkt.
- Payload-formatet som skickas till Claude ändras, vilket kan påverka promptens
  fungerade förutsättningar. Behåll samma nycklar i `product`-dict — ta bara bort
  fält som inte är relevanta, lägg inte till nya.
- Komplexitets-attributet används inte av FEED-064 i sig. Det är en forward-compatible
  förberedelse för FEED-065. Definiera det nu men koppla det inte till något beslut än.

## Definition of Done

- Claude Code har arbetat en fil i taget.
- `field_metadata.py` och `payload_builder.py` finns som separata filer.
- `EnrichmentService` använder `build_enrichment_payload()` istället för
  `_build_user_message()`.
- Minst 5 tester i `test_field_metadata.py`.
- Inga riktiga AI-anrop i tester.
- Codex har reviewat diffen.
- Codex har kört backendtesterna i Docker.
- Backendtester passerar utan regression.
- Ticketen markeras Done först när testerna passerar eller blocker är dokumenterad.

## Codex Review — 2026-05-07

Resultat: Godkänd.

Ändringar:

- `backend/app/services/field_metadata.py` har `FieldMeta`, `FIELD_REGISTRY` och `get_field_meta()`.
- `FIELD_REGISTRY` täcker core fields: `title`, `description`, `brand`, `category`, `color`, `material`.
- `backend/app/services/payload_builder.py` bygger minimal enrichment-payload från `CanonicalProduct`, `missing_fields` och RAG-context.
- `extra_attributes` serialiseras under befintlig payload-nyckel `attributes`.
- `backend/app/services/enrichment_service.py` använder `build_enrichment_payload()` via `_build_user_message()`.
- `backend/tests/test_field_metadata.py` täcker registry och payload-builder.
- `backend/tests/test_enrichment_service.py` verifierar att `EnrichmentService` skickar minimal payload till `ask_claude()`.

Verifierade krav:

- Metadata ligger i backend-kod, inte prompt.
- Payloaden innehåller alltid `sku_id`.
- Payloaden innehåller bara unionen av relevanta context fields för `missing_fields`.
- Hela produktobjektet skickas inte som default.
- Inga riktiga AI-anrop görs i testerna.

Verifiering:

```bash
docker compose exec backend pytest tests/
# 32 passed, 2 FastAPI on_event deprecation warnings
```

Notering:

- `FieldMeta.context_fields` är en `list[str]` i en frozen dataclass. Det är accepterat i denna ticket, men kan skärpas till tuple senare om registryt behöver vara strikt immutabelt.
- FEED-065 ska bygga vidare på `complexity`, men FEED-064 använder det inte för beslut.
