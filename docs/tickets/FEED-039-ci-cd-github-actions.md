# FEED-039 — CI/CD: GitHub Actions pipeline + branch protection

**Sprint:** Sprint 2
**Typ:** Infra / DevOps
**Prioritet:** Hög
**Skapad:** 2026-05-19
**Status:** ✅ Klar — mergad i PR #12

---

## Problem

Projektet saknade automatiserade checks vid push/PR. Alla commits till `main` gick rakt in utan test-verifiering. Ingen branch protection.

---

## Vad som gjordes

### Branch protection
- GitHub-ruleset "Protect main" skapad
- Kräver PR + 2 godkända status checks innan merge till `main`
- Direct push till main blockerad

### GitHub Actions (`ci.yml`)
Två parallella jobb:

**Backend — pytest**
- Startar Postgres + Redis + backend via Docker Compose
- Skapar `backend/.env` med rätt fältnamn (se nedan)
- Väntar på `GET /api/v1/health` innan tester körs
- Kör `pytest tests/ -v` inuti backend-containern
- Skriver ut `docker compose logs backend` vid fel

**Frontend — lint + tests**
- Node 20, npm ci, `npm run lint`, `npm test`

### docker-compose.ci.yml (override-fil)
Skapad för att åsidosätta `platform: linux/arm64` i `docker-compose.yml`.
CI-runners är `ubuntu-latest` (AMD64) — utan overriden misslyckas alla image-pulls.

```yaml
services:
  backend:
    platform: linux/amd64
  postgres:
    platform: linux/amd64
  redis:
    platform: linux/amd64
  worker:
    platform: linux/amd64
```

CI kör alltid med: `docker compose -f docker-compose.yml -f docker-compose.ci.yml`

### .env.example
Skapad i repo-roten med exakta fältnamn från `Settings`-modellen:

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=postgresql://feedpilot:feedpilot@postgres:5432/feedpilot
REDIS_HOST=redis
REDIS_PORT=6379
```

---

## Buggar som hittades och fixades under arbetet

| # | Fel | Orsak | Fix |
|---|-----|-------|-----|
| 1 | Backend-imagen drog ARM64 | `FROM --platform=linux/arm64` i `Dockerfile` | Tog bort `--platform`-flaggan |
| 2 | Alla compose-tjänster ARM64 | `platform: linux/arm64` på alla services i `docker-compose.yml` | `docker-compose.ci.yml` override |
| 3 | `.env` skapades på fel plats | CI skrev till `./` istf `backend/` | Ändrade path i CI-steget |
| 4 | Health check fel path | `/health` istf `/api/v1/health` | Fixade URL |
| 5 | Pydantic `ValidationError: redis_url extra inputs not permitted` | CI skickade `REDIS_URL=redis://...` men Settings-modellen har `redis_host`/`redis_port` | Ändrade env-variabler i CI |
| 6 | `frontend/lib/` ignorerades av git | `.gitignore` hade `lib/` (Python-template-rest) | Tog bort raden, committade `api.ts` och `types.ts` |

---

## Filer som skapades/ändrades

| Fil | Ändring |
|-----|---------|
| `.github/workflows/ci.yml` | Ny fil — hela CI-pipelinen |
| `docker-compose.ci.yml` | Ny fil — ARM64→AMD64 override |
| `.env.example` | Ny fil — korrekt fältnamn för `Settings` |
| `backend/Dockerfile` | Tog bort `--platform=linux/arm64` |
| `.gitignore` | Tog bort `lib/` (rad 17) |
| `frontend/lib/api.ts` | Committades (låg tidigare bara lokalt) |
| `frontend/lib/types.ts` | Committades (låg tidigare bara lokalt) |

---

## Slutresultat

PR #12 (`fix/ci-platform-and-env`) mergad till `main`:
- Backend — pytest ✅ (1m 2s) — 56 tester
- Frontend — lint + tests ✅ (28s)

Varje ny PR mot `main` kör nu automatiskt båda checks.

---

## Lärdomar / beslut

**REDIS_HOST + REDIS_PORT, inte REDIS_URL** — `Settings`-modellen i `backend/app/core/config.py` har separata fält för host och port. Använd aldrig `REDIS_URL` — pydantic-settings castar det inte automatiskt och kastar `ValidationError` med `extra_forbidden`.

**Lokal ARM64 / CI AMD64** — `docker-compose.yml` har `platform: linux/arm64` för lokal Mac M-chip-utveckling. CI behöver alltid override-filen. Lägg aldrig till `platform` direkt i `docker-compose.yml` för CI-kompatibilitet — håll separationen.

**`.gitignore` Python-template** — root `.gitignore` genererades från ett Python-repo-template och innehöll `lib/` som ignorerade `frontend/lib/`. Kontrollera alltid att `.gitignore` inte ignorerar frontend-kod.

---

## Nästa ticket

**FEED-014** — JWT + login page (blockar alla andra auth-tickets)
