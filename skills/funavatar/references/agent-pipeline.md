# Agent-assisted avatar pipeline

Use this reference when choosing or coordinating Blender, Unity and OSC tools.
Native authoring and the existing [production workflow](native-production.md)
remain the default. A server's README, connected socket or `success: true` does
not establish a working avatar pipeline.

## Discover and record the real capability

Start from [the source-inspected registry](../assets/mcp-capability-registry.json).
Copy relevant entries into the authorized project when recording local evidence;
the bundled registry does not describe the user's installations. Discover the
actual callable name and input schema before use, including an `operation` value
when one MCP tool exposes several actions. Do not guess tool names from articles.

| State | Evidence needed | What it establishes |
| --- | --- | --- |
| `unknown` | No adequate source or local evidence | Nothing about availability. |
| `source_inspected` | Repository, pinned commit, path/symbol, license and limitations | A particular implementation was read. |
| `connected` | Host, installed version/hash, actual tool discovery and bounded read-only response | The selected endpoint responds in this session. |
| `executed` | Exact operation/input revision, target/version, output hash and native readback | That operation worked on that subject. |

Record those states per capability, host and version; inspection of one operation
cannot certify another. Keep failures and `unknown` checks explicit. Invalidate
affected evidence when binaries, project packages, source assets or targets change.
A fixture can establish tool operation, never completion of the user's avatar.

For parallel work, give each worker a bounded artifact, acceptance condition and
owner. Keep one writer for a `.blend`, Unity scene or prefab at a time. Choose a
model by available tools, demonstrated task quality, privacy and the authorized
budget. Do not assign permanent roles or prices to speculative model versions.

## Blender: author, measure, inspect

Use available native `bpy`, an inspected MCP operation or a focused headless script.
A subprocess isolates an application instance; it is not a security sandbox.
Record the selected `.blend`, export target, timeout and expected outputs. Inspect
the saved derivative and structured results, including nested errors, before
marking an operation complete.

Treat automatic face regions, weights and shape generation as starting points.
Check anatomical regions, eyelid closure, mouth interior, teeth/tongue, left/right
independence and combined expressions; inspect 0, intermediate and full values.
Presence of an ARKit/Unified name is not useful deformation or tested tracking.

For a read-only check of shape deltas on one explicit mesh:

```sh
blender --background avatar.blend --python scripts/blender_face_probe.py -- \
  --mesh Face --required vrc.v_aa --required eyeBlinkLeft --out face-probe.json
```

The output is new-only. The probe reads coordinates against each relative key
(against the first key in absolute mode), without setting shape values, frames,
modes or render settings. Required missing/zero-delta shapes need repair;
unreadable or missing observations remain `unknown`. A saved file hash describes
disk bytes; `source.dirty` identifies unsaved Blender changes. Read the JSON status,
not the Blender process exit code. The probe does not assess aesthetics, poses,
weights, export fidelity or hardware behavior.
List only shapes that must deform under `--required`; a deliberate neutral/rest
or silence shape can validly have zero delta and should be reviewed separately.

Optimize a protected derivative. Recount evaluated meshes and material slots after
changes, validate bake channels and pixels, and compare skinning and facial
deformation before/after. Do not copy an operation merely because it claims to
preserve shape keys or automatically detect landmarks.

## Unity: native assembly and modular build

Verify the supported editor and installed SDK/package versions. Live editor
operations require the matching bridge and project. Prefer Editor APIs,
`SerializedObject` and `AssetDatabase` for persistent changes. UnityPy inspection
of serialized binary assets is separate from UnityYAML source editing. Substring
replacement in `.prefab`, `.unity` or `.asset` is not a safe general serializer;
preserve `.meta`/GUID/fileID references and prove import/compilation after edits.

Use compatible, already-installed Modular Avatar, VRCFury or Avatar Optimizer when
they solve the requested feature. Keep source prefabs intact and assign ownership
for armature merges, menu/parameter installation, controller changes and optimization
so packages do not independently rewrite the same feature. Inspect their generated
build result, not only source counts. Protect OSC-, SDK- and tracking-driven shape
keys from pruning even if direct animation references are absent. Follow the
installed package's documented preservation mechanism and test the built result.

