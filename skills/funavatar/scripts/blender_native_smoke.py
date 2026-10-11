#!/usr/bin/env python3
"""Build/reload a TEMP validation fixture in Blender, never an avatar or user file.

blender --background --factory-startup --python blender_native_smoke.py -- \
    --outdir /absolute/new-directory [--require-fbx]

Ordinary Python can use --plan without bpy or creating files. Native execution
requires a fresh background process with no loaded .blend. It resets that process,
creates one rounded limb with two bones and two actions, saves a new .blend, and
optionally exports/reimports FBX. No packages, preferences or services are changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


LABEL = "TEMP_VALIDATION_FIXTURE_ONLY"
BONES = ("TEMP_Lower", "TEMP_Upper")
ACTIONS = ("TEMP_Sway", "TEMP_Bend")
FILES = ("TEMP_fixture.blend", "TEMP_fixture.fbx", "native-smoke.json")
LIMITATIONS = [
    "Temporary toolchain fixture only; this is not a finished character or avatar.",
    "No semantic fidelity, humanoid mapping, hands, face, IK or full-body tracking test.",
    "No Unity import, SDK build, VRChat client, PhysBone or target-device certification.",
    "Sampled mesh motion demonstrates deformation, not acceptable production joint quality.",
]


def output_directory(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("--outdir must be an explicit absolute path")
    if path.exists() or path.is_symlink():
        raise ValueError("Refusing existing output directory or symlink")
    if not path.parent.is_dir():
        raise ValueError("Output parent must already be a directory")
    return path


def plan(path, require_fbx=False):
    return {"schema_version": 1, "kind": "native_toolchain_fixture", "status": "planned",
            "executed": False, "fixture_only": True, "subject": LABEL,
            "outdir": str(path), "outputs": list(FILES), "require_fbx": require_fbx,
            "limitations": LIMITATIONS}


def rounded_limb(sides=32, rings=25, length=2.4, radius=0.28):
    """Closed capsule-like quad rings, curved centerline and explicit seam UVs."""
    if sides < 8 or rings < 5 or not (length > 2 * radius > 0):
        raise ValueError("Invalid rounded fixture dimensions")
    vertices, coordinates = [(0.0, 0.0, 0.0)], [(0.5, 0.0)]
    for ring in range(rings):
        z = length * (ring + 1) / (rings + 1)
        cap_distance = min(z, length - z)
        width = math.sqrt(radius ** 2 - (radius - cap_distance) ** 2) if cap_distance < radius else radius
        center_x = 0.11 * math.sin(math.pi * z / length)
        for side in range(sides):
            angle = 2 * math.pi * side / sides
            vertices.append((center_x + width * math.cos(angle), width * math.sin(angle), z))
            coordinates.append((side / sides, z / length))
    top = len(vertices)
    vertices.append((0.0, 0.0, length))
    coordinates.append((0.5, 1.0))
    faces = []
    for side in range(sides):
        following = (side + 1) % sides
        faces.append((0, 1 + following, 1 + side))
        for ring in range(rings - 1):
            lower, upper = 1 + ring * sides, 1 + (ring + 1) * sides
            faces.append((lower + side, lower + following, upper + following, upper + side))
        final = 1 + (rings - 1) * sides
        faces.append((final + side, final + following, top))
    face_uvs = []
    for face in faces:
        uv = [coordinates[index] for index in face]
        crosses_seam = max(u for u, _ in uv) - min(u for u, _ in uv) > 0.5
        face_uvs.append([(1.0 if crosses_seam and u == 0 else u, v) for u, v in uv])
    return vertices, faces, face_uvs


def limb_weights(z):
    upper = max(0.0, min(1.0, (z - 0.9) / 0.6))
    return (1.0 - upper, upper)


def weight_facts(vertices, deform_indices):
    unweighted, invalid, maximum_error = 0, 0, 0.0
    for vertex in vertices:
        weights = [group.weight for group in vertex.groups if group.group in deform_indices]
        if not weights or not any(math.isfinite(w) and w > 0 for w in weights):
            unweighted += 1
        if any(not math.isfinite(w) or w < 0 or w > 1 for w in weights):
            invalid += 1
        elif weights:
            maximum_error = max(maximum_error, abs(sum(weights) - 1.0))
    return {"unweighted_vertices": unweighted, "invalid_weight_vertices": invalid,
            "maximum_weight_sum_error": maximum_error}


def attach_action(rig, action):
    rig.animation_data_create()
    rig.animation_data.action = action
    # Blender 4.4+ uses slots; assigning an action alone may not bind its channels.
    if hasattr(action, "slots") and len(action.slots):
        rig.animation_data.action_slot = action.slots[0]


def make_fixture(bpy):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = LABEL
    scene["fixture_only"] = True
    scene["warning"] = "TEMP toolchain validation; NOT AN AVATAR"
    scene.frame_start, scene.frame_end = 1, 25
    vertices, faces, face_uvs = rounded_limb()
    data = bpy.data.meshes.new(LABEL + "_Mesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    mesh = bpy.data.objects.new(LABEL + "_RoundedLimb", data)
    scene.collection.objects.link(mesh)
    for polygon in data.polygons:
        polygon.use_smooth = True
    uv = data.uv_layers.new(name="TEMP_CylindricalUV")
    for polygon, values in zip(data.polygons, face_uvs):
        for loop, coordinate in zip(polygon.loop_indices, values):
            uv.data[loop].uv = coordinate
    material = bpy.data.materials.new("TEMP_Fixture_Cyan")
    material.diffuse_color = (0.04, 0.55, 0.7, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = material.diffuse_color
    shader.inputs["Roughness"].default_value = 0.45
    data.materials.append(material)
    armature = bpy.data.armatures.new(LABEL + "_Bones")
    rig = bpy.data.objects.new(LABEL + "_Armature", armature)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    lower = armature.edit_bones.new(BONES[0])
    lower.head, lower.tail = (0, 0, 0), (0, 0, 1.2)
    upper = armature.edit_bones.new(BONES[1])
    upper.head, upper.tail = lower.tail, (0, 0, 2.4)
    upper.parent, upper.use_connect = lower, True
    bpy.ops.object.mode_set(mode="OBJECT")
    groups = [mesh.vertex_groups.new(name=name) for name in BONES]
    for index, (_, _, z) in enumerate(vertices):
        for group, weight in zip(groups, limb_weights(z)):
            if weight > 0:
                group.add([index], weight, "REPLACE")
    modifier = mesh.modifiers.new("TEMP_ArmatureDeformation", "ARMATURE")
    modifier.object = rig
    modifier.use_bone_envelopes = False
    mesh.parent = rig
    rig.animation_data_create()
    for name, amplitude in zip(ACTIONS, (0.28, 0.85)):
        rig.animation_data.action = None
        for frame, factor in ((1, 0), (13, 1), (25, 0)):
            for index, bone in enumerate(rig.pose.bones):
                bone.rotation_mode = "XYZ"
                bone.rotation_euler = (amplitude * factor * (0.2 if index == 0 else 1), 0, 0)
                bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone.name)
        action = rig.animation_data.action
        action.name = name
        action.use_fake_user = True
    attach_action(rig, bpy.data.actions[ACTIONS[0]])
    scene.frame_set(1)
    return mesh, rig


def mesh_coordinates(bpy, mesh, frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    try:
        temporary = evaluated.to_mesh()
        return [tuple(vertex.co) for vertex in temporary.vertices]
    finally:
        evaluated.to_mesh_clear()


def observe(bpy):
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(meshes) != 1 or len(rigs) != 1:
        raise ValueError("Fixture must contain exactly one mesh and one armature")
    mesh, rig = meshes[0], rigs[0]
    deform_names = {bone.name for bone in rig.data.bones if bone.use_deform}
    indices = {group.index for group in mesh.vertex_groups if group.name in deform_names}
    facts = {"mesh_name": mesh.name, "armature_name": rig.name,
             "vertices": len(mesh.data.vertices), "polygons": len(mesh.data.polygons),
             "smooth_polygons": sum(polygon.use_smooth for polygon in mesh.data.polygons),
             "uv_layers": len(mesh.data.uv_layers), "materials": len(mesh.data.materials),
             "deform_bones": len(deform_names),
             "deform_vertex_groups": sorted(group.name for group in mesh.vertex_groups if group.index in indices),
             "armature_modifiers": sum(modifier.type == "ARMATURE" and modifier.object == rig for modifier in mesh.modifiers),
             **weight_facts(mesh.data.vertices, indices), "actions": []}
    for action in sorted(bpy.data.actions, key=lambda item: item.name):
        attach_action(rig, action)
        start, end = (int(value) for value in action.frame_range)
        first = mesh_coordinates(bpy, mesh, start)
        middle = mesh_coordinates(bpy, mesh, (start + end) // 2)
        delta = max((math.dist(a, b) for a, b in zip(first, middle)), default=0.0)
        facts["actions"].append({"name": action.name, "frames": [start, end],
                                 "sampled_mesh_motion": delta, "deforms_mesh": delta > 1e-4})
    if facts["actions"]:
        attach_action(rig, bpy.data.actions[facts["actions"][0]["name"]])
    bpy.context.scene.frame_set(1)
    return facts


def check_facts(facts):
    checks = {
        "rounded_mesh_density": facts["vertices"] >= 200 and facts["polygons"] >= 200,
        "smooth_surface": facts["smooth_polygons"] == facts["polygons"],
        "uv_and_material_preserved": facts["uv_layers"] >= 1 and facts["materials"] >= 1,
        "two_bone_skin": facts["deform_bones"] == 2 and facts["armature_modifiers"] == 1 and len(facts["deform_vertex_groups"]) == 2,
        "normalized_complete_weights": facts["unweighted_vertices"] == 0 and facts["invalid_weight_vertices"] == 0 and facts["maximum_weight_sum_error"] < 1e-5,
        "two_deforming_actions": len(facts["actions"]) >= 2 and all(action["deforms_mesh"] for action in facts["actions"]),
    }
    return checks


def operator_available(operator):
    try:
        operator.get_rna_type()
        return True
    except (AttributeError, RuntimeError):
        return False


def new_file(path):
    if path.exists() or path.is_symlink():
        raise ValueError("Refusing to overwrite output: " + path.name)
    return str(path)


def file_facts(path):
    return {"name": path.name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run_native(bpy, path, require_fbx):
    if not bpy.app.background or bpy.data.filepath:
        raise ValueError("Use a fresh --background --factory-startup process with no loaded .blend")
    path.mkdir(mode=0o700)  # Atomic reservation; never reuse a pre-existing directory.
    report = plan(path, require_fbx)
    report.update(executed=True, status="failed", tool="blender", tool_version=bpy.app.version_string)
    try:
        make_fixture(bpy)
        blend = path / FILES[0]
        result = bpy.ops.wm.save_as_mainfile(filepath=new_file(blend), check_existing=True)
        if "FINISHED" not in result:
            raise RuntimeError("Blender did not finish saving the fixture")
        report["blend"] = file_facts(blend)
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        report["blend_reload"] = observe(bpy)
        report["blend_reload_checks"] = check_facts(report["blend_reload"])
        if not all(report["blend_reload_checks"].values()):
            raise RuntimeError("Saved/reloaded Blender fixture failed its native checks")
        fbx = path / FILES[1]
        # Some releases ship FBX as a bundled add-on. Enable only in this disposable
        # process; never install an extension or save preferences to obtain it.
        if not operator_available(bpy.ops.export_scene.fbx):
            try:
                import addon_utils
                addon_utils.enable("io_scene_fbx", default_set=False, persistent=False)
            except (ImportError, RuntimeError):
                pass
        if not operator_available(bpy.ops.export_scene.fbx):
            report["fbx"] = {"status": "unavailable", "reason": "Native FBX export operator is absent"}
            report["status"] = "blend_pass_fbx_unavailable"
            return report, 3 if require_fbx else 0
        bpy.ops.object.select_all(action="SELECT")
        result = bpy.ops.export_scene.fbx(filepath=new_file(fbx), check_existing=True,
            use_selection=True, object_types={"MESH", "ARMATURE"}, add_leaf_bones=False,
            bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
            bake_anim_simplify_factor=0.0, mesh_smooth_type="FACE", axis_forward="-Z", axis_up="Y")
        if "FINISHED" not in result or not fbx.is_file():
            raise RuntimeError("Blender did not finish exporting FBX")
        report["fbx"] = {"status": "exported", **file_facts(fbx)}
        if not operator_available(bpy.ops.import_scene.fbx):
            report["fbx"]["status"] = "exported_reimport_unavailable"
            report["status"] = "blend_pass_fbx_reimport_unavailable"
            return report, 3 if require_fbx else 0
        bpy.ops.wm.read_factory_settings(use_empty=True)
        result = bpy.ops.import_scene.fbx(filepath=str(fbx), use_anim=True)
        if "FINISHED" not in result:
            raise RuntimeError("Blender did not finish reimporting FBX")
        report["fbx_reimport"] = observe(bpy)
        report["fbx_reimport_checks"] = check_facts(report["fbx_reimport"])
        if not all(report["fbx_reimport_checks"].values()):
            raise RuntimeError("FBX reimport failed its native fixture checks")
        report["fbx"]["status"] = "exported_and_reimported"
        report["status"] = "fixture_pass"
        return report, 0
    except Exception as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        return report, 1


def main(argv=None, bpy_module=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, help="Absolute NEW directory in an existing parent")
    parser.add_argument("--plan", action="store_true", help="Print an unexecuted plan; create nothing")
    parser.add_argument("--require-fbx", action="store_true", help="Return 3 if native FBX round trip is unavailable")
    args = parser.parse_args(argv)
    try:
        path = output_directory(args.outdir)
        if args.plan:
            print(json.dumps(plan(path, args.require_fbx), indent=2))
            return 0
        if bpy_module is None:
            try:
                import bpy as bpy_module
            except ImportError:
                print(json.dumps({"status": "unavailable", "executed": False,
                                  "reason": "Run with a Blender executable; bpy is unavailable"}))
                return 3
        report, code = run_native(bpy_module, path, args.require_fbx)
        with (path / FILES[2]).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": report["status"], "fixture_only": True,
                          "report": str(path / FILES[2])}))
        return code
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
