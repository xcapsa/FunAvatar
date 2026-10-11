"""Offline safety/geometry checks; these do not establish native Blender success."""

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import math
from pathlib import Path
from types import SimpleNamespace as Item
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts/blender_native_smoke.py"
SPEC = importlib.util.spec_from_file_location("blender_native_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class NativeSmokeTests(unittest.TestCase):
    def test_plan_is_unexecuted_and_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new-fixture"
            output = io.StringIO()
            with redirect_stdout(output):
                result = smoke.main(["--outdir", str(target), "--plan"])
            report = json.loads(output.getvalue())
            self.assertEqual(result, 0)
            self.assertFalse(target.exists())
            self.assertFalse(report["executed"])
            self.assertTrue(report["fixture_only"])
            self.assertEqual(report["status"], "planned")

    def test_output_requires_new_absolute_directory_and_existing_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "protected.blend"
            file.write_bytes(b"user-model")
            link = root / "link"
            link.symlink_to(root / "missing", target_is_directory=True)
            for value in ("relative", str(root), str(file), str(link), str(root / "missing" / "child")):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    smoke.output_directory(value)
            self.assertEqual(file.read_bytes(), b"user-model")

    def test_existing_output_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "TEMP_fixture.blend"
            file.write_bytes(b"old")
            with self.assertRaises(ValueError):
                smoke.new_file(file)
            self.assertEqual(file.read_bytes(), b"old")

    def test_loaded_user_file_and_interactive_process_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            for background, filepath in ((False, ""), (True, "/user/avatar.blend")):
                target = Path(directory) / "untouched"
                fake = Item(app=Item(background=background), data=Item(filepath=filepath))
                errors = io.StringIO()
                with redirect_stderr(errors):
                    result = smoke.main(["--outdir", str(target)], bpy_module=fake)
                self.assertEqual(result, 2)
                self.assertFalse(target.exists())
                self.assertIn("fresh", errors.getvalue())

    def test_native_directory_reservation_refuses_concurrent_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = Item(app=Item(background=True), data=Item(filepath=""))
            with self.assertRaises(FileExistsError):
                smoke.run_native(fake, root, False)

    def test_rounded_mesh_is_closed_finite_curved_and_has_seam_safe_uvs(self):
        vertices, faces, face_uvs = smoke.rounded_limb()
        edges = Counter(tuple(sorted((face[index], face[(index + 1) % len(face)])))
                        for face in faces for index in range(len(face)))
        self.assertEqual(set(edges.values()), {2})
        self.assertEqual(len(vertices), 802)
        self.assertEqual(len(faces), 832)
        self.assertTrue(all(math.isfinite(value) for vertex in vertices for value in vertex))
        # Body rings curve away from the end-to-end centerline and narrow at caps.
        first_ring, middle_ring = vertices[1:33], vertices[385:417]
        self.assertGreater(sum(x for x, _, _ in middle_ring) / 32, 0.1)
        self.assertLess(max(abs(y) for _, y, _ in first_ring), 0.28)
        self.assertEqual(len(face_uvs), len(faces))
        self.assertTrue(all(len(face) == len(uv) for face, uv in zip(faces, face_uvs)))
        self.assertTrue(all(0 <= u <= 1 and 0 <= v <= 1 for uv in face_uvs for u, v in uv))
        for face, uv in zip(faces, face_uvs):
            if len(face) == 4:
                self.assertLessEqual(max(u for u, _ in uv) - min(u for u, _ in uv), 1 / 32 + 1e-10)

    def test_joint_weights_cover_every_vertex_and_blend_across_joint(self):
        vertices, _, _ = smoke.rounded_limb()
        for _, _, z in vertices:
            weights = smoke.limb_weights(z)
            self.assertAlmostEqual(sum(weights), 1.0)
            self.assertTrue(all(0 <= weight <= 1 for weight in weights))
        self.assertEqual(smoke.limb_weights(0), (1, 0))
        self.assertEqual(smoke.limb_weights(2.4), (0, 1))
        self.assertAlmostEqual(smoke.limb_weights(1.2)[0], 0.5)

    def test_weight_report_detects_missing_invalid_and_non_normalized_skin(self):
        def vertex(*weights):
            return Item(groups=[Item(group=index, weight=value) for index, value in enumerate(weights)])
        facts = smoke.weight_facts([vertex(0.4, 0.6), vertex(), vertex(0.2, 0.2),
                                   vertex(float("nan")), vertex(-0.5, 1.5)], {0, 1})
        self.assertEqual(facts["unweighted_vertices"], 2)
        self.assertEqual(facts["invalid_weight_vertices"], 2)
        self.assertAlmostEqual(facts["maximum_weight_sum_error"], 0.6)

    def test_missing_or_static_actions_cannot_pass_deformation_check(self):
        facts = dict(vertices=802, polygons=832, smooth_polygons=832, uv_layers=1,
                     materials=1, deform_bones=2, armature_modifiers=1,
                     deform_vertex_groups=["Lower", "Upper"], unweighted_vertices=0,
                     invalid_weight_vertices=0, maximum_weight_sum_error=0, actions=[])
        self.assertFalse(smoke.check_facts(facts)["two_deforming_actions"])
        facts["actions"] = [{"deforms_mesh": True}, {"deforms_mesh": False}]
        self.assertFalse(smoke.check_facts(facts)["two_deforming_actions"])
        facts["actions"][1]["deforms_mesh"] = True
        self.assertTrue(all(smoke.check_facts(facts).values()))


if __name__ == "__main__":
    unittest.main()
