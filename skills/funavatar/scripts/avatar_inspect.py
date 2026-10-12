#!/usr/bin/env python3
"""Study Unity packages offline. Never extract, import, or execute their assets.

YAML observations are a bounded line index, not a complete YAML/Unity parser.
Counts describe archive contents, never an active avatar or SDK/runtime result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import tarfile
import zipfile
import zlib

MIB = 1024 * 1024
GUID = re.compile(r"[0-9a-fA-F]{32}\Z")
TEXT_ASSETS = {".prefab", ".controller", ".overridecontroller", ".anim", ".mat", ".asset", ".unity"}
DOCUMENT = re.compile(r"^--- !u!(\d{1,10}) &(-?\d{1,20})(?: stripped)?\s*$")
FIELD = re.compile(r"^( *)(- )?([A-Za-z_][A-Za-z_0-9]*):(?:\s*(.*))?$")
SCALAR_KEYS = {"m_Name", "name", "m_Type", "type", "valueType", "defaultValue", "saved",
               "networkSynced", "m_DefaultFloat", "m_DefaultInt", "m_DefaultBool",
               "m_WriteDefaultValues", "m_ConditionMode", "m_ConditionEvent",
               "m_ConditionTreshold", "m_Duration", "m_ExitTime", "m_HasExitTime",
               "m_TransitionDuration", "m_TransitionOffset", "m_InterruptionSource",
               "m_DefaultWeight", "m_BlendingMode", "m_Weight", "m_BlendType",
               "m_BlendParameter", "m_BlendParameterY", "path", "attribute", "classID",
               "propertyName", "m_LoopTime", "m_Enabled", "m_Active", "m_UpdateMode",
               "m_EditorClassIdentifier", "menuName", "isSave", "isLocalOnly", "referencePath",
               "LockMode", "mangleNames", "freezeBlendShape", "removeUnusedObjects",
               "optimizePhysBone", "optimizeAnimator", "mergeSkinnedMesh", "pull", "spring",
               "stiffness", "gravity", "radius", "height", "shapeType"}
WRAPPED_PPTR_MAX_BYTES = 1024
WRAPPED_PPTR_MAX_LINES = 8


class StudyError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    source_bytes: int = 2 * 1024 * MIB
    decompressed_bytes: int = 8 * 1024 * MIB
    members: int = 100_000
    metadata_bytes: int = MIB
    metadata_total_bytes: int = 128 * MIB
    directory_bytes: int = 64 * MIB
    text_asset_bytes: int = 16 * MIB
    text_total_bytes: int = 64 * MIB
    records: int = 100_000
    report_bytes: int = 64 * MIB


class Budget:
    def __init__(self, limits):
        self.limits = limits
        self.bytes = self.members = self.text_bytes = self.metadata_bytes = self.records = 0

    def add(self, key, count, maximum):
        value = getattr(self, key) + count
        if value > maximum:
            raise StudyError("Inspection limit exceeded: " + key)
        setattr(self, key, value)

    def member(self):
        self.add("members", 1, self.limits.members)

    def record(self):
        self.add("records", 1, self.limits.records)


class CountedReader(io.RawIOBase):
    def __init__(self, raw, budget):
        self.raw, self.budget = raw, budget
        self.count, self.tail = 0, b""

    def readable(self):
        return True

    def read(self, size=-1):
        remaining = self.budget.limits.decompressed_bytes - self.budget.bytes
        # Bound even a caller's unbounded read; the one extra byte detects overflow.
        size = min(size if size >= 0 else MIB, remaining + 1, MIB)
        result = self.raw.read(size)
        self.budget.add("bytes", len(result), self.budget.limits.decompressed_bytes)
        self.count += len(result)
        self.tail = (self.tail + result)[-1024:]
        return result


def safe_path(name, *, allow_root=False):
    if (not isinstance(name, str) or not name or any(not c.isprintable() for c in name)
            or "\\" in name or ":" in name or name.startswith("/")):
        raise StudyError("Unsafe archive/asset pathname")
    path = PurePosixPath(name)
    if ".." in path.parts or (str(path) == "." and not allow_root):
        raise StudyError("Unsafe archive/asset pathname")
    return path.as_posix()


def file_signature(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read_hash(stream, *, retain=False, expected=None):
    digest, chunks, count = hashlib.sha256(), [], 0
    while True:
        block = stream.read(MIB)
        if not block:
            break
        count += len(block)
        if expected is not None and count > expected:
            raise StudyError("Archive member exceeds its declared size")
        digest.update(block)
        if retain:
            chunks.append(block)
    if expected is not None and count != expected:
        raise StudyError("Truncated archive member")
    return digest.hexdigest(), b"".join(chunks) if retain else None


def zip_directory_guard(stream, budget):
    """Check central-directory size/count before ZipFile allocates its inventory."""
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(max(0, size - 65_557))
    tail = stream.read(65_557)
    offset = tail.rfind(b"PK\x05\x06")
    while offset >= 0:
        if offset + 22 <= len(tail):
            values = struct.unpack_from("<4s4H2LH", tail, offset)
            if offset + 22 + values[-1] == len(tail):
                break
        offset = tail.rfind(b"PK\x05\x06", 0, offset)
    if offset < 0:
        raise StudyError("Missing/truncated ZIP directory")
    _, disk, cd_disk, local_count, count, cd_size, cd_offset, _ = values
    if disk or cd_disk or local_count != count:
        raise StudyError("Multi-disk ZIP is unsupported")
    if count == 0xffff or cd_size == 0xffffffff or cd_offset == 0xffffffff:
        end_offset = size - len(tail) + offset
        if end_offset < 20:
            raise StudyError("Truncated ZIP64 locator")
        stream.seek(end_offset - 20)
        locator = stream.read(20)
        if len(locator) != 20:
            raise StudyError("Truncated ZIP64 locator")
        signature, disk, location, disks = struct.unpack("<4sLQL", locator)
        if signature != b"PK\x06\x07" or disk or disks != 1:
            raise StudyError("Unsupported ZIP64 locator")
        stream.seek(location)
        header = stream.read(56)
        if len(header) != 56:
            raise StudyError("Truncated ZIP64 directory")
        signature, length, _, _, disk, cd_disk, local_count, count, cd_size, cd_offset = struct.unpack("<4sQ2H2L4Q", header)
        if (signature != b"PK\x06\x06" or length < 44 or length > budget.limits.metadata_bytes
                or disk or cd_disk or local_count != count):
            raise StudyError("Unsupported/oversized ZIP64 directory")
    if count > budget.limits.members or cd_size > budget.limits.directory_bytes:
        raise StudyError("ZIP directory inspection limit exceeded")
    if cd_offset + cd_size > size:
        raise StudyError("ZIP directory is outside the source")
    stream.seek(0)


def field_path(stack):
    return "".join(token if token.startswith("[") else ("." if i else "") + token
                   for i, (_, token, _) in enumerate(stack))


def scalar(value):
    value = value.strip()
    if len(value) > 256:
        return {"omitted": "scalar_over_256_characters"}
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"-?\d{1,20}", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", value):
        number = float(value)
        if abs(number) != float("inf"):
            return number
    return value.strip('"\'')


def unity_integer(value, *, class_id=False):
    if not re.fullmatch(r"-?\d{1,20}", value):
        raise StudyError("Unity integer exceeds the supported signed width")
    number = int(value)
    minimum, maximum = (0, (1 << 31) - 1) if class_id else (-(1 << 63), (1 << 63) - 1)
    if not minimum <= number <= maximum:
        raise StudyError("Unity integer exceeds the supported signed width")
    return number


def flow_reference(body, *, wrapped=False):
    if wrapped:
        values = {}
        for field in body.split(","):
            if not field.strip():
                continue
            match = re.fullmatch(r"\s*(fileID|guid|type):\s*([^\s,{}]+)\s*", field)
            if match is None or match.group(1) in values:
                raise StudyError("Unsupported/malformed wrapped flat PPtr")
            values[match.group(1)] = match.group(2)
        if "type" in values:
            unity_integer(values["type"])
        if not ("guid" in values or "fileID" in values):
            raise StudyError("Wrapped flow is not a PPtr")
    file_ids = re.findall(r"\bfileID:\s*([^,}\s]+)", body)
    guids = re.findall(r"\bguid:\s*([^,}\s]+)", body)
    if len(file_ids) > 1 or len(guids) > 1 or (guids and not GUID.fullmatch(guids[0])):
        raise StudyError("Duplicate/malformed flow reference field")
    file_id = unity_integer(file_ids[0]) if file_ids else None
    guid = guids[0].lower() if guids else None
    return {"file_id": file_id, "guid": guid} if file_id is not None or guid is not None else None


def yaml_index(raw, budget):
    """Index Unity's usual document headers, indented keys and PPtr references."""
    text = raw.decode("utf-8-sig")
    documents, references, fields, stack, counters, parts = [], [], [], [], {}, {}
    document_id, class_id, root_type = None, None, None
    seen_documents = set()
    pending = None
    for line_number, line in enumerate(text.splitlines(), 1):
        if pending is not None:
            if line.startswith(("---", "%")):
                raise StudyError("Unterminated wrapped PPtr before document header")
            pending["lines"] += 1
            pending["bytes"] += 1 + len(line.encode("utf-8"))
            if (pending["lines"] > WRAPPED_PPTR_MAX_LINES
                    or pending["bytes"] > WRAPPED_PPTR_MAX_BYTES):
                raise StudyError("Wrapped PPtr inspection limit exceeded")
            pending["body"] += "\n" + line
            if "{" in line:
                raise StudyError("Nested flow is unsupported in a wrapped PPtr")
            if "}" not in line:
                continue
            body, trailing = pending["body"].split("}", 1)
            if trailing.strip():
                raise StudyError("Trailing data is unsupported after a wrapped PPtr")
            reference = flow_reference(body, wrapped=True)
            budget.record()
            references.append(pending["provenance"] | reference | {"end_line": line_number})
            pending = None
            continue
        header = DOCUMENT.fullmatch(line)
        if line.startswith("--- !u!") and header is None:
            raise StudyError("Malformed/oversized Unity document header")
        if header:
            class_id = unity_integer(header.group(1), class_id=True)
            document_id = unity_integer(header.group(2))
            if document_id in seen_documents:
                raise StudyError("Duplicate YAML document fileID")
            seen_documents.add(document_id)
            stack, counters, root_type = [], {}, None
            budget.record()
            documents.append({"class_id": class_id, "file_id": document_id, "line": line_number})
            continue
        if document_id is None or not line.strip() or line.lstrip().startswith(("#", "%")):
            continue
        match = FIELD.fullmatch(line)
        key, value, path = None, "", field_path(stack)
        is_list = bool(re.match(r"^ *-($| )", line))
        indent = len(line) - len(line.lstrip(" "))
        if match or is_list:
            if is_list:
                while stack and (stack[-1][0] > indent or (stack[-1][0] == indent and stack[-1][2])):
                    stack.pop()
                parent = field_path(stack)
                marker = (parent, indent)
                index = counters.get(marker, -1) + 1
                counters[marker] = index
                stack.append((indent, "[" + str(index) + "]", True))
                path = field_path(stack)
            else:
                while stack and stack[-1][0] >= indent:
                    stack.pop()
            if match:
                key, value = match.group(3), match.group(4) or ""
                parent = field_path(stack)
                path = parent + ("." if parent else "") + key
                if root_type is None and indent == 0:
                    root_type = key
                    documents[-1]["root_type"] = key
                if key in {"guid", "fileID"} and not value.startswith(("{", "[")):
                    part = parts.setdefault((document_id, parent), {"document_file_id": document_id,
                        "class_id": class_id, "field_path": parent, "line": line_number})
                    if key in part:
                        raise StudyError("Duplicate YAML reference field")
                    part[key] = value.strip()
                    part[key + "_line"] = line_number
                if key in SCALAR_KEYS and value and not value.startswith(("{", "[", "|", ">")):
                    low = path.lower()
                    role = ("parameter" if "parameter" in low else "menu_control" if "controls[" in low
                            else "animation_binding" if key in {"path", "attribute", "classID", "propertyName"}
                            else "controller" if root_type and root_type.startswith(("Animator", "BlendTree"))
                            else "configuration")
                    budget.record()
                    fields.append({"document_file_id": document_id, "class_id": class_id,
                        "field_path": path, "line": line_number, "role": role, "value": scalar(value)})
                if not value:
                    stack.append((indent + (2 if is_list else 0), key, False))
        for flow in re.finditer(r"\{([^{}]*)\}", line):
            reference = flow_reference(flow.group(1))
            if reference is None:
                continue
            budget.record()
            references.append({"document_file_id": document_id, "class_id": class_id,
                "field_path": path, "line": line_number} | reference)
        opening = re.search(r"\{([^{}]*)$", line)
        if opening and re.search(r"\b(?:fileID|guid|type):", opening.group(1)):
            body = opening.group(1)
            if len(body.encode("utf-8")) > WRAPPED_PPTR_MAX_BYTES:
                raise StudyError("Wrapped PPtr inspection limit exceeded")
            pending = {"body": body, "lines": 1, "bytes": len(body.encode("utf-8")), "provenance": {"document_file_id": document_id,
                "class_id": class_id, "field_path": path, "line": line_number}}
    if pending is not None:
        raise StudyError("Unterminated wrapped PPtr at end of YAML")
    for part in parts.values():
        guid = part.get("guid")
        file_id = part.get("fileID")
        if guid is not None and not GUID.fullmatch(guid):
            raise StudyError("Malformed multiline reference GUID")
        file_id = unity_integer(file_id) if file_id is not None else None
        budget.record()
        references.append({key: value for key, value in part.items() if key not in {"guid", "fileID"}} |
            {"guid": guid.lower() if guid else None, "file_id": file_id})
    return {"parser": "bounded_unity_line_index", "documents": documents,
            "references": references, "field_observations": fields}


