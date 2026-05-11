---
name: preflight-check
description: Run a preflight analysis before a bulk enrichment job. Use when about to start a large enrichment run, estimating cost, or verifying batch parameters. Always run this before confirming an expensive bulk operation.
allowed-tools: Bash(docker compose ps:*), Bash(docker compose logs:*), Bash(curl:*)
---

## Bulk enrichment preflight check

Target limit: $ARGUMENTS

If no limit is provided, use `25`.

### Step 1 — Verify services are running

!`docker compose ps`

### Step 2 — Run backend preflight

Use the real FeedPilot preflight endpoint. The default command uses limit `25`.
If the user supplied a different limit in `$ARGUMENTS`, replace `25` with that value before running.

!`curl -s -X POST http://localhost:8010/api/v1/enrich/preflight -H "Content-Type: application/json" -d '{"limit": 25}' | python3 -m json.tool`

### Step 3 — Check worker status and recent errors

!`docker compose logs --tail=20 worker`

---

Based on the above, produce a preflight report:

**Preflight report:**

| Parameter                                         | Value                               |
| ------------------------------------------------- | ----------------------------------- |
| Requested limit                                   | (argument or 25)                    |
| Product count                                     | `product_count`                     |
| Estimated AI calls                                | `estimated_ai_calls`                |
| Estimated input tokens                            | `estimated_input_tokens`            |
| Estimated output tokens                           | `estimated_output_tokens`           |
| Estimated total tokens                            | `estimated_total_tokens`            |
| Estimated cost USD                                | `estimated_cost_usd`                |
| Fields to enrich                                  | `fields_to_enrich`                  |
| Tool plan                                         | `tool_plan`                         |
| Requires confirmation                             | `requires_confirmation`             |
| Worker healthy                                    | (from step 3)                       |

**Checklist before proceeding:**

- [ ] Preflight endpoint returned valid JSON
- [ ] Worker is running and healthy
- [ ] `estimated_ai_calls == product_count`
- [ ] `requires_confirmation` is true
- [ ] Tool plan is backend-controlled, not prompt-controlled
- [ ] User has confirmed the cost estimate

**Recommendation:** PROCEED / HOLD (with reason)

Do NOT start the bulk run until the user explicitly confirms after seeing this report.
