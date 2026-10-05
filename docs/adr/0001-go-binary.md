---
status: accepted
date: 2026-10-05
decider: owner
issue: 20
---

# 0001. Ship the installer and board helper as one Go binary

## Context

`factory.py` and `board.py` need Python 3.8+ wherever the kit is installed or run. The tool mostly configures a
repository with text files for AI agents, so it should be a self-contained download with no runtime. The forge
backends planned for v0.4 and v0.5 (#12 to #15) would otherwise grow stdlib-only Python scripts further.

## Decision

Rewrite as a single Go binary using cobra (with pflag), bundling the `kit/` payload with `go:embed` and releasing
per-OS and per-architecture builds. Owner's answer: "Option B would be preferred as I want to make this
self-contained binary, reduce any dependencies when we want to run it, as it's mostly configuring a repository
with text files for AI agents."

## Consequences

- Supersedes CLAUDE.md rule 5 (stdlib-only Python) once the port lands; until then the Python tools remain the
  shipped ones and the gates stay as they are.
- The manifest format and `.factory/config.json` stay unchanged so existing installs update cleanly.
- Skills will call `factory ...` instead of `python3 .factory/scripts/board.py ...`; the managed skill files change
  with the port.
- Needs a release pipeline (GoReleaser, checksums, pinned action commits) and a self-update path for the binary.
- The forge interface (#12) is built in Go, after the port.

## Alternatives considered

- Stay on stdlib Python: needs a Python runtime everywhere; rejected by the owner.
- Hybrid (Go `factory`, Python `board.py` until #12): two toolchains; not chosen.
- `urfave/cli`, `kong`, stdlib `flag`: less adopted or without subcommand help and completion than cobra.
