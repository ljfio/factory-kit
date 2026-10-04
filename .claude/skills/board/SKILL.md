---
name: board
description: Show what is ongoing, ready, waiting, blocked and which decisions are waiting for the owner, from the GitHub project. Use when asked for status, "where are we", "what's in progress", or before planning work.
---

The GitHub issues and the project board (`python3 .factory/scripts/board.py project-url`) are the record of what is done, ongoing and next. There is no status file.

1. Run `python3 .factory/scripts/board.py board` and `python3 .factory/scripts/board.py adr-pending`.
2. Summarise in a few lines, not a dump: what is **in progress** (and whether a `wp/*` branch or worktree exists for it: `git branch --list 'wp/*'`, `git worktree list`), what is **ready**, which decisions block the most work (`board.py decisions`, then see which waiting items name them), anything **blocked**, and any decided issue still **missing an ADR**.
3. Recommend the next move: usually the `next-item` skill; `add-adr` if ADRs are pending; or a reminder that decisions are waiting for the owner.

Read only. Do not change statuses here.
x
