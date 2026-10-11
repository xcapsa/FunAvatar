#!/usr/bin/env python3
"""Opt-in, invocation-time stable updates for local FunAvatar installations.

Only the already installed installer runs. Downloaded Python is copied as data,
never imported or executed. No background process, Git, token or telemetry.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile
import zlib

import funavatar_installer as installer

LATEST_URL = "https://api.github.com/repos/xcapsa/FunAvatar/releases/latest"
RELEASE_BASE = "https://github.com/xcapsa/FunAvatar/releases/"
PACKAGE = "funavatar-skill.zip"
CHECKSUMS = "SHA256SUMS"
TARGETS = {"codex": ".agents", "claude": ".claude"}
MAX_METADATA = 1024 * 1024
MAX_PACKAGE = 10 * 1024 * 1024
MAX_CHECKSUMS = 16 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_ENTRIES = 512
VERSION = re.compile(r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\Z")


class UpdateError(ValueError):
    """Fixed local reason code, never a raw HTTP body or redirect URL."""


def version_tuple(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise UpdateError("invalid_stable_version")
    return tuple(int(part) for part in value.split("."))


def _regular_path(path):
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise UpdateError("symlinked_path")


def _state_path(home):
    path = home / ".local/share/funavatar/auto-update.json"
    _regular_path(path)
    return path


def _read_config(home):
    path = _state_path(home)
    if not path.exists():
        return {"schema_version": 1, "enabled": False, "target": None}
    if not path.is_file() or path.stat().st_size > 4096:
        raise UpdateError("invalid_configuration")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(config, dict) or set(config) != {"schema_version", "enabled", "target"}
                or type(config["schema_version"]) is not int or config["schema_version"] != 1
                or type(config["enabled"]) is not bool
                or config["target"] not in (*TARGETS, "both", None)
                or (config["enabled"] and config["target"] is None)):
            raise ValueError
    except (ValueError, UnicodeError, RecursionError):
        raise UpdateError("invalid_configuration") from None
    return config


def _write_config(home, *, enabled, target):
    path = _state_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".auto-update-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"schema_version": 1, "enabled": enabled, "target": target}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def _update_lock(home):
    _state_path(home)
    try:
        with installer.installation_lock(home):
            yield
    except installer.InstallationBusy:
        raise UpdateError("update_busy") from None


def _names(target):
    if target not in (*TARGETS, "both"):
        raise UpdateError("invalid_target")
    return list(TARGETS) if target == "both" else [target]


def _installed(home, target):
    versions, paths, managed = {}, [], {}
    for name in _names(target):
        folder = home / TARGETS[name] / "skills/funavatar"
        _regular_path(folder)
        if not folder.is_dir() or not (folder / "SKILL.md").is_file():
            raise UpdateError("target_not_installed")
        # No legacy guess or receipt synthesized from an unverified local copy.
        try:
            managed[folder] = installer.verify_existing(folder)
            version = (folder / "VERSION").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            raise UpdateError("installation_changed_or_unmanaged") from None
        version_tuple(version)
        versions[name] = version
        paths.append(str(folder / "SKILL.md"))
    return versions, paths, managed


def _infer_target(home, config):
    if config["target"]:
        return config["target"]
    existing = [name for name, folder in TARGETS.items() if (home / folder / "skills/funavatar").exists()]
    if not existing:
        raise UpdateError("target_not_installed")
    return "both" if len(existing) == 2 else existing[0]


def _allow_url(url):
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443) or parts.fragment or len(url) > 16384
                or any(ord(char) < 33 for char in url)):
            raise ValueError
        if url == LATEST_URL:
            return
        if parts.hostname == "github.com" and parts.path.startswith("/xcapsa/FunAvatar/releases/download/"):
            return
        if parts.hostname in ("release-assets.githubusercontent.com", "objects.githubusercontent.com"):
            return
    except (TypeError, ValueError):
        pass
    raise UpdateError("untrusted_release_url")


class _ReleaseRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _allow_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url, limit):
    _allow_url(url)
    request = Request(url, headers={"User-Agent": "FunAvatar-Updater", "Accept": "application/vnd.github+json"})
    opener = build_opener(ProxyHandler({}), _ReleaseRedirect())
    deadline = time.monotonic() + 15
    try:
        with opener.open(request, timeout=5) as response:
            if response.status != 200:
                raise UpdateError("release_http_error")
            chunks, size = [], 0
            while True:
                if time.monotonic() > deadline:
                    raise UpdateError("network_timeout")
                chunk = response.read(min(65536, limit - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise UpdateError("release_size_limit")
                chunks.append(chunk)
            return b"".join(chunks)
    except (OSError, URLError, http.client.HTTPException):
        raise UpdateError("network_unavailable") from None


def _release(fetch):
    raw = fetch(LATEST_URL, MAX_METADATA)
    try:
        data = json.loads(raw)
        if (not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False
                or not isinstance(data.get("tag_name"), str) or not data["tag_name"].startswith("v")):
            raise ValueError
        version = data["tag_name"][1:]
        version_tuple(version)
        if data.get("html_url") != RELEASE_BASE + "tag/v" + version:
            raise ValueError
        assets = {}
        for name, limit in ((PACKAGE, MAX_PACKAGE), (CHECKSUMS, MAX_CHECKSUMS)):
            matches = [asset for asset in data["assets"] if isinstance(asset, dict) and asset.get("name") == name]
            if len(matches) != 1:
                raise ValueError
            asset = matches[0]
            if (asset.get("browser_download_url") != RELEASE_BASE + f"download/v{version}/{name}"
                    or type(asset.get("size")) is not int or not 0 < asset["size"] <= limit):
                raise ValueError
            digest = asset.get("digest")
            if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
                raise ValueError
            assets[name] = asset
        return version, assets
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        raise UpdateError("invalid_stable_release") from None


def _asset_bytes(asset, fetch, limit):
    content = fetch(asset["browser_download_url"], limit)
    if len(content) != asset["size"] or len(content) > limit:
        raise UpdateError("release_size_mismatch")
    digest = asset.get("digest")
    if digest and digest != "sha256:" + hashlib.sha256(content).hexdigest():
        raise UpdateError("release_digest_mismatch")
    return content


def _verified_package(assets, fetch):
    sums = _asset_bytes(assets[CHECKSUMS], fetch, MAX_CHECKSUMS)
    try:
        records = {}
        for line in sums.decode("ascii").splitlines():
            match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *]([^\r\n]+)", line)
            if not match or match[2] in records:
                raise ValueError
            records[match[2]] = match[1].lower()
        expected = records[PACKAGE]
    except (ValueError, KeyError, UnicodeError):
        raise UpdateError("invalid_checksum_manifest") from None
    package = _asset_bytes(assets[PACKAGE], fetch, MAX_PACKAGE)
    if hashlib.sha256(package).hexdigest() != expected:
        raise UpdateError("package_checksum_mismatch")
    return package


def _extract(package, folder, version):
    required = {"funavatar/SKILL.md", "funavatar/VERSION", "funavatar/scripts/funavatar.py",
                "funavatar/scripts/funavatar_update.py", "funavatar/scripts/funavatar_installer.py"}
    top_level = {"SKILL.md", "VERSION", "THIRD_PARTY_NOTICES.md", "scripts", "references", "assets", "agents"}
    try:
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ENTRIES:
                raise UpdateError("unsafe_package_structure")
            seen, files, total = set(), set(), 0
            for entry in entries:
                # ZipInfo normalizes Windows separators and truncates NULs.
                # Validate the actual stored name before trusting that view.
                name = entry.orig_filename
                path = PurePosixPath(name)
                parts = name.rstrip("/").split("/")
                mode = entry.external_attr >> 16
                if (name != entry.filename or not re.fullmatch(r"[A-Za-z0-9_./-]+", name) or path.is_absolute()
                        or any(part in ("", ".", "..") or part.endswith(".") for part in parts)
                        or any(re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", part) for part in parts)
                        or parts[0] != "funavatar" or (len(parts) > 1 and parts[1] not in top_level)
                        or name.casefold().rstrip("/") in seen
                        or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or (stat.S_IFMT(mode) == stat.S_IFDIR and not entry.is_dir())
                        or entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or entry.file_size > MAX_FILE or entry.file_size > max(1, entry.compress_size) * 200
                        or installer.RECEIPT in parts or "__pycache__" in parts or name.endswith(".pyc")):
                    raise UpdateError("unsafe_package_structure")
                seen.add(name.casefold().rstrip("/"))
                total += entry.file_size
                if total > MAX_EXPANDED:
                    raise UpdateError("package_expansion_limit")
                if not entry.is_dir():
                    files.add(name)
            if not required.issubset(files):
                raise UpdateError("incomplete_skill_package")
            for entry in entries:
                destination = folder.joinpath(*PurePosixPath(entry.filename).parts)
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, destination.open("xb") as output:
                    written = 0
                    while True:
                        chunk = source.read(min(65536, MAX_FILE - written + 1))
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > MAX_FILE or written > entry.file_size:
                            raise UpdateError("package_expansion_limit")
                        output.write(chunk)
            skill = folder / "funavatar"
            if (skill / "VERSION").read_text(encoding="ascii").strip() != version:
                raise UpdateError("package_version_mismatch")
            return skill
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, EOFError, zlib.error):
        raise UpdateError("invalid_skill_archive") from None


def _result(status, target=None, versions=None, paths=None, **extra):
    return {"status": status, "updated": status == "updated", "continue_current": True,
            "target": target, "installed_versions": versions or {}, "skill_paths": paths or [],
            "reread_skill_paths": paths or [] if status == "updated" else [], **extra}


def _run(command, home, target, fetch):
    if command == "disable":
        _write_config(home, enabled=False, target=None)
        return _result("disabled")
    config = _read_config(home)
    if command == "auto" and not config["enabled"]:
        return _result("disabled")
    if command == "auto":
        target = config["target"]
    elif command in ("enable", "update") and target is None:
        raise UpdateError("explicit_target_required")
    else:
        target = target or _infer_target(home, config)
    versions, paths, expected_installed = _installed(home, target)
    if command == "enable":
        _write_config(home, enabled=True, target=target)
        return _result("enabled", target, versions, paths)
    latest, assets = _release(fetch)
    comparison = [version_tuple(value) for value in versions.values()]
    if any(value > version_tuple(latest) for value in comparison):
        return _result("newer_installed", target, versions, paths, latest_version=latest)
    if all(value == version_tuple(latest) for value in comparison):
        return _result("up_to_date", target, versions, paths, latest_version=latest)
    if command == "check":
        return _result("update_available", target, versions, paths, latest_version=latest)
    package = _verified_package(assets, fetch)
    with tempfile.TemporaryDirectory(prefix="funavatar-update-") as temporary:
        source = _extract(package, Path(temporary), latest)
        try:
            installer._install_under_lock(target, home, source, update=True, expected_installed=expected_installed)
        except installer.InstallationChanged:
            raise UpdateError("installation_changed_during_update") from None
        except (OSError, ValueError):
            raise UpdateError("installation_refused_or_rolled_back") from None
    versions = {name: latest for name in versions}
    return _result("updated", target, versions, paths, latest_version=latest, integrity_verified=True)


def run(command, home=None, target=None, *, fetch=None):
    home = Path(home or Path.home()).expanduser().resolve()
    if command not in ("check", "enable", "disable", "auto", "update"):
        raise UpdateError("invalid_command")
    try:
        # Disabled automatic invocations must not create state or make requests.
        if command == "auto" and not _read_config(home)["enabled"]:
            return _result("disabled")
        if command == "check":
            return _run(command, home, target, fetch or _fetch)
        with _update_lock(home):
            return _run(command, home, target, fetch or _fetch)
    except (OSError, ValueError) as error:
        reason = str(error) if isinstance(error, UpdateError) else "local_update_error"
        try:
            config = _read_config(home)
            chosen = config["target"] if command == "auto" else target or _infer_target(home, config)
            versions, paths, _ = _installed(home, chosen)
        except (OSError, ValueError):
            chosen, versions, paths = target, {}, []
        return _result("deferred" if command == "auto" else "blocked", chosen, versions, paths, reason=reason)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "enable", "disable", "auto", "update"))
    parser.add_argument("--target", choices=(*TARGETS, "both"))
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args(argv)
    if args.command in ("auto", "disable") and args.target is not None:
        parser.error("auto uses the opted-in target; disable turns off the saved opt-in")
    result = run(args.command, args.home, args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
