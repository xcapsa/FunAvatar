#!/usr/bin/env python3
"""Inspect local export dependencies without converting, copying or fetching files."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import struct
from urllib.parse import unquote, unquote_to_bytes, urlsplit

MAX_JSON = 16 * 1024 * 1024
MAX_EMBEDDED = 64 * 1024 * 1024
MAX_LINE = 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# These extensions use core buffers/images or add no external file dependencies.
KNOWN_EXTENSIONS = {
    "KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu",
    "EXT_texture_webp", "EXT_texture_avif", "KHR_texture_transform",
    "KHR_materials_unlit", "KHR_materials_pbrSpecularGlossiness",
    "KHR_materials_clearcoat", "KHR_materials_transmission", "KHR_materials_volume",
    "KHR_materials_ior", "KHR_materials_specular", "KHR_materials_sheen",
    "KHR_materials_emissive_strength", "KHR_materials_iridescence",
    "KHR_materials_anisotropy", "KHR_materials_dispersion", "KHR_materials_variants",
    "KHR_lights_punctual", "KHR_mesh_quantization", "EXT_mesh_gpu_instancing",
}


class ExportError(ValueError):
    """Invalid invocation or an unsafe file boundary."""


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _json(data):
    if len(data) > MAX_JSON:
        raise ValueError("JSON exceeds the inspection limit")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))


def _relative(value, *, uri=False):
    if not isinstance(value, str) or not value or "\0" in value or "\\" in value:
        raise ExportError("Expected a nonempty local relative path without backslashes")
    if uri:
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ExportError("Whitespace or control characters are not allowed in dependency URIs")
        parts = urlsplit(value)
        if parts.scheme or parts.netloc or parts.query or parts.fragment:
            raise ExportError("Remote, absolute, query and fragment URIs are not local dependencies")
        if re.search(r"%(?![0-9A-Fa-f]{2})", value):
            raise ExportError("Malformed percent escape in dependency URI")
        value = unquote(value, errors="strict")
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts or ":" in value
            or "\0" in value or "\\" in value or not path.parts):
        raise ExportError("Absolute paths and parent traversal are not allowed")
    return path


def _file(path):
    before = path.stat()
    if not path.is_file():
        raise ExportError("Dependency must be a regular file")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    signature = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if signature(before) != signature(after):
        raise ExportError("File changed during inspection")
    return {"bytes": after.st_size, "sha256": digest.hexdigest()}


class _Inspection:
    def __init__(self, root):
        self.root = root
        self.files = {}
        self.embedded = []
        self.issues = []
        self.edges = []
        self.buffer_sources = {}

    def issue(self, code, locator, message, status="incomplete"):
        self.issues.append({"code": code, "locator": locator, "message": message, "status": status})

    def safe_path(self, base, reference, *, uri=False):
        relative = _relative(reference, uri=uri)
        candidate = base.joinpath(*relative.parts)
        try:
            rel = candidate.relative_to(self.root)
        except ValueError as exc:
            raise ExportError("Dependency escapes the selected root") from exc
        current = self.root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise ExportError("Symlinks are not allowed inside an export bundle")
        return candidate

    def add(self, base, reference, role, locator, *, uri=False):
        try:
            path = self.safe_path(base, reference, uri=uri)
            name = path.relative_to(self.root).as_posix()
            self.edges.append({"from": locator, "path": name, "role": role})
            if name not in self.files:
                self.files[name] = {"path": name, **_file(path), "roles": []}
            if role not in self.files[name]["roles"]:
                self.files[name]["roles"].append(role)
            return path, self.files[name]
        except (ExportError, OSError, UnicodeError, ValueError) as exc:
            self.issue("unsafe_or_missing_dependency", locator,
                       "Dependency is missing or unreadable" if isinstance(exc, OSError)
                       else "Dependency contains invalid text" if isinstance(exc, UnicodeError) else str(exc))
            return None, None

    def embedded_uri(self, uri, locator, retain=False):
        try:
            if not isinstance(uri, str) or not uri.startswith("data:") or "," not in uri:
                raise ValueError("Invalid data URI")
            header, payload = uri[5:].split(",", 1)
            if re.search(r"%(?![0-9A-Fa-f]{2})", payload):
                raise ValueError("Malformed percent escape in data URI")
            if len(payload) > MAX_EMBEDDED * 4 // 3 + 8:
                raise ValueError("Embedded dependency exceeds the inspection limit")
            data = (base64.b64decode(payload, validate=True) if header.endswith(";base64")
                    else unquote_to_bytes(payload))
            if not data:
                raise ValueError("Embedded dependency is empty")
            if len(data) > MAX_EMBEDDED:
                raise ValueError("Embedded dependency exceeds the inspection limit")
            if retain:
                self.buffer_sources[locator] = data
            self.embedded.append({"locator": locator, "bytes": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest(), "storage": "data_uri"})
            return len(data)
        except (ValueError, binascii.Error) as exc:
            self.issue("invalid_embedded_dependency", locator, str(exc))
            return None

    def resource(self, model, uri, role, locator):
        if isinstance(uri, str) and uri.startswith("data:"):
            return self.embedded_uri(uri, locator, retain=role == "buffer")
        dependency, record = self.add(model.parent, uri, role, locator, uri=True)
        if record and role == "buffer":
            self.buffer_sources[locator] = (dependency, 0)
        return record["bytes"] if record else None


def _integer(value):
    return type(value) is int and value >= 0


def _glb(path, inspection):
    size = path.stat().st_size
    chunks = []
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise ValueError("Truncated GLB header")
        magic, version, length = struct.unpack("<4sII", header)
        if magic != b"glTF" or version != 2 or length != size:
            raise ValueError("Expected a glTF 2 GLB with its exact declared length")
        while stream.tell() < size:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("Truncated GLB chunk header")
            count, kind = struct.unpack("<II", header)
            if count % 4 or count > size - stream.tell():
                raise ValueError("Invalid GLB chunk size")
            offset = stream.tell()
            if kind == 0x4E4F534A:
                if chunks or count > MAX_JSON:
                    raise ValueError("GLB must start with one bounded JSON chunk")
                document = _json(stream.read(count))
            else:
                stream.seek(count, 1)
            chunks.append((kind, offset, count))
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError("GLB has no first JSON chunk")
    if any(kind == 0x004E4942 and index != 1 for index, (kind, _, _) in enumerate(chunks)):
        raise ValueError("GLB BIN must be the second chunk")
    if len([chunk for chunk in chunks if chunk[0] == 0x004E4942]) > 1:
        raise ValueError("Duplicate GLB BIN chunk")
    if any(kind not in {0x4E4F534A, 0x004E4942} for kind, _, _ in chunks):
        inspection.issue("unknown_glb_chunk", "glb", "Unknown GLB chunk contents were not inspected", "not_assessed")
    binary = next(((offset, count) for kind, offset, count in chunks if kind == 0x004E4942), None)
    return document, binary


def _gltf(path, inspection):
    if path.suffix.lower() == ".glb":
        document, binary = _glb(path, inspection)
    else:
        if path.stat().st_size > MAX_JSON:
            raise ValueError("glTF JSON exceeds the inspection limit")
        document, binary = _json(path.read_bytes()), None
    if (not isinstance(document, dict) or not isinstance(document.get("asset"), dict)
            or document["asset"].get("version") != "2.0"
            or document["asset"].get("minVersion", "2.0") != "2.0"):
        raise ValueError("Expected a glTF 2.0 asset")
    for field in ("buffers", "bufferViews", "images", "textures", "extensionsUsed", "extensionsRequired"):
        if not isinstance(document.get(field, []), list):
            raise ValueError(f"glTF {field} must be an array")
    used = set()
    def extensions(value):
        if isinstance(value, dict):
            ext = value.get("extensions", {})
            if not isinstance(ext, dict):
                raise ValueError("glTF extensions must be an object")
            used.update(ext)
            for item in value.values():
                extensions(item)
        elif isinstance(value, list):
            for item in value:
                extensions(item)
    extensions(document)
    for name in document.get("extensionsUsed", []) + document.get("extensionsRequired", []):
        if not isinstance(name, str):
            raise ValueError("glTF extension names must be strings")
        used.add(name)
    for name in sorted(used - KNOWN_EXTENSIONS):
        inspection.issue("uninspectable_extension", name,
                         "Extension-specific dependencies are not covered by this checker", "not_assessed")
    buffers = []
    for index, item in enumerate(document.get("buffers", [])):
        locator = f"buffers[{index}]"
        if not isinstance(item, dict) or not _integer(item.get("byteLength")) or item["byteLength"] < 1:
            raise ValueError("Each glTF buffer needs a positive integer byteLength")
        if "uri" in item:
            actual = inspection.resource(path, item["uri"], "buffer", locator)
            if actual is not None and actual < item["byteLength"]:
                inspection.issue("buffer_length_mismatch", locator, "Buffer is shorter than its declared byteLength")
        elif binary is not None and index == 0:
            offset, actual = binary
            inspection.buffer_sources[locator] = (path, offset)
            if not item["byteLength"] <= actual <= item["byteLength"] + 3:
                inspection.issue("buffer_length_mismatch", locator, "GLB BIN bytes do not match buffer length plus padding")
            with path.open("rb") as stream:
                stream.seek(offset)
                remaining, digest = actual, hashlib.sha256()
                while remaining:
                    block = stream.read(min(remaining, 1024 * 1024))
                    if not block:
                        raise ValueError("Truncated GLB BIN data")
                    digest.update(block)
                    remaining -= len(block)
                stream.seek(offset + item["byteLength"])
                if stream.read(max(0, actual - item["byteLength"])).strip(b"\0"):
                    inspection.issue("invalid_glb_padding", locator, "GLB BIN padding must contain zeros")
            inspection.embedded.append({"locator": locator, "bytes": actual,
                                        "sha256": digest.hexdigest(), "storage": "glb_bin"})
        else:
            actual = None
            inspection.issue("missing_buffer_uri", locator, "Buffer has neither a local URI nor a GLB BIN chunk")
        buffers.append(item["byteLength"] if actual is not None else None)
    if binary and not any("uri" not in item for item in document.get("buffers", [])):
        inspection.issue("unreferenced_glb_bin", "glb", "GLB BIN chunk has no corresponding buffer")
    views = []
    for index, view in enumerate(document.get("bufferViews", [])):
        valid = (isinstance(view, dict) and _integer(view.get("buffer"))
                 and _integer(view.get("byteOffset", 0)) and _integer(view.get("byteLength"))
                 and view["byteLength"] > 0
                 and view["buffer"] < len(buffers) and buffers[view["buffer"]] is not None
                 and view.get("byteOffset", 0) + view["byteLength"] <= buffers[view["buffer"]])
        if not valid:
            inspection.issue("invalid_buffer_view", f"bufferViews[{index}]", "Buffer view exceeds or refers to an unavailable buffer")
        views.append(valid)
    images = document.get("images", [])
    for index, item in enumerate(images):
        locator = f"images[{index}]"
        if not isinstance(item, dict) or (("uri" in item) == ("bufferView" in item)):
            inspection.issue("invalid_image_source", locator, "Image requires exactly one URI or bufferView")
        elif "uri" in item:
            inspection.resource(path, item["uri"], "texture", locator)
        elif (not _integer(item["bufferView"]) or item["bufferView"] >= len(views)
              or not views[item["bufferView"]] or not isinstance(item.get("mimeType"), str) or not item["mimeType"]):
            inspection.issue("invalid_image_view", locator, "Embedded image requires a valid bufferView and mimeType")
        else:
            view = document["bufferViews"][item["bufferView"]]
            origin = inspection.buffer_sources[f"buffers[{view['buffer']}]"]
            start, length = view.get("byteOffset", 0), view["byteLength"]
            digest = hashlib.sha256()
            if isinstance(origin, bytes):
                digest.update(origin[start:start + length])
            else:
                file_path, buffer_offset = origin
                with file_path.open("rb") as stream:
                    stream.seek(buffer_offset + start)
                    remaining = length
                    while remaining:
                        block = stream.read(min(remaining, 1024 * 1024))
                        if not block:
                            raise ValueError("Truncated embedded image buffer view")
                        digest.update(block)
                        remaining -= len(block)
            inspection.embedded.append({"locator": locator, "storage": "buffer_view",
                                        "buffer_view": item["bufferView"], "bytes": length,
                                        "sha256": digest.hexdigest()})
    for index, texture in enumerate(document.get("textures", [])):
        if not isinstance(texture, dict):
            raise ValueError("glTF textures must contain objects")
        sources = [texture["source"]] if "source" in texture else []
        for name in ("KHR_texture_basisu", "EXT_texture_webp", "EXT_texture_avif"):
            ext = texture.get("extensions", {}).get(name)
            if ext is not None:
                if not isinstance(ext, dict) or "source" not in ext:
                    raise ValueError("Texture extension is missing its image source")
                sources.append(ext["source"])
        if any(not _integer(source) or source >= len(images) for source in sources) or not sources:
            inspection.issue("invalid_texture_source", f"textures[{index}]", "Texture has no valid image source")


def _lines(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        number = 0
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            number += 1
            if len(line) > MAX_LINE:
                raise ValueError("OBJ/MTL line exceeds the inspection limit")
            if line.rstrip().endswith("\\"):
                raise ValueError("OBJ/MTL continued lines are not covered by this checker")
            try:
                fields = shlex.split(line, comments=True, posix=True)
            except ValueError as exc:
                raise ValueError(f"Invalid OBJ/MTL quoting at line {number}") from exc
            if fields:
                yield number, fields


def _map_path(fields):
    fixed = {"-blendu": 1, "-blendv": 1, "-boost": 1, "-mm": 2, "-texres": 1,
             "-clamp": 1, "-bm": 1, "-imfchan": 1, "-type": 1, "-cc": 1, "-colorspace": 1}
    index = 1
    while index < len(fields) and fields[index].startswith("-"):
        option = fields[index]
        index += 1
        if option in {"-o", "-s", "-t"}:
            start = index
            while index < len(fields) and index - start < 3:
                try:
                    float(fields[index])
                except ValueError:
                    break
                index += 1
            if start == index:
                raise ValueError("MTL vector option has no numeric value")
        elif option in fixed:
            index += fixed[option]
        else:
            raise ValueError("Unsupported MTL map option; cannot establish its filename")
    if index >= len(fields):
        raise ValueError("MTL texture map has no filename")
    return " ".join(fields[index:])


def _obj(path, inspection):
    libraries, used, declared = [], set(), set()
    for number, fields in _lines(path):
        if fields[0] == "mtllib":
            if len(fields) == 1:
                inspection.issue("empty_material_library", f"obj:{number}", "mtllib has no filename")
            for name in fields[1:]:
                library, _ = inspection.add(path.parent, name, "material", f"obj:{number}")
                if library and library not in libraries:
                    libraries.append(library)
        elif fields[0] == "usemtl":
            used.add(" ".join(fields[1:]))
        elif fields[0] in {"call", "csh"}:
            inspection.issue("unsupported_obj_directive", f"obj:{number}", "External OBJ scripts are never executed or resolved", "not_assessed")
    for library in libraries:
        for number, fields in _lines(library):
            key = fields[0].lower()
            if key == "newmtl":
                declared.add(" ".join(fields[1:]))
            elif key.startswith("map_") or key in {"bump", "disp", "decal", "refl", "norm"}:
                locator = f"{library.relative_to(inspection.root).as_posix()}:{number}"
                try:
                    reference = _map_path(fields)
                except ValueError as exc:
                    inspection.issue("uninspectable_mtl_map", locator, str(exc), "not_assessed")
                    continue
                inspection.add(library.parent, reference, "texture", locator)
    for material in sorted(used - declared):
        inspection.issue("missing_material", "obj", f"Used material is not declared in a resolved MTL: {material}")


def _declaration(path, source, inspection):
    if path.stat().st_size > MAX_JSON:
        raise ValueError("Dependency declaration exceeds the inspection limit")
    value = _json(path.read_bytes())
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1
            or value.get("kind") != "funavatar_export_dependency_declaration"
            or value.get("source_sha256") != source["sha256"]
            or value.get("exhaustive") is not True
            or not isinstance(value.get("basis"), str) or not value["basis"].strip()
            or not isinstance(value.get("dependencies"), list)
            or not isinstance(value.get("native_evidence"), dict)):
        raise ValueError("Expected an exhaustive dependency declaration tied to the exact source SHA-256, with a basis")
    evidence = value["native_evidence"]
    if (evidence.get("source_sha256") != source["sha256"]
            or not isinstance(evidence.get("sha256"), str)
            or not SHA256.fullmatch(evidence["sha256"])):
        raise ValueError("Native evidence must be hash-bound to the exact model revision")
    _, measured = inspection.add(inspection.root, evidence.get("path"), "native_evidence", "declaration")
    if measured and measured["sha256"] != evidence["sha256"]:
        inspection.issue("native_evidence_hash_mismatch", "declaration", "Native export evidence changed")
    seen = set()
    for item in value["dependencies"]:
        if (not isinstance(item, dict) or not isinstance(item.get("sha256"), str)
                or not SHA256.fullmatch(item["sha256"]) or not isinstance(item.get("path"), str)
                or item["path"] in seen):
            raise ValueError("Each declared dependency needs a unique local path and exact SHA-256")
        seen.add(item["path"])
        _, actual = inspection.add(inspection.root, item["path"], "declared_dependency", "declaration")
        if actual and actual["sha256"] != item["sha256"]:
            inspection.issue("declared_hash_mismatch", item["path"], "Dependency changed since the native export declaration")
    return {"asserted_by": value["basis"].strip(), "exhaustive": True, "native_evidence": {"path": measured["path"] if measured else None,
                                "sha256": evidence["sha256"], "source_sha256": source["sha256"]}}


def inspect_export(model, *, root=None, declaration=None):
    """Return a deterministic dependency manifest; it never writes or fetches files.

    `complete` only covers resolved dependencies. For opaque formats it covers an
    explicitly declared exhaustive set, not dependencies inferred from the model.
    """
    model = Path(model).expanduser()
    if ".." in model.parts or model.is_symlink():
        raise ExportError("Model path must not traverse parents or be a symlink")
    model = model.absolute()
    selected_root = Path(root).expanduser().absolute() if root is not None else model.parent
    if selected_root.is_symlink() or not selected_root.is_dir():
        raise ExportError("Export root must be an existing directory, not a symlink")
    input_root = selected_root
    selected_root = selected_root.resolve(strict=True)
    # Retain un-resolved descendants so an in-bundle symlink cannot disappear.
    if root is None:
        model = selected_root / model.name
    else:
        try:
            relative_model = model.relative_to(Path(root).expanduser().absolute())
        except ValueError as exc:
            raise ExportError("Model must be inside the selected export root") from exc
        model = selected_root / relative_model
    inspection = _Inspection(selected_root)
    try:
        relative_model = model.relative_to(selected_root).as_posix()
    except ValueError as exc:
        raise ExportError("Model must be inside the selected export root") from exc
    _, source = inspection.add(selected_root, relative_model, "model", "source")
    if source is None:
        raise ExportError("Model must be a safe, existing regular file")
    basis = "format_dependencies"
    format_name = model.suffix.lower().lstrip(".") or "unknown"
    try:
        if format_name in {"gltf", "glb"}:
            _gltf(model, inspection)
        elif format_name == "obj":
            _obj(model, inspection)
        else:
            basis = "uninspectable_format"
            if declaration is None:
                inspection.issue("uninspectable_format", "source",
                                 "This format needs an explicit native export dependency declaration", "not_assessed")
        if declaration is not None:
            declared_path = Path(declaration).expanduser().absolute()
            try:
                relative_declaration = declared_path.relative_to(input_root)
            except ValueError as exc:
                raise ValueError("Declaration must be inside the selected root") from exc
            declared_path, _ = inspection.add(selected_root, relative_declaration.as_posix(), "declaration", "declaration")
            if declared_path:
                declaration_basis = _declaration(declared_path, source, inspection)
                if basis == "uninspectable_format":
                    basis = "declared_dependencies"

            else:
                declaration_basis = None
        else:
            declaration_basis = None
    except (ValueError, OSError, UnicodeError, RecursionError) as exc:
        inspection.issue("invalid_or_uninspectable_export", "source",
                         "Export or declaration is unreadable" if isinstance(exc, OSError)
                         else "Export contains invalid UTF-8" if isinstance(exc, UnicodeError) else str(exc))
        declaration_basis = None
    # Check the exact parsed revision and sidecars again before returning evidence.
    for name, record in sorted(inspection.files.items()):
        try:
            inspection.safe_path(selected_root, name)
            if _file(selected_root / name) != {key: record[key] for key in ("bytes", "sha256")}:
                raise ExportError("File changed while its dependencies were being inspected")
        except (ValueError, OSError) as exc:
            inspection.issue("revision_changed", name,
                             "Recorded file is missing or unreadable" if isinstance(exc, OSError) else str(exc))
        record["roles"].sort()
    statuses = {issue["status"] for issue in inspection.issues}
    report = {"schema_version": 1, "kind": "funavatar_export_bundle", "format": format_name,
              "status": "incomplete" if "incomplete" in statuses else "not_assessed" if statuses else "complete",
              "scope": "file_dependencies_only",
              "basis": basis, "source": {key: source[key] for key in ("path", "bytes", "sha256")},
              "files": [inspection.files[name] for name in sorted(inspection.files)],
              "embedded": sorted(inspection.embedded, key=lambda value: value["locator"]),
              "dependencies": sorted(inspection.edges, key=lambda value: (value["from"], value["path"], value["role"])),
              "issues": sorted(inspection.issues, key=lambda value: (value["locator"], value["code"], value["message"])),
              "declaration": declaration_basis,
              "limitations": "Dependency resolution and hashes only; no rendering, texture decoding, geometry, rig, animation, SDK or client validation. Opaque formats use the explicitly declared set, not inferred dependencies."}
    report["bundle_sha256"] = fingerprint(report)
    return report


def export_check(model, root=None, declaration=None, out=None):
    report = inspect_export(model, root=root, declaration=declaration)
    if out:
        output = Path(out).expanduser()
        if output.is_symlink():
            raise ExportError("Refusing a symlink output")
        # Exclusive creation preserves every existing report and source file.
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    return report, {"complete": 0, "incomplete": 1, "not_assessed": 3}[report["status"]]
