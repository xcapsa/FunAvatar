# Reconstruct the reference before producing the avatar

Use this for reproducing a supplied image in any 3D route: native Blender, MCP, a generator or an imported mesh. A reference can depict a human, creature, robot or stylized character; do not impose humanoid proportions, five fingers, generic armor or one material style on every subject. The target is the user's visible design. A technically working avatar with a different appearance fails that request.

## Read the source, not a description of it

Inspect actual pixels of **every supplied view and relevant close-up**. Original user images are primary unless the user selects a different master. Agent-generated turnarounds are supporting interpretations; they cannot silently replace the originals. Record file hashes, view orientation and primary/supporting roles in `reference-set.json` before production. Do not remove inconvenient views or demote originals to make a review pass.

Use the delivery contract's `visible_constraints` as a compact table: **region → reference/view → observed shape/material/placement → native construction → verification view**. Describe specific contours and relationships, not keywords such as “cyberpunk jacket.” For example, a loose bomber needs its sleeve volume, shoulder drop, waist gathering and collar construction; a tapered cylinder with random wrinkles is not equivalent. Keep `inferred_hidden_regions` and contradictions separate. Anatomical left/right is the character's, not the viewer's; record both when colors or accessories differ by side.

For a sheet, identify each relevant panel with a separate inventory ID/view and a note describing its position; IDs can share the original file/hash. Never trust generated labels over visible orientation. If supplied panels conflict, use the user's selected master for the disputed feature, record a justified reversible choice when minor, or ask one focused question when identity depends on it. Continue unambiguous work. Do not claim contradictory references are all exactly reproduced.

One image does not determine the hidden surface, physical dimensions, camera or material response uniquely. Model supported visible features faithfully; label the rest as inferred. Do not invent missing supplied images in the inventory or make a single-view project wait for nonexistent back views. Exact reconstruction of unseen geometry is not a promised capability.

## Direct Blender in small, observable steps

1. **Calibrate and block out.** Match the reference projection, pose, framing and ground line in disposable comparison views. Record whether camera matching is estimated. Mark useful image landmarks and relative ratios: head/body, shoulder/hip widths, joint heights, garment extents and accessory locations. Use measured values from the actual image, with declared manual/automated method and reference-specific tolerances. Do not invent precision, physical height or a universal “similarity percentage.” Build the main silhouette and volumes first; inspect front and every provided side/back view before adding details.
2. **Construct the observed forms.** Drive contours, cross-sections and feature placement from those measurements. Use curves, editable meshes, sculpting, modifiers and topology appropriate to the subject. Hair needs observed masses, flow, layering and silhouette before individual strands; garments need construction, thickness, seams and folds following their form; hands/paws, face and shoes need their actual structure. Procedural repetition is useful only where the reference repeats. Do not replace missing modeling work with uniformly repeated spikes, generic lofts, random noise or smooth shading. Preserve exact supplied graphic/logo assets; without an extractable clean source, keep the specific graphic pending instead of substituting another symbol.
3. **Render, compare, repair.** Save a new native revision, reload it, and render the actual model (`scripts/blender_ortho_render.py` gives matched orthographic front/left/back views at one recorded scale; see [comparison renders](project-checks.md#vrchat-export-readiness-checks-and-comparison-renders)). Use matched neutral-lit views for appearance, clay views for disputed geometry, and unlit/material views for palette and graphics. Keep original references unwarped. Diagnose geometry, camera/pose, shading, UV/texture and lighting separately. Repair the largest visible mismatch first, rerender the affected views and check previously correct regions. A beauty render, extra polygons or a successful save is not acceptance.

Each authoring operation should name its input revision, target objects, reference constraints, intended edit, new output and readback/render check. Keep the reference/calibration data separate from geometry code so a repair changes the relevant contour or material instead of regenerating the whole character. Scope operators and selections; inspect saved geometry rather than trusting the script's success message. Do not continue issuing variants of a failed generic generator without changing the diagnosed construction method.

Use a provisional pose rig only when needed for a fair comparison; production weights, actions and Unity avatar assembly follow the refined appearance review. Environment installation/checks can proceed independently. Optimization is a derivative of the accepted source and must be compared again; a lower polygon count never authorizes a changed silhouette.

## Review before running the next production stage

Use [the review template](../assets/fidelity-review.template.json) for the refined native/imported asset. The reviewer must inspect actual pixels and record concrete notes for silhouette, proportions, head/hair, outfit, materials, side-specific details and branding. For a feature absent by design, use `pass` with the specific reference-based absence, not an invented feature. A genuinely supplied view that is missing, unreadable, unreviewed or incompatible in pose/camera blocks downstream appearance acceptance, not repair, calibration or provisional posing. A view never supplied is not a missing evidence file. Technical test counts and the builder's self-assessment are not evidence of likeness.

When available and authorized, give an independent reviewer the original images, model renders and user request without the builder's verdict. Keep user review simple: show a clear comparison at meaningful milestones; do not make them approve every command. A user rejection invalidates the current appearance acceptance. Preserve that history; clear the rejection only in a new review that points to the repaired revision and addresses the stated defects. If the user explicitly requires their own approval, wait for it. Reinterpretation requires their actual instruction recorded as a quoted, hash-bound text artifact; it cannot be inferred from “make it professional.”

Inventory format (paths can be relative to the inventory; add every supplied view):

```json
{
  "schema_version": 1,
  "references": [
    {
      "id": "original_front",
      "view": "front",
      "role": "primary",
      "availability": "available",
      "path": "references/original.png",
      "sha256": "REPLACE_WITH_ACTUAL_SHA256",
      "note": "User-supplied master; front panel at upper left."
    }
  ]
}
```

Review paths are relative to the review file. Bind its `asset`, `reference_set` and each comparison `render` to the actual paths/hashes. Every inventory ID needs a comparison; categories cite those IDs. `render_view` describes the actual render, not a convenient label; `camera_pose_compatible` is an observed declaration. Keep the render receipt linking source, camera and settings alongside the review. Source changes require new renders and review; do not merely update hashes on an old verdict.

```sh
python3 scripts/fidelity_review.py check /absolute/avatar/fidelity-review.json --out /absolute/avatar/new-preflight.json
python3 scripts/fidelity_review.py run /absolute/avatar/fidelity-review.json -- /absolute/Blender --background /absolute/avatar/reviewed.blend --python /absolute/avatar/rig_stage.py
```

`check` returns **0** for a complete current declared review, **1** for a blocked review and **2** for invalid input/I/O. It never overwrites an output. `run` repeats that check immediately and launches the supplied argument vector without a shell only when it passes; otherwise the production process does not start. On launch it returns the child process's exit code. Use this guard for authorized production rig/animation, optimization and Unity assembly commands. For an in-process MCP/application action, run `check` immediately beforehand against the exact input and do not send the mutation if blocked. Repair and comparison commands remain available while blocked.

This helper checks review completeness and file bindings, **not pixels, speaker identity or artistic quality**. It cannot prove that a render came from the declared asset, that a reviewer told the truth, or that an arbitrary child command uses that asset. Verify these associations during review; a command launched directly outside the guard is not protected. A complete declared review is not a guarantee of identical appearance. Report observed fidelity and remaining inferences separately from rig, SDK and client results.
