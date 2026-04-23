"""Context injection commands: /task, /plan, /recipe, /image."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from core.repl_utils import apply_recipe_payload, recipe_candidate_paths, safe_name
from llm.vision import build_user_content_with_image
from tools.registry import WORKSPACE, _resolve
from ui.console import console
from ui.context_logs import print_error
from ui.dimming import muted
from ui.palette import success

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_task(ctx: CommandContext) -> None:
    """Inject a structured task checklist into context."""
    text = ctx.arg
    if text.strip():
        ctx.runner.state.messages.append({
            "role": "system",
            "content": f"[Task checklist]\n1. Restate goal.\n2. List tools.\n3. Execute.\nGoal: {text}",
        })
        console.print(success("  task checklist injected"))


def cmd_plan(ctx: CommandContext) -> None:
    """Add planning checklist message."""
    ctx.runner.state.messages.append(
        {"role": "system", "content": "[Planning mode]\n- Break work down.\n- Read before write."}
    )
    console.print(success("  planning prompt injected"))


def cmd_recipe(ctx: CommandContext) -> None:
    """Load a prompt recipe from .minillm/recipes/."""
    arg = ctx.arg
    if not arg:
        console.print(muted("  /recipe <name>  — loads .minillm/recipes/<name>.json (workspace or ~/.minillm)"))
        return

    found = None
    for path in recipe_candidate_paths(WORKSPACE, arg):
        if os.path.isfile(path):
            found = path
            break
    if not found:
        bn = safe_name(arg)
        print_error(f"Recipe not found: .minillm/recipes/{bn}.json")
        return

    try:
        with open(found, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print_error(str(e))
        return
    if not isinstance(data, dict) or not apply_recipe_payload(ctx.runner, data):
        print_error("Recipe JSON needs prompt, system, user, or messages[]")
        return
    console.print(success(f"  recipe injected ({os.path.basename(found)})"))


def cmd_image(ctx: CommandContext) -> None:
    """Send a workspace image to the multimodal model."""
    rest = ctx.rest
    if not rest:
        console.print(muted("  Usage: /image <file.png> [instruction]  — file path."))
        console.print(muted("  Embeds the image as base64 for multimodal models (OpenAI-style image_url)."))
        console.print(muted("  Example: /image 1.png describe what you see"))
        return

    path_raw, _, tail = rest.partition(" ")
    path_raw = path_raw.strip()
    instruction = tail.strip() if tail.strip() else "Describe this image in detail."

    resolved = _resolve(path_raw)
    if not os.path.isfile(resolved):
        print_error(f"Not a file: {path_raw}")
        return

    rel = os.path.relpath(resolved, WORKSPACE).replace("\\", "/")
    max_mb = float(ctx.config.get("max_image_mb", 20))
    max_bytes = int(max_mb * 1024 * 1024)
    d_raw = ctx.config.get("vision_image_detail", "auto")
    detail_kw: str | None
    if d_raw in (False, None, "", "omit", "none"):
        detail_kw = None
    else:
        detail_kw = str(d_raw)

    try:
        content = build_user_content_with_image(
            instruction, resolved, max_bytes=max_bytes, detail=detail_kw
        )
    except ValueError as e:
        print_error(str(e))
        return

    console.print(muted(f"  sending image to model ({rel})…"))
    ctx.runner.chat_turn(content)
