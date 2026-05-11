---
name: enrichment-test
description: Run a quick enrichment test for one or more product SKUs and verify the output schema. Use when testing the enrichment pipeline after changes, debugging enrichment failures, or verifying CanonicalProduct output.
allowed-tools: Bash(docker compose exec:*), Bash(curl:*)
---

## Enrichment pipeline test

Target SKU(s): $ARGUMENTS

### Step 1 — Verify backend is running

!`docker compose ps`

### Step 2 — Run enrichment for the target SKU

!`curl -s -X POST http://localhost:8010/api/v1/products/$ARGUMENTS/enrich | python3 -m json.tool`

### Step 3 — Check worker logs for token usage and errors

!`docker compose logs --tail=50 worker`

---

After running the above, verify:

**Output schema checklist:**

- [ ] Response contains expected enriched fields
- [ ] No raw ORM fields leaked into response (check against CanonicalProduct schema)
- [ ] `stop_reason` is NOT `max_tokens` (would mean truncated response)
- [ ] Token usage logged (check worker logs)
- [ ] `job.processed` incremented if part of bulk run
- [ ] No unvalidated fields persisted to DB

**If enrichment failed:**

- Check `stop_reason` in AI response
- Check `_extract_json()` handled truncation safely
- Check retry logic triggered (look for 529 in logs)
- Check `max_tokens` is 4096 in the enrichment call

Report findings with severity: LOW / MEDIUM / HIGH
