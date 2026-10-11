import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "funavatar" / "scripts" / "blender_face_probe.py"
SPEC = importlib.util.spec_from_file_location("blender_face_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def shapes():
    return {
        "Rest": {"relative_key": "Rest", "coordinates": [(0, 0, 0), (1, 0, 0)]},
        "Jaw": {"relative_key": "Rest", "coordinates": [(0, 0.2, 0), (1, 0, 0)]},
        "JawSmile": {"relative_key": "Jaw", "coordinates": [(0, 0.2, 0), (1, 0, 0)]},
    }


class DeltaTests(unittest.TestCase):
    def test_nonzero_displacement(self):
        result = probe.delta_metrics([(0, 3, 4), (1, 0, 0)], [(0, 0, 0), (1, 0, 0)])
        self.assertEqual(result, {"vertex_count": 2, "changed_vertex_count": 1,
                                  "max_delta": 5, "has_delta": True})

    def test_tolerance_boundary(self):
        self.assertFalse(probe.delta_metrics([(0, 1e-6, 0)], [(0, 0, 0)])["has_delta"])
        self.assertTrue(probe.delta_metrics([(0, 2e-6, 0)], [(0, 0, 0)])["has_delta"])

    def test_invalid_observations_are_rejected(self):
        cases = [(None, [(0, 0, 0)]), ([], []), ([(0, 0, 0)], []),
                 ([(0, 0)], [(0, 0, 0)]), ([(0, float("nan"), 0)], [(0, 0, 0)]),
                 ([(0, True, 0)], [(0, 0, 0)])]
        for coords, reference in cases:
            with self.subTest(coords=coords), self.assertRaises(ValueError):
                probe.delta_metrics(coords, reference)

    def test_invalid_epsilon_is_rejected(self):
        for epsilon in (-1, float("nan"), float("inf"), True):
            with self.subTest(epsilon=epsilon), self.assertRaises(ValueError):
                probe.analyze_shapes(None, epsilon=epsilon)


class ShapeTests(unittest.TestCase):
    def test_required_nonzero_is_only_structural_pass(self):
        report = probe.analyze_shapes(shapes(), ["Jaw"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["basis_name"], "Rest")

    def test_actual_relative_reference_can_reveal_zero_delta(self):
        report = probe.analyze_shapes(shapes(), ["JawSmile"])
        self.assertEqual(report["status"], "needs_repair")
        self.assertEqual(report["zero_delta_required"], ["JawSmile"])
        self.assertEqual(report["shapes"][2]["comparison_key"], "Jaw")

    def test_absolute_shapes_compare_against_first_key(self):
        report = probe.analyze_shapes(shapes(), ["JawSmile"], use_relative=False)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["shapes"][2]["comparison_key"], "Rest")

    def test_missing_required_shape_needs_repair(self):
        report = probe.analyze_shapes({}, ["Blink"])
        self.assertEqual(report["status"], "needs_repair")
        self.assertEqual(report["missing"], ["Blink"])

    def test_unavailable_observation_does_not_assert_missing(self):
        report = probe.analyze_shapes(None, ["Blink"])
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unobserved_required"], ["Blink"])

    def test_missing_reference_stays_unknown(self):
        data = shapes()
        data["Jaw"]["relative_key"] = "Unavailable"
        report = probe.analyze_shapes(data, ["Jaw"])
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["unobserved_required"], ["Jaw"])

    def test_bad_coordinate_count_stays_unknown(self):
        data = shapes()
        data["Jaw"]["coordinates"] = [(0, 0, 0)]
        report = probe.analyze_shapes(data, ["Jaw"])
        self.assertEqual(report["status"], "unknown")
        self.assertIsNone(report["shapes"][1]["max_delta"])

    def test_no_requirements_is_observation_not_pass(self):
        self.assertEqual(probe.analyze_shapes(shapes())["status"], "observed")
        self.assertEqual(probe.analyze_shapes({})["status"], "observed")


class OutputTests(unittest.TestCase):
    def test_saved_source_fingerprint_and_dirty_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "test.blend"
            source.write_bytes(b"fixture only")
            result = probe.source_fingerprint(str(source), True)
            self.assertEqual(result["sha256"], hashlib.sha256(b"fixture only").hexdigest())
            self.assertEqual(result["state"], "saved")
            self.assertTrue(result["dirty"])
            self.assertEqual(result["name"], "test.blend")

    def test_unsaved_and_unreadable_source_hash_remain_unknown(self):
        self.assertIsNone(probe.source_fingerprint("", True)["sha256"])
        with tempfile.TemporaryDirectory() as folder:
            result = probe.source_fingerprint(str(Path(folder) / "missing.blend"), False)
            self.assertEqual(result["state"], "unreadable")
            self.assertIsNone(result["sha256"])

    def test_report_is_new_only_and_valid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            report = probe.analyze_shapes(shapes(), ["Jaw"])
            probe.write_report(report, output)
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["status"], "pass")
            with self.assertRaises(FileExistsError):
                probe.write_report({"changed": True}, output)
            self.assertEqual(output.read_bytes(), original)

    def test_invalid_json_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            with self.assertRaises(ValueError):
                probe.write_report({"value": float("nan")}, output)
            self.assertFalse(output.exists())

    def test_missing_mesh_produces_unknown_without_scene_actions(self):
        native = types.SimpleNamespace(
            app=types.SimpleNamespace(version_string="fixture"),
            data=types.SimpleNamespace(filepath="", is_dirty=False, objects={}),
        )
        report = probe.collect_report(native, "NotPresent", ["Blink"])
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["schema"], "funavatar.blender-face-probe.v1")
        self.assertEqual(report["missing"], [])


if __name__ == "__main__":
    unittest.main()
