# Production tools and compatible handoffs

Official sources checked **2026-10-11**. Start with native Blender authoring and
Unity assembly. Generators are optional sources of editable geometry, never a
prerequisite for producing an avatar. Choose an installed tool that serves the
approved design; verify its version, license and actual export before use.

“Documented handoff” below means the vendor documents an interchange route. It
does not mean FunAvatar has executed that provider, preserved every feature, or
validated an avatar. Connector status describes this skill's bundled code;
inspect the host separately before claiming an application or plug-in is installed.

## Tool matrix

| Tool and role | Route / useful formats | Automatic connector bundled or verified installed? | Documented handoff and remaining work |
| --- | --- | --- | --- |
| **Blender: primary authoring** | Model, sculpt, retopologize, UV, texture, rig, shape keys and animate; native [`bpy`](https://github.com/blender/blender/blob/main/doc/python_api/rst/info_quickstart.rst). Keep `.blend`; export FBX or [GLB/glTF](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/docs/blender_docs/scene_gltf2.rst). | Native Python API; bundled observation script. Authoring runs require the installed Blender/version and task-specific work. | Editable master plus interchange export. Inspect imported materials, skinning, shape keys and animations; procedural nodes/constraints need baking or reconstruction where unsupported. |
| **Unity: primary assembly** | [Editor C# / AssetDatabase](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/AssetDatabase.html), prefabs, materials, Animator assets and SDK configuration. Prefer [FBX import](https://docs.unity3d.com/2022.3/Documentation/Manual/3D-formats.html). | Native editor scripting; bundled inspection source. No general live-editor connector is implied. | Use the [VRChat-supported editor](https://creators.vrchat.com/sdk/upgrade/current-unity-version/), installed SDK and preserved project metadata. Compilation, SDK build and client tests remain distinct. |
| **Tripo: optional cloud generation/processing** | [v3 API](https://developers.tripo3d.ai/en/docs/introduction), textured mesh; [rig outputs GLB/FBX](https://developers.tripo3d.ai/en/docs/animations-rig). | **Bundled Tripo adapter**; offline tests do not establish live account/API access. | Existing tracked route in [workflow-3d.md](workflow-3d.md). Authorized uploads, operations and numeric budget required; inspect actual topology, textures and deformation. |
| **Meshy: optional cloud generation/rigging** | [Image-to-3D](https://docs.meshy.ai/en/api/image-to-3d): GLB/FBX/OBJ and optional PBR maps. [Rigging](https://docs.meshy.ai/en/api/rigging): textured humanoid GLB input, rigged FBX/GLB and basic animation outputs. | None bundled or verified installed; web export/manual import only in this skill. | API requires a key and credits. Standard bipeds are the documented rigging case; creatures, unclear limbs and untextured meshes need another route. Recheck available model IDs rather than copying retired versions. |
| **Hyper3D / Rodin: optional cloud geometry/materials** | [Gen-2.5 API](https://docs.hyper3d.ai/en/api-specification/rodin-gen2-5): GLB/FBX/OBJ, PBR or baked/shaded materials; image or text input. | None bundled or verified installed. Vendor [DCC add-ons](https://docs.hyper3d.ai/en/addons) are separate installations. | Account/key and current credit terms required. Preserve explicit tier/settings. This documented generation route does not establish a delivered skeleton, facial rig or animation; build/verify those separately. |
| **Microsoft TRELLIS.2: optional local image-to-mesh** | [Official repository](https://github.com/microsoft/TRELLIS.2): PBR GLB export; no documented avatar-rig stage in this route. | None bundled or verified installed; manual export/import. | Official code tested only on Linux, NVIDIA GPU with at least 24 GB, CUDA tooling. Model/code MIT; dependencies have separate terms. No native Mac execution claim. Check opacity: exported GLB defaults to opaque despite retaining texture alpha. |
| **Tencent Hunyuan3D-2.1: restricted local alternative** | [Shape/PBR pipeline](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1), [GLB/OBJ export code](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/gradio_app.py). | None bundled or verified installed. | [Community license excludes EU, UK and South Korea](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE); not an actionable default there. README lists 10 GB shape / 21 GB texture / 29 GB combined VRAM and CUDA-tested dependencies. Its OS support statement does not prove this host can execute the complete pipeline. Rigging remains separate. |

Optional specialist handoffs also fit this contract: [Maya](https://help.autodesk.com/cloudhelp/2024/ENU/Maya-Interoperability/files/GUID-FE8DBEAA-C2DD-43B3-9933-4BA4CDDEAA89.htm)
for rig/animation FBX, [ZBrush](https://help.maxon.net/zbr/en-us/Content/html/user-guide/zbrush-plugins/fbx-exportimport/fbx-exportimport.html)
for sculpted mesh FBX, and [Substance 3D Painter](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/export/export)
for exported texture maps. No connector is bundled or installation verified;
use an authorized licensed installation and check its exporter/version. These
tools do not replace Unity/SDK/client validation.

## One provider-neutral handoff contract

1. Preserve the original and editable master. Deliver `.blend` plus a reviewed
   FBX for Unity; use GLB for portable inspection or Blender interchange.
   Unity's built-in model importer does not establish GLB support: import into
   Blender and export FBX, or use an already authorized compatible importer.
   Avoid Unity's implicit `.blend` conversion as the shared production artifact.
2. Include base color, normal, roughness, metallic, opacity and emission **when
   actually present**, with UVs, color-space/channel conventions and material
   assignments. Keep sidecars or pack assets deliberately. Rebuild target
   shaders; neither FBX nor PBR maps preserve an arbitrary node graph.
3. Record units, measured height, axes/forward direction, transforms and origin.
   Preserve skeleton hierarchy, bind/rest pose, bone names, weights, shape keys
   and named animation clips when supplied. Static OBJ/STL cannot substitute for
   a skinned animated handoff. Round-trip the export and compare actual contents.
4. Reuse the existing ledger offline, despite its historical filename:

   ```sh
   python3 scripts/tripo_workflow.py init --out /path/avatar/run --name Character --platform both --budget-credits 0
   python3 scripts/tripo_workflow.py asset /path/avatar/run/workflow.json --id native-master --file /path/avatar/master.blend --stage geometry
   python3 scripts/tripo_workflow.py asset /path/avatar/run/workflow.json --id unity-export --file /path/avatar/avatar.fbx --stage export --parent native-master
   ```

   Register textures and a provenance/settings JSON as additional assets and
   dependencies. Include tool/provider, version, license/source, known task ID,
   settings and unknown costs. The `asset` command hashes regular files; it
   neither converts nor validates them. Do not pass another provider's job to
   Tripo's `plan`, `submit` or `resume` commands.
5. Apply [fidelity](technical-handoff.md#image-to-3d-fidelity-gate), geometry,
   surface, native deformation and export checks to the exact revision. Then
   record SDK and observed client results separately for PC and native Android.
   Preserve Unity assets, `.meta`, package versions and configuration evidence.
   Use [project checks](project-checks.md) for observations; unperformed checks
   remain `not_assessed`. A format match or completed generation is not avatar
   compatibility proof.
