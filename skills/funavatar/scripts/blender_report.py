#!/usr/bin/env python3
"""Read-only Blender observations; run with Blender --python, after opening a .blend.

Geometry uses the current frame and viewport dependency graph, including modifiers.
Weight checks use original vertices, not modifier-generated topology. No save or
operator calls are made. Only temporary evaluated meshes are allocated and freed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

COLLECTOR_VERSION = "2.0.0"


def source_provenance(bpy):
    source = {"kind": "blend_file", "state": "unknown", "hash_algorithm": "sha256", "hash": ""}
    data = getattr(bpy, "data", None)
    filename = getattr(data, "filepath", "")
    if not filename:
        source["state"] = "unsaved"
    elif getattr(data, "is_dirty", None) is True:
        source["state"] = "modified"
    elif getattr(data, "is_dirty", None) is False:
        try:
            path = Path(filename)
            before = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = path.stat()
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                source.update(state="saved", hash=digest.hexdigest())
        except OSError:
            pass  # Missing/unreadable source remains unknown, without a stale hash.
    return {"collector": "funavatar.blender_report", "collector_version": COLLECTOR_VERSION,
            "native_target": "not_applicable", "source": source,
            "packages_state": "not_applicable", "packages": []}


def safe_subject(name):
    """Keep an object/scene label, without path syntax or control characters."""
    label = "".join(c if c.isprintable() and c not in "/\\" else "_" for c in name)
    return label.strip()[:120] or "unnamed"


def unweighted_vertices(obj):
    """Return a source-vertex count, or None when group weighting is inapplicable.

    Envelope deformation is not equivalent to vertex-group weighting. A modifier
    mask also changes which vertices need weights, so neither case is guessed.
    """
    deform_names = set()
    for modifier in obj.modifiers:
        if modifier.type != "ARMATURE" or not modifier.show_viewport:
            continue
        rig = modifier.object
        if (rig is None or rig.type != "ARMATURE" or modifier.use_bone_envelopes
                or modifier.vertex_group):
            return None
        if modifier.use_vertex_groups:
            deform_names.update(bone.name for bone in rig.data.bones if bone.use_deform)
    if not deform_names:
        return None
    indices = {group.index for group in obj.vertex_groups if group.name in deform_names}
    return sum(not any(group.group in indices and math.isfinite(group.weight)
                       and group.weight > 0 for group in vertex.groups)
               for vertex in obj.data.vertices)


def collect_report(bpy, root_name=None):
    """Collect native facts. The injected bpy module also permits offline tests."""
    scene = bpy.context.scene
    scene_names = {obj.name for obj in scene.objects}
    if root_name is not None:
        root = scene.objects.get(root_name)
        if root is None:
            raise ValueError("Requested root is not an object in the current scene")
        objects = [root, *(child for child in root.children_recursive if child.name in scene_names)]
        subject = root.name
    else:
        objects = list(scene.objects)
        subject = scene.name
    meshes = [obj for obj in objects if obj.type == "MESH"]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    if not meshes and not armatures:
        raise ValueError("Scope contains no mesh or armature; no avatar target was checked")

    observations = {"mesh_count": len(meshes), "armature_count": len(armatures)}
    scales = [tuple(abs(value) for value in obj.matrix_world.to_scale()) for obj in objects]
    if all(all(math.isfinite(value) for value in scale) for scale in scales):
        observations["nonuniform_scale_objects"] = sum(
            not all(math.isclose(scale[0], value, rel_tol=1e-5, abs_tol=1e-8)
                    for value in scale[1:]) for scale in scales)

    totals = {"triangle_count": 0, "zero_area_faces": 0, "nonfinite_vertices": 0}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    weights = []
    weights_available = True
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        try:
            mesh = evaluated.to_mesh()
            if mesh is None:
                raise ValueError("A mesh object could not be evaluated")
            mesh.calc_loop_triangles()
            totals["triangle_count"] += len(mesh.loop_triangles)
            totals["zero_area_faces"] += sum(face.area == 0 for face in mesh.polygons)
            totals["nonfinite_vertices"] += sum(
                not all(math.isfinite(value) for value in vertex.co) for vertex in mesh.vertices)
        finally:
            evaluated.to_mesh_clear()
        count = unweighted_vertices(obj)
        # An unrelated static mesh does not invalidate checks on deforming meshes.
        has_armature = any(modifier.type == "ARMATURE" and modifier.show_viewport
                           for modifier in obj.modifiers)
        if has_armature and count is None:
            weights_available = False
        if count is not None:
            weights.append(count)
    observations.update(totals)
    if weights and weights_available:
        observations["unweighted_vertices"] = sum(weights)
    return {"schema_version": 2, "tool": "blender", "tool_version": bpy.app.version_string,
            "subject": safe_subject(subject), "observations": observations,
            "provenance": source_provenance(bpy)}


def main(argv=None, bpy_module=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New report file; never overwritten")
    parser.add_argument("--root", help="Existing scene object and its descendants; default: current scene")
    args = parser.parse_args(argv)
    try:
        if args.out.exists():
            raise ValueError("Refusing to overwrite an existing report")
        if bpy_module is None:
            import bpy as bpy_module
        report = collect_report(bpy_module, args.root)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        # Avoid leaking source/project paths from native exception messages.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print("Blender report failed: " + message, file=sys.stderr)
        return 2
    print("Blender observations exported; source file was not saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
