# FunAvatar

Turn an idea or character reference into consistent avatar concept sheets with Codex or Claude Code. FunAvatar combines a reusable skill, a small offline planning/checking tool, and visual review guidance for a Blender → Unity → VRChat handoff.

The output is **2D reference art**. A modeler still creates the mesh, UVs, materials and rig; the installed VRChat SDK validates the finished avatar.

## Install

Requires Python 3.10 or newer. No Python packages, API keys or background services are needed for installation or the helper tool.

```bash
git clone https://github.com/xcapsa/FunAvatar.git
cd FunAvatar
python3 install.py --target both
```

This copies the skill to `~/.agents/skills/funavatar` for Codex and `~/.claude/skills/funavatar` for Claude Code. Existing installations are preserved: the installer stops instead of replacing them. To uninstall, remove the corresponding `funavatar` folder. Installation does not change application settings.

These local discovery locations follow the [official Codex skill guide](https://learn.chatgpt.com/docs/build-skills) and [Claude Code skill guide](https://code.claude.com/docs/en/skills). Claude Cowork and cloud sessions use account-enabled skills instead of the local personal folder; the release includes a separate `funavatar-skill.zip` for manual upload where supported.

## Use

In Codex, invoke `$funavatar`. In Claude Code, invoke `/funavatar`. If a new skill does not appear, start a new session.

Example request:

> Use FunAvatar to create an Oculandia character from my reference: a scientist in a white coat with a red hoodie and green goggles, who transforms into a sloth. Preserve his identity and outfit. Make separate human, transformed and detail sheets. Use multiple agents for art direction and technical review. Remove Odido branding.

Codex uses its built-in image-generation tool when available. Claude uses an available connected image-generation tool. If the session has no image generator, FunAvatar prepares the brief and prompts and explains what still needs generating. It does not install a provider, spend API credit, or claim that prompts are images.

## Offline helper

Create a brief and prompts:

```bash
python3 skills/funavatar/scripts/funavatar.py plan \
  --name "L'Infissiologo" \
  --idea "Scientist with white coat, red hoodie, green goggles and two drills" \
  --transformation "sloth" \
  --brand "Oculandia" \
  --out output/infissiologo
```

Add `--reference path/to/image.jpg` for each reference image. Planning preserves existing outputs. The helper does not generate images or contact any service.

Inspect image dimensions, file structure and checksums:

```bash
python3 skills/funavatar/scripts/funavatar.py check \
  examples/infissiologo/human-turnaround.png --min-long-edge 1536
```

Automated checks cannot judge anatomy, visual consistency, model topology or VRChat compatibility. The skill includes a separate visual review rubric.

## Included example

[L'Infissiologo](examples/infissiologo/) is an Oculandia human character with a sloth transformation. The folder contains separate full-resolution sheets, the prompts used and review notes. Original source references and personal local paths are not included.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The helper and installer use the Python standard library. Contributions should preserve reference identity, avoid destructive output replacement, and keep image-generation capability separate from 3D validation.
