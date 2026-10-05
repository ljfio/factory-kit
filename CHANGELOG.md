# Changelog

## Unreleased

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
