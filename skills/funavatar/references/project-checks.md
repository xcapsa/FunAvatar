# Local planning and project checks

The offline helper uses Python 3.10+ and the standard library. It does not generate images, execute Blender/Unity, install packages, contact services, validate an SDK build or certify runtime behavior. The optional Tripo adapter is a separate, explicitly authorized online route described in [workflow-3d.md](workflow-3d.md). Commands below run from the `funavatar` skill directory; quote paths containing spaces. Use new output names to preserve earlier artifacts.

## Concept helper

```sh
python3 scripts/funavatar.py plan --idea "A friendly cyberpunk explorer" --name explorer --out ./output/explorer
python3 scripts/funavatar.py plan --idea "A cheerful inventor" --name inventor --transformation "human to sloth" --reference ./reference.jpg --brand Oculandia --out ./output/inventor
python3 scripts/funavatar.py check ./output/explorer/front.png ./output/explorer/back.png
```

`plan` writes `brief.json` and `prompts.md`, preserving existing targets. Repeat `--reference` for existing PNG/JPEG/WebP images. Transformation plans include complete base and transformed view sets; an intermediate sketch is optional. Oculandia branding is selected explicitly.

`check` reports container/header structure, dimensions, SHA-256 and a configurable minimum long edge (`--min-long-edge`, default 1024). It does not decode pixels, judge anatomy/identity, or establish 3D readiness. Always inspect actual images.

## Collect the relevant native observations

Use the existing project's native tooling first. These optional collectors read selected content and write a compact JSON report; run only in the authorized asset/project and supported editor.

**Blender:** use an available compatible Blender executable, a copy of the source `.blend` and a new report path:

```sh
blender --background /path/avatar.blend --python scripts/blender_report.py -- --out /path/new-blender-report.json --root AvatarRoot
```

`--root` selects the named object and descendants; omit it for the current scene. Counts reflect evaluated current-frame/viewport geometry, not final exported/build geometry. Weight checks cover source deform-bone vertex groups when applicable; envelope or unsupported setups leave relevant observations absent. The collector does not save the `.blend`, apply modifiers or normalize weights. A count cannot judge topology, normals, UV quality or deformation visually.

**Unity:** copy `assets/unity/Editor/FunAvatarReport.cs` into the authorized avatar project's `Assets/Editor/` if it would not replace an existing file. Select the intended avatar root, then use **Tools → FunAvatar → Export selected avatar observations** and choose a new JSON path. Use the project's supported Unity editor and active target; do not migrate the project merely to run this collector.

The collector includes inactive descendants and inspects direct Animator/legacy clips plus custom Descriptor layer controllers. Bindings are relative to their owning Animator/Descriptor root. Build-time merge tools can change the final hierarchy, controllers or bindings: use their preview and actual SDK validation for the generated result. Reports omit source paths and retain a sanitized subject name, but still review reports before sharing.

## Native provenance, schema version 2

Both collectors now emit `schema_version: 2`; the helper still reads unchanged v1 reports. Version 2 adds a required `provenance` object:

```json
{
  "collector": "funavatar.unity_report",
  "collector_version": "2.0.0",
  "native_target": "Android",
  "source": {
    "kind": "unity_asset",
    "state": "saved",
    "hash_algorithm": "unity_dependency_hash128",
    "hash": "1234567890abcdef1234567890abcdef"
  },
  "packages_state": "observed",
  "packages": [{"name": "com.vrchat.avatars", "version": "3.10.1"}]
}
```

This is an illustrative format, not evidence for a real asset or a recommended SDK version. `source.state` is `saved`, `modified`, `unsaved` or `unknown`. Only `saved` carries a current fingerprint; the other states require an empty `hash`. Collectors never save a source to manufacture its fingerprint. The reader preserves provenance as supplied, rather than independently verifying the source from a report.

Blender records a streaming SHA-256 of the existing, unmodified `.blend` file, with source kind `blend_file`. An unreadable/changing file is `unknown`; a dirty in-memory file is `modified`. This covers the saved `.blend` bytes, not external linked libraries/textures, current runtime state or an entire dependency package. Its native target and package state are `not_applicable`.

Unity records the exact active `BuildTarget` and a native [asset dependency Hash128](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/AssetDatabase.GetAssetDependencyHash.html) for the selected saved prefab/asset or containing scene, with kind `unity_asset` or `unity_scene`. This native aggregate includes source, meta/import configuration and target; it is **not SHA-256** or a whole-project fingerprint. Dirty scene/prefab/components or loaded dependencies leave `modified` with no hash. Native dirty flags cannot identify every edit made by arbitrary external scripts without notifying Unity. A missing/unavailable source remains `unknown`; an unsaved scene remains `unsaved`.

