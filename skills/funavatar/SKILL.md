---
name: funavatar
description: Build, inspect and debug expressive avatar projects in Blender and Unity; learn construction techniques from authorized avatar packages, plan tracking and platform-specific physics, and create consistent 2D references. Use for FunAvatar, avatar reverse engineering, animation, hand/full-body tracking and concrete defects. Generators are optional; assets and static reports do not certify tested avatar behavior.
---

# FunAvatar

## Optional updates at the start of use

For explicitly read-only inspection or evaluation, skip the automatic update command because an existing opt-in could mutate the installation.

For a local Codex or Claude Code installation with Python 3.10+ and persistent filesystem access, run `python3 <this-skill-folder>/scripts/funavatar_update.py auto` once at the start of a new use, before production commands. Without an existing user opt-in it performs no network request or update. Do not enable updates merely because the skill was invoked. If the user asks to enable or disable them, follow [updates.md](references/updates.md) for the exact command and target scope.

If the result reports an update, reread `SKILL.md` and the relevant resources at the returned installed path before proceeding. Keep updates outside an ongoing production operation; do not interrupt another active avatar workflow to update its tools. On a deferred update, continue with the current installation and state the specific limitation when relevant. Never bypass local-change protection or execute an installer from a downloaded package during an automatic update; an explicitly requested manual bootstrap from a verified ZIP is a separate route. In hosts without a usable local Python/filesystem route, explain the manual import path instead of claiming automatic updates. This feature runs when the skill is used; it is not a background service or an update to already-loaded chat instructions.

Choose the route that matches the supplied evidence. Keep **2D concept**, **3D production**, **project inspection**, **SDK validation** and **tested avatar behavior** distinct.

