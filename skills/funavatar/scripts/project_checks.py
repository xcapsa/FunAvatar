"""Bounded offline checks of supplied facts; never runtime certification. Python 3.10+."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


MAX_REPORT_BYTES = 128 * 1024
MAX_REPORTS = 8
MAX_COUNT = 2**53 - 1  # Serialization bound, not an avatar performance budget.
SOURCES = {
    "armature": "https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html",
    "shading": "https://docs.blender.org/manual/en/latest/scene_layout/object/editing/shading.html",
    "skin": "https://docs.unity3d.com/2022.3/Documentation/Manual/class-SkinnedMeshRenderer.html",
    "texture": "https://docs.unity3d.com/2022.3/Documentation/Manual/class-TextureImporter.html",
    "humanoid": "https://docs.unity3d.com/2022.3/Documentation/Manual/ConfiguringtheAvatar.html",
    "layers": "https://creators.vrchat.com/avatars/playable-layers/",
    "parameters": "https://creators.vrchat.com/avatars/animator-parameters/",
    "android": "https://creators.vrchat.com/platforms/android/quest-content-limitations/",
    "physbones": "https://creators.vrchat.com/common-components/physbones/",
}

# key, source, status when nonzero, explanation. Inventory never implies readiness.
RULES = {
    "blender": (
        ("mesh_count", "shading", None, "Mesh inventory only; confirm the surveyed scene or selection."),
        ("triangle_count", "shading", None, "Triangle inventory only; no universal performance threshold."),
        ("zero_area_faces", "shading", "needs_review", "Inspect degenerate geometry before editing; preserve intentional design."),
        ("nonfinite_vertices", "shading", "fail", "Nonfinite vertex coordinates were reported; locate and repair the affected geometry."),
        ("armature_count", "armature", None, "Armature inventory only; the intended rig type still needs review."),
        ("unweighted_vertices", "armature", "needs_review", "Review intended deformation and weighting method; envelopes or rigid parts may be intentional."),
        ("nonuniform_scale_objects", "armature", "needs_review", "Check export and deformation before changing transforms; do not blindly apply scale."),
    ),
    "unity": (
        ("renderer_count", "skin", None, "Renderer inventory only; visibility and bounds require pose tests."),
        ("missing_scripts", "layers", "fail", "Missing script references were reported in the surveyed hierarchy."),
        ("missing_material_slots", "skin", "needs_review", "Review empty material slots; unused slots may be intentional."),
        ("missing_shaders", "android", "fail", "Missing or error shaders were reported; inspect the material and target build."),
        ("missing_animation_bindings", "layers", "needs_review", "Pre-build paths may be rewritten by existing tools; inspect the generated avatar before declaring broken animation."),
        ("invalid_humanoid_avatars", "humanoid", "needs_review", "Inspect configured Humanoid mapping and pose if intended; do not force Humanoid onto nonhumanoid designs."),
        ("vrchat_descriptor_count", "layers", None, "Descriptor presence alone does not prove correct SDK configuration or upload readiness."),
    ),
}
OPTIONAL_COUNTS = {"unity": {"checked_animation_bindings", "conditional_animation_bindings"}, "blender": set()}
RUNTIME_CHECKS = (
    ("reference_fidelity", "shading", "Compare neutral model views and measured proportions with the approved reference; static counts cannot certify visual similarity."),
    ("deformation_and_bounds", "skin", "Compare imported pose extremes, skin weights and renderer bounds with the source model."),
    ("dynamic_motion", "humanoid", "Verify wearer-following tracking/IK, skin deformation and attachments through head/body turns, raised arms, crouch, lean, walk and fast stop; record rest, interruption and reset separately per client/platform. Static counts or one pose cannot certify motion."),
    ("effects_and_reset", "layers", "Trace parameter, state, mask and property; test off/on/reset, interruption and reloading."),
    ("remote_visibility", "parameters", "Test a second VRChat client, including late join and synchronized parameters."),
    ("target_performance_and_compatibility", "android", "Run SDK validation and measure the intended build on target hardware; counts alone do not certify it."),
    ("secondary_motion", "physbones", "Inspect intended PhysBone roots, chains and collisions; test actual secondary motion when used."),
)
SYMPTOM_STEPS = {
    "fidelity": (
        ("shading", "Record image-to-3D provider, version, settings and supported inputs. Use a clean isolated single-character reference; decorative collages or multiview sheets require explicit provider support."),
        ("shading", "Compare neutral front/back/anatomical side renders with approved references: silhouette, proportions, helmet, chestplate, gloves, hair and materials. Mark unseen reference details as unknown or proposed."),
        ("armature", "Measure model units and imported engine height against the intended brief separately from camera framing, zoom and pose; do not assume a height from a screenshot."),
        ("texture", "Separate missing geometry from baked texture detail and lighting. Stop before rig or effects if material identity, proportion or detail defects persist; repair or regenerate the affected asset and compare again."),
    ),
    "effects": (
        ("layers", "Trace menu or trigger -> parameter -> active state -> clip binding -> material, blendshape or object property; use FX for non-transform effects."),
        ("layers", "Check layer order and masks, then compare source bindings with the avatar generated by existing build tools before rewriting controllers."),
        ("parameters", "Exercise off/on/reset, repeated triggers, interruption and avatar reload; record the expected and actual state."),
    ),
    "remote": (
        ("parameters", "Compare parameter names, types, defaults and synchronization in the Animator and Expression Parameters asset; inspect local-only branching. Across PC/Android builds synchronization matches list position and type: prefer the same Expression Parameters asset."),
        ("layers", "Check the playable layer and masks for the affected property; compare local view, mirror and a second client."),
        ("parameters", "Test late join, parameter changes, reset and reload on the second client; a local preview cannot prove remote behavior."),
    ),
    "mobile": (
        ("android", "Inspect the actual Android build, current SDK shader/component restrictions and platform overrides; replace only the unsupported feature."),
        ("texture", "Compare imported Android texture size, format and compression with the source; verify the intended material on device."),
        ("android", "Run SDK validation and compare repeatable frame and memory measurements on target hardware; do not infer compatibility from a PC preview."),
    ),
    "deformation": (
        ("armature", "Compare the same elbow, shoulder, squat and hand poses in Blender and the imported model; isolate topology, weights, modifier/export behavior and scale."),
        ("humanoid", "For an intended Humanoid rig, inspect mapping, optional bones and reference pose; preserve an intentional Generic or nonhumanoid rig."),
        ("skin", "Inspect imported bone influences and renderer bounds in extreme poses; correct measured bounds rather than routinely enabling offscreen updates."),
    ),
    "pixelation": (
        ("shading", "Use a neutral material and wireframe to separate a coarse silhouette from faceted shading and texture pixels; smoothing does not add silhouette geometry."),
        ("texture", "Compare source and target-imported texture resolution, UV coverage, filter, mipmaps and compression at the same distance; change one variable."),
        ("shading", "Inspect normals and local topology for shading or silhouette defects; avoid blanket subdivision or upscaling as a claimed fix."),
    ),
    "motion": (
        ("humanoid", "Inspect rig mapping, rest/bind pose, skin weights and imported deformation against the baseline; revalidate changed generated/retopologized meshes. Preserve intentional nonhumanoid rigs."),
        ("layers", "Trace wearer tracking/IK, parameters, transitions, masks and competing animation/constraint ownership; confirm emote/transformation exits restore intended tracking. Check attached props and garment-bound graphics follow their actual bones or skinned mesh."),
        ("physbones", "Declare which secondary motion is used or intentionally absent. For used PhysBones inspect roots/chains/endpoints, gravity/inertia, limits and colliders; avoid Humanoid roots or Constraint control on the same object. No universal preset or worlds-only VRCPhysBoneRoot timing on avatars."),
        ("android", "Repeat head/body turns, arms raised, crouch, lean, walk and fast stop, then rest, interruption and reset. Keep local view, mirror, remote client and native Android proof separate; do not add unsupported rigidbodies/Cloth or custom scripts as a generic motion fix."),
    ),
}


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate report key: {key}")
        result[key] = value
    return result


def _bad_constant(value: str):
    raise ValueError(f"Nonfinite JSON number: {value}")


def validate_report(report: dict) -> dict:
    if not isinstance(report, dict):
        raise ValueError("Report must be a JSON object")
    required = {"schema_version", "tool", "tool_version", "subject", "observations"}
    if not required <= report.keys() or report.keys() - required - {"target"}:
        raise ValueError("Report needs schema_version, tool, tool_version, subject, observations; only target is optional")
    if type(report["schema_version"]) is not int or report["schema_version"] != 1:
        raise ValueError("Unsupported report schema_version; expected integer 1")
    tool = report["tool"]
    if not isinstance(tool, str) or tool not in RULES:
        raise ValueError("Report tool must be blender or unity")
    for key in ("tool_version", "subject"):
        value = report[key]
        if (not isinstance(value, str) or not value.strip() or len(value) > 512
                or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
            raise ValueError(f"Report {key} must be nonempty text of at most 512 characters without control characters")
    if "target" in report and report["target"] not in ("pc", "android", "both"):
        raise ValueError("Report target must be pc, android or both")
    facts = report["observations"]
    if not isinstance(facts, dict):
        raise ValueError("Report observations must be an object of known integer counts")
    allowed = {rule[0] for rule in RULES[tool]} | OPTIONAL_COUNTS[tool]
    if facts.keys() - allowed:
        raise ValueError(f"Unknown {tool} observation: {', '.join(sorted(facts.keys() - allowed))}")
    for key, value in facts.items():
        if type(value) is not int or not 0 <= value <= MAX_COUNT:
            raise ValueError(f"Observation {key} must be an integer between 0 and {MAX_COUNT}")
    if "checked_animation_bindings" in facts:
        if facts.get("missing_animation_bindings", 0) > facts["checked_animation_bindings"]:
            raise ValueError("missing_animation_bindings exceeds checked_animation_bindings")
    if "conditional_animation_bindings" in facts and "missing_animation_bindings" in facts:
        if facts["conditional_animation_bindings"] > facts["missing_animation_bindings"]:
            raise ValueError("conditional_animation_bindings exceeds missing_animation_bindings")
    return report


def load_report(filename: str) -> tuple[dict, dict]:
    path = Path(filename).expanduser().resolve(strict=True)
    if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError(f"Report must be a regular file of at most {MAX_REPORT_BYTES} bytes: {path}")
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError(f"Report exceeds {MAX_REPORT_BYTES} bytes")
    try:
        report = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_bad_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Report must be bounded UTF-8 JSON") from exc
    report = validate_report(report)
    evidence = {"report": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    return report, evidence


def _status(checks: list[dict]) -> str:
    for status in ("fail", "needs_review", "not_verified"):
        if any(check["status"] == status for check in checks):
            return status
    return "pass"


def _write_new(path: Path, content: str) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        try:
            stream.write(content)
        except BaseException:
            path.unlink(missing_ok=True)
            raise


def project_check(filenames: list[str], out: str | None = None) -> tuple[dict, int]:
    """Exit 1: static fail; 3: needs review; 0: neither (runtime stays unverified)."""
    if not 1 <= len(filenames) <= MAX_REPORTS:
        raise ValueError(f"Supply 1 to {MAX_REPORTS} reports")
    checked = []
    tools = set()
    for filename in filenames:
        report, provenance = load_report(filename)
        tool, facts = report["tool"], report["observations"]
        tools.add(tool)
        checks = []
        for key, source, issue, explanation in RULES[tool]:
            evidence = {**provenance, "observation": key}
            if key not in facts:
                status, detail = "not_verified", "No observation supplied; not checked."
            else:
                value = facts[key]
                evidence["value"] = value
                status = issue if value and issue else "pass"
                if key in ("mesh_count", "renderer_count") and not value:
                    status = "needs_review"
                if key == "vrchat_descriptor_count" and value != 1:
                    status = "needs_review"
                detail = explanation if status != "pass" or issue is None else "Reported count is zero in the surveyed scope only."
            checks.append({"id": key, "status": status, "evidence": evidence,
                           "source": source, "detail": detail})
        checked.append({"tool": tool, "tool_version": report["tool_version"],
                        "subject": report["subject"], "target": report.get("target"),
                        "checks": checks,
                        "additional_observations": {key: facts[key] for key in sorted(OPTIONAL_COUNTS[tool] & facts.keys())}})
    runtime = [{"id": key, "status": "not_verified", "evidence": None,
                "source": source, "detail": detail} for key, source, detail in RUNTIME_CHECKS]
    for tool in sorted(RULES.keys() - tools):
        runtime.append({"id": f"{tool}_static_report", "status": "not_verified",
                        "evidence": None, "detail": "No report supplied for this tool."})
    checks = [check for report in checked for check in report["checks"]] + runtime
    status = _status(checks)
    result = {"schema_version": 1, "scope": "static_supplied_reports", "status": status,
              "runtime_status": "not_verified", "reports": checked, "required_evidence": runtime,
              "sources": {key: SOURCES[key] for key in sorted({check["source"] for check in checks if "source" in check})},
              "limitations": ["Supplied facts are not independently collected by this command; a static pass applies only to the named observation and surveyed scope.",
                              "Reports may concern different subjects or versions; no cross-tool match or current project state is inferred.",
                              "No runtime, SDK build, remote-client, device or performance certification; no universal numeric performance limits."]}
    if out:
        _write_new(Path(out).expanduser().absolute(), json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return result, {"fail": 1, "needs_review": 3}.get(status, 0)


def debug_plan(symptom: str, out: str, platform: str = "both") -> dict:
    if symptom not in SYMPTOM_STEPS or platform not in ("pc", "android", "both"):
        raise ValueError("Unsupported symptom or platform")
    steps = [
        "Record the asset/scene, Blender/Unity/SDK versions, target, exact trigger and expected/actual behavior; preserve a baseline.",
        "Inspect the relevant native project and a working example; reuse existing components and installed tools before adding dependencies or custom code.",
    ] + [step for _, step in SYMPTOM_STEPS[symptom]]
    steps.append("Change one variable on a reversible copy, repeat the same reproduction, and retain before/after evidence plus limits; no fix is verified by this plan.")
    evidence = [
        ("baseline", "Versioned project/settings and exact reproduction before changes."),
        ("static_reports", "Read-only native collector reports for the relevant Blender/Unity subject."),
        ("isolated_comparison", "Before/after recording of the same trigger, pose, view and settings."),
        ("vrchat_client", f"SDK result and repeatable test on the intended {platform} target; device/client versions recorded."),
    ]
    if symptom == "fidelity":
        evidence.append(("reference_fidelity", "Approved reference identity/hash, matching neutral model views and documented model-unit/engine-height comparison with the brief."))
    if symptom == "motion":
        evidence.extend([
            ("rig_and_weights", "Baseline and final imported rig mapping, bind pose, skin weights and controlled deformation comparison, including any generated/retopologized mesh change."),
            ("tracked_motion", "Before/after wearer tracking/IK sequence: head/body turns, arms raised, crouch, lean, walk, fast stop, rest, interruption and reset; attachments and garment graphics follow correctly. Separate local view and mirror proof."),
            ("secondary_motion", "Declare used or intentionally absent secondary motion; before/after setup and motion/rest/reset proof for the chains, gravity/inertia, limits and collisions actually used, on each intended target."),
        ])
    if symptom in ("effects", "remote", "motion"):
        evidence.append(("second_client", "Second-client and late-join recording with reset/interruption results."))
    if platform in ("android", "both") or symptom == "mobile":
        evidence.append(("android_device", "Android build validation, on-device visuals and repeatable performance measurements."))
    result = {"schema_version": 1, "status": "not_verified", "executed": False,
              "symptom": symptom, "platform": platform, "steps": steps,
              "evidence_checklist": [{"id": key, "status": "not_verified", "evidence": None, "required": text} for key, text in evidence],
              "sources": {key: SOURCES[key] for key in sorted({source for source, _ in SYMPTOM_STEPS[symptom]})}}
    target = Path(out).expanduser().absolute()
    paths = [target / "debug-plan.json", target / "debug-plan.md"]
    if any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError(f"Refusing to overwrite an existing debug plan in {target}")
    markdown = [f"# FunAvatar debug plan: {symptom} ({platform})", "", "NOT VERIFIED — a plan only; no project inspection or tests executed.", ""]
    markdown += [f"{index}. {step}" for index, step in enumerate(steps, 1)]
    markdown += ["", "## Evidence still needed", ""]
    markdown += [f"- [ ] NOT VERIFIED: {description}" for _, description in evidence]
    markdown += ["", "## Official references", ""] + [f"- [{key}]({url})" for key, url in result["sources"].items()]
    payloads = [json.dumps(result, ensure_ascii=False, indent=2) + "\n", "\n".join(markdown) + "\n"]
    created = []
    try:
        for path, content in zip(paths, payloads):
            _write_new(path, content)
            created.append(path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {"status": "not_verified", "executed": False, "symptom": symptom,
            "platform": platform, "files": [str(path) for path in paths]}
