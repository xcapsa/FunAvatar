#!/usr/bin/env python3
"""Render matched orthographic comparison views of an avatar in background Blender.

    blender --background avatar.blend --python scripts/blender_ortho_render.py -- --outdir /abs/new-dir

Produces one PNG per view, a 2x2 sheet (front, left / back, three-quarter) and
render.json with camera scale so pixels can be converted to scene meters.
Optional --weights-bone adds front/left views colored by that bone's subtree weight
(e.g. Head for first-person checks).  Temporary cameras, lights and attributes live
only in the background process; the .blend is never saved.  The images are evidence
for a visual comparison against the reference; they do not score likeness.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

SCHEMA = "funavatar.blender-ortho-render.v1"
# Blender convention: the character faces -Y, its left side is +X, Z is up.
VIEW_DIRECTIONS = {
    "front": (0.0, -1.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "left": (1.0, 0.0, 0.0),
    "right": (-1.0, 0.0, 0.0),
    "three_quarter": (math.sqrt(0.5), -math.sqrt(0.5), 0.0),
}
SHEET_ORDER = ("front", "left", "back", "three_quarter")
ENGINE_CHOICES = ("workbench", "eevee", "cycles")


ENGINE_IDS = {"workbench": ["BLENDER_WORKBENCH"],
              "eevee": ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"],
              "cycles": ["CYCLES"]}


def resolve_engine(choice, try_set):
    """Map a portable name to this Blender's identifier (EEVEE was renamed in 4.2 and again in 5.0).

    `try_set(identifier)` must assign the engine and return False/raise when rejected; the
    RNA enum listing is not used because Blender 5.x omits built-in engines from it.
    """
    for identifier in ENGINE_IDS[choice]:
        try:
            if try_set(identifier) is not False:
                return identifier
        except (TypeError, ValueError):
            continue
    raise ValueError(f"Render engine {choice!r} unavailable in this Blender")


def framing(points, padding=0.08):
    """Shared orthographic scale and centre for a set of world-space points."""
    if not points:
        raise ValueError("No geometry to frame")
    xs, ys, zs = zip(*points)
    lo = (min(xs), min(ys), min(zs))
    hi = (max(xs), max(ys), max(zs))
    centre = tuple((a + b) / 2 for a, b in zip(lo, hi))
    horizontal = math.dist((lo[0], lo[1]), (hi[0], hi[1]))  # widest extent any vertical view can see
    height = hi[2] - lo[2]
    size = max(horizontal, height)
    if size <= 0 or not math.isfinite(size):
        raise ValueError("Degenerate bounding box")
    return {"centre": centre, "bbox_min": lo, "bbox_max": hi, "ortho_scale": size * (1 + 2 * padding),
            "height_m": height}


def tile_2x2(images, width, height):
    """Combine four flat RGBA float lists (row-major, bottom-up as Blender stores them)."""
    if len(images) != 4 or any(len(img) != width * height * 4 for img in images):
        raise ValueError("Need four images of identical size")
    sheet = [0.0] * (width * 2 * height * 2 * 4)
    # Blender pixel rows start at the bottom: top row of the sheet = images 0,1.
    layout = {0: (0, 1), 1: (1, 1), 2: (0, 0), 3: (1, 0)}
    row_stride = width * 2 * 4
    for index, img in enumerate(images):
        col, row = layout[index]
        for y in range(height):
            src = img[y * width * 4:(y + 1) * width * 4]
            start = (row * height + y) * row_stride + col * width * 4
            sheet[start:start + width * 4] = src
    return sheet


def _require_new_dir(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("--outdir must be absolute")
    if path.exists() or path.is_symlink():
        raise ValueError("--outdir must not exist yet")
    if not path.parent.is_dir():
        raise ValueError("--outdir parent must exist")
    path.mkdir()
    return path


def _target_objects(bpy, collection, names):
    if names:
        objs = [bpy.data.objects.get(n) for n in names]
        if any(o is None or o.type != "MESH" for o in objs):
            raise ValueError("An explicit --object is missing or not a mesh")
        return objs
    if collection:
        coll = bpy.data.collections.get(collection)
        if coll is None:
            raise ValueError("Collection not found")
        return [o for o in coll.all_objects if o.type == "MESH"]
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]


def _world_points(bpy, objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objs:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mw = evaluated.matrix_world
            points.extend(tuple(mw @ v.co) for v in mesh.vertices)
        finally:
            evaluated.to_mesh_clear()
    return points


def _weight_attribute(obj, bone_names, attribute="FA_weight"):
    """Temporary point color: red = weight on the bone subtree, blue = none."""
    indices = {g.index for g in obj.vertex_groups if g.name in bone_names}
    mesh = obj.data
    if attribute in mesh.color_attributes:
        mesh.color_attributes.remove(mesh.color_attributes[attribute])
    layer = mesh.color_attributes.new(attribute, "FLOAT_COLOR", "POINT")
    for vertex in mesh.vertices:
        w = min(1.0, sum(g.weight for g in vertex.groups if g.group in indices))
        layer.data[vertex.index].color = (w, 0.05, 1.0 - w, 1.0)
    return layer


def render(bpy, outdir, engine="workbench", resolution=1024, views=SHEET_ORDER, collection=None,
           objects=(), weights_bone=None, armature=None, color="material"):
    import mathutils

    if not bpy.app.background:
        raise ValueError("Run with blender --background so the open session is never modified")
    scene = bpy.context.scene
    def try_set(identifier):
        scene.render.engine = identifier
        return scene.render.engine == identifier

    engine_id = resolve_engine(engine, try_set)
    targets = _target_objects(bpy, collection, objects)
    if not targets:
        raise ValueError("No mesh objects to render")
    target_set = set(targets)
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and obj not in target_set:
            obj.hide_render = True
    frame = framing(_world_points(bpy, targets))
    centre = mathutils.Vector(frame["centre"])
    distance = frame["ortho_scale"] * 3

    scene.render.resolution_x = scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("FA_world")
    if engine_id == "BLENDER_WORKBENCH":
        shading = scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = {"material": "MATERIAL", "texture": "TEXTURE", "solid": "SINGLE"}[color]
        shading.background_type = "VIEWPORT"
        shading.background_color = (0.82, 0.82, 0.82)
        shading.show_cavity = False
    else:
        scene.world.color = (0.82, 0.82, 0.82)
        tree = getattr(scene.world, "node_tree", None)
        background = tree.nodes.get("Background") if tree else None
        if background is not None:  # node-based worlds ignore world.color
            background.inputs["Color"].default_value = (0.82, 0.82, 0.82, 1.0)
            background.inputs["Strength"].default_value = 1.0
        sun = bpy.data.objects.new("FA_sun", bpy.data.lights.new("FA_sun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0, math.radians(30))
        scene.collection.objects.link(sun)
        if engine_id == "CYCLES":
            scene.cycles.samples = 32
            scene.cycles.device = "CPU"

    cam_data = bpy.data.cameras.new("FA_cam")
    cam = bpy.data.objects.new("FA_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    def shoot(view, path, ortho=True):
        direction = mathutils.Vector(VIEW_DIRECTIONS[view])
        cam.location = centre + direction * distance
        cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        cam_data.type = "ORTHO" if ortho else "PERSP"
        cam_data.ortho_scale = frame["ortho_scale"]
        cam_data.clip_end = distance * 4
        if not ortho:
            cam_data.lens = 85
            # 85 mm on a 36 mm sensor: ~2.35x the framed size fills the view.
            cam.location = centre + direction * frame["ortho_scale"] * 2.45
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return str(path)

    files = {}
    for view in views:
        files[view] = shoot(view, outdir / f"{view}.png", ortho=view != "three_quarter")

    sheet_path = None
    if all(v in files for v in SHEET_ORDER):
        pixels = []
        for view in SHEET_ORDER:
            image = bpy.data.images.load(files[view], check_existing=False)
            pixels.append(list(image.pixels[:]))
            bpy.data.images.remove(image)
        sheet = bpy.data.images.new("FA_sheet", resolution * 2, resolution * 2, alpha=True)
        try:
            import numpy as np
            a = [np.asarray(p, dtype=np.float32).reshape(resolution, resolution, 4) for p in pixels]
            tiled = np.concatenate([np.concatenate([a[2], a[3]], axis=1),
                                    np.concatenate([a[0], a[1]], axis=1)], axis=0)
            sheet.pixels.foreach_set(tiled.ravel())
        except ImportError:
            sheet.pixels[:] = tile_2x2(pixels, resolution, resolution)
        sheet_path = outdir / "sheet-2x2.png"
        sheet.filepath_raw = str(sheet_path)
        sheet.file_format = "PNG"
        sheet.save()

    weight_files = {}
    weights_note = None
    if weights_bone:
        if armature:
            arm = bpy.data.objects.get(armature)
            arm = arm if arm is not None and arm.type == "ARMATURE" else None
        else:
            rigs = {m.object for o in targets for m in o.modifiers
                    if m.type == "ARMATURE" and m.object is not None}
            arm = next(iter(rigs)) if len(rigs) == 1 else None
        if arm is None:
            weights_note = ("Armature not found or ambiguous across target meshes; pass --armature. "
                            "Weight views skipped")
        elif weights_bone not in arm.data.bones:
            weights_note = "Weights bone not in armature; weight views skipped"
        elif engine_id != "BLENDER_WORKBENCH":
            weights_note = "Weight views need --engine workbench; skipped"
        else:
            root = arm.data.bones[weights_bone]
            subtree = {root.name} | {b.name for b in root.children_recursive}
            for obj in targets:
                layer = _weight_attribute(obj, subtree)
                obj.data.color_attributes.active_color = layer
            scene.display.shading.color_type = "VERTEX"
            for view in ("front", "left"):
                weight_files[view] = shoot(view, outdir / f"weights-{weights_bone}-{view}.png")

    pixel_size = frame["ortho_scale"] / resolution
    return {"engine": engine_id, "resolution_px": resolution, "color": color,
            "objects": [o.name for o in targets], "framing": frame,
            "meters_per_pixel_ortho": pixel_size, "views": files,
            "sheet": str(sheet_path) if sheet_path else None,
            "sheet_layout": [["front", "left"], ["back", "three_quarter"]],
            "three_quarter_projection": "perspective 85mm (not measurable)",
            "weights_bone": weights_bone, "weight_views": weight_files, "weights_note": weights_note,
            "view_convention": "character faces -Y; 'left' is the character's anatomical left (+X)"}


def main(argv=None, bpy_module=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outdir", required=True, help="Absolute, not yet existing output directory")
    parser.add_argument("--engine", choices=ENGINE_CHOICES, default="workbench")
    parser.add_argument("--color", choices=("material", "texture", "solid"), default="material",
                        help="Workbench coloring")
    parser.add_argument("--resolution", type=int, default=1024, help="Pixels per square view")
    parser.add_argument("--views", default=",".join(SHEET_ORDER),
                        help="Comma list from " + ", ".join(VIEW_DIRECTIONS))
    parser.add_argument("--collection", help="Render only meshes in this collection")
    parser.add_argument("--object", action="append", default=[], help="Exact mesh name; repeatable")
    parser.add_argument("--weights-bone", help="Also render weight views for this bone and its children")
    parser.add_argument("--armature", help="Armature for --weights-bone")
    args = parser.parse_args(argv)
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    if not views or any(v not in VIEW_DIRECTIONS for v in views):
        parser.error("unknown view")
    if not 64 <= args.resolution <= 4096:
        parser.error("--resolution must be between 64 and 4096")
    bpy = bpy_module
    if bpy is None:
        try:
            import bpy  # noqa: F811
        except ImportError:
            parser.error("Run inside Blender")
    outdir = _require_new_dir(args.outdir)
    report = {"schema": SCHEMA, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "blender_version": bpy.app.version_string,
              "source": Path(bpy.data.filepath).name if bpy.data.filepath else None,
              "scope": "Diagnostic renders for visual comparison; no likeness score or runtime evidence"}
    try:
        report.update(status="rendered", **render(bpy, outdir, args.engine, args.resolution, views,
                                                  args.collection, args.object, args.weights_bone,
                                                  args.armature, args.color))
    except ValueError as error:
        report.update(status="failed", error=str(error))
    (outdir / "render.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "status": report["status"], "outdir": str(outdir)}))
    return report


if __name__ == "__main__":
    main()
