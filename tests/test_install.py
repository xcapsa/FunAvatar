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

    def test_update_preserves_previous_versions_and_writes_matching_receipts(self):
        destinations = INSTALLER.install("both", self.home, self.source)
        previous = {path: INSTALLER.snapshot(path) for path in destinations}
        (self.source / "SKILL.md").write_text("updated skill\n", encoding="utf-8")
        (self.source / "VERSION").write_text("0.2.0\n", encoding="utf-8")
        INSTALLER.install("both", self.home, self.source, update=True)
        backups = list((self.home / ".local/share/funavatar/backups").iterdir())
        self.assertEqual(len(backups), 2)
        self.assertTrue(all(INSTALLER.snapshot(path) in previous.values() for path in backups))
        for destination in destinations:
            self.assertEqual(INSTALLER.snapshot(destination), INSTALLER.snapshot(self.source))
            receipt = INSTALLER.json.loads((destination / INSTALLER.RECEIPT).read_text())
            self.assertEqual(receipt["version"], "0.2.0")

    def test_local_edit_stops_both_updates_without_replacement(self):
        destinations = INSTALLER.install("both", self.home, self.source)
        (destinations[1] / "SKILL.md").write_text("personal customization\n", encoding="utf-8")
        previous = {path: INSTALLER.snapshot(path) for path in destinations}
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            INSTALLER.install("both", self.home, self.source, update=True)
        self.assertEqual({path: INSTALLER.snapshot(path) for path in destinations}, previous)
        self.assertFalse((self.home / ".local/share/funavatar/backups").exists())

    def test_untracked_customization_is_preserved(self):
        destinations = INSTALLER.install("codex", self.home, self.source)
        (destinations[0] / "personal-notes.md").write_text("Keep this", encoding="utf-8")
        with self.assertRaises(ValueError):
            INSTALLER.install("codex", self.home, self.source, update=True)
        self.assertEqual((destinations[0] / "personal-notes.md").read_text(), "Keep this")

    def test_recognized_legacy_installation_can_update_without_receipt(self):
        destination = self.home / ".agents/skills/funavatar"
        destination.parent.mkdir(parents=True)
        INSTALLER.shutil.copytree(self.source, destination)
        old_snapshot = INSTALLER.snapshot(destination)
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        with patch.object(INSTALLER, "known_baselines", return_value=[old_snapshot]):
            INSTALLER.install("codex", self.home, self.source, update=True)
        self.assertEqual(INSTALLER.snapshot(destination), INSTALLER.snapshot(self.source))

    def test_second_cutover_failure_restores_both_old_versions(self):
        destinations = INSTALLER.install("both", self.home, self.source)
        previous = {path: INSTALLER.snapshot(path) for path in destinations}
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        real_rename = Path.rename

        def fail_second_stage(path, target):
            if path.name == "funavatar" and path.parent.name.startswith(".funavatar-install-") and target == destinations[1]:
                raise OSError("simulated second cutover failure")
            return real_rename(path, target)

        with patch.object(Path, "rename", fail_second_stage):
            with self.assertRaises(OSError):
                INSTALLER.install("both", self.home, self.source, update=True)
        self.assertEqual({path: INSTALLER.snapshot(path) for path in destinations}, previous)
        self.assertEqual(list(self.home.rglob(".funavatar-install-*")), [])


if __name__ == "__main__":
    unittest.main()
