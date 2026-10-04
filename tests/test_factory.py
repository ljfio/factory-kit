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
        self.proj = self.tmp / "proj"
        self.proj.mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=self.proj)
        self.fake_gh()
        self.factory("init", "--repo", "acme/widgets", "--source", str(self.kit), "--ref", "main")

    def fake_gh(self):
        """init asks gh for the owner id; answer without the network."""
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        gh = bin_ / "gh"
        gh.write_text("#!/bin/sh\necho 4242\n")
        gh.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}

    def factory(self, *args):
        p = subprocess.run([sys.executable, str(ROOT / "factory.py"), *args], cwd=self.proj,
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def update(self, *args):
        return self.factory("update", "--source", str(self.kit), "--ref", "main", *args)

    def kit_commit(self, path, text):
        f = self.kit / path
        f.write_text(f.read_text() + text)
        sh(*GIT, "commit", "-qam", "change", cwd=self.kit)

    def test_init_renders_and_records(self):
        owner = (self.proj / ".github/CODEOWNERS").read_text()
        self.assertIn("@acme", owner)
        self.assertNotIn("{{", owner)
        wf = (self.proj / ".github/workflows/claude.yml").read_text()
        self.assertIn("github.event.sender.id == 4242", wf)
        self.assertIn("${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", wf)
        self.assertIn("factory-kit:begin", (self.proj / "CLAUDE.md").read_text())
        m = json.loads((self.proj / ".factory/manifest.json").read_text())
        self.assertEqual(m["files"][".claude/skills/board/SKILL.md"]["kind"], "managed")

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
        out = subprocess.run([sys.executable, ".claude/scripts/board.py", "repo"], cwd=self.proj,
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "acme/widgets")


if __name__ == "__main__":
    unittest.main()
