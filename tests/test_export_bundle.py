"""Real export containers and dependency boundaries, without providers or DCC tools."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts"


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


exports = module("export_bundle")
funavatar = module("funavatar")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def glb(document, binary=None, extra_chunks=()):
    encoded = json.dumps(document).encode()
    encoded += b" " * (-len(encoded) % 4)
    chunks = [struct.pack("<II", len(encoded), 0x4E4F534A) + encoded]
    if binary is not None:
        binary += b"\0" * (-len(binary) % 4)
        chunks.append(struct.pack("<II", len(binary), 0x004E4942) + binary)
    chunks.extend(struct.pack("<II", len(data), kind) + data for kind, data in extra_chunks)
    body = b"".join(chunks)
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


class ExportBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "export"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return path

    def gltf(self, **extra):
        return self.write("avatar.gltf", json.dumps({"asset": {"version": "2.0"}, **extra}))

    def check(self, model, **options):
        return exports.inspect_export(model, root=self.root, **options)

    def test_external_gltf_hashes_all_dependencies_and_changes_with_sidecar(self):
        binary = self.write("geometry.bin", b"12345678")
        image = self.write("textures/base color.png", b"image payload")
        model = self.gltf(buffers=[{"uri": "geometry.bin", "byteLength": 4}],
                          images=[{"uri": "textures/base%20color.png"}], textures=[{"source": 0}])
        report = self.check(model)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["scope"], "file_dependencies_only")
        self.assertEqual(report["source"]["sha256"], sha(model.read_bytes()))
        self.assertEqual([item["path"] for item in report["files"]],
                         ["avatar.gltf", "geometry.bin", "textures/base color.png"])
        self.assertEqual(report, self.check(model))
        image.write_bytes(b"changed texture")
        changed = self.check(model)
        self.assertEqual(changed["status"], "complete")
        self.assertEqual(changed["source"], report["source"])
        self.assertNotEqual(changed["bundle_sha256"], report["bundle_sha256"])
        binary.write_bytes(b"12")
        self.assertEqual(self.check(model)["status"], "incomplete")

    def test_missing_gltf_buffer_and_texture_are_explicit_and_relocatable(self):
        model = self.gltf(buffers=[{"uri": "missing.bin", "byteLength": 4}],
                          images=[{"uri": "missing.png"}])
        report = self.check(model)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(len([issue for issue in report["issues"]
                              if issue["code"] == "unsafe_or_missing_dependency"]), 2)
        self.assertNotIn(str(self.root), json.dumps(report))
        other = self.root.parent / "relocated"
        shutil.copytree(self.root, other)
        self.assertEqual(report, exports.inspect_export(other / model.name, root=other))

    def test_complete_bundle_is_independent_of_absolute_location(self):
        self.write("mesh.bin", b"abcd")
        model = self.gltf(buffers=[{"uri": "mesh.bin", "byteLength": 4}])
        original = self.check(model)
        other = self.root.parent / "copied"
        shutil.copytree(self.root, other)
        self.assertEqual(original, exports.inspect_export(other / model.name, root=other))

    def test_data_uris_are_measured_and_invalid_data_is_not_complete(self):
        data = b"abcdefgh"
        model = self.gltf(buffers=[{"uri": "data:application/gltf-buffer;base64," + base64.b64encode(data).decode(), "byteLength": 4}],
                          images=[{"uri": "data:image/png;base64,aW1hZ2U="}])
        report = self.check(model)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["embedded"][0]["sha256"], sha(data))
        self.assertEqual(len(report["files"]), 1)
        with patch.object(exports, "MAX_EMBEDDED", 3):
            self.assertEqual(self.check(model)["status"], "incomplete")
        for uri in ("data:application/octet-stream;base64,***", "data:application/octet-stream,%GG", "data:no-comma", "data:image/png;base64,"):
            with self.subTest(uri=uri):
                self.assertEqual(self.check(self.gltf(buffers=[{"uri": uri, "byteLength": 4}]))["status"], "incomplete")

    def test_glb_bin_padding_views_and_external_images(self):
        self.write("face.png", b"face image")
        document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 5}],
                    "bufferViews": [{"buffer": 0, "byteOffset": 1, "byteLength": 4}],
                    "images": [{"bufferView": 0, "mimeType": "image/png"}, {"uri": "face.png"}]}
        model = self.write("avatar.glb", glb(document, b"12345"))
        report = self.check(model)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["embedded"][0]["bytes"], 8)
        self.assertEqual(report["embedded"][0]["sha256"], sha(b"12345\0\0\0"))
        document["bufferViews"][0]["byteLength"] = 10
        model.write_bytes(glb(document, b"12345"))
        self.assertEqual(self.check(model)["status"], "incomplete")
        document["bufferViews"][0]["byteLength"] = 4
        corrupt = bytearray(glb(document, b"12345"))
        corrupt[-1] = 1
        model.write_bytes(corrupt)
        self.assertIn("invalid_glb_padding", {issue["code"] for issue in self.check(model)["issues"]})

    def test_glb_header_chunk_order_unknown_and_truncation(self):
        document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}]}
        good = glb(document, b"1234")
        for bad in (good[:-1], b"no glb", good[:4] + struct.pack("<I", 1) + good[8:],
                    good + b"trailing", glb(document, b"1234", [(0x004E4942, b"abcd")]),
                    glb(document, None, [(0x41414141, b"abcd"), (0x004E4942, b"1234")])):
            with self.subTest(data=bad[:20]):
                self.assertEqual(self.check(self.write("bad.glb", bad))["status"], "incomplete")
        unknown = self.write("unknown.glb", glb(document, b"1234", [(0x41414141, b"abcd")]))
        self.assertEqual(self.check(unknown)["status"], "not_assessed")
        no_bin = self.write("nobin.glb", glb({"asset": {"version": "2.0"}}))
        self.assertEqual(self.check(no_bin)["status"], "complete")

    def test_local_boundary_rejects_remote_absolute_encoded_parent_and_symlinks(self):
        outside = self.root.parent / "outside.bin"
        outside.write_bytes(b"abcd")
        (self.root / "link.bin").symlink_to(outside)
        (self.root / "linked").symlink_to(self.root.parent, target_is_directory=True)
        references = ["https://example.test/file.bin", "file:///tmp/file.bin", "//example.test/file.bin",
                      str(outside), "../outside.bin", "%2e%2e/outside.bin", "linked/outside.bin",
                      "link.bin", "broken%xx.bin", "C:\\file.bin", "mesh.bin?token=secret", "mesh.bin#part"]
        for reference in references:
            with self.subTest(reference=reference):
                model = self.gltf(buffers=[{"uri": reference, "byteLength": 4}])
                report = self.check(model)
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(len(report["files"]), 1)
        model = self.write("source-link.gltf", '{}')
        model.unlink()
        model.symlink_to(outside)
        with self.assertRaises(exports.ExportError):
            self.check(model)

    def test_unknown_extensions_are_not_silently_complete(self):
        model = self.gltf(extensionsUsed=["VENDOR_remote_asset"], extensions={"VENDOR_remote_asset": {"uri": "private"}})
        self.assertEqual(self.check(model)["status"], "not_assessed")
        model = self.gltf(extensionsUsed=["KHR_materials_unlit"], materials=[{"extensions": {"KHR_materials_unlit": {}}}])
        self.assertEqual(self.check(model)["status"], "complete")

    def test_malformed_json_shapes_do_not_crash_or_pass(self):
        for document in ([], {"asset": []}, {"asset": "2.0"}, {"asset": {"version": "1.0"}},
                         {"asset": {"version": "2.0"}, "buffers": {}},
                         {"asset": {"version": "2.0"}, "buffers": [None]},
                         {"asset": {"version": "2.0"}, "textures": [{"extensions": []}]},
                         {"asset": {"version": "2.0"}, "extensionsUsed": [None]}):
            with self.subTest(document=document):
                model = self.write("malformed.gltf", json.dumps(document))
                self.assertEqual(self.check(model)["status"], "incomplete")
        for data in ('{"asset":{"version":"2.0"},"asset":{}}', '{"asset":{"version":"2.0"},"extras":NaN}', '{bad'):
            self.assertEqual(self.check(self.write("bad.gltf", data))["status"], "incomplete")

    def test_obj_materials_textures_options_and_nested_relative_resolution(self):
        model = self.write("avatar.obj", 'mtllib mats/body.mtl\nusemtl coat\nv 0 0 0\n')
        self.write("mats/body.mtl", 'newmtl coat\nmap_Kd -s 1 1 1 "textures/base color.png"\nbump -bm 0.5 textures/norm.png\n')
        image = self.write("mats/textures/base color.png", b"base")
        self.write("mats/textures/norm.png", b"normal")
        report = self.check(model)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["files"]), 4)
        image.unlink()
        self.assertEqual(self.check(model)["status"], "incomplete")
        self.write("mats/body.mtl", 'newmtl coat\nmap_Kd -unknown option textures/norm.png\n')
        self.assertEqual(self.check(model)["status"], "not_assessed")

    def test_obj_missing_material_library_use_and_parent_texture(self):
        model = self.write("avatar.obj", 'mtllib missing.mtl\nusemtl coat\n')
        report = self.check(model)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("missing_material", {issue["code"] for issue in report["issues"]})
        self.write("missing.mtl", 'newmtl coat\nmap_Kd ../outside.png\n')
        self.assertEqual(self.check(model)["status"], "incomplete")
        self.write("missing.mtl", 'newmtl coat\nmap_Kd https://example.test/private.png\n')
        self.assertEqual(self.check(model)["status"], "incomplete")
        model.write_text('call ignored.obj\n')
        self.assertEqual(self.check(model)["status"], "not_assessed")

    def declaration(self, model):
        image = self.write("texture.png", b"texture")
        evidence = self.write("native-export.json", json.dumps({"source_sha256": sha(model.read_bytes()), "exporter": "test fixture"}))
        value = {"schema_version": 1, "kind": "funavatar_export_dependency_declaration",
                 "source_sha256": sha(model.read_bytes()), "exhaustive": True, "basis": "Native exporter dependency report",
                 "dependencies": [{"path": image.name, "sha256": sha(image.read_bytes())}],
                 "native_evidence": {"path": evidence.name, "sha256": sha(evidence.read_bytes()), "source_sha256": sha(model.read_bytes())}}
        return self.write("dependencies.json", json.dumps(value)), value

    def test_opaque_formats_need_hash_bound_native_declaration_and_detect_changes(self):
        model = self.write("avatar.fbx", b"opaque model")
        self.assertEqual(self.check(model)["status"], "not_assessed")
        declaration, value = self.declaration(model)
        report = self.check(model, declaration=declaration)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["basis"], "declared_dependencies")
        self.assertEqual(report["declaration"]["native_evidence"]["source_sha256"], report["source"]["sha256"])
        self.write("texture.png", b"different")
        self.assertEqual(self.check(model, declaration=declaration)["status"], "incomplete")

        model.write_bytes(b"changed model")
        self.assertEqual(self.check(model, declaration=declaration)["status"], "incomplete")
        model.write_bytes(b"opaque model")
        self.write("texture.png", b"texture")
        value["native_evidence"]["sha256"] = "0" * 64
        declaration.write_text(json.dumps(value))
        self.assertIn("native_evidence_hash_mismatch", {issue["code"] for issue in self.check(model, declaration=declaration)["issues"]})
        value["source_sha256"] = sha(model.read_bytes())
        del value["native_evidence"]
        declaration.write_text(json.dumps(value))
        self.assertEqual(self.check(model, declaration=declaration)["status"], "incomplete")

    def test_declaration_schema_requires_integer_version(self):
        model = self.write("avatar.fbx", b"opaque model")
        declaration, value = self.declaration(model)
        for invalid in (True, 1.0, "1"):
            with self.subTest(schema_version=invalid):
                value["schema_version"] = invalid
                declaration.write_text(json.dumps(value))
                self.assertEqual(self.check(model, declaration=declaration)["status"], "incomplete")

    def test_hash_changes_during_inspection_invalidate_report(self):
        model = self.gltf()
        original = exports._file
        calls = 0
        def change_on_recheck(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_text('{"asset":{"version":"2.0"},"changed":true}')
            return original(path)
        with patch.object(exports, "_file", side_effect=change_on_recheck):
            report = self.check(model)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("revision_changed", {issue["code"] for issue in report["issues"]})

    def test_json_and_line_limits_are_bounded(self):
        model = self.write("large.gltf", '{"asset":{"version":"2.0"}}')
        with patch.object(exports, "MAX_JSON", 8):
            self.assertEqual(self.check(model)["status"], "incomplete")
        model = self.write("long.obj", 'v ' + '1' * 100 + '\n')
        with patch.object(exports, "MAX_LINE", 20):
            self.assertEqual(self.check(model)["status"], "incomplete")

    def test_cli_exit_status_and_exclusive_output_preserve_originals(self):
        model = self.gltf()
        target = self.root / "manifest.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = funavatar.main(["export-check", str(model), "--root", str(self.root), "--out", str(target)])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        self.assertEqual(json.loads(stdout.getvalue()), json.loads(target.read_text()))
        before = target.read_bytes(), model.read_bytes()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(funavatar.main(["export-check", str(model), "--out", str(target)]), 2)
        self.assertEqual(before, (target.read_bytes(), model.read_bytes()))
        linked = self.root / "linked-output.json"
        linked.symlink_to(target)
        with self.assertRaises(exports.ExportError):
            exports.export_check(model, out=linked)
        self.assertEqual(before, (target.read_bytes(), model.read_bytes()))
        for source, status in ((self.gltf(images=[{"uri": "missing.png"}]), 1),
                               (self.write("opaque.fbx", b"opaque"), 3)):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(funavatar.main(["export-check", str(source)]), status)


if __name__ == "__main__":
    unittest.main()
