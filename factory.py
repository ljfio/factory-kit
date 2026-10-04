#!/usr/bin/env python3
"""factory-kit: install and update an agent-driven GitHub delivery workflow in any repository.

  factory.py init [--ref REF] [--source URL|PATH] [--project N] [--repo OWNER/NAME] [--adopt]
                              install the kit into the current repository; keeps an existing .factory/config.json,
                              --adopt replaces existing managed files (older skills) with the kit's
  factory.py update [--ref REF] [--dry-run] [--force]
                              bring the kit files up to date with the latest release
  factory.py agent add|remove NAME
                              enable or disable an agent (claude, codex, gemini, copilot, cursor)
  factory.py status           show what differs from the installed kit
  factory.py bootstrap        create the labels (and milestones from config `waves`) on GitHub
  factory.py version

Run from the root of a git repository. Standard library only; needs git, and gh for init and bootstrap.

First install, without a copy of this file:
  curl -fsSL https://raw.githubusercontent.com/ljfio/factory-kit/main/factory.py | python3 - init

Afterwards the copy at .factory/factory.py is the updater: python3 .factory/factory.py update

Three kinds of file, recorded in .factory/manifest.json with the hash that was installed:
  managed   skills, board.py and this script. Replaced on update unless you changed them; a file you changed
            is never overwritten, the kit's version is written next to it as <file>.factory-new instead.
  scaffold  workflows, CODEOWNERS, issue and PR templates, config. Created once and yours from then on;
            when the kit changes one, the new version is written as <file>.factory-new for you to merge.
  block     a marked section of the instruction file (AGENTS.md or CLAUDE.md), replaced on update.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_SOURCE = os.environ.get("FACTORY_SOURCE") or "https://github.com/ljfio/factory-kit.git"
MANIFEST = Path(".factory/manifest.json")
CONFIG = Path(".factory/config.json")
BEGIN, END = "<!-- factory-kit:begin -->", "<!-- factory-kit:end -->"
STANDARD_LABELS = {
    "work-package": ("0E8A16", "A package from the plan"),
    "follow-up": ("FBCA04", "Work found along the way"),
    "epic": ("5319E7", "Groups sub-issues"),
    "decision-needed": ("D93F0B", "Waiting on the owner"),
    "decided": ("0E8A16", "A decision that has been made"),
    "adr-recorded": ("C2E0C6", "The decision is written up as an ADR"),
    "owner-action": ("B60205", "Only the owner can do it"),
    "blocked": ("000000", "Cannot proceed; the reason is in a comment"),
    "offline-done": ("BFD4F2", "Built without the real environment; only the environment part remains"),
    "size:S": ("EDEDED", "Under a day"),
    "size:M": ("EDEDED", "One to three days"),
    "size:L": ("EDEDED", "Three to five days"),
}


def die(msg):
    sys.exit(f"factory.py: {msg}")


def run(*cmd, cwd=None, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if check and p.returncode != 0:
        die(f"{' '.join(cmd[:3])} failed: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout.strip()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# ---- the kit source -------------------------------------------------------------------------------------------

def version_key(tag):
    return [int(x) for x in re.findall(r"\d+", tag)]


def resolve_ref(source, ref):
    if ref:
        return ref
    tags = [ln.split("refs/tags/")[1] for ln in run("git", "ls-remote", "--tags", "--refs", source).splitlines()
            if "refs/tags/" in ln]
    tags = [t for t in tags if re.match(r"v?\d+(\.\d+)*$", t)]
    return max(tags, key=version_key) if tags else "main"


def fetch_kit(source, ref):
    """Shallow clone of the kit at ref into a temp dir; returns (dir, ref, commit, version)."""
    ref = resolve_ref(source, ref)
    tmp = Path(tempfile.mkdtemp(prefix="factory-kit-"))
    local = Path(source).exists()
    cmd = ["git", "clone", "--quiet", "--branch", ref, source, str(tmp / "kit")]
    if not local:
        cmd.insert(3, "--depth=1")
    run(*cmd)
    kit = tmp / "kit"
    commit = run("git", "rev-parse", "HEAD", cwd=kit)
    version = (kit / "VERSION").read_text().strip() if (kit / "VERSION").exists() else ref
    return kit, ref, commit, version


def agent_names(cfg, meta):
    names = cfg.get("agents") or ["claude"]
    unknown = [n for n in names if n not in meta["agents"]]
    if unknown:
        die(f"unknown agent(s): {', '.join(unknown)} (known: {', '.join(meta['agents'])})")
    return list(dict.fromkeys(names))


def skills_dirs(names, meta):
    """The fewest skills directories that every enabled agent reads; agents with one choice decide first."""
    chosen = []
    for n in sorted(names, key=lambda n: len(meta["agents"][n]["skills"])):
        opts = meta["agents"][n]["skills"]
        if not any(d in chosen for d in opts):
            chosen.append(opts[0])
    return chosen


def instruction_files(cfg, meta, names):
    """Map of instruction file -> True when it holds the managed block, False when it only points at the one that does."""
    canonical = cfg.get("instructions", "CLAUDE.md")
    out = {canonical: True}
    for n in names:
        out.setdefault(meta["agents"][n]["instructions"], False)
    return out


def kit_files(kit, cfg):
    """Map of project path -> (bytes rendered with the project's config, kind, mode), and the managed block."""
    meta = json.loads((kit / "kit.json").read_text())
    managed = meta["managed"]
    exclude = cfg.get("exclude", [])
    labels = cfg.get("labels", {})
    values = {
        "repo": cfg.get("repo", ""), "owner": cfg.get("owner", ""), "owner_id": str(cfg.get("owner_id", "")),
        "label_needs_env": labels.get("needs_env", "needs-env"),
        "label_env_gated": labels.get("env_gated", "env-gated"),
    }
    names = agent_names(cfg, meta)
    owned = {f: n for n, a in meta["agents"].items() for f in a.get("files", [])}
    skills_src = meta["skills_source"]
    targets = [d.rstrip("/") + "/" for d in skills_dirs(names, meta)]
    out = {}
    sources = {}
    for p in (kit / "kit").rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(kit / "kit"))
        if rel.startswith(skills_src):  # the skills are written once per directory an enabled agent reads
            for t in targets:
                sources[t + rel[len(skills_src):]] = p
        elif owned.get(rel) is None or owned[rel] in names:  # a file an agent owns is skipped unless it is enabled
            sources[rel] = p
    sources[".factory/factory.py"] = kit / "factory.py"
    for rel, src in sorted(sources.items()):
        if rel == meta["claude_md_block"] or any(rel.startswith(x) for x in exclude):
            continue
        data = raw = src.read_bytes()
        kind = "managed" if any(rel == m or (m.endswith("/") and rel.startswith(m)) for m in managed) else "scaffold"
        if kind == "scaffold":  # managed files are copied verbatim (factory.py contains the placeholders itself)
            try:
                data = re.sub(r"\{\{(repo|owner|owner_id|label_needs_env|label_env_gated)\}\}",
                              lambda m: values[m.group(1)], data.decode()).encode()
            except UnicodeDecodeError:
                pass
        out[rel] = (data, kind, 0o755 if rel.endswith(".py") else 0o644, sha(raw))
    block = (kit / "kit" / meta["instruction_block"]).read_text().strip()
    return out, block, instruction_files(cfg, meta, names)


