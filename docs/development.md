# How it works and how to keep developing it

This is the long-form guide. [`README.md`](../README.md) says what the kit is, [`agents.md`](agents.md) covers agent
support, [`customising.md`](customising.md) covers per-project settings, [`ci-agent.md`](ci-agent.md) covers the CI
workflow, [`handoff.md`](handoff.md) is the short state-of-play. Read this when you want to change the kit itself.

## 1. The model in one page

A project installs the kit once and then runs its work through GitHub:

```
   issues + project board  <-- the only state (no status files, no database)
        ^            |
        |            v
   board.py     skills (agent-readable procedures)  -->  branches wp/<id>-<slug>  -->  pull request "Closes #N"
        ^                                                                                    |
        |                                                                                    v
   .factory/config.json  (repo, owner, project, areas, waves, hotspots, labels, agents)   owner reviews and merges
```

- **The owner** is one person (`owner` in config, chosen by `init --owner`, default your `gh` login). Only the owner's
  comments are instructions. The owner steers by commenting on issues and merging pull requests.
- **The agent** (Claude, Codex, ...) reads skills, picks issues, builds on a branch, runs the gates, opens a pull
  request, and raises anything it cannot decide as a `decision-needed` issue assigned to the owner.
- **Agent and owner post as the same GitHub account**, so every agent comment starts with a marker (`**[Claude]**`
  today). `board.py inbox` lists open issues whose latest comment lacks the marker: those are owner replies to act on.
- **Nothing merges itself.** Agents open pull requests; the owner merges (or tells the agent to).

## 2. The pieces

| Piece | Where it lives in the kit | Where it lands in a project | Kind |
|---|---|---|---|
| Skills (9) | `kit/.claude/skills/<name>/SKILL.md` | one copy per skills directory the enabled agents read | managed |
| `board.py` | `kit/.factory/scripts/board.py` | `.factory/scripts/board.py` | managed |
| Installer | `factory.py` | `.factory/factory.py` | managed |
| Instruction block | `kit/.factory/CLAUDE.snippet.md` | between `<!-- factory-kit:begin -->` / `end` in the instruction file | block |
| Config template | `kit/.factory/config.json` | `.factory/config.json` | scaffold |
| Issue and PR templates | `kit/.github/ISSUE_TEMPLATE/*`, `pull_request_template.md` | same paths | scaffold |
| CODEOWNERS | `kit/.github/CODEOWNERS` | `.github/CODEOWNERS` | scaffold |
| CI agent | `kit/.github/workflows/claude.yml` | `.github/workflows/claude.yml` (only if `claude` is enabled) | scaffold, agent-owned |
| CI agent | `kit/.github/workflows/codex.yml` | `.github/workflows/codex.yml` (only if `codex` is enabled) | scaffold, agent-owned |

**Managed** files are replaced on `update` unless the project edited them (then the kit's version is saved as
`<file>.factory-new` and nothing is overwritten). **Scaffolds** are created once and belong to the project afterwards.
The **block** is the only part of the instruction file the kit rewrites.

### The skills

Skills are plain Markdown procedures with `name` and `description` frontmatter. The description is what makes an
agent choose the skill, so write it as "Use when ...". They are project-neutral: they say "the Gates section of
CLAUDE.md" and read specifics from `.factory/config.json`; they never name a project, a path or a tool of the project.

| Skill | Purpose | Calls |
|---|---|---|
| `board` | Status: ongoing, ready, waiting, blocked, decisions | `board.py board` |
| `next-item` | Recommend what to build next (unblocks most, earliest wave, smallest), flag safe parallel sets | `board.py ready`, `deps` |
| `work-package <issue>` | Claim, branch `wp/<id>-<slug>`, implement, gate, open PR with `Closes #N` | `status`, `deps`, `gh` |
| `continue-work` | Resume an interrupted package | `board`, `git`, `gh` |
| `review-decisions` | Act on the owner's new comments (ADRs, answers, unblocking) | `inbox` |
| `raise-decision` | Open a `decision-needed` issue for the owner instead of writing a note | `new` |
| `add-adr <issue>` | Turn a settled decision into `docs/adr/NNNN-*.md` and close the loop | `adr-pending` |
| `new-work-item` | File follow-ups, bugs, verification items (anything not done now) | `template`, `new` |
| `run-parallel` | One worktree worker per independent ready issue, then gate and open PRs | `ready`, `deps` |

