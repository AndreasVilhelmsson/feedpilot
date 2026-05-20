# FEED-073 — Preflight-modal innan bulk enrichment

**Sprint:** Sprint 2
**Prioritet:** Hög
**Risk:** Low — enbart frontend, inga backend-ändringar
**Skapad:** 2026-05-15

---

## Problem

`handleEnrichAll()` i `dashboard/page.tsx` (rad 258–268) kör idag:

```
klick → setBulkStatus("processing") → POST /enrich/bulk → kö jobb
```

Användaren ser ingen kostnadsbedömning, inget produktantal och ingen möjlighet att avbryta. Backend-endpointen `POST /api/v1/enrich/preflight` finns och returnerar exakt den information som behövs, men den anropas aldrig från frontend.

`PreflightResponse` saknas också helt i `frontend/lib/types.ts` — `grep "PreflightResponse"` ger noll träffar.

---

## Mål och användarflöde

```
Klick "Enrich all"
  → POST /api/v1/enrich/preflight   (knapp visar "Beräknar...")
  → PreflightModal öppnas med:
      • Antal produkter att enricha
      • Estimerade tokens (input + output)
      • Estimerad kostnad i USD
  → "Bekräfta" → POST /api/v1/enrich/bulk → jobb köas
  → Modal stängs → progressbar visas under "Enrich all"-knappen
      • Pollar GET /api/v1/jobs/{job_id} var 3s (befintlig logik)
      • Visar: [████████░░░░] 45% — 12 / 26 produkter klara
      • Animerad fill: width = progress_pct %
  → Vid completed: progressbar ersätts av grön "✓ Klart — 26/26 enrichade"
  → Vid failed:    progressbar ersätts av röd "Fel — X produkter misslyckades"
  → "Avbryt" i modal → modal stängs, state återställs till idle
```

Inga ändringar på backend — `POST /api/v1/enrich/preflight` och `POST /api/v1/enrich/bulk` är opåverkade.

---

## Berörda filer

| # | Fil | Lager | Ändring |
|---|---|---|---|
| 1 | `frontend/__tests__/dashboard.test.tsx` | Test | Lägg till 4 tester (befintlig fil) |
| 2 | `frontend/lib/types.ts` | Frontend | Lägg till `PreflightResponse`-interface |
| 3 | `frontend/components/ui/PreflightModal.tsx` | Frontend | **Ny fil** — confirmation modal |
| 4 | `frontend/app/dashboard/page.tsx` | Frontend | Uppdatera `handleEnrichAll()`, lägg till preflight-state, importera och wire modal |

**Inga backend-filer rörs.**

---

## Teknisk plan

### `frontend/lib/types.ts`

Nytt interface som matchar `PreflightResponse` i `backend/app/schemas/enrich.py` exakt:

```typescript
export interface PreflightResponse {
  product_count: number
  estimated_ai_calls: number
  estimated_input_tokens: number
  estimated_output_tokens: number
  estimated_total_tokens: number
  estimated_cost_usd: number
  fields_to_enrich: Record<string, number>
  tool_plan: Record<string, boolean>
  requires_confirmation: boolean
}
```

---

### `frontend/components/ui/PreflightModal.tsx`

Ny komponent. Följer samma mönster som `UploadModal.tsx` (props: `isOpen`, `onClose`, callback).

Props:

```typescript
interface PreflightModalProps {
  isOpen: boolean
  preflight: PreflightResponse | null
  onConfirm: () => void
  onCancel: () => void
}
```

Innehåll i modal:
- Rubrik: "Bekräfta enrichment"
- Tre nyckeltal: `product_count` produkter, `estimated_total_tokens` tokens, `$estimated_cost_usd`
- Knapp "Bekräfta" → anropar `onConfirm()`
- Knapp "Avbryt" → anropar `onCancel()`
- Visas inte (`return null`) när `isOpen=false` eller `preflight=null`

Design: Material Design 3-tokens som resten av UI:t. Knapp-struktur speglar `UploadModal`.

---

### `frontend/app/dashboard/page.tsx`

**Ny state:**

```typescript
const [preflight, setPreflight] = useState<PreflightResponse | null>(null)
const [showPreflightModal, setShowPreflightModal] = useState(false)
const [bulkProcessed, setBulkProcessed] = useState(0)
const [bulkTotal, setBulkTotal] = useState(0)
const [bulkFailed, setBulkFailed] = useState(0)
```

**`BulkStatus` utökas** med `"preflight"` för laddningsfasen:

```typescript
type BulkStatus = "idle" | "preflight" | "processing" | "complete" | "failed"
```

`enrichButtonLabel()` uppdateras med nytt case:
```typescript
if (status === "preflight") return "Beräknar..."
```

**Polling-`useEffect`** utökas för att fånga `processed`, `total` och `failed` från `JobResponse`
(fälten är optional i `JobResponse` — använd `?? 0` som fallback):

```typescript
setBulkProgress(data.progress_pct)
setBulkProcessed(data.processed ?? 0)
setBulkTotal(data.total ?? 0)
setBulkFailed(data.failed ?? 0)
```

**Ny inline-komponent `EnrichProgress`** i `page.tsx` — visas under Hero-sektionens knappar
när `bulkStatus === "processing" || "complete" || "failed"`:

```
processing: [████████░░░░] 45% — 12 / 26 produkter klara    (blå fill, animerad)
complete:   ✓ Klart — 26/26 enrichade                        (grön text)
failed:     Fel — X produkter misslyckades                   (röd text)
```

Fill-bredd: `style={{ width: `${bulkProgress}%` }}` — samma mönster som progress-baren
i `processing/page.tsx`.

