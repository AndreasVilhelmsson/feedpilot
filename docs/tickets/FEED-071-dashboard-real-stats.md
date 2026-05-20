# FEED-071 — Dashboard: riktiga nyckeltal (avg enrichment-score)

**Sprint:** Sprint 2
**Prioritet:** Medium
**Risk:** Low
**Skapad:** 2026-05-14

---

## Problem

Dashboardens KPI-rad hämtar redan riktiga värden från `GET /api/v1/stats` för
`total_products`, `enriched`, `needs_attention` och `return_risk_high`.

En nyckel saknas helt i pipeline-kedjan:

| Nyckeltal | Status | Var problemet sitter |
|---|---|---|
| Antal produkter (`total_products`) | ✅ Riktigt | — |
| Antal enrichade (`enriched`) | ✅ Riktigt | — |
| Genomsnittlig enrichment-score (`avg_enrichment_score`) | ❌ Saknas | Inte i repo / service / schema / frontend-typ |
| FeedQualityScore (cirkeldiagram) | ❌ Hårdkodat | `page.tsx` rad 87–88: `const overall = 73` |

Konkret: `FeedQualityScore`-komponenten i `page.tsx` innehåller hårdkodade
värden (`overall = 73`, completeness = 82, accuracy = 71, richness = 64) med
kommentaren *"chart data removed until backend aggregation endpoints exist"*.
Ingen ände av pipeline — `StatsRepository`, `StatsService`, `schemas/stats.py`,
`lib/types.ts` — exponerar ett genomsnitts-score.

---

## Mål

Lägga till `avg_enrichment_score` (genomsnitt av `overall_score` från senaste
`AnalysisResult` per produkt) i hela stats-kedjan, och koppla
`FeedQualityScore`-diagrammets `overall`-värde till det riktiga talet.

Sub-scores (Completeness / Accuracy / Richness) finns inte i databasen och
hanteras **inte** i denna ticket — de döljs eller ersätts med ett meddelande
tills ett separat aggregerings-ticket löser dem.

---

## Berörda filer

| # | Fil | Lager | Ändring |
|---|---|---|---|
| 1 | `backend/tests/test_stats_repository.py` | Test | **Ny fil** — TDD-tester för `get_avg_enrichment_score()` |
| 2 | `backend/tests/test_stats_service.py` | Test | **Ny fil** — TDD-tester för `StatsService.get_stats()` med nytt fält |
| 3 | `backend/app/repositories/stats_repository.py` | Repository | Lägg till `get_avg_enrichment_score(db)` |
| 4 | `backend/app/schemas/stats.py` | Schema | Lägg till `avg_enrichment_score: float \| None` |
| 5 | `backend/app/services/stats_service.py` | Service | Anropa nytt repo-metod, inkludera i `StatsResponse` |
| 6 | `frontend/lib/types.ts` | Frontend | Lägg till `avg_enrichment_score: number \| null` i `StatsResponse` |
| 7 | `frontend/app/dashboard/page.tsx` | Frontend | Ersätt hårdkodat `overall = 73` med `stats.avg_enrichment_score`; dölj sub-scores |

**Inga andra filer rörs.**

---

## Teknisk plan

### Backend

#### Repository — `stats_repository.py`

Ny metod `get_avg_enrichment_score(db: Session) -> float | None`:

```sql
-- Semantik (SQLAlchemy-ekvivalent)
SELECT ROUND(AVG(ar.overall_score), 1)
FROM   analysis_results ar
JOIN  (
    SELECT   product_id, MAX(created_at) AS latest_created_at
    FROM     analysis_results
    GROUP BY product_id
) sub ON ar.product_id = sub.product_id
     AND ar.created_at = sub.latest_created_at
WHERE  ar.overall_score IS NOT NULL
```

- `MAX(created_at)` används för att identifiera senaste körning per produkt —
  semantiskt korrekt eftersom `created_at` speglar när analysen gjordes.
  (`id` är auto-increment och sammanfaller normalt, men `created_at` är
  den kanoniska tidsstämpeln för ordning i denna modell.)
- Returnerar `None` om inga enrichade produkter finns (tom katalog).
- JOIN-mönstret med `(product_id, MAX(created_at))` skiljer sig från
  befintliga metoder som joinar på `MAX(id)`; kommentera detta i koden.

#### Schema — `schemas/stats.py`

```python
avg_enrichment_score: float | None = Field(
    default=None,
    description="Average overall_score across latest AnalysisResult per product."
)
```

Nullable — undviker att API:et kraschar mot en tom katalog.

#### Service — `stats_service.py`

Anrop läggs till i `get_stats()` direkt efter befintliga repo-anrop:

```python
avg_score = self._repo.get_avg_enrichment_score(db)
```

Skickas vidare som `avg_enrichment_score=avg_score` i `StatsResponse(...)`.

#### API route — `api/stats.py`

Ingen förändring krävs. Routen delegerar till service och returnerar
`StatsResponse` — Pydantic serialiserar det nya fältet automatiskt.

