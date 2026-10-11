#!/usr/bin/env python3
"""Read stored Blender shape-key deltas without changing the scene or saving it."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys


def delta_metrics(coordinates, reference, epsilon=1e-6):
    """Measure corresponding local-space coordinates; absent/invalid data raises."""
    if isinstance(epsilon, bool) or not isinstance(epsilon, (int, float)):
        raise ValueError("epsilon must be a finite nonnegative number")
    if not math.isfinite(epsilon) or epsilon < 0:
        raise ValueError("epsilon must be a finite nonnegative number")
    if not isinstance(coordinates, (list, tuple)) or not isinstance(reference, (list, tuple)):
        raise ValueError("coordinates and reference must be sequences")
    if not coordinates or len(coordinates) != len(reference):
        raise ValueError("coordinate counts are empty or do not match")
    changed = 0
    maximum = 0.0
    for point, base in zip(coordinates, reference):
        for vector in (point, base):
            if not isinstance(vector, (list, tuple)) or len(vector) != 3:
                raise ValueError("each coordinate must have three components")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in vector):
                raise ValueError("coordinates must be finite numbers")
        distance = math.dist(point, base)
        if not math.isfinite(distance):
            raise ValueError("delta is not finite")
        maximum = max(maximum, distance)
        changed += distance > epsilon
    return {"vertex_count": len(coordinates), "changed_vertex_count": changed,
            "max_delta": maximum, "has_delta": changed > 0}


def analyze_shapes(shape_keys, required_names=(), epsilon=1e-6, use_relative=True):
    """Analyze a captured mapping; pass means only required names/nonzero deltas."""
    delta_metrics([(0, 0, 0)], [(0, 0, 0)], epsilon)
    required = list(dict.fromkeys(required_names))
    if any(not isinstance(name, str) or not name.strip() for name in required):
        raise ValueError("required shape names must be nonempty strings")
    result = {"status": "unknown", "required_names": required, "missing": [],
              "zero_delta_required": [], "unobserved_required": [],
              "epsilon": epsilon, "use_relative": use_relative, "shapes": []}
    if shape_keys is None:
        result["unobserved_required"] = required
        result["note"] = "Shape-key observations unavailable"
        return result
    if not isinstance(shape_keys, dict):
        raise ValueError("shape_keys must be a captured mapping or None")
    basis = next(iter(shape_keys), None)
    result["basis_name"] = basis
    result["missing"] = [name for name in required if name not in shape_keys]
    for name, record in shape_keys.items():
        relative = record.get("relative_key") if isinstance(record, dict) else None
        reference_name = relative if use_relative else basis
        item = {"name": name, "is_basis": name == basis, "comparison_key": reference_name,
                "status": "unknown", "vertex_count": None, "changed_vertex_count": None,
                "max_delta": None, "has_delta": None}
        try:
            if not isinstance(record, dict) or reference_name not in shape_keys:
                raise ValueError("Reference shape unavailable")
            reference = shape_keys[reference_name]
            if not isinstance(reference, dict):
                raise ValueError("Reference coordinates unavailable")
            item.update(delta_metrics(record.get("coordinates"), reference.get("coordinates"), epsilon))
            item["status"] = "observed"
        except (TypeError, ValueError, OverflowError) as error:
            item["note"] = str(error)
        result["shapes"].append(item)
        if name in required:
            if item["status"] == "unknown":
                result["unobserved_required"].append(name)
            elif not item["has_delta"]:
                result["zero_delta_required"].append(name)
    if result["missing"] or result["zero_delta_required"]:
        result["status"] = "needs_repair"
    elif any(item["status"] == "unknown" for item in result["shapes"]):
        result["status"] = "unknown"
    else:
        result["status"] = "pass" if required else "observed"
    return result


def source_fingerprint(filepath, dirty):
    source = {"name": Path(filepath).name if filepath else None, "sha256": None,
              "dirty": dirty, "hash_scope": "saved_file_bytes", "state": "unsaved"}
    if filepath:
        try:
            digest = hashlib.sha256()
            with open(filepath, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            source.update(sha256=digest.hexdigest(), state="saved")
        except OSError:
            source["state"] = "unreadable"
    return source


def collect_report(bpy, mesh_name, required_names=(), epsilon=1e-6):
    """Read only: no operators, evaluated transforms, frame changes or saves."""
    report = {"schema": "funavatar.blender-face-probe.v1",
              "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "blender_version": bpy.app.version_string,
              "subject": {"mesh_name": mesh_name},
              "source": source_fingerprint(bpy.data.filepath, bpy.data.is_dirty),
              "scope": "Stored local-space shape coordinates; no aesthetic or runtime assessment"}
    obj = bpy.data.objects.get(mesh_name)
    captured = None
    use_relative = True
    if obj is None or obj.type != "MESH":
        report["observation_error"] = "Explicit mesh object not found"
    elif obj.mode == "EDIT":
        report["observation_error"] = "Edit-mode coordinates may be stale; probe did not change mode"
    else:
        report["subject"]["mesh_data_name"] = obj.data.name
        report["subject"]["vertex_count"] = len(obj.data.vertices)
        keys = obj.data.shape_keys
        captured = {}
        if keys is not None:
            use_relative = bool(keys.use_relative)
            for key in keys.key_blocks:
                captured[key.name] = {
                    "relative_key": key.relative_key.name if key.relative_key is not None else None,
                    "coordinates": [tuple(point.co) for point in key.data],
                }
    report.update(analyze_shapes(captured, required_names, epsilon, use_relative))
    return report


def write_report(report, output):
    """Serialize first; exclusive creation refuses existing paths and symlinks."""
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True, help="Exact mesh object name")
    parser.add_argument("--required", action="append", default=[], help="Shape required to deform; repeatable")
    parser.add_argument("--epsilon", type=float, default=1e-6, help="Nonzero threshold in mesh-local units")
    parser.add_argument("--out", required=True, help="New JSON output path; never overwritten")
    args = parser.parse_args(argv)
    if not args.mesh.strip():
        parser.error("--mesh must name an explicit mesh object")
    try:
        import bpy
    except ImportError:
        parser.error("Run inside Blender; bpy observations are unavailable")
    report = collect_report(bpy, args.mesh, args.required, args.epsilon)
    write_report(report, args.out)
    print(json.dumps({"schema": report["schema"], "status": report["status"],
                      "shape_count": len(report["shapes"]), "output": args.out}))
    return report


if __name__ == "__main__":
    main()
