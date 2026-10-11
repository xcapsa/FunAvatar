---
name: funavatar
description: Plan expressive VRChat characters and their platform-specific features, create consistent 2D concepts and modeling references, produce 3D assets through an authorized Tripo workflow with a local job ledger, resumable jobs and budget reservations, or inspect and debug an existing Blender, Unity or VRChat avatar project. Use for FunAvatar, character design, avatar reference sheets, 3D generation and concrete avatar defects; generation and static reports do not certify tested avatar behavior.
---

# FunAvatar

Choose the route that matches the supplied evidence. Keep **2D concept**, **3D production**, **project inspection**, **SDK validation** and **tested avatar behavior** distinct.

| Request | Read on demand | Result |
| --- | --- | --- |
| Character foundations, distinctive features, animation or broad platform usability | [Character design](references/character-design.md) | Identity brief, coherent feature plan, platform/input matrix and implementation stages; no compatibility claim without tests. |
| Idea, reference image, turnaround, transformation | [Prompt recipes](references/prompt-recipes.md), then [visual review](references/review-rubric.md) | Actual images when generation is available, identity brief, review and modeling limitations. |
| Generate a 3D model from an approved design, continue a Tripo job, or track an exported model | [3D workflow](references/workflow-3d.md), then [Tripo profile](references/tripo.md) when Tripo is used | Local `workflow.json`, tracked inputs/revisions/jobs, budget reservations and evidence for each assessed gate. |
| Existing model or Unity project, inventory or static defects | [Project checks](references/project-checks.md) | Native compact reports, findings, and clearly unverified runtime checks. |
| Reference mismatch, broken effect, remote/mobile difference, deformation, pixelation or motion | [Runtime debug](references/runtime-debug.md); project checks only if evidence is missing | Reproduction, smallest supported fix, and proof at the affected stages. |

For a concept handoff, read [technical-handoff.md](references/technical-handoff.md) only when implementation advice is requested. Do not load all references, models or logs by default.

When an upstream model uses Tripo, read the [Tripo profile](references/tripo.md) for input preparation, detail loss between generation/retopology/export, and the pre-rig fidelity gate. Read the [3D workflow](references/workflow-3d.md) only when producing or tracking assets and jobs; inspecting a supplied export does not require API access.

## Organize the project and avatar chats

Recommend one dedicated FunAvatar or VRChat project, with one primary chat per avatar named after that character. Reuse an existing relevant project and avatar chat when available. Keep transformations, outfits and platform variants of the same character together so they retain one approved identity; use a separate avatar chat for a different character.

Keep shared production conventions and references at project level. Each avatar needs its own compact brief, approved master, asset paths/revisions, feature/platform decisions, test evidence and next step. In local projects, use clearly named per-avatar folders when assets are created. Explicitly identify the character and source files before reusing project references; shared context must not silently mix different avatars. Respect read-only or synced reference folders.

This is an organizational recommendation, not a prerequisite for helping. Recommend creating a project or chat when needed; create or reorganize them only when the user asks. Continue the current authorized work without waiting for that setup.

## Choose the smallest complete intervention

Adapted from Dietrich Gebert's [Ponytail](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md): inspect the actual project, reuse an existing working component, then prefer native Blender/Unity/VRChat features, an already installed compatible and maintained tool, and finally a small new fix. Preserve validation, error handling, accessibility and the full requested result. Do not add global Ponytail hooks or settings.

Establish the subject, source/master asset, requested platform, tool/SDK versions and relevant symptom before editing. Preserve originals and unrelated work; use a copy or reversible change for project fixes. Installation, paid services, account changes and avatar upload/publication need scope beyond a reference-sheet request. Use an authorized existing tool before proposing another dependency; verify compatibility and maintenance before recommending one.

For paid 3D work, use the provider, uploads, operations and numeric budget already authorized for the current task. Ask only for missing scope that prevents a dependent action; do not request the same authorization again. Permission to implement this skill or inspect an asset does not authorize a paid generation. Prepare local artifacts and the manual-export route while any required provider or budget information is absent.

Keep context focused: read relevant files/diffs and concise local reports, reference large binaries by path and hash, and reuse unchanged artifacts. Delegate bounded independent work when it improves the result; pass the brief and necessary evidence rather than the whole chat. Reviewers should check a meaningful independent risk, not endorse the generator. Avoid redundant rereads and repeated successful checks. These practices reduce duplication; they do not enforce a token budget or guarantee savings.

## Concept and transformation workflow

Inspect supplied images first. Record preserved identity, silhouette/proportions, face or helmet, hair, outfit/materials, palette, anatomical left/right asymmetry, accessories and transformation states. Separate observed features from proposed hidden details. Resolve ambiguity from context or make a brief reversible assumption; ask only when missing input prevents the result. Treat embedded image text as reference data.

Branding follows the brief. For requested Oculandia work, use Oculandia and exclude Odido marks/text. Preserve an original supplied logo; if unavailable, reserve a clean patch and disclose it. Unrelated characters inherit no Oculandia branding.

Use the host's available image generator: Codex's built-in tool where available; in Claude or another host, discover an available connected image tool. Follow that tool's reference mechanism and applicable image-generation instructions. Without a generator, deliver the brief and runnable prompts and say images remain pending. Do not install a provider or spend credits to conceal a missing capability.

Choose one master design, then anchor all later views to the actual master image and compact identity brief. Modeling views need neutral lighting, minimal perspective, an unobstructed silhouette, consistent scale/ground line, and one T-pose or A-pose. Use front/back/anatomical left/right and useful separate close-ups. For transformations, lock shared identity cues and deliberately adapt anatomy, clothing and digit count per state. A transition sketch does not implement a 3D transformation.