Skills still call `gh` directly in about 26 places. Issue #13 moves those behind `board.py` so a GitLab or Azure
DevOps backend only has to replace one file.

### `board.py`

Stdlib Python that wraps `gh` and reads `.factory/config.json` (two directories above itself). `board.py --help`
lists every command. Settings can be overridden by `FACTORY_REPO`, `FACTORY_PROJECT_OWNER`, `FACTORY_PROJECT`. With
no `project` set, status changes print a notice and do nothing. It only classifies issues labelled `work-package` or
`follow-up` as ready work; epics, decisions and owner actions are deliberately excluded.

### Config (`.factory/config.json`)

| Key | Meaning |
|---|---|
| `repo`, `owner`, `owner_id` | Repository, the steering person, and their numeric id (the CI agent checks it) |
| `project_owner` | Account that owns the project board; defaults to the repo's account (set only when it differs from `owner`) |
| `project` | GitHub project number; null disables board updates |
| `areas`, `waves`, `hotspots` | Area labels, ordered milestones, files that make parallel work collide |
| `notes` | Project hints the skills read |
| `labels` | `env_gated`, `needs_env` label names |
| `exclude` | Path prefixes the installer skips |
| `agents`, `instructions` | Enabled agents and the one instruction file that holds the block |

Rule: a new key needs a safe default **in code**, and should not be added to the template (an older installer would
report a scaffold conflict on the template).

## 3. The installer (`factory.py`)

- `init [--repo] [--owner] [--project N] [--agents a,b] [--source] [--ref]`: resolves the repo and owner, fetches the
  kit (default: highest `vX.Y.Z` tag, else `main`), writes config, installs files, writes `.factory/manifest.json`.
- `update`: no-op if the commit and agents are unchanged; otherwise per file: replace if unedited, conflict
  (`.factory-new`) if both sides changed, keep scaffolds, delete files the kit removed (when unedited).
- `agent add|remove NAME`: edit `agents`, then sync (files appear, or disappear if unedited).
- `status` (missing/edited managed files, pending `.factory-new`), `bootstrap` (labels, milestones), `version`.
- `kit.json` is the kit's own metadata: which paths are `managed`, the **agent registry**, and which file is the
  block source. The manifest records the hash of what the kit offered, not of the local file; that is how "the
  project edited it" and "the kit changed it" are told apart.
- Skills placement is a minimal cover: agents with one option decide first, so `claude,copilot,cursor` writes only
  `.claude/skills/`.

Compatibility: installers older than 0.2 can still update to 0.2+ because the kit keeps the `claude_md_block` key
and the `kit/.claude/skills` source layout. Do not rename them without a migration plan.

## 4. Developing the kit

### Setup and gates

```bash
git clone https://github.com/ljfio/factory-kit && cd factory-kit
python3 -m unittest discover -s tests       # needs git only; overlays your uncommitted changes onto a clone
python3 -m py_compile factory.py kit/.factory/scripts/board.py
```

Also smoke-test: install into a scratch git repo with a real or fake `gh` (`python3 factory.py init --repo o/n
--source . --ref main`), change the kit, run `update`. [`CLAUDE.md`](../CLAUDE.md) has the eight rules; the ones that
bite are: skills stay project-neutral, no project names anywhere, managed files are copied verbatim (no templating),
never overwrite project-edited files, stdlib only, new config keys need defaults, no weaker CI-agent controls.

### Recipes

**Change a skill.** Edit `kit/.claude/skills/<name>/SKILL.md`. Keep it neutral. The tests check skills use the
neutral helper path. Add a CHANGELOG line; projects get it on `update`.

**Add a skill.** New directory under `kit/.claude/skills/` with `SKILL.md`; add a row to the tables above and to
`kit/.factory/CLAUDE.snippet.md` (the skills line every project sees).

