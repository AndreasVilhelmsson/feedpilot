# FEED-060 — Test Baseline och Verifieringskommando

## Status

Done

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

FeedPilot är byggd som MVP men koden är ojämnt reviewad. För att kunna fortsätta säkert behöver vi ett reproducerbart sätt att verifiera appen.

Just nu:

- Backendtester passerar i Docker.
- Lokal backend `pytest` failar om Python-miljön saknar dependencies.
- Frontend lint och tester passerar.
- Teststatus finns i `docs/STATUS.md`, men testkommandon och arbetsflöde bör vara tydligare samlade.

Det här är första ticketen för att testa vårt nya arbetssätt:

```txt
Claude Code implementerar en fil i taget.
Codex analyserar, testar och godkänner mot krav.
```

## Problem

Det är svårt att veta om appen fungerar efter ändringar eftersom testvägen inte är helt tydlig.

Vi behöver en liten, kontrollerad ticket som:

- dokumenterar verifieringskommandon
- gör teststatus lätt att förstå
- kräver minimala kodändringar
- bekräftar att Claude/Codex-arbetsflödet fungerar

## Mål

Skapa en tydlig testbaseline för nuvarande app.

Efter ticketen ska en utvecklare kunna förstå:

- vilka kommandon som ska köras
- var backendtester ska köras
- vilka tester som finns
- vilka kända gap som finns
- vad som räknas som grön verifiering

## Berörda filer

Claude Code får bara ändra en fil i taget.

Primär fil:

- `docs/TOOLING.md`

Tillåtna efter separat godkännande:

- `docs/STATUS.md`
- `docs/EXECUTION_PLAN.md`
- `README.md`

Inga produktionskodfiler ska ändras i denna ticket.

## Krav

### 1. Lägg till sektion i `docs/TOOLING.md`

Lägg till en sektion:

```txt
## Verifiering / Test Baseline
```

Sektionen ska innehålla:

- backend testkommando via Docker
- frontend lintkommando
- frontend testkommando
- kort förklaring att lokal backend pytest kräver installerade backend dependencies
- nuvarande kända testgap
- förväntat grönt resultat

### 2. Dokumentera kommandon exakt

Kommandon:

```bash
docker compose exec backend pytest tests/
cd frontend && npm run lint
cd frontend && npm test -- --runInBand
```

### 3. Dokumentera aktuellt verifierat läge

Nuvarande verifierade baseline:

```txt
Backend: 12 tests pass in Docker
Frontend lint: pass
Frontend tests: 7 tests pass
Known backend warning: FastAPI on_event deprecation
Known gap: backend/tests/test_ingest.py is empty
```

### 4. Dokumentera review-regel

Lägg in denna regel:

```txt
Claude Code skriver implementation.
Codex kör verifiering och review.
Ingen ticket går till Done utan testresultat eller dokumenterad blocker.
```

## Acceptance Criteria

- `docs/TOOLING.md` har en tydlig verifieringssektion.
- Kommandon är copy/paste-klara.
- Dokumentet skiljer på Docker-backendtest och lokal backendtest.
- Kända gap nämns utan att markeras som lösta.
- Inga produktionskodfiler ändras.
- Codex kan köra verifieringskommandon efter ändringen.

## Testkrav

Codex ska köra:

```bash
docker compose exec backend pytest tests/
cd frontend && npm run lint
cd frontend && npm test -- --runInBand
```

Om Docker inte är tillgängligt ska blocker dokumenteras i review.

## Risker

- Risk att dokumentationen säger att tester täcker mer än de faktiskt gör.
- Risk att lokal `pytest` presenteras som fungerande trots att dependencies saknas.
- Risk att ticketen växer till att ändra kod. Det ska den inte göra.

## Definition of Done

- Claude Code har ändrat `docs/TOOLING.md`.
- Codex har reviewat diffen.
- Codex har kört verifiering eller dokumenterat blocker.
- `docs/STATUS.md` uppdateras endast om testresultat ändrats.

## Codex Review — 2026-04-29

Resultat: Godkänd.

Verifiering:

```bash
docker compose exec backend pytest tests/
# 12 passed, 2 FastAPI on_event deprecation warnings

cd frontend && npm run lint
# pass

cd frontend && npm test -- --runInBand
# 2 suites passed, 7 tests passed
```

Notering:

- Första backend-körningen rapporterade att `backend`-servicen inte körde.
- `docker compose ps` visade därefter att backend, postgres, redis och worker var uppe igen.
- Backendtesterna kördes om och passerade.
- Frontendtester loggar avsiktliga `console.error` från simulerade API-fel i processing-testerna.