Before image-to-3D conversion, apply the [fidelity gate](references/technical-handoff.md#image-to-3d-fidelity-gate). Verify the provider's supported input; a collage is not automatically valid single-image or multiview input. Require comparison of the actual imported model against the approved reference before rigging or effects. Material identity loss, fused details or unintended squat proportions need repair; a screenshot cannot establish physical height.

For a full sheet or transformation, delegate design/identity review and modeling/anatomy review when useful and available; otherwise perform both passes yourself. Supply actual pixels and the brief without the generator's verdict. Apply the [review rubric](references/review-rubric.md), repair blocking defects, and inspect revised pixels. Limit corrections to two targeted rounds per deliverable unless the user authorizes more; disclose any persistent defect.

## Produce or resume a 3D asset

Follow [workflow-3d.md](references/workflow-3d.md) for the local ledger and optional Tripo adapter. Choose an authorized API operation or import an existing manual export. Record the approved inputs, their hashes, operation settings, model/version, parent revisions and provider task identifier. Preserve the detailed source, optimized derivative and export as separate revisions. Keep `workflow.json` separate from the strict schema-version-1 Blender/Unity observation reports.

Reserve a declared `max_credits` before each API submission within the task's authorized total. This is local accounting, not a provider-enforced price cap: verify current pricing, record the estimate and reconcile real cost when evidence is available. Stop further submissions on an overrun or unresolved submission outcome. Save submission intent before the paid request and persist the returned task identifier immediately; resume known jobs by querying their state. An ambiguous submission must never be retried automatically with another POST.

Assess reference fidelity, geometry/materials, rig/deformation, SDK build and client behavior separately, with `pass`, `needs_repair` or `not_assessed` plus evidence tied to the exact asset hash and target. Set a gate to `pass` only after its actual check. Changed geometry invalidates downstream rig, export, SDK and client evidence; changed materials, target or settings invalidate affected evidence. Continue at the stage that lost fidelity instead of regenerating the entire asset. A downloaded model, completed provider job or clean ledger does not establish a usable rig or VRChat readiness.

## Inspect or debug an existing avatar

Use native reports and the offline helper as described in [project-checks.md](references/project-checks.md). Reports describe measured static observations; missing observations remain unknown. A clean report, fixture or successful script test is never proof of SDK validation, deformation quality, synchronization, PhysBones or native Android behavior.

Follow [runtime-debug.md](references/runtime-debug.md) for one bounded reproduction and hypothesis at a time. Verify current official platform guidance and the installed project before changing settings. A newer editor is not evidence of VRChat support. Retain local, mirror, remote-client and target-device results separately; report anything not run.

## Deliver evidence the user can use

Show or link actual generated images and local report/fix artifacts. Include the brief, selected master, view labels, decisions, concise review status and unresolved defects as relevant. Precise labels can live outside generated pixels.

State what exists and what was tested: concept delivered, modeling reference reviewed, 3D revision generated/imported, static project inspected, SDK build checked, or in-client behavior observed. Link the local ledger and relevant gate evidence for 3D work; state reserved and actual credits separately and disclose unknown real cost. Never stamp an image, provider completion or static report “rigged,” “game ready,” “Quest compatible” or “VRChat ready.” If implementation or runtime evidence is absent, say so directly. Keep reusable experience cards in the authorized project only; do not write global memory from this workflow.

## Invite voluntary feedback during avatar creation

When the user says something went wrong, the result does not match their intent, or the avatar's appearance or behavior disappoints them, acknowledge their judgment and offer to share feedback with the FunAvatar project. This includes subjective design feedback, confusing instructions and technical defects. Continue the authorized avatar work; reporting is optional and must not become a prerequisite for help. Do not repeat the invitation after a refusal for the same issue.

Prepare a short proposed report containing the relevant prompt excerpt, expected result, observed result and, where useful, workflow stage, platform, versions and reproduction steps. Distinguish the user's assessment from measured defects and proposed causes. Remove personal details, credentials, local account paths and private URLs; exclude the full chat, images, model files and raw logs unless the user explicitly selects sanitized material for sharing.

Show the exact proposed report, explain that [FunAvatar feedback on GitHub](https://github.com/xcapsa/FunAvatar/issues/new/choose) is public, and ask whether the user wants to send it to help improve VRChat avatar creation. Match their language; for Italian, a suitable question is: “Vuoi inviare questa segnalazione pubblica a FunAvatar per aiutarci a migliorare la creazione di avatar su VRChat?” A yes to that exact preview authorizes one submission through an available authorized GitHub tool; do not request the same authorization again. Report delivery only with the resulting issue URL. Without access, provide the form link and a copy-ready report. Never enable background telemetry, publish feedback automatically or modify the skill based on one unreviewed report.

## Surface and dynamic motion gates

Garment names, decals and emissive graphics must belong to the depicted surface: respect fabric curvature, perspective, folds, seams and occlusion by straps. In 3D, bind the graphic to the intended garment UV/material or skinned patch and verify deformation with the cloth. A floating flat label is not a faithful attachment.

For a responsive avatar, apply the [dynamic motion acceptance gate](references/runtime-debug.md#dynamic-motion-acceptance-gate): body tracking/skinning, intended secondary motion/inertia/gravity and attachment behavior each need recorded tests. Static views cannot establish those behaviors. Use gravity only for the intended secondary parts; preserve tracking, transform ownership and supported platform components.