# ---- project state ---------------------------------------------------------------------------------------------

def detect_repo():
    return run("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner", check=False)


def write_file(rel, data, mode):
    p = Path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    p.chmod(mode)


def pointer_block(canonical):
    return f"@./{canonical}\n\nThe project instructions for this repository are in {canonical}; read that file first."


def apply_block(name, block, dry):
    f = Path(name)
    marked = f"{BEGIN}\n{block}\n{END}"
    if not f.exists():
        action, text = f"create {name}", f"# {Path.cwd().name}\n\n{marked}\n"
    else:
        cur = f.read_text()
        if BEGIN in cur and END in cur:
            new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: marked, cur, flags=re.S)
            if new == cur:
                return f"{name} block unchanged"
            action, text = f"update the {name} block", new
        else:
            action, text = f"append the workflow block to {name}", cur.rstrip("\n") + "\n\n" + marked + "\n"
    if not dry:
        f.write_text(text)
    return action


def sync(kit, ref, commit, version, cfg, manifest, dry, force, first, adopt=False):
    files, block, instr = kit_files(kit, cfg)
    old = manifest.get("files", {})
    new_manifest = {}
    report = []
    for rel, (data, kind, mode, raw) in files.items():
        h, p, rec = sha(data), Path(rel), old.get(rel)
        local = sha(p.read_bytes()) if p.exists() else None
        inst = rec["sha"] if rec else None
        keep = {"sha": inst, "kind": kind} if rec else None
        if keep and "raw" in rec:
            keep["raw"] = rec["raw"]

        def done(h_=h):  # raw: hash of the unrendered kit file, so a config change is not mistaken for a kit change
            new_manifest[rel] = {"sha": h_, "kind": kind, **({"raw": raw} if kind == "scaffold" else {})}

        def conflict(why):
            report.append(("conflict", rel, why))
            if not dry:
                write_file(rel + ".factory-new", data, mode)
            if keep:
                new_manifest[rel] = keep

        if local is None:
            if rec and not force:
                report.append(("skipped", rel, "deleted locally; run with --force to restore"))
                new_manifest[rel] = keep
            else:
                report.append(("added", rel, kind))
                if not dry:
                    write_file(rel, data, mode)
                done()
        elif local == h:
            done()
        elif kind == "managed":
            if force or (rec and local == inst) or (adopt and not rec):
                report.append(("updated", rel, "adopted" if adopt and not rec else ""))
                if not dry:
                    write_file(rel, data, mode)
                done()
            elif rec and h == inst:
                report.append(("kept", rel, "modified locally, kit unchanged"))
                new_manifest[rel] = keep
            else:
                conflict("modified locally and changed in the kit" if rec else "exists and was not installed by the kit")
        else:  # scaffold, differs from the kit
            if rec and (rec["raw"] != raw if "raw" in rec else h != inst):
                conflict("kit changed this scaffold; merge by hand")
            elif rec:
                new_manifest[rel] = {**keep, "raw": raw}
            else:
                report.append(("kept", rel, "scaffold already exists"))
                done()
    for rel, rec in old.items():
        if rel in files:
            continue
        p = Path(rel)
        if p.exists():  # managed or scaffold: removed when unedited, kept (and reported) when edited
            if sha(p.read_bytes()) == rec["sha"]:
                report.append(("removed", rel, "no longer in the kit or excluded"))
                if not dry:
                    p.unlink()
                    for d in p.parents:  # leave no empty directories behind
                        if d == Path(".") or any(d.iterdir()):
                            break
                        d.rmdir()
                continue
            report.append(("kept", rel, "no longer in the kit or excluded, but modified locally"))
            new_manifest[rel] = rec
    canonical = next(f for f, full in instr.items() if full)
    for name, full in instr.items():
        report.append(("block", name, apply_block(name, block if full else pointer_block(canonical), dry)))
    if not dry:
        write_json(MANIFEST, {"source": manifest.get("source_arg"), "ref": ref, "version": version, "commit": commit,
                              "agents": cfg.get("agents") or ["claude"], "exclude": cfg.get("exclude", []),
                              "files": dict(sorted(new_manifest.items()))})
    return report


