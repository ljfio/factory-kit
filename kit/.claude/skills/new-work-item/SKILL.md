---
name: new-work-item
description: Create a tracked work item (follow-up, bug, verification, chore) as a GitHub issue on the project board, linked under its epic. Use when work is found that will not be done in the current package, or when asked to "add a task/issue for this".
argument-hint: <title>
---

Anything not done now becomes an issue, not a note in a doc or a TODO comment. Issues are created from the templates in `.github/ISSUE_TEMPLATE/` through `board.py new`, so the web form and this skill produce the same shape.

1. Check for duplicates: `gh issue list -R "$(python3 .claude/scripts/board.py repo)" --state all --search "<keywords>"`.
2. Pick the **type**: `follow-up` (non-plan work or a bug), `verification` (built without the real environment, not verified against it; adds the needs-env label), `work-package` (only when the plan gains a package), `owner-action` (only the owner can do it). `python3 .claude/scripts/board.py template` lists them. An open question is `raise-decision`, not this.
3. Pick: **area** (one of `areas` in `.factory/config.json`), **size** (`S|M|L`), **milestone** (the wave: `gh api repos/$(python3 .claude/scripts/board.py repo)/milestones --jq '.[].title'`), **parent epic** (the epic named in `.factory/config.json` `verification_epic` for anything "not verified against the real environment", else the epic of its area: `gh issue list -R "$(python3 .claude/scripts/board.py repo)" --label epic`). Add the env-gated label with `--label` if it cannot even start without a deployed environment.
4. Fill the template: `python3 .claude/scripts/board.py template <type> > /tmp/body.md` (use the scratchpad), replace every placeholder and keep every `###` section. List blockers under `### Depends on` as `- #N title` (the board reads this); a verification item lists its checks as `- [ ]` lines.
5. Create it (labels and assignee come from the template; the body is checked for the template's sections; it goes on the board as Todo and under its parent):
   ```
   python3 .claude/scripts/board.py new <type> --title "<title>" --body-file <file> \
     --area <a> --size <S|M|L> --milestone "<wave>" --parent <epic>
   ```
   Add `--dry-run` first to see what would be sent. Do not assign it to the owner unless the type does (`owner-action`).
6. Reference it from where it came from (comment on the originating issue, starting `**[Claude]**`).
