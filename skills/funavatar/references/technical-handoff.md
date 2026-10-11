# From concept to a tested avatar

FunAvatar's concept route produces 2D design and modeling references. Its project and debug routes inspect supplied assets and support authorized fixes. A sheet cannot establish that geometry, textures, rigging, or runtime features exist. Keep concept review, static inspection, SDK validation and client tests separate.

## Handoff notes

Give the modeler the selected master and labeled views, intended real-world scale if chosen, palette/material map, asymmetry, hidden construction decisions, and any transformation states. Mark undecided features explicitly. Do not present an AI-drawn wireframe as actual topology.

For a future 3D implementation, the remaining work includes mesh construction and deformation topology; UVs and textures; material setup; armature and skin weights; expressions or blendshapes if requested; export/import checks; SDK configuration; and local runtime testing. Features such as tails, cloth motion, eye tracking, lip sync or form switching need their own implementation and testing. A human-to-animal design may require major rig changes; it is not automatically a blendshape transformation.

Treat PC and mobile/Quest targets separately. Preserve the requested visual identity while planning simplifications for the actual platform. Do not promise a performance rank from a concept image or triangle count alone.

The implementation brief must include wearer-following body motion, intended prop attachment bones/constraints, garment-bound graphics and any optional secondary motion. Use the [dynamic motion acceptance gate](runtime-debug.md#dynamic-motion-acceptance-gate): rig/weights and actual tracking first, then the supported motion setup for hair, straps or other chosen parts. A reference pose or static mesh does not establish a moving avatar. Without the actual rig and client tests, keep dynamics `not_verified`; do not claim working gravity or tracking.

## Image-to-3D fidelity gate

Apply [reference reconstruction](reference-reconstruction.md) before production rigging or effects for **native Blender creation as well as imported/generated meshes**. It defines original-reference authority, blockout review, repair loops and the command guard. When a provider is selected, verify its current official input requirements and available settings; do not assume it supports multiview or understands a reference collage. Prepare clean, isolated character views with consistent proportions, plus separate head, hands and material references. Exclude grids, decorative labels, extra figures and “high-poly/game-ready” badges from conversion input. If only one view is supported, choose the appropriate clean character view and retain other references for comparison rather than feeding a collage by default.

Compare the **actual native or imported 3D model** in neutral light from front, back and both sides against the approved reference. Check silhouette and head/torso/leg ratios; helmet shape and markings; distinct chest plates; gloves and separated fingers; hair; outfit panels and material identity. Use suitable shaded, unlit/material and wireframe views to distinguish real geometry, baked texture illusions and lighting. Detail painted into a texture is not proof of modeled structure.

Record intended height from the user brief when known, measurement points, units/transforms and measured height in the actual engine. A generated ruler, camera framing or screenshot cannot establish physical height. For human/sloth or other transformations, record the intended height/proportion ratio explicitly rather than shrinking a state by assumption.

Mark the gate `pass`, `needs repair` or `not assessed`, with comparison evidence. Material identity loss, melted/fused details and unintended squat proportions block further rig/effect work until repaired or explicitly accepted by the user. Unobserved back/side details remain identified as inferences; never fabricate a missing view or claim fidelity for an unseen surface. This is a manual/tool-assisted visual gate; the helper does not automatically judge semantic fidelity and generative 3D does not guarantee a perfect match.

Keep the image-to-3D tool/provider, version, settings, input hashes, exported mesh/texture files and before/after comparison proof with the project. Without actual imported-model evidence, keep reference fidelity unverified. Use `debug-plan --symptom fidelity` for an unexecuted checklist; see [project checks](project-checks.md).

After conversion, retopology or a later mesh replacement, revalidate bone assignments, skin weights and deformation on the final imported mesh before motion acceptance. A prior rig check does not transfer automatically to changed geometry.

## Verify current official guidance

Consult these official pages at the time technical advice is given, link the pages supporting the advice, and record the check date. Do not hard-code Unity versions or numerical budgets from memory into the brief or reusable prompts.

- [Creating Your First Avatar](https://creators.vrchat.com/avatars/creating-your-first-avatar/): model import, configuration, build and testing workflow.
- [Current Unity Version](https://creators.vrchat.com/sdk/upgrade/current-unity-version/): supported editor version; use the current recommendation rather than “latest Unity.” This page specified **2022.3.22f1** when checked on 2026-10-11; recheck before future use. An installed Unity 6000.6 editor does not establish VRChat compatibility.
- [Rig Requirements](https://creators.vrchat.com/avatars/rig-requirements/): rig considerations. This page currently carries an out-of-date warning and includes historical SDK2 text; do not copy old finger, chest or hierarchy rules as universal current requirements. Verify against the active SDK, current Unity humanoid configuration, and runtime tests.
- [Performance Ranks](https://creators.vrchat.com/avatars/avatar-performance-ranking-system/): platform-specific categories and current thresholds. Distinguish rank recommendations, display behavior and enforced limits.
- [Avatar Optimization Tips](https://creators.vrchat.com/avatars/avatar-optimizing-tips/): implementation choices for the actual asset.
- [Avatar Size Limits](https://creators.vrchat.com/avatars/avatar-size-limits/): current asset size restrictions; verify the relevant target and units before quoting a number.

If a page is unavailable or its guidance conflicts with installed SDK behavior, report the uncertainty and use the SDK's actual validation output and a local test for the concrete project. A successful SDK build and an in-client test are separate evidence. Uploading or publishing an avatar requires the user's authorization for that external action; creating a reference sheet grants no such permission.

Official links checked 2026-10-11 for this skill. Recheck them for future technical advice; this date is not ongoing certification of compatibility.