def package_index(stream, label, budget):
    entries, member_names, paths = {}, set(), set()

    class SafeTarInfo(tarfile.TarInfo):
        def _proc_member(self, archive):
            # Reject extended/special headers before tarfile can allocate their payloads.
            budget.member()
            if self.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
                raise StudyError("Unsupported TAR member (links/special/extended headers)")
            name = safe_path(self.name, allow_root=self.isdir())
            folded = name.casefold()
            if folded in member_names:
                raise StudyError("Duplicate TAR member")
            member_names.add(folded)
            if self.size < 0 or self.size > budget.limits.decompressed_bytes - budget.bytes:
                raise StudyError("TAR member exceeds inspection limit")
            return super()._proc_member(archive)

    with gzip.GzipFile(fileobj=stream) as compressed:
        counted = CountedReader(compressed, budget)
        with tarfile.open(fileobj=counted, mode="r|", tarinfo=SafeTarInfo) as archive:
            for member in archive:
                if not member.isfile():
                    continue
                components = PurePosixPath(member.name).parts
                if len(components) != 2 or not GUID.fullmatch(components[0]):
                    raise StudyError("Unexpected Unity package member layout")
                guid, leaf = components[0].lower(), components[1]
                if leaf not in {"asset", "asset.meta", "pathname", "preview.png"}:
                    raise StudyError("Unsupported Unity package member")
                entry = entries.setdefault(guid, {"guid": guid})
                if leaf in entry:
                    raise StudyError("Duplicate GUID member")
                retain = leaf in {"pathname", "asset.meta"} or (leaf == "asset" and member.size <= budget.limits.text_asset_bytes)
                if leaf in {"pathname", "asset.meta"} and member.size > budget.limits.metadata_bytes:
                    raise StudyError("Unity metadata inspection limit exceeded")
                if leaf in {"pathname", "asset.meta"}:
                    budget.add("metadata_bytes", member.size, budget.limits.metadata_total_bytes)
                with archive.extractfile(member) as content:
                    digest, raw = read_hash(content, retain=retain, expected=member.size)
                entry[leaf] = {"bytes": member.size, "sha256": digest}
                if leaf in {"pathname", "asset.meta"}:
                    entry[leaf]["_text"] = raw.decode("utf-8-sig")
                elif leaf == "asset" and raw is not None and raw.lstrip(b"\xef\xbb\xbf").startswith(b"%YAML"):
                    budget.add("text_bytes", len(raw), budget.limits.text_total_bytes)
                    entry[leaf]["_yaml"] = raw
            required_end = archive.offset + 1024
        # Read the gzip footer and remaining ZIP member bytes, checking CRC/truncation.
        while counted.read(MIB):
            pass
        if counted.count < required_end or counted.count % 512 or counted.tail != b"\0" * 1024:
            raise StudyError("Missing/truncated TAR end records")
    result = []
    for guid, entry in sorted(entries.items()):
        if "pathname" not in entry:
            raise StudyError("Unity GUID has no pathname")
        path = safe_path(entry.pop("pathname")["_text"].rstrip("\r\n"))
        if path.casefold() in paths:
            raise StudyError("Duplicate Unity asset pathname")
        paths.add(path.casefold())
        entry["path"], entry["extension"] = path, PurePosixPath(path).suffix.lower()
        meta = entry.get("asset.meta", {}).pop("_text", None)
        if meta is not None:
            meta_guids = re.findall(r"^guid:\s*([0-9a-fA-F]{32})\s*$", meta, re.MULTILINE)
            if len(meta_guids) != 1 or meta_guids[0].lower() != guid:
                raise StudyError("Missing/duplicate/mismatched meta GUID")
        asset = entry.get("asset")
        if asset is None:
            entry["format"] = "folder_or_metadata_only"
        else:
            raw = asset.pop("_yaml", None)
            if raw is not None and entry["extension"] in TEXT_ASSETS:
                entry["format"] = "unity_yaml"
                entry["yaml"] = yaml_index(raw, budget)
            else:
                entry["format"] = "opaque_not_parsed"
        result.append(entry)
    return {"name": label, "entries": result}


