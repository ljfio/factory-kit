---
name: next-item
description: Pick the next work package or follow-up to build. Use when asked to "pick up the next item", "what should I work on", or at the start of an unplanned session. Recommends one item (or a safe parallel set) and can hand off to work-package.
---

1. Run `python3 .factory/scripts/board.py ready`. If `board.py board` shows something **In progress** that has no active session (a `wp/*` branch exists, nobody working), offer `continue-work` first: finishing beats starting.
2. For the top candidates read the issue (`gh issue view N`) and check:
   - dependencies are met (`board.py deps N`; closed or `offline-done`),
   - a **decision** that affects it is open (`gh issue list --label decision-needed --search "#N"` and the issue's own text). If the default in that decision is safe (the rules in CLAUDE.md hold) the item can go ahead on the default and the decision stays open; if not, say it is blocked on that decision.
3. Choose by this order: it unblocks the most other items; earlier wave (milestone order); smaller size when equal. Do not pick env-gated items (they need a deployed environment) or anything labelled `blocked`.
4. Present **one recommendation** with a one-line reason and the next two alternatives. If several ready items are independent (different areas, no dependency between them, not both touching the `hotspots` in `.factory/config.json`), say they can run in parallel and point to `run-parallel`.
5. If the user (or the loop prompt) already said to proceed, hand off to the `work-package` skill with the issue number. Otherwise ask which one.

Never start work from this skill; `work-package` does the claiming and the branch.
y
