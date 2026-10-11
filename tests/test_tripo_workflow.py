"""Offline behavioral tests for durable Tripo jobs and credit ceilings."""

from __future__ import annotations

import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "funavatar" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import tripo_workflow as workflow_module

Workflow = workflow_module.Workflow


class FakeClient:
    """The public adapter contract without credentials or real HTTP."""

    def __init__(self):
        self.submissions = []
        self.lookups = []
        self.downloads = []
        self.uploads = []
        self.submit_error = None
        self.tasks = {}

    def submit(self, operation, payload):
        self.submissions.append((operation, payload))
        if self.submit_error:
            raise self.submit_error
        task_id = f"task_{len(self.submissions)}"
        self.tasks.setdefault(task_id, {"task_id": task_id, "status": "queued", "progress": 0})
        return {"task_id": task_id}

    def get_task(self, task_id):
        self.lookups.append(task_id)
        return dict(self.tasks[task_id])

    def download(self, url, destination):
        self.downloads.append((url, str(destination)))
        content = b"offline mock GLB asset"
        path = Path(destination)
        with path.open("xb") as handle:
            handle.write(content)
        return {"path": str(path.resolve()), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}

    def upload_file(self, path):
        self.uploads.append(str(path))
        return {"file_token": f"file_{len(self.uploads)}"}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.wf = Workflow.initialize(self.base / "run", "Offline avatar", "10", target="both")
        self.client = FakeClient()

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, job_id="draft", credits="6", **kwargs):
        return self.wf.plan_job(job_id, "text_to_model", {
            "prompt": "A simple neutral character", "model": "v3.1-20260211"
        }, credits, pricing_note="Offline test ceiling, no provider call", **kwargs)

    def reopen(self):
        self.wf = Workflow(self.wf.path)
        return self.wf

    def asset(self, asset_id="mesh", stage="geometry"):
        path = self.base / f"{asset_id}.glb"
        path.write_bytes(b"original-" + asset_id.encode())
        self.wf.add_asset(asset_id, path, stage=stage)
        return path

    def evidence(self, name="review"):
        path = self.base / f"{name}.txt"
        path.write_text("Reviewer checked the actual asset at this revision.", encoding="utf-8")
        return path

    def test_initialization_is_persistent_and_summary_never_certifies_runtime(self):
        self.assertTrue(self.wf.path.is_file())
        self.assertEqual(self.wf.path.name, "workflow.json")
        before = self.wf.path.read_bytes()
        self.assertIsInstance(self.reopen().summary(), dict)
        self.assertEqual(self.wf.path.read_bytes(), before)
        self.assertEqual(self.client.submissions, [])

    def test_status_command_needs_only_manifest_and_stays_offline(self):
        before = self.wf.path.read_bytes()
        with patch("tripo_api.TripoClient", side_effect=AssertionError("Status must remain offline")), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            code = workflow_module.main(["status", str(self.wf.path)])
        self.assertEqual(code, 0)
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["workflow"], str(self.wf.path))
        self.assertEqual(summary["jobs"], [])
        self.assertEqual(self.wf.path.read_bytes(), before)

    def test_rejected_submission_keeps_safe_diagnosis_in_cli_and_offline_status(self):
        self.plan()
        self.client.submit_error = workflow_module.APIError(
            "private provider body https://private.example/?token=secret", status=422, code=2008)
        with patch("tripo_api.TripoClient", return_value=self.client), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            code = workflow_module.main(["submit", str(self.wf.path), "--job", "draft"])
        self.assertEqual(code, 3)
        result = json.loads(output.getvalue())
        diagnostic = result["last_error"]
        self.assertEqual((diagnostic["stage"], diagnostic["operation"], diagnostic["type"]),
                         ("submit", "text_to_model", "APIError"))
        self.assertEqual((diagnostic["http_status"], diagnostic["provider_code"]), (422, 2008))
        self.assertIsNotNone(workflow_module.datetime.fromisoformat(diagnostic["observed_at"]).tzinfo)
        self.assertEqual(self.reopen().read_json()["jobs"]["draft"]["last_error"], diagnostic)
        with patch("tripo_api.TripoClient", side_effect=AssertionError("Status must remain offline")), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(workflow_module.main(["status", str(self.wf.path)]), 0)
        self.assertEqual(json.loads(output.getvalue())["jobs"][0]["last_error"], diagnostic)
        self.assertEqual(len(self.client.submissions), 1)
        for content in (self.wf.path.read_text(), output.getvalue(), json.dumps(result)):
            self.assertNotIn("private provider body", content)
            self.assertNotIn("token=secret", content)

    def test_failed_task_without_later_detail_keeps_the_previous_diagnosis(self):
        self.plan()
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"].update({"status": "failed", "error": {"code": 3004}})
        diagnostic = self.wf.resume("draft", self.client, download=False)["last_error"]
        self.client.tasks["task_1"].pop("error")
        result = self.reopen().resume("draft", self.client, download=False)
        self.assertEqual(result["last_error"], diagnostic)
        self.assertEqual(result["status"], "failed")

    def test_failed_task_uninformative_errors_keep_the_original_diagnosis_and_timestamp(self):
        self.plan()
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"].update({"status": "failed", "error": {"code": 3004}})
        with patch.object(workflow_module, "now", return_value="2026-10-12T00:00:00+00:00"):
            diagnostic = self.wf.resume("draft", self.client, download=False)["last_error"]
        for error in ({}, "generic failure", {"message": "generic failure"},
                      {"code": "3004", "status": True}, {"code": 3004}):
            with self.subTest(error=error), \
                    patch.object(workflow_module, "now", return_value="2026-10-12T01:00:00+00:00"):
                self.client.tasks["task_1"]["error"] = error
                result = self.reopen().resume("draft", self.client, download=False)
                self.assertEqual(result["last_error"], diagnostic)

    def test_failed_task_new_safe_metadata_updates_the_diagnosis_and_timestamp(self):
        self.plan()
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"].update({"status": "failed", "error": {"code": 3004}})
        with patch.object(workflow_module, "now", return_value="2026-10-12T00:00:00+00:00"):
            self.wf.resume("draft", self.client, download=False)
        self.client.tasks["task_1"]["error"] = {"code": 3005, "message": "private failure text"}
        with patch.object(workflow_module, "now", return_value="2026-10-12T01:00:00+00:00"):
            result = self.reopen().resume("draft", self.client, download=False)
        self.assertEqual(result["last_error"]["provider_code"], 3005)
        self.assertEqual(result["last_error"]["observed_at"], "2026-10-12T01:00:00+00:00")
        self.assertNotIn("private failure text", self.wf.path.read_text())
        self.assertEqual(len(self.client.submissions), 1)

    def test_diagnostics_never_copy_non_numeric_error_metadata_or_provider_text(self):
        for index, error in enumerate([
            {"status": True, "code": False, "message": "private prompt"},
            {"status": "private token", "code": "https://private.example/?token=secret"},
            {"status": 999, "code": 1.5}, "private task failure",
        ]):
            with self.subTest(error=index):
                job_id = f"failure-{index}"
                self.plan(job_id, "1")
                task_id = self.wf.submit(job_id, self.client)["task_id"]
                self.client.tasks[task_id].update({"status": "failed", "error": error})
                diagnostic = self.wf.resume(job_id, self.client, download=False)["last_error"]
                self.assertIsNone(diagnostic["http_status"])
                self.assertIsNone(diagnostic["provider_code"])
        saved = self.reopen().path.read_text()
        for secret in ("private prompt", "private token", "private.example", "private task failure"):
            self.assertNotIn(secret, saved)

    def test_arbitrary_exception_message_and_class_name_are_not_recorded_or_echoed(self):
        self.plan()
        private_exception = type("PrivatePromptInClassName", (RuntimeError,), {})
        self.client.submit_error = private_exception("secret prompt https://private.example/?token=secret")
        with self.assertRaises(ValueError) as raised:
            self.wf.submit("draft", self.client)
        job = self.reopen().read_json()["jobs"]["draft"]
        self.assertEqual(job["status"], "unknown_submission")
        self.assertEqual(job["last_error"]["type"], "UnexpectedError")
        for content in (self.wf.path.read_text(), str(raised.exception)):
            for secret in ("PrivatePromptInClassName", "secret prompt", "private.example", "token=secret"):
                self.assertNotIn(secret, content)
        self.assertEqual(len(self.client.submissions), 1)

    def test_uncertain_upload_keeps_diagnosis_and_does_not_repeat_upload(self):
        self.asset()
        with patch.object(self.client, "upload_file", side_effect=workflow_module.SubmissionUncertain(
                "private upload body", status=503)) as upload:
            with self.assertRaises(workflow_module.SubmissionUncertain):
                self.wf.upload("mesh", self.client)
            with self.assertRaises(ValueError):
                self.reopen().upload("mesh", self.client)
        self.assertEqual(upload.call_count, 1)
        recorded = self.wf.read_json()["artifacts"]["mesh"]["upload"]
        self.assertEqual(recorded["status"], "unknown")
        self.assertEqual(recorded["last_error"]["http_status"], 503)

    def test_uncertain_diagnosis_survives_reopen_without_releasing_budget_or_retrying(self):
        self.plan()
        self.client.submit_error = workflow_module.SubmissionUncertain("private token", status=503)
        result = self.wf.submit("draft", self.client)
        self.assertEqual(result["status"], "unknown_submission")
        self.assertEqual(result["last_error"]["type"], "SubmissionUncertain")
        self.assertEqual(result["last_error"]["http_status"], 503)
        self.assertEqual(self.reopen().resume("draft", self.client, download=False)["last_error"],
                         result["last_error"])
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        self.assertEqual(self.wf.summary()["budget"]["committed_credits"], "6.00")
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(self.client.lookups, [])

    def test_failed_task_keeps_only_safe_provider_error_after_reopen(self):
        self.plan()
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"].update({"status": "failed", "error": {
            "code": 3004, "message": "private prompt", "url": "https://private.example/?signature=secret",
            "token": "secret-token"}})
        result = self.wf.resume("draft", self.client, download=False)
        diagnostic = result["last_error"]
        self.assertEqual((diagnostic["stage"], diagnostic["operation"], diagnostic["type"]),
                         ("task", "text_to_model", "ProviderTaskError"))
        self.assertEqual(diagnostic["provider_code"], 3004)
        self.assertEqual(self.reopen().summary()["jobs"][0]["last_error"], diagnostic)
        self.assertEqual(self.wf.summary()["budget"]["committed_credits"], "6.00")
        for content in (self.wf.path.read_text(), json.dumps(result)):
            for secret in ("private prompt", "private.example", "secret-token", "signature=secret"):
                self.assertNotIn(secret, content)
        self.assertEqual(len(self.client.submissions), 1)

    def test_upload_failure_diagnosis_is_durable_and_safe(self):
        self.asset()
        with patch.object(self.client, "upload_file", side_effect=workflow_module.APIError(
                "private upload token", status=413, code=2012)), self.assertRaises(workflow_module.APIError) as raised:
            self.wf.upload("mesh", self.client)
        diagnostic = self.reopen().read_json()["artifacts"]["mesh"]["upload"]["last_error"]
        self.assertEqual((diagnostic["stage"], diagnostic["operation"]), ("upload", "upload_file"))
        self.assertEqual((diagnostic["http_status"], diagnostic["provider_code"]), (413, 2012))
        self.assertEqual(self.wf.summary()["artifacts"][0]["upload"]["last_error"], diagnostic)
        self.assertNotIn("private upload token", str(raised.exception))
        self.assertNotIn("private upload token", self.wf.path.read_text())

    def test_poll_failure_keeps_diagnosis_and_known_task_without_new_post(self):
        self.plan()
        self.wf.submit("draft", self.client)
        with patch.object(self.client, "get_task", side_effect=workflow_module.APIError(
                "private poll token", status=429)), self.assertRaises(workflow_module.APIError) as raised:
            self.wf.resume("draft", self.client, download=False)
        saved = self.reopen().read_json()["jobs"]["draft"]
        self.assertEqual((saved["status"], saved["task_id"]), ("submitted", "task_1"))
        self.assertEqual(saved["last_error"]["stage"], "poll")
        self.assertEqual(saved["last_error"]["http_status"], 429)
        self.assertNotIn("private poll token", str(raised.exception))
        self.assertEqual(self.wf.summary()["budget"]["committed_credits"], "6.00")
        self.wf.resume("draft", self.client, download=False)
        self.assertEqual(len(self.client.submissions), 1)

    def test_legacy_manifest_without_diagnostics_remains_valid_and_status_does_not_rewrite_it(self):
        self.plan()
        legacy = self.wf.read_json()
        legacy["jobs"]["draft"].pop("last_error", None)
        self.wf._save(legacy)
        before = self.wf.path.read_bytes()
        self.assertIsNone(self.reopen().summary()["jobs"][0].get("last_error"))
        self.assertEqual(self.wf.path.read_bytes(), before)
        self.assertEqual(self.wf.submit("draft", self.client)["status"], "submitted")

    def test_invalid_budget_cannot_initialize(self):
        for number, value in enumerate(["-1", "NaN", "Infinity", "", True]):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                Workflow.initialize(self.base / f"bad-{number}", "Bad", value)

    def test_job_ceiling_and_pricing_note_required_before_submit(self):
        for number, value in enumerate(["-1", "NaN", "Infinity", True, "11"]):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.plan(f"bad-{number}", value)
        with self.assertRaises(ValueError):
            self.wf.plan_job("no-price", "text_to_model", {"prompt": "Test"}, "1")
        self.assertEqual(self.client.submissions, [])

    def test_budget_reserves_before_post_and_survives_restart(self):
        self.plan("first", "6")
        self.plan("second", "6")
        self.wf.submit("first", self.client)
        self.reopen()
        with self.assertRaises(ValueError):
            self.wf.submit("second", self.client)
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(self.wf.read_json()["jobs"]["first"]["task_id"], "task_1")

    def test_submission_timeout_does_not_create_another_paid_job(self):
        self.plan()
        self.client.submit_error = TimeoutError("Simulated lost response")
        try:
            self.wf.submit("draft", self.client)
        except ValueError:
            pass
        self.reopen()
        self.assertIn(self.wf.read_json()["jobs"]["draft"]["status"], {"unknown_submission", "submitting"})
        self.client.submit_error = None
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        self.wf.resume("draft", self.client, download=False)
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(self.client.lookups, [])

    def test_hard_interruption_leaves_reservation_and_prevents_duplicate_post(self):
        self.plan()
        self.client.submit_error = KeyboardInterrupt()
        with self.assertRaises((KeyboardInterrupt, ValueError)):
            self.wf.submit("draft", self.client)
        self.reopen()
        self.client.submit_error = None
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        self.assertEqual(len(self.client.submissions), 1)
        self.plan("extra", "5")
        with self.assertRaises(ValueError):
            self.wf.submit("extra", self.client)
        self.assertEqual(len(self.client.submissions), 1)

    def test_resume_known_job_only_queries_and_uses_verified_terminal_charge(self):
        self.plan("first", "6")
        self.wf.submit("first", self.client)
        self.client.tasks["task_1"] = {"task_id": "task_1", "status": "success", "progress": 100, "credits_consumed": "3"}
        self.reopen().resume("first", self.client, download=False)
        self.assertEqual(self.client.lookups, ["task_1"])
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(Decimal(self.wf.read_json()["jobs"]["first"]["charged_credits"]), Decimal("3"))
        self.plan("second", "7")
        self.wf.submit("second", self.client)
        self.assertEqual(len(self.client.submissions), 2)

    def test_failed_job_without_verified_cost_retains_its_credit_reservation(self):
        self.plan("first", "6")
        self.wf.submit("first", self.client)
        self.client.tasks["task_1"] = {"task_id": "task_1", "status": "failed", "progress": 0}
        self.wf.resume("first", self.client, download=False)
        self.plan("second", "5")
        with self.assertRaises(ValueError):
            self.reopen().submit("second", self.client)
        self.assertIsNone(self.wf.read_json()["jobs"]["first"]["charged_credits"])
        self.assertEqual(len(self.client.submissions), 1)

    def test_provider_cost_over_ceiling_freezes_new_paid_jobs(self):
        self.plan("first", "2")
        self.wf.submit("first", self.client)
        self.client.tasks["task_1"] = {"task_id": "task_1", "status": "success", "progress": 100, "credits_consumed": "3"}
        self.wf.resume("first", self.client, download=False)
        self.plan("second", "1")
        with self.assertRaises(ValueError):
            self.reopen().submit("second", self.client)
        self.assertEqual(len(self.client.submissions), 1)

    def test_changed_input_is_rejected_before_any_paid_post(self):
        path = self.asset("reference", stage="input")
        self.plan(input_ids=["reference"])
        path.write_bytes(b"changed after plan")
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        self.assertEqual(self.client.submissions, [])

    def test_missing_evidence_cannot_make_gate_pass(self):
        self.asset()
        with self.assertRaises(ValueError):
            self.wf.record_gate("mesh", "fidelity", "pass", note="I looked")
        with self.assertRaises((ValueError, OSError)):
            self.wf.record_gate("mesh", "fidelity", "pass", [self.base / "missing.txt"], note="I looked")
        with self.assertRaises(ValueError):
            self.wf.record_gate("mesh", "fidelity", "pass", [self.evidence()], note="")

    def test_url_and_secret_payloads_are_not_recorded(self):
        for number, payload in enumerate([
            {"prompt": "Test", "api_key": "private-key"},
            {"prompt": "Test", "source": "https://example.org/asset?token=secret"},
        ]):
            with self.subTest(payload=number), self.assertRaises(ValueError):
                self.wf.plan_job(f"unsafe-{number}", "text_to_model", payload, "1", pricing_note="Offline")
        content = self.wf.path.read_text(encoding="utf-8")
        self.assertNotIn("private-key", content)
        self.assertNotIn("token=secret", content)

    def test_resume_download_is_reused_by_hash_and_signed_urls_are_not_persisted(self):
        self.plan()
        self.wf.submit("draft", self.client)
        signed_url = "https://models.example.org/model.glb?X-Amz-Signature=secret_download_signature"
        self.client.tasks["task_1"] = {
            "task_id": "task_1", "status": "success", "progress": 100,
            "credits_consumed": "4", "output": {"model_url": signed_url},
        }
        self.wf.resume("draft", self.client)
        self.reopen().resume("draft", self.client)
        self.assertEqual(len(self.client.downloads), 1)
        self.assertNotIn(signed_url, self.wf.path.read_text(encoding="utf-8"))
        self.assertNotIn("secret_download_signature", self.wf.path.read_text(encoding="utf-8"))
        self.assertEqual(len(self.client.submissions), 1)

    def test_uncertain_submission_blocks_other_paid_jobs_even_with_remaining_budget(self):
        self.plan("uncertain", "1")
        self.plan("other", "1")
        self.client.submit_error = TimeoutError("Simulated lost response")
        with self.assertRaises(ValueError):
            self.wf.submit("uncertain", self.client)
        self.client.submit_error = None
        with self.assertRaises(ValueError):
            self.reopen().submit("other", self.client)
        self.assertEqual(len(self.client.submissions), 1)

    def test_manual_recovery_resumes_only_the_evidenced_provider_job(self):
        self.plan()
        self.client.submit_error = TimeoutError("Simulated lost response")
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        self.reopen().recover("draft", "task_recovered", "Task ID found in provider task history for this exact request")
        self.client.submit_error = None
        self.client.tasks["task_recovered"] = {"task_id": "task_recovered", "status": "running", "progress": 50}
        self.wf.resume("draft", self.client, download=False)
        self.assertEqual(self.client.lookups, ["task_recovered"])
        self.assertEqual(len(self.client.submissions), 1)
        with self.assertRaises(ValueError):
            self.wf.recover("draft", "task_different", "Do not rebind an already known task")

    def test_concurrent_submission_cannot_race_the_credit_reservation(self):
        self.plan("first", "6")
        self.plan("second", "6")
        entered = threading.Event()
        release = threading.Event()
        original = self.client.submit

        def blocked_submit(operation, payload):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test synchronization timeout")
            return original(operation, payload)

        self.client.submit = blocked_submit
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.wf.submit, "first", self.client)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(ValueError):
                    Workflow(self.wf.path).submit("second", self.client)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)["task_id"], "task_1")
        self.assertEqual(len(self.client.submissions), 1)

    def test_image_job_binds_only_the_uploaded_approved_revision(self):
        self.asset("front", stage="input")
        self.wf.plan_job("image", "image_to_model", {"input": {"asset_id": "front"}, "model": "v3.1-20260211"},
                         "2", input_ids=["front"], pricing_note="Offline test ceiling")
        with self.assertRaises(ValueError):
            self.wf.upload("front", self.client)
        self.assertEqual(self.client.uploads, [])
        self.wf.record_gate("front", "input", "pass", [self.evidence("input")], "One isolated approved character")
        with self.assertRaises(ValueError):
            self.wf.submit("image", self.client)
        self.wf.upload("front", self.client)
        self.wf.upload("front", self.client)
        self.wf.submit("image", self.client)
        self.assertEqual(len(self.client.uploads), 1)
        self.assertEqual(self.client.submissions[0][1]["input"], {"file_token": "file_1"})

    def test_rig_requires_current_fidelity_and_geometry_evidence(self):
        self.asset()
        self.wf.upload("mesh", self.client)
        self.wf.plan_job("rig", "rig", {"input": {"asset_id": "mesh"}}, "2", input_ids=["mesh"], pricing_note="Offline")
        with self.assertRaises(ValueError):
            self.wf.submit("rig", self.client)
        self.wf.record_gate("mesh", "fidelity", "pass", [self.evidence("fidelity")], "Reference compared")
        with self.assertRaises(ValueError):
            self.wf.submit("rig", self.client)
        self.wf.record_gate("mesh", "geometry", "pass", [self.evidence("geometry")], "Final mesh checked")
        self.wf.submit("rig", self.client)
        self.assertEqual(len(self.client.submissions), 1)

    def test_changed_gate_evidence_is_not_reused_to_authorize_a_paid_job(self):
        self.asset()
        self.wf.upload("mesh", self.client)
        fidelity = self.evidence("fidelity")
        self.wf.record_gate("mesh", "fidelity", "pass", [fidelity], "Reference compared")
        self.wf.record_gate("mesh", "geometry", "pass", [self.evidence("geometry")], "Final mesh checked")
        self.wf.plan_job("rig", "rig", {"input": {"asset_id": "mesh"}}, "2", input_ids=["mesh"], pricing_note="Offline")
        fidelity.write_text("Changed evidence after approval", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.wf.submit("rig", self.client)
        self.assertEqual(self.client.submissions, [])

    def test_changed_parent_revision_invalidates_a_derived_model(self):
        original = self.asset("source")
        child = self.base / "optimized.glb"
        child.write_bytes(b"derived model")
        self.wf.add_asset("optimized", child, stage="geometry", parents=["source"])
        self.wf.upload("optimized", self.client)
        for gate in ("fidelity", "geometry"):
            self.wf.record_gate("optimized", gate, "pass", [self.evidence(gate)], "Reviewed derived revision")
        self.wf.plan_job("rig", "rig", {"input": {"asset_id": "optimized"}}, "2", input_ids=["optimized"], pricing_note="Offline")
        original.write_bytes(b"changed parent model")
        with self.assertRaises(ValueError):
            self.wf.submit("rig", self.client)
        self.assertEqual(self.client.submissions, [])

    def test_retarget_requires_rig_deformation_evidence(self):
        self.asset("rigged", stage="rig")
        self.wf.upload("rigged", self.client)
        for gate in ("fidelity", "geometry"):
            self.wf.record_gate("rigged", gate, "pass", [self.evidence(gate)], "Reviewed current revision")
        self.wf.plan_job("retarget", "retarget", {"input": {"asset_id": "rigged"}}, "2", input_ids=["rigged"], pricing_note="Offline")
        with self.assertRaises(ValueError):
            self.wf.submit("retarget", self.client)
        self.wf.record_gate("rigged", "rig", "pass", [self.evidence("rig")], "Actual pose extremes reviewed")
        self.wf.submit("retarget", self.client)
        self.assertEqual(len(self.client.submissions), 1)

    def test_untracked_primary_input_cannot_borrow_unrelated_asset_provenance(self):
        self.asset()
        self.wf.upload("mesh", self.client)
        self.wf.plan_job("texture", "texture", {
            "input": "file_untracked", "unused": {"asset_id": "mesh"}, "model": "v3.0-20250812"
        }, "2", input_ids=["mesh"], pricing_note="Offline")
        with self.assertRaises(ValueError):
            self.wf.submit("texture", self.client)
        self.assertEqual(self.client.submissions, [])

    def test_recovery_rejects_invalid_provider_task_id_before_binding(self):
        self.plan()
        self.client.submit_error = TimeoutError("Simulated lost response")
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        with self.assertRaises(ValueError):
            self.wf.recover("draft", "typo", "Wrong identifier format")
        self.assertIsNone(self.wf.read_json()["jobs"]["draft"]["task_id"])

    def test_provider_charge_cannot_regress_after_a_later_query(self):
        self.plan("first", "6")
        self.wf.submit("first", self.client)
        self.client.tasks["task_1"] = {"task_id": "task_1", "status": "success", "progress": 100, "credits_consumed": "5"}
        self.wf.resume("first", self.client, download=False)
        self.client.tasks["task_1"]["credits_consumed"] = "0"
        self.reopen().resume("first", self.client, download=False)
        self.assertEqual(Decimal(self.wf.read_json()["jobs"]["first"]["charged_credits"]), Decimal("5"))

    def test_changed_download_is_not_overwritten_or_silently_reused(self):
        self.plan()
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"] = {
            "task_id": "task_1", "status": "success", "progress": 100,
            "credits_consumed": "4", "output": {"model_url": "https://models.example.org/model.glb"},
        }
        self.wf.resume("draft", self.client)
        asset = self.wf.read_json()["artifacts"]["draft-model"]
        Path(asset["path"]).write_bytes(b"edited after download")
        with self.assertRaises(ValueError):
            self.reopen().resume("draft", self.client)
        self.assertEqual(len(self.client.downloads), 1)
        self.assertEqual(Path(asset["path"]).read_bytes(), b"edited after download")

    def test_download_commit_crash_is_resumed_by_explicit_output_adoption(self):
        self.plan()
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"] = {
            "task_id": "task_1", "status": "success", "progress": 100,
            "credits_consumed": "4", "output": {"model_url": "https://models.example.org/model.glb"},
        }
        original = self.client.download

        def commit_then_crash(url, destination):
            original(url, destination)
            raise RuntimeError("Simulated interruption after file commit")

        self.client.download = commit_then_crash
        with self.assertRaises(RuntimeError):
            self.wf.resume("draft", self.client)
        job = self.reopen().read_json()["jobs"]["draft"]
        self.assertEqual(job["status"], "success")
        self.assertEqual(Decimal(job["charged_credits"]), Decimal("4"))
        self.assertEqual(job["output_assets"], [])
        with self.assertRaises(ValueError):
            self.wf.resume("draft", self.client)
        output = self.wf.path.parent / "artifacts" / "draft-model.glb"
        self.wf.adopt_output("draft", output, "Recovered the fully committed output from this exact task")
        self.reopen().resume("draft", self.client)
        self.assertEqual(self.wf.read_json()["jobs"]["draft"]["output_assets"], ["draft-model"])
        self.assertEqual(len(self.client.downloads), 1)
        self.assertEqual(len(self.client.submissions), 1)

    def test_workflow_to_real_adapter_http_shapes_and_download_offline(self):
        from tripo_api import TripoClient

        class Response(io.BytesIO):
            status = 200

            def __init__(self, content):
                super().__init__(content)
                self.headers = {"Content-Length": str(len(content))}

        requests = []
        signed = "https://assets.example.org/avatar.glb?signature=integration_download_secret"

        class Opener:
            def open(_self, request, timeout):
                body = json.loads(request.data) if request.data is not None else None
                requests.append((request.get_method(), request.full_url, body))
                if request.full_url.endswith("/generation/text-to-model"):
                    data = {"task_id": "task_generated"}
                elif request.full_url.endswith("/tasks/task_generated"):
                    data = {"task_id": "task_generated", "status": "success", "progress": 100,
                            "credits_consumed": "3", "output": {"model_url": signed}}
                elif request.full_url.endswith("/animations/rig"):
                    data = {"task_id": "task_rigged"}
                else:
                    raise AssertionError("Unexpected HTTP request in offline integration")
                return Response(json.dumps({"code": 0, "data": data}).encode())

        client = TripoClient(api_key="offline-test-key")
        client._opener = Opener()
        client._open_asset = lambda url: Response(b"offline actual transport asset")
        self.plan("generated", "5")
        with patch("socket.getaddrinfo", side_effect=AssertionError("Real DNS forbidden")), \
                patch("socket.create_connection", side_effect=AssertionError("Real network forbidden")):
            self.wf.submit("generated", client)
            self.reopen().resume("generated", client)
            for gate in ("fidelity", "geometry"):
                self.wf.record_gate("generated-model", gate, "pass", [self.evidence(gate)], "Reviewed downloaded model")
            self.wf.plan_job("rigged", "rig", {"input": {"task_id": "task_generated"}}, "2",
                             input_ids=["generated-model"], parent_job="generated", pricing_note="Offline test ceiling")
            self.wf.submit("rigged", client)
        self.assertEqual([method for method, _, _ in requests], ["POST", "GET", "POST"])
        self.assertEqual(requests[-1][2]["input"], "task_generated")
        self.assertTrue(Path(self.wf.read_json()["artifacts"]["generated-model"]["path"]).is_file())
        saved = self.wf.path.read_text(encoding="utf-8")
        self.assertNotIn("offline-test-key", saved)
        self.assertNotIn("integration_download_secret", saved)

    def test_cost_reconciliation_requires_receipt_note_and_never_reduces_observed_charge(self):
        self.plan()
        self.client.submit_error = TimeoutError("Simulated lost response")
        with self.assertRaises(ValueError):
            self.wf.submit("draft", self.client)
        receipt = self.evidence("provider-receipt")
        with self.assertRaises(ValueError):
            self.wf.reconcile_cost("draft", "4", [], "Provider history checked")
        with self.assertRaises(ValueError):
            self.wf.reconcile_cost("draft", "4", [receipt], "")
        with self.assertRaises((ValueError, OSError)):
            self.wf.reconcile_cost("draft", "4", [self.base / "absent-receipt.txt"], "Provider history checked")
        self.wf.reconcile_cost("draft", "4", [receipt], "Provider history confirms the settled charge")
        self.reopen().reconcile_cost("draft", "0", [receipt], "A later observation cannot erase a recorded charge")
        self.assertEqual(Decimal(self.wf.read_json()["jobs"]["draft"]["charged_credits"]), Decimal("4"))
        self.wf.reconcile_cost("draft", "9", [receipt], "Provider confirms charge above the reserved ceiling")
        self.assertTrue(self.wf.read_json()["budget"]["blocked"])

    def test_verified_zero_cost_releases_unknown_reservation_without_resubmitting_original(self):
        self.plan("uncertain", "6")
        self.plan("replacement", "10")
        self.client.submit_error = TimeoutError("Simulated lost response")
        with self.assertRaises(ValueError):
            self.wf.submit("uncertain", self.client)
        self.client.submit_error = None
        with self.assertRaises(ValueError):
            self.wf.submit("replacement", self.client)
        self.reopen().reconcile_cost("uncertain", "0", [self.evidence("zero-receipt")],
                                   "Provider history verifies no task or charge for this exact request")
        self.assertEqual(self.wf.read_json()["jobs"]["uncertain"]["status"], "reconciled")
        self.assertEqual(Decimal(self.wf.summary()["budget"]["remaining_credits"]), Decimal("10"))
        with self.assertRaises(ValueError):
            self.wf.submit("uncertain", self.client)
        self.wf.submit("replacement", self.client)
        self.assertEqual(len(self.client.submissions), 2)

    def test_unsubmitted_and_running_jobs_cannot_be_settled_by_receipt(self):
        self.plan()
        receipt = self.evidence("receipt")
        with self.assertRaises(ValueError):
            self.wf.reconcile_cost("draft", "0", [receipt], "Premature settlement")
        self.wf.submit("draft", self.client)
        self.client.tasks["task_1"] = {"task_id": "task_1", "status": "running", "progress": 10}
        self.wf.resume("draft", self.client, download=False)
        with self.assertRaises(ValueError):
            self.reopen().reconcile_cost("draft", "0", [receipt], "Still running")
        self.assertIsNone(self.wf.read_json()["jobs"]["draft"]["charged_credits"])
        self.assertEqual(Decimal(self.wf.summary()["budget"]["committed_credits"]), Decimal("6"))

    def test_summary_keeps_recorded_gate_but_marks_changed_asset_or_evidence_unassessed(self):
        mesh = self.asset()
        evidence = self.evidence()
        self.wf.record_gate("mesh", "fidelity", "pass", [evidence], "Original revision compared")
        before = self.wf.path.read_bytes()
        self.assertEqual(self.wf.summary()["artifacts"][0]["gates"]["fidelity"]["status"], "pass")
        evidence.write_text("Changed reviewer evidence", encoding="utf-8")
        gate = self.wf.summary()["artifacts"][0]["gates"]["fidelity"]
        self.assertEqual((gate["recorded_status"], gate["status"]), ("pass", "not_assessed"))
        self.assertEqual(self.wf.path.read_bytes(), before)
        self.wf.record_gate("mesh", "fidelity", "pass", [evidence], "New evidence compared")
        mesh.write_bytes(b"changed source mesh")
        artifact = self.wf.summary()["artifacts"][0]
        self.assertEqual(artifact["integrity"], "changed_or_missing")
        self.assertEqual((artifact["gates"]["fidelity"]["recorded_status"], artifact["gates"]["fidelity"]["status"]),
                         ("pass", "not_assessed"))


if __name__ == "__main__":
    unittest.main()
