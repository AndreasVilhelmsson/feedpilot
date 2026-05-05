# FeedPilot — Roadmap

## Nuläge

Backend Dag 1–11 är klart. MVP Frontend (Sprint 1) är i stort sett klart.
Efter reverse engineering är nästa steg inte Auth direkt, utan en stabiliseringsfas.

Nytt beslut:

```txt
Sprint 1.5 — Stabilisering och AI Control
```

Auth och multi-tenant ligger kvar, men bör inte starta innan vi har bättre testbas, kodstyrd AI-output och preflight/kostnadskontroll.

---

## Sprint 1 — MVP Frontend (Dag 12–14) ✅

Mål: Fungerande UI att demo för externa personer.

- Next.js setup, Sidebar, TopNav, Dashboard, Catalog
- Product Detail med enrichment-tabell + inline editing
- Accept/Reject per fält, Enrich Again, ImagePanel
- Upload feed modal (CSV + Excel)
- Variant Manager

Återstår:
- View History per produkt (FEED-009)
- Skeletons på alla datavyer (FEED-013)

---

## Sprint 1.5 — Stabilisering och AI Control

Mål: göra MVP:n reviewbar, testbar och redo att utvecklas mot ett kodstyrt AI enrichment-system.

Prioriterat:

1. Test baseline och verifieringskommando (FEED-060)
2. Ingestion test coverage (FEED-061)
3. Enrichment output schema validation (FEED-062)
4. Preflight för bulk enrichment (FEED-063)
5. Field metadata och minimal AI payload (FEED-064)
6. Model/tool decision planner (FEED-065)
7. AI observability (FEED-066)
8. API endpoint coverage (FEED-067)
9. Layering cleanup plan (FEED-068)

Roller:

- Claude Code: implementation.
- Codex: review, test, arkitekturkontroll och status.

Definition of done för sprinten:

- backend/frontend verifieringskommandon passerar
- ingestion har riktig testtäckning
- enrichment-output valideras i kod innan persistence
- bulk enrichment har preflight innan jobb startar
- AI-input kan minimeras per fält/task
- tokens/kostnad/modell/tools kan följas upp

---

## Sprint 2 — Auth + Stabilitet

Mål: Kan visas för externa användare utan att exponera data okontrollerat.

Prioriterat:
1. JWT auth + login page (FEED-014)
2. Rollbaserat skydd — routes + API (FEED-015, 016, 017)
3. Sentry error tracking (FEED-040)
4. GitHub Actions CI/CD (FEED-039)
5. GCP staging + Cloud SQL (FEED-041, 042)
6. Separata ARQ-köer (FEED-025)
7. Retry + backoff för Claude API (FEED-026)

---

## Sprint 3 — Multi-tenant

Mål: Kan onboarda betalande kund nummer 1.

Prioriterat:
1. Tenant-modell + schema isolation (FEED-032, 033)
2. API-nycklar per tenant (FEED-034)
3. Onboarding flow (FEED-035)
4. Structured logging (FEED-028)
5. Rate limiting per tenant (FEED-029)
6. Tester — services + API endpoints (FEED-046, 047)

---

## Sprint 4 — Produkt-features v2

- Field mapping UI (FEED-018)
- Feedback-loop/self-learning (FEED-020)
- Shopify Pull connector (FEED-023)
- ROI-rapport (FEED-022)
- Image-Product Mismatch rapport (FEED-021)
- Prometheus metrics (FEED-031)

---

## Sprint 5 — Scale + Monetization

- Stripe abonnemangshantering (FEED-051)
- Akeneo + inRiver connectors (FEED-053, 054)
- Multi-language enrichment (FEED-055)
- PostHog analytics (FEED-052)

---

## Milestone: Före första betalande kund

Dessa måste vara klara — inget undantag:

- [ ] Auth med JWT (FEED-014–017)
- [ ] Multi-tenant schema isolation (FEED-032)
- [ ] API-nycklar per tenant (FEED-034)
- [ ] Sentry error tracking (FEED-040)
- [ ] Docker production build utan --reload (FEED-049)
- [ ] Produktionsmiljö på GCP (FEED-043)
- [ ] Automatiska DB-backups verifierade
- [ ] GDPR-policy + Terms of Service (FEED-050)
- [ ] Custom domain + SSL
- [ ] Monitoring + alerting konfigurerat

---

## Deployment-miljöer

```
LOCAL (nu)
  docker-compose på Mac
  Fejkdata, --reload, debug på

STAGING (Sprint 2)
  GCP Cloud Run
  Kopia av prod-infrastruktur
  Används för test + beta-kunder
  Separat databas

PRODUCTION (Milestone: Första kund)
  GCP Cloud Run (api + worker)
  Cloud SQL PostgreSQL 15 + pgvector
  Cloud Memorystore Redis
  Cloud Storage (bilder + CSV)
  Secret Manager
  Cloud Monitoring + Sentry
```

Uppskattad kostnad prod: ~$60/månad
- Cloud Run: ~$20
- Cloud SQL: ~$15
- Cloud Memorystore: ~$25
- Storage + övrigt: ~$1