---

### Frontend

#### `lib/types.ts`

```typescript
export interface StatsResponse {
  total_products: number
  enriched: number
  pending: number
  failed: number
  needs_attention: number
  return_risk_high: number
  enrichment_rate: number
  avg_enrichment_score: number | null   // ← nytt
}
```

#### `app/dashboard/page.tsx`

`FeedQualityScore`-komponenten (rad 86–125) görs om från ren presentationskomponent
till att ta emot `score: number | null` som prop:

```tsx
function FeedQualityScore({ score }: { score: number | null }) {
  const overall = score ?? 0
  // circumference-logik oförändrad
}
```

- Hårdkodad `const overall = 73` tas bort.
- Sub-scores (completeness/accuracy/richness) döljs med en placeholder-text
  *"Detaljerade sub-scores tillkommer"* tills backend exponerar dem.
- Anropet i JSX uppdateras: `<FeedQualityScore score={stats?.avg_enrichment_score ?? null} />`
- Skeleton visas under `statsLoading`.

---

## Acceptance criteria

Alla krav skall vara automatiskt testbara.

| # | Krav |
|---|---|
| AC-1 | `GET /api/v1/stats` returnerar fältet `avg_enrichment_score` (float eller null) |
| AC-2 | Med 0 enrichade produkter returneras `avg_enrichment_score: null` |
| AC-3 | Med N enrichade produkter returneras korrekt medelvärde av deras senaste `overall_score`, avrundat till 1 decimal |
| AC-4 | Endast den **senaste** `AnalysisResult` per produkt räknas in i medelvärdet |
| AC-5 | Cirkeldiagrammets `overall`-värde i dashboarden matchar `avg_enrichment_score` från API:et |
| AC-6 | Hårdkodad `const overall = 73` finns inte kvar i `page.tsx` |
| AC-7 | `docker compose exec backend pytest tests/` passerar utan fel |
| AC-8 | `cd frontend && npm run lint && npm test -- --runInBand` passerar utan fel |

---

## TDD-plan

Testerna skrivs **innan** implementation-filerna ändras.

### Fil 1 (ny): `backend/tests/test_stats_repository.py`

```
test_get_avg_enrichment_score_empty_catalog
  → inga produkter → returnerar None

test_get_avg_enrichment_score_single_product
  → 1 produkt, 1 AnalysisResult med overall_score=80 → returnerar 80.0

test_get_avg_enrichment_score_multiple_products
  → 3 produkter med score 60, 70, 80 → returnerar 70.0

test_get_avg_enrichment_score_uses_latest_only
  → 1 produkt, 2 AnalysisResults (score=40 gammal, score=90 ny)
  → returnerar 90.0 (inte 65.0)

test_get_avg_enrichment_score_excludes_null_scores
  → 2 produkter: en med score=80, en med score=None (misslyckad enrichment)
  → returnerar 80.0 (None räknas inte in)
```

### Fil 2 (ny): `backend/tests/test_stats_service.py`

```
test_get_stats_includes_avg_enrichment_score
  → mockar repo, bekräftar att StatsResponse innehåller avg_enrichment_score

test_get_stats_avg_score_is_none_when_no_enriched
  → repo.get_avg_enrichment_score returnerar None
  → StatsResponse.avg_enrichment_score == None

test_get_stats_passes_avg_score_from_repo_unchanged
  → repo returnerar 73.4
  → StatsResponse.avg_enrichment_score == 73.4
```

### Frontend — befintlig fil: `frontend/__tests__/dashboard.test.tsx`

Testerna läggs till i den **befintliga** testfilen (inte en ny fil).

```
test: FeedQualityScore renders real score from prop
  → score=73 → cirkeldiagrammet visar "73"

test: FeedQualityScore renders 0 when score is null
  → score=null → cirkeldiagrammet visar "0"

test: DashboardPage passes avg_enrichment_score to FeedQualityScore
  → mockar api.get('/api/v1/stats') med avg_enrichment_score=65
  → FeedQualityScore visar "65"
```

---

## Definition of Done

- [ ] `test_stats_repository.py` skriven och **röd** innan repo-ändringar
- [ ] `test_stats_service.py` skriven och **röd** innan service-ändringar
- [ ] `stats_repository.py` — `get_avg_enrichment_score()` tillagd
- [ ] `schemas/stats.py` — `avg_enrichment_score: float | None` tillagd
- [ ] `stats_service.py` — anropar repo, inkluderar i `StatsResponse`
- [ ] `lib/types.ts` — `avg_enrichment_score: number | null` tillagd
- [ ] `page.tsx` — hårdkodat `overall = 73` borttaget, prop kopplad till API-svar
- [ ] `docker compose exec backend pytest tests/` — grönt
- [ ] `cd frontend && npm run lint && npm test -- --runInBand` — grönt
- [ ] `docs/STATUS.md` och `docs/BACKLOG.md` uppdaterade
- [ ] Ingen logik i API-lagret, inga direkta DB-anrop från service
