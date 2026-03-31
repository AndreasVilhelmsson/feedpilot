# FeedPilot — Arkitektur

## Systemöversikt

```
Internet
    ↓
Load Balancer (SSL)
    ↓
FastAPI (Cloud Run)    ←→    Next.js (Vercel/Cloud Run)
    ↓                               ↓
ARQ Worker (Cloud Run)       Browser
    ↓
Redis (Memorystore)
    ↓
PostgreSQL + pgvector (Cloud SQL)
    ↓
Cloud Storage (bilder, CSV-uploads)
```

Komponentflöde:
```
FastAPI  → Tar emot requests, validerar med Pydantic,
           köar jobb via ARQ, svarar direkt med job_id

ARQ      → Python async task queue byggd på Redis
           Kör async def-funktioner som bakgrundsjobb
           Inbyggd retry, timeout, scheduling

Redis    → Enkel lista med jobb-payloads
           ARQ läser och skriver direkt

PostgreSQL → Appdata + job status-tabell
             Worker uppdaterar progress löpande

Worker   → Separat process, kör samma kod som API
           async def enrich_bulk_task(ctx, job_id)
           Skalbar horisontellt (flera workers)
```

---

## Varför async (FastAPI + ARQ)?

Claude API tar 3–8 sekunder per anrop. Med sync blockeras hela processen:

```python
# Synkront — BLOCKERAR i 4 sekunder
def enrich_product(sku_id):
    result = claude_api.call(...)
    return result

# Asynkront — väntar men blockerar inte
async def enrich_product(sku_id):
    result = await claude_api.call(...)
    return result
```

Med async kan en worker köra 50 parallella Claude-anrop simultant.
Se ADR-003 för fullständig jämförelse mot Celery + RabbitMQ.

---

## Queue-design

### Nuläge (en kö för allt)

Problem: En stor ingest-job kan blockera alla enrichment-jobb.

```
Redis Queue (en kö)
  enrich_bulk_task
  embed_all_task
```

### Förbättring (FEED-025): Separata köer

```
feedpilot:ai (långsam)        feedpilot:data (snabb)
  enrich_task                   ingest_task
  embed_task                    embed_task
  Worker AI, max_jobs=5         Worker Data, max_jobs=20
```

Implementering:
```python
class AIWorkerSettings:
    functions = [enrich_bulk_task]
    queue_name = "feedpilot:ai"
    max_jobs = 5

class DataWorkerSettings:
    functions = [embed_all_task, ingest_task]
    queue_name = "feedpilot:data"
    max_jobs = 20
```

---

## Multi-tenant schema isolation

Strategi: Separat PostgreSQL-schema per kund (istället för shared tables med tenant_id).

Fördelar:
- Stark dataisolering utan applikationslogik
- Enkelt att migrera en kund till egen DB
- pgvector-index per kund (bättre relevans)

```python
# models/tenant.py
class Tenant(Base):
    __tablename__ = "tenants"
    id          = Column(String, primary_key=True)
    name        = Column(String)
    schema_name = Column(String, unique=True)
    api_key     = Column(String, unique=True)
    created_at  = Column(DateTime)
    plan        = Column(String)
    usage_tokens = Column(Integer, default=0)

# core/tenant.py
def create_tenant_schema(schema_name: str, db: Session):
    db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
    db.execute(text(f"""
        CREATE TABLE {schema_name}.products (
            LIKE public.products INCLUDING ALL
        )
    """))
    db.commit()

def get_tenant_db(tenant_id: str, db: Session):
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    db.execute(text(f"SET search_path = {tenant.schema_name}"))
    return db
```

---

## GCP Production-arkitektur

```
Internet
    ↓
Cloud Load Balancer (SSL-terminering)
    ↓
Cloud Run — api (FastAPI)
Cloud Run — worker (ARQ)
    ↓
Cloud SQL — PostgreSQL 15 + pgvector
  (hanterad DB, automatiska backups, point-in-time recovery)
    ↓
Cloud Memorystore — Redis
    ↓
Cloud Storage — produktbilder + CSV-uploads
    ↓
Secret Manager — API-nycklar, DB-lösenord
    ↓
Cloud Monitoring + Logging
    ↓
Sentry — application errors
```

Uppskattad månadskostnad:
- Cloud Run (api + worker): ~$20
- Cloud SQL (db-f1-micro): ~$15
- Cloud Memorystore (1 GB): ~$25
- Cloud Storage (10 GB): ~$0.20
- Secret Manager: ~$0.06
- **Total: ~$60/månad**

DB-migrering från container till Cloud SQL: ändra `DATABASE_URL` i env → kör `alembic upgrade head` → klart.

---

## Retry-strategi för Claude API

```python
# FEED-026: Exponential backoff
@app.task(bind=True, max_retries=3)
async def enrich_bulk_task(ctx, job_id):
    for product in products:
        try:
            result = await ask_claude(...)
            job.processed += 1
        except RateLimitError as exc:
            await asyncio.sleep([10, 30, 60, 120][attempt])
            raise  # ARQ requeues
        except Exception as exc:
            job.failed += 1
            continue  # Pipeline fortsätter
```
