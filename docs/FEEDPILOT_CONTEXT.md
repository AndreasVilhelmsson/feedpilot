# FeedPilot — Projektkontext för ny session

## Vad är FeedPilot?
AI-drivet produktdata-enrichment system för e-commerce.
E-handlare laddar upp CSV/Excel → Claude analyserar och enrichar
varje produkt med SEO-optimerade titlar, beskrivningar, attribut → 
exporteras tillbaka till kundens PIM-system.

---

## Tech Stack

### Backend (kör på localhost:8010)
- FastAPI (Python 3.11)
- PostgreSQL 15 + pgvector (port 5433)
- Redis 7 + ARQ (async job queue, port 6380)
- Anthropic Claude claude-sonnet-4-6
- OpenAI text-embedding-3-small
- Docker Compose (api, postgres, redis, worker)

### Frontend (kör på localhost:3000)
- Next.js 14 App Router
- TypeScript + Tailwind CSS
- axios via lib/api.ts
- Material Symbols Outlined (ikoner)
- Montserrat + Inter (fonts)

---

## Projektstruktur

```
~/feedpilot-ai/feedpilot/
  backend/app/
    api/          health, analyze, ingest, embeddings, search,
                  enrich, variants, images, jobs, stats, catalog,
                  products
    core/         config, database, ai (ask_claude + retry 529)
    models/       product, embedding, analysis_result, variant,
                  job, customer_pim_config
    schemas/      canonical, product, enrich, variant, job,
                  stats, catalog
    services/     ingestion, embedding, rag, enrichment,
                  variant_enrichment, image_analysis, stats
    repositories/ product_repository (get_all, get_unenriched),
                  variant, stats
    workers/      tasks.py (enrich_bulk_task, embed_all_task)
    prompts/      v1-v4 prompt versions

  frontend/app/
    dashboard/page.tsx      ✅ Klar + live data
    catalog/page.tsx        ✅ Klar + live data
    products/[sku_id]/      ✅ Klar + live data + bildanalys
    variants/[sku_id]/      ❌ Tom
    image-analysis/         ❌ Tom
  
  frontend/components/
    layout/Sidebar.tsx      ✅ Klar
    layout/TopNav.tsx       ✅ Klar
    ui/Badge, SkeletonCard, ScoreGauge, UploadModal
  
  frontend/lib/
    api.ts      axios mot NEXT_PUBLIC_BACKEND_URL
    types.ts    StatsResponse, CatalogProduct, ProductDetail,
                EnrichmentDetail, ImageAnalysisResult, JobResponse
```

---

## Backend API-endpoints

```
GET  /api/v1/health
POST /api/v1/ingest/csv
POST /api/v1/ingest/xlsx
POST /api/v1/embeddings/embed-all
POST /api/v1/search/semantic
POST /api/v1/search/ask
POST /api/v1/enrich/{sku_id}
POST /api/v1/enrich/bulk          → {job_id, status}
GET  /api/v1/jobs/{job_id}        → progress_pct, ETA
POST /api/v1/variants/ingest
POST /api/v1/variants/enrich-all
GET  /api/v1/variants/{sku_id}
POST /api/v1/images/analyze-url
POST /api/v1/images/analyze-upload/{sku_id}
GET  /api/v1/stats                → total, enriched, pending, failed
GET  /api/v1/catalog              → paginerad produktlista
GET  /api/v1/products/{sku_id}    → full produkt + enrichment
POST /api/v1/products/{sku_id}/enrich
PATCH /api/v1/products/{sku_id}/image → spara image_url
```

---

## Designsystem (Google Stitch)

```
Primary:    #072078
Background: #fcf9f5
Sidebar:    #31302e
Error:      #ba1a1a
Fonts:      Montserrat (headlines) + Inter (body)
Icons:      Material Symbols Outlined
```

Tailwind-tokens i tailwind.config.ts:
`surface-container-low`, `primary`, `error`, `on-surface-variant` etc.

---

## Vad som är byggt och fungerar

### Dashboard (app/dashboard/page.tsx) ✅
- KPI-kort: Total SKUs, Enriched, Needs attention, Return risk
  → Live data från GET /api/v1/stats
- Upload-modal: CSV/XLSX → POST /api/v1/ingest/csv|xlsx
  → Refetchar stats efter lyckad upload
- Enrich all-knapp: POST /api/v1/enrich/bulk → polling var 3s
  → Knappen visar "Processing... X%"
- Health-indikator: GET /api/v1/health → grön/röd prick

