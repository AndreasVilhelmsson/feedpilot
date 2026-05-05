# FEED-063 — Bulk Enrichment Preflight

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

Vi har lärt oss av Textual att ett AI enrichment-system kan bli väldigt dyrt och svårt att styra om det byggs som:

```txt
produktfält -> AI-call
produktfält -> AI-call
produktfält -> AI-call
```

Det gör att kostnaden skalar med:

```txt
antal produkter * antal fält * context size
```

I praktiken skickas samma produktdata, prompt och kontext flera gånger.

FeedPilot ska byggas annorlunda:

```txt
produkt -> enrichment plan -> grupperade fält -> få AI-calls
```

Målet är att kostnad och workload ska vara synlig innan körning.

## Problem från Textual

Nuvarande problem vi vill undvika i FeedPilot:

- AI prompts körs per fält istället för per produkt.
- Samma produktdata och prompt-context skickas flera gånger.
- Ingen grouping/batching av fält.
- AI körs även när fält redan har data eller inte är relevanta.
- Ingen preflight innan användaren startar enrichment.
- Ingen token-/kostnadsestimering innan jobb skapas.
- Tool usage, t.ex. web search, styrs för löst via prompt.
- Intern AI-kostnad och kundpris kan glida isär.
- Queue-design kan bli överbelastad om tasks är för små och för många.

## Mål för FeedPilot

FeedPilot ska:

- köra enrichment per produkt, inte per fält
- gruppera flera fält i färre AI-anrop
- filtrera bort onödiga enrichment-tasks
- estimera token usage och kostnad före execution
- kräva användarbekräftelse före bulk-körning
- kontrollera tools i backend-kod/config, inte prompt
- logga tokens/kostnad per jobb och senare per produkt
- minimera input tokens
- undvika duplicerad produktkontext

## Scope för FEED-063

Detta är första implementationen av preflight.

Den ska vara backend-first och deterministisk.

I denna ticket ska vi inte göra riktiga AI-anrop.

Vi ska skapa ett preflight-flöde som svarar på:

```txt
Om användaren startar bulk enrichment nu:
  Hur många produkter påverkas?
  Vilka fält verkar behöva enrichment?
  Hur många AI-calls planeras ungefär?
  Hur många tokens uppskattas?
  Vad blir ungefärlig kostnad?
  Kräver körningen confirmation?
```

## Viktig arkitekturregel

Preflight får inte bygga på prompt.

Kod ska avgöra:

- vilka produkter som ingår
- vilka fält som saknas
- vilka fält som behöver enrichment
- om fält kan grupperas
- uppskattad payload-storlek
- uppskattad kostnad
- om tools är tillåtna

## Berörda filer

Claude Code ska ändra en fil i taget.

Rekommenderad filordning:

1. `backend/app/schemas/enrich.py`
2. `backend/app/services/enrichment_service.py` eller ny `backend/app/services/preflight_service.py`
3. `backend/app/api/enrich.py`
4. `backend/tests/test_enrichment_preflight.py`

Tillåtna efter separat godkännande:

- `backend/app/repositories/product_repository.py`
- `backend/app/schemas/job.py`

Inte tillåtet i denna ticket:

- frontend UI
- faktiska AI-anrop
- web search implementation
- model/tool planner i full version
- prissättnings-/billing-system
- queue refactor

## Föreslagen API-design

Första version:

```txt
POST /api/v1/enrich/preflight
```

Request:

```json
{
  "limit": 25
}
```

Response:

```json
{
  "product_count": 25,
  "estimated_ai_calls": 25,
  "estimated_input_tokens": 30000,
  "estimated_output_tokens": 12500,
  "estimated_total_tokens": 42500,
  "estimated_cost_usd": 0.12,
  "fields_to_enrich": {
    "title": 3,
    "description": 18,
    "brand": 7,
    "color": 5,
    "material": 9,
    "size": 4
  },
  "tool_plan": {
    "rag": true,
    "web_search": false,
    "image_analysis": false
  },
  "requires_confirmation": true
}
```

Exakt token/kostnad behöver inte vara perfekt i första versionen. Det viktiga är att den är:

- deterministisk
- transparent
- billig att beräkna
- bättre än att starta jobb blint

## Estimeringsregler i första version

Första versionen får använda enkla konstanter i kod.

Exempel:

```python
ESTIMATED_INPUT_TOKENS_PER_PRODUCT = 1200
ESTIMATED_OUTPUT_TOKENS_PER_PRODUCT = 500
ESTIMATED_COST_PER_1K_INPUT_TOKENS_USD = 0.003
ESTIMATED_COST_PER_1K_OUTPUT_TOKENS_USD = 0.015
```

Viktigt:

- Konstanterna ska ligga i backend-kod, inte prompt.
- Namnen ska göra tydligt att detta är estimate.
- Senare kan FEED-066/observability ersätta estimate med faktisk kostnadslogg.

