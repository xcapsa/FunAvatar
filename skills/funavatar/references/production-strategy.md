# From a useful input to a complete avatar

The intended result is a faithful, usable avatar from an image, a clear prompt, or both, with little repeated work for the user. Instructions alone do not establish that this result has been achieved. Keep visual acceptance and feature/runtime acceptance separate.

## Establish the brief once

Inspect supplied images and reuse the existing avatar contract. A usable brief identifies the subject/style, proportions and defining features, required behavior and target platform. If a vague prompt leaves identity undefined, ask a small bundled set of questions before building. Do not ask the user to restate facts visible in the photo or answers already in the project. For prompt-only work, establish a visual master before detailed 3D authoring; generated views remain proposals until reviewed.

Keep all requested capabilities in the contract: expressive face/display and speech, animation/interrupt/reset, hands, full-body input, clothing/secondary physics, props and requested platform variants. Mark a capability not applicable only with a reason tied to this character; missing hardware leaves its runtime test unverified, not silently removed.

## Learn from actual assets before choosing the implementation

Read existing authorized avatar-study results before commissioning another investigation. Select only evidence relevant to the current problem. Learn construction and behavior from accessible source assets and their licenses; permission to study a package does not automatically permit copying its meshes, textures or redistribution.

Each reusable recipe needs: source/version/hash and object or asset, observed mechanism, evidence level (static/native/build/client), unresolved assumptions, the smallest original reproduction, and its acceptance test. Retain those study cards in the authorized project. Promote a recipe from observation to reusable implementation only after the original reproduction works. Do not turn an attractive screenshot or package inventory into a proven authoring method.

Useful mechanisms observed in reference-avatar studies, to reproduce and verify on one's own assets:

| Mechanism | Apply it | Verify it |
| --- | --- | --- |
| Platform variants can share a rig and facial data while changing garments and geometry | Derive PC/mobile branches from one source and declare which features must survive | Compare bone hierarchy, facial names and actual deltas, then deformation and final SDK builds; counts alone do not prove parity |
| Explicit facial reset clips restore properties | Trace input → parameter → controller → clip → mesh/property → reset, with one owner per property | Exercise entry, exit, interruption and retrigger on the original implementation |
| Modular clothing/menu/optimization declarations are resolved during build | Keep independently editable parts and explicit rig/dependency bindings | Inspect the effective built prefab; an empty source Descriptor field may be populated by a generator |
| A nominal mobile package can still reference PC assets | Resolve GUID/fileID and prefab dependencies before handing off a variant | Test the intended installation/import order and SDK build; filenames do not establish independence |

For artistic problems, inspect the actual relevant construction too: hair volume/cards and roots, topology and normals, garment folds, UVs and material maps. A controller study cannot supply a hair-modeling recipe. Record `unknown` when the source does not expose the relevant construction.

## Choose and prove a route before scaling it

Prefer an existing suitable, permitted source/component and a verified workflow; otherwise use a demonstrated native technique or an authorized 3D generator. Keep Blender/Unity for refinement and verification. Do not default to a generic loft/sweep generator merely because it is easy to script. Respect already-authorized provider and cost limits; changing the production route does not authorize a new paid job or asset upload.

Test the hardest identity-defining feature first, such as the head/hair or a distinctive garment. Produce one reversible candidate and the minimum useful matched views. Reuse the original input and compare actual pixels. Only expand the technique to the full avatar when it demonstrates the required likeness. A working skeleton is not justification to continue from a visibly wrong design.

Before each repair, record one concrete defect, its suspected cause and the change expected in the next render. After two targeted attempts without material visual improvement, **stop that method**: consult a relevant inspected asset, choose a different proven technique/source, or prepare a bounded alternative for any genuinely missing authorization. Adding more strands, polygons, render angles or textual rules is not a method change by itself. Preserve useful work; do not restart the whole avatar to repair one part.

Use one builder and one independent reviewer for the active uncertain feature when delegation helps. Parallelize genuinely separate tasks, not competing variants of the same unresolved shape. Send concise paths/hashes, the reference, defect and acceptance condition; avoid replaying the full chat or large logs. Render changed regions first, then one integrated comparison after successful repairs. Reread/retest unchanged evidence only when a dependency changed. Record available actual usage/cost and operation counts; never invent token savings.

## Make a 5–10% target testable

Treat a requested 5–10% error margin as a target to define and validate, never an automatic promise of 90–95% similarity. For camera/pose-aligned views, measure chosen visible dimensions or landmark relationships against the reference: `abs(candidate - reference) / abs(reference) × 100`. Record units/normalization, method and uncertainty. Target ≤5% and flag >10% for those selected nonzero quantities; do not apply the formula to an undefined aesthetic score, unreadable feature or unseen surface.

Numeric agreement cannot offset a wrong identity, missing feature, swapped side, substituted graphic, visible intersection or broken required behavior. These remain individual blockers. Keep the user's visual rejection controlling for the rejected revision. One image leaves hidden geometry inferred; a vague prompt needs clarification. Do not claim the overall margin has been reached without a declared benchmark and actual evidence across its required cases.

Use the [reference reconstruction review](reference-reconstruction.md) and command guard for appearance, then the [delivery contract](../assets/avatar-contract.template.json), [tracking/environment](tracking-environment.md), export readback, Unity/SDK and applicable client tests for completion. A recipe, one successful example or a passing helper test does not establish reliable one-image-to-complete-avatar production for future characters.
