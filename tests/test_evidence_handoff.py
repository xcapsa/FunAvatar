"""Export dependency evidence must become stale when a registered sidecar changes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts"
sys.path.insert(0, str(SCRIPTS))
from export_bundle import inspect_export
from tripo_workflow import Workflow


class EvidenceHandoffTests(unittest.TestCase):
    def test_sidecar_revision_invalidates_export_gate_without_changing_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "avatar.gltf"
            texture = root / "face.png"
            texture.write_bytes(b"texture bytes; image decoding is outside this check")
            model.write_text(json.dumps({"asset": {"version": "2.0"},
                                         "images": [{"uri": "face.png"}]}))
            manifest = inspect_export(model, root=root)
            self.assertEqual((manifest["status"], manifest["scope"]),
                             ("complete", "file_dependencies_only"))
            evidence = root / "export-check.json"
            evidence.write_text(json.dumps(manifest))

            workflow = Workflow.initialize(root / "run", "Offline handoff", "0")
            parents = []
            for index, item in enumerate(manifest["files"]):
                if "model" in item["roles"]:
                    continue
                identifier = f"sidecar-{index}"
                workflow.add_asset(identifier, root / item["path"], stage="surface")
                parents.append(identifier)
            workflow.add_asset("unity-export", model, stage="export", parents=parents)
            workflow.record_gate("unity-export", "export", "pass", [evidence],
                                 "File dependencies inspected; native import and runtime are separate.")
            before = next(a for a in workflow.summary()["artifacts"] if a["id"] == "unity-export")
            self.assertEqual(before["gates"]["export"]["status"], "pass")

            texture.write_bytes(b"changed texture, unchanged model file")
            current = inspect_export(model, root=root)
            self.assertEqual(current["source"]["sha256"], manifest["source"]["sha256"])
            self.assertNotEqual(current["bundle_sha256"], manifest["bundle_sha256"])
            after = next(a for a in Workflow(workflow.path).summary()["artifacts"]
                         if a["id"] == "unity-export")
            self.assertEqual(after["integrity"], "changed_or_missing")
            self.assertEqual(after["gates"]["export"]["recorded_status"], "pass")
            self.assertEqual(after["gates"]["export"]["status"], "not_assessed")
            self.assertEqual(workflow.summary()["budget"]["committed_credits"], "0.00")
