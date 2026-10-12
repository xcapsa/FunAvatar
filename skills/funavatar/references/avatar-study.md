# Learn how an avatar is built

Use this route for studying an authorized avatar package, understanding a feature,
or transferring a construction technique into a new avatar. The useful result is
a supported explanation and an original implementation with the relevant checks.
An inventory alone is an intermediate result.

Choose one question before collecting large reports: for example, how an outfit
follows the rig, how a facial expression returns to neutral, or how a PC feature
is adapted for Android. Record the source, licence, exact archive hash, intended
target and behavior that would demonstrate the lesson. Preserve originals and
use a separate project folder for the study. Do not silently mix the studied
character's identity with the avatar being built.

## Inspect the package before importing it

From the skill directory, with Python 3.10+:

```sh
python3 scripts/avatar_inspect.py /path/avatar.zip --out /path/new-study.json
python3 scripts/avatar_inspect.py /path/avatar.unitypackage --out /path/new-study.json
```

The helper reads ZIP/UnityPackage containers without extracting assets, running
code or launching an editor. It records source provenance, package assets, GUID
relationships and selected serialized Unity observations. Its compact report has
a separate `funavatar.package_study` schema; do not feed it to `project-check` or
treat it as a native observation report. Existing outputs are preserved. The
report records configured limits, consumed bytes/members and opaque content.
Defaults bound the source to 2 GiB, aggregate decompressed reads to 8 GiB,
members to 100,000, each YAML asset to 16 MiB and retained YAML to 64 MiB. An
oversized or unsupported input needs a narrower supported inspection route.

Keep the detailed index on disk; it can be several MiB. Start with the short CLI
summary, then retrieve only the asset/property needed for the question. Do not
paste the complete index into model context. For example, this prints at most
20 matching declarations or references from one selected asset:

```sh
python3 - /path/study.json Assets/Avatar/Selected.prefab expressionsMenu <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    report = json.load(source)
for package in report["packages"]:
    for entry in package["entries"]:
        if entry["path"] == sys.argv[2]:
            data = entry.get("yaml", {})
            rows = data.get("field_observations", []) + data.get("references", [])
            matches = [r for r in rows if sys.argv[3] in r["field_path"]][:20]
            print(json.dumps({"package": package["name"], "guid": entry["guid"],
                              "matches": matches}, ensure_ascii=False))
PY
```

Build the GUID map across the relevant packages before diagnosing missing assets.
A Quest prefab can reference a controller contained only in the PC package. A
GUID absent from the archive can also belong to an external SDK/package, so an
unresolved reference is an investigation lead, not automatically a broken avatar.
Record the dependency's source and version when resolving it. Do not fetch a
package merely to make a report look complete.

Preserve the full `(GUID, fileID)` pair and the asset/line that used it. A DLL's
single GUID can identify several MonoScript types through different fileIDs.
Resolve those types with a compatible installed SDK and native readback; matching
field names or a familiar GUID is weaker evidence. YAML source counts include
inactive objects and omit inherited or generated content unless separately read.
They are not active component counts, a final performance rank or a built avatar.

Keep serialized observations distinct from behavior:

- A parameter declaration does not establish which controller consumes it.
- A clip binding does not establish that its state can be reached.
- A null Descriptor menu does not prove that the final avatar has no menu:
  modular tools can generate and install it during the build.
- An optimization flag records intent; measure the generated build separately.
- FBX, textures and compiled assemblies remain opaque to this text inspector.

Resolve the selected prefab's base/variant chain and `m_Modifications` before
diagnosing its effective Descriptor. A serialized null can be inherited or
overridden; flattened text from one prefab is not its complete configuration.
Record unresolved inheritance separately from build-time generation. Confirm
the effective selected variant natively when the source evidence is insufficient.

Start with the causal chain below. Choose native work according to the unresolved
question: a menu investigation does not require a geometry/UV tour. Read the native
section when geometry, deformation, effective prefab inheritance or generated
content is needed to resolve the question.

## Native observations when needed

Use existing [native tools](native-production.md) and [collectors](project-checks.md)
on a protected working copy. For a Blender study, open/import only the selected
source in an isolated process with `--disable-autoexec`; use scripts you control.
A background process is not a security sandbox. An unfamiliar Unity import can
compile and execute Editor scripts or importers, so review the content and its
dependencies before copying it into an editor project. Do not import an entire
download into an active production project as an inventory shortcut.

For geometry or deformation questions, compare PC/mobile derivatives with the same camera, scale and pose. Collect mesh
and material separation, evaluated triangles, UV layers, armature hierarchy,
deform weights, shape keys and actions. Use matched silhouette, neutral/clay,
wireframe and material views to distinguish modeled detail from shading or paint.
A geometry-only view cannot assess the author's intended shader or final texture.
Counts and weight coverage cannot judge joint bends or likeness visually.