### Mock-data på Dashboard (EJ kopplat till backend än):
- Feed Quality Score (73, 82%, 71%, 64%) — hårdkodat
- AI Confidence Trend (stapeldiagram) — hårdkodat
- Enrichment by Category (Electronics 423 osv) — hårdkodat
- Recent Activity (SKU-4821 osv) — hårdkodat

### Catalog (app/catalog/page.tsx) ✅
- Tabell: SKU, Produkt, Status-badge, Score-cirkel, Actions
- Filter-pills: All / Enriched / Needs review / Return risk
- Sökning med 300ms debounce
- Paginering: 10 per sida
- Klick på rad → /products/{sku_id}
- Live data från GET /api/v1/catalog

### Product Detail (app/products/[sku_id]/page.tsx) ✅
- Header: Back, SKU, produkttitel, score-cirkel, Re-enrich-knapp
- Enrichment-tabell: FÄLT | NUVARANDE VÄRDE | AI-FÖRSLAG | 
  CONFIDENCE | ÅTGÄRD
  - Inline editing: klicka på AI-förslag för att redigera
  - Accept ✓ / Skip ✗ per fält
  - Accept all + Export JSON + Send to PIM
- Quality Issues + Action Items
- Overall Content Score längst ner
- Product Image-panel (höger):
  - URL-input eller fil-upload
  - Loading overlay med spinner + progress bar under analys
  - Claude Vision returnerar Visual Quality %, attribut, taggar
  - Sparar image_url till databasen via PATCH
- Return Risk, Product Info, Feed Info, Attributes (höger)

### Kända buggar att fixa:
1. **Click propagation i enrichment-tabellen** — klick på 
   AI-FÖRSLAG-cellen för inline editing navigerar bort från sidan.
   Fix: e.stopPropagation() på td onClick, Accept/Skip-knappar.

2. **Dashboard mock-data** — Feed Quality Score, AI Confidence 
   Trend, Enrichment by Category, Recent Activity är hårdkodat.
   Behöver tre nya endpoints:
   GET /api/v1/stats/recent     → senaste AnalysisResult
   GET /api/v1/stats/categories → produkter per category
   GET /api/v1/stats/quality    → genomsnitt overall_score

---

## Viktiga arkitekturbeslut

- **Canonical mapping**: CSV/Excel → FieldMapper → CanonicalProduct
  Hanterar Shopify, WooCommerce, generic CSV automatiskt
- **ARQ worker**: Kör som separat Docker-container
  enrich_bulk_task använder repo.get_unenriched() (ej get_all)
- **Retry-logik**: ask_claude() har exponential backoff vid 529
  (OverloadedError) via anthropic.APIStatusError
- **CORS**: CORSMiddleware tillåter localhost:3000

---

## Workflow

```
1. Du (Claude.ai) — prompt-arkitekt + visuell reviewer via Chrome MCP
2. Claude Code — kör i terminalen, skriver koden
3. ChatGPT — code review + pedagogisk analys
```

### ChatGPT-prompt för code review:
```
Du är code reviewer för FeedPilot — Next.js 14 + FastAPI.
Granska: arkitektur, TypeScript-typer, Tailwind-användning,
API-koppling via axios/lib/api.ts, error handling.
Svara med: Förklaring → Best practices → Förbättringsförslag → 
Frågor till nästa iteration.
```

---

## Nästa steg (prioriterat)

### Imorgon — Fix 1 (5 min):
Fixa click propagation i enrichment-tabellen:
```
I app/products/[sku_id]/page.tsx, EnrichmentTableRow:
Lägg till e.stopPropagation() på:
- <td onClick> som startar inline editing
- Accept ✓ knapp
- Skip ✗ knapp
```

### Imorgon — Fix 2 (30 min):
Koppla Dashboard mock-data till backend:
```
Bygg GET /api/v1/stats/recent, /categories, /quality
Koppla dashboard/page.tsx mot dessa endpoints
```

### Kommande funktioner:
- Variants-sidan (app/variants/[sku_id]/page.tsx)
- Image Analysis-sidan (dedikerad vy)
- Export-knappen (CSV med enrichad data)
- "Batch Processing" — byt namn på Dashboard-fliken
- Bulk field editor (regler per fält/kategori)

---

## Docker-kommandon

```bash
# Starta allt
cd ~/feedpilot-ai/feedpilot
docker compose up -d

# Rebuild specifik container
docker compose up --build -d worker

# Loggar
docker compose logs worker --tail=50
docker compose logs api --tail=50

# Restart API
docker compose restart api
```

## Starta frontend
```bash
cd ~/feedpilot-ai/feedpilot/frontend
npm run dev
```
