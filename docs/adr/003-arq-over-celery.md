# ADR-003: ARQ over Celery + RabbitMQ

## Status
Accepted

## Context
Vi behöver en async task queue för att köra bulk enrichment (Claude API-anrop) i bakgrunden utan att blockera API-servern.

## Decision
Vi valde ARQ (async Redis queue) istället för Celery + RabbitMQ.

## Reasoning

ARQ är native async Python — samma `async def`-funktioner som i FastAPI.
Celery är synkront by default och kräver workarounds (gevent/eventlet) för async.

Jämförelse:

```
                    ARQ + Redis         Celery + RabbitMQ
─────────────────────────────────────────────────────────
Komplexitet         Låg                 Hög
  Setup             5 minuter           2-4 timmar
  Konfiguration     ~20 rader           ~200 rader
  Dependencies      1 (Redis)           3 (Redis+RabbitMQ+Celery)

Prestanda           Utmärkt             Bra
  Async native      Ja                  Nej (threads)
  Concurrent jobs   Hög (async)         Lägre
  Latency           ~1ms queue          ~5-10ms queue

Prod-readiness      Medium              Hög
  Dead letters      Saknas              Inbyggt i RabbitMQ
  Msg persistence   Nej (Redis)         Ja (RabbitMQ)
  Monitoring        Manuellt            Flower inbyggt
```

För FeedPilot (AI-tungt, litet team, homogena jobb) vinner ARQ klart.

## När Celery + RabbitMQ vore bättre
- Garanterad leverans är affärskritisk (RabbitMQ persisterar till disk)
- Komplex routing (olika jobb till olika workers per typ/prioritet)
- Befintlig Django-stack
- Stort ops-team som behöver Flower-monitoring

## Consequences
+ 50 parallella Claude-anrop i en worker utan extra konfiguration
+ Enklare codebase — ingen broker-konfiguration
+ Konsekvent async-stil med FastAPI
- Inga dead letter queues out-of-the-box (vi bygger det manuellt, FEED-027)
- Sämre monitoring (ingen Flower)
- Redis utan persistens — jobb kan tappas vid omstart (acceptabelt för nu)

## Planerad förbättring
FEED-025: Separata ARQ-köer — `feedpilot:ai` (max_jobs=5) och `feedpilot:data` (max_jobs=20).
