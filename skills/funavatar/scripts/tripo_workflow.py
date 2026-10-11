#!/usr/bin/env python3
"""FunAvatar 3D ledger and explicit Tripo operations. Python 3.10+, standard library.

Offline commands never contact Tripo. submit/upload/resume are explicit online
actions; no command automatically creates a replacement for an uncertain job.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid
from urllib.parse import urlsplit
from tripo_api import APIError, SubmissionUncertain, OPERATIONS, TASK_ID, FILE_TOKEN

STAGES = ("input", "generation", "geometry", "surface", "rig", "export", "report", "evidence")
GATES = ("input", "fidelity", "geometry", "surface", "rig", "export", "sdk_pc", "sdk_android", "client_pc", "client_android")
TERMINAL = {"success", "failed", "cancelled"}
UNSENT = {"planned", "rejected"}
KINDS = set(OPERATIONS)
GENERATORS = {"text_to_model", "image_to_model", "multiview_to_model"}
OUTPUT_STAGES = {"text_to_model": "generation", "image_to_model": "generation", "multiview_to_model": "generation", "retopology": "geometry", "segment": "geometry", "complete": "geometry", "texture": "surface", "rig": "rig", "retarget": "rig", "convert": "export"}
MAX_JSON = 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


class WorkflowError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise WorkflowError("Use a short identifier containing letters, digits, hyphens or underscores")
    return value


def credits(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise WorkflowError("Credits must be a nonnegative number with at most two decimal places")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("1000000000") or amount != amount.quantize(Decimal("0.01")):
            raise WorkflowError("Invalid credit amount")
    except (InvalidOperation, ValueError) as exc:
        raise WorkflowError("Invalid credit amount") from exc
    return amount


def amount(value):
    return format(credits(value), ".2f")


def text(value, label="note"):
    if not isinstance(value, str) or not value.strip() or len(value) > 8000 or "\0" in value:
        raise WorkflowError(f"{label} must contain 1 to 8000 characters")
    return value.strip()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkflowError("Duplicate JSON key")
        result[key] = value
    return result


def json_file(path):
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise WorkflowError("Expected a bounded regular JSON file, without a symlink")
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_JSON:
            raise WorkflowError("JSON file is too large")
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(WorkflowError("Nonfinite JSON number")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise WorkflowError("Invalid UTF-8 JSON") from exc


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_record(filename):
    path = Path(filename).expanduser()
    if path.is_symlink():
        raise WorkflowError("Asset and evidence files must not be symlinks")
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise WorkflowError("Asset or evidence file is missing") from exc
    if not path.is_file():
        raise WorkflowError("Expected a regular asset or evidence file")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise WorkflowError("File changed while it was being measured")
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": after.st_size}


def _unchanged(record):
    actual = file_record(record["path"])
    if actual["sha256"] != record["sha256"] or actual["bytes"] != record["bytes"]:
        raise WorkflowError("A recorded file changed; register a new revision and repeat its dependent checks")


def _safe_payload(value, depth=0):
    if depth > 16:
        raise WorkflowError("Payload nesting is too deep")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or re.search(r"secret|password|authorization|api.?key|cookie|access.?token", key, re.I):
                raise WorkflowError("Credentials do not belong in a workflow payload")
            _safe_payload(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _safe_payload(item, depth + 1)
    elif isinstance(value, str):
        if re.search(r"https?://|tsk_", value, re.I):
            raise WorkflowError("Use local asset placeholders or task references; do not persist URLs or API keys in payloads")
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise WorkflowError("Payload must contain JSON values")
    if isinstance(value, float) and not Decimal(str(value)).is_finite():
        raise WorkflowError("Nonfinite payload number")


def _diagnostic(stage, operation, error):
    """Keep useful failure metadata without trusting provider/exception text."""
    status = code = None
    if stage == "task":
        error_type = "ProviderTaskError"
        if isinstance(error, dict):
            status, code = error.get("status"), error.get("code")
        elif type(error) is int:
            code = error
    else:
        error_type = next((name for cls, name in (
            (SubmissionUncertain, "SubmissionUncertain"), (APIError, "APIError"),
            (TimeoutError, "TimeoutError"), (OSError, "OSError"),
            (WorkflowError, "WorkflowError"), (KeyboardInterrupt, "KeyboardInterrupt"),
            (SystemExit, "SystemExit")) if isinstance(error, cls)), "UnexpectedError")
        if isinstance(error, APIError):
            status, code = error.status, error.code
    # bools, numeric strings and provider free text are not numeric evidence.
    status = status if type(status) is int and 100 <= status <= 599 else None
    code = code if type(code) is int else None
    details = [error_type]
    if status is not None:
        details.append(f"HTTP {status}")
    if code is not None:
        details.append(f"provider code {code}")
    return {"stage": stage, "operation": operation, "type": error_type,
            "http_status": status, "provider_code": code, "observed_at": now(),
            "message": f"Tripo {stage} error: {', '.join(details)}"}


def _safe_api_error(error, diagnostic):
    cls = SubmissionUncertain if isinstance(error, SubmissionUncertain) else APIError
    return cls(diagnostic["message"], status=diagnostic["http_status"], code=diagnostic["provider_code"])


class Workflow:
    def __init__(self, path):
        original = Path(path).expanduser().absolute()
        if original.is_symlink():
            raise WorkflowError("Workflow must not be a symlink")
        self.path = original.parent.resolve(strict=True) / original.name

    @classmethod
    def initialize(cls, out, name, budget_credits, target="both", region="global", references=()):
        if target not in ("pc", "android", "both") or region not in ("global", "china"):
            raise WorkflowError("Invalid target or API region")
        folder = Path(out).expanduser().absolute()
        folder.mkdir(parents=True, exist_ok=True)
        folder = folder.resolve(strict=True)
        workflow = cls(folder / "workflow.json")
        data = {"schema_version": 1, "kind": "funavatar_3d_workflow", "workflow_id": str(uuid.uuid4()),
                "name": text(name, "name"), "target": target, "region": region, "created_at": now(), "updated_at": now(),
                "budget": {"limit_credits": amount(budget_credits), "blocked": False}, "artifacts": {}, "jobs": {}}
        for index, path in enumerate(references, 1):
            asset_id = f"ref-{index}"
            data["artifacts"][asset_id] = {"id": asset_id, "stage": "input", **file_record(path), "parents": [], "gates": {}, "upload": None}
        with workflow._lock():
            workflow._save(data, new=True)
        return workflow

    @contextmanager
    def _lock(self):
        lock = self.path.with_name(self.path.name + ".lock")
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WorkflowError("Workflow is busy; resume after the current command finishes") from exc
            yield
        finally:
            os.close(fd)

    def _save(self, data, new=False):
        data["updated_at"] = now()
        raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        if len(raw) > MAX_JSON or self.path.is_symlink():
            raise WorkflowError("Unsafe or oversized workflow destination")
        fd, temporary = tempfile.mkstemp(prefix=".workflow-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if new:
                os.link(temporary, self.path)
            else:
                os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def read_json(self):
        data = json_file(self.path)
        if not isinstance(data, dict) or data.get("kind") != "funavatar_3d_workflow" or data.get("schema_version") != 1:
            raise WorkflowError("Not a supported FunAvatar 3D workflow")
        if not isinstance(data.get("jobs"), dict) or not isinstance(data.get("artifacts"), dict):
            raise WorkflowError("Invalid workflow collections")
        credits(data["budget"]["limit_credits"])
        return data

    def _asset(self, data, asset_id, ancestors=()):
        if asset_id in ancestors or len(ancestors) > 100:
            raise WorkflowError("Invalid or excessively deep asset lineage")
        if asset_id not in data["artifacts"]:
            raise WorkflowError("Unknown asset identifier")
        asset = data["artifacts"][asset_id]
        _unchanged(asset)
        for parent in asset["parents"]:
            self._asset(data, parent, (*ancestors, asset_id))
        return asset

    def _job(self, data, job_id):
        if job_id not in data["jobs"]:
            raise WorkflowError("Unknown job identifier")
        return data["jobs"][job_id]

    def _output_status(self, data, job):
        if not job["output_assets"]:
            return job.get("output_status", "not_available" if job["operation"] == "rig_check" else "not_downloaded")
        for asset_id in job["output_assets"]:
            asset = data["artifacts"].get(asset_id)
            if not asset or not Path(asset["path"]).exists():
                return "missing"
            try:
                self._asset(data, asset_id)
            except (OSError, WorkflowError):
                return "mismatch"
        return "materialized"

    @staticmethod
    def _committed(data):
        return sum((credits(job["charged_credits"]) if job.get("charged_credits") is not None
                    else credits(job["max_credits"]) if job["status"] not in UNSENT else Decimal(0)
                    for job in data["jobs"].values()), Decimal(0))

    def summary(self):
        data = self.read_json()
        committed = self._committed(data)
        artifacts = []
        for asset in data["artifacts"].values():
            try:
                self._asset(data, asset["id"])
                integrity = "unchanged"
            except (OSError, WorkflowError):
                integrity = "changed_or_missing"
            gates = {}
            for gate, result in asset["gates"].items():
                effective = result["status"]
                try:
                    if integrity != "unchanged" or result.get("target") != data["target"]:
                        raise WorkflowError("Stale gate")
                    for item in result["evidence"]:
                        _unchanged(item)
                except (OSError, WorkflowError):
                    effective = "not_assessed"
                gates[gate] = {**result, "recorded_status": result["status"], "status": effective}
            artifacts.append({"id": asset["id"], "stage": asset["stage"], "path": asset["path"],
                              "sha256": asset["sha256"], "integrity": integrity, "gates": gates,
                              "upload": {"status": asset["upload"].get("status"),
                                         "last_error": asset["upload"].get("last_error")}
                              if asset.get("upload") else None})
        return {"workflow": str(self.path), "name": data["name"], "target": data["target"], "region": data["region"],
                "budget": {**data["budget"], "committed_credits": amount(committed),
                           "remaining_credits": amount(max(Decimal(0), credits(data["budget"]["limit_credits"]) - committed)),
                           "scope": "local reservations and observed charges; no provider-side spending cap"},
                "jobs": [{"id": j["id"], "operation": j["operation"], "status": j["status"], "task_id": j["task_id"],
                          "max_credits": j["max_credits"], "charged_credits": j["charged_credits"], "output_assets": j["output_assets"],
                          "output_status": self._output_status(data, j),
                          "last_error": j.get("last_error")}
                         for j in data["jobs"].values()],
                "artifacts": artifacts,
                "runtime_status": "See revision-specific SDK/client evidence; job completion is not avatar certification"}

    def add_asset(self, asset_id, path, stage="input", parents=()):
        identifier(asset_id)
        if stage not in STAGES:
            raise WorkflowError("Unknown asset stage")
        record = file_record(path)
        with self._lock():
            data = self.read_json()
            if asset_id in data["artifacts"]:
                raise WorkflowError("Asset IDs are immutable; use a new revision ID")
            for parent in parents:
                self._asset(data, parent)
            asset = {"id": asset_id, "stage": stage, **record, "parents": list(parents), "gates": {}, "upload": None}
            data["artifacts"][asset_id] = asset
            self._save(data)
            return asset

    def record_gate(self, asset_id, gate, status, evidence_paths=(), note=""):
        if gate not in GATES or status not in ("pass", "needs_repair", "not_assessed"):
            raise WorkflowError("Invalid gate or gate status")
        if status != "not_assessed" and (not evidence_paths or not note.strip()):
            raise WorkflowError("An assessed gate needs actual evidence files and a note")
        evidence = [file_record(path) for path in evidence_paths]
        with self._lock():
            data = self.read_json()
            asset = self._asset(data, asset_id)
            asset["gates"][gate] = {"status": status, "asset_sha256": asset["sha256"], "target": data["target"],
                                    "evidence": evidence, "note": note.strip(), "checked_at": now()}
            asset.setdefault("gate_history", []).append({"gate": gate, **asset["gates"][gate]})
            self._save(data)
            return asset["gates"][gate]

    def _require_gate(self, asset, gate, target):
        result = asset["gates"].get(gate, {})
        if result.get("status") != "pass" or result.get("asset_sha256") != asset["sha256"] or result.get("target") != target:
            raise WorkflowError(f"Asset {asset['id']} needs a current {gate} gate before this operation")
        for item in result.get("evidence", []):
            _unchanged(item)

    def plan_job(self, job_id, operation, payload, max_credits, input_ids=(), parent_job=None, pricing_note=""):
        identifier(job_id)
        if operation not in KINDS or not isinstance(payload, dict):
            raise WorkflowError("Unknown operation or invalid payload")
        _safe_payload(payload)
        if "model_version" in payload or "original_model_task_id" in payload:
            raise WorkflowError("Use the v3 fields model/input, not legacy v2 request fields")
        if operation in GENERATORS | {"texture", "retopology"}:
            text(payload.get("model"), "explicit model/version")
        if operation == "text_to_model":
            text(payload.get("prompt"), "prompt")
        reservation = credits(max_credits)
        if reservation == 0 and operation != "rig_check":
            raise WorkflowError("A paid job needs a positive verified maximum credit reservation")
        pricing_note = text(pricing_note, "pricing_note (source, check date and ceiling rationale)")
        with self._lock():
            data = self.read_json()
            if job_id in data["jobs"]:
                raise WorkflowError("Job IDs are immutable; resume the existing job")
            if reservation > credits(data["budget"]["limit_credits"]):
                raise WorkflowError("Job ceiling exceeds the authorized workflow budget")
            inputs = {asset_id: self._asset(data, asset_id)["sha256"] for asset_id in input_ids}
            if parent_job is not None:
                parent = self._job(data, parent_job)
                if parent["status"] != "success" or not parent["task_id"]:
                    raise WorkflowError("Parent job must have a successful provider task")
                if not inputs or not set(parent["output_assets"]) & inputs.keys():
                    raise WorkflowError("Include the actual downloaded parent model as an input")
            job = {"id": job_id, "operation": operation, "payload": payload, "payload_sha256": fingerprint(payload),
                   "input_hashes": inputs, "parent_job": parent_job, "pricing_note": pricing_note,
                   "max_credits": amount(reservation), "charged_credits": None, "status": "planned", "task_id": None,
                   "output_assets": [], "created_at": now(), "events": []}
            data["jobs"][job_id] = job
            self._save(data)
            return job

    def upload(self, asset_id, client):
        with self._lock():
            data = self.read_json()
            asset = self._asset(data, asset_id)
            if asset["stage"] == "input":
                self._require_gate(asset, "input", data["target"])
            if asset.get("upload") and asset["upload"].get("status") != "rejected":
                if asset["upload"].get("file_token"):
                    return {"status": "already_uploaded", "asset": asset_id}
                raise WorkflowError("Prior upload is uncertain; inspect provider state before explicitly registering a new revision")
            asset["upload"] = {"status": "uploading", "started_at": now()}
            self._save(data)
            try:
                response = client.upload_file(asset["path"])
                token = response.get("file_token")
                if not isinstance(token, str) or not FILE_TOKEN.fullmatch(token):
                    raise WorkflowError("Upload did not return a valid file token")
                _unchanged(asset)
            except APIError as exc:
                asset["upload"]["status"] = "unknown" if isinstance(exc, SubmissionUncertain) else "rejected"
                asset["upload"]["last_error"] = _diagnostic("upload", "upload_file", exc)
                self._save(data)
                raise _safe_api_error(exc, asset["upload"]["last_error"]) from None
            except BaseException as exc:
                asset["upload"]["status"] = "unknown"
                asset["upload"]["last_error"] = _diagnostic("upload", "upload_file", exc)
                self._save(data)
                raise WorkflowError(asset["upload"]["last_error"]["message"] +
                                    "; upload outcome is unknown, no automatic retry") from None
            asset["upload"] = {"status": "uploaded", "file_token": token, "sha256": asset["sha256"], "uploaded_at": now()}
            self._save(data)
            return {"status": "uploaded", "asset": asset_id}

    def _request(self, data, job):
        assets = []
        for asset_id, digest in job["input_hashes"].items():
            asset = self._asset(data, asset_id)
            if digest != asset["sha256"]:
                raise WorkflowError("Job inputs no longer match the planned revision")
            assets.append(asset)
        if fingerprint(job["payload"]) != job["payload_sha256"]:
            raise WorkflowError("Planned request was modified")
        operation = job["operation"]
        payload = job["payload"]
        def local_source(value):
            return isinstance(value, dict) and set(value) == {"asset_id"} and value["asset_id"] in job["input_hashes"]
        def parent_source(value):
            return (isinstance(value, dict) and set(value) == {"task_id"} and job["parent_job"] is not None
                    and value["task_id"] == self._job(data, job["parent_job"])["task_id"])
        if operation == "image_to_model" and not local_source(payload.get("input")):
            raise WorkflowError("The primary image input must be a registered asset_id placeholder")
        if operation == "multiview_to_model":
            views = payload.get("inputs")
            if (not isinstance(views, list) or len(views) != 4 or not local_source(views[0])
                    or sum(local_source(view) for view in views) < 2
                    or any(view not in (None, "") and not local_source(view) for view in views)):
                raise WorkflowError("Multiview needs four slots [front,left,back,right], at least two registered views, front required")
        if operation not in GENERATORS and not (local_source(payload.get("input")) or parent_source(payload.get("input"))):
            raise WorkflowError("The primary model input must name a registered asset or the declared parent task")
        if operation in ("image_to_model", "multiview_to_model"):
            if not assets:
                raise WorkflowError("Image generation needs registered input images")
            for asset in assets:
                self._require_gate(asset, "input", data["target"])
        if operation in ("rig", "retarget", "convert"):
            if not assets:
                raise WorkflowError("This operation needs a measured input model")
            for asset in assets:
                self._require_gate(asset, "fidelity", data["target"])
                self._require_gate(asset, "geometry", data["target"])
                if operation == "retarget" or (operation == "convert" and asset["stage"] == "rig"):
                    self._require_gate(asset, "rig", data["target"])
        used_assets = set()
        used_tasks = set()

        def resolve(value):
            if isinstance(value, dict):
                if "asset_id" in value:
                    if set(value) != {"asset_id"} or value["asset_id"] not in job["input_hashes"]:
                        raise WorkflowError("Asset placeholder must name a registered job input")
                    asset = self._asset(data, value["asset_id"])
                    upload = asset.get("upload") or {}
                    if not upload.get("file_token") or upload.get("sha256") != asset["sha256"]:
                        raise WorkflowError("Upload the exact input revision before submitting")
                    used_assets.add(asset["id"])
                    return {"file_token": upload["file_token"]}
                if "file_token" in value:
                    raise WorkflowError("Use an asset_id placeholder so input provenance can be verified")
                if "task_id" in value:
                    parent = self._job(data, job["parent_job"]) if job["parent_job"] else None
                    if not parent or value["task_id"] != parent["task_id"]:
                        raise WorkflowError("Task input must match the declared parent job")
                    used_tasks.add(parent["id"])
                return {key: resolve(item) for key, item in value.items()}
            if isinstance(value, list):
                return [resolve(item) for item in value]
            return value

        request = resolve(job["payload"])
        if operation not in GENERATORS:
            # Processing APIs use a scalar token. Generation APIs use image
            # descriptors; nested texture reference images remain descriptors.
            descriptor = request["input"]
            request["input"] = descriptor.get("file_token") or descriptor.get("task_id")
        if operation == "multiview_to_model":
            request["inputs"] = [view if view is not None else "" for view in request["inputs"]]
        if operation in ("image_to_model", "multiview_to_model") and used_assets != set(job["input_hashes"]):
            raise WorkflowError("Every image input must be bound to an asset placeholder")
        if operation not in ("text_to_model", "image_to_model", "multiview_to_model") and not used_assets and not used_tasks:
            raise WorkflowError("Processing needs a bound asset or parent task input")
        return request

    def submit(self, job_id, client):
        with self._lock():
            data = self.read_json()
            job = self._job(data, job_id)
            if job["status"] != "planned" or job["task_id"]:
                raise WorkflowError("Job was already attempted; use resume or recover, never submit again")
            if any(item["status"] in ("submitting", "unknown_submission") for item in data["jobs"].values()):
                raise WorkflowError("Reconcile the uncertain submission before sending another job")
            if data["budget"]["blocked"] or self._committed(data) + credits(job["max_credits"]) > credits(data["budget"]["limit_credits"]):
                raise WorkflowError("Budget exhausted or blocked; no request sent")
            request = self._request(data, job)
            job["status"] = "submitting"
            job["submitted_payload_sha256"] = fingerprint(request)
            job["events"].append({"event": "reservation_before_submission", "at": now()})
            self._save(data)
            try:
                response = client.submit(job["operation"], request)
                task_id = response.get("task_id")
                if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
                    raise SubmissionUncertain("Provider did not return a valid task ID")
                if any(other["task_id"] == task_id for other in data["jobs"].values() if other is not job):
                    raise SubmissionUncertain("Provider task is already associated with another job")
            except APIError as exc:
                if isinstance(exc, SubmissionUncertain):
                    job["status"] = "unknown_submission"
                else:
                    job["status"] = "rejected"
                job["last_error"] = _diagnostic("submit", job["operation"], exc)
                job["events"].append({"event": job["status"], "at": now()})
                self._save(data)
                return {"id": job_id, "status": job["status"], "task_id": None, "last_error": job["last_error"]}
            except BaseException as exc:
                job["status"] = "unknown_submission"
                job["last_error"] = _diagnostic("submit", job["operation"], exc)
                self._save(data)
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                raise WorkflowError(job["last_error"]["message"] +
                                    "; submission outcome is unknown, reservation retained, no automatic retry") from None
            job["task_id"] = task_id
            job["status"] = "submitted"
            self._save(data)
            return {"id": job_id, "status": "submitted", "task_id": task_id}

    def recover(self, job_id, task_id, note):
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise WorkflowError("Recovery needs a provider task_ identifier")
        note = text(note, "recovery evidence note")
        with self._lock():
            data = self.read_json()
            job = self._job(data, job_id)
            if job["status"] not in ("submitting", "unknown_submission") or job["task_id"]:
                raise WorkflowError("Only an uncertain submission without an ID can be recovered")
            if any(item["task_id"] == task_id for item in data["jobs"].values()):
                raise WorkflowError("Provider task is already linked")
            job["task_id"] = task_id
            job["status"] = "submitted"
            job["events"].append({"event": "manual_task_recovery", "at": now(), "note": note})
            self._save(data)
            return {"id": job_id, "status": job["status"], "task_id": task_id}

    def resume(self, job_id, client, download=True):
        with self._lock():
            data = self.read_json()
            job = self._job(data, job_id)
            if not job["task_id"]:
                if job["status"] == "submitting":
                    job["status"] = "unknown_submission"
                    self._save(data)
                return {"id": job_id, "status": job["status"], "task_id": None, "request_sent": False,
                        "output_status": self._output_status(data, job),
                        "last_error": job.get("last_error")}
            try:
                task = client.get_task(job["task_id"])
            except APIError as exc:
                job["last_error"] = _diagnostic("poll", job["operation"], exc)
                self._save(data)
                raise _safe_api_error(exc, job["last_error"]) from None
            except BaseException as exc:
                job["last_error"] = _diagnostic("poll", job["operation"], exc)
                self._save(data)
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                raise WorkflowError(job["last_error"]["message"]) from None
            if task.get("task_id") != job["task_id"] or task.get("status") not in TERMINAL | {"queued", "running"}:
                raise WorkflowError("Task query returned an unexpected ID or status")
            job["status"] = task["status"]
            if job["status"] in ("failed", "cancelled"):
                diagnostic = _diagnostic("task", job["operation"], task.get("error"))
                previous_error = job.get("last_error") or {}
                # A later empty/generic reply must not erase useful evidence or
                # make an old diagnosis look newly observed.
                if previous_error.get("stage") != "task" or any(
                        diagnostic[field] is not None and diagnostic[field] != previous_error.get(field)
                        for field in ("http_status", "provider_code")):
                    job["last_error"] = diagnostic
            progress = task.get("progress")
            if type(progress) is int and 0 <= progress <= 100:
                job["progress"] = progress
            if job["status"] in TERMINAL and task.get("credits_consumed") is not None:
                observed = credits(task["credits_consumed"])
                previous = credits(job["charged_credits"]) if job["charged_credits"] is not None else Decimal(0)
                job["charged_credits"] = amount(max(previous, observed))
                job["charge_evidence"] = {"source": "Tripo task query credits_consumed", "task_id": job["task_id"], "observed_at": now()}
                if observed > credits(job["max_credits"]) or self._committed(data) > credits(data["budget"]["limit_credits"]):
                    data["budget"]["blocked"] = True
                    job["budget_overrun"] = True
            output = task.get("output")
            url = output.get("model_url") if isinstance(output, dict) else None
            if job["status"] == "success" and not job["output_assets"]:
                if job.get("output_status") != "mismatch":
                    job["output_status"] = "not_downloaded" if isinstance(url, str) and url else "not_available"
            else:
                job["output_status"] = self._output_status(data, job)
            self._save(data)  # Save task/charge before attempting a fallible download.
            if job["status"] == "success" and download:
                try:
                    if job["output_status"] == "mismatch" and not job["output_assets"]:
                        raise WorkflowError("A mismatched output requires verified explicit adoption before reuse")
                    for asset_id in job["output_assets"]:
                        self._asset(data, asset_id)
                    if not job["output_assets"] and not (job["operation"] == "rig_check" and url is None):
                        if not isinstance(url, str) or not url:
                            raise WorkflowError("Successful task has no primary downloadable model")
                        suffix = Path(urlsplit(url).path).suffix.lower()
                        if suffix not in (".glb", ".gltf", ".fbx", ".obj", ".stl", ".zip", ".usdz", ".3mf"):
                            suffix = ".bin"
                        destination = self.path.parent / "artifacts" / f"{job_id}-model{suffix}"
                        asset_id = f"{job_id}-model"
                        if asset_id in data["artifacts"]:
                            raise WorkflowError("Output asset ID already exists")
                        if destination.parent.is_symlink():
                            raise WorkflowError("Output directory must not be a symlink")
                        destination.parent.mkdir(exist_ok=True)
                        if destination.exists() or destination.is_symlink():
                            raise WorkflowError("Unrecorded output already exists; preserve it and register it explicitly with adopt-output")
                        downloaded = client.download(url, destination)
                        record = file_record(destination)
                        if (not isinstance(downloaded, dict) or not record["bytes"]
                                or any(downloaded.get(key) != record[key] for key in ("path", "sha256", "bytes"))
                                or type(downloaded.get("bytes")) is not int):
                            job["output_status"] = "mismatch"
                            raise WorkflowError("Downloaded file does not match its measured transport record")
                        data["artifacts"][asset_id] = {"id": asset_id, "stage": OUTPUT_STAGES.get(job["operation"], "report"),
                                                      **record, "parents": list(job["input_hashes"]), "gates": {}, "upload": None,
                                                      "provider_task_id": job["task_id"]}
                        job["output_assets"].append(asset_id)
                    job["output_status"] = self._output_status(data, job)
                    if job["output_status"] == "materialized" and (job.get("last_error") or {}).get("stage") == "download":
                        job.pop("last_error")
                    self._save(data)
                except APIError as exc:
                    job["last_error"] = _diagnostic("download", job["operation"], exc)
                    self._save(data)
                    raise _safe_api_error(exc, job["last_error"]) from None
                except BaseException as exc:
                    job["last_error"] = _diagnostic("download", job["operation"], exc)
                    self._save(data)
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise
                    raise WorkflowError(job["last_error"]["message"]) from None
            return {"id": job_id, "status": job["status"], "task_id": job["task_id"],
                    "charged_credits": job["charged_credits"], "output_assets": job["output_assets"],
                    "output_status": job["output_status"], "budget_blocked": data["budget"]["blocked"],
                    "last_error": job.get("last_error")}

    def adopt_output(self, job_id, path, note):
        note = text(note, "output provenance note")
        record = file_record(path)
        if not record["bytes"]:
            raise WorkflowError("Cannot adopt an empty model file")
        with self._lock():
            data = self.read_json()
            job = self._job(data, job_id)
            asset_id = f"{job_id}-model"
            if job["status"] != "success" or job["output_assets"] or asset_id in data["artifacts"]:
                raise WorkflowError("Adoption requires a successful job without a registered model")
            for input_id, digest in job["input_hashes"].items():
                if self._asset(data, input_id)["sha256"] != digest:
                    raise WorkflowError("Job inputs no longer match the planned revision")
            data["artifacts"][asset_id] = {"id": asset_id, "stage": OUTPUT_STAGES.get(job["operation"], "generation"),
                                          **record, "parents": list(job["input_hashes"]), "gates": {}, "upload": None,
                                          "provider_task_id": job["task_id"], "provenance_note": note}
            self._asset(data, asset_id)
            job["output_assets"].append(asset_id)
            job["output_status"] = "materialized"
            if (job.get("last_error") or {}).get("stage") == "download":
                job.pop("last_error")
            self._save(data)
            return {"asset": asset_id, "status": "adopted", "sha256": record["sha256"]}

    def reconcile_cost(self, job_id, charged_credits, evidence_paths, note):
        """Explicit receipt-based settlement when task-query evidence is absent.

        This never retries a job. An unknown submission without a task ID can
        become reconciled only through this explicit evidence-bearing action.
        """
        observed = credits(charged_credits)
        note = text(note, "receipt reconciliation note")
        if not evidence_paths:
            raise WorkflowError("Reconciliation requires saved provider receipt/history evidence")
        evidence = [file_record(path) for path in evidence_paths]
        with self._lock():
            data = self.read_json()
            job = self._job(data, job_id)
            if job["status"] not in TERMINAL | {"submitting", "unknown_submission", "rejected", "reconciled"}:
                raise WorkflowError("Do not settle a job that is unsubmitted or still running")
            previous = credits(job["charged_credits"]) if job["charged_credits"] is not None else Decimal(0)
            job["charged_credits"] = amount(max(previous, observed))
            job["charge_evidence"] = {"source": "explicit provider receipt reconciliation", "evidence": evidence, "note": note, "observed_at": now()}
            if not job["task_id"]:
                job["status"] = "reconciled"
            if observed > credits(job["max_credits"]) or self._committed(data) > credits(data["budget"]["limit_credits"]):
                data["budget"]["blocked"] = True
                job["budget_overrun"] = True
            job["events"].append({"event": "receipt_reconciliation", "at": now(), "charged_credits": job["charged_credits"]})
            self._save(data)
            return {"id": job_id, "status": job["status"], "charged_credits": job["charged_credits"], "budget_blocked": data["budget"]["blocked"]}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Offline: create a new workflow.json")
    init.add_argument("--out", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--budget-credits", required=True)
    init.add_argument("--platform", choices=("pc", "android", "both"), default="both")
    init.add_argument("--region", choices=("global", "china"), default="global")
    init.add_argument("--reference", action="append", default=[])
    for command in ("status", "asset", "gate", "plan", "upload", "submit", "resume", "recover", "adopt-output", "reconcile"):
        sub = commands.add_parser(command)
        sub.add_argument("manifest")
        if command == "asset":
            sub.add_argument("--id", required=True)
            sub.add_argument("--file", required=True)
            sub.add_argument("--stage", choices=STAGES, default="input")
            sub.add_argument("--parent", action="append", default=[])
        elif command == "gate":
            sub.add_argument("--asset", required=True)
            sub.add_argument("--gate", choices=GATES, required=True)
            sub.add_argument("--status", choices=("pass", "needs_repair", "not_assessed"), required=True)
            sub.add_argument("--evidence", action="append", default=[])
            sub.add_argument("--note", default="")
        elif command == "plan":
            sub.add_argument("--job", required=True)
            sub.add_argument("--operation", choices=sorted(KINDS), required=True)
            sub.add_argument("--payload", required=True, help="Local JSON; use {asset_id: id} input placeholders")
            sub.add_argument("--max-credits", required=True)
            sub.add_argument("--input", action="append", default=[])
            sub.add_argument("--parent-job")
            sub.add_argument("--pricing-note", required=True)
        elif command == "upload":
            sub.add_argument("--asset", required=True)
        elif command != "status":
            sub.add_argument("--job", required=True)
            if command == "resume":
                sub.add_argument("--no-download", action="store_true")
            if command == "recover":
                sub.add_argument("--task-id", required=True)
                sub.add_argument("--note", required=True)
            if command == "adopt-output":
                sub.add_argument("--file", required=True)
                sub.add_argument("--note", required=True)
            if command == "reconcile":
                sub.add_argument("--charged-credits", required=True)
                sub.add_argument("--evidence", action="append", required=True)
                sub.add_argument("--note", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            output = Workflow.initialize(args.out, args.name, args.budget_credits, args.platform, args.region, args.reference).summary()
        else:
            workflow = Workflow(args.manifest)
            if args.command == "status":
                output = workflow.summary()
            elif args.command == "asset":
                output = workflow.add_asset(args.id, args.file, args.stage, args.parent)
            elif args.command == "gate":
                output = workflow.record_gate(args.asset, args.gate, args.status, args.evidence, args.note)
            elif args.command == "plan":
                output = workflow.plan_job(args.job, args.operation, json_file(args.payload), args.max_credits, args.input, args.parent_job, args.pricing_note)
            elif args.command == "recover":
                output = workflow.recover(args.job, args.task_id, args.note)
            elif args.command == "adopt-output":
                output = workflow.adopt_output(args.job, args.file, args.note)
            elif args.command == "reconcile":
                output = workflow.reconcile_cost(args.job, args.charged_credits, args.evidence, args.note)
            else:
                from tripo_api import TripoClient
                client = TripoClient(region=workflow.read_json()["region"])
                if args.command == "upload":
                    output = workflow.upload(args.asset, client)
                elif args.command == "submit":
                    output = workflow.submit(args.job, client)
                else:
                    output = workflow.resume(args.job, client, not args.no_download)
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if output.get("status") not in ("unknown_submission", "rejected", "failed", "cancelled") else 3
    except (OSError, ValueError, KeyError, APIError) as exc:
        print(f"funavatar-3d: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
