"""Offline updater contract: consent, official integrity, safe replace and fallback."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts"
sys.path.insert(0, str(SCRIPTS))
import funavatar_installer as installer
import funavatar_update as updater


def package_bytes(version="0.5.1", extras=(), overrides=None):
    files = {
        "funavatar/SKILL.md": "name: funavatar\nNew skill version\n",
        "funavatar/VERSION": version + "\n",
        "funavatar/scripts/funavatar.py": "raise AssertionError('downloaded code executed')\n",
        "funavatar/scripts/funavatar_update.py": "raise AssertionError('downloaded updater executed')\n",
        "funavatar/scripts/funavatar_installer.py": "raise AssertionError('downloaded installer executed')\n",
    }
    files.update(overrides or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        for name, content in extras:
            if isinstance(name, str):
                entry = zipfile.ZipInfo(name)
                # Keep deliberately malformed wire names on Windows too;
                # ZipInfo.__init__ otherwise repairs backslashes in the test.
                entry.filename = name
                entry.compress_type = zipfile.ZIP_DEFLATED
            else:
                entry = name
            archive.writestr(entry, content)
    return output.getvalue()


class ReleaseFixture:
    def __init__(self, version="0.5.1", package=None, checksums=None):
        package = package_bytes(version) if package is None else package
        checksums = checksums if checksums is not None else (hashlib.sha256(package).hexdigest() + "  funavatar-skill.zip\n").encode()
        self.calls = []
        self.content = {}
        self.release = {"tag_name": "v" + version, "draft": False, "prerelease": False,
                        "html_url": updater.RELEASE_BASE + "tag/v" + version, "assets": []}
        for name, content in ((updater.PACKAGE, package), (updater.CHECKSUMS, checksums)):
            url = updater.RELEASE_BASE + f"download/v{version}/{name}"
            self.content[url] = content
            self.release["assets"].append({"name": name, "size": len(content), "browser_download_url": url,
                                           "digest": "sha256:" + hashlib.sha256(content).hexdigest()})

    def fetch(self, url, limit):
        self.calls.append(url)
        result = json.dumps(self.release).encode() if url == updater.LATEST_URL else self.content[url]
        if len(result) > limit:
            raise updater.UpdateError("release_size_limit")
        return result


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home"
        self.source = self.root / "extracted/funavatar"
        (self.source / "scripts").mkdir(parents=True)
        (self.source / "SKILL.md").write_text("name: funavatar\n", encoding="utf-8")
        (self.source / "VERSION").write_text("0.5.0\n", encoding="utf-8")
        (self.source / "scripts/funavatar.py").write_text("print('current version')\n", encoding="utf-8")
        for name in ("funavatar_update.py", "funavatar_installer.py"):
            shutil.copy2(SCRIPTS / name, self.source / "scripts" / name)
        self.destinations = installer.install("both", self.home, self.source)
        self.fixture = ReleaseFixture()

    def snapshots(self):
        return [installer.snapshot(path) for path in self.destinations]

    def enable(self, target="both"):
        result = updater.run("enable", self.home, target, fetch=self.fixture.fetch)
        self.assertEqual(result["status"], "enabled", result)
        return result

    def assert_unchanged_failure(self, fixture=None):
        self.enable()
        previous = self.snapshots()
        result = updater.run("auto", self.home, fetch=(fixture or self.fixture).fetch)
        self.assertEqual(result["status"], "deferred", result)
        self.assertFalse(result["updated"])
        self.assertTrue(result["continue_current"])
        self.assertEqual(self.snapshots(), previous)
        self.assertFalse((self.home / ".local/share/funavatar/backups").exists())
        return result

    def test_auto_is_disabled_without_consent_and_creates_no_state_or_requests(self):
        previous = self.snapshots()
        shutil.rmtree(self.home / ".local")
        result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(self.fixture.calls, [])
        self.assertFalse((self.home / ".local/share/funavatar/auto-update.json").exists())
        self.assertFalse((self.home / ".local/share/funavatar/update.lock").exists())
        self.assertFalse((self.home / ".local").exists())
        self.assertEqual(self.snapshots(), previous)

    def test_enable_is_explicit_scoped_and_outside_managed_files(self):
        previous = self.snapshots()
        self.assertEqual(updater.run("enable", self.home)["reason"], "explicit_target_required")
        self.enable("codex")
        config = json.loads((self.home / ".local/share/funavatar/auto-update.json").read_text())
        self.assertEqual(config, {"schema_version": 1, "enabled": True, "target": "codex"})
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(self.snapshots(), previous)

    def test_unmanaged_zip_copy_cannot_enable_by_synthesizing_receipt(self):
        receipt = self.destinations[0] / installer.RECEIPT
        receipt.unlink()
        result = updater.run("enable", self.home, "codex")
        self.assertEqual(result["reason"], "installation_changed_or_unmanaged")
        self.assertFalse(receipt.exists())
        self.assertFalse((self.home / ".local/share/funavatar/auto-update.json").exists())

    def test_enable_requires_every_selected_target_to_be_installed(self):
        shutil.rmtree(self.destinations[1])
        self.assertEqual(updater.run("enable", self.home, "both")["reason"], "target_not_installed")
        self.enable("codex")
        self.assertFalse(self.destinations[1].exists())

    def test_check_only_reads_release_metadata_and_never_updates_or_enables(self):
        previous = self.snapshots()
        result = updater.run("check", self.home, "both", fetch=self.fixture.fetch)
        self.assertEqual(result["status"], "update_available")
        self.assertEqual(result["latest_version"], "0.5.1")
        self.assertEqual(self.fixture.calls, [updater.LATEST_URL])
        self.assertEqual(self.snapshots(), previous)
        self.assertFalse((self.home / ".local/share/funavatar/auto-update.json").exists())

    def test_auto_updates_only_consented_target_and_never_executes_downloaded_code(self):
        self.enable("codex")
        previous = self.snapshots()
        result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["status"], "updated", result)
        self.assertTrue(result["integrity_verified"])
        self.assertEqual(result["installed_versions"], {"codex": "0.5.1"})
        self.assertEqual(result["reread_skill_paths"], [str(self.destinations[0] / "SKILL.md")])
        self.assertEqual(installer.verify_existing(self.destinations[0]), installer.snapshot(self.destinations[0]))
        self.assertEqual(installer.snapshot(self.destinations[1]), previous[1])
        backups = list((self.home / ".local/share/funavatar/backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(installer.snapshot(backups[0]), previous[0])
        self.assertEqual(json.loads((self.home / ".local/share/funavatar/auto-update.json").read_text())["target"], "codex")

    def test_manual_update_does_not_enable_automatic_updates(self):
        result = updater.run("update", self.home, "both", fetch=self.fixture.fetch)
        self.assertEqual(result["status"], "updated", result)
        self.assertFalse((self.home / ".local/share/funavatar/auto-update.json").exists())
        self.assertEqual(updater.run("auto", self.home)["status"], "disabled")

    def test_disable_stops_subsequent_network_checks(self):
        self.enable()
        self.assertEqual(updater.run("disable", self.home)["status"], "disabled")
        self.assertEqual(updater.run("auto", self.home, fetch=self.fixture.fetch)["status"], "disabled")
        self.assertEqual(self.fixture.calls, [])

    def test_offline_auto_defers_safely_and_cli_allows_current_work(self):
        self.enable()
        previous = self.snapshots()
        with patch.object(updater, "_fetch", side_effect=updater.UpdateError("network_unavailable")), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(updater.main(["auto", "--home", str(self.home)]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(result["reason"], "network_unavailable")
        self.assertEqual(result["installed_versions"], {"codex": "0.5.0", "claude": "0.5.0"})
        self.assertFalse(result["updated"])
        self.assertTrue(result["continue_current"])
        self.assertEqual(self.snapshots(), previous)

    def test_untrusted_release_identity_prerelease_and_arbitrary_assets_are_refused(self):
        changes = [
            lambda release: release.update(prerelease=True),
            lambda release: release.update(draft=True),
            lambda release: release.update(tag_name="v0.5.1-rc1"),
            lambda release: release.update(html_url="https://github.com/other/project/releases/tag/v0.5.1"),
            lambda release: release["assets"][0].update(browser_download_url="https://example.org/skill.zip"),
            lambda release: release["assets"][0].update(name="arbitrary.zip"),
            lambda release: release["assets"].append(dict(release["assets"][0])),
            lambda release: release["assets"][0].update(size=updater.MAX_PACKAGE + 1),
        ]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                fixture = ReleaseFixture()
                change(fixture.release)
                result = self.assert_unchanged_failure(fixture)
                self.assertEqual(result["reason"], "invalid_stable_release")
                self.assertEqual(fixture.calls, [updater.LATEST_URL])

    def test_equal_versions_and_downgrades_do_not_download_packages(self):
        self.enable()
        previous = self.snapshots()
        for version, expected in (("0.5.0", "up_to_date"), ("0.4.9", "newer_installed")):
            fixture = ReleaseFixture(version)
            result = updater.run("auto", self.home, fetch=fixture.fetch)
            self.assertEqual(result["status"], expected)
            self.assertEqual(fixture.calls, [updater.LATEST_URL])
        self.assertEqual(self.snapshots(), previous)

    def test_checksum_and_github_asset_digests_are_both_checked(self):
        fixture = ReleaseFixture(checksums=("0" * 64 + "  funavatar-skill.zip\n").encode())
        self.assertEqual(self.assert_unchanged_failure(fixture)["reason"], "package_checksum_mismatch")
        for index in (0, 1):
            fixture = ReleaseFixture()
            fixture.release["assets"][index]["digest"] = "sha256:" + "0" * 64
            self.assertEqual(self.assert_unchanged_failure(fixture)["reason"], "release_digest_mismatch")

    def test_checksum_manifest_must_name_one_exact_package(self):
        for sums in (b"not a checksum\n", ("0" * 64 + "  other.zip\n").encode(),
                     (("0" * 64 + "  funavatar-skill.zip\n") * 2).encode()):
            self.assertEqual(self.assert_unchanged_failure(ReleaseFixture(checksums=sums))["reason"],
                             "invalid_checksum_manifest")

    def test_zip_traversal_absolute_windows_duplicate_and_receipt_entries_are_refused(self):
        for name in ("funavatar/../outside", "/outside", "C:/outside", "funavatar/scripts/../../escape.py",
                     "funavatar/scripts/CON.txt", "funavatar/scripts/evil.", "funavatar/scripts\\escape.py",
                     "funavatar/.funavatar-install.json", "funavatar/skill.md", "another/SKILL.md"):
            with self.subTest(name=name):
                result = self.assert_unchanged_failure(ReleaseFixture(package=package_bytes(extras=[(name, "unsafe")])) )
                self.assertEqual(result["reason"], "unsafe_package_structure")
        self.assertFalse((self.root / "outside").exists())

    def test_zip_stored_names_are_checked_before_platform_normalization(self):
        package = package_bytes(extras=[("funavatar/scripts\\escape.py", "unsafe")])
        real_zip = zipfile.ZipFile

        class NormalizingZipFile(real_zip):
            def infolist(self):
                entries = super().infolist()
                for entry in entries:
                    entry.filename = entry.filename.replace("\\", "/")
                return entries

        with patch.object(updater.zipfile, "ZipFile", NormalizingZipFile):
            result = self.assert_unchanged_failure(ReleaseFixture(package=package))
        self.assertEqual(result["reason"], "unsafe_package_structure")

    def test_zip_symlink_and_high_expansion_are_refused_without_extraction(self):
        entry = zipfile.ZipInfo("funavatar/scripts/link.py")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        fixture = ReleaseFixture(package=package_bytes(extras=[(entry, "/outside")]))
        self.assertEqual(self.assert_unchanged_failure(fixture)["reason"], "unsafe_package_structure")
        fixture = ReleaseFixture(package=package_bytes(extras=[("funavatar/assets/bomb.txt", "0" * 200000)]))
        self.assertEqual(self.assert_unchanged_failure(fixture)["reason"], "unsafe_package_structure")

    def test_zip_file_count_expansion_budget_and_version_must_match(self):
        extras = [(f"funavatar/assets/file-{index}.txt", "x") for index in range(updater.MAX_ENTRIES)]
        self.assertEqual(self.assert_unchanged_failure(ReleaseFixture(package=package_bytes(extras=extras)))["reason"],
                         "unsafe_package_structure")
        with patch.object(updater, "MAX_EXPANDED", 5):
            self.assertEqual(self.assert_unchanged_failure()["reason"], "package_expansion_limit")
        fixture = ReleaseFixture(package=package_bytes("0.4.9"))
        self.assertEqual(self.assert_unchanged_failure(fixture)["reason"], "package_version_mismatch")

    def test_local_edits_stop_all_targets_before_network_or_cutover(self):
        self.enable()
        (self.destinations[1] / "personal.txt").write_text("keep my notes", encoding="utf-8")
        previous = self.snapshots()
        result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["reason"], "installation_changed_or_unmanaged")
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(self.snapshots(), previous)

    def test_late_local_edits_are_refused_by_the_shared_installer(self):
        self.enable()
        def change_after_preflight(url, limit):
            content = self.fixture.fetch(url, limit)
            if url.endswith(updater.PACKAGE):
                (self.destinations[1] / "personal.txt").write_text("arrived during download", encoding="utf-8")
            return content
        previous = installer.snapshot(self.destinations[0])
        result = updater.run("auto", self.home, fetch=change_after_preflight)
        self.assertEqual(result["reason"], "installation_refused_or_rolled_back")
        self.assertEqual(installer.snapshot(self.destinations[0]), previous)
        self.assertEqual((self.destinations[1] / "personal.txt").read_text(), "arrived during download")

    def test_legacy_install_during_download_cannot_make_auto_downgrade(self):
        self.enable()
        def legacy_install_during_fetch(url, limit):
            content = self.fixture.fetch(url, limit)
            if url.endswith(updater.PACKAGE):
                (self.source / "VERSION").write_text("0.6.0\n", encoding="utf-8")
                (self.source / "SKILL.md").write_text("newer installed release\n", encoding="utf-8")
                # Simulate the pre-lock installer: valid managed replacement
                # with fresh receipts, without participating in the new guard.
                installer._install_under_lock("both", self.home, self.source, update=True)
            return content
        result = updater.run("auto", self.home, fetch=legacy_install_during_fetch)
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(result["reason"], "installation_changed_during_update")
        self.assertEqual(result["installed_versions"], {"codex": "0.6.0", "claude": "0.6.0"})
        self.assertFalse(result["updated"])
        for destination in self.destinations:
            self.assertEqual(installer.verify_existing(destination), installer.snapshot(self.source))

    def test_second_target_cutover_failure_restores_both_versions(self):
        self.enable()
        previous = self.snapshots()
        original = Path.rename
        def fail_second(path, destination):
            if path.name == "funavatar" and path.parent.name.startswith(".funavatar-install-") and destination == self.destinations[1]:
                raise OSError("simulated disk failure")
            return original(path, destination)
        with patch.object(Path, "rename", fail_second):
            result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["reason"], "installation_refused_or_rolled_back")
        self.assertEqual(self.snapshots(), previous)
        with installer.installation_lock(self.home):
            pass  # A persistent guard file is unlocked after rollback.

    def test_concurrent_invocation_defers_without_network_or_replacement(self):
        self.enable()
        previous = self.snapshots()
        with updater._update_lock(self.home):
            result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["reason"], "update_busy")
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(self.snapshots(), previous)

    def test_shared_guard_stops_manual_installer_processes_and_auto_cutovers(self):
        self.enable()
        previous = self.snapshots()
        with installer.installation_lock(self.home):
            for script in (SCRIPTS.parents[2] / "install.py", self.source / "scripts/funavatar_installer.py"):
                result = subprocess.run([sys.executable, str(script), "--target", "both", "--update", "--home", str(self.home)],
                                        cwd=self.root, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("busy", result.stderr)
            result = updater.run("auto", self.home, fetch=self.fixture.fetch)
            self.assertEqual(result["reason"], "update_busy")
        self.assertEqual(self.snapshots(), previous)
        self.assertEqual(self.fixture.calls, [])

    def test_manual_and_automatic_updates_refuse_symlinked_backup_directory(self):
        self.enable()
        previous = self.snapshots()
        outside = self.root / "outside-backups"
        outside.mkdir()
        backup = self.home / ".local/share/funavatar/backups"
        try:
            backup.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Filesystem does not permit symlinks: {type(error).__name__}")
        result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["reason"], "installation_refused_or_rolled_back")
        self.assertEqual(self.snapshots(), previous)
        self.assertEqual(list(outside.iterdir()), [])

    def test_killed_lock_holder_does_not_block_future_updates(self):
        self.enable()
        marker = self.root / "lock-ready"
        worker = ("import sys,time; from pathlib import Path; "
                  "sys.path.insert(0,sys.argv[1]); import funavatar_installer as installer\n"
                  "with installer.installation_lock(Path(sys.argv[2])):\n"
                  "    Path(sys.argv[3]).write_text('ready')\n"
                  "    time.sleep(30)\n")
        process = subprocess.Popen([sys.executable, "-c", worker, str(SCRIPTS), str(self.home), str(marker)],
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "Lock holder did not start within ten seconds")
            self.assertEqual(updater.run("auto", self.home, fetch=self.fixture.fetch)["reason"], "update_busy")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        result = updater.run("auto", self.home, fetch=self.fixture.fetch)
        self.assertEqual(result["status"], "updated", result)

    def test_invalid_optin_configuration_never_permits_auto(self):
        self.enable()
        config = self.home / ".local/share/funavatar/auto-update.json"
        for content in ('{"schema_version":1,"enabled":"true","target":"both"}', '{"enabled":true}', '{bad'):
            config.write_text(content, encoding="utf-8")
            result = updater.run("auto", self.home, fetch=self.fixture.fetch)
            self.assertEqual(result["reason"], "invalid_configuration")
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(updater.run("disable", self.home)["status"], "disabled")

    def test_symlinked_configuration_is_refused_without_touching_target(self):
        self.enable()
        config = self.home / ".local/share/funavatar/auto-update.json"
        original = self.root / "original.json"
        config.rename(original)
        try:
            config.symlink_to(original)
        except OSError as error:
            self.skipTest(f"Filesystem does not permit symlinks: {type(error).__name__}")
        content = original.read_bytes()
        self.assertEqual(updater.run("auto", self.home, fetch=self.fixture.fetch)["reason"], "symlinked_path")
        self.assertEqual(updater.run("disable", self.home)["reason"], "symlinked_path")
        self.assertEqual(original.read_bytes(), content)
        self.assertEqual(self.fixture.calls, [])

    def test_installed_zip_layout_bootstraps_and_runs_without_repository_or_git(self):
        other_home = self.root / "standalone-home"
        environment = dict(os.environ, PYTHONPATH="", PYTHONNOUSERSITE="1")
        install = subprocess.run([sys.executable, str(self.source / "scripts/funavatar_installer.py"),
                                  "--target", "codex", "--home", str(other_home)],
                                 cwd=self.root, env=environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(install.returncode, 0, install.stderr)
        script = other_home / ".agents/skills/funavatar/scripts/funavatar_update.py"
        for args, expected in ((["auto"], "disabled"), (["enable", "--target", "codex"], "enabled"),
                               (["disable"], "disabled")):
            result = subprocess.run([sys.executable, str(script), *args, "--home", str(other_home)],
                                    cwd=self.root, env=environment, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], expected)

    def test_redirect_allowlist_rejects_arbitrary_hosts_and_credentials(self):
        for url in ("http://github.com/xcapsa/FunAvatar/releases/download/v0.5.1/funavatar-skill.zip",
                    "https://evil.example/funavatar.zip", "https://github.com/other/repo/releases/download/a/b",
                    "https://user:token@release-assets.githubusercontent.com/file", "https://github.com:444/file"):
            with self.subTest(url=url), self.assertRaises(updater.UpdateError):
                updater._allow_url(url)


if __name__ == "__main__":
    unittest.main()