**`handleEnrichAll()` ersätts** med tvåstegsflöde:

```typescript
async function handleEnrichAll() {
  if (bulkStatus === "preflight" || bulkStatus === "processing") return
  setBulkStatus("preflight")
  try {
    const { data } = await api.post<PreflightResponse>("/api/v1/enrich/preflight", { limit: 10 })
    setPreflight(data)
    setShowPreflightModal(true)
  } catch {
    setBulkStatus("failed")
  }
}

async function handleConfirmEnrich() {
  setShowPreflightModal(false)
  setBulkStatus("processing")
  setBulkProgress(0)
  try {
    const { data } = await api.post<BulkEnrichResponse>("/api/v1/enrich/bulk", { limit: 10 })
    setBulkJobId(data.job_id)
  } catch {
    setBulkStatus("failed")
  }
}

function handleCancelEnrich() {
  setShowPreflightModal(false)
  setPreflight(null)
  setBulkStatus("idle")
}
```

**Modal wiras** i JSX under befintlig `UploadModal`:

```tsx
<PreflightModal
  isOpen={showPreflightModal}
  preflight={preflight}
  onConfirm={handleConfirmEnrich}
  onCancel={handleCancelEnrich}
/>
```

---

## Acceptance criteria

| # | Krav |
|---|---|
| AC-1 | Klick på "Enrich all" anropar `POST /api/v1/enrich/preflight` — inte `/enrich/bulk` direkt |
| AC-2 | Knappen visar "Beräknar..." under preflight-anropet |
| AC-3 | Modalen öppnas med korrekt `product_count`, `estimated_total_tokens` och `estimated_cost_usd` från preflight-svaret |
| AC-4 | Klick "Bekräfta" i modalen anropar `POST /api/v1/enrich/bulk` och startar polling |
| AC-5 | Klick "Avbryt" i modalen anropar inte `/enrich/bulk` och återställer knappen till idle |
| AC-6 | Knappen är inaktiverad (`disabled`) under både `"preflight"` och `"processing"` |
| AC-7 | Progressbar visas under Hero-knapparna under `"processing"` med korrekt fill-bredd från `progress_pct` |
| AC-8 | Progressbar-texten visar `processed` / `total` produkter från job-polling |
| AC-9 | Vid `completed`: progressbar ersätts av grön "✓ Klart — N/N enrichade" med faktiskt `processed`-värde |
| AC-10 | Vid `failed`: progressbar ersätts av röd "Fel — X produkter misslyckades" med faktiskt `failed`-värde |
| AC-11 | `cd frontend && npm run lint && npm test -- --runInBand` passerar utan fel |

---

## TDD-plan

Alla 4 tester läggs till i den **befintliga** `frontend/__tests__/dashboard.test.tsx`.
Testerna skrivs **innan** `PreflightModal.tsx` och `page.tsx` ändras.

```
test: "Enrich all" anropar preflight-endpoint, inte bulk direkt
  → klicka "Enrich all"
  → verifiera att api.post kallades med "/api/v1/enrich/preflight"
  → verifiera att api.post INTE kallades med "/api/v1/enrich/bulk"

test: PreflightModal visas med korrekt data efter preflight-svar
  → mocka preflight-svar: product_count=5, estimated_cost_usd=0.0225, estimated_total_tokens=8500
  → klicka "Enrich all"
  → verifiera att modalen innehåller "5 produkter", "8500" och "0.0225"

test: klick Bekräfta anropar /enrich/bulk
  → preflight-svar mocked, modal visas
  → klicka "Bekräfta"
  → verifiera att api.post kallades med "/api/v1/enrich/bulk"

test: klick Avbryt anropar inte /enrich/bulk
  → preflight-svar mocked, modal visas
  → klicka "Avbryt"
  → verifiera att api.post INTE kallades med "/api/v1/enrich/bulk"
  → verifiera att knappen återgår till "Enrich all"-label

test: progressbar visas med korrekt fill och räknare under processing
  → mocka job-polling: progress_pct=45, processed=12, total=26
  → verifiera att progressbar-elementet har width="45%"
  → verifiera att texten innehåller "12" och "26"

test: completed-state visar grön bekräftelse med korrekt antal
  → mocka job-polling: status="completed", processed=26, total=26
  → verifiera att "✓ Klart" och "26/26" visas
  → verifiera att progressbar-elementet inte visas

test: failed-state visar röd felbeskrivning med antal misslyckade
  → mocka job-polling: status="failed", failed=3
  → verifiera att "Fel" och "3" visas i röd text
```

---

## Definition of Done

- [ ] Tester skrivna och **röda** innan implementation
- [ ] `frontend/lib/types.ts` — `PreflightResponse` tillagd
- [ ] `frontend/components/ui/PreflightModal.tsx` — ny komponent skapad
- [ ] `frontend/app/dashboard/page.tsx` — `handleEnrichAll()` ersatt, state utökat, modal wired
- [ ] Knappen visar "Beräknar..." under preflight och är disabled under både preflight och processing
- [ ] Progressbar visas under Hero-knapparna under processing med animerad fill
- [ ] Polling fångar `processed`, `total` och `failed` från `JobResponse`
- [ ] Completed-state: grön text "✓ Klart — N/N enrichade"
- [ ] Failed-state: röd text "Fel — X produkter misslyckades"
- [ ] `cd frontend && npm run lint && npm test -- --runInBand` — grönt
- [ ] `docs/STATUS.md` och `docs/BACKLOG.md` uppdaterade
- [ ] Ingen logik i `PreflightModal` utöver rendering — all state lever i `DashboardPage`
