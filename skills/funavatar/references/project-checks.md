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

The collector includes inactive descendants and inspects direct Animator/legacy clips plus custom Descriptor layer controllers. Bindings are relative to their owning Animator/Descriptor root. Build-time merge tools can change the final hierarchy, controllers or bindings: use their preview and actual SDK validation for the generated result. Reports omit full asset paths and retain a sanitized subject name, but still review reports before sharing.

## Check reports and prepare a debug plan

```sh
python3 scripts/funavatar.py project-check /path/new-blender-report.json /path/new-unity-report.json --out ./output/project-check.json
python3 scripts/funavatar.py debug-plan --symptom fidelity --platform both --out ./output/fidelity-debug
```

`project-check REPORT [REPORT ...] [--out FILE]` reads up to eight compact reports (128 KiB each), validates the report structure and emits findings. Accepted reports use `schema_version: 1`, `tool: blender|unity`, nonempty `tool_version` and `subject`, and an `observations` object with recognized nonnegative integer counts. Optional `target` is `pc`, `android` or `both`. Missing measurements are unknown; unknown fields, duplicate JSON keys, invalid values and oversized input are rejected. Output is printed; `--out` also writes a new file, creates needed parent directories, and refuses an existing file or symlink.

Exit status: `0` means no reported static fail/review finding, `1` means a fail, `3` means review is needed without a fail, and `2` means invalid input or an I/O error. Even status `0` leaves runtime **not verified**. Findings are leads for native inspection, not automatic permission to change a project.

`debug-plan --symptom fidelity|effects|remote|mobile|deformation|pixelation|motion --out DIR [--platform pc|android|both]` writes `debug-plan.json` and `debug-plan.md`, defaulting to `both`. It preserves existing output targets. Plans start with `executed: false` and `status: not_verified`; no check has run. `project-check` also leaves runtime `reference_fidelity` as `not_verified`; static counts cannot judge resemblance. Follow [runtime-debug.md](runtime-debug.md) for evidence and targeted fixes.

Keep reports with the source revision/hash, collector version and scope. Reuse a report only while its source, target and relevant settings remain unchanged. Fixtures and helper tests establish the helper's behavior, not the real avatar's condition.

## Connect observations to a 3D workflow

When a tracked 3D asset is under inspection, attach the native report as evidence for the precise revision/hash in the separate `workflow.json` ledger. Do not add ledger, job, cost or lineage fields to these strict schema-version-1 reports, and do not pass a workflow ledger to `project-check`. Missing observations remain unknown in both routes.

The workflow gates use `pass`, `needs_repair` or `not_assessed` for the specific check and asset revision. Static report results inform native investigation; they cannot by themselves pass reference fidelity, deformation, SDK or client gates. Preserve report evidence for earlier revisions, and invalidate affected downstream checks after geometry, materials, target or relevant settings change. Follow [workflow-3d.md](workflow-3d.md) only when creating or updating the production ledger.
