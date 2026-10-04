#!/usr/bin/env python3
"""Read and update the delivery board (GitHub issues + project).

The GitHub issues and the project are the record of what is done, ongoing and next.
Skills call this instead of re-deriving the queries.

  board.py ready              work that can start now (dependencies closed or offline-done)
  board.py board              ongoing, ready, waiting on decisions, blocked
  board.py status N STATE     set the project status of issue N: todo | in-progress | done
  board.py deps N             show the dependencies of issue N and whether each is closed
  board.py decisions          open decision-needed issues
  board.py inbox              open issues whose latest comment is not from Claude (owner replies to act on)
  board.py adr-pending        decided issues that have no ADR yet (run the add-adr skill for each)
  board.py sub PARENT CHILD   make CHILD a sub-issue of PARENT
  board.py template [TYPE]    list the issue types, or print the body template of one (.github/ISSUE_TEMPLATE)
  board.py new TYPE --title T --body-file F [--area A] [--size S|M|L] [--label L] [--milestone M]
                [--parent N] [--from N] [--dry-run]
                              create an issue from its template: labels and assignee from the template, body
                              checked for the template's sections, put on the board, linked under --parent.
                              TYPE decided closes the issue at once (--from is the package issue it came from)

  board.py repo               print the repository (owner/name) this board belongs to
  board.py project-url        print the project board URL

Settings come from .factory/config.json (repo, owner, project, areas, waves, labels), falling back to the
git remote. Needs the gh CLI with the `project` scope. Override with FACTORY_REPO, FACTORY_OWNER, FACTORY_PROJECT.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
STATES = {"todo": "Todo", "in-progress": "In Progress", "done": "Done"}


def load_config():
    f = ROOT / ".factory" / "config.json"
    return json.loads(f.read_text()) if f.exists() else {}


CFG = load_config()


def detect_repo():
    p = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
                       capture_output=True, text=True, cwd=ROOT)
    if p.returncode != 0 or not p.stdout.strip():
        sys.exit("no repo: set `repo` in .factory/config.json or FACTORY_REPO")
    return p.stdout.strip()


REPO = os.environ.get("FACTORY_REPO") or CFG.get("repo") or detect_repo()
OWNER = os.environ.get("FACTORY_OWNER") or CFG.get("owner") or REPO.split("/")[0]
PROJECT = str(os.environ.get("FACTORY_PROJECT") or CFG.get("project") or "")
WAVE_ORDER = CFG.get("waves", [])
AREAS = CFG.get("areas", [])
LABELS = {"env_gated": "env-gated", "needs_env": "needs-env", **CFG.get("labels", {})}


def gh(*args):
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"gh {' '.join(args[:3])} failed: {p.stderr.strip()}")
    return p.stdout


def issues():
    out = gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "500", "--json",
             "number,title,state,body,labels,milestone,assignees")
    return {i["number"]: i for i in json.loads(out)}


def project_items():
    if not PROJECT:
        return {}
    out = gh("project", "item-list", PROJECT, "--owner", OWNER, "--limit", "500", "--format", "json")
    return {i["content"]["number"]: i for i in json.loads(out)["items"] if i.get("content", {}).get("number")}


def labels(i):
    return {l["name"] for l in i["labels"]}


def deps(i):
    m = re.search(r"### Depends on\s*\n(.*?)(?:\n###|\n---|\Z)", i["body"] or "", re.S)
    return [int(n) for n in re.findall(r"#(\d+)", m.group(1))] if m else []


def wave(i):
    t = (i["milestone"] or {}).get("title", "zzz")
    for k, w in enumerate(WAVE_ORDER):
        if t.startswith(w):
            return k
    return 99


def size(i):
    return next((l[5:] for l in labels(i) if l.startswith("size:")), "?")


def classify():
    iss, items = issues(), project_items()
    res = {"ongoing": [], "ready": [], "gated": [], "waiting": [], "blocked": []}
    for n, i in sorted(iss.items(), key=lambda kv: (wave(kv[1]), kv[0])):
        lab = labels(i)
        if i["state"] != "OPEN" or "epic" in lab or "decision-needed" in lab or "owner-action" in lab:
            continue
        if not lab & {"work-package", "follow-up"}:
            continue
        status = items.get(n, {}).get("status", "Todo")
        # a dependency is met when closed, or built offline with only the real-environment part left
        open_deps = [d for d in deps(i) if d in iss and iss[d]["state"] == "OPEN" and "offline-done" not in labels(iss[d])]
        if status == "In Progress":
            res["ongoing"].append((i, open_deps))
        elif "blocked" in lab:
            res["blocked"].append((i, open_deps))
        elif open_deps:
            res["waiting"].append((i, open_deps))
        elif LABELS["env_gated"] in lab:
            res["gated"].append((i, open_deps))
        else:
            res["ready"].append((i, open_deps))
    return res, iss


def line(i, extra=""):
    ms = (i["milestone"] or {}).get("title", "-")
    return f"  #{i['number']:<4} {size(i):<2} {i['title'][:70]:<70} [{ms}]{extra}"


def cmd_ready():
    res, iss = classify()
    print("Ready to start (dependencies closed, not in progress, not blocked):")
    for i, _ in res["ready"]:
        print(line(i))
    if not res["ready"]:
        print("  (none)")


def cmd_board():
    res, iss = classify()
    for key, head in (("ongoing", "In progress"), ("ready", "Ready"), ("gated", f"Needs a deployed environment ({LABELS['env_gated']})"), ("waiting", "Waiting on dependencies"), ("blocked", "Blocked")):
        print(f"\n{head} ({len(res[key])})")
        for i, od in res[key]:
            extra = ""
            if key == "waiting":
                extra = "  needs " + ", ".join(f"#{d}" + ("(decision)" if "decision-needed" in labels(iss[d]) else "") for d in od)
            print(line(i, extra))
    ds = [i for i in iss.values() if i["state"] == "OPEN" and "decision-needed" in labels(i)]
    print(f"\nDecisions waiting for the owner: {len(ds)} (board.py decisions)")


def cmd_decisions():
    for i in sorted(issues().values(), key=lambda i: i["number"]):
        if i["state"] == "OPEN" and "decision-needed" in labels(i):
            print(f"  #{i['number']:<4} {i['title'][:100]}  [{(i['milestone'] or {}).get('title', '-')}]")


def cmd_inbox():
    """Claude signs every comment it posts with **[Claude]** (both write as the owner's account), so a latest
    comment without that marker is a human reply that has not been handled yet."""
    out = gh("issue", "list", "-R", REPO, "--state", "open", "--limit", "500", "--json",
             "number,title,labels,comments,milestone")
    n = 0
    for i in sorted(json.loads(out), key=lambda i: i["number"]):
        cs = i["comments"]
        if not cs or cs[-1]["body"].lstrip().startswith("**[Claude]**"):
            continue
        c = cs[-1]
        lab = ",".join(sorted(l["name"] for l in i["labels"] if l["name"] in
                              ("decision-needed", "owner-action", "blocked", "work-package", "follow-up")))
        snippet = " ".join(c["body"].split())[:160]
        print(f"  #{i['number']:<4} [{lab}] {i['title'][:60]}\n        {c['author']['login']} {c['createdAt'][:16]}: {snippet}")
        n += 1
    if not n:
        print("  (nothing waiting)")


def cmd_adr_pending():
    n = 0
    for i in sorted(issues().values(), key=lambda i: i["number"]):
        lab = labels(i)
        if i["state"] == "CLOSED" and "decided" in lab and "adr-recorded" not in lab:
            print(f"  #{i['number']:<4} {i['title'][:100]}")
            n += 1
    if not n:
        print("  (none)")


def cmd_sub(parent, child):
    cid = json.loads(gh("api", f"repos/{REPO}/issues/{child}"))["id"]
    p = subprocess.run(["gh", "api", f"repos/{REPO}/issues/{parent}/sub_issues", "-F", f"sub_issue_id={cid}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(p.stderr.strip())
    print(f"#{child} is now a sub-issue of #{parent}")


def cmd_deps(n):
    iss = issues()
    for d in deps(iss[n]):
        print(f"  #{d} {iss[d]['state']:<6} {iss[d]['title'][:80]}")


def cmd_status(n, state):
    if not PROJECT:
        print("no project configured (`project` in .factory/config.json); status not recorded")
        return
    if state not in STATES:
        sys.exit("state must be todo, in-progress or done")
    proj = json.loads(gh("project", "view", PROJECT, "--owner", OWNER, "--format", "json"))
    fields = json.loads(gh("project", "field-list", PROJECT, "--owner", OWNER, "--format", "json"))["fields"]
    f = next(x for x in fields if x["name"] == "Status")
    opt = next(o["id"] for o in f["options"] if o["name"] == STATES[state])
    item = project_items().get(n)
    if not item:
        add = json.loads(gh("project", "item-add", PROJECT, "--owner", OWNER, "--url",
                            f"https://github.com/{REPO}/issues/{n}", "--format", "json"))
        item_id = add["id"]
    else:
        item_id = item["id"]
    gh("project", "item-edit", "--id", item_id, "--project-id", proj["id"], "--field-id", f["id"], "--single-select-option-id", opt)
    print(f"#{n} -> {STATES[state]}")


def load_template(kind):
    f = TEMPLATES / f"{kind}.md"
    if not f.exists():
        known = ", ".join(sorted(p.stem for p in TEMPLATES.glob("*.md")))
        sys.exit(f"unknown issue type '{kind}'; known: {known}")
    m = re.match(r"---\n(.*?)\n---\n(.*)", f.read_text(), re.S)
    meta = {}
    for ln in m.group(1).splitlines():
        k, _, v = ln.partition(":")
        meta[k.strip()] = v.strip().strip("\"'")
    return meta, m.group(2).lstrip("\n")


def cmd_template(kind=None):
    if not kind:
        for f in sorted(TEMPLATES.glob("*.md")):
            meta, _ = load_template(f.stem)
            print(f"  {f.stem:<14} {meta.get('about', '')}")
        return
    print(load_template(kind)[1], end="")


def cmd_new(argv):
    ap = argparse.ArgumentParser(prog="board.py new")
    ap.add_argument("kind")
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True, help="filled-in template body ('-' for stdin)")
    ap.add_argument("--area", help="one of: " + (", ".join(AREAS) or "(any; set `areas` in .factory/config.json)"))
    ap.add_argument("--size", choices=["S", "M", "L"])
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--milestone")
    ap.add_argument("--parent", type=int)
    ap.add_argument("--from", dest="origin", type=int, help="issue this came from (decided type)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    meta, tpl = load_template(a.kind)
    body = sys.stdin.read() if a.body_file == "-" else Path(a.body_file).read_text()
    missing = [h for h in re.findall(r"^### .+$", tpl, re.M) if h not in body]
    if missing:
        sys.exit("body is missing sections from the template: " + ", ".join(missing))
    prose = re.sub(r"<!--.*?-->|`[^`]*`", "", body, flags=re.S)
    if re.search(r"<[A-Za-z][^<>\n]*>", prose):
        sys.exit("body still has <placeholder> text from the template")
    if a.area and AREAS and a.area not in AREAS:
        sys.exit(f"unknown area '{a.area}'; known: {', '.join(AREAS)}")
    labels_ = [l.strip() for l in meta.get("labels", "").split(",") if l.strip()] + a.label
    if a.area:
        labels_.append(f"area:{a.area}")
    if a.size:
        labels_.append(f"size:{a.size}")
    cmd = ["issue", "create", "-R", REPO, "--title", a.title, "--body-file", "-"]
    for l in dict.fromkeys(labels_):
        cmd += ["--label", l]
    if meta.get("assignees"):
        cmd += ["--assignee", meta["assignees"]]
    if a.milestone:
        cmd += ["--milestone", a.milestone]
    if a.dry_run:
        print("gh " + " ".join(cmd) + "\n---\n" + body)
        return
    p = subprocess.run(["gh", *cmd], input=body, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"gh issue create failed: {p.stderr.strip()}")
    url = p.stdout.strip().splitlines()[-1]
    n = int(url.rsplit("/", 1)[1])
    print(url)
    if a.kind == "decided":
        gh("issue", "close", str(n), "-R", REPO, "-c", f"**[Claude]** Decided in #{a.origin}" if a.origin else "**[Claude]** Decided in a package")
        return
    cmd_status(n, "todo")
    if a.parent:
        cmd_sub(a.parent, n)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "repo":
        print(REPO)
    elif a[0] == "project-url":
        print(f"https://github.com/users/{OWNER}/projects/{PROJECT}" if PROJECT else "(no project configured)")
    elif a[0] == "ready":
        cmd_ready()
    elif a[0] == "board":
        cmd_board()
    elif a[0] == "decisions":
        cmd_decisions()
    elif a[0] == "inbox":
        cmd_inbox()
    elif a[0] == "adr-pending":
        cmd_adr_pending()
    elif a[0] == "template" and len(a) <= 2:
        cmd_template(*a[1:])
    elif a[0] == "new" and len(a) >= 2:
        cmd_new(a[1:])
    elif a[0] == "sub" and len(a) == 3:
        cmd_sub(int(a[1].lstrip("#")), int(a[2].lstrip("#")))
    elif a[0] == "deps" and len(a) == 2:
        cmd_deps(int(a[1].lstrip("#")))
    elif a[0] == "status" and len(a) == 3:
        cmd_status(int(a[1].lstrip("#")), a[2])
    else:
        sys.exit(__doc__)
