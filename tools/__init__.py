"""MINILLM Tools package — organized by category.

Submodules:
    tools.registry    — Core infrastructure (decorator, executor, sandbox)
    tools.files       — File operations (17 tools)
    tools.git_local   — Local git operations (14 tools)
    tools.git_remote  — Remote git + GitHub (8 tools)
    tools.search_web  — Web search + URL fetching (4 tools)
    tools.system      — Shell, env info, processes (3 tools)

Importing this package auto-registers all tools in the shared TOOL_REGISTRY.
"""

from .registry import (
    TOOL_REGISTRY,
    WORKSPACE,
    MAX_READ_SIZE,
    set_workspace,
    get_tool_schemas,
    execute_tool,
    _resolve,
    tool,
)

from .search_web import set_serper_key

# Import submodules so their @tool decorators run and populate the registry.
from . import files       # noqa: F401
from . import git_local   # noqa: F401
from . import git_remote  # noqa: F401
from . import search_web  # noqa: F401
from . import system      # noqa: F401
