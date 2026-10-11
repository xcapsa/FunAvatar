# From concept to a tested avatar

FunAvatar currently produces 2D design and modeling references. A sheet can guide modeling but cannot establish that geometry, textures, rigging, or runtime features exist. Keep concept review separate from implementation validation.

## Handoff notes

Give the modeler the selected master and labeled views, intended real-world scale if chosen, palette/material map, asymmetry, hidden construction decisions, and any transformation states. Mark undecided features explicitly. Do not present an AI-drawn wireframe as actual topology.

For a future 3D implementation, the remaining work includes mesh construction and deformation topology; UVs and textures; material setup; armature and skin weights; expressions or blendshapes if requested; export/import checks; SDK configuration; and local runtime testing. Features such as tails, cloth motion, eye tracking, lip sync or form switching need their own implementation and testing. A human-to-animal design may require major rig changes; it is not automatically a blendshape transformation.

Treat PC and mobile/Quest targets separately. Preserve the requested visual identity while planning simplifications for the actual platform. Do not promise a performance rank from a concept image or triangle count alone.

## Verify current official guidance

Consult these official pages at the time technical advice is given, link the pages supporting the advice, and record the check date. Do not hard-code Unity versions or numerical budgets from memory into the brief or reusable prompts.

- [Creating Your First Avatar](https://creators.vrchat.com/avatars/creating-your-first-avatar/): model import, configuration, build and testing workflow.
- [Current Unity Version](https://creators.vrchat.com/sdk/upgrade/current-unity-version/): supported editor version; use the current recommendation rather than “latest Unity.”
- [Rig Requirements](https://creators.vrchat.com/avatars/rig-requirements/): rig considerations. This page currently carries an out-of-date warning and includes historical SDK2 text; do not copy old finger, chest or hierarchy rules as universal current requirements. Verify against the active SDK, current Unity humanoid configuration, and runtime tests.
- [Performance Ranks](https://creators.vrchat.com/avatars/avatar-performance-ranking-system/): platform-specific categories and current thresholds. Distinguish rank recommendations, display behavior and enforced limits.
- [Avatar Optimization Tips](https://creators.vrchat.com/avatars/avatar-optimizing-tips/): implementation choices for the actual asset.
- [Avatar Size Limits](https://creators.vrchat.com/avatars/avatar-size-limits/): current asset size restrictions; verify the relevant target and units before quoting a number.

If a page is unavailable or its guidance conflicts with installed SDK behavior, report the uncertainty and use the SDK's actual validation output and a local test for the concrete project. A successful SDK build and an in-client test are separate evidence. Uploading or publishing an avatar requires the user's authorization for that external action; creating a reference sheet grants no such permission.

Official links checked 2026-10-11 for this skill. Recheck them for future technical advice; this date is not ongoing certification of compatibility.
