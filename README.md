# factory-kit

A small, opinionated "software factory" for any GitHub repository, driven from Claude Code: GitHub issues and a
project board are the record of the work, agents pick up issues and open pull requests, and the owner steers with
comments. Install it into a project with one command and pull updates from here whenever it improves.

## What you get

| Piece | Where it lands in your project | What it does |
|---|---|---|
| Skills | `.claude/skills/` and/or `.agents/skills/`, per [agent](docs/agents.md) | `board`, `next-item`, `work-package`, `continue-work`, `review-decisions`, `raise-decision`, `add-adr`, `new-work-item`, `run-parallel` |
| Board helper | `.factory/scripts/board.py` | Queries and updates issues and the project board (ready, status, inbox, deps, create-from-template) |
| Issue and PR templates | `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md` | One template per kind of work, used by the web form and by `board.py new` |
| CI agent | `.github/workflows/claude.yml` | `@claude` in an issue or PR comment runs Claude Code in Actions on your subscription, owner only |
| Review guard | `.github/CODEOWNERS` | Workflows, skills and `CLAUDE.md` need the owner's review |
| Workflow summary | a marked block in `AGENTS.md` or `CLAUDE.md` | Tells agents how the loop works; replaced on update |
| Config | `.factory/config.json` | Repo, owner (`init --owner`, default: your `gh` login), project number, areas, waves, hotspots, labels |

The loop: `board` shows the state, `next-item` picks, `work-package <issue>` claims, branches, builds, runs your
gates and opens a pull request with `Closes #N`. Open questions are `decision-needed` issues; `review-decisions`
reads your replies and `add-adr` records the decision. Anything not done now becomes an issue (`new-work-item`).
`run-parallel` runs several independent issues in isolated worktrees.

## Install

In a git repository with a GitHub remote, with the [`gh` CLI](https://cli.github.com) logged in
(`gh auth refresh -s project` for the board):

```bash
curl -fsSL https://raw.githubusercontent.com/ljfio/factory-kit/main/factory.py | python3 - init --project 3
```

or clone this repo and run `python3 factory.py init --project 3` in your project. Then:

1. Edit `.factory/config.json` (areas, waves, hotspots) and fill the **Gates** section of `CLAUDE.md`.
2. `python3 .factory/factory.py bootstrap` creates the labels and milestones on GitHub.
3. Set up the CI agent if you want it: [`docs/ci-agent.md`](docs/ci-agent.md).
4. Commit on a branch and open a pull request.

## Update

```bash
python3 .factory/factory.py update --dry-run   # see what would change
python3 .factory/factory.py update             # latest release tag (or main if untagged)
python3 .factory/factory.py update --ref v0.3.0
python3 .factory/factory.py status             # what differs from the installed kit
```

Files are in three classes, recorded in `.factory/manifest.json` with the hash that was installed:

- **managed** (skills, `board.py`, `factory.py` itself): replaced on update. If you edited one, it is never
  overwritten: the kit's version is written next to it as `<file>.factory-new` and the update reports a conflict.
- **scaffold** (workflows, CODEOWNERS, templates, config): created once and yours afterwards. If the kit changes
  one, the new version is written as `<file>.factory-new` to merge by hand.
- **block** (the section of `CLAUDE.md` between the `factory-kit` markers): replaced on update.

Keep a managed file out of the kit entirely by listing its path in `exclude` in `.factory/config.json`.
See [`docs/customising.md`](docs/customising.md).

## Design rules

- GitHub is the only state: no status files, no database. Skills read and write issues, comments and the board.
- Project specifics live in `.factory/config.json` and `CLAUDE.md`, never in the skills, so the skills stay
  identical across projects and update cleanly.
- Claude and the owner post as the same account, so every Claude comment starts with `**[Claude]**`; the
  inbox is the open issues whose latest comment lacks it. Only the owner's comments are instructions.
- Nothing merges itself: agents open pull requests; the owner merges (or says so).
- Standard library Python and `gh`; no dependencies to install.

## Develop the kit

```bash
python3 -m unittest discover -s tests
```

Release by bumping `VERSION`, adding to `CHANGELOG.md` and tagging `vX.Y.Z`; `update` follows the latest tag.

MIT licensed.

More: [how it works and how to keep developing it](docs/development.md), [agents](docs/agents.md), [customising](docs/customising.md), [CI agent](docs/ci-agent.md).
