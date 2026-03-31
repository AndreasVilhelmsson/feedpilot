# FeedPilot — Backlog

Alla FEED-tickets samlade. Uppdatera status i STATUS.md när ett ticket är klart.

---

## Frontend (Sprint 1 / Dag 12–14)

| ID       | Titel                              | Prioritet | Sprint     | Status |
|----------|------------------------------------|-----------|------------|--------|
| FEED-001 | Next.js 14 setup + routing         | Hög       | Dag 12     | ✅     |
| FEED-002 | Shared layout — Sidebar + TopNav   | Hög       | Dag 12     | ✅     |
| FEED-003 | Dashboard med live metrics         | Hög       | Dag 12     | ✅     |
| FEED-004 | Job progress bar (live polling)    | Hög       | Dag 12     | ✅     |
| FEED-005 | Catalog — produktlista med filter  | Hög       | Dag 12     | ✅     |
| FEED-006 | Product Detail enrichment view     | Hög       | Dag 13     | ✅     |
| FEED-007 | Accept/Reject/Edit per fält        | Hög       | Dag 13     | ✅     |
| FEED-008 | Enrich Again                       | Medium    | Dag 13     | ✅     |
| FEED-009 | View History per produkt           | Medium    | Dag 13     | ⬜     |
| FEED-010 | Variant Manager UI                 | Hög       | Dag 13     | ✅     |
| FEED-011 | Image Analysis UI                  | Medium    | Dag 14     | ✅     |
| FEED-012 | Upload feed modal                  | Hög       | Dag 12     | ✅     |
| FEED-013 | Loading skeletons på alla vyer     | Medium    | Dag 14     | ⬜     |

---

## Auth + Roller (Sprint 2)

| ID       | Titel                              | Prioritet | Sprint | Status |
|----------|------------------------------------|-----------|--------|--------|
| FEED-014 | Auth — JWT + login page            | Hög       | 2      | ⬜     |
| FEED-015 | Roller + behörigheter              | Hög       | 2      | ⬜     |
| FEED-016 | Skyddade routes i Next.js          | Hög       | 2      | ⬜     |
| FEED-017 | Auth middleware i FastAPI          | Hög       | 2      | ⬜     |

Rollmatris:
- `superuser` → allt + systeminställningar
- `admin` → allt inom sin tenant
- `user` → enrichment + export
- `guest` → läsa, ej ändra

---

## ARQ + Worker-förbättringar (Sprint 2)

| ID       | Titel                              | Prioritet | Sprint | Status |
|----------|------------------------------------|-----------|--------|--------|
| FEED-025 | Separata ARQ-köer (ai + data)      | Hög       | 2      | ⬜     |
| FEED-026 | Retry med exponential backoff      | Hög       | 2      | ⬜     |
| FEED-027 | Dead letter handling               | Medium    | 2      | ⬜     |
| FEED-028 | Structured logging (structlog)     | Medium    | 3      | ⬜     |
| FEED-029 | Rate limiting per tenant           | Medium    | 3      | ⬜     |
| FEED-030 | Job prioritering per tenant        | Medium    | 4      | ⬜     |
| FEED-031 | Prometheus metrics                 | Medium    | 4      | ⬜     |

FEED-025 detaljer:
- `feedpilot:ai` → Claude-anrop, max_jobs=5
- `feedpilot:data` → ingest + embeddings, max_jobs=20
- Ny worker-container i docker-compose per kö

---

## Multi-tenant + Onboarding (Sprint 3)

| ID       | Titel                              | Prioritet | Sprint | Status |
|----------|------------------------------------|-----------|--------|--------|
| FEED-032 | Multi-tenant schema isolation      | Hög       | 3      | ⬜     |
| FEED-033 | Tenant-modell i databasen          | Hög       | 3      | ⬜     |
| FEED-034 | API-nycklar per tenant             | Hög       | 3      | ⬜     |
| FEED-035 | Onboarding flow för ny kund        | Hög       | 3      | ⬜     |

FEED-033 schema: `id, name, schema_name, api_key, created_at, plan, usage_tokens`
FEED-035 flow: `POST /tenants/register` → skapar tenant + schema + API-nyckel + välkomstmail

---

## Produkt-features v2 (Sprint 4)

| ID       | Titel                              | Prioritet | Sprint | Status |
|----------|------------------------------------|-----------|--------|--------|
| FEED-018 | Field mapping UI (Nivå 2)          | Medium    | 4      | ⬜     |
| FEED-019 | Schema editor per kund (Nivå 3)    | Medium    | 4      | ⬜     |
| FEED-020 | Feedback-loop och self-learning    | Medium    | 4      | ⬜     |
| FEED-021 | Image-Product Mismatch rapport     | Medium    | 4      | ⬜     |
| FEED-022 | ROI-rapport per kund               | Medium    | 4      | ⬜     |
| FEED-023 | Shopify Pull connector             | Hög       | 4      | ⬜     |
| FEED-024 | WooCommerce Pull connector         | Medium    | 5      | ⬜     |

---

## Infrastruktur + Miljö (Sprint 2–3)

| ID       | Titel                              | Prioritet | Sprint      | Status |
|----------|------------------------------------|-----------|-------------|--------|
| FEED-036 | Linear + Notion setup              | Hög       | Nu direkt   | ⬜     |
| FEED-037 | ADR-001 till ADR-005               | Medium    | Nu direkt   | ⬜     |
| FEED-038 | Branch protection + PR-template    | Hög       | Nu direkt   | ⬜     |
| FEED-039 | GitHub Actions CI/CD               | Hög       | 2           | ⬜     |
| FEED-040 | Sentry integration                 | Hög       | 2           | ⬜     |
| FEED-041 | GCP-konto + staging                | Hög       | 2           | ⬜     |
| FEED-042 | Cloud SQL migration (staging)      | Hög       | 2           | ⬜     |
| FEED-043 | Produktionsmiljö GCP               | Hög       | Före kund   | ⬜     |
| FEED-044 | Environment separation             | Medium    | 3           | ⬜     |
| FEED-045 | UptimeRobot monitoring             | Medium    | 3           | ⬜     |

---

## Teknisk skuld (Sprint 3–4)

| ID       | Titel                              | Prioritet | Sprint | Status |
|----------|------------------------------------|-----------|--------|--------|
| FEED-046 | Pytest tester dag 8–11             | Medium    | 3      | ⬜     |
| FEED-047 | Integration tests för API          | Medium    | 3      | ⬜     |
| FEED-048 | OpenAPI spec export                | Låg       | 4      | ⬜     |
| FEED-049 | Docker production build            | Hög       | Före kund | ⬜  |
| FEED-050 | GDPR-policy + Terms of Service     | Hög       | Före kund | ⬜  |

---

## Produkt-features v3 (Sprint 5)

| ID       | Titel                              | Prioritet | Sprint | Status |
|----------|------------------------------------|-----------|--------|--------|
| FEED-051 | Stripe integration                 | Medium    | 5      | ⬜     |
| FEED-052 | PostHog analytics                  | Låg       | 5      | ⬜     |
| FEED-053 | Akeneo connector                   | Medium    | 5      | ⬜     |
| FEED-054 | inRiver connector                  | Medium    | 5      | ⬜     |
| FEED-055 | Multi-language enrichment          | Medium    | 5      | ⬜     |
| FEED-056 | Advanced analytics dashboard       | Medium    | 5      | ⬜     |
