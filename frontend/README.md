# FeedPilot 🚀

> AI-drivet produktdata-enrichment system för e-commerce

FeedPilot hjälper e-handlare att automatiskt berika produktdata med SEO-optimerade titlar, beskrivningar och attribut via Claude AI. Ladda upp en produktfeed som CSV eller Excel — FeedPilot analyserar, enrichar och returnerar klar data redo att skickas tillbaka till ditt PIM-system.

---

## Innehåll

- [Funktioner](#funktioner)
- [Arkitektur](#arkitektur)
- [Tech Stack](#tech-stack)
- [Kom igång](#kom-igång)
- [API-dokumentation](#api-dokumentation)
- [Frontend-sidor](#frontend-sidor)
- [Dataflöde](#dataflöde)
- [Konfiguration](#konfiguration)
- [Utveckling](#utveckling)

---

## Funktioner

- 📤 **CSV/Excel-import** med automatisk schema-detektering (Shopify, WooCommerce, generisk CSV)
- 🤖 **AI-enrichment** via Claude — titlar, beskrivningar, kategorier, attribut
- 🔍 **Semantisk sökning** med pgvector och OpenAI embeddings
- 🖼️ **Bildanalys** via Claude Vision — Visual Quality Score, attributdetektering
- ⚡ **Asynkron bulk-enrichment** med ARQ job queue och realtids-progress
- ✏️ **Inline editing** — redigera AI-förslag direkt i UI innan export
- 📊 **Enrichment-statistik** — score per produkt, return risk, quality issues
- 🔄 **PIM-export** — acceptera/avvisa förslag fält för fält, exportera som JSON

---

## Arkitektur

```
┌─────────────────────────────────────────────────────────┐
│                     Next.js 14 Frontend                  │
│         Dashboard │ Catalog │ Product Detail             │
└─────────────────────────┬───────────────────────────────┘
                          │ axios / REST
┌─────────────────────────▼───────────────────────────────┐
│                    FastAPI Backend                        │
│   api/ → services/ → repositories/ → models/            │
└──────┬──────────────────┬──────────────────┬────────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼──────┐  ┌───────▼────────┐
│ PostgreSQL  │  │     Redis     │  │  Anthropic API │
│  + pgvector │  │  ARQ Workers  │  │  + OpenAI      │
└─────────────┘  └───────────────┘  └────────────────┘
```

### Backend-principer
- `api/` — bara HTTP-hantering, ingen business logic
- `services/` — all business logic
- `repositories/` — all dataåtkomst
- `models/` — SQLAlchemy ORM
- `schemas/` — Pydantic V2 med ConfigDict
- Dependency injection via FastAPI `Depends()`

---

## Tech Stack

| Komponent | Teknologi |
|-----------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11 |
| Databas | PostgreSQL 15 + pgvector |
| Job queue | Redis 7 + ARQ |
| AI | Anthropic Claude claude-sonnet-4-6 |
| Embeddings | OpenAI text-embedding-3-small (1536 dim) |
| Container | Docker Compose (ARM64/Apple M1) |

---

## Kom igång

### Krav
- Docker Desktop
- Node.js 18+
- API-nycklar för Anthropic och OpenAI

### 1. Klona och konfigurera

```bash
git clone <repo>
cd feedpilot
```

Skapa `backend/.env`:
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://feedpilot:feedpilot@postgres:5432/feedpilot
REDIS_URL=redis://redis:6379
```

Skapa `frontend/.env.local`:
```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8010
```

### 2. Starta backend

```bash
cd feedpilot
docker compose up -d
```

Tjänster som startar:
| Tjänst | Port | Beskrivning |
|--------|------|-------------|
| API | 8010 | FastAPI backend |
| PostgreSQL | 5433 | Databas med pgvector |
| Redis | 6380 | Job queue |
| Worker | — | ARQ background worker |

Swagger-dokumentation: http://localhost:8010/docs

### 3. Starta frontend

```bash
cd frontend
npm install
npm run dev
```

Öppna: http://localhost:3000

---

## API-dokumentation

### Health & Stats
```
GET  /api/v1/health          Hälsostatus
GET  /api/v1/stats           Total, enriched, pending, failed
GET  /api/v1/catalog         Paginerad produktlista med filter
GET  /api/v1/products/{sku}  Full produktdetalj + enrichment
```

### Ingest
```
POST /api/v1/ingest/csv      Ladda upp CSV-feed
POST /api/v1/ingest/xlsx     Ladda upp Excel-feed
```

### Enrichment
```
POST /api/v1/enrich/{sku_id}     Enricha en produkt synkront
POST /api/v1/enrich/bulk         Köa bulk-enrichment → {job_id}
GET  /api/v1/jobs/{job_id}       Jobbstatus + progress_pct
```

### Bilder
```
POST /api/v1/images/analyze-url           Analysera bild via URL
POST /api/v1/images/analyze-upload/{sku}  Analysera uppladdad bild
PATCH /api/v1/products/{sku}/image        Spara image_url
```

### Varianter & Sökning
```
POST /api/v1/variants/ingest         Importera varianter
POST /api/v1/variants/enrich-all     Enricha alla varianter
GET  /api/v1/variants/{sku_id}       Hämta varianter
POST /api/v1/search/semantic         Semantisk sökning
POST /api/v1/search/ask              RAG-fråga mot produktkatalog
POST /api/v1/embeddings/embed-all    Skapa embeddings för alla
```

---

## Frontend-sidor

### Dashboard (`/dashboard`)
Editorial Hub med realtidsöversikt av katalogstatus.
- KPI-kort: Total SKUs, Enriched, Needs attention, Return risk
- Upload-modal för CSV/XLSX
- Bulk Enrich med realtids-progress polling
- Health-indikator

### Catalog (`/catalog`)
Produktlista med filter och sökning.
- Filter: All / Enriched / Needs review / Return risk
- Score-cirkel per produkt (färgkodad 0-100)
- Sökning med debounce
- Klickbar rad → Product Detail

### Product Detail (`/products/[sku_id]`)
Detaljvy för enrichment-resultat per produkt.
- **Enrichment-tabell**: FÄLT | NUVARANDE VÄRDE | AI-FÖRSLAG | CONFIDENCE | ÅTGÄRD
- **Inline editing**: klicka på AI-förslag för att redigera innan accept
- Per-fält Accept ✓ / Skip ✗
- Accept All + Export JSON + Send to PIM
- **Bildanalys**: URL eller fil-upload → Claude Vision → Visual Quality Score
- Quality Issues + Action Items
- Overall Content Score

---

## Dataflöde

### Import
```
CSV/Excel → Connector → FieldMapper → CanonicalProduct
→ normalize() → validate() → Product → PostgreSQL
```

### Enrichment
```
Product → CanonicalProduct → missing_core_fields()
→ semantic_search() pgvector → RAG-kontext
→ ask_claude() → AnalysisResult → PostgreSQL
```

### Bulk Enrichment (asynkront)
```
POST /enrich/bulk → Job skapas → ARQ köar task
→ Worker: get_unenriched() → enrichar produkt för produkt
→ job.processed++ + db.commit() efter varje produkt
→ GET /jobs/{id} → progress_pct (pollas var 3s av frontend)
```

### Schema-detektering
FeedPilot detekterar automatiskt format via `SchemaRegistry`:
- Shopify (produkter, varianter)
- WooCommerce
- Generic CSV/Excel

---

## Konfiguration

### Designsystem (Google Stitch Material Design)
```
Primary:    #072078  (mörkblå)
Background: #fcf9f5  (cream)
Sidebar:    #31302e  (kol)
Error:      #ba1a1a
Fonts:      Montserrat (headlines) + Inter (body)
Icons:      Material Symbols Outlined
```

### Tailwind-tokens
Definierade i `tailwind.config.ts`:
`primary`, `surface-container-low`, `on-surface-variant`,
`error-container`, `outline-variant` m.fl.

### AI-konfiguration
- **Prompt-versioner**: v1 (feedfixer) → v2 (enrichment) → 
  v3 (variant SEO) → v4 (bildanalys)
- **Adaptiv max_tokens**: critical=4096, high=2048, medium=1024, low=512
- **Retry-logik**: Exponential backoff (2s, 5s, 10s, 20s) vid 529 Overloaded

---

## Utveckling

### Projektstruktur
```
feedpilot/
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP-endpoints
│   │   ├── core/         # Config, DB, AI-klient
│   │   ├── ingestion/    # Connectors, FieldMapper
│   │   ├── models/       # SQLAlchemy-modeller
│   │   ├── prompts/      # Prompt-versioner
│   │   ├── repositories/ # Dataåtkomst
│   │   ├── schemas/      # Pydantic-scheman
│   │   ├── services/     # Business logic
│   │   └── workers/      # ARQ-tasks
│   ├── tests/
│   │   └── fixtures/     # test_feed.csv, test_feed.xlsx
│   └── docker-compose.yml
└── frontend/
    ├── app/
    │   ├── dashboard/
    │   ├── catalog/
    │   ├── products/[sku_id]/
    │   ├── variants/[sku_id]/
    │   └── image-analysis/
    ├── components/
    │   ├── layout/       # Sidebar, TopNav
    │   └── ui/           # Badge, SkeletonCard, ScoreGauge
    └── lib/
        ├── api.ts        # axios-klient
        └── types.ts      # TypeScript-typer
```

### Användbara kommandon

```bash
# Docker
docker compose up -d                    # Starta allt
docker compose up --build -d worker    # Rebuild worker
docker compose restart api             # Restart API
docker compose logs worker --tail=50   # Worker-loggar
docker compose logs api --tail=50      # API-loggar

# Frontend
npm run dev    # Starta dev-server (port 3000)
npm run build  # Produktionsbygge
npm run lint   # Lint

# Databas (direkt)
docker exec postgres-1 psql -U feedpilot -d feedpilot
```

### Test-data
Testfiler finns i `backend/tests/fixtures/`:
- `test_feed.csv` — generisk CSV
- `test_feed.xlsx` — Excel-format
- `test_variants.json` — variantdata

---

## Licens

Proprietär — FeedPilot © 2026