Check Write Defaults, tracking ownership, masks, reset paths, parameter types and
budgets against the actual controllers; do not force a global conversion merely
because a tool offers it. Keep PC and mobile derivatives, shaders and test evidence
separate. A successful local build needs an actual output and SDK result.

## Build, publication and runtime are separate

Distinguish pre-build callbacks, SDK validation, generated bundle, upload receipt
and observed client behavior. A process returning zero or finding an avatar ID in
an old log cannot establish a new upload. Use the task's existing authorization;
when publication is outside scope, finish the local deliverable. Keep credentials
and 2FA in the authorized native login flow, outside prompts and reports.

Sampling may ask the client's model for a plan. It only becomes an executed
workflow when actual tool calls and outputs have been recorded. Keep context
minimal and do not silently select paid providers or export private assets.

OSC is an optional runtime route. Identify the loaded avatar and exposed parameter
types, establish an allowlist and baseline/reset, bound rates and session duration,
then distinguish a sent UDP packet from a readback or visible result. Receiving
OSC events does not prove access to all world state. Chatbox/TTS/social input needs
the user's explicit messaging scope; read-only discovery must not send an automatic
startup message. Stop and release owned controls on errors or avatar changes.

## Source findings to preserve

Checked 2026-10-12; these are pinned source observations, not current-host tests.
No third-party source code is included in this addition.

- **Blender Copilot, MIT:** [face tools](https://github.com/dwgx/blender-copilot/blob/ca345c1aea977d9103df0ceca6fcff9fe3865951/src/blender_copilot/face_tracking_tools.py)
  include empty-key paths; [Rigify conversion](https://github.com/dwgx/blender-copilot/blob/ca345c1aea977d9103df0ceca6fcff9fe3865951/src/blender_copilot/rigify_tools.py#L390)
  changes source mesh groups/parents. Its atlas is diffuse-only and can continue
  after a failed bake. Its build tool only invokes a pre-build callback.
- **sandraschi Blender MCP, MIT:** [geometry audit](https://github.com/sandraschi/blender-mcp/blob/3f158ed1047329c81fe6adb6fb8d00ca1bcdd158/src/blender_mcp/handlers/mesh_validation_handler.py)
  has concrete measurements. Review bundles can contain failed child operations
  despite an outer success. Inspect each child result.
- **sandraschi Unity MCP, MIT:** [validation](https://github.com/sandraschi/unity3d-mcp/blob/6d7e12b3e55c118f1ee9af9067cbf53cd3aadc58/src/unity3d_mcp/vrchat/__init__.py#L310)
  returns a fixed positive stub; reject it as SDK evidence. [Disk writes](https://github.com/sandraschi/unity3d-mcp/blob/6d7e12b3e55c118f1ee9af9067cbf53cd3aadc58/src/unity3d_mcp/tools/portmanteau/unity_disk_ops.py#L77)
  use line matching. Its agentic entrypoint samples a plan without executing it.
- **Krekun OSC:** [license terms](https://github.com/Krekun/vrchat-mcp-osc/blob/bd125daa1c3a04feac68f1d9addf615e2e23f90e/README.md#license)
  restrict commercial use; do not copy into general distribution without permission.
  The client sends a chatbox on startup and logs message values. Prefer an independent
  implementation against official OSC documentation when needed.
- **Seidr-Smidja:** [gate](https://github.com/hrabanazviking/Seidr-Smidja/blob/132fcc2777467f56637ccb1be4001d2fd880eecb/src/seidr_smidja/gate/gate.py#L144)
  leaves polygon/texture checks unevaluated with advisory warnings. Its LICENSE and
  updated README specify Apache-2.0/NOTICE, while package metadata still says MIT.
  Preserve notices and verify provenance before selective reuse.

For any reused implementation, retain the applicable license/copyright/NOTICE and
record the upstream commit. Models, textures, datasets and connected cloud services
can carry separate terms. A repository license does not authorize their reuse.
