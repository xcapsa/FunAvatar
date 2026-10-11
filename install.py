#!/usr/bin/env python3
"""Install FunAvatar locally without changing settings or replacing skills."""

import argparse
from pathlib import Path
import shutil
import sys
import tempfile


def install(target, home, source=None):
    source = source or Path(__file__).resolve().parent / "skills" / "funavatar"
    if not (source / "SKILL.md").is_file():
        raise ValueError("FunAvatar source SKILL.md is missing")
    folders = {"codex": ".agents", "claude": ".claude"}
    names = list(folders) if target == "both" else [target]
    destinations = [home / folders[name] / "skills" / "funavatar" for name in names]
    for destination in destinations:
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Already exists; nothing replaced: {destination}")
    installed = []
    try:
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".funavatar-install-", dir=destination.parent))
            try:
                shutil.copytree(source, staging / "funavatar", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                # An exclusive mkdir also protects against an installation racing this one.
                destination.mkdir()
                installed.append(destination)
                for child in (staging / "funavatar").iterdir():
                    child.rename(destination / child.name)
            finally:
                shutil.rmtree(staging)
    except (OSError, ValueError):
        for destination in reversed(installed):
            shutil.rmtree(destination)
        raise
    return destinations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory (also useful for isolated installation tests)")
    args = parser.parse_args()
    try:
        for destination in install(args.target, args.home.expanduser().resolve()):
            print(f"Installed: {destination}")
    except (OSError, ValueError) as error:
        print(f"FunAvatar: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
