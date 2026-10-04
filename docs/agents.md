# Agents

The kit is agent-neutral. `agents` in `.factory/config.json` lists which coding agents the project uses (default
`["claude"]`); `init --agents claude,codex` sets it (an existing config's `agents` is kept when the flag is omitted), `factory.py agent add|remove NAME` changes it later.

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
instruction file an enabled agent reads becomes a short pointer (`@./AGENTS.md` plus a sentence; the `./` form is the one Gemini documents). If you move an
existing `CLAUDE.md` to `AGENTS.md`, move your rules by hand.

## Agent-owned files

A scaffold that only makes sense for one agent ships only when that agent is enabled. Today that is
`.github/workflows/claude.yml` for `claude`. CI agents for other providers are planned (see `handoff.md`).

## Copilot cloud agent

Nothing is installed for it (no workflow, no scaffold): GitHub starts it when an issue is assigned to Copilot, so
`work-package` issues are picked up by assigning them to Copilot rather than by a label or comment trigger. Facts
below are from GitHub's documentation (October 2026; sources at the end of this file):

- Available on all paid Copilot plans; on Business and Enterprise an administrator must enable the policy, and a
  repository can opt out. The owner has to confirm both; `doctor` prints them as notes when `copilot` is enabled.
- It works in an ephemeral environment powered by GitHub Actions and opens a pull request.
- It reads repository instructions from `AGENTS.md` (any number, anywhere in the repository), or a single root
  `CLAUDE.md` or `GEMINI.md`, as well as `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md`.
  The kit's pointer files cover `AGENTS.md`/`CLAUDE.md`. It can use agent skills (directories in the table above).
- Not verified: how issue assignment is done from the API or `gh`, who may assign, and whether workflows on its pull
  requests need approval before they run. Tracked in a follow-up issue.

## Adding an agent to the kit

It is data, not installer code: add an entry to `kit.json` under `agents` with `skills` (directories it reads,
preferred first), `instructions` (its file) and optionally `files` (scaffolds it owns), then add it to the table
above and a test. The vendors' docs moved paths during 2026, so re-verify before trusting this table.

## Sources checked (October 2026)

- Codex reads `AGENTS.md` from `~/.codex/` (an `AGENTS.override.md` wins), then walks from the Git root down to the
  working directory taking `AGENTS.override.md`, else `AGENTS.md`, else a `project_doc_fallback_filenames` name, one
  file per directory, concatenated root first, capped at 32 KiB by default
  ([Codex AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)). Codex documents no `@file`
  import, so a pointer file is only read as text; that is why the pointer sentence names the file in words too. Keep
  the managed block small.
- Gemini CLI imports with `@./file.md`, `@../file.md` or an absolute path, ignores `@` inside code, and stops at depth 5
  ([Memory Import Processor](https://geminicli.com/docs/reference/memport/)). A bare `@AGENTS.md` is not a documented
  form, so pointers use `@./AGENTS.md`.
- Copilot cloud agent: [About Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)
  (assign an issue to Copilot, paid plans, administrator policy, Actions-powered environment, skills) and
  [Add repository custom instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)
  (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`).
