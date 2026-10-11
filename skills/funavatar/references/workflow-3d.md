# Tracked 3D production

For requested native construction, start with [Blender/Unity production](native-production.md). This ledger is optional revision tracking for native files and imported exports; it is not a requirement to use a generator. Use a zero-credit workflow for native/manual work and register its files with `asset`. The Tripo API sections below apply only when that provider is selected and authorized; other providers use the [documented handoffs](production-tools.md), not Tripo job commands.

Read for tracking native/imported revisions or an optional resumable Tripo job.
The existing `funavatar.py` remains an offline concept/report
helper. The separate `scripts/tripo_workflow.py` owns the 3D ledger and calls the
standard-library `tripo_api.py` only for explicit `upload`, `submit` and `resume`
commands. No installation or paid call is part of skill setup or validation.

## Select the work and its authority

Establish the avatar, approved master, target (`pc`, `android`, `both`), output
folder, and requested operations. Reuse the task's existing authorization. API
work needs authorized reference uploads, provider use and a numeric credit
budget. A Studio subscription does not establish API credit access. If that
scope is absent, prepare inputs and the ledger or inspect an existing export;
ask only for the missing information needed for an external action.

Here `both` means PC plus Android/Quest, not all VRChat platforms. iOS is not an implemented ledger target or SDK/client gate. Preserve an iOS requirement in the avatar contract and keep its evidence separately until explicit target support exists; never count an Android or `both` gate as iOS validation.

When Tripo is selected, use [tripo.md](tripo.md) for clean inputs and the pre-rig fidelity gate. Choose
the actual available mode/model for the task; do not require an expensive
high-detail generation followed by retopology when a direct topology-oriented
generation serves the brief. Verify Studio/API feature parity before selecting
an API operation. The adapter currently supports text/image/multiview to model,
texture, retopology, segmentation, completion, rig check, rig, retarget and
conversion. It does not expose an unverified standalone Smart UV or import
endpoint. Retopology's documented `smart_uv` option is a parameter, not a new
standalone operation.

## Ledger and revision rules

Create a new output directory per avatar/workflow. `workflow.json` is a separate
`kind: funavatar_3d_workflow`, `schema_version: 1` ledger, not a Blender/Unity
observation report. Never pass it to `project-check` as if it were a report.

The ledger contains:

- Subject, platform, API region and authorized total credit budget.
- Immutable asset IDs, absolute paths, SHA-256, byte counts, stage and parent IDs.
- Immutable job IDs, operation, explicit version/settings, request fingerprint,
  input revision hashes, parent job, maximum credit reservation, task ID, status
  and observed charge evidence.
- Revision-specific gates, their history, target, notes and hashed evidence.

Failed submissions, uploads, task queries, downloads and failed/cancelled tasks retain optional `last_error` metadata: stage, operation, observation time, a fixed error class and numeric HTTP/provider codes when available. `status` exposes this diagnostic without contacting the provider. The message is generated locally; provider text, response bodies and signed URLs are not copied. `last_error` is the latest recorded failure, not a complete error history, and must be read alongside the current job status. A verified download or explicit output adoption clears only a latest `download` error; earlier submit/poll/task diagnoses remain historical when they are still the latest diagnosis. `--no-download` does not clear diagnoses. Existing ledgers without this field remain valid; an uncertain submission still retains its reservation and is never resubmitted automatically.

Keep originals and derivatives in separate files. Register a changed model,
material package, Unity project snapshot or relevant configuration report under
a new asset ID; attach its actual dependencies with `--parent`. The new revision
starts without passed gates. Editing an existing recorded file makes it and
dependent revisions stale; operations reject stale inputs. `status` reports
stale evidence as `not_assessed` while preserving the historical gate record.
Include external textures/material files or a preserved package as additional
registered dependencies: a lone GLTF/FBX hash does not cover sidecar files.

For an SDK/client check, register a compact project/configuration report or
immutable snapshot as a revision dependent on the imported model and relevant
materials. Attach the actual SDK log or observed client evidence to that
revision. This prevents a mesh-only hash from standing in for Unity settings.

Commands below run from the skill directory with Python 3.10+ on macOS/Linux.
The workflow requires Unix `fcntl` process locks; native Windows is unsupported.
The ledger uses atomic writes and private file permissions.

```sh
python3 scripts/tripo_workflow.py init --out /path/avatars/explorer/run-01 --name Explorer --platform both --budget-credits 100 --reference /path/approved/front.png
python3 scripts/tripo_workflow.py status /path/avatars/explorer/run-01/workflow.json
```

