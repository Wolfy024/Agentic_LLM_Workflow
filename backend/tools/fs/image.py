"""
Image viewing tool for multimodal LLM interaction.

Encodes an image as base64 and returns a special marker so the runner
can inject it as a multimodal user message for vision-capable models.
"""

from __future__ import annotations

import json
import os

from tools.registry import tool, _resolve
from llm.vision import build_user_content_with_image, _EXT_MIME

# Extensions recognized as images
_IMAGE_EXTENSIONS = set(_EXT_MIME.keys())

# Marker key used by the runner to detect image tool results
IMAGE_MARKER = "__view_image__"


@tool(
    name="view_image",
    description=(
        "View an image file and send it to the model for analysis. "
        "Use this when the user asks about screenshots, photos, diagrams, "
        "or any visual content. Supports PNG, JPG, GIF, WebP, BMP, TIFF. "
        "CRITICAL: Do NOT use this tool automatically after generating an image. Only use it if the user explicitly asks you to."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the image file (relative or absolute)"},
            "question": {
                "type": "string",
                "description": "What to ask about the image. Default: 'Describe this image in detail.'",
            },
        },
        "required": ["path"],
    },
)
def view_image(path: str, question: str = "Describe this image in detail.") -> str:
    """Read an image and return a marker for the runner to inject as multimodal content."""
    resolved = _resolve(path)

    if not os.path.isfile(resolved):
        return json.dumps({"error": f"Not a file: {path}"})

    ext = os.path.splitext(resolved)[1].lower()
    if ext not in _IMAGE_EXTENSIONS:
        return json.dumps({"error": f"Not a recognized image format: {ext}. Supported: {', '.join(sorted(_IMAGE_EXTENSIONS))}"})

    try:
        content = build_user_content_with_image(question, resolved)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    # Return special marker JSON that the runner will intercept
    return json.dumps({
        IMAGE_MARKER: True,
        "content": content,
        "path": path,
    })
