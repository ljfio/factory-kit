---
name: raise-decision
description: Raise an open question or a choice for the owner as a decision-needed GitHub issue (assigned to the owner) instead of writing it into a doc. Use whenever work hits a decision that is not yours to make, or you need to record a decision you made inside a package.
argument-hint: <short question>
---

Open questions never go into files. They are issues with the `decision-needed` label, assigned to the owner (`owner` in `.factory/config.json`), on the project board.

## Open question for the owner
1. Check it is not already asked: `gh issue list -R "$(python3 .claude/scripts/board.py repo)" --label decision-needed --search "<keywords>" --state all`. Comment on the existing one instead of duplicating.
2. Fill the template: `python3 .claude/scripts/board.py template decision > <file>` (scratchpad), replacing every placeholder and keeping every `###` section (Question with the options and the cost or risk of each, Default until decided, Needed by, Affects). The default must satisfy the rules in CLAUDE.md.
3. Create it (assigned to the owner and labelled `decision-needed` by the template; put on the board as Todo):
   ```
   python3 .claude/scripts/board.py new decision --title "<the question, short>" --body-file <file> \
     --area <x> [--milestone "<milestone it is needed by>"]
   ```
   Add `--dry-run` first to see what would be sent.
4. Mention it on the issue you are working (`gh issue comment`) with the default you are proceeding on. If the default would break a rule in CLAUDE.md, do not proceed: add the decision to the dependent issue's `### Depends on` list so the board shows it waiting, and stop that item.

## A decision you made inside a package
Technical choices within your scope are yours. Record them so the orchestrator can write the ADR: fill `board.py template decided` (Decision, Why, Alternatives considered) and run
`python3 .claude/scripts/board.py new decided --title "<decision>" --body-file <file> --from <package issue>`. It creates the issue labelled `decided` with no assignee and closes it (`Decided in #<package issue>`). `board.py adr-pending` will list it and `add-adr` turns it into a record. Never write the ADR file yourself.
