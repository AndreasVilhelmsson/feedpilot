# FeedPilot — Status

## Backend (Dag 1–11)

| Dag  | Innehåll                                      | Status |
|------|-----------------------------------------------|--------|
| 1    | Arkitektur + design document                  | ✅     |
| 2    | FastAPI grundstruktur + Docker                | ✅     |
| 3    | Claude API + service layer                    | ✅     |
| 4    | Prompt engineering + versionshantering        | ✅     |
| 5    | CSV ingest + schema detection                 | ✅     |
| 6    | pgvector + embeddings                         | ✅     |
| 7    | RAG pipeline                                  | ✅     |
| 8    | Enrichment med reasoning + confidence         | ✅     |
| 9    | Variant-level SEO + EAN                       | ✅     |
| 10   | Multimodal bildanalys                         | ✅     |
| 11   | ARQ async pipeline + Excel ingest             | ✅     |
| —    | Canonical schema + mapping layer refactor     | ✅     |

---

## Sprint 1 — MVP Frontend (Dag 12)

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-001  | Next.js 14 setup + routing            | ✅     |
| FEED-002  | Shared layout — Sidebar + TopNav      | ✅     |
| FEED-003  | Dashboard med live metrics            | ✅     |
| FEED-004  | Job progress bar (live polling)       | ✅     |
| FEED-005  | Catalog — produktlista med filter     | ✅     |
| FEED-006  | Product Detail enrichment view        | ✅     |
| FEED-007  | Accept/Reject/Edit per fält           | ✅ inkl. inline editing |
| FEED-008  | Enrich Again-knapp                    | ✅     |
| FEED-009  | View History per produkt              | ⬜     |
| FEED-010  | Variant Manager UI                    | ✅     |
| FEED-011  | Image Analysis UI (ImagePanel)        | ✅     |
| FEED-012  | Upload feed modal (CSV + Excel)       | ✅     |
| FEED-013  | Loading skeletons på alla datavyer    | ⬜ delvis |
| FEED-021  | README + arkitekturdiagram            | ✅     |

---

## Sprint 2 — Auth + Roller

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-014  | Auth — JWT + login page               | ⬜     |
| FEED-015  | Roller + behörigheter                 | ⬜     |
| FEED-016  | Skyddade routes i Next.js             | ⬜     |
| FEED-017  | Auth middleware i FastAPI             | ⬜     |
| FEED-025  | Separata ARQ-köer (ai + data)         | ⬜     |
| FEED-026  | Retry med exponential backoff         | ⬜     |
| FEED-027  | Dead letter handling                  | ⬜     |
| FEED-028  | Sentry integration                    | ⬜     |
| FEED-040  | GitHub Actions CI/CD pipeline         | ⬜     |
| FEED-041  | Sentry integration                    | ⬜     |
| FEED-042  | GCP-konto + staging miljö             | ⬜     |
| FEED-043  | Migrera DB till Cloud SQL             | ⬜     |

---

## Sprint 3 — Multi-tenant

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-032  | Multi-tenant schema isolation         | ⬜     |
| FEED-033  | Tenant-modell i databasen             | ⬜     |
| FEED-034  | API-nycklar per tenant                | ⬜     |
| FEED-035  | Onboarding flow för ny kund           | ⬜     |
| FEED-029  | Structured logging (structlog)        | ⬜     |
| FEED-030  | Rate limiting per tenant              | ⬜     |
| FEED-036  | Pytest tester dag 8–11                | ⬜     |
| FEED-037  | Integration tests för API endpoints   | ⬜     |
| FEED-045  | Environment separation (dev/stg/prod) | ⬜     |
| FEED-046  | UptimeRobot monitoring                | ⬜     |

---

## Innan första kund (blocking)

| Ticket    | Beskrivning                           | Status |
|-----------|---------------------------------------|--------|
| FEED-032  | Multi-tenant schema isolation         | ⬜     |
| FEED-033  | Tenant-modell                         | ⬜     |
| FEED-034  | API-nycklar                           | ⬜     |
| FEED-039  | Docker production build (ej --reload) | ⬜     |
| FEED-040  | GDPR-policy + Terms of Service        | ⬜     |
| FEED-044  | Produktionsmiljö GCP                  | ⬜     |
| Auth      | JWT + roller (Sprint 2)               | ⬜     |
