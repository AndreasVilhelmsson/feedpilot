---
name: session-init
description: Run the mandatory FeedPilot session startup protocol. Use at the start of every coding session before writing any code. Orients Claude in the file system, reads current status docs, and outputs a session context statement.
allowed-tools: Bash(ls:*), Read
---

## FeedPilot — Session Startup Protocol

### Steg 1 — Orientera i filsystemet

!`ls feedpilot/docs/tickets/`
!`ls feedpilot/backend/app/`
!`ls feedpilot/backend/app/services/`
!`ls feedpilot/backend/app/repositories/`
!`ls feedpilot/backend/app/api/`
!`ls feedpilot/frontend/app/`

### Steg 2 — Läs statusdokumenten (i denna ordning)

Läs dessa tre filer i sin helhet:

1. `feedpilot/docs/STATUS.md`
2. `feedpilot/docs/BACKLOG.md`
3. `feedpilot/docs/ROADMAP.md`

### Steg 3 — Beräkna nästa FEED-nummer

Räkna det högsta FEED-numret i `feedpilot/docs/BACKLOG.md` och i `feedpilot/docs/tickets/`. Nästa nummer = högsta + 1.

---

Baserat på ovanstående, skriv ut session context i detta exakta format:

```
SESSION CONTEXT
═══════════════════════════════════════
Current sprint:      [sprint-namn från ROADMAP.md]
Next FEED-number:    FEED-[XXX]
Working on:          [FEED-ticket om $ARGUMENTS angetts, annars "TBD — väntar på instruktion"]
Files to be touched: [lista om känt, annars "TBD"]
Risk level:          [low / medium / high, motivera kortfattat]
═══════════════════════════════════════
```

Om `$ARGUMENTS` innehåller ett FEED-nummer eller en beskrivning av vad som ska göras, inkludera det i "Working on" och lista relevanta filer.

**Påminn sedan om workflow-reglerna:**
- Ticket skapas och granskas INNAN kod skrivs (`/ticket-creator`)
- En fil i taget, vänta på godkännande mellan varje fil
- TDD — tester skrivs före implementation
