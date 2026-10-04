# Agents

The kit is agent-neutral. `agents` in `.factory/config.json` lists which coding agents the project uses (default
`["claude"]`); `init --agents claude,codex` sets it, `factory.py agent add|remove NAME` changes it later.

## What each agent gets

Where an agent reads skills and instructions, checked against each vendor's documentation (October 2026):

| Agent | Skills directories it reads | Instruction file |
|---|---|---|
| `claude` | `.claude/skills/` | `CLAUDE.md` (supports `@file` imports) |
| `codex` | `.agents/skills/` | `AGENTS.md` |
| `gemini` | `.agents/skills/`, `.gemini/skills/` | `GEMINI.md` (`AGENTS.md` only via `context.fileName`; `@file` imports) |
| `copilot` | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `AGENTS.md`, `CLAUDE.md` or `GEMINI.md` (cloud agent) |
| `cursor` | `.agents/skills/`, `.cursor/skills/`, `.claude/skills/` | `AGENTS.md` |

The skills are written once per directory that some enabled agent needs, and no more: `claude,copilot,cursor`
installs only `.claude/skills/`; add `codex` and `.agents/skills/` appears too. Skills are `managed` files in every
directory, so the update rules are the same everywhere.

## Instructions

One file holds the managed workflow block and the project's rules: `instructions` in config. `init` picks
`AGENTS.md` when more than one instruction file would otherwise be needed, else the agent's own file. Every other
instruction file an enabled agent reads becomes a short pointer (`@AGENTS.md` plus a sentence). If you move an
existing `CLAUDE.md` to `AGENTS.md`, move your rules by hand.

## Agent-owned files

A scaffold that only makes sense for one agent ships only when that agent is enabled. Today that is
`.github/workflows/claude.yml` for `claude`. CI agents for other providers are planned (see `handoff.md`).

## Adding an agent to the kit

It is data, not installer code: add an entry to `kit.json` under `agents` with `skills` (directories it reads,
preferred first), `instructions` (its file) and optionally `files` (scaffolds it owns), then add it to the table
above and a test. The vendors' docs moved paths during 2026, so re-verify before trusting this table.
