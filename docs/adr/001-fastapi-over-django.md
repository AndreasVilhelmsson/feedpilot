# ADR-001: FastAPI over Django

## Status
Accepted

## Context
Vi behövde ett Python web framework för ett AI-first API-system med async-stöd.

## Decision
Vi valde FastAPI.

## Reasoning
- Native async support — kritiskt för parallella Claude API-anrop (3–8s per anrop)
- Pydantic V2 inbyggt — automatisk validering och serialisering
- Automatisk Swagger/OpenAPI-dokumentation utan extra setup
- Bättre prestanda för rena API-endpoints
- Konsekvent kodstil med resten av stacken (async/await genomgående)

## Consequences
+ Snabbare development av API-endpoints
+ Bättre integration med async AI-anrop (50 parallella Claude-anrop i en worker)
+ Automatisk API-dokumentation på /docs
- Ingen inbyggd admin-panel (Django har det inbyggt)
- Kräver mer manuell setup än Django för auth, permissions, etc.
