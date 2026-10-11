#!/usr/bin/env python3
"""Shared trusted installer for the source CLI and installed FunAvatar updater.

No downloaded installer code is imported or executed. Receipt verification,
managed hashes, staging, backups and rollback have one implementation here.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

RECEIPT = ".funavatar-install.json"


class InstallationBusy(ValueError):
    pass


class InstallationChanged(ValueError):
    pass


@contextmanager
def installation_lock(home):
    """Serialize manual and automatic installs, including their version checks."""
    home = Path(home).expanduser().resolve()
    folder = home / ".local/share/funavatar"
    if any(path.is_symlink() for path in (folder, *folder.parents)):
        raise ValueError("Symlinked installation state directory")
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / "update.lock"
    if lock.is_symlink():
        raise ValueError("Symlinked installation lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "r+b") as handle:
        # Keep the file in place: deleting a locked inode permits competing
        # processes to lock different files. OS locks release even after kill.
        if os.name == "nt":
            import msvcrt
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise InstallationBusy("Installation update is busy; current files are unchanged") from None
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise InstallationBusy("Installation update is busy; current files are unchanged") from None
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def snapshot(folder):
    """Hash managed files; caches and the installer receipt are not skill source."""
    files = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if "__pycache__" in relative.parts or path.suffix == ".pyc" or str(relative) == RECEIPT:
            continue
        if path.is_symlink():
            raise ValueError(f"Symlinked skill content cannot be replaced safely: {path}")
        if path.is_file():
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def verify_existing(destination, *, baselines=()):
    current = snapshot(destination)
    receipt = destination / RECEIPT
    if receipt.is_symlink():
        raise ValueError(f"Symlinked installation receipt; nothing replaced: {destination}")
    if receipt.is_file() and not receipt.is_symlink():
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
            expected = data["managed"]
            valid = (data["schema_version"] == 1 and isinstance(expected, dict)
                     and all(isinstance(key, str) and isinstance(value, str)
                             and re.fullmatch(r"[0-9a-f]{64}", value)
                             for key, value in expected.items()))
        except (ValueError, KeyError, TypeError):
            valid = False
        if not valid:
            raise ValueError(f"Invalid installation receipt; nothing replaced: {destination}")
        if current == expected:
            return current
    elif current in baselines:
        return current
    raise ValueError(f"Local changes or unrecognized installation; nothing replaced: {destination}")


def install(target, home, source=None, *, update=False, baselines=()):
    with installation_lock(home):
        return _install_under_lock(target, home, source, update=update, baselines=baselines)


def _install_under_lock(target, home, source=None, *, update=False, baselines=(), expected_installed=None):
    """Internal entrypoint: caller must own installation_lock for this home."""
    source = Path(source or Path(__file__).resolve().parent.parent)
    home = Path(home).expanduser().resolve()
    if target not in ("codex", "claude", "both"):
        raise ValueError("Unsupported installation target")
    if not (source / "SKILL.md").is_file():
        raise ValueError("FunAvatar source SKILL.md is missing")
    folders = {"codex": ".agents", "claude": ".claude"}
    names = list(folders) if target == "both" else [target]
    destinations = [home / folders[name] / "skills" / "funavatar" for name in names]
    expected = {}
    for destination in destinations:
        if any(path.is_symlink() for path in (destination, *destination.parents)) or (destination.exists() and not destination.is_dir()):
            raise ValueError(f"Destination is not a regular skill directory: {destination}")
        if destination.exists():
            if not update:
                raise ValueError(f"Already exists; nothing replaced: {destination}. Use --update for a checked upgrade.")
            expected[destination] = verify_existing(destination, baselines=baselines)
        if expected_installed is not None and expected.get(destination) != expected_installed.get(destination):
            raise InstallationChanged("Installation changed since update preflight; nothing replaced")
    managed = snapshot(source)
    version_file = source / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "unversioned"
    stages, changed = [], []
    try:
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".funavatar-install-", dir=destination.parent))
            stages.append((destination, staging))
            staged_skill = staging / "funavatar"
            shutil.copytree(source, staged_skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", RECEIPT))
            if snapshot(staged_skill) != managed:
                raise ValueError("Source changed while staging the installation; retry")
            (staged_skill / RECEIPT).write_text(json.dumps({
                "schema_version": 1, "version": version, "managed": managed
            }, indent=2) + "\n", encoding="utf-8")
        for destination, staging in stages:
            backup = None
            if destination in expected:
                if verify_existing(destination, baselines=baselines) != expected[destination]:
                    raise ValueError(f"Installation changed during update: {destination}")
                backup_folder = home / ".local" / "share" / "funavatar" / "backups"
                if backup_folder.is_symlink():
                    raise ValueError("Symlinked backup directory; nothing replaced")
                backup_folder.mkdir(parents=True, exist_ok=True)
                backup = backup_folder / (destination.parent.parent.name.lstrip(".") + "-" + uuid.uuid4().hex)
                destination.rename(backup)
            else:
                # Reserve a fresh destination exclusively, protecting existing local files.
                destination.mkdir()
            changed.append((destination, backup))
            if backup is None:
                for child in (staging / "funavatar").iterdir():
                    child.rename(destination / child.name)
            else:
                (staging / "funavatar").rename(destination)
    except BaseException:
        for destination, backup in reversed(changed):
            if destination.exists():
                shutil.rmtree(destination)
            if backup is not None:
                backup.rename(destination)
        raise
    finally:
        for _, staging in stages:
            shutil.rmtree(staging, ignore_errors=True)
    return destinations



def main(argv=None, *, install_function=install):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--update", action="store_true", help="Upgrade only an unchanged recognized installation; retain a backup")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory (also useful for isolated installation tests)")
    args = parser.parse_args(argv)
    try:
        for destination in install_function(args.target, args.home.expanduser().resolve(), update=args.update):
            print(f"{'Updated' if args.update else 'Installed'}: {destination}")
        if args.update:
            print(f"Previous installations retained in: {args.home.expanduser().resolve() / '.local/share/funavatar/backups'}")
    except (OSError, ValueError) as error:
        print(f"FunAvatar: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
