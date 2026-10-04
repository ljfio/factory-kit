# Changelog

## Unreleased

- Copilot cloud agent setup guide in `docs/agents.md`; `doctor` prints its prerequisites when `copilot` is enabled.
- `factory.py doctor`: read-only check of gh auth and scope, project, labels, milestones and the `claude`
  environment and secret, with the fix for each failure; exits non-zero when anything is missing.
- `init` keeps an existing `.factory/config.json` (merging the kit's defaults for missing keys) and `init --adopt`
  replaces already-present managed files, such as older skills, instead of writing `.factory-new`.
- Renaming `labels` (or any other render input) no longer reports the kit as having changed a scaffold: the manifest
  records the hash of the unrendered kit file for scaffolds.
- `exclude` now also removes an already-installed scaffold when unedited (kept and reported when edited), and a
  changed `exclude` triggers an update even when the kit is unchanged.
- Pointer files now import with `@./AGENTS.md` (Gemini documents only `./` and `../` forms). Codex and Gemini paths
  checked against vendor docs; sources in `docs/agents.md`.

## 0.2.0

- Agent-neutral: `agents` in config (`init --agents`, `factory.py agent add|remove`) for claude, codex, gemini,
  copilot and cursor. Skills are written once per directory the enabled agents read; the instruction block lives in
  one file (`instructions`) and other agents' files point at it. See `docs/agents.md`.
- `board.py` moved to `.factory/scripts/board.py` so no agent's directory holds it. `update` moves it and rewrites the
  skills; anything of yours that calls the old path must change.
- `claude.yml` ships only when `claude` is an enabled agent.
- Files removed by `update` no longer leave empty directories.
- The owner is chosen at install: `init --owner LOGIN`, default the user signed in to `gh` (before, it was the repo's
  account, wrong for organisation repos). Assignee, CODEOWNERS and the CI sender check use it. `project_owner` (set
  only when it differs; defaults to the repo's account) says who owns the project. `FACTORY_SOURCE` overrides the
  kit source; `FACTORY_OWNER` is now `FACTORY_PROJECT_OWNER`.
- Installers older than 0.2 can still update to this release (the kit keeps the `claude_md_block` key and layout).

## 0.1.2

Fix: managed files (including `factory.py`) are copied verbatim; only scaffolds are templated.

## 0.1.1

board.py: remove leftover Azure naming.



## 0.1.0

First release: nine skills, `board.py`, issue and PR templates, the owner-only CI agent
workflow, CODEOWNERS, and the `factory.py` installer and updater (`init`, `update`, `status`, `bootstrap`).
