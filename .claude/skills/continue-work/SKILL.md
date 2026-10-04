---
name: continue-work
description: Resume development that is already in progress - find the issue, branch and state, then carry on. Use when asked to "continue", "carry on", or after a session was interrupted.
---

1. Find what is in progress:
   - Current branch: `git branch --show-current`. A `wp/<id>-<slug>` branch maps to an issue (`gh issue list -R "$(python3 .factory/scripts/board.py repo)" --search "<ID>: in:title" --state all`).
   - Otherwise `python3 .factory/scripts/board.py board` (the In progress section) plus `git branch --list 'wp/*'` and `git worktree list`. If several, ask which; if none, use `next-item`.
2. Rebuild context: `gh issue view N --comments` (acceptance, checklist, started and progress comments), `git log --oneline main..HEAD`, `git status`, `git diff --stat main...HEAD`, and the docs the issue links.
3. Establish where it stands: run the build and the tests for the area (the CLAUDE.md gates that apply). Compare the diff with the issue's acceptance criteria and checklist; list what is done, what is left, and anything broken.
4. Say in two or three lines what remains, then continue by following steps 3 to 7 of the `work-package` skill (implement, tracking, gates, docs, finish, report). Do not re-claim the issue; it is already In Progress.
5. If the branch has diverged from `main` (other work merged), rebase or merge `main` in first and re-run the gates before going on.
