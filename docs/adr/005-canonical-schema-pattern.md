# ADR-005: Canonical Schema Pattern for Feed Ingestion

## Status
Accepted

## Context
FeedPilot importerar produktdata från flera olika källor: Shopify, WooCommerce, Google Shopping, Akeneo, och generiska CSV/XLSX-filer. Varje källa har sina egna fältnamn och strukturer.

## Decision
Vi implementerade ett canonical schema-lager som normaliserar alla inkommande feeds till ett enhetligt internt format (`CanonicalProduct`) innan data sparas i databasen.

## Reasoning

Utan canonical schema:
- Enrichment-logiken behöver hantera varje sources fältnamn separat
- AI-prompts behöver anpassas per källa
- Svårt att lägga till nya sources utan att röra core-logiken

Med canonical schema:
- En enda enrichment-pipeline för alla sources
- Nya sources kräver bara en ny mapper-funktion
- Konsekvent datamodell i databasen

Flöde:
```
CSV/XLSX → Ingestion Service → Detect source format
                             → Source-specific mapper
                             → CanonicalProduct
                             → Save to DB (Product model)
```

## Consequences
+ Enrichment-service är source-agnostisk
+ Enkelt att lägga till nya connectors (Akeneo, inRiver, etc.)
+ Konsekvent datamodell — en Product-tabell för alla sources
+ Field mapping UI (FEED-018) kan byggas ovanpå denna abstraktion
- Extra abstraktionslager att förstå för nya utvecklare
- Informationsförlust om en source har fält som inte mappas till canonical
