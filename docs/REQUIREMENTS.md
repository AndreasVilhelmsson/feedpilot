# FeedPilot — Krav

## Funktionella krav

### Ingest
| ID    | Krav                                          | Status |
|-------|-----------------------------------------------|--------|
| FR-01 | CSV ingest med auto schema detection          | ✅     |
| FR-02 | Excel (XLSX) ingest                           | ✅     |
| FR-03 | JSON API push endpoint                        | ⬜     |
| FR-04 | Shopify Pull connector                        | ⬜     |
| FR-05 | WooCommerce Pull connector                    | ⬜     |

Auto-detekterade format: Shopify, WooCommerce, Google Shopping, Akeneo

### Enrichment
| ID    | Krav                                          | Status |
|-------|-----------------------------------------------|--------|
| FR-06 | AI enrichment med reasoning + confidence      | ✅     |
| FR-07 | Variant-level SEO enrichment                  | ✅     |
| FR-08 | Multimodal bildanalys                         | ✅     |
| FR-09 | Bulk enrichment via ARQ async queue           | ✅     |
| FR-10 | Enrich Again (trigger nytt jobb)              | ✅     |
| FR-11 | Human-in-the-loop feedback (Accept/Reject)    | ✅     |
| FR-12 | Inline edit av AI-förslag                     | ✅     |

### Frontend
| ID    | Krav                                          | Status |
|-------|-----------------------------------------------|--------|
| FR-13 | Dashboard med live metrics                    | ✅     |
| FR-14 | Product catalog med filter + sökning          | ✅     |
| FR-15 | Enrichment review UI med beslut per fält      | ✅     |
| FR-16 | Variant manager UI                            | ✅     |
| FR-17 | Image analysis panel                          | ✅     |
| FR-18 | Upload feed modal                             | ✅     |
| FR-19 | View History per produkt                      | ⬜     |
| FR-20 | Export JSON med accepterade fält              | ✅     |
| FR-21 | Send to PIM (accepterade fält)                | ⬜ stub |

### Auth + Säkerhet
| ID    | Krav                                          | Status |
|-------|-----------------------------------------------|--------|
| FR-22 | Inloggning med JWT (email + password)         | ⬜     |
| FR-23 | Roller: superuser / admin / user / guest      | ⬜     |
| FR-24 | Skyddade routes i Next.js                     | ⬜     |
| FR-25 | Auth middleware i FastAPI                     | ⬜     |
| FR-26 | Multi-tenant dataisolering                    | ⬜     |
| FR-27 | API-nycklar per tenant                        | ⬜     |

---

## Non-funktionella krav

### Prestanda
| ID     | Krav                                          |
|--------|-----------------------------------------------|
| NFR-01 | API svarstid < 200ms (ej AI-anrop)            |
| NFR-02 | Bulk enrichment skalbart till 50k SKU         |
| NFR-03 | Frontend first load < 2s                      |

### Säkerhet
| ID     | Krav                                          |
|--------|-----------------------------------------------|
| NFR-04 | JWT med expiry + refresh tokens               |
| NFR-05 | API-nycklar per tenant, hashade i DB          |
| NFR-06 | Rate limiting på API                          |
| NFR-07 | Ingen känslig data i logs                     |
| NFR-08 | GDPR-policy + Terms of Service                |

### Tillgänglighet
| ID     | Krav                                          |
|--------|-----------------------------------------------|
| NFR-09 | Loading states på alla async operationer      |
| NFR-10 | Error states med tydliga meddelanden          |
| NFR-11 | Empty states med call-to-action               |

### Driftsättning
| ID     | Krav                                          |
|--------|-----------------------------------------------|
| NFR-12 | Docker production build utan --reload         |
| NFR-13 | Separata miljöer: dev / staging / prod        |
| NFR-14 | Automatiska DB-backups (dagliga)              |
| NFR-15 | Monitoring + alerting i prod                  |
| NFR-16 | Felrapportering via Sentry                    |