def resolve_references(packages):
    union, issues, counts, shared = defaultdict(list), [], Counter(), []
    for package in packages:
        for entry in package["entries"]:
            union[entry["guid"]].append((package["name"], entry))
    conflicts = set()
    for guid, matches in sorted(union.items()):
        versions = {(e["path"], e.get("asset", {}).get("sha256"), e.get("asset.meta", {}).get("sha256"))
                    for _, e in matches}
        if len(versions) > 1:
            conflicts.add(guid)
            issues.append({"code": "cross_package_guid_conflict", "guid": guid,
                           "packages": [name for name, _ in matches]})
        elif len(matches) > 1:
            shared.append({"guid": guid, "path": matches[0][1]["path"],
                           "packages": [name for name, _ in matches]})
    for package in packages:
        local = {entry["guid"]: entry for entry in package["entries"]}
        dependencies, external, package_counts = set(), set(), Counter()
        for entry in package["entries"]:
            own_ids = {d["file_id"] for d in entry.get("yaml", {}).get("documents", [])}
            for reference in entry.get("yaml", {}).get("references", []):
                guid, file_id = reference["guid"], reference["file_id"]
                if file_id == 0:
                    resolution = "null"
                elif guid is None:
                    resolution = "local_file_id" if file_id in own_ids else "unresolved_local_file_id"
                elif re.fullmatch(r"0000000000000000[def0]000000000000000", guid):
                    resolution = "builtin"
                elif guid in conflicts:
                    resolution = "conflicting_guid"
                elif guid in union:
                    target_package, target = next(((name, e) for name, e in union[guid] if name == package["name"]), union[guid][0])
                    resolution = "same_package" if guid in local else "other_package"
                    reference["target"] = {"package": target_package, "path": target["path"]}
                    target_ids = {d["file_id"] for d in target.get("yaml", {}).get("documents", [])}
                    reference["file_id_status"] = ("present_in_yaml" if file_id in target_ids
                        else "absent_from_yaml" if target.get("format") == "unity_yaml"
                        else "not_assessed_native_or_binary_subasset")
                    if resolution == "other_package":
                        dependencies.add(target_package)
                else:
                    resolution = "external_unresolved"
                    external.add(guid)
                reference["resolution"] = resolution
                counts[resolution] += 1
                package_counts[resolution] += 1
        package["dependencies_on_other_packages"] = sorted(dependencies)
        package["unresolved_external_guids"] = sorted(external)
        package["reference_resolution_counts"] = dict(sorted(package_counts.items()))
        package["issues"] = [{"code": "references_other_package_in_archive", "package": name}
                            for name in sorted(dependencies)]
    return {"reference_resolution_counts": dict(sorted(counts.items())), "shared_guids": shared, "issues": issues}


