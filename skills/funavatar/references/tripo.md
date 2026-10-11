# Tripo: tracked 3D production and reference fidelity

Read this profile only when the supplied model or requested generation uses Tripo. Public guidance checked 2026-10-11; verify the actual Studio mode/version and available controls before an operation. A paid subscription does not establish which settings produced a model, access to every feature, or reference fidelity. Do not spend credits, upload references or install a bridge merely to inspect a supplied result.

For generation, job resumption or tracked manual exports, read [workflow-3d.md](workflow-3d.md) for the ledger and optional adapter commands. For inspection of an existing result, use only the relevant gates below. The API adapter is optional; a manual export can enter the same ledger and review workflow without sending a new paid request.

## Choose an authorized route

**Manual export:** preserve the supplied original, record its source/task information when known and hash the actual file. Mark absent provider settings or costs as unknown. A file supplied by the user establishes an asset to inspect, not permission to access their account or regenerate it.

**API:** use the official endpoint supported by the installed adapter and verify the requested operation and current model/version before submission. Studio features are not automatically API features. Supply the API key through the adapter's documented environment variable, never a command argument, ledger, report or committed file. Use the provider/uploads/operations and numeric budget already authorized for this task; implementing the adapter alone does not authorize real usage.

Record every paid operation separately with its prepared inputs, hashes, request parameters, `max_credits` reservation and eventual `task_id`. Reserve before POST, persist intent before sending, and save the returned identifier immediately. Resume a known task through read-only status queries. If the request may have reached the provider but no identifier was saved, record the uncertainty, retain the reservation and reconcile from provider evidence; never send a replacement POST automatically.

The local reservation limits admission of jobs against the ledger's authorized total. It cannot enforce Tripo's actual charge without an independent provider cap. Verify the current charge or a conservative estimate for the selected operation; do not infer price from a plan name. Record actual cost only with provider evidence. Keep unknown or uncertain cost reserved, and stop new submissions on a detected overrun until the authorized budget and ledger are reconciled.

## Input gate

Use a single isolated complete character on a plain background with even light. Tripo's [input-quality guide](https://www.tripo3d.ai/help/features/how-to-get-better-image-to-3d-results) recommends a large centered subject with clear margins and adequate native resolution, and warns that multiple subjects can merge into one mesh. A decorative turnaround board with four figures, hand studies, labels and a grid is not a clean single-image input. Enlarging a small figure cropped from that board does not recover missing detail.

Prepare independent approved views if the selected workflow supports multi-view. Keep outfit, anatomy, pose, scale and lighting consistent; label anatomical sides outside the pixels. Inspect any generated unseen view before using it: an inferred back is a proposed design. [Tripo's feature guide](https://www.tripo3d.ai/help/getting-started/what-features-does-tripo-have) documents multi-view, but current controls and image-count limits must be checked in the selected interface; batch upload and multi-view are different operations.

## Locate the stage that lost detail

Record the model/task identifier locally, generation mode/version, original input, topology target, texture settings and each exported revision in `workflow.json`. Connect each revision to its actual file hash and parent revisions; attach evidence to the revision assessed. Compare the original generated mesh, any retopologized mesh and the imported engine result rather than repeatedly regenerating everything.

The [Image-to-3D guide](https://www.tripo3d.ai/help/features/how-to-use-the-image-to-3d-feature) distinguishes **Best Quality / HD Model** from **Clean Topology / Smart Mesh**. The [Smart Mesh guide](https://www.tripo3d.ai/help/features/what-is-smart-mesh) describes a lightweight structured mesh versus a detailed source. Choose the stage for the actual task: inspect a cheap shape test if one already exists; preserve a detailed master when needed; derive the real-time mesh only after the silhouette and defining features are accepted. No fixed polygon count guarantees either fidelity or VRChat performance.

Inspect solid/untextured, wireframe and textured views under comparable neutral lighting. Require readable silhouette, proportions, helmet/face markings, distinct armor or chest plates, gloves/digits, hair and garment construction. A painted line, shiny normal effect or enlarged texture cannot replace missing silhouette geometry. Compare each relevant region against the approved reference; persistent material identity loss, fused fingers or unintended proportions fail the [fidelity gate](technical-handoff.md#image-to-3d-fidelity-gate).

Measure intended height in engine units with transforms/import scale recorded. A screenshot's camera, pose and surrounding furniture cannot certify physical height. Keep the human/transformed height relationship explicit if the brief specifies one.

## Finish geometry, then validate rig and export

Keep a reversible original before mesh edits or retopology. Tripo's [OpenAPI conversion documentation](https://docs.tripo3d.ai/export/conversion.html) explicitly warns that remeshing operations do not retain skeletal data. This API statement is not proof of an identical Studio control: inspect the actual exported mesh, bones, weights and animations after processing, and redo affected rigging when necessary.

Use separate gates for reference fidelity, geometry/materials, rig/deformation, SDK validation and client behavior. Each is `pass`, `needs_repair` or `not_assessed`; evidence must name the actual revision, target and relevant settings. Changed geometry invalidates downstream rig, export, SDK and client evidence. Any changed material, target or setting invalidates the checks it affects. A previous pass remains historical evidence for its original revision only.

For an animated asset, verify that the chosen export includes the intended skeleton and that all material/texture files reach Blender and Unity. Reopen the export, compare scale and visible detail, then run the targeted deformation, SDK and VRChat client checks. A Tripo preview, auto-rig badge or successful file conversion does not certify those later stages.
