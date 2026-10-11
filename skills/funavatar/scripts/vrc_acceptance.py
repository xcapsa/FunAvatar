#!/usr/bin/env python3
"""Check declared static VRChat measurements offline. Python 3.10+, stdlib only.

Input: schema_version=1, kind=funavatar_vrc_measurements, asset_sha256 (lowercase
SHA-256), target=pc|android|ios, evidence_scope=static_measured; optional metrics,
expression_parameters [{name, type: bool|int|float, synced: boolean}], asset_path.
Missing observations are unknown. A supplied asset_path is relative to the input
JSON and must still match its hash. This helper neither collects measurements nor
calculates an official SDK rank, validates an upload or verifies runtime behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

MAX_JSON_BYTES = 2 * 1024 * 1024
PROFILE_PATH = Path(__file__).resolve().parent.parent / "assets/vrchat-performance-profile.json"


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError("Nonfinite JSON number")


def _finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("Nonfinite JSON number")
    return value


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Expected a bounded regular JSON file without a symlink")
    with path.open("rb") as source:
        raw = source.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON file exceeds the size limit")
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_nonfinite, parse_float=_finite_float)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Invalid UTF-8 JSON or excessive nesting") from error


def _asset_integrity(data, base_dir):
    if "asset_path" not in data:
        return {"status": "hash_declared_only"}
    value = data["asset_path"]
    if not isinstance(value, str) or not value.strip() or "\0" in value or len(value) > 4096:
        raise ValueError("asset_path must be a nonempty local file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    if path.is_symlink() or not path.is_file():
        raise ValueError("asset_path must name a regular file without a symlink")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Asset changed while checking its hash; remeasure it")
    if digest.hexdigest() != data["asset_sha256"]:
        raise ValueError("Stale measurements: asset SHA-256 no longer matches; remeasure it")
    return {"status": "hash_matches_file", "path": str(path.resolve())}


def _thresholds(metrics, thresholds):
    rows = {}
    for name, maximum in thresholds.items():
        observed = metrics.get(name)
        status = "unknown" if observed is None else "within" if observed <= maximum else "exceeded"
        rows[name] = {"observed": observed, "maximum": maximum, "status": status}
    statuses = {row["status"] for row in rows.values()}
    status = "exceeded" if "exceeded" in statuses else "unknown" if "unknown" in statuses else "within"
    return {"status": status, "complete_for_supported_metrics": "unknown" not in statuses, "metrics": rows}


def _parameters(parameters, rules):
    if parameters is None:
        return {"status": "unknown", "synced_bits": None, "custom_parameter_count": None,
                "max_synced_bits": rules["max_synced_bits"], "max_custom_parameters": rules["max_custom_parameters"]}
    if not isinstance(parameters, list):
        raise ValueError("expression_parameters must be an array of custom parameters")
    names, bits = set(), 0
    for parameter in parameters:
        if not isinstance(parameter, dict) or set(parameter) != {"name", "type", "synced"}:
            raise ValueError("Each custom parameter must contain name, type and synced only")
        name = parameter["name"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 128 or name != name.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in name)):
            raise ValueError("Custom parameter names must be nonempty without surrounding whitespace or controls")
        if name in names:
            raise ValueError("Duplicate custom parameter name")
        if name in rules["built_in_read_only"]:
            raise ValueError("Built-in read-only parameters do not belong in the custom parameter list")
        names.add(name)
        kind = parameter["type"]
        if not isinstance(kind, str) or kind not in rules["synced_bits_per_type"] or type(parameter["synced"]) is not bool:
            raise ValueError("Use bool/int/float parameter types and a boolean synced flag")
        if parameter["synced"]:
            bits += rules["synced_bits_per_type"][kind]
    exceeded = []
    if bits > rules["max_synced_bits"]:
        exceeded.append("synced_bits")
    if len(parameters) > rules["max_custom_parameters"]:
        exceeded.append("custom_parameter_count")
    return {"status": "exceeded" if exceeded else "within", "synced_bits": bits,
            "custom_parameter_count": len(parameters), "max_synced_bits": rules["max_synced_bits"],
            "max_custom_parameters": rules["max_custom_parameters"], "exceeded_limits": exceeded}


def check(data, base_dir=None):
    profile = read_json(PROFILE_PATH)
    required = {"schema_version", "kind", "asset_sha256", "target", "evidence_scope"}
    allowed = required | {"asset_path", "metrics", "expression_parameters"}
    if not isinstance(data, dict) or not required.issubset(data) or set(data) - allowed:
        raise ValueError("Expected the declared funavatar_vrc_measurements input schema")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["kind"] != "funavatar_vrc_measurements":
        raise ValueError("Unsupported measurement schema or kind")
    if not isinstance(data["asset_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", data["asset_sha256"]):
        raise ValueError("asset_sha256 must be a lowercase SHA-256 digest")
    if data["target"] not in ("pc", "android", "ios") or data["evidence_scope"] != "static_measured":
        raise ValueError("Use a pc/android/ios target and evidence_scope static_measured")
    selected = "pc" if data["target"] == "pc" else "mobile"
    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict) or set(metrics) - set(profile["good"][selected]):
        raise ValueError("metrics must contain only the supported measured metric names")
    for name, value in metrics.items():
        if value is None:
            continue
        valid = type(value) is int or (name == "texture_memory_mb" and type(value) is float and math.isfinite(value))
        if not valid or value < 0:
            raise ValueError("Metrics must be nonnegative integers; texture_memory_mb may also be a finite number")
    integrity = _asset_integrity(data, Path(base_dir or "."))
    good = _thresholds(metrics, profile["good"][selected])
    hard = (_thresholds(metrics, profile["hard_limits"]["mobile"]) if selected == "mobile"
            else {"status": "not_assessed", "reason": "No PC hard-limit profile is supplied"})
    visibility = {"status": "not_assessed"}
    if selected == "mobile":
        rule = profile["mobile_triangles"]
        triangles = metrics.get("triangles")
        visibility = {**rule, "observed": triangles,
                      "status": "unknown" if triangles is None else "above_very_poor_threshold" if triangles > rule["very_poor_above"] else "within_threshold"}
    return {"schema_version": 1, "kind": "funavatar_vrc_acceptance", "profile_id": profile["profile_id"],
            "asset_sha256": data["asset_sha256"], "target": data["target"], "evidence_scope": data["evidence_scope"],
            "asset_integrity": integrity, "good_partial_profile": good, "hard_limits": hard,
            "triangle_visibility": visibility,
            "expression_parameters": _parameters(data.get("expression_parameters"), profile["expression_parameters"]),
            "sdk_rank": "not_assessed", "upload_eligibility": "not_assessed", "runtime_verified": False,
            "profile_scope": profile["scope"], "sources": profile["sources"],
            "target_note": "Shared mobile numeric profile; native iOS behavior and ledger support are not assessed" if data["target"] == "ios" else "Static measurements only; native target behavior is not assessed"}


def write_new_json(path, result):
    path = Path(path).expanduser().absolute()
    raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Output exceeds the JSON size limit")
    fd, temporary = tempfile.mkstemp(prefix=".vrc-acceptance-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)  # Exclusive publication preserves any existing output, including symlinks.
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        result = check(read_json(args.input), args.input.absolute().parent)
        if args.out:
            write_new_json(args.out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        statuses = {result[section]["status"] for section in (
            "good_partial_profile", "hard_limits", "expression_parameters")}
        return 1 if "exceeded" in statuses else 3 if "unknown" in statuses else 0
    except (OSError, ValueError) as error:
        print(f"vrc-acceptance: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
