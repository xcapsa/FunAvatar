#!/usr/bin/env python3
"""Install or safely update FunAvatar without changing application settings."""

import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "skills/funavatar/scripts"))
import funavatar_installer as _installer

RECEIPT = _installer.RECEIPT
snapshot = _installer.snapshot


def known_baselines():
    folder = Path(__file__).resolve().parent / "baselines"
    return [json.loads(path.read_text(encoding="utf-8"))["managed"]
            for path in sorted(folder.glob("*.json"))]


def verify_existing(destination):
    return _installer.verify_existing(destination, baselines=known_baselines())


def install(target, home, source=None, *, update=False):
    source = source or Path(__file__).resolve().parent / "skills/funavatar"
    return _installer.install(target, home, source, update=update, baselines=known_baselines())


def main():
    return _installer.main(install_function=install)


if __name__ == "__main__":
    sys.exit(main())
