---
name: work-package
description: Execute one work package or follow-up issue end to end - claim it, branch, implement, run the gates, report. Use with an issue number or a package id (for example "/work-package 14" or "/work-package W2").
argument-hint: <issue number or package id>
---

Execute **$ARGUMENTS**. The GitHub issue is the unit of work; the project board is where "in progress" and "done" are recorded.

## 1. Resolve and check
- A number is the issue. An id like `W2` is found with `gh issue list -R "$(python3 .factory/scripts/board.py repo)" --state all --search "W2: in:title"`. Read it with `gh issue view N --comments`.
- Read `CLAUDE.md`, the package's section in the plan the issue links (for example `docs/plan.md`), every design doc the issue links, any `CLAUDE.md` in the folders you touch, and any ADR it cites.
- `python3 .factory/scripts/board.py deps N`: every dependency must be closed or `offline-done`. If not, stop and report which. Refuse env-gated issues (the `labels.env_gated` label) unless the user confirms an environment exists.
- Check open decisions that affect it (see the issue's text and `gh issue list --label decision-needed`). Proceed on the stated default if it is safe under the CLAUDE.md rules; otherwise stop and report.

## 2. Claim it (so ongoing work is visible)
- Every comment you post starts with `**[Claude]**` (it posts as the owner's account; the marker is how `board.py inbox` tells your comments from the owner's replies).
- `python3 .factory/scripts/board.py status N in-progress`
- Branch `wp/<id>-<slug>` from `main` (id lower-cased for follow-ups: `wp/fu-<slug>`). If you are already in a worktree on a `wp/*` branch, use it.
- Comment on the issue: `gh issue comment N -b "**[Claude]** Started on branch wp/<id>-<slug>."`

## 3. Implement
Exactly the issue scope. Follow the rules in CLAUDE.md and the folder rules. Write the tests the issue lists. Match the surrounding code's naming and comment density. Commit in small commits; reference the issue (`Refs #N`).

Tracking while you work:
- A new open question or choice the owner should make: use the `raise-decision` skill, then carry on with the default.
- Work you found but will not do here, and anything you could not verify against the real environment: use the `new-work-item` skill (parent: the `verification_epic` for verification items). Do **not** write status notes, TODO lists or open questions into docs.
- Tick finished items in the issue's checklist as you go (`gh issue edit N --body-file`) or comment with progress for long packages.
- Do not write ADR files and do not number decisions. ADRs are written by `add-adr` from the main checkout.

## 4. Gates
Run every gate in the Gates section of `CLAUDE.md` that applies to what you touched. Fix failures; never skip or weaken a test. Record what you ran.

## 5. Docs
Fix any doc the change made wrong (design docs, the plan if the package scope truly changed, READMEs). Docs describe the design and plan; they never carry status.

## 6. Finish
Do **not** close the issue from here: it closes when the pull request is merged.
- Leave the issue In Progress. Comment (starting **[Claude]**): branch, commits, gates run and their results, what could not be verified and the follow-up issues created, decisions raised.
- Push the branch and open a pull request `git push -u origin wp/<id>-<slug>`, then `gh pr create --body-file` with the sections of `.github/pull_request_template.md` filled in and `Closes #N` at the top, so the merge closes the issue. A worker agent in a worktree (see `run-parallel`) does not push; its orchestrator does.
- Merge only if the user asked you to: `gh pr merge --merge` once the checks pass, then `python3 .factory/scripts/board.py status N done`. Without a remote, or if they ask for a local merge: `git merge --no-ff wp/<id>-<slug>`, re-run the gates on `main`, close the issue with `gh issue close N -c "Merged <sha>. Gates: <summary>."`.
- If the package cannot be completed as written: `gh issue edit N --add-label blocked`, comment the reason, `board.py status N todo`, stop. Do not change scope quietly.

## 7. Report
What changed, what you verified and how, what you could not verify, decisions raised (issue numbers), follow-ups created (issue numbers).
