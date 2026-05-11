---
name: codex-review
description: Codex-review guidelines for FeedPilot. Claude should follow these rules automatically when writing or modifying code.
user-invocable: false
---

Allowed tools: Bash(git diff:_), Bash(git status:_), Bash(git log:\*)

Current changes
!git diff HEAD

Status
!git status

Recent commits
!git log --oneline -5

Format the above for a Codex (ChatGPT) senior code review of the FeedPilot codebase.

Structure the output as:

What changed
Brief summary of what was modified and why.

Layer context
Which layer(s) does this touch? (API / Service / Repository / Model / Schema / Worker / Frontend)

Architecture checklist
No business logic in API routes
No DB queries in services
CanonicalProduct used as AI input (not raw ORM)
AI output validated via Pydantic before persistence
max_tokens = 4096
job.result only written after full run
Token usage logged per enrichment call
No Mapped[] in ORM models
Specific things to verify
List any async correctness concerns, tenant isolation, ARQ task signatures, or enrichment pipeline steps involved.

Diff
Paste the raw diff below for Codex to read.

$ARGUMENTS
