"""LLM Orchestrator Tools — registry and tool implementations.

Importing this package loads all tool modules so the shared TOOL_REGISTRY is populated.
"""

from __future__ import annotations

import importlib

from .registry import (
    TOOL_REGISTRY,
    WORKSPACE,
    MAX_READ_SIZE,
    set_workspace,
    get_tool_schemas,
    execute_tool,
    _resolve,
    is_path_inside_workspace,
    tool,
)

from .web.serper import set_serper_key

_TOOL_SUBMODULES = (
    ".fs.read",
    ".fs.write",
    ".fs.edit",
    ".fs.search",
    ".fs.external",
    ".fs.image",
    ".git.core",
    ".git.diff",
    ".git.info",
    ".git.ops",
    ".git.remote_sync",
    ".git.github",
    ".web.serper",
    ".web.fetch",
    ".system",
    ".image_gen",
)

for _sub in _TOOL_SUBMODULES:
    importlib.import_module(_sub, __name__)

del importlib, _sub, _TOOL_SUBMODULES
