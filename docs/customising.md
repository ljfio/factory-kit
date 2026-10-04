# Customising

## `.factory/config.json`

| Key | Used by | Meaning |
|---|---|---|
| `repo`, `owner`, `owner_id` | `board.py`, `claude.yml`, CODEOWNERS | Repository, owner login, owner's numeric account id (the CI agent checks the id, which cannot be taken over like a login) |
| `project` | `board.py` | GitHub project number; leave `null` to track by issues only (status changes are then skipped) |
| `areas` | `board.py new --area` | Allowed `area:*` labels; empty allows any |
| `waves` | `board.py` | Milestone titles in delivery order (prefix match); `bootstrap` creates them |
| `hotspots` | `run-parallel`, `next-item` | Paths two parallel agents must not both change (lockfiles, solution files, generated bundles) |
| `notes` | `run-parallel` | Free-text constraints for parallel runs (for example "one emulator suite at a time") |
| `verification_epic` | `new-work-item`, `work-package` | Issue number of the epic that collects "not verified against the real environment" items |
| `labels` | `board.py`, templates | Names for the env-gated and needs-env labels (for example `azure-gated` and `needs-azure`) |
| `exclude` | `factory.py` | Kit paths (prefix match) that this project does not want installed or updated |
| `adr_dir` | `add-adr` | ADR directory, default `docs/adr` |

`update` adds any new keys the kit gains and never changes yours.

## Project rules belong in `CLAUDE.md`

The skills refer to "the rules in `CLAUDE.md`" and "the Gates section". Put your gates there (the commands that
must pass before a pull request), your non-negotiable rules, and what lives where. The skills then apply them
without being edited.

## Changing a skill

Edit it in place. The next `update` will leave your version alone and write the kit's as `<file>.factory-new` when
the kit also changed it. Prefer config or `CLAUDE.md` over editing a skill; if the change is general, send it to
the kit.

## Labels

`bootstrap` creates: `work-package`, `follow-up`, `epic`, `decision-needed`, `decided`, `adr-recorded`,
`owner-action`, `blocked`, `offline-done` (built without the real environment, only that part remains; counts as
a met dependency), the env-gated and needs-env labels, `size:S/M/L` and one `area:*` per configured area.