| Request | Read on demand | Result |
| --- | --- | --- |
| Character foundations, distinctive features, animation or broad platform usability | [Character design](references/character-design.md) | Identity brief, coherent feature plan, platform/input matrix and implementation stages; no compatibility claim without tests. |
| Idea, reference image, turnaround, transformation | [Prompt recipes](references/prompt-recipes.md), then [visual review](references/review-rubric.md) | Actual images when generation is available, identity brief, review and modeling limitations. |
| Reproduce a supplied photo/design, or correct a likeness mismatch | [Reference reconstruction](references/reference-reconstruction.md), then native production | Reference-led geometry and materials, comparable model renders and a current fidelity review before production rigging. |
| Build or repair the actual 3D character, rig and animations | [Native production](references/native-production.md), then [tracking/environment](references/tracking-environment.md) for responsive behavior | Editable Blender source and actual Unity assets/exports, native readback and distinct tracking/runtime proof. |
| Select another production tool, use an optional generator, or track an imported model | [Production tools](references/production-tools.md), then [3D workflow](references/workflow-3d.md); [Tripo profile](references/tripo.md) only when selected | Provider-neutral source/export handoff and local revision ledger; only the selected adapter's operations are used. |
| Existing model or Unity project, inventory or static defects | [Project checks](references/project-checks.md) | Native compact reports, findings, and clearly unverified runtime checks. |
| Blender avatar about to go to Unity, or matched views for a likeness review | [VRChat export-readiness checks](references/project-checks.md#vrchat-export-readiness-checks-and-comparison-renders) | Read-only checks for transforms, leaf bones, Humanoid roles, modifiers vs shape keys, weights and first-person Head isolation; orthographic comparison sheet. |
| Understand how an existing avatar is built, reverse engineer a feature, or transfer a construction technique | [Avatar study](references/avatar-study.md), then the relevant native route | Package/GUID evidence, native anatomy observations, a causal feature trace and an original tested implementation; source inventory is not runtime proof. |
| Coordinated Blender/Unity work, MCP selection, facial shapes or modular integration | [Agent pipeline](references/agent-pipeline.md) | Source-inspected capabilities, actual local discovery, measured facial deltas and separate build/publication evidence. |
| Measured performance or custom-parameter budgets | [Performance budgets](references/performance-budgets.md) | Offline checks of supported metrics and synced bits, with missing observations and SDK/runtime status explicit. |
| OSC parameters, face-mode controls or runtime bridge planning | [OSC runtime](references/osc-runtime.md) | Read-only config inspection and typed set/reset packet plans; no network or social messages from the bundled planner. |
| Broken effect, remote/mobile difference, deformation, pixelation or motion | [Runtime debug](references/runtime-debug.md); project checks only if evidence is missing | Reproduction, smallest supported fix, and proof at the affected stages. |

For a concept handoff, read [technical-handoff.md](references/technical-handoff.md) only when implementation advice is requested. Do not load all references, models or logs by default.

Native Blender/Unity authoring and verification are the default for requested 3D creation; choose the source/base and construction method through the production strategy first. Use available MCP, CLI or application interfaces and focused native scripts; a missing MCP alone does not justify stopping at prompts. Read [production tools](references/production-tools.md) only when choosing a tool or interchange route. Tripo, Meshy, Rodin and suitable local generators are optional, subject to actual access, licenses and supported handoffs. When Tripo is selected, read its profile and job workflow; no provider is mandatory and no other provider's job may be sent to the Tripo adapter.

## Start with a clear brief and a proven construction route

Accept an image, a sufficiently specific prompt, or both. Read [production strategy](references/production-strategy.md) before authoring a new avatar or repeating failed likeness repairs. Ask only for missing decisions that change the design, required behavior or platform; reuse answers already given. Select an inspected, permitted base/component or a demonstrated modeling method before generating geometry. Blender/Unity are the authoring and verification environments; that does not require inventing every organic surface with procedural scripts. After two targeted attempts without material visual progress, stop that approach and change the construction route. Preserve the fidelity hold and completed evidence; do not keep spending on variants of the same failed shape.

## Required moving-avatar result

When reproducing a supplied image, default to **faithful reconstruction**, not a new design inspired by its theme. Read [reference reconstruction](references/reference-reconstruction.md) before writing geometry code. Inspect all supplied views, preserve original references above generated interpretations, and bind observed features to concrete modeling choices. The actual blockout and refined model must pass a visual comparison before production rigging, animation, optimization or Unity avatar assembly. Provisional posing for comparison is allowed. Use the fidelity preflight/command guard described there; technical tests cannot substitute for likeness. A user-rejected result remains on fidelity hold until the defect is repaired and reviewed; do not quietly relabel it an interpretation.

For an actual avatar request, use the [native production](references/native-production.md) and [tracking/environment](references/tracking-environment.md) routes. Preserve an editable source with refined mesh, UV/materials, deforming rig/weights, actual requested actions and a Unity prefab/controller when that target is available. Images, static exports, primitive mannequins and the native smoke fixture are not the requested finished character. Distinguish unintended boxy silhouette, faceted normals and texture artifacts; intentional hard armor and quad topology are not defects by themselves.

Start a per-avatar contract from [the template](assets/avatar-contract.template.json), recording required animation coverage, actual hand/FBT input routes, target platforms, attachments and intended physics. Track idle/locomotion, turn, sit/crouch, hands/face, requested props and all transitions/interruption/reset paths. Do not silently drop requested hand tracking or FBT when hardware is missing; keep their evidence unverified and specify the real setup required. Every animation override must restore intended tracking.

Garments first follow body deformation, then supported secondary chains may add gravity/inertia/collision. Wind/water are separate environment-dependent features: document the world/app signal and simulation path, with explicit fallback when absent. Do not promise automatic forces in every VRChat world or use unsupported avatar scripts/components. Static art or a recorded pose cannot pass tracking, environmental response or dynamic-motion gates.

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

Build natively through [native-production.md](references/native-production.md) unless the user chooses another route. The [3D workflow](references/workflow-3d.md) can track native/imported files with a zero-credit ledger; its Tripo adapter is optional. Record the approved inputs, hashes, native scripts/settings, tool or provider version, parent revisions and any real provider task identifier. Preserve editable source, optimized derivative and export as separate revisions. Keep `workflow.json` separate from strict Blender/Unity observation reports and the temporary native toolchain fixture.

Reserve a declared `max_credits` before each API submission within the task's authorized total. This is local accounting, not a provider-enforced price cap: verify current pricing, record the estimate and reconcile real cost when evidence is available. Stop further submissions on an overrun or unresolved submission outcome. Save submission intent before the paid request and persist the returned task identifier immediately; resume known jobs by querying their state. An ambiguous submission must never be retried automatically with another POST.

Assess reference fidelity, geometry/materials, rig/deformation, SDK build and client behavior separately, with `pass`, `needs_repair` or `not_assessed` plus evidence tied to the exact asset hash and target. Set a gate to `pass` only after its actual check. Changed geometry invalidates downstream rig, export, SDK and client evidence; changed materials, target or settings invalidate affected evidence. Continue at the stage that lost fidelity instead of regenerating the entire asset. A downloaded model, completed provider job or clean ledger does not establish a usable rig or VRChat readiness.

When using external MCP tools, discover their actual schema and consult the [capability registry](assets/mcp-capability-registry.json) for pinned source findings. Never pass an SDK, export or facial gate from a positive stub, a pre-build callback, an empty generated shape or an outer success containing failed children. Capture native output and read it back. The registry is source research, not an installation or runtime attestation.

## Inspect or debug an existing avatar

For unfamiliar avatar packages, prefab assembly or a request to learn/transfer a feature, start with [avatar study](references/avatar-study.md), including questions about apparently missing components or menus. Inspect the package offline before importing unfamiliar Unity content, select one behavior to trace, and reconstruct its mechanism on an original small probe. Keep third-party assets and study-specific evidence in the authorized project; add only reusable methods to the skill. Preserve the current reference-fidelity and dynamic-motion gates when applying a lesson to production.

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
