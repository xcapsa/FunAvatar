"""Build a disposable humanoid mannequin to exercise blender_vrc_checks/ortho_render in real Blender.

    blender --background --factory-startup --python tests/blender/vrc_fixture.py -- --out /abs/new.blend [--defects]

TEST FIXTURE ONLY: rigid capsule parts, not an avatar.  --defects adds a leaf bone,
an A-pose, an eye weighted to the chest, an unapplied DataTransfer beside shape keys
and an unapplied object scale, so every check has a known failing case.
"""

import argparse
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

args = argparse.ArgumentParser()
args.add_argument("--out", required=True)
args.add_argument("--defects", action="store_true")
opts = args.parse_args(sys.argv[sys.argv.index("--") + 1:])
out = Path(opts.out)
if not out.is_absolute() or out.exists():
    raise SystemExit("--out must be absolute and new")

bpy.ops.wm.read_factory_settings(use_empty=True)
drop = 0.18 if opts.defects else 0.0
BONES = {  # name: (parent, head, tail, radius)
    "Hips": (None, (0, 0, 0.95), (0, 0, 1.08), 0.15),
    "Spine": ("Hips", (0, 0, 1.08), (0, 0, 1.25), 0.14),
    "Chest": ("Spine", (0, 0, 1.25), (0, 0, 1.45), 0.16),
    "Neck": ("Chest", (0, 0, 1.45), (0, 0, 1.55), 0.05),
    "Head": ("Neck", (0, 0, 1.55), (0, 0, 1.78), 0.11),
    "Eye.L": ("Head", (0.04, -0.09, 1.66), (0.04, -0.12, 1.66), 0.0),
    "Eye.R": ("Head", (-0.04, -0.09, 1.66), (-0.04, -0.12, 1.66), 0.0),
}
for side, sx in (("L", 1), ("R", -1)):
    BONES.update({
        f"UpperLeg.{side}": ("Hips", (0.09 * sx, 0, 0.95), (0.09 * sx, 0, 0.52), 0.07),
        f"LowerLeg.{side}": (f"UpperLeg.{side}", (0.09 * sx, 0, 0.52), (0.09 * sx, 0, 0.08), 0.055),
        f"Foot.{side}": (f"LowerLeg.{side}", (0.09 * sx, 0, 0.08), (0.09 * sx, -0.14, 0.03), 0.045),
        f"UpperArm.{side}": ("Chest", (0.19 * sx, 0, 1.42), (0.45 * sx, 0, 1.42 - drop), 0.045),
        f"LowerArm.{side}": (f"UpperArm.{side}", (0.45 * sx, 0, 1.42 - drop), (0.7 * sx, 0, 1.42 - 2 * drop), 0.04),
        f"Hand.{side}": (f"LowerArm.{side}", (0.7 * sx, 0, 1.42 - 2 * drop), (0.8 * sx, 0, 1.42 - 2.4 * drop), 0.04),
    })
if opts.defects:
    BONES["Head_end"] = ("Head", (0, 0, 1.78), (0, 0, 1.88), 0.0)

arm_data = bpy.data.armatures.new("Armature")
arm = bpy.data.objects.new("Armature", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for name, (parent, head, tail, _) in BONES.items():
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = head, tail
    eb.use_deform = not name.endswith("_end")
for name, (parent, *_rest) in BONES.items():
    if parent:
        arm_data.edit_bones[name].parent = arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")


def part_mesh(name, parts):
    """parts: list of (bone, matrix, segments) -> one mesh, each part rigidly weighted to its bone."""
    # Weights live in a bmesh deform layer so they stay bound to vertices whatever order to_mesh writes.
    me = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    group_index = {}
    for bone_name, _, _ in parts:
        if bone_name not in group_index:
            group_index[bone_name] = obj.vertex_groups.new(name=bone_name).index
    bm = bmesh.new()
    deform = bm.verts.layers.deform.verify()
    for bone_name, matrix, seg in parts:
        result = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg // 2),
                                           radius=1.0, matrix=matrix)
        for vert in result["verts"]:
            vert[deform][group_index[bone_name]] = 1.0
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    return obj


def capsule(bone_name):
    _, head, tail, radius = BONES[bone_name]
    head, tail = Vector(head), Vector(tail)
    axis = tail - head
    rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
    scale = Matrix.Diagonal((radius, radius, axis.length / 2 + radius * 0.6, 1))
    return Matrix.Translation((head + tail) / 2) @ rot @ scale


body_parts = [(n, capsule(n), 24) for n, b in BONES.items() if b[3] > 0]
body = part_mesh("Body", body_parts)
mat = bpy.data.materials.new("Skin")
mat.diffuse_color = (0.85, 0.62, 0.48, 1)
body.data.materials.append(mat)

eye_owner = "Chest" if opts.defects else None
eyes = part_mesh("Eyes", [(eye_owner or "Eye.L", Matrix.Translation((0.04, -0.095, 1.66)) @ Matrix.Diagonal((0.022,) * 3 + (1,)), 12),
                          ("Eye.R", Matrix.Translation((-0.04, -0.095, 1.66)) @ Matrix.Diagonal((0.022,) * 3 + (1,)), 12)])
eye_mat = bpy.data.materials.new("Eye")
eye_mat.diffuse_color = (0.05, 0.05, 0.08, 1)
eyes.data.materials.append(eye_mat)

if opts.defects:
    body.shape_key_add(name="Basis")
    body.shape_key_add(name="vrc.v_aa")
    dt = body.modifiers.new("WeightsFromCage", "DATA_TRANSFER")
    dt.object = eyes
    eyes.scale = (1.0, 1.0, 1.0)
    body.scale = (1.02, 1.02, 1.02)

bpy.ops.wm.save_as_mainfile(filepath=str(out))
print("FIXTURE", out, "defects" if opts.defects else "clean")
