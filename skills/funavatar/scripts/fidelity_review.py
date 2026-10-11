#!/usr/bin/env python3
"""Offline review preflight; validates bindings and completeness, never judges pixels.

Run production through: run REVIEW.json -- EXECUTABLE ARGS...
This wrapper is not a sandbox and does not prevent direct execution elsewhere.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from vrc_acceptance import MAX_JSON_BYTES, read_json, write_new_json

CATEGORIES = ("silhouette", "proportions", "head_and_hair", "outfit", "materials",
              "side_specific_details", "branding")
VIEWS = {"front", "back", "left", "right", "three_quarter", "detail", "multiview_sheet", "mask_states"}
STATUSES = {"pass", "needs_repair", "not_assessed"}
SCOPE = "validates review completeness and evidence binding, does not judge pixels"


def _object(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("Expected fields: " + ", ".join(sorted(required)))


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 8192 or "\0" in value:
        raise ValueError("Expected nonempty bounded text")
    return value


def _version(data):
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")


def _list(value):
    if not isinstance(value, list) or len(value) > 256:
        raise ValueError("Expected an array with at most 256 entries")
    return value


def _status(value):
    if not isinstance(value, str) or value not in STATUSES:
        raise ValueError("Use pass, needs_repair or not_assessed")


def _bound(value, base, label, issues, bindings):
    _object(value, {"path", "sha256"})
    name = _text(value["path"])
    expected = value["sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Expected a lowercase SHA-256 digest")
    path = Path(name).expanduser()
    if not path.is_absolute():
        path = base / path
    if path.is_symlink() or not path.is_file():
        issues.append({"code": "missing_file", "at": label})
        return None
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    signature = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    current = digest.hexdigest()
    bindings.append({"at": label, "path": str(path.absolute()), "expected_sha256": expected, "sha256": current})
    if signature(before) != signature(after) or current != expected:
        issues.append({"code": "stale_evidence", "at": label})
    return path


def check(data, base_dir=None):
    _object(data, {"schema_version", "asset", "reference_set", "comparisons", "categories", "user_rejection"},
            {"intent", "authorised_change"})
    _version(data)
    intent = data.get("intent", "faithful_reconstruction")
    if intent not in ("faithful_reconstruction", "reinterpretation"):
        raise ValueError("Unknown intent")
    base = Path(base_dir or ".")
    issues, bindings = [], []
    _bound(data["asset"], base, "asset", issues, bindings)
    inventory_path = _bound(data["reference_set"], base, "reference_set", issues, bindings)
    references = {}
    if inventory_path:
        inventory = read_json(inventory_path)
        _object(inventory, {"schema_version", "references"})
        _version(inventory)
        for ref in _list(inventory["references"]):
            _object(ref, {"id", "view", "role", "availability", "path", "sha256", "note"})
            identifier = _text(ref["id"])
            if identifier in references:
                raise ValueError("Duplicate reference id")
            if not isinstance(ref["view"], str) or ref["view"] not in VIEWS:
                raise ValueError("Unknown reference view")
            if ref["role"] not in ("primary", "supporting") or ref["availability"] not in ("available", "unavailable"):
                raise ValueError("Unknown reference role or availability")
            _text(ref["note"])
            references[identifier] = ref
            if ref["availability"] == "available":
                _bound({"path": ref["path"], "sha256": ref["sha256"]}, inventory_path.parent,
                       "reference:" + identifier, issues, bindings)
            else:
                if ref["path"] is not None or ref["sha256"] is not None:
                    raise ValueError("Unavailable references require null path/hash and an explanatory note")
                issues.append({"code": "unavailable_reference", "at": identifier})
        # Recheck the inventory after parsing; roles and view inventory stay tied to its hash.
        _bound(data["reference_set"], base, "reference_set_recheck", issues, bindings)
    if not any(ref["role"] == "primary" for ref in references.values()):
        issues.append({"code": "missing_primary_reference", "at": "reference_set"})
    compared = set()
    for item in _list(data["comparisons"]):
        _object(item, {"reference_id", "render", "render_view", "camera_pose_compatible", "status", "note"})
        identifier = _text(item["reference_id"])
        if identifier in compared:
            raise ValueError("Duplicate comparison reference_id")
        compared.add(identifier)
        _status(item["status"])
        _text(item["note"])
        if not isinstance(item["render_view"], str) or item["render_view"] not in VIEWS:
            raise ValueError("Unknown render view")
        if type(item["camera_pose_compatible"]) is not bool:
            raise ValueError("camera_pose_compatible must be a boolean declaration")
        if item["render"] is not None:
            _bound(item["render"], base, "render:" + identifier, issues, bindings)
        else:
            issues.append({"code": "missing_comparison_render", "at": identifier})
        ref = references.get(identifier)
        if ref is None:
            issues.append({"code": "unknown_reference", "at": identifier})
        elif ref["view"] != "multiview_sheet" and item["render_view"] != ref["view"]:
            issues.append({"code": "declared_view_mismatch", "at": identifier})
        if not item["camera_pose_compatible"]:
            issues.append({"code": "camera_pose_not_comparable", "at": identifier})
        if item["status"] != "pass":
            issues.append({"code": item["status"], "at": "comparison:" + identifier})
    for identifier in sorted(references.keys() - compared):
        issues.append({"code": "missing_view_comparison", "at": identifier})
    categories = data["categories"]
    if not isinstance(categories, dict) or categories.keys() - set(CATEGORIES):
        raise ValueError("Unknown fidelity category")
    for name in CATEGORIES:
        item = categories.get(name)
        if item is None:
            issues.append({"code": "unreviewed_category", "at": name})
            continue
        _object(item, {"status", "note", "reference_ids"})
        _status(item["status"])
        _text(item["note"])
        identifiers = [_text(value) for value in _list(item["reference_ids"])]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate category reference_ids")
        if not identifiers or set(identifiers) - references.keys():
            issues.append({"code": "category_evidence_missing", "at": name})
        if item["status"] != "pass":
            issues.append({"code": item["status"], "at": name})
    rejection = data["user_rejection"]
    _object(rejection, {"rejected", "note"})
    if type(rejection["rejected"]) is not bool:
        raise ValueError("user_rejection.rejected must be a boolean")
    _text(rejection["note"])
    if rejection["rejected"]:
        issues.append({"code": "user_rejected", "at": "user_rejection", "note": rejection["note"]})
    change = data.get("authorised_change")
    if change is not None:
        _object(change, {"quote", "evidence"})
        quote = _text(change["quote"])
        path = _bound(change["evidence"], base, "authorised_change", issues, bindings)
        if path:
            if path.stat().st_size > MAX_JSON_BYTES:
                raise ValueError("Authorization evidence exceeds the text limit")
            if quote not in path.read_text(encoding="utf-8"):
                issues.append({"code": "authorization_quote_not_found", "at": "authorised_change"})
    elif intent == "reinterpretation":
        issues.append({"code": "reinterpretation_not_authorised", "at": "intent"})
    ready = not issues
    return {"schema_version": 1, "kind": "funavatar_fidelity_review_preflight", "scope": SCOPE,
            "intent": intent, "review_status": "complete" if ready else "blocked", "issues": issues,
            "can_proceed_to_production_rig": ready,
            "can_claim_fidelity": ready and intent == "faithful_reconstruction",
            "visual_judgment_performed": False, "bindings": bindings,
            "reference_roles": {key: ref["role"] for key, ref in references.items()},
            "limitations": ["Flags reflect supplied review declarations, not machine visual acceptance.",
                            "The initial reference inventory and the speaker/meaning of an authorization quote are not independently verified.",
                            "Hashes do not prove that a render was generated from the declared asset; that association remains a reviewer declaration.",
                            "This workflow gate does not prevent direct Blender/Unity execution or guarantee an exact reconstruction."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "run"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    values = list(sys.argv[1:] if argv is None else argv)
    command = []
    if values[:1] == ["run"]:
        if "--" not in values:
            parser.error("run requires -- EXECUTABLE ARGS...")
        separator = values.index("--")
        command, values = values[separator + 1:], values[:separator]
        if not command:
            parser.error("run requires an executable after --")
    args = parser.parse_args(values)
    if args.command == "run" and args.out is not None:
        parser.error("--out is only supported by check")
    try:
        result = check(read_json(args.input), args.input.absolute().parent)
        if args.out:
            write_new_json(args.out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), flush=True)
        if not result["can_proceed_to_production_rig"]:
            return 1
        if args.command == "run":
            return subprocess.run(command, shell=False, check=False).returncode
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f"fidelity-review: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