The budget in this example is illustrative; use the user's authorized amount.
Initialization hashes references as `ref-1`, `ref-2`, etc. It contacts no service.
Existing ledgers are never overwritten.

## Gates before dependent work

Assess only checks actually performed. `pass` and `needs_repair` require a saved
evidence file and a note. A note or screenshot is evidence to review, not proof
automatically evaluated by the script. `not_assessed` remains available when a
check has not run.

```sh
python3 scripts/tripo_workflow.py gate /path/run/workflow.json --asset ref-1 --gate input --status pass --evidence /path/review/input-review.md --note "Approved isolated front, complete silhouette, neutral light and correct identity."
```

Gate names: `input`, `fidelity`, `geometry`, `surface`, `rig`, `export`, `sdk_pc`,
`sdk_android`, `client_pc`, `client_android`. Apply the current target and actual
revision. Before rigging, require imported-model fidelity and geometry checks.
Before retargeting, also require rig/deformation checks. Conversion requires
fidelity/geometry, plus the rig gate for an animated/rig-stage source. Every
resulting revision needs its own review; the adapter never marks gates passed.

Separate geometry/material inspection, native deformation tests, SDK validation
and client behavior. Use [project-checks.md](project-checks.md) for compact native
reports and [runtime-debug.md](runtime-debug.md) for actual reproduction/tests.
PC client evidence does not establish native Android/Quest compatibility.

## Upload and prepare a job

Provide credentials through `TRIPO_API_KEY` in the execution environment, never
in arguments, payload files, notes or ledgers. The API region is fixed at ledger
creation (`global` or `china`); there is no arbitrary API host override.

```sh
python3 scripts/tripo_workflow.py upload /path/run/workflow.json --asset ref-1
```

Upload is an explicit external action. Repeating it reuses the recorded token
for the unchanged revision. An uncertain upload is retained rather than silently
repeated. Supported uploads are JPEG/PNG and GLB/GLTF/FBX/OBJ/STL within current
provider size limits. The adapter does not package sidecars or implement large
file multipart sessions. Use a self-contained GLB or preserve all required
dependencies through a supported route.

Prepare a local payload JSON using an asset placeholder:

```json
{
  "input": {"asset_id": "ref-1"},
  "model": "v3.1-20260211",
  "texture": true,
  "pbr": true
}
```

The example version must be checked for availability and suitability at the time
of use. Generation, texture and retopology require explicit `model`; legacy v2
`model_version`/`original_model_task_id` fields are rejected. Verify the other
parameters against current v3 documentation. Raw URLs/tokens are not accepted
as a substitute for registered input provenance.

```sh
python3 scripts/tripo_workflow.py plan /path/run/workflow.json --job base-01 --operation image_to_model --payload /path/image-job.json --input ref-1 --max-credits 30 --pricing-note "Official API pricing checked YYYY-MM-DD; selected model and options fit the 30-credit ceiling."
python3 scripts/tripo_workflow.py submit /path/run/workflow.json --job base-01
python3 scripts/tripo_workflow.py resume /path/run/workflow.json --job base-01
```

The 30-credit ceiling is an example, not a maintained quote. `plan` is offline;
it records a reviewed upper bound and pricing rationale without submitting.
`submit` persists the reservation and intent before exactly one POST. It binds
the real source field to the uploaded revision, then saves the returned task ID.

For multiview, `inputs` has four slots in `[front, left, back, right]` order,
each supplied view is an `asset_id` placeholder, front is mandatory and at least
two views are needed. Use `null` for omitted slots; the adapter normalizes them.
Register and review each input separately. A collage is not multiview input.

For processing, use `{"input":{"asset_id":"base-01-model"}, ...}` after
uploading that measured model, or `{"input":{"task_id":"task_..."}, ...}`
with `--parent-job base-01` and `--input base-01-model`. The adapter binds the
declared parent and translates the primary processing input to the scalar
token required by v3. Nested image references remain image descriptors.

## Resume and recover without duplicate charges

Each `resume` performs one task query. If still queued/running, repeat a bounded
read-only query later against the same job. No background scheduler or unbounded
polling is created. The ledger and model files survive process/session changes.

