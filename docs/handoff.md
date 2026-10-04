# Handoff

Written for the next session working in this repo. Written at v0.1.2; the agent-neutral work below landed in 0.2.0 (unreleased until tagged), see `docs/agents.md`.

Full guide to how it works and how to continue: [`development.md`](development.md).

## What this is and why

The kit's author built an agent-driven delivery workflow inside one of their own projects: GitHub issues
and a project board are the record of work, Claude skills pick up issues, build on `wp/<id>-<slug>` branches and
open pull requests, the owner steers by commenting, and an owner-only `@claude` workflow runs Claude Code in
Actions on their subscription. This repo extracts that into a generic kit so any project can install it and pull
improvements. The original project is the first adopter, but it must not be named in this repo.

## State at v0.1.2

- Public repo `ljfio/factory-kit`, MIT, `main` plus tags `v0.1.1` and `v0.1.2`. CI (`.github/workflows/ci.yml`)
  runs the unit tests and `py_compile`; it was green.
- History was rewritten once on request (single clean commit, project name removed, old `v0.1.0` tag deleted, then a
  normal commit for 0.1.2). Anyone who cloned before that must re-clone.
- The first adopter installed v0.1.2 from the GitHub tag and has the kit's workflow running locally against its real
  project board (`board.py repo|ready|board` verified). Its adoption pull request is open and unmerged.
- Not verified: the `@claude` CI workflow has never run on GitHub (it needs to be on the default branch of a project
  with the `claude` environment and `CLAUDE_CODE_OAUTH_TOKEN` set); a full `work-package` cycle using the kit's
  skills in a fresh session; `factory.py bootstrap` (labels and milestones) has not been run against GitHub.

## How the installer works (`factory.py`)

- `init`: needs a git repo, `gh`. Resolves `owner/name` (from `--repo` or `gh repo view`), asks `gh api users/<owner>`
  for the numeric id, shallow-clones the source at `--ref` (default: highest `vX.Y.Z` tag, else `main`), writes
  `.factory/config.json`, installs every file under `kit/` plus `factory.py` as `.factory/factory.py`, inserts the
  `CLAUDE.md` block between `<!-- factory-kit:begin -->` and `<!-- factory-kit:end -->`, and writes
  `.factory/manifest.json` (source, ref, version, commit, per-file sha256 and kind; scaffolds also `raw`, the hash of
  the unrendered kit file, which is what decides "the kit changed this scaffold" so renaming `labels` is not a kit change;
  manifests from before `raw` was recorded compare rendered hashes once).
- File kinds come from `kit.json`: **managed** (skills, `board.py`, `factory.py`) are replaced on update when the
  project has not edited them; **scaffold** (everything else under `kit/`) is created once. The manifest hash is the
  hash of what the kit offered, not of the local file, so "project edited it" and "kit changed it" can be told apart.
- `update`: no-op when the commit, the agents and `exclude` are unchanged (the manifest records the last two). Per file: missing locally and in manifest, deleted by the project
  and skipped unless `--force`; managed and unedited, replaced; managed and edited with the kit also changed,
  conflict (`<file>.factory-new`); managed and edited with the kit unchanged, kept; scaffold changed by the kit,
  `.factory-new`; a managed or scaffold file removed from the kit, or newly excluded, is deleted (and dropped from the manifest) when
  unedited, and kept and reported when edited. New config keys are merged in.
- `init` keeps an existing `.factory/config.json` (existing values win, the kit's defaults fill gaps, objects such as
  `labels` merge one level deep; `--repo`, `--owner`, `--project`, `--agents` override). `init --adopt` takes the
  kit's version of managed files that already exist without a manifest entry (older skills) instead of writing
  `.factory-new`; scaffolds that exist are still kept.
- `exclude` in config (path prefixes) skips files. `status` lists missing or edited managed files and pending
  `.factory-new` files. `bootstrap` creates labels and milestones with `gh`.
- `--source` accepts a git URL or a local path (tests and local development use a path).

## `board.py` (installed at `.factory/scripts/board.py`)

