# ADR-002: pgvector over Pinecone/OpenAI Vector Store

## Status
Accepted

## Context
Vi behöver vector search för RAG-pipeline (hitta liknande produkter, kontextuell enrichment).

## Decision
Vi valde pgvector — PostgreSQL-extension — istället för en dedikerad vector-databas som Pinecone.

## Reasoning
- Ingen extra service att driftsätta eller betala för
- Samma databas som appdata → inga cross-service-joins
- Fungerar med befintlig SQLAlchemy-stack
- pgvector stöds av Cloud SQL (PostgreSQL 15)
- Tillräcklig prestanda för upp till ~1M vektorer
- Multi-tenant isolation är enklare (ett index per schema)

## Consequences
+ Enklare infrastruktur — en databas för allt
+ Lägre kostnad (ingen separat vector DB-räkning)
+ Fungerar med befintliga migrationsverktyg (Alembic)
- Sämre prestanda vid >10M vektorer jämfört med Pinecone
- Kräver pgvector-extension (stöds av Cloud SQL, inte alla hosts)
- Ingen inbyggd hybrid search (text + vector) utan extra setup
