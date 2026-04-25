"""
Startup banner rendering logic.

Builds the LLM Orchestrator styled Rich panel logotype dynamically and 
displays the configuration stats.
"""

from __future__ import annotations
import os
import sys

from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.console import Group
from rich import box

from ui.console import console
from ui.dimming import muted
from ui.palette import primary
from ui.components import divider, label_value, status_dot

WELCOME_TIP = f"  {muted('Type a message to start. Use')} {primary('/help', bold=False)} {muted('for commands.')}"


def build_antigravity_banner() -> Panel:
    """Dynamically build the centered ASCII art banner using a color gradient."""
    logo_text = [
        "  _    _    __  __    ___  ___  ___ _  _ ___ ___ _____ ___    _ _____ ___  ___ ",
        " | |  | |  |  \\/  |  / _ \\| _ \\/ __| || | __/ __|_   _| _ \\  /_\\_   _/ _ \\| _ \\",
        " | |__| |__| |\\/| | | (_) |   / (__| __ | _|\\__ \\ | | |   / / _ \\| || (_) |   /",
        " |____|____|_|  |_|  \\___/|_|_\\\\___|_||_|___|___/ |_| |_|_\\/_/ \\_\\_| \\___/|_|_\\"
    ]
    colors = ["#6C63FF", "#4A8CFF", "#28B4FF", "#00D9FF"]
    group = Group()
    for row, color in zip(logo_text, colors):
        group.renderables.append(Text(row, style=f"bold {color}", justify="center"))
    
    group.renderables.append(Text(""))
    subtitle = Text("A U T O N O M O U S   A G E N T", justify="center")
    subtitle.stylize("bold #E5E7EB")
    group.renderables.append(subtitle)
    
    return Panel(
        group,
        box=box.ROUNDED,
        border_style="#4B5563",
        padding=(1, 4),
        expand=False
    )


def build_goodbye_banner() -> Panel:
    """Dynamically build the centered ASCII art goodbye banner."""
    logo_text = [
        "  ___ ___ ___  __   _____  _   _   ___  ___   ___  _  _  ",
        " / __| __| __| \\ \\ / / _ \\| | | | / __|/ _ \\ / _ \\| \\| | ",
        " \\__ \\ _|| _|   \\ V / (_) | |_| | \\__ \\ (_) | (_) | .` | ",
        " |___/___|___|   |_| \\___/ \\___/  |___/\\___/ \\___/|_|\\_| "
    ]
    colors = ["#6C63FF", "#4A8CFF", "#28B4FF", "#00D9FF"]
    group = Group()
    for row, color in zip(logo_text, colors):
        group.renderables.append(Text(row, style=f"bold {color}", justify="center"))
    
    group.renderables.append(Text(""))
    subtitle = Text("H A V E   F U N !", justify="center")
    subtitle.stylize("bold #E5E7EB")
    group.renderables.append(subtitle)
    
    return Panel(
        group,
        box=box.ROUNDED,
        border_style="#4B5563",
        padding=(1, 4),
        expand=False
    )


def print_banner(config: dict, workspace: str, session_name: str | None = None) -> None:
    """Print the startup banner sequence along with session config stats."""
    from core.config import get_root_dir
    banner_path = get_root_dir() / "startup_banner.txt"
    if banner_path.exists():
        with open(banner_path, "r", encoding="utf-8") as f:
            banner_content = f.read()
        sys.stdout.write(banner_content)
        sys.stdout.flush()
    else:
        console.print()
        console.print(Align.center(build_antigravity_banner()))
    
    console.print(f"  {divider(width=72)}")
    console.print()
    model_short = config.get("model", "unknown").split("/")[-1].split(":")[0]
    console.print(label_value("workspace", workspace))
    console.print(label_value("model", model_short))
    if session_name:
        console.print(label_value("last session", session_name))
    prof = config.get("profile", "strict")
    console.print(label_value("profile", prof))
    console.print(label_value("streaming", f"{status_dot(True)} enabled"))
    console.print(label_value("search", f"{status_dot(bool(config.get('serper_api_key')))} serper"))

    # MCP server status
    try:
        from mcp.manager import get_manager
        mgr = get_manager()
        if mgr.connected_count > 0 or mgr.server_names:
            console.print(label_value("mcp", f"{status_dot(mgr.connected_count > 0)} {mgr.get_summary()}"))
    except Exception:
        pass

    console.print()
    console.print(f"  {divider(width=72)}")
    console.print(WELCOME_TIP)
    console.print()