**Add a `board.py` command.** Add the handler and the `--help` docstring line, keep it stdlib, and make it work when
`project` is unset. Skills should call it, not `gh`.

**Add a config key.** Read it with a default in code (`CFG.get(...)`). Do not put it in `kit/.factory/config.json`
unless the project must set it. Document it in the table above and in `customising.md`.

**Add an agent.** An entry in `kit.json` (`skills`, `instructions`, optional `files`), the row in `agents.md`, a test.
Re-verify the vendor's paths first (they moved during 2026).

**Add a forge (GitLab, Azure DevOps).** Not built yet; the design is issues #12 to #15:
1. #12: a forge interface in `board.py` (issues, comments, labels, milestones, project status, pull request create,
   sub-issues, current user) with the GitHub backend as the first implementation, and `forge` in config.
2. #13: move every `gh` call in the skills behind `board.py` commands, so skills become forge-neutral.
3. #14, #15: backends that implement the interface, with contract tests against fake CLIs (`glab`, `az`).
4. Per-forge CI templates replace `claude.yml`'s GitHub-Actions specifics.

**Release.** Bump `VERSION`, add a `CHANGELOG.md` entry, commit, tag `vX.Y.Z`, push `main` and the tag. Only on the
owner's say-so; never force-push or move tags.

## 5. Dogfooding: how you continue from here

This repo installs its own kit (`.factory/`, `.claude/skills/`, project board 4). The backlog is on the board; the
kit's skills build the kit. Nothing has been built this way yet because the skills reach `main` only after the two open
pull requests merge.

### Where things stand

- PR #1 `feat/agent-neutral` (0.2.0 agent support) and PR #2 `chore/dogfood-install` (self-install, stacked on #1).
- Backlog, with waves: v0.3 (#3 verify agent claims, #4 `exclude` vs installed scaffolds, #5 spurious label-rename
  conflict, #6 `init --adopt` and config merge, #7 `doctor`, #8 configurable marker, #9-#11 CI agents and Copilot
  guide), v0.4 (#12 forge interface, #13 skills stop calling `gh`), v0.5 (#14 GitLab, #15 Azure DevOps).
- Yours: #16 decision on the comment marker, #17 enable the CI agent (needs the `claude` environment and secret).
- Unverified: the CI workflow has never run on GitHub. (Agent paths were checked in #3; sources in `agents.md`.)

### The loop

1. Review and merge PR #1, retarget #2 to `main`, merge it. Optionally tag `v0.2.0`.
2. Open an agent session in this repo. `/board` shows status; `/next-item` recommends one item (try #3 or #8 first:
   both small and independent).
3. `/work-package <issue>` claims it, branches `wp/<id>-<slug>`, implements, runs the gates in `CLAUDE.md`, and opens
   a pull request that says `Closes #N`.
4. You review and merge. Comment on issues to steer; run `/review-decisions` so the agent acts on your replies and
   turns settled decisions into ADRs under `docs/adr/`.
5. When the agent finds something it will not do now, it files it (`/new-work-item`); open questions become
   `decision-needed` issues assigned to you (`/raise-decision`). Answer in a comment.
6. For several independent items at once: `/run-parallel`. Items touching the `hotspots` (`factory.py`, `kit.json`)
   collide, so run those one at a time.
7. After merging kit changes, run `python3 .factory/factory.py update` here to take your own release (the dogfood
   install tracks a tag or `main`).

### Suggested order

1. **#3** verify the unchecked agent paths and fix `agents.md` (small, de-risks everything agent-related).
2. **#8** configurable marker (needs your answer on #16; recommended: keep `**[Claude]**` as default).
3. **#4, #5, #6** installer rough edges (all touch `factory.py`: one at a time).
4. **#7** `doctor`, then **#9-#11**.
5. **#12 then #13** (the forge seam) before **#14/#15**. #12 is the big one: write its design as an ADR first
   (`/raise-decision` if you want to choose between options).

### Keeping the docs true

Docs describe design, never status: status lives on the board. When a change makes a doc wrong, fix it in the same
pull request. This file's tables (skills, config keys, recipes) are the ones most likely to drift; update them when
you add a skill, a key or a command.
