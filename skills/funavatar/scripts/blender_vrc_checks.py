#!/usr/bin/env python3
"""Read-only Blender checks for failures that commonly break scripted VRChat avatars.

Run inside Blender in background mode; it never changes, saves or exports the file:

    blender --background avatar.blend --python scripts/blender_vrc_checks.py -- --out report.json

Checks: applied object transforms, FBX leaf bones, Unity Humanoid bone coverage,
rest-pose arm orientation, modifiers that would be lost beside shape keys,
unweighted vertices and first-person Head isolation.  The report is a static
observation of the saved source; it is not an SDK build or in-client test.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = "funavatar.blender-vrc-checks.v1"

REQUIRED_HUMANOID = (
    "Hips", "Spine", "Head",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
    "RightUpperLeg", "RightLowerLeg", "RightFoot",
    "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightUpperArm", "RightLowerArm", "RightHand",
)
OPTIONAL_HUMANOID = ("Chest", "Neck", "LeftShoulder", "RightShoulder")

# Normalized base name -> humanoid role (side added separately).
_BASE_ALIASES = {
    "hips": "Hips", "hip": "Hips", "pelvis": "Hips", "root.hips": "Hips",
    "spine": "Spine", "chest": "Chest", "upperchest": "Chest",
    "neck": "Neck", "head": "Head",
    "upperleg": "UpperLeg", "upleg": "UpperLeg", "thigh": "UpperLeg",
    "lowerleg": "LowerLeg", "calf": "LowerLeg", "shin": "LowerLeg", "knee": "LowerLeg",
    "leg": "LowerLeg",
    "foot": "Foot", "ankle": "Foot",
    "shoulder": "Shoulder", "clavicle": "Shoulder",
    "upperarm": "UpperArm", "arm": "UpperArm",
    "lowerarm": "LowerArm", "forearm": "LowerArm", "elbow": "LowerArm",
    "hand": "Hand", "wrist": "Hand",
}
_SIDED = {"UpperLeg", "LowerLeg", "Foot", "Shoulder", "UpperArm", "LowerArm", "Hand"}
_LEAF_RE = re.compile(r"(_end|\.end|_leaf|\.leaf|_nub)$", re.IGNORECASE)
_WEIGHT_EPS = 1e-4


# --------------------------------------------------------------------------- helpers

def _finite_vector(value, size=3):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError("vector has the wrong size")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("vector components must be finite numbers")
    return tuple(float(v) for v in value)


def _check(name, status, severity, summary, **details):
    return {"name": name, "status": status, "severity": severity, "summary": summary, **details}


def normalize_bone_name(name):
    """Return (side, base) using common Unity, Mixamo, Rigify, MPFB and Unreal spellings."""
    raw = name.strip()
    lowered = raw.lower()
    for prefix in ("def-", "def_", "mixamorig:", "mixamorig_", "bip01 ", "bip01_", "armature|"):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):]
    side = None
    patterns = (
        (r"^(left|l)[ _.\-]+(.+)$", 1, 2), (r"^(.+?)[ _.\-]+(left|l)$", 2, 1),
        (r"^(right|r)[ _.\-]+(.+)$", 1, 2), (r"^(.+?)[ _.\-]+(right|r)$", 2, 1),
        (r"^(left)(.+)$", 1, 2), (r"^(right)(.+)$", 1, 2),
    )
    for pattern, side_group, base_group in patterns:
        match = re.match(pattern, lowered)
        if match:
            token = match.group(side_group)
            side = "Left" if token.startswith("l") else "Right"
            lowered = match.group(base_group)
            break
    base = re.sub(r"[ _.\-]+", "", lowered)
    number = re.search(r"(\d+)$", base)
    index = int(number.group(1)) if number else None
    base = re.sub(r"\d+$", "", base)
    return side, base, index


def guess_humanoid_map(bones):
    """Map humanoid roles to bone names; ambiguous roles are returned separately."""
    candidates = {}
    for name in bones:
        side, base, index = normalize_bone_name(name)
        role = _BASE_ALIASES.get(base)
        if role is None:
            continue
        if role in _SIDED:
            if side is None:
                continue
            role = side + role
        elif side is not None:
            continue
        candidates.setdefault(role, []).append((index, name))
    mapping, ambiguous = {}, {}
    spine_like = sorted(candidates.pop("Spine", []), key=lambda item: (item[0] is not None, item[0] or 0))
    if spine_like:
        mapping["Spine"] = spine_like[0][1]
        if len(spine_like) > 1 and "Chest" not in candidates:
            candidates["Chest"] = [spine_like[1]]
    for role, found in candidates.items():
        names = sorted({name for _, name in found})
        if len(names) == 1:
            mapping[role] = names[0]
        else:
            ambiguous[role] = names
    return mapping, ambiguous


def descendants(bones, root):
    children = {}
    for name, bone in bones.items():
        children.setdefault(bone.get("parent"), []).append(name)
    found, stack = set(), [root]
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(children.get(current, []))
    return found


def islands(vertex_count, edges):
    parent = list(range(vertex_count))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    groups = {}
    for i in range(vertex_count):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


# --------------------------------------------------------------------------- checks

def check_transforms(objects, tolerance=1e-4):
    bad = []
    for item in objects:
        scale = _finite_vector(item["scale"])
        rotation = _finite_vector(item["rotation_euler"])
        if any(abs(s - 1.0) > tolerance for s in scale) or any(abs(r) > tolerance for r in rotation):
            bad.append({"object": item["name"], "scale": scale, "rotation_euler": rotation})
    if bad:
        return _check("transforms_applied", "needs_repair", "blocking",
                      "Apply rotation and scale (scale exactly 1.0) on armature and meshes before FBX export",
                      objects=bad)
    return _check("transforms_applied", "pass", "blocking", "Armature and meshes have unit scale and zero rotation")


def check_leaf_bones(bones, weighted_bones=frozenset()):
    """FBX-generated tips: end-style name, no children, and no deforming role (no weights)."""
    leaf, kept = [], []
    for name, bone in bones.items():
        if not _LEAF_RE.search(name) or any(b.get("parent") == name for b in bones.values()):
            continue
        if bone.get("use_deform", True) and name in weighted_bones:
            kept.append(name)  # an intentional deforming tip such as hair_end
        else:
            leaf.append(name)
    if leaf:
        return _check("leaf_bones", "needs_repair", "blocking",
                      "Remove unweighted leaf/end tip bones; export FBX with add_leaf_bones=False",
                      bones=sorted(leaf), weighted_tips_kept=sorted(kept))
    return _check("leaf_bones", "pass", "blocking", "No unweighted leaf/end tip bones found",
                  weighted_tips_kept=sorted(kept))


def check_humanoid(mapping, ambiguous):
    missing = [role for role in REQUIRED_HUMANOID if role not in mapping]
    if missing and any(role in ambiguous for role in missing):
        return _check("humanoid_bones", "unknown", "blocking",
                      "Some required roles match several bones; pass --bone-map to resolve",
                      mapping=mapping, ambiguous=ambiguous, missing=missing)
    if missing:
        return _check("humanoid_bones", "needs_repair", "blocking",
                      "Required Unity Humanoid bones are missing or unrecognized",
                      mapping=mapping, ambiguous=ambiguous, missing=missing)
    optional_missing = [role for role in OPTIONAL_HUMANOID if role not in mapping]
    return _check("humanoid_bones", "pass", "blocking",
                  "All 15 required Humanoid roles map to one bone each (Unity import still needs checking)",
                  mapping=mapping, ambiguous=ambiguous, optional_missing=optional_missing)


def check_rest_pose(bones, mapping, max_tilt_degrees=10.0):
    """T-pose: upper/lower arms horizontal and pointing outward along X."""
    results, unknown = [], []
    for role, outward in (("LeftUpperArm", 1), ("LeftLowerArm", 1), ("RightUpperArm", -1), ("RightLowerArm", -1)):
        name = mapping.get(role)
        if name is None:
            unknown.append(role)
            continue
        head = _finite_vector(bones[name]["head"])
        tail = _finite_vector(bones[name]["tail"])
        dx, dy, dz = (tail[i] - head[i] for i in range(3))
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length <= 0:
            unknown.append(role)
            continue
        tilt = math.degrees(math.asin(max(-1.0, min(1.0, dz / length))))
        results.append({"role": role, "bone": name, "tilt_degrees": round(tilt, 2),
                        "points_outward": dx * outward > 0})
    if unknown and not results:
        return _check("rest_pose", "unknown", "advisory", "Arm roles not mapped; rest pose not assessed",
                      unmapped=unknown)
    off = [r for r in results if abs(r["tilt_degrees"]) > max_tilt_degrees or not r["points_outward"]]
    if off:
        return _check("rest_pose", "needs_repair", "advisory",
                      "Rest pose is not a T-pose; rotate arms horizontal and apply as rest pose before export "
                      "(A-pose can work, but T-pose is the FunAvatar default for reliable Humanoid mapping)",
                      max_tilt_degrees=max_tilt_degrees, arms=results, unmapped=unknown)
    return _check("rest_pose", "pass" if not unknown else "unknown", "advisory",
                  "Mapped arm bones are horizontal and point outward", max_tilt_degrees=max_tilt_degrees,
                  arms=results, unmapped=unknown)


def check_modifiers(meshes):
    lost, pending = [], []
    for mesh in meshes:
        others = [m for m in mesh["modifiers"] if m != "ARMATURE"]
        if not others:
            continue
        record = {"mesh": mesh["name"], "modifiers": others, "shape_key_count": mesh["shape_key_count"]}
        (lost if mesh["shape_key_count"] else pending).append(record)
    if lost:
        return _check("modifiers_vs_shape_keys", "needs_repair", "blocking",
                      "Meshes with shape keys still carry non-Armature modifiers: Blender cannot apply them "
                      "and FBX export with use_mesh_modifiers=False drops their effect. Apply modifiers "
                      "(including DataTransfer weights) before creating visemes.",
                      lost=lost, pending=pending)
    if pending:
        return _check("modifiers_vs_shape_keys", "needs_repair", "advisory",
                      "Apply these modifiers before adding shape keys/visemes", pending=pending)
    return _check("modifiers_vs_shape_keys", "pass", "blocking", "Only Armature modifiers remain")


def _normalized_bone_weights(groups, deform_bones):
    weights = {}
    for name, value in groups:
        if name in deform_bones and value > 0:
            weights[name] = weights.get(name, 0.0) + float(value)
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {name: value / total for name, value in weights.items()}


def check_weights(meshes, bones, mapping, head_blend_margin=0.25, sample_limit=20):
    """Unweighted vertices plus first-person Head isolation."""
    deform = {name for name, bone in bones.items() if bone.get("use_deform", True)}
    head_name, neck_name = mapping.get("Head"), mapping.get("Neck")
    unweighted, checks = [], []
    if not meshes:
        note = "No skinned meshes in scope; pass --mesh or add an Armature modifier targeting the armature"
        return [_check("unweighted_vertices", "unknown", "blocking", note),
                _check("first_person_head", "unknown", "blocking", note)]
    head_known = head_name is not None and head_name in bones
    if head_known:
        head_set = descendants(bones, head_name)
        head_base = _finite_vector(bones[head_name]["head"])
        head_tail = _finite_vector(bones[head_name]["tail"])
        head_len = math.dist(head_base, head_tail)
        threshold_z = head_base[2] + head_blend_margin * head_len
        neck_set = descendants(bones, neck_name) - head_set if neck_name in bones else set()
    region, island_bad, neck_gap = [], [], []
    for mesh in meshes:
        vertices = mesh["vertices"]
        normalized = []
        for index, vertex in enumerate(vertices):
            weights = _normalized_bone_weights(vertex["groups"], deform)
            normalized.append(weights)
            if not weights:
                unweighted.append((mesh["name"], index))
        if not head_known:
            continue
        z_values = [_finite_vector(v["co"])[2] for v in vertices]
        head_w = [sum(w for b, w in weights.items() if b in head_set) for weights in normalized]
        for island in islands(len(vertices), mesh.get("edges", [])):
            weighted = [i for i in island if normalized[i]]
            if not weighted:
                continue
            for i in weighted:
                outside = 1.0 - head_w[i]
                if z_values[i] >= threshold_z and outside > _WEIGHT_EPS:
                    region.append((mesh["name"], i, round(outside, 4)))
            # Loose part sitting on the head (eyes, teeth, hair caps): all of it must follow Head.
            mostly_head = sum(head_w[i] for i in weighted) / len(weighted) > 0.5
            if mostly_head and all(z_values[i] >= head_base[2] for i in island):
                offenders = [i for i in weighted if 1.0 - head_w[i] > _WEIGHT_EPS]
                if offenders:
                    island_bad.append({"mesh": mesh["name"], "island_vertex_count": len(island),
                                       "offending_vertex_count": len(offenders),
                                       "sample_vertices": offenders[:sample_limit]})
            # Skin connected to the neck must blend; long hair hanging below the head is exempt.
            if neck_set and any(any(b in neck_set for b in normalized[i]) for i in weighted):
                for i in weighted:
                    if z_values[i] < head_base[2] and head_w[i] > 0.5 and \
                            not any(b in neck_set for b in normalized[i]):
                        neck_gap.append((mesh["name"], i, round(head_w[i], 4)))

    if unweighted:
        checks.append(_check("unweighted_vertices", "needs_repair", "blocking",
                             "Vertices without deform-bone weight stay behind when the avatar moves",
                             count=len(unweighted),
                             samples=[{"mesh": m, "vertex": i} for m, i in unweighted[:sample_limit]]))
    else:
        checks.append(_check("unweighted_vertices", "pass", "blocking", "Every vertex has deform-bone weight"))

    if not head_known:
        checks.append(_check("first_person_head", "unknown", "blocking",
                             "Head bone not mapped; first-person isolation not assessed"))
        return checks
    problems = {}
    if region:
        problems["head_region_outside_weight"] = {
            "count": len(region), "rule": "vertices above the Head joint plus blend margin must be weighted "
            "only to Head or its descendants",
            "samples": [{"mesh": m, "vertex": i, "outside_weight": w} for m, i, w in region[:sample_limit]]}
    if island_bad:
        problems["head_islands_with_outside_weight"] = {
            "count": len(island_bad), "rule": "loose head parts (eyes, teeth, hair) must follow only Head "
            "descendants", "islands": island_bad[:sample_limit]}
    if neck_gap:
        problems["neck_without_neck_weight"] = {
            "count": len(neck_gap), "rule": "vertices below the Head joint with >0.5 Head weight need "
            "Neck/Chest blending", "samples": [{"mesh": m, "vertex": i, "head_weight": w}
                                              for m, i, w in neck_gap[:sample_limit]]}
    notes = {"head_bone": head_name, "neck_bone": neck_name,
             "head_blend_margin_fraction": head_blend_margin, "region_threshold_z": round(threshold_z, 5)}
    if neck_name is None:
        notes["neck_note"] = "Neck not mapped; neck blending check skipped"
    if problems:
        checks.append(_check("first_person_head", "needs_repair", "blocking",
                             "In first person VRChat shrinks Head; these weights would leave stretched or "
                             "floating geometry", **notes, problems=problems))
    else:
        checks.append(_check("first_person_head", "pass", "blocking",
                             "Head region and loose head islands follow only Head descendants "
                             "(static weight check; first-person view still needs a client test)", **notes))
    return checks


def analyze(captured, bone_map=None, max_tilt_degrees=10.0, head_blend_margin=0.25):
    bones = captured["armature"]["bones"]
    mapping, ambiguous = guess_humanoid_map(bones)
    if bone_map:
        for role, name in bone_map.items():
            if name not in bones:
                raise ValueError(f"--bone-map names unknown bone {name!r} for {role}")
            mapping[role] = name
            ambiguous.pop(role, None)
    checks = [
        check_transforms([captured["armature"]] + captured["meshes"]),
        check_leaf_bones(bones, {g for m in captured["meshes"] for v in m["vertices"]
                                 for g, w in v["groups"] if w > 0}),
        check_humanoid(mapping, ambiguous),
        check_rest_pose(bones, mapping, max_tilt_degrees),
        check_modifiers(captured["meshes"]),
    ]
    checks.extend(check_weights(captured["meshes"], bones, mapping, head_blend_margin))
    blocking = [c for c in checks if c["severity"] == "blocking"]
    if any(c["status"] == "needs_repair" for c in blocking):
        status = "needs_repair"
    elif any(c["status"] == "unknown" for c in blocking):
        status = "unknown"
    else:
        status = "pass"
    advisories = [c["name"] for c in checks if c["severity"] == "advisory" and c["status"] != "pass"]
    deform_count = sum(1 for b in bones.values() if b.get("use_deform", True))
    observations = {
        "bone_count": len(bones), "deform_bone_count": deform_count,
        "meshes": [{"name": m["name"], "vertex_count": len(m["vertices"]), "triangle_count": m.get("triangle_count"),
                    "shape_key_count": m["shape_key_count"], "material_slot_count": m.get("material_slot_count")}
                   for m in captured["meshes"]],
        "triangle_total": sum(m.get("triangle_count") or 0 for m in captured["meshes"]),
    }
    return {"status": status, "advisories": advisories, "humanoid_map": mapping,
            "observations": observations, "checks": checks}


# --------------------------------------------------------------------------- Blender capture

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


def _object_transform(obj):
    loc, rot, scale = obj.matrix_world.decompose()
    euler = rot.to_euler()
    return {"name": obj.name, "scale": tuple(scale), "rotation_euler": tuple(euler)}


def capture(bpy, armature_name=None, mesh_names=()):
    """Read stored rest data only: no operators, mode changes, evaluation or saves."""
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if armature_name:
        arm = bpy.data.objects.get(armature_name)
        if arm is None or arm.type != "ARMATURE":
            raise ValueError("Explicit armature object not found")
    elif len(armatures) == 1:
        arm = armatures[0]
    else:
        raise ValueError(f"{len(armatures)} armatures found; pass --armature")
    if arm.mode == "EDIT":
        raise ValueError("Armature is in Edit mode; save from Object mode first")
    world = arm.matrix_world
    bones = {}
    for bone in arm.data.bones:
        bones[bone.name] = {"parent": bone.parent.name if bone.parent else None,
                            "head": tuple(world @ bone.head_local), "tail": tuple(world @ bone.tail_local),
                            "use_deform": bool(bone.use_deform)}
    if mesh_names:
        objs = []
        for name in mesh_names:
            obj = bpy.data.objects.get(name)
            if obj is None or obj.type != "MESH":
                raise ValueError(f"Explicit mesh {name!r} not found")
            objs.append(obj)
    else:
        objs = [o for o in bpy.data.objects if o.type == "MESH" and any(
            m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
    meshes = []
    for obj in objs:
        if obj.mode == "EDIT":
            raise ValueError(f"Mesh {obj.name!r} is in Edit mode; save from Object mode first")
        data = obj.data
        names = {g.index: g.name for g in obj.vertex_groups}
        mw = obj.matrix_world
        vertices = [{"co": tuple(mw @ v.co),
                     "groups": [(names[g.group], g.weight) for g in v.groups if g.group in names]}
                    for v in data.vertices]
        meshes.append({**_object_transform(obj),
                       "modifiers": [m.type for m in obj.modifiers],
                       "shape_key_count": len(data.shape_keys.key_blocks) if data.shape_keys else 0,
                       "material_slot_count": len(obj.material_slots),
                       "triangle_count": sum(max(0, len(p.vertices) - 2) for p in data.polygons),
                       "vertices": vertices, "edges": [tuple(e.vertices) for e in data.edges]})
    return {"armature": {**_object_transform(arm), "bones": bones}, "meshes": meshes}


def write_report(report, output):
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def main(argv=None, bpy_module=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--armature", help="Exact armature object name (required if several exist)")
    parser.add_argument("--mesh", action="append", default=[], help="Exact mesh name; default: meshes "
                        "with an Armature modifier targeting the armature")
    parser.add_argument("--bone-map", help="JSON file mapping Humanoid roles to bone names")
    parser.add_argument("--max-arm-tilt", type=float, default=10.0, help="T-pose tolerance in degrees")
    parser.add_argument("--head-blend-margin", type=float, default=0.25,
                        help="Head blend zone above the Head joint, as a fraction of Head bone length")
    parser.add_argument("--out", required=True, help="New JSON output path; never overwritten")
    args = parser.parse_args(argv)
    if not (0 <= args.head_blend_margin <= 2) or not (0 < args.max_arm_tilt < 90):
        parser.error("tolerances out of range")
    bone_map = None
    if args.bone_map:
        bone_map = json.loads(Path(args.bone_map).read_text(encoding="utf-8"))
        if not isinstance(bone_map, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                     for k, v in bone_map.items()):
            parser.error("--bone-map must be a JSON object of role -> bone name")
    bpy = bpy_module
    if bpy is None:
        try:
            import bpy  # noqa: F811
        except ImportError:
            parser.error("Run inside Blender; bpy observations are unavailable")
    report = {"schema": SCHEMA, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "blender_version": bpy.app.version_string,
              "source": source_fingerprint(bpy.data.filepath, bpy.data.is_dirty),
              "scope": "Static rest-pose/weight observations of the saved source; not an FBX round trip, "
                       "Unity import, SDK build or in-client test"}
    try:
        report.update(analyze(capture(bpy, args.armature, args.mesh), bone_map,
                              args.max_arm_tilt, args.head_blend_margin))
    except ValueError as error:
        report.update(status="unknown", observation_error=str(error), checks=[])
    write_report(report, args.out)
    print(json.dumps({"schema": SCHEMA, "status": report["status"],
                      "failed": [c["name"] for c in report["checks"] if c["status"] != "pass"],
                      "output": args.out}))
    return report


if __name__ == "__main__":
    main()