Unity's [registered package inventory](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/PackageManager.PackageInfo.GetAllRegisteredPackages.html) records only names/versions for `com.unity.*`, VRChat base/avatars, NDMF, Modular Avatar and VRCFury. It excludes paths, registry/source URLs and unrelated/private packages. `packages_state: unknown` means enumeration was unavailable; `observed` with an empty list means no allowlisted registered package was observed. A `.unitypackage` installation may have no registered package/version and must be documented separately. No package presence certifies SDK compilation or compatibility. API guidance checked against Unity 2022.3 on 2026-10-12.

`project-check` includes `source_schema_version` and the unchanged provenance per report; v1 reports have `provenance: null`. It derives an operational target only for recognized standalone-PC or Android native targets. iOS may be recorded as `native_target: iOS` without claiming an operational iOS helper/SDK gate. A contradictory explicit `target`, invalid fingerprint, private extra fields or a saved fingerprint attached to an unknown/dirty source is rejected.

Optional native regression tests live in the repository at `tests/unity/FunAvatarReportTests.cs` with its `.asmdef`. In a disposable authorized project with the Unity Test Framework already available, place those two files and the collector together under a new `Assets/FunAvatarTests/` folder (without a second collector copy elsewhere). Run them as EditMode tests. They cover saved/unsaved provenance, dirty material dependencies, material slots and controller binding scope. They create and clean only their own temporary scene/assets, without saving other scenes/assets. Offline Python tests or a C# compile do not execute these native checks; record any unrun tests explicitly.

## Check reports and prepare a debug plan

```sh
python3 scripts/funavatar.py project-check /path/new-blender-report.json /path/new-unity-report.json --out ./output/project-check.json
python3 scripts/funavatar.py debug-plan --symptom fidelity --platform both --out ./output/fidelity-debug
```

`project-check REPORT [REPORT ...] [--out FILE]` reads up to eight compact reports (128 KiB each), validates the report structure and emits findings. Accepted reports use `schema_version: 1|2`, `tool: blender|unity`, nonempty `tool_version` and `subject`, and an `observations` object with recognized nonnegative integer counts. Version 2 also requires the provenance above. Optional v1 `target` is `pc`, `android` or `both`; an explicit v2 target must match its observed native target. Missing measurements are unknown; unknown fields, duplicate JSON keys, invalid values and oversized input are rejected. Output is printed; `--out` also writes a new file, creates needed parent directories, and refuses an existing file or symlink.

Exit status: `0` means no reported static fail/review finding, `1` means a fail, `3` means review is needed without a fail, and `2` means invalid input or an I/O error. Even status `0` leaves runtime **not verified**. Findings are leads for native inspection, not automatic permission to change a project.

`debug-plan --symptom fidelity|effects|remote|mobile|deformation|pixelation|motion --out DIR [--platform pc|android|both]` writes `debug-plan.json` and `debug-plan.md`, defaulting to `both`. It preserves existing output targets. Plans start with `executed: false` and `status: not_verified`; no check has run. `project-check` also leaves runtime `reference_fidelity` as `not_verified`; static counts cannot judge resemblance. Follow [runtime-debug.md](runtime-debug.md) for evidence and targeted fixes.

Keep reports with the source revision/hash, collector version and scope. Reuse a report only while its source, target and relevant settings remain unchanged. Fixtures and helper tests establish the helper's behavior, not the real avatar's condition.

Platform scope: `both` means PC plus Android/Quest. Reports and debug plans do not implement an operational iOS target. Keep requested iOS checks in a separate avatar-contract evidence record; do not change their target to Android to make the helper accept them. A v1 report without `target`, or v2 report with an unrecognized native target, leaves the operational target unknown.

## Connect observations to a 3D workflow

When a tracked 3D asset is under inspection, attach the native report as evidence for the precise revision/hash in the separate `workflow.json` ledger. Do not add ledger, job, cost or lineage fields to these versioned observation reports, and do not pass a workflow ledger to `project-check`. Missing observations remain unknown in both routes.

The workflow gates use `pass`, `needs_repair` or `not_assessed` for the specific check and asset revision. Static report results inform native investigation; they cannot by themselves pass reference fidelity, deformation, SDK or client gates. Preserve report evidence for earlier revisions, and invalidate affected downstream checks after geometry, materials, target or relevant settings change. Follow [workflow-3d.md](workflow-3d.md) only when creating or updating the production ledger.
