# Build in Blender and Unity

Use this route when the user asks the agent to **make or repair the actual 3D character**. Native production is the default: inspect the available Blender/Unity project and capabilities, then build in the tools. A concept, prompt, provider suggestion or project report does not complete a request for an editable, rigged, animated asset. Tripo and other generators are optional sources or handoffs when the user chooses them; they are not a prerequisite for native work.

Read [production strategy](production-strategy.md) first for intake, inspected reference-avatar techniques, source selection and the stop/change-route rule. Native execution is not a requirement to build every shape from scratch.

## Establish a usable native workspace

Identify the character, approved design or source asset, intended platform and requested animation/features. Inspect available Blender and Unity MCP tools, application control, executables, installed project packages and Editor scripting support. Use an already available native interface that can create/edit/save the project. When an MCP is absent but the executable is available, write and run a focused `bpy` script or Unity C# Editor script in the authorized project. A missing MCP alone is not a reason to stop at prompts.

If present on the local host, `~/.local/share/funavatar/native-tools.json` records previously discovered native binaries and diagnostic reports. Recheck the executable and version before use. The portable skill does not imply that this local file, an application license or a native connector exists on another host.

Before edits, inspect the native file/project and make a reversible working copy or protected revision. Keep synced reference folders read-only. Record the installed versions and verify the project's supported Unity/SDK combination; an installed newer Unity editor does not justify migration. Do not activate a license, install paid services, change global preferences, migrate the app/project, upload models or publish an avatar as a workaround. State a concrete missing capability if native execution is unavailable, while completing independent local preparation.

For scripted execution, isolate user data and use explicit input/output paths. Avoid interpolating raw prompts or file contents into executable code. Scope Blender edits to named character objects/collections. Scope Unity Editor edits to the intended prefab, asset paths, controller and avatar Descriptor; preserve asset GUIDs and unrelated scenes/packages. A successful exit code is followed by native readback of the saved result.

## Produce the requested character

For supplied photos/designs, apply [reference reconstruction](reference-reconstruction.md) first, including native scripts and MCP creation. Work in short **edit → native readback → matched render → visual comparison** cycles. Keep blockout, surface refinement and production rigging as separate operations; do not write or launch a monolithic script that invents the body, clothes, hair and final rig before looking at intermediate results. Run downstream production commands through `fidelity_review.py run` with the current review. An environment check or a temporary pose control is allowed while fidelity is blocked; production animation, optimization and Unity avatar assembly are not.

Construct or repair mesh shapes against the reference silhouette and proportions. Use suitable rounded surfaces and adequate segments where curvature changes, with connected joint loops and topology that supports the intended bends. Primitive shapes may be useful construction blocks, but a pile of cubes/cylinders or a diagnostic fixture is not the final character. Refine the face, hands, clothing, accessories and other identity details that the brief actually needs.

Separate causes of a blocky result. Silhouette facets need geometry; flat surface shading needs inspection of normals/smooth/sharp boundaries; blurred or blocky paint needs UV density, texture resolution and import/compression checks. Smooth shading cannot create a curved silhouette, and extra polygons cannot recover missing texture detail. Preserve intentional hard surfaces. Compare matching neutral-lit, material/unlit and wireframe views so texture illusions do not stand in for modeled detail.

Create usable UVs and materials, then preserve them in the `.blend` source alongside the editable mesh, modifiers, armature, weights, shape keys and actions that are actually used. Keep the detailed source and any optimized/exported derivative separate. Use named bones, a deliberate rest/bind pose, complete normalized weights and joint bend checks on the final mesh. Automatic weights or a generated skeleton are starting points until actual deformation is inspected.

