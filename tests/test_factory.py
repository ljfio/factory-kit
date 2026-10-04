"""Installer tests: init, update (clean, modified, conflict, removed file), scaffold safety. Needs git only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]


def sh(*cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


class FactoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.kit = self.tmp / "kit"
        sh("git", "clone", "-q", str(ROOT), str(self.kit), cwd=self.tmp)
        sh("git", "checkout", "-q", "-B", "main", cwd=self.kit)  # whatever branch (or detached HEAD) is checked out here
        self.overlay_working_tree()
        self.proj = self.tmp / "proj"
        self.proj.mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=self.proj)
        self.fake_gh()
        self.factory("init", "--repo", "acme/widgets", "--source", str(self.kit), "--ref", "main")

    def overlay_working_tree(self):
        """Test the files on disk, committed or not, so nothing has to be committed before running the tests."""
        files = sh("git", "ls-files", "-co", "--exclude-standard", cwd=ROOT).splitlines()
        for tracked in sh("git", "ls-files", cwd=self.kit).splitlines():
            if tracked not in files:
                (self.kit / tracked).unlink()
        for rel in files:
            if (ROOT / rel).is_file():
                (self.kit / rel).parent.mkdir(parents=True, exist_ok=True)
                (self.kit / rel).write_bytes((ROOT / rel).read_bytes())
        sh("git", "add", "-A", cwd=self.kit)
        sh(*GIT, "commit", "-qm", "working tree", "--allow-empty", cwd=self.kit)

    def fake_gh(self):
        """init asks gh for the owner id; answer without the network."""
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        gh = bin_ / "gh"
        gh.write_text('#!/bin/sh\ncase "$*" in "api user --jq .login") echo dev;; *) echo 4242;; esac\n')
        gh.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}

    def fresh_project(self, *init_args):
        """A second project initialised with extra init arguments (agents)."""
        proj = self.tmp / "proj2"
        proj.mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=proj)
        p = subprocess.run([sys.executable, str(ROOT / "factory.py"), "init", "--repo", "acme/widgets", "--source",
                            str(self.kit), "--ref", "main", *init_args], cwd=proj, capture_output=True, text=True,
                           env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return proj

    def factory(self, *args):
        p = subprocess.run([sys.executable, str(ROOT / "factory.py"), *args], cwd=self.proj,
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def agent(self, *args):
        return self.factory("agent", *args, "--source", str(self.kit), "--ref", "main")

    def update(self, *args):
        return self.factory("update", "--source", str(self.kit), "--ref", "main", *args)

    def kit_commit(self, path, text):
        f = self.kit / path
        f.write_text(f.read_text() + text)
        sh(*GIT, "commit", "-qam", "change", cwd=self.kit)

    def test_init_renders_and_records(self):
        owner = (self.proj / ".github/CODEOWNERS").read_text()
        self.assertIn("@dev", owner)
        self.assertNotIn("{{", owner)
        wf = (self.proj / ".github/workflows/claude.yml").read_text()
        self.assertIn("github.event.sender.id == 4242", wf)
        self.assertIn("${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", wf)
        self.assertIn("factory-kit:begin", (self.proj / "CLAUDE.md").read_text())
        m = json.loads((self.proj / ".factory/manifest.json").read_text())
        self.assertEqual(m["files"][".claude/skills/board/SKILL.md"]["kind"], "managed")

    def test_owner_is_the_signed_in_user_not_the_repo_account(self):
        cfg = json.loads((self.proj / ".factory/config.json").read_text())
        self.assertEqual((cfg["owner"], cfg["project_owner"]), ("dev", "acme"))
        self.assertIn("@dev", (self.proj / ".github/CODEOWNERS").read_text())

    def test_owner_flag_overrides(self):
        proj = self.fresh_project("--owner", "someone")
        cfg = json.loads((proj / ".factory/config.json").read_text())
        self.assertEqual(cfg["owner"], "someone")
        self.assertIn("@someone", (proj / ".github/CODEOWNERS").read_text())

    def test_managed_files_are_copied_verbatim(self):
        self.assertEqual((self.proj / ".factory/factory.py").read_bytes(), (ROOT / "factory.py").read_bytes())

    def test_update_replaces_unmodified_managed_file(self):
        self.kit_commit("kit/.claude/skills/board/SKILL.md", "\nnew line\n")
        out = self.update()
        self.assertIn("updated", out)
        self.assertIn("new line", (self.proj / ".claude/skills/board/SKILL.md").read_text())

    def test_update_never_overwrites_local_changes(self):
        f = self.proj / ".claude/skills/board/SKILL.md"
        f.write_text(f.read_text() + "\nmine\n")
        self.kit_commit("kit/.claude/skills/board/SKILL.md", "\ntheirs\n")
        out = self.update()
        self.assertIn("conflict", out)
        self.assertIn("mine", f.read_text())
        self.assertNotIn("theirs", f.read_text())
        self.assertIn("theirs", (self.proj / ".claude/skills/board/SKILL.md.factory-new").read_text())

    def test_scaffold_is_kept(self):
        f = self.proj / ".github/workflows/claude.yml"
        f.write_text(f.read_text() + "# mine\n")
        self.kit_commit("kit/.github/workflows/claude.yml", "# theirs\n")
        self.update()
        self.assertIn("# mine", f.read_text())
        self.assertNotIn("# theirs", f.read_text())
        self.assertTrue((self.proj / ".github/workflows/claude.yml.factory-new").exists())

    def test_removed_upstream_file_is_deleted_when_unmodified(self):
        sh("git", "rm", "-q", "kit/.claude/skills/board/SKILL.md", cwd=self.kit)
        sh(*GIT, "commit", "-qm", "drop", cwd=self.kit)
        self.update()
        self.assertFalse((self.proj / ".claude/skills/board/SKILL.md").exists())

    def test_exclude_skips_paths(self):
        cfg = self.proj / ".factory/config.json"
        c = json.loads(cfg.read_text())
        c["exclude"] = [".claude/skills/run-parallel/"]
        cfg.write_text(json.dumps(c))
        (self.proj / ".claude/skills/run-parallel/SKILL.md").unlink()
        self.kit_commit("kit/.claude/skills/run-parallel/SKILL.md", "\nx\n")
        self.update()
        self.assertFalse((self.proj / ".claude/skills/run-parallel/SKILL.md").exists())

    def test_board_reads_config(self):
        out = subprocess.run([sys.executable, ".factory/scripts/board.py", "repo"], cwd=self.proj,
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "acme/widgets")


    def test_default_install_is_claude_only(self):
        c = json.loads((self.proj / ".factory/config.json").read_text())
        self.assertEqual(c["agents"], ["claude"])
        self.assertTrue((self.proj / ".claude/skills/board/SKILL.md").exists())
        self.assertFalse((self.proj / ".agents").exists())
        self.assertTrue((self.proj / ".github/workflows/claude.yml").exists())
        self.assertFalse((self.proj / "AGENTS.md").exists())

    def test_codex_only_gets_agents_skills_and_no_claude_files(self):
        p = self.fresh_project("--agents", "codex")
        self.assertTrue((p / ".agents/skills/board/SKILL.md").exists())
        self.assertFalse((p / ".claude").exists())
        self.assertFalse((p / ".github/workflows/claude.yml").exists())
        self.assertIn("factory-kit:begin", (p / "AGENTS.md").read_text())
        self.assertFalse((p / "CLAUDE.md").exists())
        self.assertTrue((p / ".factory/scripts/board.py").exists())

    def test_skills_are_shared_and_instructions_point_at_one_file(self):
        p = self.fresh_project("--agents", "claude,codex,gemini,copilot,cursor")
        self.assertEqual(json.loads((p / ".factory/config.json").read_text())["instructions"], "AGENTS.md")
        self.assertTrue((p / ".claude/skills/board/SKILL.md").exists())
        self.assertTrue((p / ".agents/skills/board/SKILL.md").exists())  # codex and gemini need it; copilot and cursor reuse
        self.assertIn("factory-kit:begin -->\n## Delivery workflow", (p / "AGENTS.md").read_text())
        for pointer in ("CLAUDE.md", "GEMINI.md"):
            text = (p / pointer).read_text()
            self.assertIn("@./AGENTS.md", text)  # Gemini documents only ./ and ../ imports
            self.assertNotIn("Delivery workflow", text)

    def test_copilot_and_cursor_reuse_the_claude_skills(self):
        p = self.fresh_project("--agents", "claude,copilot,cursor")
        self.assertTrue((p / ".claude/skills/board/SKILL.md").exists())
        self.assertFalse((p / ".agents").exists())

    def test_unknown_agent_is_refused(self):
        proj = self.tmp / "proj3"
        proj.mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=proj)
        p = subprocess.run([sys.executable, str(ROOT / "factory.py"), "init", "--repo", "a/b", "--source", str(self.kit),
                            "--ref", "main", "--agents", "nope"], cwd=proj, capture_output=True, text=True, env=self.env)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unknown agent", p.stderr)

    def test_agent_add_and_remove(self):
        out = self.agent("add", "codex")
        self.assertIn(".agents/skills/board/SKILL.md", out)
        self.assertTrue((self.proj / ".agents/skills/board/SKILL.md").exists())
        self.assertIn("codex", json.loads((self.proj / ".factory/config.json").read_text())["agents"])
        self.agent("remove", "codex")
        self.assertFalse((self.proj / ".agents/skills/board/SKILL.md").exists())
        self.assertTrue((self.proj / ".claude/skills/board/SKILL.md").exists())

    def test_agent_remove_keeps_edited_skill(self):
        self.agent("add", "codex")
        f = self.proj / ".agents/skills/board/SKILL.md"
        f.write_text(f.read_text() + "mine\n")
        self.agent("remove", "codex")
        self.assertIn("mine", f.read_text())

    def test_skills_use_the_neutral_helper_path(self):
        for f in (self.proj / ".claude/skills").rglob("SKILL.md"):
            self.assertNotIn(".claude/scripts", f.read_text())

    def set_config(self, **kv):
        cfg = self.proj / ".factory/config.json"
        c = json.loads(cfg.read_text())
        c.update(kv)
        cfg.write_text(json.dumps(c, indent=2))

    def manifest(self):
        return json.loads((self.proj / ".factory/manifest.json").read_text())

    def test_exclude_removes_unedited_scaffold(self):
        rel = ".github/ISSUE_TEMPLATE/verification.md"
        self.assertTrue((self.proj / rel).exists())
        self.set_config(exclude=[rel])
        out = self.update()  # the kit did not change: the exclude alone must trigger the sync
        self.assertIn("removed", out)
        self.assertFalse((self.proj / rel).exists())
        self.assertNotIn(rel, self.manifest()["files"])

    def test_exclude_keeps_edited_scaffold(self):
        rel = ".github/ISSUE_TEMPLATE/verification.md"
        (self.proj / rel).write_text("mine\n")
        self.set_config(exclude=[rel])
        out = self.update()
        self.assertIn("modified locally", out)
        self.assertEqual((self.proj / rel).read_text(), "mine\n")

    def test_label_rename_is_not_a_kit_change(self):
        self.set_config(labels={"needs_env": "wait-env", "env_gated": "gated"})
        self.kit_commit("kit/.claude/skills/board/SKILL.md", "\nunrelated\n")  # a new kit commit so update runs
        out = self.update()
        self.assertNotIn("conflict", out)
        self.assertEqual(list(self.proj.rglob("*.factory-new")), [])
        # a real kit change to the same scaffold is still reported
        self.kit_commit("kit/.github/ISSUE_TEMPLATE/verification.md", "\nreal change\n")
        self.assertIn("conflict", self.update())

    def preinstalled_project(self, init_args=()):
        """A repository with older skills and a config of its own, but no manifest, then `init`."""
        proj = self.tmp / "proj3"
        (proj / ".claude/skills/board").mkdir(parents=True)
        (proj / ".factory").mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=proj)
        (proj / ".claude/skills/board/SKILL.md").write_text("old skill\n")
        (proj / ".factory/config.json").write_text(json.dumps({"areas": ["web"], "project": 7,
                                                               "labels": {"needs_env": "wait-env"}}))
        p = subprocess.run([sys.executable, str(ROOT / "factory.py"), "init", "--repo", "acme/widgets", "--source",
                            str(self.kit), "--ref", "main", *init_args], cwd=proj, capture_output=True, text=True,
                           env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return proj

    def test_adopt_takes_managed_files(self):
        proj = self.preinstalled_project(["--adopt"])
        skill = proj / ".claude/skills/board/SKILL.md"
        self.assertEqual(skill.read_bytes(), (ROOT / "kit/.claude/skills/board/SKILL.md").read_bytes())
        self.assertFalse(skill.with_name("SKILL.md.factory-new").exists())
        self.assertEqual(list(proj.rglob("*.factory-new")), [])

    def test_without_adopt_an_existing_managed_file_conflicts(self):
        proj = self.preinstalled_project()
        self.assertEqual((proj / ".claude/skills/board/SKILL.md").read_text(), "old skill\n")
        self.assertTrue((proj / ".claude/skills/board/SKILL.md.factory-new").exists())

    def test_init_keeps_existing_config(self):
        proj = self.preinstalled_project(["--adopt"])
        cfg = json.loads((proj / ".factory/config.json").read_text())
        self.assertEqual((cfg["areas"], cfg["project"]), (["web"], 7))
        self.assertEqual(cfg["labels"]["needs_env"], "wait-env")
        self.assertIn("env_gated", cfg["labels"])  # the kit's defaults fill the gaps
        self.assertEqual((cfg["repo"], cfg["owner"]), ("acme/widgets", "dev"))

    FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = " ".join(sys.argv[1:])
for prefix, rc, out in json.load(open(os.environ["FAKE_GH_RESPONSES"])):
    if args.startswith(prefix):
        sys.stdout.write(out)
        sys.exit(rc)
sys.stderr.write("fake gh: no response for " + args)
sys.exit(1)
"""

    def doctor(self, responses, **cfg):
        """Run `doctor` against a fake gh that answers by argument prefix: [(prefix, exit code, stdout)]."""
        gh = self.tmp / "bin" / "gh"
        gh.write_text(self.FAKE_GH)
        rfile = self.tmp / "responses.json"
        rfile.write_text(json.dumps(responses))
        self.env["FAKE_GH_RESPONSES"] = str(rfile)
        self.set_config(**cfg)
        return subprocess.run([sys.executable, str(ROOT / "factory.py"), "doctor"], cwd=self.proj,
                              capture_output=True, text=True, env=self.env)

    def healthy(self, labels=None):
        names = labels if labels is not None else sorted(self.wanted)
        return [
            ["auth status", 0, "Logged in\n  - Token scopes: 'project', 'repo'\n"],
            ["repo view", 0, "{}"],
            ["project view", 0, "{}"],
            ["api graphql", 0, json.dumps({"data": {"repository": {"projectsV2": {"nodes": [{"number": 3}]}}}})],
            ["label list", 0, json.dumps([{"name": n} for n in names])],
            ["api repos/acme/widgets/milestones", 0, json.dumps([{"title": "v1"}])],
            ["api repos/acme/widgets/environments/claude", 0, "{}"],
            ["secret list", 0, "CLAUDE_CODE_OAUTH_TOKEN\t2026-01-01\n"],
        ]

    @property
    def wanted(self):
        sys.path.insert(0, str(ROOT))
        import factory
        return factory.wanted_labels(json.loads((self.proj / ".factory/config.json").read_text()))

    def test_doctor_passes_when_everything_is_set_up(self):
        p = self.doctor(self.healthy(), project=3, waves=["v1"])
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("All checks passed", p.stdout)

    def test_doctor_reports_missing_label(self):
        names = [n for n in self.wanted if n != "decision-needed"]
        p = self.doctor(self.healthy(names), project=3, waves=["v1"])
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("FAIL labels exist", p.stdout)
        self.assertIn("decision-needed", p.stdout)
        self.assertIn("fix: python3 .factory/factory.py bootstrap", p.stdout)

    def test_doctor_reports_missing_project_scope_and_secret(self):
        r = self.healthy()
        r[0][2] = "Logged in\n  - Token scopes: 'repo'\n"
        r[7] = ["secret list", 0, ""]
        p = self.doctor(r, project=3, waves=["v1"])
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("gh auth refresh -s project", p.stdout)
        self.assertIn("gh secret set CLAUDE_CODE_OAUTH_TOKEN --env claude -R acme/widgets", p.stdout)

    def test_doctor_stops_when_gh_is_not_signed_in(self):
        p = self.doctor([["auth status", 1, ""]], project=3)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("gh auth login", p.stdout)

    def test_doctor_mentions_copilot_prerequisites_when_enabled(self):
        p = self.doctor(self.healthy(), project=3, waves=["v1"], agents=["claude", "copilot"])
        self.assertIn("Copilot cloud agent prerequisites", p.stdout)
        self.assertIn("administrator must enable", p.stdout)
        p = self.doctor(self.healthy(), project=3, waves=["v1"], agents=["claude"])
        self.assertNotIn("Copilot", p.stdout)


if __name__ == "__main__":
    unittest.main()
