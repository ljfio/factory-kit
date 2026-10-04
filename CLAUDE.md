# factory-kit: working rules for agents

This repo is the source of a reusable GitHub delivery workflow for Claude Code (skills, `board.py`, issue and PR
templates, an owner-only CI agent workflow, CODEOWNERS) and the `factory.py` installer and updater. Projects
install it with `factory.py init` and pull updates with `factory.py update`. Read [`docs/handoff.md`](docs/handoff.md)
first: it has the current state, decisions, gotchas and the next piece of work. [`README.md`](README.md) is the
user-facing description.

## Layout

| Path | What |
|---|---|
| `factory.py` | Installer and updater (stdlib Python 3.8+, plus `git` and `gh`). Copied into projects as `.factory/factory.py` |
| `kit.json` | Which kit paths are `managed`, the agent registry, and which file holds the instruction block |
| `kit/` | The payload, laid out as it lands in a project (`.claude/`, `.github/`, `.factory/`) |
| `tests/test_factory.py` | Installer tests; use a fake `gh` and clone this repo as the kit source |
| `docs/` | `customising.md`, `agents.md`, `ci-agent.md`, `handoff.md` |
| `VERSION`, `CHANGELOG.md` | Release metadata; `update` follows the latest `vX.Y.Z` tag |

## Rules

1. **Skills stay project-neutral.** No project names, paths, label names or tooling in `kit/.claude/skills/`. Project
   specifics go in `.factory/config.json` (read by `board.py`) or in the project's `CLAUDE.md`. Skills say "the rules
   in CLAUDE.md" and "the Gates section".
2. **No project names anywhere** in files or commit messages (this repo is public and generic).
3. **Managed files are copied verbatim**, never templated (`factory.py` contains the placeholders itself). Only
   scaffolds get `{{repo}}`, `{{owner}}`, `{{owner_id}}`, `{{label_needs_env}}`, `{{label_env_gated}}` filled in.
4. **Never overwrite a file the project changed.** Conflicts become `<file>.factory-new`. Keep it that way.
5. **Stdlib only.** No third-party Python packages; the installer must run from a bare checkout.
6. **GitHub is the only state.** No status files or databases in the kit or in what it installs.
7. A new key in `kit/.factory/config.json` must have a safe default, because `update` adds it to existing projects.
8. Do not publish the owner-only CI workflow with weaker controls (account-id check, environment-scoped secret,
   pinned action commit, no `pull_request_target`).

## Verify before you release

```bash
python3 -m unittest discover -s tests        # needs git only; CI runs the same
python3 -m py_compile factory.py kit/.factory/scripts/board.py
```

Also install into a scratch git repo (`python3 factory.py init --repo owner/name --source . --ref main` with a
fake or real `gh`) and run `update` after a kit change. The tests overlay the working tree onto a clone, so uncommitted changes are tested.

## Release

Bump `VERSION`, add a `CHANGELOG.md` entry, commit, tag `vX.Y.Z`, push `main` and the tag. Commit messages end with
the Co-Authored-By and Claude-Session trailers given in the session. Do not force-push or move tags unless the
owner asks.
