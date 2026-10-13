import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "skills" / "funavatar" / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checks = load("blender_vrc_checks")
render = load("blender_ortho_render")


def bone(parent, head, tail, deform=True):
    return {"parent": parent, "head": head, "tail": tail, "use_deform": deform}


def skeleton(arm_z_drop=0.0):
    b = {
        "Hips": bone(None, (0, 0, 1.0), (0, 0, 1.1)),
        "Spine": bone("Hips", (0, 0, 1.1), (0, 0, 1.3)),
        "Chest": bone("Spine", (0, 0, 1.3), (0, 0, 1.45)),
        "Neck": bone("Chest", (0, 0, 1.45), (0, 0, 1.55)),
        "Head": bone("Neck", (0, 0, 1.55), (0, 0, 1.75)),
        "Eye_L": bone("Head", (0.03, -0.08, 1.65), (0.03, -0.1, 1.65)),
    }
    for side, sx in (("Left", 1), ("Right", -1)):
        b[f"{side}UpperLeg"] = bone("Hips", (0.1 * sx, 0, 1.0), (0.1 * sx, 0, 0.55))
        b[f"{side}LowerLeg"] = bone(f"{side}UpperLeg", (0.1 * sx, 0, 0.55), (0.1 * sx, 0, 0.1))
        b[f"{side}Foot"] = bone(f"{side}LowerLeg", (0.1 * sx, 0, 0.1), (0.1 * sx, -0.1, 0.0))
        b[f"{side}UpperArm"] = bone("Chest", (0.2 * sx, 0, 1.42), (0.45 * sx, 0, 1.42 - arm_z_drop))
        b[f"{side}LowerArm"] = bone(f"{side}UpperArm", (0.45 * sx, 0, 1.42 - arm_z_drop),
                                    (0.7 * sx, 0, 1.42 - 2 * arm_z_drop))
        b[f"{side}Hand"] = bone(f"{side}LowerArm", (0.7 * sx, 0, 1.42 - 2 * arm_z_drop),
                                (0.8 * sx, 0, 1.42 - 2 * arm_z_drop))
    return b


def mesh(name, vertices, edges, modifiers=("ARMATURE",), shape_keys=0):
    return {"name": name, "scale": (1, 1, 1), "rotation_euler": (0, 0, 0), "modifiers": list(modifiers),
            "shape_key_count": shape_keys, "material_slot_count": 1, "triangle_count": 2,
            "vertices": [{"co": co, "groups": groups} for co, groups in vertices], "edges": edges}


def clean_capture():
    body = mesh("Body", [
        ((0, 0, 1.2), [("Spine", 1.0)]),
        ((0, 0, 1.5), [("Neck", 0.6), ("Head", 0.4)]),
        ((0, 0, 1.6), [("Head", 1.0)]),
        ((0, 0, 1.74), [("Head", 1.0)]),
    ], [(0, 1), (1, 2), (2, 3)])
    eyes = mesh("Eyes", [((0.03, -0.09, 1.65), [("Eye_L", 1.0)]),
                         ((0.03, -0.1, 1.66), [("Eye_L", 1.0)])], [(0, 1)])
    hair = mesh("Hair", [((0, 0.05, 1.76), [("Head", 1.0)]),
                         ((0, 0.12, 1.30), [("Head", 1.0)])], [(0, 1)])  # long hair below the head
    return {"armature": {"name": "Armature", "scale": (1, 1, 1), "rotation_euler": (0, 0, 0),
                         "bones": skeleton()},
            "meshes": [body, eyes, hair]}


def by_name(report):
    return {c["name"]: c for c in report["checks"]}


class NamingTests(unittest.TestCase):
    def test_common_rig_spellings_map(self):
        for name, role in [("thigh_l", "LeftUpperLeg"), ("LeftUpLeg", "LeftUpperLeg"),
                           ("DEF-upper_arm.L", "LeftUpperArm"), ("mixamorig:RightForeArm", "RightLowerArm"),
                           ("calf_r", "RightLowerLeg"), ("pelvis", "Hips"), ("neck_01", "Neck")]:
            with self.subTest(name=name):
                mapping, _ = checks.guess_humanoid_map({name: {}})
                self.assertEqual(mapping, {role: name})

    def test_numbered_spine_chain_assigns_chest(self):
        mapping, _ = checks.guess_humanoid_map({"spine_01": {}, "spine_02": {}, "spine_03": {}})
        self.assertEqual(mapping["Spine"], "spine_01")
        self.assertEqual(mapping["Chest"], "spine_02")

    def test_duplicates_are_ambiguous_not_guessed(self):
        mapping, ambiguous = checks.guess_humanoid_map({"Head": {}, "head.001": {}})
        self.assertNotIn("Head", mapping)
        self.assertEqual(ambiguous["Head"], ["Head", "head.001"])


