"""
Multimodal user messages (vision) for OpenAI-compatible chat APIs.

Embeds a local image as a data URL in ``image_url`` so the model can see pixels.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import core.runtime_config as rc

_DEFAULT_MAX_BYTES = 20 * 1024 * 1024


def _max_image_bytes() -> int:
    return int(rc.get("max_image_mb", 20)) * 1024 * 1024

# Prefer explicit MIME; guess_type is fallback.
_EXT_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def build_user_content_with_image(
    instruction: str,
    resolved_path: str,
    *,
    max_bytes: int | None = None,
    detail: str | None = "auto",
) -> list[dict]:
    """
    Build OpenAI-style ``content`` parts: text + image_url (base64 data URL).

    Raises:
        ValueError: empty file, unknown type, or over ``max_bytes``.
    """
    if max_bytes is None:
        max_bytes = _max_image_bytes()
    ext = os.path.splitext(resolved_path)[1].lower()
    mime = _EXT_MIME.get(ext)
    if not mime:
        guessed, _ = mimetypes.guess_type(resolved_path)
        mime = guessed or "image/png"

    size = os.path.getsize(resolved_path)
    if size == 0:
        raise ValueError("Image file is empty.")
    if size > max_bytes:
        raise ValueError(
            f"Image too large ({size:,} bytes; max {max_bytes:,}). "
            f"Shrink the file or raise config max_image_mb."
        )

    with open(resolved_path, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    text = instruction.strip() or "Describe this image in detail."
    image_url: dict = {"url": data_url}
    if detail:
        image_url["detail"] = detail
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": image_url},
    ]
