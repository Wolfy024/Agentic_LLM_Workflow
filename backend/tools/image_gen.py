"""
Image generation tool using a Stable Diffusion API endpoint.

Calls a remote SD API, saves the generated image to disk, and opens it
in the system's default image viewer.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import datetime

import httpx

from tools.registry import tool, _resolve

# Module-level state set from config at startup
_SD_API_BASE: str = ""
_SD_API_KEY: str = ""


def configure_sd(api_base: str, api_key: str = "") -> None:
    """Set the Stable Diffusion API endpoint and key at startup."""
    global _SD_API_BASE, _SD_API_KEY
    _SD_API_BASE = api_base.rstrip("/")
    _SD_API_KEY = api_key


def _default_save_path(prompt: str) -> str:
    """Generate a default filename from the prompt."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Clean prompt for filename: take first 40 chars, replace spaces
    clean = prompt[:40].strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return f"generated_{clean}_{ts}.png"


@tool(
    name="generate_image",
    description=(
        "Generate an image using Stable Diffusion from a text prompt. "
        "Saves the image to the specified path and opens it in the default viewer. "
        "If no save_path is given, saves to the workspace with an auto-generated name. "
        "CRITICAL: Do NOT call view_image on the generated image after using this tool unless the user explicitly requests a description or analysis of it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the image to generate.",
            },
            "save_path": {
                "type": "string",
                "description": "Where to save the generated image. Relative to workspace or absolute. If omitted, auto-generates a name in the workspace.",
            },
        },
        "required": ["prompt"],
    },
)
def generate_image(prompt: str, save_path: str | None = None) -> str:
    """Call the SD API, save the image, and open it."""
    if not _SD_API_BASE:
        return json.dumps({"error": "Stable Diffusion API not configured. Set 'sd_api_base' in config.json."})

    # Resolve save path
    if not save_path:
        save_path = _default_save_path(prompt)
    resolved = _resolve(save_path)

    # Ensure parent directory exists
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Call SD API
    url = f"{_SD_API_BASE}/generate"
    headers = {"Content-Type": "application/json"}
    if _SD_API_KEY:
        headers["Authorization"] = f"Bearer {_SD_API_KEY}"

    import core.runtime_config as rc
    timeout_val = float(rc.get("sd_timeout", 120))
    try:
        with httpx.Client(timeout=timeout_val) as client:
            resp = client.post(url, json={"prompt": prompt}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return json.dumps({"error": "SD API timed out (120s). The model may be loading or the prompt is too complex."})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"SD API returned {e.response.status_code}: {e.response.text[:200]}"})
    except Exception as e:
        return json.dumps({"error": f"SD API request failed: {str(e)}"})

    img_b64 = data.get("image")
    if not img_b64:
        return json.dumps({"error": f"SD API response missing 'image' key. Got keys: {list(data.keys())}"})

    # Decode and save
    try:
        img_bytes = base64.b64decode(img_b64)
    except Exception as e:
        return json.dumps({"error": f"Failed to decode base64 image: {e}"})

    with open(resolved, "wb") as f:
        f.write(img_bytes)

    # Open in default viewer (non-blocking)
    _open_image(resolved)

    return json.dumps({
        "status": "success",
        "path": resolved,
        "size_bytes": len(img_bytes),
        "prompt": prompt,
        "message": f"Image generated and saved to {resolved}. Opened in default viewer.",
    })


def _open_image(path: str) -> None:
    """Open an image in the system's default viewer."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass  # Non-critical — don't fail the tool if viewer can't open
