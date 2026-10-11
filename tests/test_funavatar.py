"""Dependency-free functional tests for the local FunAvatar helper."""

import binascii
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "funavatar" / "scripts" / "funavatar.py"
SPEC = importlib.util.spec_from_file_location("funavatar", SCRIPT)
funavatar = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(funavatar)


def png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF))


def png_image(width, height):
    """A genuinely decodable RGB PNG containing neutral gray pixels."""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = (b"\0" + b"\x80\x80\x80" * width) * height
    return (funavatar.PNG_SIGNATURE + png_chunk(b"IHDR", header)
            + png_chunk(b"IDAT", zlib.compress(pixels)) + png_chunk(b"IEND", b""))


def jpeg_image():
    """A complete 1x1 baseline grayscale JPEG using one zero-valued DCT block."""
    def segment(marker, payload):
        return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload
    counts = b"\x01" + b"\0" * 15
    return (b"\xff\xd8"
            + segment(0xDB, b"\0" + b"\x01" * 64)
            + segment(0xC0, b"\x08\0\x01\0\x01\x01\x01\x11\0")
            + segment(0xC4, b"\0" + counts + b"\0" + b"\x10" + counts + b"\0")
            + segment(0xDA, b"\x01\x01\0\0\x3f\0")
            + b"\x3f\xff\xd9")


def webp_chunk(kind, payload):
    return kind + struct.pack("<I", len(payload)) + payload + b"\0" * (len(payload) & 1)


def webp_container(*chunks):
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def webp_lossless_header(width, height):
    # Metadata fixture: tests explicitly do not claim to decode pixels.
    bits = (width - 1) | ((height - 1) << 14)
    return b"\x2f" + bits.to_bytes(4, "little")


class FunAvatarTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = funavatar.main(list(args))
        return code, output.getvalue(), errors.getvalue()

    def write_image(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_transformation_plan_preserves_intent_references_and_honest_delivery(self):
        reference = self.write_image("original face.png", png_image(48, 64))
        target = self.root / "new project"
        code, output, errors = self.run_cli(
            "plan", "--name", "../Sara & Sloth", "--idea",
            "Sara with hazel eyes and one red LEFT ear cuff.", "--transformation",
            "Human to friendly three-toed sloth, keeping her hazel eyes.",
            "--brand", "Oculandia, original logo if supplied", "--out", str(target),
            "--reference", str(reference), "--reference", str(reference))
        self.assertEqual((code, errors), (0, ""))
        result = json.loads(output)
        self.assertFalse(result["images_generated"])
        brief = json.loads((target / "brief.json").read_text())
        self.assertEqual(brief["generation"]["capability_status"], "not_checked_by_offline_helper")
        self.assertEqual(brief["generation"]["status"], "not_started")
        self.assertEqual(brief["idea"], "Sara with hazel eyes and one red LEFT ear cuff.")
        self.assertEqual(brief["slug"], "sara-sloth")
        self.assertEqual(len(brief["references"]), 1)
        self.assertEqual(brief["references"][0]["path"], str(reference.resolve()))
        self.assertEqual(len(brief["references"][0]["sha256"]), 64)
        expected_views = {"front", "back", "left", "right", "head", "hands", "accessories"}
        self.assertEqual({view["id"] for view in brief["views"]},
                         expected_views | {"transformed_" + view for view in expected_views})
        self.assertEqual({view["id"] for view in brief["views"] if view["state"] == "base"}, expected_views)
        self.assertEqual(sum(view["state"] == "transformed" for view in brief["views"]), 7)
        self.assertTrue(all(Path(view["filename"]).name == view["filename"] for view in brief["views"]))
        prompts = (target / "prompts.md").read_text()
        self.assertIn("Human to friendly three-toed sloth", prompts)
        self.assertIn("do not force five human fingers", prompts)
        self.assertIn("do not obtain this view by mirroring", prompts)
        self.assertIn("original asset is still needed", prompts)
        self.assertIn("No images have been generated", prompts)
        self.assertIn("Original base form, before the requested transformation", prompts)
        self.assertIn("Final transformed form", prompts)
        self.assertNotIn("three-stage sequence", prompts)
        self.assertIn("No pixel decoding", self.run_cli("check", str(reference))[1])

    def test_unbranded_plan_has_seven_views_and_does_not_invent_brand(self):
        target = self.root / "unbranded"
        code, output, errors = self.run_cli("plan", "--name", "🦥", "--idea",
                                          "A gentle blue sloth", "--out", str(target))
        self.assertEqual((code, errors), (0, ""))
        brief = json.loads((target / "brief.json").read_text())
        self.assertEqual(brief["slug"], "avatar")
        self.assertIsNone(brief["brand"])
        self.assertIsNone(brief["transformation"])
        self.assertEqual(len(brief["views"]), 7)
        self.assertEqual(brief["references"], [])
        prompts = (target / "prompts.md").read_text()
        self.assertIn("Add no logos or unrelated branding", prompts)
        self.assertNotIn("Oculandia", prompts)

    def test_existing_plan_is_not_overwritten_or_partially_created(self):
        target = self.root / "existing"
        target.mkdir()
        existing = target / "prompts.md"
        existing.write_text("Human-authored notes")
        code, output, errors = self.run_cli("plan", "--name", "Test", "--idea", "Sloth",
                                          "--out", str(target))
        self.assertEqual(code, 2)
        self.assertIn("Refusing to overwrite", errors)
        self.assertEqual(output, "")
        self.assertEqual(existing.read_text(), "Human-authored notes")
        self.assertFalse((target / "brief.json").exists())

    def test_missing_reference_fails_before_creating_output_directory(self):
        target = self.root / "no partial output"
        code, output, errors = self.run_cli("plan", "--name", "Test", "--idea", "Sloth",
                                          "--out", str(target), "--reference", str(self.root / "missing.png"))
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertFalse(target.exists())
        self.assertTrue(errors)

    def test_check_reports_all_files_and_resolution_failure_without_modifying_them(self):
        large = self.write_image("portrait.dat", png_image(100, 1200))
        small = self.write_image("small.png", png_image(16, 24))
        malformed = self.write_image("invalid.png", b"this is not an image")
        before = {path: path.read_bytes() for path in (large, small, malformed)}
        code, output, errors = self.run_cli("check", str(large), str(small), str(malformed))
        self.assertEqual((code, errors), (1, ""))
        report = json.loads(output)
        self.assertEqual([item["status"] for item in report["images"]], ["pass", "fail", "fail"])
        self.assertEqual(report["images"][0]["format"], "PNG")
        self.assertEqual(report["images"][0]["width"], 100)
        self.assertEqual(report["images"][0]["height"], 1200)
        self.assertIn("1024", report["images"][1]["error"])
        self.assertIn("Unsupported image format", report["images"][2]["error"])
        self.assertIn("Cannot verify anatomy", report["limitations"])
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_valid_jpeg_metadata_and_custom_minimum(self):
        image = self.write_image("one-pixel.jpeg", jpeg_image())
        code, output, errors = self.run_cli("check", str(image), "--min-long-edge", "1")
        self.assertEqual((code, errors), (0, ""))
        metadata = json.loads(output)["images"][0]
        self.assertEqual((metadata["format"], metadata["width"], metadata["height"]), ("JPEG", 1, 1))

    def test_webp_lossless_lossy_and_extended_headers(self):
        lossless = webp_chunk(b"VP8L", webp_lossless_header(1920, 1080))
        lossy = webp_chunk(b"VP8 ", b"\x10\0\0\x9d\x01\x2a" + struct.pack("<HH", 320, 240))
        extended = webp_chunk(b"VP8X", b"\0\0\0\0" + (1919).to_bytes(3, "little") + (1079).to_bytes(3, "little"))
        for index, (data, expected) in enumerate([
                (webp_container(lossless), (1920, 1080)),
                (webp_container(lossy), (320, 240)),
                (webp_container(extended, lossless), (1920, 1080))]):
            with self.subTest(index=index):
                image = self.write_image(f"fixture-{index}.webp", data)
                metadata = funavatar.inspect_image(image)
                self.assertEqual((metadata["width"], metadata["height"]), expected)
                self.assertEqual(metadata["format"], "WebP")

    def test_webp_animation_reports_canvas_dimensions(self):
        extended = webp_chunk(b"VP8X", b"\x02\0\0\0" + (639).to_bytes(3, "little") + (479).to_bytes(3, "little"))
        anim = webp_chunk(b"ANIM", b"\0" * 6)
        frame_header = b"\0" * 6 + (63).to_bytes(3, "little") + (47).to_bytes(3, "little") + b"\x64\0\0\0"
        frame = webp_chunk(b"ANMF", frame_header + webp_chunk(b"VP8L", webp_lossless_header(64, 48)))
        image = self.write_image("animated.webp", webp_container(extended, anim, frame))
        metadata = funavatar.inspect_image(image)
        self.assertEqual((metadata["width"], metadata["height"]), (640, 480))

    def test_malformed_containers_fail_with_explanation(self):
        valid_png = png_image(8, 8)
        invalid_crc = bytearray(valid_png)
        invalid_crc[29] ^= 1
        bad_png_dimensions = (funavatar.PNG_SIGNATURE
                              + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 0, 8, 8, 2, 0, 0, 0)))
        valid_webp = webp_container(webp_chunk(b"VP8L", webp_lossless_header(20, 40)))
        wrong_size = valid_webp[:4] + struct.pack("<I", 999) + valid_webp[8:]
        canvas = webp_chunk(b"VP8X", b"\0" * 4 + (19).to_bytes(3, "little") + (19).to_bytes(3, "little"))
        mismatched = webp_container(canvas, webp_chunk(b"VP8L", webp_lossless_header(20, 40)))
        fixtures = [
            ("truncated PNG", valid_png[:-5]),
            ("bad PNG checksum", bytes(invalid_crc)),
            ("zero PNG width", bad_png_dimensions),
            ("missing JPEG ending", jpeg_image()[:-2]),
            ("bad JPEG segment", b"\xff\xd8\xff\xe0\0\x01"),
            ("bad RIFF size", wrong_size),
            ("mismatched WebP canvas", mismatched),
            ("empty WebP", webp_container()),
        ]
        for index, (label, data) in enumerate(fixtures):
            with self.subTest(label=label):
                image = self.write_image(f"bad-{index}", data)
                code, output, errors = self.run_cli("check", str(image), "--min-long-edge", "1")
                self.assertEqual((code, errors), (1, ""))
                report = json.loads(output)
                self.assertEqual(report["status"], "fail")
                self.assertTrue(report["images"][0]["error"])

    def test_cli_rejects_empty_idea_and_nonpositive_resolution(self):
        for arguments in [
                ["plan", "--name", "Test", "--idea", " ", "--out", str(self.root)],
                ["check", "anything.png", "--min-long-edge", "0"]]:
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    funavatar.main(arguments)
                self.assertEqual(failure.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