def inspect(source, limits=Limits()):
    source = Path(source)
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode) or source.is_symlink():
        raise StudyError("Source must be a regular file, not a symlink")
    if before.st_size > limits.source_bytes:
        raise StudyError("Source inspection limit exceeded")
    budget, packages, outer = Budget(limits), [], []
    descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        # Path and handle timestamps can differ; compare each interface to itself.
        if (not os.path.samestat(opened, before) or opened.st_size != before.st_size
                or file_signature(source.lstat()) != file_signature(before)):
            raise StudyError("Source changed before inspection")
        digest, _ = read_hash(stream, expected=before.st_size)
        stream.seek(0)
        if source.suffix.lower() == ".unitypackage":
            packages.append(package_index(stream, source.name, budget))
        elif source.suffix.lower() == ".zip":
            zip_directory_guard(stream, budget)
            with zipfile.ZipFile(stream) as archive:
                seen = set()
                for member in archive.infolist():
                    budget.member()
                    name = safe_path(member.filename, allow_root=member.is_dir())
                    if name.casefold() in seen:
                        raise StudyError("Duplicate ZIP member")
                    seen.add(name.casefold())
                    mode = member.external_attr >> 16
                    if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR} or member.flag_bits & 1:
                        raise StudyError("ZIP links/special/encrypted members are unsupported")
                    if member.is_dir():
                        continue
                    if member.file_size > limits.decompressed_bytes - budget.bytes:
                        raise StudyError("ZIP member exceeds inspection limit")
                    record = {"path": name, "bytes": member.file_size}
                    with archive.open(member) as content:
                        counted = CountedReader(content, budget)
                        if name.lower().endswith(".unitypackage"):
                            packages.append(package_index(counted, name, budget))
                            record["kind"] = "unitypackage"
                        else:
                            record["sha256"], _ = read_hash(counted, expected=member.file_size)
                            record["kind"] = "not_parsed"
                    outer.append(record)
        else:
            raise StudyError("Expected .zip or .unitypackage")
        if (file_signature(os.fstat(stream.fileno())) != file_signature(opened)
                or file_signature(source.lstat()) != file_signature(before)):
            raise StudyError("Source changed during inspection")
    if not packages:
        raise StudyError("No Unity package found")
    closure = resolve_references(packages)
    entries = [entry for package in packages for entry in package["entries"]]
    roles = Counter(field["role"] for entry in entries for field in entry.get("yaml", {}).get("field_observations", []))
    labels = [{"package": package["name"], "path": entry["path"], "labels": sorted(set(
        re.findall(r"(?i)(?<![a-z])(quest|android|mobile|opti(?:mized|mised)?|excellent|good|medium|poor)(?![a-z])", entry["path"])))}
        for package in packages for entry in package["entries"]]
    return {"schema": "funavatar.package_study", "schema_version": 1,
        "source": {"name": source.name, "bytes": before.st_size, "sha256": digest, "stable_stat_checked": True},
        "scope": "offline_archive_inventory_and_partial_unity_yaml_index",
        "outer_inventory": outer, "packages": packages, "closure": closure,
        "summary": {"packages": len(packages), "assets": len(entries),
            "formats": dict(Counter(e["format"] for e in entries)), "field_roles": dict(roles),
            "declared_filename_labels": [item for item in labels if item["labels"]]},
        "limits": vars(limits), "consumed": {"members": budget.members, "decompressed_bytes": budget.bytes,
            "text_bytes": budget.text_bytes, "metadata_bytes": budget.metadata_bytes, "indexed_records": budget.records},
        "limitations": ["Not a complete YAML parser; unsupported syntax and encoded/hashed bindings may be absent.",
            "Archive union resolution is not an import-order or build dependency proof; unresolved GUIDs may be external SDK/tools.",
            "Binary FBX, textures, DLL classes and native subasset fileIDs are not parsed; geometry/performance/runtime values remain unknown.",
            "Filename optimization labels and serialized fields are declarations, not measured performance or current active state.",
            "No assets, source YAML/C# bodies, license text or runtime/build certification are included; review author terms separately."]}


def write_report(report, output, limits=Limits()):
    output = Path(output)
    for parent in (output, *output.parents):
        if parent.is_symlink():
            raise StudyError("Output path must not use symlinks")
    payload = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > limits.report_bytes:
        raise StudyError("Report size inspection limit exceeded")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Existing .zip or .unitypackage; never modified")
    parser.add_argument("--out", type=Path, required=True, help="New report file; no overwrite or symlinks")
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.out):
            raise StudyError("Output already exists")
        report = inspect(args.input)
        write_report(report, args.out)
    except (OSError, ValueError, EOFError, UnicodeError, tarfile.TarError, zipfile.BadZipFile, zlib.error) as error:
        print("Package study failed: " + str(error), file=sys.stderr)
        return 2
    summary = {key: value for key, value in report["summary"].items()
               if key != "declared_filename_labels"}
    summary["labeled_assets"] = len(report["summary"]["declared_filename_labels"])
    print(json.dumps({"schema": report["schema"], "output": str(args.out), **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
