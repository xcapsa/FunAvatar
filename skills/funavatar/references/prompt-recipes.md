# Prompt recipes

Use one compact identity block in every generation request. Tool-specific reference attachments matter more than repeating adjectives; reuse the actual master image when the tool supports it.

## Identity block

Record only features that affect consistency:

```text
Character: [name and core concept]
Preserve from reference: [face/helmet shape, silhouette, hair, outfit, palette]
Body: [proportions, posture, anatomical design, planned digit count]
Outfit/materials: [layers, seams, closures, surface finish]
Asymmetry: [character's anatomical left/right details]
Palette: [base colors and controlled accents]
Branding: [none / requested brand / supplied original logo asset]
Exclude: [explicit user exclusions, unwanted marks, unwanted text]
States: [base form and any transformed form; features shared between them]
```

Specify missing or intentionally simplified details as proposed design. Avoid adding novel armor, jewelry, glowing motifs, logos, or body parts independently to each view.

## Master concept

```text
Create a polished full-body character concept from the attached reference and identity block. Preserve the listed identity anchors. Show the complete silhouette, hands and feet against a simple neutral background, with controlled studio lighting and clear material separation. Do not add a display base or effects that hide anatomy. This is a 2D design concept for a modeler, with no claim that a 3D asset exists. Omit technical readiness badges and decorative text.
```

A dynamic hero view is optional. For a modeling task, prioritize a readable neutral master over action effects.

## Turnaround

```text
Using the attached master design, produce consistent full-body front, back, anatomical left side and anatomical right side views of exactly the same character. [T-pose / A-pose] in every panel; neutral expression and identical outfit state. Orthographic-looking camera, no intentional perspective, equal character scale, same ground line and aligned head, shoulders, elbows, wrists, hips, knees and soles. Keep arms and hands readable in side views. Preserve character-relative asymmetry; the two sides must not be mirrored duplicates when the design is asymmetric. Plain neutral background and even lighting, with margin around all hair, fingers, accessories and feet. No extra characters, hidden limbs, duplicated props or readiness claims. Leave labels out of the generated pixels if precise lettering cannot be controlled.
```

Separate views are preferable when a four-panel sheet produces drift or unreadably small figures. Use consistent framing when combining them later, and retain the source images. Do not call a side view “orthographic” if its pixels visibly show perspective or conflicting proportions.

## Detail sheet

```text
Show close-ups of the same character from the attached master: head front/side/back; anatomical left and right hand, palm and back, with relaxed separated digits; relevant garment closures and layer boundaries; sole and accessory attachment points where useful. Preserve the planned digit count and construction. Separate panels clearly and keep each detail at a useful modeling scale. No invented wireframe or UV diagrams; these would be illustrations, not evidence of real geometry.
```

Do not demand five digits for every species. Set the count deliberately and review it against the brief. A robotic human hand and a stylized sloth paw need different checks.

## Human → sloth example

```text
Design two states of one recognizable character: a human inventor and a stylized bipedal sloth transformation. Keep the same hairstyle cue, eye expression, warm personality, signature jacket colors and recognizable accessory. In sloth form, deliberately adapt the muzzle, facial markings, rounded ears, limb proportions, fur and planned claws/digits. Show how sleeves, cuffs and footwear change or are removed; no human hands accidentally attached to sloth wrists. Keep the sloth version suitable for the chosen bipedal concept while marking humanoid rig feasibility as untested. Present each state in the same neutral pose and scale convention, with a short transition sketch only if requested. No gore, no fake topology, no claim that a morph or animation has been implemented.
```

The shared cues come from the actual brief; do not impose this example's jacket, palette, or anatomy on other characters. A transition sketch communicates an idea, while a working transformation requires a separate 3D and animation implementation.

## Targeted repair

```text
Edit the attached sheet only to resolve [panel and concrete defect]. Preserve the master identity, all accepted views, color/material choices, pose and framing. Correct [specific anatomy/alignment/asymmetry issue]. Recheck the edited area and its corresponding feature in the other views. Do not redesign the character or add new accessories.
```
