# FEED-072 — Investigation: låg avg_enrichment_score och hög return_risk_high

**Sprint:** Sprint 2
**Typ:** Investigation — ingen kod skrivs
**Prioritet:** Hög
**Skapad:** 2026-05-15

---

## Problem och frågeställning

Efter att FEED-071 kopplade dashboarden till riktiga data visar GET /api/v1/stats:

- `avg_enrichment_score`: **35.6** (av 100)
- `return_risk_high`-andel: **84.6%** av enrichade produkter

Dessa siffror är alarmerande men kan förklaras av minst tre olika saker:

| Hypotes | Innebär |
|---|---|
| A — Skev testdata | Produkterna i databasen saknar titel/beskrivning/kategori. AI bedömer dem som svaga eftersom inputen är svag. Siffrorna är korrekta men speglar dålig testdata, inte ett pipeline-problem. |
| B — Felaktigt scoring-kriterium | Prompten sätter ribban för `overall_score` systematiskt lågt, eller `return_risk=high` triggas för lätt av ett felaktigt villkor. |
| C — Parsningsfel | `_extract_json()` parserar AI-svaret fel vid edge cases, vilket ger låga scores eller felaktiga return_risk-värden som sparas utan att kastas. |

**Frågan som ska besvaras:** Är 35.6 / 84.6% ett rimligt utfall för den faktiska produktdatan i databasen — eller finns det ett konkret problem i pipelinen att åtgärda?

---

## Undersökningsplan

Stegen körs i ordning. Varje steg dokumenterar sin output innan nästa påbörjas.

### Steg 1 — Se 10 faktiska AnalysisResult-rader

Förstå hur data faktiskt ser ut innan vi tolkar aggregaten.

```bash
docker compose exec postgres psql -U feedpilot -d feedpilot -c "
SELECT
    ar.sku_id,
    ar.overall_score,
    ar.return_risk,
    ar.prompt_version,
    ar.total_tokens,
    ar.created_at
FROM analysis_results ar
ORDER BY ar.created_at DESC
LIMIT 10;
"
```

**Vad vi letar efter:**
- Är scores jämnt låga eller varierar de?
- Är `return_risk` alltid `high`, eller finns spridning?
- Är `prompt_version` konsekvent `2.0.0` på alla rader?
- Är `total_tokens` rimliga (~1000–3000) eller extremt låga (trunkering)?

---

### Steg 2 — Score-fördelning grupperad på return_risk

Bekräfta aggregaten och se hur `overall_score` korrelerar med `return_risk`.

```bash
docker compose exec postgres psql -U feedpilot -d feedpilot -c "
SELECT
    return_risk,
    COUNT(*)           AS antal,
    MIN(overall_score) AS min_score,
    MAX(overall_score) AS max_score,
    ROUND(AVG(overall_score), 1) AS avg_score
FROM analysis_results
WHERE overall_score IS NOT NULL
GROUP BY return_risk
ORDER BY avg_score DESC;
"
```

**Vad vi letar efter:**
- Är `return_risk=high` verkligen kopplat till låga scores, eller är det frikopplat?
- Om `high` har avg_score > 60 är det ett tecken på att `return_risk`-bedömningen inte stämmer med `overall_score` — möjligt promptproblem (Hypotes B).
- Om alla rader är `high` oavsett score är det ett starkt tecken på felaktigt kriterium.

---

### Steg 3 — Läs scoring-kriterierna i prompten

```
backend/app/prompts/versions/v2_enrichment.py
```

**Vad vi letar efter:**
- Hur definieras `overall_score`? Vilka villkor ger 0–30 vs 70–100?
- Hur definieras `return_risk=high`? Är tröskeln rimlig?
- Finns det instruktioner som systematiskt straffar produkter med tomma fält — t.ex. "om beskrivning saknas → score < 40"?
- Stämmer promptens definition med vad vi förväntar oss ska visas på dashboarden?

---

### Steg 4 — Läs 3 faktiska Product-rader med låg score

Förstå vad AI:n faktiskt fick som input.

```bash
docker compose exec postgres psql -U feedpilot -d feedpilot -c "
SELECT
    p.sku_id,
    p.title,
    p.description,
    p.category,
    p.brand,
    p.price,
    p.attributes,
    ar.overall_score,
    ar.return_risk
FROM products p
JOIN analysis_results ar ON ar.product_id = p.id
WHERE ar.overall_score IS NOT NULL
ORDER BY ar.overall_score ASC
LIMIT 3;
"
```

**Vad vi letar efter:**
- Är `title` och `description` tomma eller minimala? Då är Hypotes A trolig.
- Är produkterna rimliga e-handelsprodukter med bra data men ändå låg score? Då är Hypotes B trolig.
- Finns det produkter med rimlig data men `return_risk=high` av oklara skäl? Undersök `ar.action_items` och `ar.issues` separat för dessa.

---

### Steg 5 (vid behov) — Granska issues och action_items för låg-score-produkt

Kör endast om Steg 4 inte räcker för att avgöra Hypotes A vs B.

```bash
docker compose exec postgres psql -U feedpilot -d feedpilot -c "
SELECT
    ar.sku_id,
    ar.overall_score,
    ar.return_risk,
    ar.issues,
    ar.action_items
FROM analysis_results ar
WHERE ar.overall_score IS NOT NULL
ORDER BY ar.overall_score ASC
LIMIT 3;
"
```

**Vad vi letar efter:**
- Är `issues` och `action_items` konkreta och kopplade till faktiska produktbrister?
- Eller är de generiska/upprepade — t.ex. exakt samma text på alla produkter?
- Generiska issues är ett tecken på att AI:n inte läst produktdatan utan genererat boilerplate (Hypotes C).

---

## Definition of Done

Undersökningen är klar när dessa frågor har ett dokumenterat svar:

| Fråga | Svar krävs |
|---|---|
| Är avg_score 35.6 ett korrekt aggregat av `analysis_results`? | Ja / Nej — verifiera mot Steg 1–2 |
| Vilken hypotes (A, B eller C) förklarar siffrorna bäst? | En av A/B/C, eller kombination |
| Är produktdatan i databasen representativ för en riktig produktkatalog? | Ja / Nej — avgör om Hypotes A håller |
| Finns ett konkret fel i prompten eller pipelinen att åtgärda? | Ja (nytt ticket skapas) / Nej (dokumentera som känt beteende) |

**Om svaret är Nej på det sista:** dokumentera att siffrorna speglar testdatans kvalitet och att pipelinen fungerar korrekt. Stäng ticket.

**Om svaret är Ja:** skapa ett åtgärdsticket (FEED-073 eller senare) med exakt felbeskrivning och scope. Stäng inte detta ticket förrän åtgärdsticket är skapat.

---

## Filer som berörs (läsning, ingen ändring)

- `backend/app/prompts/versions/v2_enrichment.py` — scoring-kriterier
- `backend/app/services/enrichment_service.py` — `_extract_json()` och persistering
- PostgreSQL-tabellerna `products` och `analysis_results` via Docker psql
