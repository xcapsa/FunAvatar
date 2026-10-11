# Visual review rubric

Review actual pixels against the brief and attached reference. The helper's file check inspects container/header structure and dimensions without decoding pixels; it does not satisfy this rubric.

Use `pass`, `needs repair`, or `not assessed` for each relevant category. Record concrete evidence, such as “right-side view loses the left shoulder pouch” or “front wrist has a sixth digit.” Do not infer invisible details.

| Check | Evidence to inspect |
| --- | --- |
| Identity | Same head/helmet, hair, proportions, silhouette and character cues across panels; intentional changes are documented. |
| Outfit and materials | Same layers, seams, closures, pockets, shoes, accessory mounts and material placement; nothing appears or disappears accidentally. |
| Branding | Requested identity only; explicit exclusions respected; original logo matches supplied asset or patch remains clearly pending. |
| Anatomy | Plausible connected joints, consistent limb lengths, no extra/missing limbs; knees, elbows, wrists and ankles have readable construction. |
| Hands and feet | Intended digit count, separated and connected digits, coherent thumb/palm orientation, no fused fingers or repeated feet; species-specific anatomy is deliberate. |
| Turnaround | Front/back/left/right correspond to actual view orientation, not merely text labels; comparable scale, pose, joint heights and ground line. |
| Camera | Front and side views minimize perspective; no contradictory widths or visible front features in a supposed strict back view. |
| Asymmetry | Character-relative left/right details persist correctly; checks do not confuse anatomical left with image left. |
| Visibility | Hair, fingers, soles, ears, tail and accessories are not cropped or hidden by effects; relevant occluded construction has another useful view. |
| Transformation | Shared identity anchors persist; anatomy and clothing adaptation are intentional; each state remains internally consistent. |
| Handoff honesty | No invented mesh, rig, UV, shader, SDK or runtime evidence; design assumptions and unresolved ambiguity are named. |

Prioritize defects by their effect on the requested result:

- **Blocking:** identity drift, wrong form or brand, conflicting proportions, unreadable main view, serious anatomy error, or misleading readiness claim. Repair before describing the sheet as a modeling reference.
- **Material:** ambiguous attachment, hidden hand/foot detail, unintentional asymmetry, perspective or alignment drift. Repair where feasible; otherwise mark the relevant panel as concept-only.
- **Minor:** small surface decoration or label defect that does not alter construction. Preserve a useful accepted image and put precise labels in accompanying text when needed.

For an independent reviewer, provide the brief and images without the generator's self-evaluation. Ask for a concise category status, concrete defects and repair priorities. Review a repaired result again, including accepted regions that could have drifted during the edit. A score or enthusiastic verdict cannot replace defect evidence.

Final status should distinguish:

- **Concept delivered:** visual idea exists, with any modeling ambiguity stated.
- **Modeling reference reviewed:** relevant visual checks passed or remaining limitations are explicit.
- **3D/runtime status untested:** mandatory for image-only output; never infer it from a polished reference sheet.

If a 3D conversion or imported model is supplied, also apply the [image-to-3D fidelity gate](technical-handoff.md#image-to-3d-fidelity-gate). A passing concept review does not approve its reconstruction. Compare actual model views before rigging/effects; retain reference fidelity as unverified without that evidence.
