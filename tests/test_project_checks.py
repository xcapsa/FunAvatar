"""Behavior and evidence boundaries of the dependency-free project helper."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "funavatar" / "scripts"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


funavatar = load_module("funavatar_checks_cli", "funavatar.py")
checks = load_module("funavatar_checks", "project_checks.py")


class ProjectChecksTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = funavatar.main(list(args))
        return code, output.getvalue(), errors.getvalue()

    def report(self, tool="unity", observations=None, **extra):
        data = {"schema_version": 1, "tool": tool, "tool_version": "2022.3.22f1" if tool == "unity" else "4.2.0",
                "subject": "Example avatar", "observations": observations or {}}
        data.update(extra)
        path = self.root / f"{tool}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    @staticmethod
    def by_id(result):
        return {item["id"]: item for report in result["reports"] for item in report["checks"]}

    def test_missing_observations_are_unverified_and_do_not_execute_runtime(self):
        report = self.report()
        before = report.read_bytes()
        code, output, errors = self.run_cli("project-check", str(report))
        self.assertEqual((code, errors), (0, ""))
        result = json.loads(output)
        self.assertEqual(result["scope"], "static_supplied_reports")
        self.assertEqual(result["status"], "not_verified")
        self.assertEqual(result["runtime_status"], "not_verified")
        self.assertTrue(all(item["status"] == "not_verified" for item in self.by_id(result).values()))
        self.assertTrue(all(item["status"] == "not_verified" and item["evidence"] is None for item in result["required_evidence"]))
        self.assertIn("blender_static_report", {item["id"] for item in result["required_evidence"]})
        self.assertEqual(before, report.read_bytes())

    def test_reported_zero_is_narrow_static_pass_with_hashed_provenance(self):
        report = self.report(observations={"missing_scripts": 0, "renderer_count": 2, "vrchat_descriptor_count": 1})
        code, output, errors = self.run_cli("project-check", str(report))
        self.assertEqual((code, errors), (0, ""))
        result = json.loads(output)
        item = self.by_id(result)["missing_scripts"]
        self.assertEqual(item["status"], "pass")
        self.assertEqual(item["evidence"]["value"], 0)
        self.assertEqual(item["evidence"]["report"], str(report.resolve()))
        self.assertEqual(len(item["evidence"]["sha256"]), 64)
        self.assertIn(item["source"], result["sources"])
        self.assertIn("surveyed scope", item["detail"])
        self.assertEqual(result["runtime_status"], "not_verified")
        fidelity = next(item for item in result["required_evidence"] if item["id"] == "reference_fidelity")
        self.assertEqual((fidelity["status"], fidelity["evidence"]), ("not_verified", None))

    def test_conditional_issues_need_review_without_forcing_humanoid_or_rewrite(self):
        report = self.report(observations={"missing_animation_bindings": 3,
                                           "checked_animation_bindings": 7,
                                           "conditional_animation_bindings": 3,
                                           "invalid_humanoid_avatars": 1,
                                           "missing_material_slots": 1})
        code, output, errors = self.run_cli("project-check", str(report))
        self.assertEqual((code, errors), (3, ""))
        result = json.loads(output)
        by_id = self.by_id(result)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(by_id["missing_animation_bindings"]["status"], "needs_review")
        self.assertIn("rewritten by existing tools", by_id["missing_animation_bindings"]["detail"])
        self.assertIn("do not force Humanoid", by_id["invalid_humanoid_avatars"]["detail"])
        self.assertEqual(by_id["missing_material_slots"]["status"], "needs_review")
        self.assertEqual(result["reports"][0]["additional_observations"]["conditional_animation_bindings"], 3)

    def test_geometry_and_missing_references_fail_but_counts_have_no_performance_budget(self):
        blender = self.report("blender", {"nonfinite_vertices": 1, "triangle_count": 100_000_000,
                                           "unweighted_vertices": 5, "nonuniform_scale_objects": 1})
        unity = self.report(observations={"missing_scripts": 1, "missing_shaders": 1})
        code, output, errors = self.run_cli("project-check", str(blender), str(unity))
        self.assertEqual((code, errors), (1, ""))
        result = json.loads(output)
        by_id = self.by_id(result)
        self.assertEqual(by_id["nonfinite_vertices"]["status"], "fail")
        self.assertEqual(by_id["missing_scripts"]["status"], "fail")
        self.assertEqual(by_id["missing_shaders"]["status"], "fail")
        self.assertEqual(by_id["triangle_count"]["status"], "pass")
        self.assertEqual(by_id["unweighted_vertices"]["status"], "needs_review")
        self.assertIn("envelopes", by_id["unweighted_vertices"]["detail"])
        self.assertEqual(result["runtime_status"], "not_verified")

    def test_invalid_or_nonfinite_counts_are_rejected_without_output_files(self):
        target = self.root / "result.json"
        for value in (-1, True, 0.5, float("nan"), float("inf"), "0", None, checks.MAX_COUNT + 1):
            with self.subTest(value=value):
                report = self.report(observations={"missing_scripts": value})
                code, output, errors = self.run_cli("project-check", str(report), "--out", str(target))
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertTrue(errors)
                self.assertFalse(target.exists())

    def test_malformed_schema_duplicates_unknown_fields_and_oversize_are_rejected(self):
        path = self.root / "invalid.json"
        valid = {"schema_version": 1, "tool": "unity", "tool_version": "2022.3", "subject": "avatar", "observations": {}}
        fixtures = ["{", "[]", '{"schema_version":1,"schema_version":1}',
                    json.dumps({**valid, "schema_version": True}),
                    json.dumps({**valid, "tool_version": ""}),
                    json.dumps({**valid, "tool": "unknown"}),
                    json.dumps({**valid, "observations": {"missng_scripts": 0}}),
                    json.dumps({**valid, "observations": []}),
                    json.dumps({**valid, "unexpected": True}),
                    json.dumps({**valid, "target": "quest3"}),
                    json.dumps({**valid, "subject": "x" * 513}),
                    json.dumps({**valid, "observations": {"missing_animation_bindings": 5, "checked_animation_bindings": 4}}),
                    json.dumps({**valid, "observations": {"conditional_animation_bindings": 2, "missing_animation_bindings": 1}}),
                    " " * (checks.MAX_REPORT_BYTES + 1), b"\xff"]
        for fixture in fixtures:
            with self.subTest(fixture=str(fixture)[:80]):
                path.write_bytes(fixture if isinstance(fixture, bytes) else fixture.encode())
                code, output, errors = self.run_cli("project-check", str(path))
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertTrue(errors)
        report = self.report()
        self.assertEqual(self.run_cli("project-check", *([str(report)] * (checks.MAX_REPORTS + 1)))[0], 2)

    def test_compact_deterministic_output_and_no_overwrite(self):
        report = self.report(observations={"missing_scripts": 1})
        target = self.root / "new" / "result.json"
        first = self.run_cli("project-check", str(report), "--out", str(target))
        second = self.run_cli("project-check", str(report))
        self.assertEqual(first[0], 1)
        self.assertEqual(first[1], second[1])
        self.assertEqual(target.read_text(), first[1])
        self.assertEqual(first[1].count("\n"), 1)
        target.write_text("Reviewer notes")
        code, output, errors = self.run_cli("project-check", str(report), "--out", str(target))
        self.assertEqual((code, output), (2, ""))
        self.assertIn("Refusing to overwrite", errors)
        self.assertEqual(target.read_text(), "Reviewer notes")

    def test_debug_plans_route_each_symptom_without_claiming_execution(self):
        expected = {"effects": "FX", "remote": "synchronization", "mobile": "Android",
                    "deformation": "nonhumanoid", "pixelation": "wireframe", "motion": "PhysBone",
                    "fidelity": "single-character"}
        for symptom, phrase in expected.items():
            with self.subTest(symptom=symptom):
                target = self.root / symptom
                code, output, errors = self.run_cli("debug-plan", "--symptom", symptom,
                                                    "--platform", "both", "--out", str(target))
                self.assertEqual((code, errors), (0, ""))
                result = json.loads(output)
                plan = json.loads((target / "debug-plan.json").read_text())
                self.assertFalse(result["executed"])
                self.assertEqual(plan["status"], "not_verified")
                self.assertFalse(plan["executed"])
                self.assertIn(phrase, " ".join(plan["steps"]))
                if symptom == "fidelity":
                    steps = " ".join(plan["steps"])
                    self.assertIn("provider, version, settings and supported inputs", steps)
                    self.assertIn("imported engine height", steps)
                    self.assertIn("Stop before rig or effects", steps)
                    self.assertIn("reference_fidelity", {item["id"] for item in plan["evidence_checklist"]})
                self.assertTrue(all(item["status"] == "not_verified" and item["evidence"] is None for item in plan["evidence_checklist"]))
                self.assertIn("android_device", {item["id"] for item in plan["evidence_checklist"]})
                self.assertIn("no project inspection or tests executed", (target / "debug-plan.md").read_text())

    def test_debug_plan_preserves_existing_notes_and_platform_specific_scope(self):
        target = self.root / "plan"
        target.mkdir()
        notes = target / "debug-plan.md"
        notes.write_text("Existing notes")
        code, output, errors = self.run_cli("debug-plan", "--symptom", "deformation", "--platform", "pc", "--out", str(target))
        self.assertEqual((code, output), (2, ""))
        self.assertIn("Refusing to overwrite", errors)
        self.assertEqual(notes.read_text(), "Existing notes")
        self.assertFalse((target / "debug-plan.json").exists())
        target = self.root / "pc"
        self.run_cli("debug-plan", "--symptom", "deformation", "--platform", "pc", "--out", str(target))
        plan = json.loads((target / "debug-plan.json").read_text())
        self.assertNotIn("android_device", {item["id"] for item in plan["evidence_checklist"]})


if __name__ == "__main__":
    unittest.main()
