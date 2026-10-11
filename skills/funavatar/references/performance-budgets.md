# Measured budgets and expression parameters

Use `scripts/vrc_acceptance.py` when actual static measurements are available. It is an offline checker, not a collector, an optimizer, an SDK validator or a replacement for device profiling. Keep source, optimized and built-avatar observations separate; inactive objects still affect the official performance calculation.

```sh
python3 scripts/vrc_acceptance.py check measured-avatar.json --out new-budget-report.json
```

Input uses `schema_version: 1`, `kind: funavatar_vrc_measurements`, `asset_sha256`, `target: pc|android|ios` and `evidence_scope: static_measured`. Optional fields are `asset_path`, `metrics`, and `expression_parameters`, each parameter containing exactly `name`, `type` (`bool`, `int`, `float`) and `synced` (boolean). A relative asset path resolves from the input report. Supply it when the source is available: a changed file invalidates its measurements. Without it, the hash is only declared, not independently checked.

Supported metrics are triangles, texture memory in MB, skinned meshes, material slots, PhysBone components/transforms/colliders/collision checks, contacts, constraints and constraint depth. Use the exact keys in [the dated profile](../assets/vrchat-performance-profile.json). Missing measurements remain unknown; never fill them with zero. Texture memory means the measured in-memory figure, not the compressed image-file size. Constraint depth is the dependency chain, not transform hierarchy depth.

The output distinguishes:

- The **partial Good profile** for the supported metrics. Being within it does not establish the complete SDK rank.
- The separate **hard component limits** for mobile.
- The triangle-related visibility threshold, which is not an absolute upload prohibition.
- Custom parameter count and synced memory in bits.

Exit codes are `0` for supported sections known and within their thresholds, `1` for exceedances, `2` for invalid/stale input or an output conflict, and `3` for missing observations. SDK rank, upload eligibility and runtime remain unverified, even with exit code zero. The iOS numeric profile does not add iOS support to the older workflow ledger or prove an iOS build.

## Corrections to common assumptions

VRChat's synced custom-parameter budget is **256 bits**, not 256 unique parameters: a synced boolean costs one bit and an int/float costs eight. The separate total custom-parameter limit is 8192. Built-in read-only values such as `Voice` and `Viseme` are not user-writable custom controls. [Official animator parameters](https://creators.vrchat.com/avatars/animator-parameters/).

The mobile Good triangle threshold is **10,000**; 15,000 belongs to Medium. Exceeding 20,000 contributes a Very Poor rank and visibility restrictions; the current documentation describes an individual Show Avatar override. Hard component limits are separate and cannot be bypassed with that override. Do not translate a ranking threshold into an invented absolute upload/render ban. [Official performance ranks](https://creators.vrchat.com/avatars/avatar-performance-ranking-system/).

Android avatar shaders must come from the supported SDK mobile set; PC shader recipes such as Poiyomi or lilToon do not establish Quest compatibility. Preserve the PC master and produce a separately verified mobile derivative. [Android limitations](https://creators.vrchat.com/platforms/android/quest-content-limitations/).

When a budget is exceeded, identify the responsible component and compare one reversible change. Recheck facial shapes, weights, attachments and animations after decimation, atlas baking or build-time optimization. A successful modifier call, a material name or an enabled optimization component does not establish a successful optimized export. Revisit the official limits and regenerate the dated profile when platform guidance changes.
