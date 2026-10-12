"""Synthetic archive tests; no third-party avatar data or native applications."""
import dataclasses
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

SCRIPT = Path(__file__).parents[1] / "skills/funavatar/scripts/avatar_inspect.py"
SPEC = importlib.util.spec_from_file_location("avatar_inspect", SCRIPT)
study = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = study
SPEC.loader.exec_module(study)

A, B, C = "a" * 32, "b" * 32, "c" * 32
YAML = b"%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n"


def tar_bytes(members, *, format=tarfile.USTAR_FORMAT):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=format) as archive:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            info.type, info.size = kind, len(data)
            if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                info.linkname = "elsewhere"
            archive.addfile(info, io.BytesIO(data) if info.isfile() else None)
    return output.getvalue()


def asset(guid=A, path="Assets/Test.prefab", body=None, *, meta_guid=None):
    if body is None:
        body = YAML + b"--- !u!1 &11\nGameObject:\n  m_Name: Example\n"
    return [(guid + "/asset", body, tarfile.REGTYPE),
            (guid + "/asset.meta", ("fileFormatVersion: 2\nguid: " + (meta_guid or guid) + "\n").encode(), tarfile.REGTYPE),
            (guid + "/pathname", path.encode(), tarfile.REGTYPE)]


def package(*groups, format=tarfile.USTAR_FORMAT):
    return gzip.compress(tar_bytes([row for group in groups for row in group], format=format))


def zip_bytes(rows):
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in rows:
                archive.writestr(name, data)
    return output.getvalue()


class PackageStudyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()

    def tearDown(self):
        self.folder.cleanup()

    def source(self, data=None, name="example.unitypackage"):
        path = self.root / name
        path.write_bytes(data if data is not None else package(asset()))
        return path

    def assert_invalid(self, data, *, name="bad.unitypackage", limits=None):
        source = self.source(data, name)
        with self.assertRaises((study.StudyError, OSError, ValueError, EOFError, tarfile.TarError, zipfile.BadZipFile)):
            study.inspect(source, limits or study.Limits())

    def test_complete_inventory_preserves_source_and_omits_source_bodies(self):
        data = zip_bytes([("PC.unitypackage", package(asset(), asset(B, "Assets/Editor/private.cs", b"PRIVATE_SOURCE_MARKER"))),
                          ("License.txt", b"PRIVATE_LICENSE_MARKER")])
        source = self.source(data, "avatar.zip")
        report = study.inspect(source)
        self.assertEqual(source.read_bytes(), data)
        self.assertEqual(report["schema"], "funavatar.package_study")
        self.assertEqual(report["summary"]["assets"], 2)
        self.assertEqual(report["packages"][0]["entries"][0]["yaml"]["documents"][0]["class_id"], 1)
        self.assertEqual(report["outer_inventory"][1]["bytes"], len(b"PRIVATE_LICENSE_MARKER"))
        serialized = json.dumps(report)
        self.assertNotIn("PRIVATE_SOURCE_MARKER", serialized)
        self.assertNotIn("PRIVATE_LICENSE_MARKER", serialized)
        self.assertNotIn("%YAML", serialized)

    def test_cross_package_closure_and_field_chain(self):
        pc = package(asset(B, "Assets/PC.controller", YAML + b"--- !u!91 &91\nAnimatorController:\n  m_Name: PC\n"))
        quest_body = YAML + ("--- !u!114 &114\nMonoBehaviour:\n  controls:\n  - name: Face\n    type: 1\n    parameter:\n      name: FaceMode\n    subMenu: {fileID: 91, guid: " + B + ", type: 2}\n  external: {fileID: 1, guid: " + C + ", type: 3}\n").encode()
        report = study.inspect(self.source(zip_bytes([("PC.unitypackage", pc), ("Quest.unitypackage", package(asset(body=quest_body)))]), "avatar.zip"))
        quest = report["packages"][1]
        self.assertEqual(quest["dependencies_on_other_packages"], ["PC.unitypackage"])
        self.assertEqual(quest["unresolved_external_guids"], [C])
        indexed = quest["entries"][0]["yaml"]
        names = {row["field_path"]: row["value"] for row in indexed["field_observations"]}
        self.assertEqual(names["MonoBehaviour.controls[0].parameter.name"], "FaceMode")
        reference = next(row for row in indexed["references"] if row["guid"] == B)
        self.assertEqual(reference["field_path"], "MonoBehaviour.controls[0].subMenu")
        self.assertEqual(reference["resolution"], "other_package")
        self.assertEqual(reference["file_id_status"], "present_in_yaml")
        self.assertEqual(reference["line"], 10)

    def test_controller_parameters_and_multiple_list_items(self):
        raw = YAML + b"--- !u!91 &91\nAnimatorController:\n  m_AnimatorParameters:\n  - m_Name: FaceMode\n    m_Type: 3\n    m_DefaultInt: 0\n  - m_Name: Prop\n    m_Type: 4\n  m_Name: Main\n"
        fields = study.yaml_index(raw, study.Budget(study.Limits()))["field_observations"]
        self.assertEqual([row["field_path"] for row in fields[:4]], [
            "AnimatorController.m_AnimatorParameters[0].m_Name", "AnimatorController.m_AnimatorParameters[0].m_Type",
            "AnimatorController.m_AnimatorParameters[0].m_DefaultInt", "AnimatorController.m_AnimatorParameters[1].m_Name"])
        self.assertEqual(fields[-1]["field_path"], "AnimatorController.m_Name")
        self.assertEqual(fields[0]["role"], "parameter")

    def test_wrapped_flat_pptr_same_and_cross_package_keep_start_provenance(self):
        pc = package(asset(B, "Assets/PC.controller", YAML + b"--- !u!91 &91\nAnimatorController:\n  m_Name: PC\n"))
        body = YAML + ("--- !u!114 &114\nMonoBehaviour:\n  layers:\n  - m_AnimatorController: {fileID: 91, guid: " + B + ",\n      type: 2}\n  own: {fileID: 114, guid: " + A + ",\n    type: 2}\n").encode()
        report = study.inspect(self.source(zip_bytes([("PC.unitypackage", pc),
            ("Quest.unitypackage", package(asset(body=body)))]), "wrapped.zip"))
        quest = report["packages"][1]
        refs = quest["entries"][0]["yaml"]["references"]
        remote, own = next(r for r in refs if r["guid"] == B), next(r for r in refs if r["guid"] == A)
        self.assertEqual(remote["resolution"], "other_package")
        self.assertEqual(own["resolution"], "same_package")
        self.assertEqual(remote["field_path"], "MonoBehaviour.layers[0].m_AnimatorController")
        self.assertEqual((remote["line"], remote["end_line"], remote["document_file_id"], remote["class_id"]), (6, 7, 114, 114))
        self.assertEqual(quest["dependencies_on_other_packages"], ["PC.unitypackage"])

    def test_wrapped_flat_pptr_truncation_headers_and_buffers_fail_explicitly(self):
        start = YAML + b"--- !u!114 &114\nMonoBehaviour:\n  ref: {fileID: 1,\n"
        for ending in (b"", b"--- !u!1 &1\nGameObject:\n", b" " * 1025 + b"type: 2}\n",
                       b"\n" * 8 + b"type: 2}\n", b"type: 2, nested: {fileID: 1}}\n"):
            with self.subTest(ending=ending[:40]), self.assertRaises(study.StudyError):
                study.yaml_index(start + ending, study.Budget(study.Limits()))

    def test_generator_optimization_reference_path_and_physics_are_declarations(self):
        raw = YAML + b"""--- !u!114 &114
MonoBehaviour:
  m_EditorClassIdentifier: Example.Generator
  menuName: Face
  isSave: 1
  isLocalOnly: 0
  referencePath: Body/Face
  LockMode: 1
  mangleNames: 1
  freezeBlendShape: 1
  removeUnusedObjects: 1
  optimizePhysBone: 1
  optimizeAnimator: 1
  mergeSkinnedMesh: 1
  pull: 0.4
  spring: 0.2
  stiffness: 0.5
  gravity: 0.1
  radius: 0.03
  height: 0.5
  shapeType: 2
"""
        report = study.inspect(self.source(package(asset(body=raw))))
        fields = report["packages"][0]["entries"][0]["yaml"]["field_observations"]
        indexed = {row["field_path"].split(".")[-1]: row for row in fields}
        self.assertEqual(indexed["m_EditorClassIdentifier"]["value"], "Example.Generator")
        self.assertEqual(indexed["referencePath"]["value"], "Body/Face")
        self.assertEqual(indexed["optimizePhysBone"]["value"], 1)
        self.assertEqual(indexed["gravity"]["value"], 0.1)
        self.assertTrue(all(row["role"] == "configuration" for row in fields))
        self.assertNotIn("runtime", report["summary"])

    def test_multiline_and_local_fileid_references(self):
        raw = YAML + ("--- !u!1 &11\nGameObject:\n  other:\n    fileID: 22\n    guid: " + B + "\n  local: {fileID: 11}\n  absent: {fileID: 33}\n  none: {fileID: 0}\n  builtin: {fileID: 10202, guid: 0000000000000000e000000000000000, type: 0}\n").encode()
        report = study.inspect(self.source(package(asset(body=raw), asset(B, "Assets/model.fbx", b"binary"))))
        refs = report["packages"][0]["entries"][0]["yaml"]["references"]
        multipart = next(row for row in refs if row["guid"] == B)
        self.assertEqual(multipart["field_path"], "GameObject.other")
        self.assertEqual(multipart["fileID_line"], 6)
        self.assertEqual(multipart["file_id_status"], "not_assessed_native_or_binary_subasset")
        self.assertEqual({row["resolution"] for row in refs}, {"same_package", "local_file_id", "unresolved_local_file_id", "null", "builtin"})

    def test_same_guid_identical_across_packages_has_provenance(self):
        payload = package(asset())
        report = study.inspect(self.source(zip_bytes([("PC.unitypackage", payload), ("Quest.unitypackage", payload)]), "same.zip"))
        self.assertEqual(report["closure"]["issues"], [])
        self.assertEqual(report["closure"]["shared_guids"][0]["packages"], ["PC.unitypackage", "Quest.unitypackage"])

    def test_cross_package_guid_conflict_is_reported_without_guessing_import_order(self):
        payload = package(asset())
        changed = package(asset(body=YAML + b"--- !u!1 &11\nGameObject:\n  m_Name: Changed\n"))
        report = study.inspect(self.source(zip_bytes([("PC.unitypackage", payload), ("Quest.unitypackage", changed)]), "conflict.zip"))
        self.assertEqual(report["closure"]["issues"][0]["code"], "cross_package_guid_conflict")

    def test_cross_package_importer_metadata_conflict_is_not_deduplicated(self):
        rows = asset(path="Assets/model.fbx", body=b"identical FBX bytes")
        changed = list(rows)
        name, body, kind = changed[1]
        changed[1] = (name, body + b"ModelImporter:\n  globalScale: 2\n", kind)
        report = study.inspect(self.source(zip_bytes([("PC.unitypackage", package(rows)),
            ("Quest.unitypackage", package(changed))]), "metadata.zip"))
        self.assertEqual(report["closure"]["shared_guids"], [])
        self.assertEqual(report["closure"]["issues"][0]["code"], "cross_package_guid_conflict")

    def test_document_and_reference_integer_widths_are_bounded(self):
        for body in (b"--- !u!2147483648 &1\nA:\n", b"--- !u!1 &9223372036854775808\nA:\n",
                     b"--- !u!1 &1\nA:\n  ref: {fileID: " + b"9" * 100_000 + b"}\n",
                     b"--- !u!1 &1\nA:\n  ref:\n    fileID: " + b"9" * 100_000 + b"\n"):
            with self.subTest(prefix=body[:50]), self.assertRaises(study.StudyError):
                study.yaml_index(YAML + body, study.Budget(study.Limits()))
        self.assertEqual(study.unity_integer("-9223372036854775808"), -(1 << 63))
        self.assertEqual(study.unity_integer("9223372036854775807"), (1 << 63) - 1)

    def test_binary_metrics_unknown_and_filename_labels_only_declared(self):
        report = study.inspect(self.source(package(asset(path="Assets/Quest_Optimized_Good.fbx", body=b"BINARY"))))
        entry = report["packages"][0]["entries"][0]
        self.assertEqual(entry["format"], "opaque_not_parsed")
        self.assertNotIn("triangle_count", entry)
        self.assertEqual(set(report["summary"]["declared_filename_labels"][0]["labels"]), {"Quest", "Optimized", "Good"})

    def test_unsafe_pathnames(self):
        for name in ("../x", "/x", "C:/x", "C:x", "x\\y", "x\ny", "x\x7fy", "x\x85y", "a/../../b", "."):
            with self.subTest(name=name), self.assertRaises(study.StudyError):
                study.safe_path(name)

    def test_unsafe_zip_member_is_rejected(self):
        self.assert_invalid(zip_bytes([("../avatar.unitypackage", package(asset()))]), name="bad.zip")

    def test_unsafe_tar_member_is_rejected(self):
        self.assert_invalid(package([("../evil", b"x", tarfile.REGTYPE)]))

    def test_unsafe_asset_pathname_is_rejected(self):
        self.assert_invalid(package(asset(path="../evil.prefab")))

    def test_zip_symlink_and_special_file_are_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            info = zipfile.ZipInfo("link.unitypackage")
            info.create_system, info.external_attr = 3, (mode | 0o777) << 16
            with self.subTest(mode=mode):
                self.assert_invalid(zip_bytes([(info, package(asset()))]), name="link.zip")

    def test_tar_symlink_hardlink_and_special_file_are_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE):
            with self.subTest(kind=kind):
                self.assert_invalid(package([(A + "/asset", b"", kind)]))

    def test_extended_tar_headers_are_rejected_before_payload_processing(self):
        self.assert_invalid(package([("x" * 110, b"x", tarfile.REGTYPE)], format=tarfile.PAX_FORMAT))

    def test_duplicate_zip_member_is_rejected(self):
        data = package(asset())
        self.assert_invalid(zip_bytes([("same.unitypackage", data), ("same.unitypackage", data)]), name="duplicate.zip")

    def test_duplicate_tar_member_and_guid_case_collision_are_rejected(self):
        for repeated in (A + "/asset", A.upper() + "/asset"):
            with self.subTest(name=repeated):
                self.assert_invalid(package(asset(), [(repeated, b"other", tarfile.REGTYPE)]))

    def test_duplicate_asset_paths_are_rejected(self):
        self.assert_invalid(package(asset(), asset(B, "Assets/Test.prefab")))

    def test_mismatched_or_duplicate_meta_guid_is_rejected(self):
        self.assert_invalid(package(asset(meta_guid=B)))
        rows = asset()
        rows[1] = (A + "/asset.meta", ("guid: " + A + "\nguid: " + A + "\n").encode(), tarfile.REGTYPE)
        self.assert_invalid(package(rows))

    def test_missing_pathname_is_rejected(self):
        self.assert_invalid(package(asset()[:2]))

    def test_duplicate_yaml_document_and_reference_field_are_rejected(self):
        for raw in (YAML + b"--- !u!1 &1\nA:\n--- !u!2 &1\nB:\n",
                    YAML + b"--- !u!1 &1\nA:\n  ref:\n    fileID: 1\n    fileID: 2\n"):
            with self.subTest(raw=raw):
                self.assert_invalid(package(asset(body=raw)))

    def test_truncated_gzip_tar_and_zip_are_rejected(self):
        data = package(asset())
        self.assert_invalid(data[:-4])
        truncated_tar = tar_bytes(asset())[:520]
        self.assert_invalid(gzip.compress(truncated_tar))
        zipped = zip_bytes([("a.unitypackage", data)])
        self.assert_invalid(zipped[:-10], name="truncated.zip")

    def test_tar_missing_end_records_is_rejected_even_with_valid_gzip_footer(self):
        raw = tar_bytes(asset())
        # Three small regular files occupy six blocks; omit the TAR terminator.
        self.assert_invalid(gzip.compress(raw[:6 * 512]))

    def test_corrupt_zip_crc_is_rejected(self):
        data = zip_bytes([("readme.txt", b"unique body"), ("avatar.unitypackage", package(asset()))])
        self.assert_invalid(data.replace(b"unique body", b"changedbody", 1), name="corrupt.zip")

    def test_source_member_metadata_and_text_limits(self):
        for overrides in ({"source_bytes": 1}, {"members": 1}, {"decompressed_bytes": 100},
                          {"metadata_bytes": 1}, {"metadata_total_bytes": 1}, {"text_total_bytes": 1}, {"records": 0}):
            with self.subTest(overrides=overrides):
                self.assert_invalid(package(asset()), limits=dataclasses.replace(study.Limits(), **overrides))

    def test_zip_directory_budget_is_checked_before_open(self):
        data = zip_bytes([("a.unitypackage", package(asset()))])
        self.assert_invalid(data, name="directory.zip", limits=dataclasses.replace(study.Limits(), directory_bytes=1))

    def test_source_change_during_inspection_is_rejected(self):
        source = self.source()
        original = study.package_index
        def changed(*args):
            result = original(*args)
            current = source.stat()
            os.utime(source, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000))
            return result
        with mock.patch.object(study, "package_index", changed), self.assertRaisesRegex(study.StudyError, "Source changed"):
            study.inspect(source)

    def test_symlink_source_is_rejected(self):
        source = self.source()
        link = self.root / "link.unitypackage"
        link.symlink_to(source)
        with self.assertRaises(study.StudyError):
            study.inspect(link)

    def test_output_new_only_and_symlink_parents(self):
        output = self.root / "report.json"
        study.write_report({"ok": True}, output)
        before = output.read_bytes()
        with self.assertRaises(FileExistsError):
            study.write_report({"changed": True}, output)
        self.assertEqual(output.read_bytes(), before)
        symlink = self.root / "link.json"
        symlink.symlink_to(output)
        with self.assertRaises(study.StudyError):
            study.write_report({}, symlink)
        folder = self.root / "linked-folder"
        folder.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(study.StudyError):
            study.write_report({}, folder / "new.json")

    def test_report_size_limit_prevents_output_creation(self):
        output = self.root / "large.json"
        with self.assertRaises(study.StudyError):
            study.write_report({"large": "x" * 100}, output, dataclasses.replace(study.Limits(), report_bytes=10))
        self.assertFalse(output.exists())

    def test_cli_outputs_compact_summary_and_preserves_collision(self):
        source = self.source(package(asset(path="Assets/Quest_Avatar.prefab")))
        output = self.root / "nested/report.json"
        result = subprocess.run([sys.executable, str(SCRIPT), str(source), "--out", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["schema"], "funavatar.package_study")
        self.assertEqual(json.loads(result.stdout)["labeled_assets"], 1)
        self.assertNotIn("declared_filename_labels", json.loads(result.stdout))
        self.assertLess(len(result.stdout), 1500)
        before = output.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), str(source), "--out", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_bytes(), before)

    def test_no_package_and_unsupported_input_rejected(self):
        self.assert_invalid(zip_bytes([("readme.txt", b"text")]), name="empty.zip")
        self.assert_invalid(b"other", name="source.bin")


if __name__ == "__main__":
    unittest.main()
