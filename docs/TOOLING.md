# FeedPilot — Verktyg & Infrastruktur

## Projekthantering

**Linear** (rekommenderat) — snabbare och billigare än Jira för ett litet team.

Setup:
1. Skapa Linear-konto
2. Lägg in alla FEED-tickets från BACKLOG.md
3. Board-kolumner: Backlog → Todo → In Progress → In Review → Done

## Dokumentation

**Notion** — en workspace med:
- Arkitekturdiagram
- ADR (Architecture Decision Records)
- API-dokumentation
- Onboarding-guide

Se `docs/adr/` för ADR-filer som kan importeras.

## Kod (GitHub)

Lägg till:
- Branch protection på `main` (kräver PR + review)
- PR-template (`.github/pull_request_template.md`)
- `.github/CODEOWNERS`

## CI/CD

**GitHub Actions** (FEED-039):
- Kör tester på varje PR
- Auto-deploy till staging vid merge till `main`
- Bygg Docker-image automatiskt

## Error tracking

**Sentry** (FEED-040):
```python
# 3 rader i main.py
import sentry_sdk
sentry_sdk.init(dsn="...", traces_sample_rate=0.1)
```
Gratis upp till 5 000 events/månad. Fångar alla exceptions automatiskt.

## Monitoring

**UptimeRobot** (FEED-045) — gratis upp till 50 monitorer.
Notifierar om appen går ner.

**Cloud Monitoring + Logging** — inbyggt i GCP.

**Prometheus metrics** (FEED-031, Sprint 4):
- Antal jobb per minut
- Claude API latency + kostnad per tenant
- Genomsnittlig enrichment-tid

## Secret management

**Doppler** eller **GitHub Secrets** — aldrig `.env`-filer i produktion.

## Analytics

**PostHog** (FEED-052, Sprint 5) — open source, self-hosted möjligt.
Ser vad användare faktiskt gör i appen.

## Fakturering

**Stripe** (FEED-051, Sprint 5) — abonnemangshantering + fakturering per tenant.

## Customer support

**Intercom** eller **Linear** (support-läge) — när du har betalande kunder.

---

## Checklista: Denna vecka

- [ ] Skapa Linear-konto, lägg in alla FEED-tickets
- [ ] Skapa Notion workspace, kopiera in ADR-mall
- [ ] Sätt upp branch protection på GitHub `main`
- [ ] Skapa GitHub Actions workflow för tester

## Checklista: Nästa vecka

- [ ] Sätt upp GCP-konto (gratis $300 credits)
- [ ] Skapa staging-miljö på Cloud Run
- [ ] Migrera DB till Cloud SQL staging
- [ ] Koppla Sentry till staging

## Checklista: Innan första kund

- [ ] Produktionsmiljö på GCP
- [ ] Custom domain + SSL
- [ ] Automatiska backups verifierade
- [ ] Monitoring + alerting konfigurerat
- [ ] Auth implementerat
- [ ] GDPR-policy + Terms of Service
