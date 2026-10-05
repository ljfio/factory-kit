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


if __name__ == "__main__":
    unittest.main()