For generated visemes or facial-tracking shapes, use the read-only [facial probe and visual gates](agent-pipeline.md#blender-author-measure-inspect). Require nonzero deltas only for shapes intended to deform; neutral/silence can be intentionally static. Then inspect intermediate and combined poses, anatomical regions and the exported result. Names, delta counts and a generator's success flag cannot establish good facial motion. Use [measured budgets](performance-budgets.md) when observations exist, keeping source and final build measurements separate.

Implement the animation states the brief calls for as real Blender actions and/or Unity clips/controller states. Verify state entry, exit, interruption and reset. For wearer-following motion, configure Humanoid mapping when appropriate to the anatomy and target, or document the supported alternative and explicit wearer-input mapping; ordinary body bones follow tracking/IK, while hair, straps or tails may have deliberate secondary motion. Do not solve all motion by adding physics to the body. Use the [dynamic motion acceptance gate](runtime-debug.md#dynamic-motion-acceptance-gate) for actual client evidence.

Export to a new target file with explicit units, axes, rig and animation settings; reimport and inspect the result. Preserve the `.blend` as the authoring source. In a compatible Unity project, import the asset, inspect skinning/materials/clips, create or update the intended prefab/controller and run the relevant Editor/SDK checks. A license or compatible-editor blocker leaves Unity/SDK work unverified; do not manufacture proof by importing into an unsupported editor. Exported clips alone do not implement VRChat menus, synchronization, gestures or expressions.

Use [export-check](export-bundles.md) to record the exported model and its file dependencies before handing them off. For opaque formats such as FBX, supply the native exporter's explicit dependency declaration or leave completeness unassessed. Native reimport, shader reconstruction and deformation checks remain separate from file completeness.

Deliver the editable source and actual exports, plus a brief record of source hashes, native readback, views/motion samples and checks that ran. Distinguish Blender authoring, export round trip, Unity import/controller behavior, SDK build and local/remote/device client behavior. Continue repairing the native asset at the failed stage rather than replacing requested production with a new reference image.

## Check the Blender execution path with a temporary fixture

`scripts/blender_native_smoke.py` exercises native creation, skinning, animation, saving and format round trips. It is **a toolchain validation fixture only**, never an avatar, final character or evidence about the user's model. It makes a curved, smooth capsule-like limb with UVs/material, two deform bones, normalized weights and two real actions. It saves a new `.blend`, reopens it, then exports/reimports FBX if the native operators are available. Deformation checks sample evaluated vertex motion per action; they do not rate the quality of a production rig.

Run from the skill directory with an available Blender executable and an absolute, **nonexistent** output directory whose parent already exists:

```sh
python3 scripts/blender_native_smoke.py --outdir /absolute/new-smoke-output --plan
blender --background --factory-startup --python scripts/blender_native_smoke.py -- --outdir /absolute/new-smoke-output --require-fbx
```

The planning command creates nothing. The native command refuses an existing directory/symlink, an interactive Blender session or a loaded user `.blend`. It resets only its disposable background process; it never saves preferences or user models. A bundled FBX add-on may be enabled in that process only. The helper does not install missing extensions or dependencies.

Outputs are `TEMP_fixture.blend`, optional `TEMP_fixture.fbx`, and `native-smoke.json`. The JSON includes actual tool version, file hashes, reloaded/reimported mesh/armature/UV/material/weight facts, two-action deformation observations, individual checks and limitations. It is a separate diagnostic schema; do not feed it to `project-check` or confuse it with `workflow.json`. Failed runs retain their partial artifacts and error report for inspection; use a fresh directory for a retry.

Exit codes: `0` means the reported fixture stages passed (FBX may still be explicitly unavailable unless `--require-fbx` was used), `1` means an executed native stage failed, `2` means invalid/protected input or an I/O problem, and `3` means Blender or a required FBX round trip is unavailable. Inspect the JSON status and checks rather than treating `0` alone as full completion. Offline unit tests verify safety/geometry helpers; only actual Blender execution proves the native path.

## Official references

Checked 2026-10-11; use the documentation matching the executing Blender version and recheck relevant APIs before future changes.

- [Blender Python API](https://docs.blender.org/api/current/): native data access and operators. Operators depend on context and the installed release; use actual readback to verify results.
- [Save/open operators](https://docs.blender.org/api/5.0/bpy.ops.wm.html): source save and reload. Background scripts still need explicit protection against overwriting files.
- [FBX export operator](https://docs.blender.org/api/5.0/bpy.ops.export_scene.html): separate actions, animation baking, axes and skin export. Exporting all compatible actions requires careful scoping in a production project.
- [Action slots](https://docs.blender.org/api/5.0/bpy.types.ActionSlot.html): newer releases associate an animated data block with an action and a slot. Keyframe insertion can create that binding; action assignment/readback must respect it.
- [VRChat's current Unity version](https://creators.vrchat.com/sdk/upgrade/current-unity-version/) and [first avatar workflow](https://creators.vrchat.com/avatars/creating-your-first-avatar/): supported Unity setup and the separate build/client stages. See [technical handoff](technical-handoff.md#verify-current-official-guidance) for the dated compatibility check.
