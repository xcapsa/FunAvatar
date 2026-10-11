import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("funavatar_install", ROOT / "install.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("name: funavatar\n", encoding="utf-8")
        (self.source / "scripts").mkdir()
        (self.source / "scripts" / "funavatar.py").write_text("print('ready')\n", encoding="utf-8")
        self.home = self.root / "home"

    def test_installs_both_complete_skills_and_preserves_source(self):
        destinations = INSTALLER.install("both", self.home, self.source)
        self.assertEqual(len(destinations), 2)
        for destination in destinations:
            self.assertEqual((destination / "SKILL.md").read_bytes(), (self.source / "SKILL.md").read_bytes())
            self.assertTrue((destination / "scripts" / "funavatar.py").is_file())
        self.assertTrue((self.source / "SKILL.md").is_file())

    def test_existing_install_prevents_partial_install_and_preserves_content(self):
        existing = self.home / ".claude" / "skills" / "funavatar"
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_text("custom work", encoding="utf-8")
        with self.assertRaises(ValueError):
            INSTALLER.install("both", self.home, self.source)
        self.assertEqual((existing / "SKILL.md").read_text(), "custom work")
        self.assertFalse((self.home / ".agents" / "skills" / "funavatar").exists())

    def test_failed_second_copy_rolls_back_only_new_installation(self):
        original_copy = INSTALLER.shutil.copytree
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated full disk")
            return original_copy(*args, **kwargs)

        with patch.object(INSTALLER.shutil, "copytree", side_effect=fail_second):
            with self.assertRaises(OSError):
                INSTALLER.install("both", self.home, self.source)
        self.assertFalse((self.home / ".agents" / "skills" / "funavatar").exists())
        self.assertFalse((self.home / ".claude" / "skills" / "funavatar").exists())
        self.assertEqual(list(self.home.rglob(".funavatar-install-*")), [])

    def test_broken_symlink_is_preserved(self):
        destination = self.home / ".agents" / "skills" / "funavatar"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(self.root / "missing")
        with self.assertRaises(ValueError):
            INSTALLER.install("codex", self.home, self.source)
        self.assertTrue(destination.is_symlink())


if __name__ == "__main__":
    unittest.main()