Reads `.factory/config.json` from two directories above itself (`ROOT = parents[2]`): `repo`, `owner`, `project`,
`areas`, `waves`, `labels`. Env overrides `FACTORY_REPO`, `FACTORY_OWNER`, `FACTORY_PROJECT`. With no `project`,
status changes print a notice and do nothing. Commands: `ready`, `board`, `decisions`, `inbox`, `adr-pending`,
`deps`, `status`, `sub`, `template`, `new`, `repo`, `project-url`. `inbox` relies on every Claude comment starting
with `**[Claude]**` (Claude and the owner post as one account). The issue templates use `{{owner}}` for the
assignee, so `board.py new` gets it from the rendered template.

## Decisions already made (do not relitigate without the owner)

- Generic skills plus per-project config, not per-project forks of the skills.
- The pull-request flow is the default (agents open PRs, the owner merges); local merging is only a fallback in
  `work-package` and `run-parallel` when there is no remote.
- Labels for "needs the real environment" are configurable (`labels.env_gated`, `labels.needs_env`, defaults
  `env-gated` and `needs-env`); skills refer to them generically.
- Issue templates, PR template, `claude.yml` and CODEOWNERS are scaffolds (the project owns them after install).
- CI agent safety model: job-level check on the immutable sender id, environment-scoped OAuth secret limited to the
  default branch, action pinned to a commit, `issue_comment` only, merge/api/secret commands disallowed. See
  `docs/ci-agent.md`.
- MIT licence, name `factory-kit`.
- No remote piping: an attempt to run `curl ... | python3 - init` was blocked by the permission classifier in the
  session, so installs in agent sessions use a local checkout (`python3 /path/to/factory.py init --source <url>`).
  The README still documents the one-liner for humans. Do not try to work around that block.

## Known issues and rough edges

1. The `CLAUDE.md` block duplicates a skills table if the project already has one; the adopter removed its own.
2. `status` has no verbose mode (`-v` is parsed but unused).
3. `claude.yml` ships without toolchain setup steps; projects must add `setup-*` steps and `--allowedTools` entries.
4. Python 3.8+ is assumed; tested on 3.9 (macOS system Python) and 3.12 (CI).
5. `board.py` classifies only issues labelled `work-package` or `follow-up`; epics, decisions and owner actions are
   deliberately excluded from `ready`.

## Done in 0.2.0: agents

`agents` and `instructions` config, an agent registry in `kit.json`, skills fanned out per needed directory,
pointer files, agent-owned scaffolds, `agent add|remove`. Paths verified against vendor docs (see `docs/agents.md`).
Compatibility with old installers was tested by hand (old `update` against the new kit); the kit keeps the
`claude_md_block` key and the `kit/.claude/skills` layout for that reason. Do not rename them without a plan.

## Next piece of work

1. **Dogfood.** Install the kit into this repo (`init --source . --agents claude`), create a project board, and file
   the items below as issues so `work-package` builds them.
2. **CI agent per provider** (`codex`, `gemini`, `copilot`), same controls as `claude.yml` (sender-id check,
   environment-scoped secret, pinned action commit). Codex and Gemini use API keys, not subscription tokens.
3. **Forge seam**: skills still call `gh` in about 26 places. Route everything through `board.py`, then add GitLab
   and Azure DevOps backends behind it. Contract tests run against fake CLIs.
4. The `**[Claude]**` comment marker is still Claude-named; make it configurable (`marker`).

## Other candidates

- Fix known issues 1 to 3.
- A `factory.py doctor` that checks `gh` auth and the `project` scope, the `claude` environment and secret, and
  labels, and says what is missing.
- A `factory.py remove` that deletes managed files using the manifest.
- Move more skill detail into config where a second project would need it.

## Working here

Read `CLAUDE.md` for the rules. Tests clone `HEAD`, so commit before running them. The owner's account id and login
are inputs to `init` (via `gh`), never hard-coded in the kit. Owner preferences seen so far: concise reports, pull
requests reviewed by the owner before anything merges, nothing merged or released without being asked, and every
comment Claude posts to an issue starts with `**[Claude]**`.
