# Check an export and its file dependencies

Use this offline, read-only check before handing off a model or recording export
evidence. It resolves files already on disk, hashes the exact revision and emits
`complete`, `incomplete` or `not_assessed`. It never downloads, converts, archives
or modifies a model, and never passes a gate in the workflow automatically.

```sh
python3 scripts/funavatar.py export-check /path/avatar/export/avatar.glb --root /path/avatar/export --out /path/avatar/export-dependencies.json
```

`--root` is the permitted directory boundary; it defaults to the model's parent.
Use existing local paths for the model and optional declaration. Dependencies
must use relative paths within that boundary, without parent traversal,
absolute/remote URIs, query strings, fragments or symlinks. A model that depends
on `../textures` needs a deliberately arranged export from the native exporter;
this helper does not rewrite it. `--out` creates a new file exclusively and
refuses to overwrite existing reports or sources. Without `--out`, it prints the
manifest without creating files.

Exit codes: **0** complete dependency check; **1** incomplete/invalid export;
**3** dependencies not fully assessed; **2** invalid invocation or failed output.

## What the check covers

- **glTF 2.0:** declared buffer/image files, data URIs, byte-length availability,
  buffer-view ranges and texture-to-image references. All referenced files are
  hashed. Embedded data and image buffer views receive hashes as well.
- **GLB 2:** exact container length, first JSON chunk, optional second BIN chunk,
  alignment and padding, plus the glTF dependency checks. GLB can still refer to
  external files: its filename alone does not establish a self-contained model.
- **OBJ:** `mtllib` references, referenced material names and MTL texture maps,
  including common map options. Unsupported map options or external OBJ scripts
  remain unassessed. No script is executed.
- Unknown glTF extensions/chunks and opaque formats remain `not_assessed` rather
  than silently complete. A malformed or missing dependency is `incomplete`.

JSON input is bounded to 16 MiB, embedded data to 64 MiB, and an OBJ/MTL line to
1 MiB. OBJ/MTL and model binary hashes are streamed. A revision is rechecked
before returning the manifest; concurrent changes invalidate the observation.

The check follows the primary [Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
and [Khronos Validator issue definitions](https://github.com/KhronosGroup/glTF-Validator/blob/main/ISSUES.md).
External/data-URI buffers may contain more bytes than declared, but must contain
at least the declared range; GLB BIN padding is handled separately.

## FBX and other opaque formats

A directory listing cannot prove their complete dependencies. Inspect the export
in the native tool, preserve its dependency/export report, and supply an explicit
hash-bound declaration only when that native evidence actually exists:

```json
{
  "schema_version": 1,
  "kind": "funavatar_export_dependency_declaration",
  "source_sha256": "<exact model SHA-256>",
  "exhaustive": true,
  "basis": "Blender export dependency report for this revision",
  "native_evidence": {
    "path": "native-export-report.json",
    "sha256": "<exact report SHA-256>",
    "source_sha256": "<exact model SHA-256>"
  },
  "dependencies": [
    {"path": "textures/base-color.png", "sha256": "<exact texture SHA-256>"}
  ]
}
```

```sh
python3 scripts/funavatar.py export-check /path/export/avatar.fbx --root /path/export --declaration /path/export/dependencies.json
```

A successful opaque-format result uses `basis: declared_dependencies`: it
verifies the expressly attested set and its evidence hashes. It does **not**
parse FBX or prove the declaration's exhaustiveness. An empty dependency array
is appropriate only if native inspection established a self-contained export.
Never manufacture this declaration from a directory inventory or generate a
placeholder native report to obtain `complete`.

## Use the manifest as revision evidence

The report has `kind: funavatar_export_bundle`, `schema_version: 1` and
`scope: file_dependencies_only`. `source` identifies the model by relative path,
bytes and SHA-256; sorted `files`, `embedded` and `dependencies` cover resolved
resources. `issues` retain missing/uninspectable observations. `bundle_sha256`
binds the whole deterministic manifest, without timestamps or absolute root
paths. Relocating an unchanged bundle keeps its fingerprint; changing a texture,
material, model or native evidence changes it.

For API callers:

```python
from export_bundle import inspect_export
manifest = inspect_export(model_path, root=export_directory, declaration=None)
```

Preserve this report and register the exact model, relevant sidecars and report
as revisions in the ledger. Repeat the check after any change. The manifest
alone does not add workflow dependencies or invalidate an already recorded gate;
link files and evidence using the workflow's actual revision rules.

`complete` means file dependencies resolved for this scope. It provides no
texture decoding, rendered appearance, topology, rig, animation, tracking,
SDK-build or client-behavior validation. Those checks remain separate.
