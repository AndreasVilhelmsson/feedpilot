# FeedPilot

AI-powered product data enrichment platform. Upload e-commerce product feeds, score content quality, detect return risk, and enrich product data using Claude/OpenAI — all from a single dashboard.

---

## Architecture

```
feedpilot/
├── backend/          # FastAPI + Python
├── frontend/         # Next.js 14 + TypeScript
├── docker-compose.yml
└── .env.example
```

**Services (docker-compose)**

| Service    | Image                      | Port        | Purpose                          |
|------------|----------------------------|-------------|----------------------------------|
| `backend`  | Custom Dockerfile          | 8010 → 8000 | FastAPI + uvicorn                |
| `postgres` | pgvector/pgvector:pg15     | 5433 → 5432 | PostgreSQL with pgvector         |
| `redis`    | redis:7                    | 6380 → 6379 | Job queue                        |
| `worker`   | Custom Dockerfile          | —           | ARQ async worker                 |

---

## Quick start

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY and/or OPENAI_API_KEY

docker compose up --build
```

- Backend API: http://localhost:8010
- Frontend: http://localhost:3000 (run separately, see below)
- API docs: http://localhost:8010/docs

### Frontend (local dev)

```bash
cd frontend
cp .env.local.example .env.local   # set NEXT_PUBLIC_BACKEND_URL=http://localhost:8010
npm install
npm run dev
```

---

## Backend

**Stack:** FastAPI · SQLAlchemy · PostgreSQL + pgvector · Redis / ARQ · Anthropic SDK · OpenAI SDK

### API — `/api/v1/`

| Method   | Path                              | Description                        |
|----------|-----------------------------------|------------------------------------|
| `GET`    | `/products/{sku_id}`              | Full product detail + enrichment   |
| `POST`   | `/products/{sku_id}/enrich`       | Trigger single-product enrichment  |
| `PATCH`  | `/products/{sku_id}/image`        | Save image URL                     |
| `GET`    | `/catalog`                        | Paginated catalog with filters     |
| `POST`   | `/enrich/{sku_id}`                | Enrich single product              |
| `POST`   | `/enrich/bulk`                    | Queue bulk enrichment job          |
| `POST`   | `/ingest/csv`                     | Import CSV feed                    |
| `POST`   | `/ingest/xlsx`                    | Import XLSX feed                   |
| `GET`    | `/jobs/{job_id}`                  | Async job status                   |
| `GET`    | `/variants/{sku_id}`              | Product variants                   |
| `GET`    | `/stats`                          | Enrichment statistics              |
| `POST`   | `/images/analyze-url`             | Analyze product image by URL       |
| `POST`   | `/images/analyze-upload/{sku_id}` | Analyze uploaded product image     |
| `GET`    | `/health`                         | Health check                       |

### Feed sources supported

Auto-detected on ingest: **Shopify**, **WooCommerce**, **Google Shopping**, **Akeneo**

### Database models

| Model            | Purpose                                      |
|------------------|----------------------------------------------|
| `Product`        | Core product record + image URL              |
| `AnalysisResult` | Enrichment scores, issues, enriched fields   |
| `Embedding`      | Vector embeddings for similarity search      |
| `Variant`        | SKU variants (color, size, SEO fields)       |
| `Job`            | Async job tracking                           |
| `CustomerPimConfig` | PIM integration configuration            |

### Environment variables (backend)

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=postgresql://feedpilot:feedpilot@postgres:5432/feedpilot
REDIS_HOST=redis
REDIS_PORT=6379
```

---

## Frontend

**Stack:** Next.js 14 (App Router) · React 18 · TypeScript 5 · Tailwind CSS · Axios

### Pages

| Route                     | Purpose                                          |
|---------------------------|--------------------------------------------------|
| `/`                       | Landing / home                                   |
| `/dashboard`              | Enrichment overview and stats                    |
| `/catalog`                | Paginated product catalog with filters           |
| `/products/[sku_id]`      | Product detail, inline enrichment review, image analysis |
| `/variants/[sku_id]`      | Variant detail and SEO enrichment                |
| `/image-analysis`         | Standalone image analysis tool                   |

### Product detail page features

- Enrichment table with **inline editing** of AI suggestions (click to edit, Enter/Esc)
- Accept / reject per field — accepted values flow to Export JSON and Send to PIM
- Image panel with 3 states: upload/URL → preview → AI analysis results
- Return risk badge, content quality score, action items, quality issues
- Re-enrich button to trigger a fresh enrichment run

### Environment variables (frontend)

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8010
```

---

## Key dependencies

**Backend**

| Package       | Purpose               |
|---------------|-----------------------|
| fastapi       | Web framework         |
| sqlalchemy    | ORM                   |
| pgvector      | Vector search         |
| pydantic v2   | Schema validation     |
| anthropic     | Claude API client     |
| openai        | OpenAI API client     |
| arq           | Async job queue       |
| openpyxl      | Excel feed parsing    |

**Frontend**

| Package  | Purpose         |
|----------|-----------------|
| next 14  | React framework |
| axios    | HTTP client     |
| tailwindcss | Styling      |
