---
name: add-adr
description: Record a decided matter as an ADR in docs/adr and close the loop on its issue. Use when the owner has answered a decision-needed issue, when board.py adr-pending lists decided issues, or when asked to "add an ADR" or "record this decision".
argument-hint: <decision issue number>
---

The ADR directory (`adr_dir` in `.factory/config.json`, default `docs/adr`) holds only what has been **decided**, one file per decision, never edited after acceptance except to mark it superseded. Write ADRs only from the main checkout, one at a time, so numbers cannot collide (parallel work-package agents never write ADRs).

1. **Get the decision.** `gh issue view N --comments`. It must be settled: an owner comment that answers it (quote it), or the issue is `decided` with a Decision section. If the owner has not answered, stop and say so. No ADR for an open question.
2. **Number.** Take the highest number in `docs/adr/` plus one (`ls docs/adr | sort | tail -1`), four digits. Never reuse or renumber. 
3. **Write** `docs/adr/NNNN-<short-slug>.md`:
   ```
   ---
   status: accepted
   date: <today, YYYY-MM-DD>
   decider: owner | agent
   issue: <N>
   supersedes: [NNNN]      # only if it replaces one
   ---

   # NNNN. <Title: the decision, not the topic>

   ## Context
   <the forces, 2 to 6 lines; link the architecture doc and plan package>

   ## Decision
   <what we do, in the active voice, including the owner's answer verbatim if given>

   ## Consequences
   <what changes, what we accept, what to revisit and when; link follow-up issues>

   ## Alternatives considered
   <short list, why not>
   ```
   Keep it to what a reader needs a year from now; do not paste the discussion.
4. **Index.** Add the row to `docs/adr/README.md` (`| [NNNN](file) | title | accepted | date |`), keeping the table sorted.
5. **Superseding.** If it replaces an earlier ADR, set that file's `status: superseded by NNNN` (the one permitted edit) and update its index row.
6. **Docs.** If the decision makes an architecture doc or `docs/plan.md` wrong, fix it in the same commit and link the ADR from the doc.
7. **Close the loop on GitHub:** `gh issue edit N --remove-label decision-needed --add-label decided --add-label adr-recorded`, then `gh issue close N -c "**[Claude]** Recorded as ADR NNNN: docs/adr/<file>"` (for an issue already closed, just fix the labels and comment). If follow-up work follows from the decision, create it with `new-work-item`.
8. Commit: `ADR NNNN: <title>` with `Refs #N`.

Check at the end: `python3 .factory/scripts/board.py adr-pending` should no longer list the issue.
z
