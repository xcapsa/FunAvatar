# Runtime debug

Use this route for a concrete defect in an authorized avatar project. Without a model, Unity project or runtime evidence, produce an unexecuted plan and identify the missing stage. Do not diagnose an unseen rig or claim a working effect from concept art.

## One reproducible change

1. Record the exact avatar/project revision or asset hash, Unity/Blender/SDK/package versions, platform, expected behavior and shortest reproduction. Obtain a compact native report only if relevant evidence is missing; see [project checks](project-checks.md).
2. Inspect the existing working implementation and native settings before adding code or packages. Make one falsifiable hypothesis and one reversible change on a copy or protected revision. Preserve accepted identity, validation and unrelated work.
3. Compare the same reproduction before/after. Check the edited native stage, SDK validation/build, then the relevant client observations below. Record evidence paths and unrun checks. Fixing a reported symptom does not prove unrelated features work.

Use `debug-plan` from [project checks](project-checks.md) for a local checklist. Its files begin unexecuted. Complete only checks actually observed; preserve failures and unknowns. Limit a task to two targeted correction rounds unless the user authorizes more, then return the useful result with remaining uncertainty.

## Targeted checks

| Symptom | Inspect before proposing a fix | Proof needed |
| --- | --- | --- |
| Model loses reference identity or looks squat/undetailed | Provider input requirements and supported view count; clean character inputs versus collage; actual mesh/texture exports, units/transforms and intended proportions. Apply the [fidelity gate](technical-handoff.md#image-to-3d-fidelity-gate) before rigging/effects. | Neutral front/back/side comparison of the imported model; distinguish geometry, baked textures and light. Measure engine height against the brief; screenshot framing is insufficient. |
| Effect/toggle/expression | Correct Descriptor controller and FX slot; binding paths after renames; active object/component; layer weights, masks and competing clips; shader properties and reset states. | Repeated off→on→off; interruption/re-entry and avatar reset; local view and mirror; remote client when observable to others. |
| Works locally, fails remotely | Menu → Expression Parameters → Animator names/types/defaults; synced setting, current parameter budget and drivers; `IsLocal` branches; persistent states versus brief triggers. PC/Android synchronization matches list position and type; prefer the same Expression Parameters asset. | A second client observes initial state, changes, late join and reset. Local mirror is separate evidence. |
| PC works, Android fails | Actual Android build target/module, platform overrides, allowed components/shaders, material slots, textures, SDK/performance warnings; compare intended cross-platform avatar versions. | SDK validation/build for Android plus a native Android/Quest client. PCVR through a Quest headset proves the PC path only. |
| Bad joints/deformation | Rest/bind pose, scale/transforms, armature assignment, Unity humanoid mapping and T-pose; vertex weights and joint topology; conflicting animation/IK/constraints. | Neutral pose and controlled shoulder/elbow/wrist/hip/knee bends in the relevant native tool, then tracking in client. |
| Faceted/pixelated appearance | Distinguish polygonal silhouette from surface shading (normals, smooth/sharp edges, tangents) and texture blur/blocking (UV density, source resolution, imported Max Size, per-platform compression/mipmaps). | Matching camera, light and distance before/after; close-up and silhouette. Smooth normals cannot add silhouette geometry; extra polygons cannot recover discarded texture detail. |
| Motion/clipping/disappearing | Clip bindings, masks, layer ownership, root motion/IK and interruption exits; skinned-mesh bounds/culling; PhysBone roots/endpoints, colliders, limits, component version and transform ownership. | Move/turn/crouch, extreme intended poses, camera edge/offscreen return, reset/reload; PhysBone rest, motion and allowed grab/pose interactions on the target client. |

For [Write Defaults](https://creators.vrchat.com/avatars/#write-defaults-on-states), inspect the controller's policy and explicit property resets; do not bulk-convert every state to Off. Current guidance includes additive-layer and direct-blend-tree exceptions. Preserve those intentional cases and verify behavior after any change. Counts or mixed-state warnings alone do not identify the faulty transition.

For [rig requirements](https://creators.vrchat.com/avatars/rig-requirements/), heed the page's out-of-date warning and historical SDK2 passages. Verify the active SDK, Unity mapping and actual tracking rather than applying obsolete finger/chest/hierarchy rules universally.

## Evidence and reuse

Keep separate results for Blender/Unity inspection, SDK validation/build, local client, mirror, remote client and native Android. Attach brief reproduction steps and relevant screenshots/short clips or scoped log excerpts, with platform and tool versions. Do not send entire projects/raw logs to agents or unrelated providers when a local report suffices.

With user-authorized project scope, save a small experience card beside the work:

```text
Source/revision or hash:
Tool + SDK/package versions and check date:
Platform/device:
Symptom and preconditions:
Smallest fix:
Before/after proof paths and checks actually run:
Limitations and checks still unverified:
```

A card is evidence for those conditions, not a universal rule. Recheck compatibility and changed assets before reuse. Do not update global memory or global Ponytail configuration.

## Official references

Read only the page needed for the symptom, and recheck current guidance before giving version or platform advice:

- [Current Unity version](https://creators.vrchat.com/sdk/upgrade/current-unity-version/): **2022.3.22f1**, verified 2026-10-11; recheck later.
- [Playable Layers](https://creators.vrchat.com/avatars/playable-layers/) and [Animator Parameters](https://creators.vrchat.com/avatars/animator-parameters/): ownership, mirror behavior and synchronization.
- [Android guides](https://creators.vrchat.com/platforms/android/) and [Performance Ranks](https://creators.vrchat.com/avatars/avatar-performance-ranking-system/): target-specific builds, limitations and measured categories.
- [PhysBones](https://creators.vrchat.com/common-components/physbones/) and [Unity 2022.3 Skinned Mesh Renderer](https://docs.unity3d.com/2022.3/Documentation/Manual/class-SkinnedMeshRenderer.html): motion setup and bounds/culling.
- [Unity 2022.3 Texture Import Settings](https://docs.unity3d.com/2022.3/Documentation/Manual/class-TextureImporter.html): source textures, imported settings and target-specific overrides.

These links support investigation; the installed project's validation and the observed client behavior provide the concrete proof.
