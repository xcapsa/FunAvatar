"""Functional mocked-bpy tests; these do not claim native Blender execution."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace as Item
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts/blender_report.py"
SPEC = importlib.util.spec_from_file_location("blender_report", SCRIPT)
blender_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(blender_report)


class Objects(list):
    def get(self, name):
        return next((obj for obj in self if obj.name == name), None)


def vertex(co=(0, 0, 0), groups=()):
    return Item(co=co, groups=[Item(group=index, weight=weight) for index, weight in groups])


def armature(name="Rig", bones=(("Bone", True),)):
    return object_fixture(name, "ARMATURE", data=Item(
        bones=[Item(name=name, use_deform=deform) for name, deform in bones]))


def modifier(rig, **overrides):
    values = dict(type="ARMATURE", object=rig, show_viewport=True,
                  use_bone_envelopes=False, vertex_group="", use_vertex_groups=True)
    values.update(overrides)
    return Item(**values)


def object_fixture(name="Body", kind="MESH", *, scale=(1, 1, 1), vertices=None,
                   areas=(1.0,), triangles=1, modifiers=(), groups=(), data=None):
    source = data or Item(vertices=vertices or [vertex()])
    evaluated_mesh = Item(vertices=vertices or [vertex()],
                          polygons=[Item(area=area) for area in areas],
                          loop_triangles=[None] * triangles)
    evaluated_mesh.triangulated = False
    def triangulate():
        evaluated_mesh.triangulated = True
    evaluated_mesh.calc_loop_triangles = triangulate
    result = Item(name=name, type=kind, data=source, modifiers=list(modifiers),
                  vertex_groups=[Item(name=group, index=index) for index, group in enumerate(groups)],
                  matrix_world=Item(to_scale=lambda: scale), children_recursive=[])
    result.cleared = 0
    result.evaluation_count = 0
    def clear():
        result.cleared += 1
    def evaluated_get(graph):
        result.evaluation_count += 1
        return Item(to_mesh=lambda: evaluated_mesh, to_mesh_clear=clear)
    result.evaluated_get = evaluated_get
    result.evaluated_mesh = evaluated_mesh
    return result


def fake_bpy(*objects, scene_name="AvatarScene", data=None):
    return Item(app=Item(version_string="4.2.0"), data=data or Item(filepath="", is_dirty=False), context=Item(
        scene=Item(name=scene_name, objects=Objects(objects)),
        evaluated_depsgraph_get=lambda: "native graph"))


class BlenderReportTests(unittest.TestCase):
    def test_evaluated_geometry_and_source_groups_are_counted_without_mutation(self):
        rig = armature(bones=(("Bone", True), ("Control", False)))
        body = object_fixture(vertices=[vertex(groups=((0, 0.8),)),
            vertex(groups=((1, 1.0),)), vertex(groups=((0, 0.0),)),
            vertex((float("inf"), 0, 0))], areas=(1, 0), triangles=3,
            modifiers=[modifier(rig)], groups=("Bone", "Control"), scale=(1, 2, 1))
        static = object_fixture("Accessory", triangles=2)
        report = blender_report.collect_report(fake_bpy(body, rig, static))
        self.assertEqual(report["tool"], "blender")
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["observations"], dict(mesh_count=2, armature_count=1,
            triangle_count=5, zero_area_faces=1, nonfinite_vertices=1,
            nonuniform_scale_objects=1, unweighted_vertices=3))
        self.assertTrue(body.evaluated_mesh.triangulated)
        self.assertEqual(body.cleared, 1)
        self.assertEqual(body.data.vertices[0].groups[0].weight, 0.8)

    def test_saved_source_hash_is_deterministic_changes_with_file_and_omits_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-avatar.blend"
            path.write_bytes(b"saved source fixture")
            module = fake_bpy(object_fixture(), data=Item(filepath=str(path), is_dirty=False))
            first = blender_report.collect_report(module)
            second = blender_report.collect_report(module)
            self.assertEqual(first["provenance"], second["provenance"])
            source = first["provenance"]["source"]
            self.assertEqual(source["state"], "saved")
            self.assertEqual(source["hash_algorithm"], "sha256")
            self.assertEqual(source["hash"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertNotIn(str(path), json.dumps(first))
            self.assertNotIn("private-avatar", json.dumps(first))
            path.write_bytes(b"different saved source fixture")
            self.assertNotEqual(source["hash"], blender_report.collect_report(module)["provenance"]["source"]["hash"])

    def test_modified_unsaved_missing_or_unknown_source_has_no_current_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.blend"
            path.write_bytes(b"saved file must remain unchanged")
            for data, state in ((Item(filepath=str(path), is_dirty=True), "modified"),
                                (Item(filepath="", is_dirty=True), "unsaved"),
                                (Item(filepath=str(path / "missing"), is_dirty=False), "unknown"),
                                (Item(filepath=str(path)), "unknown")):
                with self.subTest(state=state):
                    provenance = blender_report.collect_report(fake_bpy(object_fixture(), data=data))["provenance"]
                    self.assertEqual(provenance["source"]["state"], state)
                    self.assertEqual(provenance["source"]["hash"], "")
                    self.assertEqual(provenance["native_target"], "not_applicable")
                    self.assertEqual(provenance["packages_state"], "not_applicable")
                    self.assertEqual(provenance["packages"], [])
            self.assertEqual(path.read_bytes(), b"saved file must remain unchanged")

    def test_blender_v2_output_is_accepted_without_certifying_runtime(self):
        helper_spec = importlib.util.spec_from_file_location("checks_from_collector", SCRIPT.with_name("project_checks.py"))
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            report = blender_report.collect_report(fake_bpy(object_fixture()))
            path.write_text(json.dumps(report))
            checked, _ = helper.project_check([str(path)])
            self.assertEqual(checked["reports"][0]["provenance"], report["provenance"])
            self.assertEqual(checked["reports"][0]["source_schema_version"], 2)
            self.assertEqual(checked["runtime_status"], "not_verified")

    def test_root_scopes_descendants_and_avoids_absolute_subject_paths(self):
        root = object_fixture("/Avatar\\Root", "EMPTY")
        child = object_fixture("Child", triangles=4)
        excluded = object_fixture("Excluded", triangles=999)
        other_scene_child = object_fixture("Other scene child", triangles=500)
        root.children_recursive = [child, other_scene_child]
        report = blender_report.collect_report(fake_bpy(root, child, excluded), root.name)
        self.assertEqual(report["subject"], "_Avatar_Root")
        self.assertEqual(report["observations"]["mesh_count"], 1)
        self.assertEqual(report["observations"]["triangle_count"], 4)
        self.assertEqual(excluded.evaluation_count, 0)
        self.assertEqual(other_scene_child.evaluation_count, 0)

    def test_static_geometry_does_not_claim_weight_check(self):
        report = blender_report.collect_report(fake_bpy(object_fixture()))
        self.assertNotIn("unweighted_vertices", report["observations"])

    def test_envelopes_masks_missing_rigs_and_disabled_groups_omit_weights(self):
        rig = armature()
        for setting in ({"use_bone_envelopes": True}, {"vertex_group": "Mask"},
                        {"object": None}, {"use_vertex_groups": False}):
            with self.subTest(setting=setting):
                values = {"rig": rig, **setting}
                if "object" in values:
                    values["rig"] = values.pop("object")
                mesh = object_fixture(modifiers=[modifier(**values)], groups=("Bone",))
                report = blender_report.collect_report(fake_bpy(mesh, rig))
                self.assertNotIn("unweighted_vertices", report["observations"])

    def test_partial_weight_checks_are_not_reported_as_a_complete_total(self):
        rig = armature()
        weighted = object_fixture("Known", modifiers=[modifier(rig)], groups=("Bone",))
        envelopes = object_fixture("Unknown", modifiers=[modifier(rig, use_bone_envelopes=True)])
        report = blender_report.collect_report(fake_bpy(weighted, envelopes, rig))
        self.assertNotIn("unweighted_vertices", report["observations"])

    def test_disabled_modifier_does_not_make_static_vertices_unweighted(self):
        rig = armature()
        body = object_fixture(modifiers=[modifier(rig, show_viewport=False)])
        self.assertNotIn("unweighted_vertices",
                         blender_report.collect_report(fake_bpy(body, rig))["observations"])

    def test_all_deformers_contribute_and_negative_uniform_scale_is_uniform(self):
        first = armature("First")
        second = armature("Second", bones=(("Other", True),))
        body = object_fixture(vertices=[vertex(groups=((0, 1),)), vertex(groups=((1, 1),))],
            modifiers=[modifier(first), modifier(second)], groups=("Bone", "Other"), scale=(-2, 2, 2))
        facts = blender_report.collect_report(fake_bpy(body, first, second))["observations"]
        self.assertEqual(facts["unweighted_vertices"], 0)
        self.assertEqual(facts["nonuniform_scale_objects"], 0)

    def test_missing_target_and_empty_scope_fail_instead_of_claiming_a_pass(self):
        for module, root in ((fake_bpy(), None), (fake_bpy(object_fixture()), "Missing"),
                             (fake_bpy(object_fixture("Empty", "EMPTY")), "Empty")):
            with self.subTest(root=root), self.assertRaises(ValueError):
                blender_report.collect_report(module, root)

    def test_unknown_scale_is_omitted(self):
        facts = blender_report.collect_report(fake_bpy(
            object_fixture(scale=(float("nan"), 1, 1))))["observations"]
        self.assertNotIn("nonuniform_scale_objects", facts)

    def test_temporary_mesh_is_freed_when_native_triangulation_fails(self):
        body = object_fixture()
        def fail():
            raise RuntimeError("native failure")
        body.evaluated_mesh.calc_loop_triangles = fail
        with self.assertRaises(RuntimeError):
            blender_report.collect_report(fake_bpy(body))
        self.assertEqual(body.cleared, 1)

    def test_cli_exports_new_json_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                code = blender_report.main(["--out", str(path)], fake_bpy(object_fixture()))
            self.assertEqual((code, errors.getvalue()), (0, ""))
            original = path.read_bytes()
            self.assertEqual(json.loads(original)["tool_version"], "4.2.0")
            with redirect_stdout(output), redirect_stderr(errors):
                code = blender_report.main(["--out", str(path)], fake_bpy(object_fixture()))
            self.assertEqual(code, 2)
            self.assertIn("Refusing to overwrite", errors.getvalue())
            self.assertEqual(original, path.read_bytes())

    def test_cli_leaves_no_report_when_no_avatar_was_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            errors = io.StringIO()
            with redirect_stderr(errors):
                code = blender_report.main(["--out", str(path)], fake_bpy())
            self.assertEqual(code, 2)
            self.assertFalse(path.exists())
            self.assertIn("no avatar target", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
