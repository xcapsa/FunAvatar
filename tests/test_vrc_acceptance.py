"""Offline checks for partial Good thresholds and expression-parameter budgets."""

import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts"
sys.path.insert(0, str(SCRIPTS))
import vrc_acceptance as checker


def measurement(target="pc", **updates):
    return {"schema_version": 1, "kind": "funavatar_vrc_measurements", "asset_sha256": "a" * 64,
            "target": target, "evidence_scope": "static_measured", **updates}


def parameters(count, kind="bool", synced=True):
    return [{"name": f"custom-{index}", "type": kind, "synced": synced} for index in range(count)]


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = checker.read_json(checker.PROFILE_PATH)

    def test_pc_and_mobile_good_boundaries_are_inclusive_for_every_supported_metric(self):
        for target, profile in (("pc", "pc"), ("android", "mobile"), ("ios", "mobile")):
            thresholds = self.profile["good"][profile]
            result = checker.check(measurement(target, metrics=thresholds))
            self.assertEqual(result["good_partial_profile"]["status"], "within")
            self.assertTrue(result["good_partial_profile"]["complete_for_supported_metrics"])
            for name, maximum in thresholds.items():
                with self.subTest(target=target, metric=name):
                    metrics = {**thresholds, name: maximum + 1}
                    result = checker.check(measurement(target, metrics=metrics))
                    self.assertEqual(result["good_partial_profile"]["metrics"][name]["status"], "exceeded")

    def test_same_measurements_can_meet_pc_good_but_exceed_mobile_good(self):
        metrics = self.profile["good"]["pc"]
        self.assertEqual(checker.check(measurement("pc", metrics=metrics))["good_partial_profile"]["status"], "within")
        self.assertEqual(checker.check(measurement("android", metrics=metrics))["good_partial_profile"]["status"], "exceeded")

    def test_missing_observations_are_unknown_even_if_some_measured_values_are_zero(self):
        result = checker.check(measurement(metrics={"triangles": 0, "contacts": None}))
        self.assertEqual(result["good_partial_profile"]["status"], "unknown")
        self.assertFalse(result["good_partial_profile"]["complete_for_supported_metrics"])
        self.assertEqual(result["good_partial_profile"]["metrics"]["triangles"]["status"], "within")
        self.assertEqual(result["good_partial_profile"]["metrics"]["contacts"]["status"], "unknown")
        self.assertEqual(result["expression_parameters"]["status"], "unknown")
        self.assertEqual(result["asset_integrity"]["status"], "hash_declared_only")

    def test_mobile_hard_limits_are_separate_from_good_rank_thresholds(self):
        thresholds = self.profile["hard_limits"]["mobile"]
        at_limit = checker.check(measurement("android", metrics=thresholds))
        self.assertEqual(at_limit["hard_limits"]["status"], "within")
        self.assertEqual(at_limit["good_partial_profile"]["status"], "exceeded")
        for name, maximum in thresholds.items():
            with self.subTest(metric=name):
                result = checker.check(measurement("android", metrics={**thresholds, name: maximum + 1}))
                self.assertEqual(result["hard_limits"]["metrics"][name]["status"], "exceeded")
        self.assertEqual(checker.check(measurement("pc"))["hard_limits"]["status"], "not_assessed")

    def test_mobile_triangle_20000_boundary_is_visibility_not_absolute_upload_block(self):
        for triangles, status in ((20000, "within_threshold"), (20001, "above_very_poor_threshold")):
            result = checker.check(measurement("android", metrics={"triangles": triangles}))
            self.assertEqual(result["triangle_visibility"]["status"], status)
            self.assertFalse(result["triangle_visibility"]["absolute_upload_limit"])
            self.assertNotIn("triangles", result["hard_limits"]["metrics"])
            self.assertEqual(result["upload_eligibility"], "not_assessed")

    def test_no_complete_profile_certifies_sdk_rank_runtime_or_ios_ledger(self):
        for target in ("pc", "android", "ios"):
            result = checker.check(measurement(target, metrics=self.profile["good"]["pc" if target == "pc" else "mobile"],
                                               expression_parameters=[]))
            self.assertFalse(result["runtime_verified"])
            self.assertEqual(result["sdk_rank"], "not_assessed")
            self.assertEqual(result["asset_sha256"], "a" * 64)
            self.assertEqual(result["target"], target)
            self.assertEqual(result["evidence_scope"], "static_measured")
        self.assertIn("ledger support are not assessed", result["target_note"])

    def test_exact_256_bits_pass_but_257_bits_and_33_ints_exceed(self):
        for values, bits, status in ((parameters(256), 256, "within"), (parameters(257), 257, "exceeded"),
                                    (parameters(32, "int"), 256, "within"), (parameters(33, "int"), 264, "exceeded"),
                                    (parameters(32, "float"), 256, "within")):
            with self.subTest(bits=bits, kind=values[0]["type"]):
                result = checker.check(measurement(expression_parameters=values))["expression_parameters"]
                self.assertEqual(result["synced_bits"], bits)
                self.assertEqual(result["status"], status)

    def test_unsynced_parameters_use_no_sync_bits_but_count_toward_8192_total(self):
        for count, status in ((8192, "within"), (8193, "exceeded")):
            result = checker.check(measurement(expression_parameters=parameters(count, "float", False)))["expression_parameters"]
            self.assertEqual(result["synced_bits"], 0)
            self.assertEqual(result["custom_parameter_count"], count)
            self.assertEqual(result["status"], status)

    def test_duplicate_and_builtin_read_only_parameters_are_rejected(self):
        for values in ([{"name": "Voice", "type": "float", "synced": True}],
                       [{"name": "Viseme", "type": "int", "synced": False}],
                       [{"name": "IsLocal", "type": "bool", "synced": False}],
                       parameters(1) * 2):
            with self.subTest(values=values), self.assertRaises(ValueError):
                checker.check(measurement(expression_parameters=values))

    def test_invalid_schema_types_and_unknown_metric_names_are_rejected(self):
        for updates in ({"schema_version": True}, {"kind": "unity_report"}, {"target": "quest"},
                        {"asset_sha256": "no-hash"}, {"evidence_scope": "runtime_verified"},
                        {"metrics": []}, {"metrics": {"triangle_typo": 1}}, {"extra": "unrecognized"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                checker.check(measurement(**updates))
        for value in (True, "10", -1, 1.5, float("nan"), float("inf")):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                checker.check(measurement(metrics={"triangles": value}))
        for value in (True, "18", -0.1, float("nan"), float("inf")):
            with self.subTest(texture=value), self.assertRaises(ValueError):
                checker.check(measurement(metrics={"texture_memory_mb": value}))
        self.assertEqual(checker.check(measurement("android", metrics={"texture_memory_mb": 18.01}))["good_partial_profile"]["metrics"]["texture_memory_mb"]["status"], "exceeded")

    def test_invalid_parameter_types_are_not_coerced(self):
        for changes in ({"synced": 1}, {"synced": "false"}, {"type": "trigger"}, {"type": []},
                        {"name": " "}, {"name": "a\0b"}, {"name": False}, {"saved": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                checker.check(measurement(expression_parameters=[{**parameters(1)[0], **changes}]))

    def test_input_reader_rejects_duplicate_keys_nonfinite_numbers_and_oversize(self):
        source = self.root / "bad.json"
        for content in ('{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}', '{"a":NaN}', '{"a":Infinity}',
                        '{"a":-Infinity}', '{"a":1e999}', ' ' * (checker.MAX_JSON_BYTES + 1)):
            source.write_text(content, encoding="utf-8")
            with self.subTest(content=content[:30]), self.assertRaises(ValueError):
                checker.read_json(source)

    def test_asset_path_is_relative_to_input_and_stale_hash_is_rejected(self):
        asset = self.root / "avatar.glb"
        asset.write_bytes(b"measured asset revision")
        data = measurement(asset_sha256=hashlib.sha256(asset.read_bytes()).hexdigest(), asset_path="avatar.glb")
        result = checker.check(data, self.root)
        self.assertEqual(result["asset_integrity"]["status"], "hash_matches_file")
        asset.write_bytes(b"changed asset revision")
        with self.assertRaisesRegex(ValueError, "Stale measurements"):
            checker.check(data, self.root)
        source, output = self.root / "stale.json", self.root / "must-not-exist.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        with patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(checker.main(["check", str(source), "--out", str(output)]), 2)
        self.assertFalse(output.exists())

    def test_cli_writes_new_output_and_preserves_existing_file(self):
        source, output = self.root / "input.json", self.root / "output.json"
        data = measurement(metrics=self.profile["good"]["pc"], expression_parameters=[])
        source.write_text(json.dumps(data), encoding="utf-8")
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(checker.main(["check", str(source), "--out", str(output)]), 0)
        result = json.loads(output.read_text())
        self.assertFalse(result["runtime_verified"])
        saved = output.read_bytes()
        with patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(checker.main(["check", str(source), "--out", str(output)]), 2)
        self.assertEqual(output.read_bytes(), saved)
        self.assertEqual(list(self.root.glob(".vrc-acceptance-*")), [])

    def test_cli_exceeded_exit_is_one_and_unknown_is_explicit_in_output(self):
        source = self.root / "input.json"
        for data, expected in ((measurement(metrics={"triangles": 70001}), 1), (measurement(), 3)):
            source.write_text(json.dumps(data), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(checker.main(["check", str(source)]), expected)
            result = json.loads(output.getvalue())
            self.assertFalse(result["good_partial_profile"]["complete_for_supported_metrics"])
            self.assertFalse(result["runtime_verified"])

    def test_output_symlink_is_preserved_without_overwriting_its_target(self):
        target, link = self.root / "keep.json", self.root / "link.json"
        target.write_text("keep existing report", encoding="utf-8")
        try:
            link.symlink_to(target)
        except OSError as error:
            self.skipTest(f"Filesystem does not permit symlinks: {type(error).__name__}")
        with self.assertRaises(OSError):
            checker.write_new_json(link, checker.check(measurement()))
        self.assertEqual(target.read_text(), "keep existing report")
        self.assertTrue(link.is_symlink())
        self.assertEqual(list(self.root.glob(".vrc-acceptance-*")), [])

    def test_checker_does_not_change_the_supplied_measurements(self):
        data = measurement("android", metrics={"triangles": 12000}, expression_parameters=parameters(3))
        previous = copy.deepcopy(data)
        checker.check(data)
        self.assertEqual(data, previous)


if __name__ == "__main__":
    unittest.main()
