# ADR-004: Google Cloud Platform as Cloud Provider

## Status
Accepted

## Context
Vi behöver välja en molnleverantör för staging och produktion.

## Decision
Vi valde GCP (Google Cloud Platform).

## Reasoning
- Cloud Run — serverless containers, betala per request, auto-scaling till noll
- Cloud SQL stöder PostgreSQL 15 + pgvector (Azure/AWS kräver extra konfiguration)
- Cloud Memorystore — hanterad Redis utan underhåll
- Secret Manager — inbyggd secrets-hantering
- $300 gratis credits för nya konton
- Bra integration med GitHub Actions för CI/CD
- Allt i ett ekosystem — enklare billing och IAM

## Deployment-arkitektur

```
Internet → Cloud Load Balancer (SSL)
         → Cloud Run (api + worker)
         → Cloud SQL PostgreSQL 15 + pgvector
         → Cloud Memorystore Redis
         → Cloud Storage (bilder, CSV)
         → Secret Manager
         → Cloud Monitoring + Logging + Sentry
```

Uppskattad kostnad: ~$60/månad för enkel prod-setup.

## Migrering från lokal Docker till Cloud SQL

1. Skapa Cloud SQL-instans med pgvector
2. Ändra `DATABASE_URL` i Secret Manager
3. Kör `alembic upgrade head`
4. Klart — noll kodändringar i applikationen

## Consequences
+ Managed services — inga ops-uppgifter för DB/Redis
+ pgvector stöds nativt i Cloud SQL
+ Skalning med ett klick
+ Point-in-time recovery på databas
- GCP-vendor lock-in för managed services
- Något dyrare än AWS för liknande konfiguration