class AnalyzeTests(unittest.TestCase):
    def test_clean_avatar_passes(self):
        report = checks.analyze(clean_capture())
        self.assertEqual(report["status"], "pass", [c for c in report["checks"] if c["status"] != "pass"])

    def test_leaf_bones_block(self):
        cap = clean_capture()
        cap["armature"]["bones"]["Head_end"] = bone("Head", (0, 0, 1.75), (0, 0, 1.85), False)
        report = checks.analyze(cap)
        self.assertEqual(by_name(report)["leaf_bones"]["bones"], ["Head_end"])
        self.assertEqual(report["status"], "needs_repair")

    def test_unapplied_scale_blocks(self):
        cap = clean_capture()
        cap["meshes"][0]["scale"] = (100, 100, 100)
        self.assertEqual(by_name(checks.analyze(cap))["transforms_applied"]["status"], "needs_repair")

    def test_a_pose_is_advisory(self):
        cap = clean_capture()
        cap["armature"]["bones"] = skeleton(arm_z_drop=0.18)
        report = checks.analyze(cap)
        self.assertEqual(by_name(report)["rest_pose"]["status"], "needs_repair")
        self.assertEqual(report["status"], "pass")
        self.assertIn("rest_pose", report["advisories"])

    def test_modifier_beside_shape_keys_blocks(self):
        cap = clean_capture()
        cap["meshes"][0]["modifiers"] = ["DATA_TRANSFER", "ARMATURE"]
        cap["meshes"][0]["shape_key_count"] = 16
        result = by_name(checks.analyze(cap))["modifiers_vs_shape_keys"]
        self.assertEqual((result["status"], result["severity"]), ("needs_repair", "blocking"))

    def test_modifier_without_shape_keys_is_advisory(self):
        cap = clean_capture()
        cap["meshes"][0]["modifiers"] = ["DATA_TRANSFER", "ARMATURE"]
        result = by_name(checks.analyze(cap))["modifiers_vs_shape_keys"]
        self.assertEqual(result["severity"], "advisory")

    def test_head_vertex_weighted_to_chest_blocks(self):
        cap = clean_capture()
        cap["meshes"][0]["vertices"][3]["groups"] = [("Head", 0.8), ("Chest", 0.2)]
        result = by_name(checks.analyze(cap))["first_person_head"]
        self.assertEqual(result["status"], "needs_repair")
        self.assertIn("head_region_outside_weight", result["problems"])

    def test_loose_eye_weighted_to_spine_blocks(self):
        cap = clean_capture()
        cap["meshes"][1]["vertices"][1]["groups"] = [("Eye_L", 0.9), ("Spine", 0.1)]
        cap["meshes"][1]["vertices"][0]["co"] = (0.03, -0.09, 1.56)  # below region threshold
        cap["meshes"][1]["vertices"][1]["co"] = (0.03, -0.1, 1.57)
        problems = by_name(checks.analyze(cap))["first_person_head"]["problems"]
        self.assertIn("head_islands_with_outside_weight", problems)

    def test_neck_skin_without_neck_weight_blocks_but_long_hair_does_not(self):
        cap = clean_capture()
        cap["meshes"][0]["vertices"][1]["groups"] = [("Head", 1.0)]
        cap["meshes"][0]["vertices"].append({"co": (0, 0, 1.47), "groups": [("Neck", 1.0)]})
        cap["meshes"][0]["edges"].append((1, 4))
        problems = by_name(checks.analyze(cap))["first_person_head"]["problems"]
        self.assertEqual([s["mesh"] for s in problems["neck_without_neck_weight"]["samples"]], ["Body"])

    def test_unweighted_vertex_blocks(self):
        cap = clean_capture()
        cap["meshes"][0]["vertices"][0]["groups"] = []
        self.assertEqual(by_name(checks.analyze(cap))["unweighted_vertices"]["count"], 1)

    def test_missing_required_bone(self):
        cap = clean_capture()
        del cap["armature"]["bones"]["LeftFoot"]
        result = by_name(checks.analyze(cap))["humanoid_bones"]
        self.assertEqual(result["missing"], ["LeftFoot"])

    def test_bone_map_overrides_and_validates(self):
        cap = clean_capture()
        cap["armature"]["bones"]["Kopf"] = cap["armature"]["bones"].pop("Head")
        for b in cap["armature"]["bones"].values():
            if b["parent"] == "Head":
                b["parent"] = "Kopf"
        for m in cap["meshes"]:
            for v in m["vertices"]:
                v["groups"] = [("Kopf" if g == "Head" else g, w) for g, w in v["groups"]]
        self.assertEqual(checks.analyze(cap, {"Head": "Kopf"})["status"], "pass")
        with self.assertRaises(ValueError):
            checks.analyze(cap, {"Head": "Nope"})


class RenderHelperTests(unittest.TestCase):
    def test_engine_names_follow_blender_version(self):
        def engines(*names):
            def try_set(identifier):
                if identifier not in names:
                    raise TypeError("enum not found")
                return True
            return try_set
        self.assertEqual(render.resolve_engine("eevee", engines("BLENDER_EEVEE_NEXT")), "BLENDER_EEVEE_NEXT")
        self.assertEqual(render.resolve_engine("eevee", engines("BLENDER_EEVEE", "CYCLES")), "BLENDER_EEVEE")
        with self.assertRaises(ValueError):
            render.resolve_engine("cycles", engines("BLENDER_WORKBENCH"))

    def test_framing_uses_one_scale_for_all_views(self):
        frame = render.framing([(-0.5, -0.1, 0), (0.5, 0.1, 1.8)], padding=0)
        self.assertAlmostEqual(frame["ortho_scale"], 1.8)
        self.assertEqual(frame["centre"], (0.0, 0.0, 0.9))
        with self.assertRaises(ValueError):
            render.framing([(0, 0, 0)])

    def test_tile_places_front_top_left(self):
        imgs = [[float(i)] * 4 for i in range(4)]  # 1x1 images
        sheet = render.tile_2x2(imgs, 1, 1)
        # Blender rows are bottom-up: bottom row back(2), three_quarter(3); top row front(0), left(1).
        self.assertEqual(sheet[0::4], [2.0, 3.0, 0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