For facial behavior, use the existing [face probe](agent-pipeline.md#blender-author-measure-inspect)
and inspect intermediate/combined expressions. For garments, trace ordinary body
skinning first, then the intended secondary chains, gravity/inertia/collisions and
attachment ownership. Do not infer tracking, wind/water response or remote
synchronization from bones, labels, component presence or a static pose.

In Unity, inspect both source and generated hierarchy/controllers. Preserve the
package versions and target in the evidence. Native merge/optimization can change
names, bones, bindings and parameter installation. The generated result, SDK
validation and client behavior remain separate checks.

## Trace one causal chain

For a menu or expression, trace the chain with concrete asset references:

```text
user input / menu control
  -> parameter name, type, default, saved and synced scope
  -> owning playable layer / controller
  -> transition condition and reachable state
  -> animation clip or build-time generated control
  -> binding path + property
  -> object, renderer, material, blendshape or supported physics component
  -> exit / interruption / reset / tracking restoration
```

Record each link as `observed_static`, `observed_native`, `hypothesis` or
`tested`, with a file/hash and a useful line, GUID/fileID or native observation.
Leave absent links unknown. For modular content, identify the generator's
declaration and its actual generated link rather than assuming the source graph
is already the final graph. For a gesture, check which layer owns transforms and
which owns non-transform properties against current VRChat guidance.

Then vary one input at a time: baseline, activation, intermediate value where
applicable, deactivation and interruption. Check retained state after reloading
when intended; distinguish saved state from synchronized state. Test both
directions of a toggle and repeated activation so a one-way demonstration cannot
hide a missing reset. For an action override, verify that ordinary tracking
regains ownership afterward. Capture local/mirror, remote and native target-device
results separately where the feature requires them.

## Reconstruct and promote the lesson

Implement the smallest original probe that tests the inferred mechanism. Use an
original mesh/material/control or a licensed test fixture; keep source assets and
author code out of reusable skill files. Reuse third-party content only when its
licence and the authorized task allow it, retaining the applicable notices.

Prefer native components and already available maintained tools, then a small
original fix. Compare the probe to the observed behavior with the same inputs.
If it fails, revise the explanation or implementation; do not label a plausible
diagram as a tested technique. A successful probe certifies that mechanism under
the recorded conditions, not a finished character or universal compatibility.

Keep a compact experience card in the authorized project:

```json
{
  "question": "How does this feature return to neutral?",
  "source_hash": "exact archive or native source hash",
  "evidence": ["package/asset + GUID/fileID/line or native report"],
  "observed_mechanism": "Only the links supported by the evidence",
  "unknowns": ["Unobserved generated/runtime links"],
  "original_probe": "local path + hash, or not_implemented",
  "checks": {"baseline": "not_assessed", "activate": "not_assessed",
             "exit": "not_assessed", "interrupt_reset": "not_assessed"},
  "transfer": "Specific change to the target avatar, with its revision"
}
```

When transferring the mechanism into an actual avatar, keep its approved identity
and [reference-fidelity gate](reference-reconstruction.md) controlling. Recheck
affected geometry, rig, export, SDK and client gates after the change. Follow the
[dynamic motion acceptance gate](runtime-debug.md#dynamic-motion-acceptance-gate)
for responsive behavior. Promote a general method into FunAvatar after evidence
and review; keep character-specific files, experiences and failed hypotheses in
the project. Do not write them to global memory or publish them automatically.

## REA and other optional analysis tools

The [REA project](https://github.com/morluto/rea) supplies software investigation
tools, including static JavaScript and .NET inspection and native binary analysis
through supported providers. Its method of investigating a feature with evidence,
then implementing and comparing it, is useful here. It does not replace Blender
or Unity for interpreting meshes, rigs or generated avatar behavior.

Use direct source/package inspection and native avatar tools for data already
available in those forms. Consider REA only for a specific unresolved software
component, such as an authorized compiled plugin, when that operation and local
tool access are actually available. Record the selected version, input hash,
operation, findings and limitations. Do not imply that REA is installed or tested
from reading its documentation, or run its setup just because this route was
selected. No REA dependency is required by the offline package inspector.

Primary references checked 2026-10-12:

- [REA capabilities and requirements](https://github.com/morluto/rea#what-you-can-analyze).
- [Modular Avatar Menu Installer](https://modular-avatar.nadena.dev/docs/reference/menu-installer):
  source declarations can install or generate menu controls.
- [Modular Avatar Merge Armature](https://modular-avatar.nadena.dev/docs/reference/merge-armature):
  rig and reference rewriting must be inspected after generation.
- [VRChat Playable Layers](https://creators.vrchat.com/avatars/playable-layers/):
  layer ownership and the actual animation properties matter.
