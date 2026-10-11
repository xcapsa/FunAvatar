#!/usr/bin/env python3
"""Install or safely update FunAvatar without changing application settings."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid


RECEIPT = ".funavatar-install.json"


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


def known_baselines():
    folder = Path(__file__).resolve().parent / "baselines"
    return [json.loads(path.read_text(encoding="utf-8"))["managed"]
            for path in sorted(folder.glob("*.json"))]


def verify_existing(destination):
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
    elif current in known_baselines():
        return current
    raise ValueError(f"Local changes or unrecognized installation; nothing replaced: {destination}")


def install(target, home, source=None, *, update=False):
    source = Path(source or Path(__file__).resolve().parent / "skills" / "funavatar")
    if not (source / "SKILL.md").is_file():
        raise ValueError("FunAvatar source SKILL.md is missing")
    folders = {"codex": ".agents", "claude": ".claude"}
    names = list(folders) if target == "both" else [target]
    destinations = [home / folders[name] / "skills" / "funavatar" for name in names]
    expected = {}
    for destination in destinations:
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            raise ValueError(f"Destination is not a regular skill directory: {destination}")
        if destination.exists():
            if not update:
                raise ValueError(f"Already exists; nothing replaced: {destination}. Use --update for a checked upgrade.")
            expected[destination] = verify_existing(destination)
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
                if snapshot(destination) != expected[destination]:
                    raise ValueError(f"Installation changed during update: {destination}")
                backup_folder = home / ".local" / "share" / "funavatar" / "backups"
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--update", action="store_true", help="Upgrade only an unchanged recognized installation; retain a backup")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory (also useful for isolated installation tests)")
    args = parser.parse_args()
    try:
        for destination in install(args.target, args.home.expanduser().resolve(), update=args.update):
            print(f"{'Updated' if args.update else 'Installed'}: {destination}")
        if args.update:
            print(f"Previous installations retained in: {args.home.expanduser().resolve() / '.local/share/funavatar/backups'}")
    except (OSError, ValueError) as error:
        print(f"FunAvatar: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