On success, `resume` downloads the primary `model_url` into `artifacts/`, checks
the actual file against the transport's path/hash/byte record, records its hash
and parents, and reuses that unchanged file on later resumes. Provider `status`
is separate from `output_status`: `not_downloaded` has no registered model,
`materialized` has verified local output, `not_available` has no usable primary
model URL (including JSON-only rig checks), and `missing`/`mismatch` indicate
absent or changed recorded output. Offline `status` rechecks registered output
integrity without rewriting the ledger. None of these statuses certifies mesh
quality, complete materials, rigging or client behavior. Download failures leave
the successful provider task, reservation and observed charge recorded and save
a sanitized `last_error` with stage `download`. Retry only `resume` for that same
known task; no replacement POST or extra generation reservation is created. Use
`--no-download` to query without fetching a model. Preview images, split output
parts and external texture files are not automatically collected; register the
files needed for the actual handoff separately. A primary-model download alone
does not establish a complete material package.

Run [export-check](export-bundles.md) on the downloaded/exported file before
handoff. It records the model, discovered dependencies and a file-set fingerprint;
missing textures or buffers leave the package incomplete. Register sidecars as
assets and attach their IDs as parents of the export revision, then preserve the
manifest as export evidence. Changing a registered sidecar invalidates that
revision's gates even when the main model file is unchanged. File completeness
does not establish native import, deformation, SDK or client success.

Output URLs remain transient in memory. Downloads omit the API key, require
public HTTPS, validate redirects, stream within a size limit and refuse to
overwrite existing files. The transport removes its incomplete temporary files;
an unrecorded final file left by an interruption or a transport-record mismatch
is preserved and never registered or automatically reused. Compare the complete
file with provider evidence before explicitly adopting it; do not adopt a partial
or mismatched file. A recorded mismatch blocks further automatic downloads even
if the same task later returns a different URL or extension. Adoption validates
the unchanged planned input hashes and the preserved output before registering
the model or clearing its download diagnosis. Empty files and symlinks cannot be adopted. If a crash committed
a download before recording its hash, use the same explicit adoption route:

```sh
python3 scripts/tripo_workflow.py adopt-output /path/run/workflow.json --job base-01 --file /path/run/artifacts/base-01-model.glb --note "Verified preserved download against this provider task after interruption."
```

An interrupted/ambiguous POST without a saved ID is `unknown_submission` and
blocks new submissions. Its full reservation remains committed. Find the exact
task in authorized provider history, verify request identity/settings, then bind
only that identifier with an evidence note:

```sh
python3 scripts/tripo_workflow.py recover /path/run/workflow.json --job base-01 --task-id task_actual_id --note "Matched this request's inputs, version, settings and submission time in provider history."
python3 scripts/tripo_workflow.py resume /path/run/workflow.json --job base-01
```

Recovery records explicit operator evidence; the task-query API does not expose
enough original request data to prove that match automatically. Job IDs are
never reset for resubmission, including failed/rejected jobs. A deliberate new
attempt needs a new job, within remaining authorized scope and budget.

## Credit accounting and reconciliation

Check [official API pricing](https://developers.tripo3d.ai/en/pricing) for the
chosen version, options and output count before setting `max_credits`; it is a
reviewed ceiling, not a server quote generated by this helper. An account's
wallet balance is separate from the workflow's authorized budget.

Admission requires current committed credits plus the proposed reservation to
fit the total. An atomic lock prevents two submissions racing that check. For a
terminal task, observed `credits_consumed` replaces its reservation. Missing
cost stays reserved, including failed/cancelled jobs; do not infer a refund from
status alone. Recorded charges never silently decrease on a later query.

When task-query cost is absent, preserve and inspect provider usage/receipt
evidence. An explicit offline settlement can record the verified amount:

```sh
python3 scripts/tripo_workflow.py reconcile /path/run/workflow.json --job base-01 --charged-credits 0 --evidence /path/receipts/provider-history.json --note "Provider history confirms this uncertain request created no task and incurred no charge."
```

Use zero only when the evidence establishes zero. Reconciliation without a task
ID marks that attempt `reconciled`; it does not resend it. Observed charges above
a job ceiling or total freeze new submissions. Preserve the evidence and obtain
new scope before further spending; the helper does not automatically raise or
clear a blocked budget.

This is a local admission/accounting control. No documented provider-side quote
or maximum-charge parameter is available here; changes in provider pricing or
an incorrect ceiling can produce a higher actual charge. State that limitation
with reserved versus observed costs. Adapter tests exercise these rules without
spending real credits or certifying avatar behavior.

API contract checked 2026-10-11: [introduction](https://developers.tripo3d.ai/en/docs/introduction),
[task query](https://developers.tripo3d.ai/en/docs/task-query),
[file upload](https://developers.tripo3d.ai/en/docs/files),
[texture](https://developers.tripo3d.ai/en/docs/models-texture),
[retopology](https://developers.tripo3d.ai/en/docs/mesh-decimate).
Recheck before live use.