## Fältfilter i första version

Preflight ska räkna saknade core fields per produkt.

Utgå från `CanonicalProduct.missing_core_fields()` eller motsvarande befintlig logik.

För varje kandidatprodukt:

```txt
Product ORM
  -> CanonicalProduct
  -> missing_core_fields()
  -> aggregate field counts
```

Exempel:

```json
{
  "fields_to_enrich": {
    "description": 18,
    "brand": 7
  }
}
```

## AI-call strategy i första version

Regel:

```txt
1 product = max 1 enrichment AI call
```

Det är den viktigaste skillnaden mot Textuals per-field-call-problem.

Preflight ska därför sätta:

```txt
estimated_ai_calls = product_count
```

Inte:

```txt
sum(fields_to_enrich)
```

## Confirmation-regel

Preflight response ska alltid innehålla:

```json
"requires_confirmation": true
```

Senare ska `/enrich/bulk` kräva en confirmation token eller preflight id, men det är out of scope i första passet om det blir för stort.

## Tester

Skapa:

```txt
backend/tests/test_enrichment_preflight.py
```

Minst 4 tester:

### Test 1: preflight räknar produkter

Given:

- 3 produkter som saknar enrichment.

Expect:

- `product_count == 3`
- `estimated_ai_calls == 3`

### Test 2: preflight aggregerar missing fields

Given:

- produkter med saknad description/brand/material.

Expect:

- `fields_to_enrich` innehåller counts per saknat fält.

### Test 3: preflight gör inga AI-anrop

Mocka `ask_claude` så testet failar om den anropas.

Expect:

- preflight kör klart utan AI-call.

### Test 4: kostnadsestimat är deterministiskt

Given:

- 2 produkter.

Expect:

- estimated tokens/cost är > 0
- samma input ger samma estimate

## Acceptance Criteria

- Preflight kan köras utan AI-anrop.
- Preflight räknar kandidatprodukter.
- Preflight räknar saknade fält.
- Preflight estimerar AI-calls per produkt, inte per fält.
- Preflight estimerar tokens och kostnad.
- Preflight response innehåller `requires_confirmation`.
- Backendtester passerar:

```bash
docker compose exec backend pytest tests/
```

## Testkrav

Codex ska köra:

```bash
docker compose exec backend pytest tests/
```

Efteråt bör backend baseline öka från:

```txt
20 tests
```

till minst:

```txt
24 tests
```

## Risker

- Kostnadsestimat kan uppfattas som exakt. Namnge det tydligt som estimate.
- Första versionen kan underskatta/överskatta tokens. Det är acceptabelt om det dokumenteras.
- Om vi kopplar preflight för hårt till dagens enrichment-service kan senare planner bli svårare. Håll preflight enkel.
- Om `/enrich/bulk` ändras för mycket kan frontendflödet påverkas. Håll enforcement av confirmation till senare om scope växer.

## Out of Scope

Detta ska inte göras i FEED-063 första pass:

- frontend preflight UI
- confirmation token enforcement i `/enrich/bulk` om det blir stort
- faktisk billing
- faktisk web search
- faktisk image analysis
- dynamiskt modellval
- queue split
- customer pricing model

## Definition of Done

- Claude Code har arbetat en fil i taget.
- Preflight är backend-kod, inte prompt.
- Minst 4 preflight-tester finns.
- Inga riktiga AI-anrop görs i testerna.
- Codex har reviewat diffen.
- Codex har kört backendtesterna i Docker.
- Ticketen markeras Done först när testerna passerar eller blocker är dokumenterad.

## Codex Review — 2026-04-29

Resultat: Godkänd.

Ändringar:

- `backend/app/schemas/enrich.py` har `PreflightRequest` och `PreflightResponse`.
- `backend/app/services/preflight_service.py` beräknar preflight utan AI-anrop.
- `backend/app/api/enrich.py` exponerar `POST /api/v1/enrich/preflight`.
- `backend/tests/test_enrichment_preflight.py` har 4 service-level tester.

Verifierade krav:

- Preflight räknar kandidatprodukter.
- `estimated_ai_calls == product_count`, inte antal fält.
- Saknade fält aggregeras via `CanonicalProduct.missing_core_fields()`.
- Token- och kostnadsestimat är deterministiska.
- `requires_confirmation` är alltid `True`.
- Preflight gör inga AI-anrop.

Verifiering:

```bash
docker compose exec backend pytest tests/
# 24 passed, 2 FastAPI on_event deprecation warnings
```

Notering:

- `_product_to_canonical()` i `preflight_service.py` duplicerar viss logik från `EnrichmentService`. Det accepteras i denna ticket för låg risk, men bör tas upp i `FEED-068`.
- `/enrich/bulk` kräver ännu inte confirmation token/preflight id. Det är medvetet out of scope för första preflight-versionen.
