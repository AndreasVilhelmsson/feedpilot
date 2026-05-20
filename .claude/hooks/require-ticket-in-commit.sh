#!/bin/bash
# PreToolUse hook — kräver FEED-XXX eller closes #N i git commit-meddelanden.
#
# Hur det fungerar:
#   Claude Code skickar JSON på stdin innan varje verktygsanrop.
#   Vi läser kommandot, kontrollerar om det är ett git commit,
#   och blockerar om ticket-referens saknas.
#
# Exit codes:
#   0  = tillåt anropet
#   2  = blockera anropet, visa stdout som fel till Claude

INPUT=$(cat)

# Extrahera kommandot ur JSON-input
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

# Hoppa över om det inte är ett git commit
if ! echo "$COMMAND" | grep -qE "git commit"; then
    exit 0
fi

# Tillåt om meddelandet redan innehåller en ticket-referens
if echo "$COMMAND" | grep -qE "(FEED-[0-9]+|closes? #[0-9]+|fix(es)? #[0-9]+)"; then
    exit 0
fi

# Blockera och förklara
cat <<'EOF'
Hook: require-ticket-in-commit
──────────────────────────────────────────────────────────────
Commit-meddelandet saknar ticket-referens.

Lägg till ett av följande:
  • FEED-XXX          → refererar ett lokalt ticket
  • closes #N         → stänger ett GitHub Issue automatiskt vid merge

Exempel:
  git commit -m "ci: fixa health check path (FEED-039)"
  git commit -m "feat: JWT login endpoint (closes #1)"

Commit blockerad.
──────────────────────────────────────────────────────────────
EOF

exit 2
