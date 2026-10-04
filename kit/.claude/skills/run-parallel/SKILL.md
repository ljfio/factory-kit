---
name: run-parallel
description: Orchestrate several independent ready issues in parallel - one isolated worktree agent per issue, then review, gate and merge each. Use when asked to deliver work in parallel, run an agent loop, or "work through the ready items". Pair with /loop for repeated passes.
argument-hint: [max agents, default 3]
---

You are the orchestrator. You own the main checkout, merging, ADRs and the board. Worker agents own one issue each and never merge, never write ADRs.

## 1. Choose the batch
1. `python3 .claude/scripts/board.py board` (also `adr-pending`; write pending ADRs first with `add-adr`).
2. From **Ready**, pick up to the max (default 3) that are independent: no dependency between them, different areas where possible. The paths in `hotspots` in `.factory/config.json` are merge hotspots, so never run two issues that both change them (read each issue's scope to tell). If unsure, run them in sequence.
3. Skip env-gated (`labels.env_gated`), `blocked`, anything with an unsafe open decision (see `next-item` step 2). If nothing is eligible, say so and stop; that is the loop's stop condition.

## 2. Launch workers
For each chosen issue, in **one message** (so they run concurrently), call the Agent tool with `isolation: "worktree"` and run in the background. Prompt:
> Run the `work-package` skill for issue #N in this worktree. Branch `wp/<id>-<slug>`. Do **not** merge, push, close the issue, or write ADR files. Raise decisions with `raise-decision` and follow-ups with `new-work-item`. Finish with the report from step 7 of the skill, including the exact gates you ran and their results.

## 3. Integrate each result (as it arrives, one at a time)
1. Read the report. Check `git log main..wp/<branch> --oneline` and `git diff main...wp/<branch> --stat`; open the diff where the change is risky (security, secrets, data isolation, and every rule in CLAUDE.md).
2. In the main checkout, gate the merge result: `git merge --no-ff wp/<branch>` on a scratch branch (or, with a remote, check the pull request's CI), resolve conflicts, regenerate generated files (the project's gates say how), then run the full gates from CLAUDE.md. If they fail and the fix is not trivial, abort or reset, comment on the issue, label `blocked`, and move on. Then push the branch and open the pull request (`Closes #N`, template filled in); merge it with `gh pr merge --merge` only when the user asked for merging, otherwise leave it for the owner. Without a remote, merge locally to `main` as before.
3. On a merge: `python3 .claude/scripts/board.py status N done` and `gh issue close N -c "**[Claude]** Merged <sha>. Gates: <summary>. Not verified: <list or none>."`. Remove the worktree and branch.
4. Handle what workers raised: new decision issues stay open for the owner; `decided` ones go through `add-adr` now; follow-up issues are already on the board.

## 4. Report and loop
Report per issue: merged or not, gates, follow-ups, decisions waiting for the owner. Then `board.py ready` for newly unblocked items. Continue only if the user asked for a loop (`/loop` with this skill) and eligible work remains; stop when nothing is eligible, when a gate failure needs the owner, or after the batch if no loop was requested.

Notes: work reaches `main` through pull requests ; never push `main` itself unless the user asks. Keep concurrency modest, and never let two workers run test suites that share one stateful resource (a local emulator, a database, a port); `notes` in `.factory/config.json` lists any such constraints.
