---
name: ticket-creator
description: Create a new FEED-XXX ticket before starting any implementation. Use when about to start a new feature, bug fix, or investigation. Reads BACKLOG.md to determine the next ticket number and generates a complete ticket file in docs/tickets/.
allowed-tools: Bash(ls:*), Bash(grep:*), Read, Write
---

## FeedPilot — Ticket Creator

Beskrivning av arbetet: $ARGUMENTS

### Steg 1 — Hitta nästa FEED-nummer

!`grep -oE "FEED-[0-9]+" feedpilot/docs/BACKLOG.md | sort -t- -k2 -n | tail -1`
!`ls feedpilot/docs/tickets/ | grep -oE "FEED-[0-9]+" | sort -t- -k2 -n | tail -1`

Nästa FEED-nummer = det högsta av de två ovanstående + 1. Paddas till tre siffror (t.ex. FEED-074).

### Steg 2 — Läs kontext

Läs dessa filer för att förstå vad som redan finns:

- `feedpilot/docs/STATUS.md` — verifierat läge
- `feedpilot/docs/BACKLOG.md` — undvik dubletter

### Steg 3 — Generera ticket

Skapa filen `feedpilot/docs/tickets/FEED-[NNN]-[kort-slug].md` med exakt detta format:

```markdown
# FEED-[NNN] — [Titel]

## Status

Open

## Ägare

- Implementation: Claude Code
- Review/test/arkitekturkontroll: Codex

## Bakgrund

[Förklara varför detta behövs. Vad är nuläget? Varför är detta ett problem?]

## Problem

[Exakt vad som är fel eller saknas idag.]

## Mål

[Vad ska vara sant när ticketen är klar?]

## Berörda filer

Claude Code får bara ändra en fil i taget.

Primär fil:
- [fil-path]

Tillåtna efter separat godkännande:
- [eventuella tilläggsfiler]

## Krav

[Numrerade, konkreta krav. Varje krav ska vara verifierbart.]

## Acceptance Criteria

- [ ] [Mätbart krav 1]
- [ ] [Mätbart krav 2]
- [ ] Alla befintliga tester passerar
- [ ] `docs/STATUS.md` och `docs/BACKLOG.md` uppdaterade

## Testkrav

[Vilka tester ska köras för att verifiera ticketen?]

```bash
docker compose exec backend pytest tests/
cd frontend && npm run lint && npm test -- --runInBand
```

## Risker

- [Risk 1 — hur den mildras]
- [Risk 2 — hur den mildras]

## Definition of Done

- [ ] Ticket skapad och granskad innan kod skrevs
- [ ] TDD — tester skrivna innan implementation
- [ ] Layer separation respekterad
- [ ] AI-output valideras via Pydantic innan persistering (om relevant)
- [ ] Claude Code har implementerat en fil i taget
- [ ] Codex har reviewat och kört verifiering
- [ ] `docs/STATUS.md` och `docs/BACKLOG.md` uppdaterade
```

### Steg 4 — Lägg till i BACKLOG.md

Läs `feedpilot/docs/BACKLOG.md` och lägg till ticketen under rätt sprint-sektion med status `⬜ Open`.

---

**Skriv INTE någon kod. Presentera ticket-filen för granskning och vänta på godkännande innan implementation påbörjas.**

Avsluta med:
```
Ticket: feedpilot/docs/tickets/FEED-[NNN]-[slug].md

Granska ticket-innehållet ovan.
Skriv "ok" för att jag ska spara filen och uppdatera BACKLOG.md.
Skriv "ändra [vad]" för att justera innan det sparas.
```
