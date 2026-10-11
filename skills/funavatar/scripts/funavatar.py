#!/usr/bin/env python3
"""Prepare local avatar image briefs and inspect image containers. Python 3.10+."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
from typing import BinaryIO


DEFAULT_MIN_LONG_EDGE = 1024
MAX_TEXT_LENGTH = 20000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


class ImageError(ValueError):
    """An unsupported or structurally invalid image container."""


def read_exact(stream: BinaryIO, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise ImageError("Truncated image container")
    return data


def png_dimensions(stream: BinaryIO, size: int) -> tuple[int, int]:
    if read_exact(stream, 8) != PNG_SIGNATURE:
        raise ImageError("Invalid PNG signature")
    dimensions = None
    saw_data = False
    while stream.tell() < size:
        length, kind = struct.unpack(">I4s", read_exact(stream, 8))
        if length > size - stream.tell() - 4:
            raise ImageError("PNG chunk exceeds file size")
        if dimensions is None and (kind != b"IHDR" or length != 13):
            raise ImageError("PNG must begin with a 13-byte IHDR")
        if dimensions is not None and kind == b"IHDR":
            raise ImageError("Duplicate PNG IHDR")
        checksum = binascii.crc32(kind)
        remaining = length
        header = b""
        while remaining:
            block = read_exact(stream, min(remaining, 65536))
            checksum = binascii.crc32(block, checksum)
            if kind == b"IHDR":
                header += block
            remaining -= len(block)
        if checksum & 0xFFFFFFFF != struct.unpack(">I", read_exact(stream, 4))[0]:
            raise ImageError("PNG chunk checksum mismatch")
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", header)
            valid_depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8},
                            4: {8, 16}, 6: {8, 16}}
            if (not width or not height or width > 0x7FFFFFFF or height > 0x7FFFFFFF
                    or depth not in valid_depths.get(color, set())
                    or compression or filtering or interlace not in {0, 1}):
                raise ImageError("Invalid PNG image header")
            dimensions = (width, height)
        elif kind == b"IDAT":
            saw_data = saw_data or length > 0
        elif kind == b"IEND":
            if length or not saw_data or stream.tell() != size:
                raise ImageError("Invalid PNG ending or missing image data")
            return dimensions
    raise ImageError("PNG has no IEND chunk")


def jpeg_dimensions(stream: BinaryIO, size: int) -> tuple[int, int]:
    if read_exact(stream, 2) != b"\xff\xd8":
        raise ImageError("Invalid JPEG signature")
    dimensions = None
    while stream.tell() < size:
        if read_exact(stream, 1) != b"\xff":
            raise ImageError("Invalid JPEG marker")
        marker = read_exact(stream, 1)[0]
        while marker == 0xFF:
            marker = read_exact(stream, 1)[0]
        if marker in {0x00, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            raise ImageError("Unexpected JPEG marker before scan")
        if marker == 0x01:
            continue
        length = struct.unpack(">H", read_exact(stream, 2))[0]
        if length < 2 or length - 2 > size - stream.tell():
            raise ImageError("Invalid or truncated JPEG segment")
        payload = read_exact(stream, length - 2)
        if marker in JPEG_SOF_MARKERS:
            if len(payload) < 6:
                raise ImageError("Truncated JPEG frame header")
            precision, height, width, components = struct.unpack(">BHHB", payload[:6])
            if (not width or not height or not components or precision not in {8, 12, 16}
                    or len(payload) != 6 + 3 * components):
                raise ImageError("Invalid JPEG frame header")
            if dimensions is not None and dimensions != (width, height):
                raise ImageError("Conflicting JPEG frame dimensions")
            dimensions = (width, height)
        elif marker == 0xDA:
            if dimensions is None or len(payload) < 6:
                raise ImageError("JPEG scan has no valid frame header")
            scan_components = payload[0]
            if not scan_components or len(payload) != 4 + 2 * scan_components:
                raise ImageError("Invalid JPEG scan header")
            if stream.tell() >= size - 2:
                raise ImageError("JPEG contains no encoded image data")
            stream.seek(-2, os.SEEK_END)
            if read_exact(stream, 2) != b"\xff\xd9":
                raise ImageError("JPEG has no final end-of-image marker")
            return dimensions
    raise ImageError("JPEG has no image scan")


def webp_bitstream_dimensions(kind: bytes, payload: bytes) -> tuple[int, int]:
    if kind == b"VP8 ":
        if len(payload) < 10 or payload[0] & 1 or payload[3:6] != b"\x9d\x01\x2a":
            raise ImageError("Invalid WebP VP8 keyframe header")
        width, height = struct.unpack("<HH", payload[6:10])
        width, height = width & 0x3FFF, height & 0x3FFF
        if not width or not height:
            raise ImageError("Invalid WebP dimensions")
        return width, height
    if kind == b"VP8L":
        if len(payload) < 5 or payload[0] != 0x2F:
            raise ImageError("Invalid WebP lossless header")
        bits = int.from_bytes(payload[1:5], "little")
        if bits >> 29:
            raise ImageError("Unsupported WebP lossless version")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ImageError("Unsupported WebP image payload")


def webp_dimensions(stream: BinaryIO, size: int) -> tuple[int, int]:
    signature, declared_size, form = struct.unpack("<4sI4s", read_exact(stream, 12))
    if signature != b"RIFF" or form != b"WEBP" or declared_size + 8 != size:
        raise ImageError("Invalid WebP RIFF size or signature")
    canvas = None
    encoded = None
    animation = False
    saw_animation_header = False
    saw_animation_frame = False
    while stream.tell() < size:
        kind, length = struct.unpack("<4sI", read_exact(stream, 8))
        if length + (length & 1) > size - stream.tell():
            raise ImageError("WebP chunk exceeds file size")
        start = stream.tell()
        prefix = read_exact(stream, min(length, 32))
        if kind == b"VP8X":
            if canvas is not None or start != 20 or length != 10:
                raise ImageError("Invalid WebP extended header")
            if prefix[0] & ~0x3E or prefix[1:4] != b"\0\0\0":
                raise ImageError("Invalid WebP extended flags")
            canvas = (int.from_bytes(prefix[4:7], "little") + 1,
                      int.from_bytes(prefix[7:10], "little") + 1)
            animation = bool(prefix[0] & 2)
        elif kind in {b"VP8 ", b"VP8L"}:
            if encoded is not None or animation:
                raise ImageError("Unexpected duplicate or animated WebP payload")
            encoded = webp_bitstream_dimensions(kind, prefix)
        elif kind == b"ANIM":
            if not animation or length != 6 or saw_animation_header:
                raise ImageError("Invalid WebP animation header")
            saw_animation_header = True
        elif kind == b"ANMF":
            if not animation or not saw_animation_header or length < 24:
                raise ImageError("Invalid WebP animation frame")
            frame_x = int.from_bytes(prefix[0:3], "little") * 2
            frame_y = int.from_bytes(prefix[3:6], "little") * 2
            frame_w = int.from_bytes(prefix[6:9], "little") + 1
            frame_h = int.from_bytes(prefix[9:12], "little") + 1
            if (prefix[15] & ~3 or frame_x + frame_w > canvas[0]
                    or frame_y + frame_h > canvas[1]):
                raise ImageError("WebP frame exceeds animation canvas")
            frame_end = start + length
            stream.seek(start + 16)
            frame_image = False
            while stream.tell() < frame_end:
                frame_kind, frame_length = struct.unpack("<4sI", read_exact(stream, 8))
                if frame_length + (frame_length & 1) > frame_end - stream.tell():
                    raise ImageError("WebP animation subchunk exceeds frame")
                frame_start = stream.tell()
                frame_prefix = read_exact(stream, min(frame_length, 10))
                if frame_kind in {b"VP8 ", b"VP8L"}:
                    if frame_image or webp_bitstream_dimensions(frame_kind, frame_prefix) != (frame_w, frame_h):
                        raise ImageError("Conflicting WebP animation frame dimensions")
                    frame_image = True
                stream.seek(frame_start + frame_length + (frame_length & 1))
            if not frame_image:
                raise ImageError("WebP animation frame has no image payload")
            saw_animation_frame = True
        stream.seek(start + length)
        if length & 1 and read_exact(stream, 1) != b"\0":
            raise ImageError("Invalid WebP chunk padding")
    if animation:
        if not saw_animation_frame:
            raise ImageError("WebP animation contains no frames")
        return canvas
    if encoded is None:
        raise ImageError("WebP contains no image payload")
    if canvas is not None and canvas != encoded:
        raise ImageError("WebP canvas and image dimensions disagree")
    return encoded


def inspect_image(path: Path) -> dict:
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ImageError("Reference must be a regular file")
    before = path.stat()
    with path.open("rb") as stream:
        signature = stream.read(12)
        stream.seek(0)
        if signature.startswith(PNG_SIGNATURE):
            image_format = "PNG"
            width, height = png_dimensions(stream, before.st_size)
        elif signature.startswith(b"\xff\xd8"):
            image_format = "JPEG"
            width, height = jpeg_dimensions(stream, before.st_size)
        elif signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
            image_format = "WebP"
            width, height = webp_dimensions(stream, before.st_size)
        else:
            raise ImageError("Unsupported image format; use PNG, JPEG, or WebP")
        stream.seek(0)
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise ImageError("Image changed while it was being inspected; retry")
    return {"path": str(path), "format": image_format, "width": width, "height": height,
            "long_edge": max(width, height), "bytes": before.st_size, "sha256": digest.hexdigest()}


def nonempty_text(value: str) -> str:
    value = value.strip()
    if not value or len(value) > MAX_TEXT_LENGTH or "\0" in value:
        raise argparse.ArgumentTypeError(f"Text must contain 1 to {MAX_TEXT_LENGTH} characters and no NUL")
    return value


def positive_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("Use a positive integer")
    return number


def safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:64].rstrip("-")
    return slug or "avatar"


def make_brief(args: argparse.Namespace) -> dict:
    references = []
    for reference in args.reference:
        metadata = inspect_image(Path(reference))
        if not any(item["path"] == metadata["path"] for item in references):
            references.append(metadata)
    slug = safe_slug(args.name)
    views = [
        ("front", "Full-body front", "Straight-on front orthographic view. Neutral A-pose, feet flat, arms separated enough to reveal torso and hands."),
        ("back", "Full-body back", "Straight-on rear orthographic view. Match the approved front image in scale, proportions, pose, materials, outfit and identity."),
        ("left", "Full-body left", "True left orthographic profile: show the character's anatomical LEFT side. Match the approved front image; preserve asymmetric features on their correct anatomical side."),
        ("right", "Full-body right", "True right orthographic profile: show the character's anatomical RIGHT side. Match the approved front image; do not obtain this view by mirroring the left view."),
        ("head", "Head detail", "Close-up reference of the same head: front and three-quarter views with neutral expression, clear eyes, muzzle/nose, ears, hair/fur and neck connection. Preserve face identity; keep all features fully visible."),
        ("hands", "Hands / paws detail", "Anatomical detail reference of the character's actual hands, paws or claws, showing palm and back. Keep the digit count and joints consistent with the approved species and design; do not force five human fingers onto nonhuman anatomy."),
        ("accessories", "Outfit and accessories detail", "Reference details of only the outfit and accessories established in the approved front image or source brief. Show attachment points, seams, closures and material boundaries clearly. If the design has no accessories, show garment or body-surface details; do not invent accessories."),
    ]
    planned_views = [{"id": view, "state": "base", "title": f"Base form: {title}",
                      "filename": f"{slug}-{view}.png", "direction": direction}
                     for view, title, direction in views]
    if args.transformation:
        planned_views += [{"id": f"transformed_{view}", "state": "transformed",
                           "title": f"Transformed form: {title}",
                           "filename": f"{slug}-transformed-{view}.png", "direction": direction}
                          for view, title, direction in views]
    return {
        "schema_version": 1,
        "name": args.name,
        "slug": slug,
        "idea": args.idea,
        "transformation": args.transformation,
        "brand": args.brand,
        "references": references,
        "output": {"suggested_min_long_edge": DEFAULT_MIN_LONG_EDGE,
                   "suggested_formats": ["PNG", "WebP"], "transparent_background": False},
        "generation": {"executor": "available host image generator",
                       "capability_status": "not_checked_by_offline_helper", "status": "not_started",
                       "images_generated": False,
                       "order": ("Approve the base front first. If transformation is requested, approve the transformed front using the base front and original references for identity anchors. Generate each state's remaining views using that state's approved front.")},
        "views": planned_views,
        "review_required": ["reference identity and user intent", "front/back/side consistency",
                            "species-appropriate anatomy and digit counts", "uncropped silhouettes",
                            "accessory and material consistency", "exact authorized branding"],
        "limitations": ["A 2D reference image is not a rigged or validated 3D avatar.",
                        "Image metadata checks cannot verify visual anatomy, originality, or VRChat compatibility.",
                        "Resolution is requested from the generator; this helper does not resize or upscale images."],
    }


def quote_text(value: str) -> str:
    return "\n".join("> " + line for line in value.splitlines())


def make_prompts(brief: dict) -> str:
    lines = [f"# FunAvatar reference plan: {brief['name'].replace(chr(10), ' ')}", "",
             "This file is a generation plan. No images have been generated. The offline helper has not checked whether this host has an image generator; verify that capability before executing prompts.", "",
             "## Source idea", "", quote_text(brief["idea"]), "",
             "## Generation workflow", "",
             "1. Inspect the supplied references and settle identity anchors, base form, any transformed form, anatomy, palette, outfit and asymmetry with the user when they are ambiguous.",
             "2. Generate and visually review the base front first. If transformation is requested, generate and approve its final front using the base front and original references to retain the requested identity anchors. Then generate each state's remaining views using that state's approved front plus the original references. Give the image generator the actual files; the local paths below do not attach images by themselves.",
             "3. Generate each view as a separate image. Use the listed filenames when saving outputs. Request the highest practical native resolution available, with 1024 pixels on the long edge as the minimum; report the actual returned dimensions and any generator limitation.",
             "4. Visually review each output for identity, anatomy, silhouette, cropping, materials and side consistency. Regenerate a failed view with a specific correction; do not upscale it to disguise missing detail.",
             "5. Run `check` on the saved outputs. Its header/container and resolution checks are separate from the visual review.", "",
             "Left and right always mean the character's anatomical left and right. Reference-sheet labels may be added separately; generated text is not trusted for correctness.", "",
             "## Local reference files", ""]
    if brief["references"]:
        for reference in brief["references"]:
            lines += [f"- {json.dumps(reference['path'], ensure_ascii=False)} — {reference['format']}, {reference['width']} × {reference['height']}; SHA-256 {reference['sha256']}"]
    else:
        lines += ["No reference files supplied. The first approved front image establishes the visual identity."]
    if brief["transformation"]:
        lines += ["", "## Requested transformation", "", quote_text(brief["transformation"])]
    if brief["brand"]:
        lines += ["", "## Requested branding", "", quote_text(brief["brand"]), "",
                  "Use an exact original logo only when its authorized source asset has been supplied. If it is missing, reserve a clean logo area and disclose that the original asset is still needed; do not approximate an original logo with generated text."]
    else:
        lines += ["", "## Branding", "", "No brand requested. Add no logos or unrelated branding."]
    common = (
        "Create a high-quality 2D character concept reference with crisp, readable forms and deliberate materials. "
        "Follow the source idea, supplied references and the form-specific instruction below. Within each form, preserve "
        "the approved identity, species, proportions, palette, outfit, accessories and anatomical asymmetry across views. "
        "Across a requested transformation preserve its identity anchors while allowing the requested species and anatomy to change. "
        "Use soft even studio light and a plain "
        "light-neutral background, no dramatic lens distortion, no cast shadow hiding anatomy. For full-body views use "
        "orthographic projection, identical framing and scale, the whole silhouette visible with comfortable margin "
        "around head, feet, hands, ears, tail and accessories. Keep the same approved species-appropriate digit count; "
        "no accidental extra limbs or fused digits. Do not add decorative props, a watermark, or unrelated logos. "
        "This is a 2D concept/reference, with no claim of rigging, topology, game readiness or VRChat readiness."
    )
    for view in brief["views"]:
        lines += ["", f"## {view['title']}", "", f"Save as: `{view['filename']}`", "", common,
                  "", view["direction"]]
        if view["state"] == "transformed":
            lines += ["", "FORM: Final transformed form, following the requested transformation above. Use the approved transformed front as the visual reference for this form. Keep the agreed identity anchors from the base form, but use the transformed species/anatomy consistently. Show only the final form in this image; no intermediate transition stages."]
        elif brief["transformation"]:
            lines += ["", "FORM: Original base form, before the requested transformation. Follow its original species/anatomy and references. Use the approved base front for this form. Do not apply the transformed anatomy to this image."]
        else:
            lines += ["", "FORM: The character as described in the source idea. Use the approved front reference for all details and remaining views."]
        if brief["brand"]:
            lines += ["", "Apply only the requested branding, subject to the original-asset rule above."]
    lines += ["", "## Delivery limits", "",
              "Deliver the actual saved images, their measured dimensions and the visual-review outcome. A concept sheet still needs 3D modeling, topology, UVs, materials, rigging and platform-specific validation before it can become a usable VRChat avatar.", ""]
    return "\n".join(lines)


def create_plan(args: argparse.Namespace) -> dict:
    brief = make_brief(args)
    target = Path(args.out).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    payloads = [(target / "brief.json", json.dumps(brief, ensure_ascii=False, indent=2) + "\n"),
                (target / "prompts.md", make_prompts(brief))]
    for path, _ in payloads:
        if path.exists() or path.is_symlink():
            raise ValueError(f"Refusing to overwrite existing plan file: {path}. Choose another --out directory.")
    created = []
    try:
        for path, content in payloads:
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {"status": "plan_created", "out": str(target),
            "files": [str(path) for path, _ in payloads], "images_generated": False,
            "next_step": "Inspect references, generate and approve front, then generate the remaining views."}


def check_images(args: argparse.Namespace) -> tuple[dict, int]:
    reports = []
    for filename in args.images:
        try:
            metadata = inspect_image(Path(filename))
            passed = metadata["long_edge"] >= args.min_long_edge
            metadata["status"] = "pass" if passed else "fail"
            if not passed:
                metadata["error"] = f"Long edge is below the requested minimum of {args.min_long_edge} pixels"
            reports.append(metadata)
        except (OSError, ValueError) as exc:
            reports.append({"path": filename, "status": "fail", "error": str(exc)})
    failed = any(report["status"] == "fail" for report in reports)
    return {"status": "fail" if failed else "pass", "minimum_long_edge": args.min_long_edge,
            "images": reports,
            "checks": "PNG/JPEG/WebP header and container structure, dimensions, file size and SHA-256",
            "limitations": "No pixel decoding or visual review. Cannot verify anatomy, character consistency, originality, 3D validity, rigging or VRChat compatibility."}, int(failed)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Create brief.json and prompts.md; never overwrite existing plans")
    plan.add_argument("--idea", required=True, type=nonempty_text)
    plan.add_argument("--name", required=True, type=nonempty_text)
    plan.add_argument("--out", required=True, help="Local output directory")
    plan.add_argument("--transformation", type=nonempty_text)
    plan.add_argument("--brand", type=nonempty_text)
    plan.add_argument("--reference", action="append", default=[], metavar="PATH",
                      help="Existing PNG/JPEG/WebP reference; repeat for multiple images")
    check = commands.add_parser("check", help="Inspect local image files; visual anatomy needs manual review")
    check.add_argument("images", nargs="+", metavar="IMAGE")
    check.add_argument("--min-long-edge", type=positive_integer, default=DEFAULT_MIN_LONG_EDGE)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "plan":
            report, code = create_plan(args), 0
        else:
            report, code = check_images(args)
    except (OSError, ValueError) as exc:
        print(f"funavatar: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