def merge_config_defaults(kit, cfg, dry):
    """Add keys the kit's config gained since install; never touch existing values."""
    meta_cfg = kit / "kit" / ".factory" / "config.json"
    defaults = json.loads(re.sub(r"\{\{\w+\}\}", "", meta_cfg.read_text().replace("{{owner_id}}", "0")))
    added = [k for k in defaults if k not in cfg]
    if added and not dry:
        for k in added:
            cfg[k] = defaults[k]
        write_json(CONFIG, cfg)
    return added


def print_report(report):
    marks = {"added": "+", "updated": "~", "removed": "-", "conflict": "!", "skipped": "?", "kept": "=", "block": "#"}
    shown = [r for r in report if r[0] != "kept" or "locally" in r[2]]
    for kind, rel, note in shown:
        print(f"  {marks[kind]} {kind:<9} {rel}" + (f"  ({note})" if note else ""))
    n = sum(1 for r in report if r[0] == "conflict")
    if n:
        print(f"\n{n} file(s) need a merge by hand: compare each <file> with <file>.factory-new, keep what you want,"
              " then delete the .factory-new file.")


# ---- commands --------------------------------------------------------------------------------------------------

def cmd_init(a):
    if not Path(".git").exists():
        die("run from the root of a git repository")
    if MANIFEST.exists():
        die("already installed; use `update`")
    existing = read_json(CONFIG, {})  # a project that already has a config keeps its values
    repo = a.repo or existing.get("repo") or detect_repo()
    if not repo:
        die("cannot tell the GitHub repository; pass --repo OWNER/NAME")
    # the owner is the person who steers the agents: --owner, else whoever is signed in to gh, else the repo's account
    repo_account = repo.split("/")[0]
    owner = a.owner or existing.get("owner") or run("gh", "api", "user", "--jq", ".login", check=False) or repo_account
    owner_id = existing.get("owner_id") if owner == existing.get("owner") and existing.get("owner_id") else \
        int(run("gh", "api", f"users/{owner}", "--jq", ".id"))
    source = a.source or DEFAULT_SOURCE
    kit, ref, commit, version = fetch_kit(source, a.ref)
    # config first (scaffold), then everything rendered with it
    cfg_text = (kit / "kit" / ".factory" / "config.json").read_text()
    for k, v in (("repo", repo), ("owner", owner), ("owner_id", str(owner_id))):
        cfg_text = cfg_text.replace("{{%s}}" % k, v)
    cfg = json.loads(cfg_text)
    for k, v in existing.items():  # existing values win over the kit's defaults (one level deep for objects)
        cfg[k] = {**cfg[k], **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
    cfg.update(repo=repo, owner=owner, owner_id=owner_id)
    if a.project:
        cfg["project"] = a.project
    if repo_account != owner and "project_owner" not in existing:
        cfg["project_owner"] = repo_account  # projects belong to the repo's account (user or organisation)
    meta = json.loads((kit / "kit.json").read_text())
    if a.agents or "agents" not in existing:
        cfg["agents"] = agent_names({"agents": [x for x in (a.agents or "claude").split(",") if x]}, meta)
        files = {meta["agents"][n]["instructions"] for n in cfg["agents"]}
        cfg["instructions"] = "AGENTS.md" if len(files) > 1 and "AGENTS.md" in files else sorted(files)[0]
    if not a.dry_run:
        write_json(CONFIG, cfg)
    report = sync(kit, ref, commit, version, cfg, {"source_arg": source}, a.dry_run, False, True, a.adopt)
    print(f"factory-kit {version} ({ref} {commit[:7]}) installed from {source}\n")
    print_report(report)
    claude = "claude" in cfg["agents"]
    print(f"""
Next:
  1. Edit .factory/config.json: project (the number of your GitHub project), areas, waves, hotspots.
  2. python3 .factory/factory.py bootstrap     (labels and milestones)
  3. Fill the Gates section of {cfg["instructions"]}""" + (", and the toolchain setup in .github/workflows/claude.yml." if claude else "."))
    if claude:
        print("""  4. For the CI agent: create the `claude` environment (deployments limited to your default branch) with the
     secret CLAUDE_CODE_OAUTH_TOKEN (see docs/ci-agent.md in the kit).""")
    print("  5. Commit .factory .github and the agent directories and instruction files on a branch and open a pull request.")


def installed():
    m = read_json(MANIFEST)
    if not m:
        die("not installed here; run `init`")
    return m, read_json(CONFIG, {})


def cmd_update(a):
    manifest, cfg = installed()
    source = a.source or manifest.get("source") or DEFAULT_SOURCE
    kit, ref, commit, version = fetch_kit(source, a.ref)
    if commit == manifest.get("commit") and not a.force and manifest.get("agents") == (cfg.get("agents") or ["claude"]) \
            and manifest.get("exclude", []) == cfg.get("exclude", []):
        print(f"already at {version} ({commit[:7]})")
        return
    manifest["source_arg"] = source
    added = merge_config_defaults(kit, cfg, a.dry_run)
    report = sync(kit, ref, commit, version, cfg, manifest, a.dry_run, a.force, False)
    print(f"{manifest.get('version')} -> {version} ({ref} {commit[:7]})" + ("  [dry run]" if a.dry_run else "") + "\n")
    if added:
        print(f"  + config keys added to .factory/config.json: {', '.join(added)}")
    print_report(report)


def cmd_agent(a):
    """Enable or disable an agent: edit config, then sync so its files are added (or removed when unedited)."""
    manifest, cfg = installed()
    names = list(cfg.get("agents") or ["claude"])
    if a.action == "add" and a.name not in names:
        names.append(a.name)
    elif a.action == "remove":
        names = [n for n in names if n != a.name]
    if not names:
        die("at least one agent must stay enabled")
    cfg["agents"] = names
    write_json(CONFIG, cfg)
    a.force, a.dry_run = False, False
    cmd_update(a)


def cmd_status(_):
    manifest, _cfg = installed()
    print(f"factory-kit {manifest.get('version')} ({manifest.get('ref')} {str(manifest.get('commit'))[:7]}) "
          f"from {manifest.get('source')}")
    for rel, rec in manifest["files"].items():
        p = Path(rel)
        state = "missing" if not p.exists() else ("clean" if sha(p.read_bytes()) == rec["sha"] else "modified")
        if state == "missing" or (state == "modified" and rec["kind"] == "managed"):
            print(f"  {state:<9} {rec['kind']:<9} {rel}")
    pending = [str(p) for p in Path(".").rglob("*.factory-new")]
    for p in pending:
        print(f"  pending merge: {p}")


def cmd_bootstrap(_):
    manifest, cfg = installed()
    repo = cfg["repo"]
    labels = dict(STANDARD_LABELS)
    lab = cfg.get("labels", {})
    labels[lab.get("env_gated", "env-gated")] = ("D4C5F9", "Cannot start before the environment is deployed")
    labels[lab.get("needs_env", "needs-env")] = ("F9D0C4", "Needs the real environment to finish")
    for area in cfg.get("areas", []):
        labels[f"area:{area}"] = ("1D76DB", f"Area: {area}")
    for name, (color, desc) in labels.items():
        run("gh", "label", "create", name, "-R", repo, "--color", color, "--description", desc, "--force")
        print(f"  label {name}")
    have = {m["title"] for m in json.loads(run("gh", "api", f"repos/{repo}/milestones?state=all&per_page=100"))}
    for w in cfg.get("waves", []):
        if w not in have:
            run("gh", "api", f"repos/{repo}/milestones", "-f", f"title={w}")
            print(f"  milestone {w}")


def main():
    ap = argparse.ArgumentParser(prog="factory.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "update"):
        s = sub.add_parser(name)
        s.add_argument("--ref", help="tag or branch of the kit (default: latest release tag, else main)")
        s.add_argument("--source", help=f"kit git URL or path (default: {DEFAULT_SOURCE})")
        s.add_argument("--dry-run", action="store_true")
        if name == "init":
            s.add_argument("--repo")
            s.add_argument("--project", type=int)
            s.add_argument("--owner", help="GitHub login of the person who steers the agents (default: the user "
                                           "signed in to gh)")
            s.add_argument("--agents", help="comma-separated agents to install for: claude, codex, gemini, copilot, "
                                            "cursor (default: those in an existing config, else claude)")
            s.add_argument("--adopt", action="store_true",
                           help="take the kit's version of managed files that already exist (e.g. older skills) "
                                "instead of writing <file>.factory-new")
        else:
            s.add_argument("--force", action="store_true", help="overwrite managed files you changed")
    s = sub.add_parser("agent")
    s.add_argument("action", choices=["add", "remove"])
    s.add_argument("name")
    s.add_argument("--ref")
    s.add_argument("--source")
    sub.add_parser("status").add_argument("-v", action="store_true")
    sub.add_parser("bootstrap")
    sub.add_parser("version")
    a = ap.parse_args()
    if a.cmd == "version":
        m = read_json(MANIFEST)
        print(m["version"] if m else "not installed")
    else:
        {"init": cmd_init, "update": cmd_update, "agent": cmd_agent, "status": cmd_status, "bootstrap": cmd_bootstrap}[a.cmd](a)


if __name__ == "__main__":
    main()
