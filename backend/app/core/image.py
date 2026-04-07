"""Image conversion and resizing utilities for AI vision input."""
from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

# Claude Vision accepts these media types
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_DIMENSION = 2048  # Claude API recommendation


def prepare_image_for_vision(data: bytes) -> tuple[bytes, str]:
    """
    Convert any image format to JPEG/PNG suitable for Claude Vision.

    Handles: JPEG, PNG, WebP, AVIF (with ffmpeg fallback).
    Resizes to MAX_DIMENSION on longest side.

    Returns:
        (image_bytes, media_type) — e.g. (b"...", "image/jpeg")

    Raises:
        ValueError: if format cannot be determined or converted.
    """
    fmt = _detect_format(data)

    if fmt == "avif":
        data = _convert_avif_to_jpeg(data)
        fmt = "jpeg"

    try:
        img = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"Cannot open image: {exc}") from exc

    img = _resize(img)

    # Normalize format: keep PNG if source was PNG, else JPEG
    output_format = "PNG" if fmt == "png" else "JPEG"
    media_type = "image/png" if output_format == "PNG" else "image/jpeg"

    if img.mode not in ("RGB", "RGBA") and output_format == "JPEG":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format=output_format, quality=90, optimize=True)
    return buf.getvalue(), media_type


def _detect_format(data: bytes) -> str:
    """Detect image format from magic bytes."""
    if data[:4] == b"\x00\x00\x00\x1c" or b"ftypavif" in data[:16] or b"ftypavis" in data[:16]:
        return "avif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    # Fallback: let Pillow figure it out
    try:
        img = Image.open(io.BytesIO(data))
        return str(img.format or "jpeg").lower()
    except Exception:
        raise ValueError("Unknown or unsupported image format")


def _resize(img: Image.Image) -> Image.Image:
    """Resize image so longest side <= MAX_DIMENSION."""
    w, h = img.size
    if max(w, h) <= MAX_DIMENSION:
        return img
    scale = MAX_DIMENSION / max(w, h)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)


def _convert_avif_to_jpeg(data: bytes) -> bytes:
    """Convert AVIF bytes to JPEG using ffmpeg subprocess."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "input.avif"
        dst = Path(tmp) / "output.jpg"
        src.write_bytes(data)

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), str(dst)],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise ValueError(
                f"ffmpeg AVIF conversion failed: {result.stderr.decode()[:200]}"
            )
        return dst.read_bytes()