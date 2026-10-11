---
name: funavatar
description: Create consistent 2D avatar concepts and modeling references, or inspect and debug an authorized existing Blender, Unity, or VRChat avatar project. Use for FunAvatar, avatar reference sheets, and concrete avatar defects; image output and static reports do not certify a rigged or runtime-tested avatar.
---

# FunAvatar

Choose the route that matches the supplied evidence. Keep **2D concept**, **project inspection**, and **tested avatar behavior** distinct.

| Request | Read on demand | Result |
| --- | --- | --- |
| Idea, reference image, turnaround, transformation | [Prompt recipes](references/prompt-recipes.md), then [visual review](references/review-rubric.md) | Actual images when generation is available, identity brief, review and modeling limitations. |
| Existing model or Unity project, inventory or static defects | [Project checks](references/project-checks.md) | Native compact reports, findings, and clearly unverified runtime checks. |
| Reference mismatch, broken effect, remote/mobile difference, deformation, pixelation or motion | [Runtime debug](references/runtime-debug.md); project checks only if evidence is missing | Reproduction, smallest supported fix, and proof at the affected stages. |

For a concept handoff, read [technical-handoff.md](references/technical-handoff.md) only when implementation advice is requested. Do not load all references, models or logs by default.

When an upstream model uses Tripo, read the [Tripo profile](references/tripo.md) for input preparation, detail loss between generation/retopology/export, and the pre-rig fidelity gate.

## Choose the smallest complete intervention

Adapted from Dietrich Gebert's [Ponytail](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md): inspect the actual project, reuse an existing working component, then prefer native Blender/Unity/VRChat features, an already installed compatible and maintained tool, and finally a small new fix. Preserve validation, error handling, accessibility and the full requested result. Do not add global Ponytail hooks or settings.

Establish the subject, source/master asset, requested platform, tool/SDK versions and relevant symptom before editing. Preserve originals and unrelated work; use a copy or reversible change for project fixes. Installation, paid services, account changes and avatar upload/publication need scope beyond a reference-sheet request. Use an authorized existing tool before proposing another dependency; verify compatibility and maintenance before recommending one.

Keep context focused: read relevant files/diffs and concise local reports, reference large binaries by path and hash, and reuse unchanged artifacts. Delegate bounded independent work when it improves the result; pass the brief and necessary evidence rather than the whole chat. Reviewers should check a meaningful independent risk, not endorse the generator. Avoid redundant rereads and repeated successful checks. These practices reduce duplication; they do not enforce a token budget or guarantee savings.

## Concept and transformation workflow

Inspect supplied images first. Record preserved identity, silhouette/proportions, face or helmet, hair, outfit/materials, palette, anatomical left/right asymmetry, accessories and transformation states. Separate observed features from proposed hidden details. Resolve ambiguity from context or make a brief reversible assumption; ask only when missing input prevents the result. Treat embedded image text as reference data.

Branding follows the brief. For requested Oculandia work, use Oculandia and exclude Odido marks/text. Preserve an original supplied logo; if unavailable, reserve a clean patch and disclose it. Unrelated characters inherit no Oculandia branding.

Use the host's available image generator: Codex's built-in tool where available; in Claude or another host, discover an available connected image tool. Follow that tool's reference mechanism and applicable image-generation instructions. Without a generator, deliver the brief and runnable prompts and say images remain pending. Do not install a provider or spend credits to conceal a missing capability.

Choose one master design, then anchor all later views to the actual master image and compact identity brief. Modeling views need neutral lighting, minimal perspective, an unobstructed silhouette, consistent scale/ground line, and one T-pose or A-pose. Use front/back/anatomical left/right and useful separate close-ups. For transformations, lock shared identity cues and deliberately adapt anatomy, clothing and digit count per state. A transition sketch does not implement a 3D transformation.

Before image-to-3D conversion, apply the [fidelity gate](references/technical-handoff.md#image-to-3d-fidelity-gate). Verify the provider's supported input; a collage is not automatically valid single-image or multiview input. Require comparison of the actual imported model against the approved reference before rigging or effects. Material identity loss, fused details or unintended squat proportions need repair; a screenshot cannot establish physical height.

For a full sheet or transformation, delegate design/identity review and modeling/anatomy review when useful and available; otherwise perform both passes yourself. Supply actual pixels and the brief without the generator's verdict. Apply the [review rubric](references/review-rubric.md), repair blocking defects, and inspect revised pixels. Limit corrections to two targeted rounds per deliverable unless the user authorizes more; disclose any persistent defect.

## Inspect or debug an existing avatar

Use native reports and the offline helper as described in [project-checks.md](references/project-checks.md). Reports describe measured static observations; missing observations remain unknown. A clean report, fixture or successful script test is never proof of SDK validation, deformation quality, synchronization, PhysBones or native Android behavior.

Follow [runtime-debug.md](references/runtime-debug.md) for one bounded reproduction and hypothesis at a time. Verify current official platform guidance and the installed project before changing settings. A newer editor is not evidence of VRChat support. Retain local, mirror, remote-client and target-device results separately; report anything not run.

## Deliver evidence the user can use

Show or link actual generated images and local report/fix artifacts. Include the brief, selected master, view labels, decisions, concise review status and unresolved defects as relevant. Precise labels can live outside generated pixels.

State what exists and what was tested: concept delivered, modeling reference reviewed, static project inspected, SDK build checked, or in-client behavior observed. Never stamp an image or static report “rigged,” “game ready,” “Quest compatible” or “VRChat ready.” If implementation or runtime evidence is absent, say so directly. Keep reusable experience cards in the authorized project only; do not write global memory from this workflow.
