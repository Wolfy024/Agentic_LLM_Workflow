"""Windows GUI installer for LLM Orchestrator."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes
    import winreg

APP_NAME = "LLM Orchestrator"
INSTALL_DIR_NAME = "LLM_Orchestrator"

EXE_SUFFIX = ".exe" if IS_WINDOWS else ""
PRIMARY_EXE_NAME = f"llm-orchestrator{EXE_SUFFIX}"
ALIAS_EXE_NAME = f"orchestrator{EXE_SUFFIX}"
CONFIG_FILE_NAME = "config.json"
STARTUP_BANNER_NAME = "startup_banner.txt"

DEFAULT_LLM_BASE = "https://chat.neuralnote.online/v1/"
DEFAULT_SD_BASE = "https://chat.neuralnote.online/sd"
DEFAULT_LLM_MODEL = "Qwen3.6-35B-Uncensored"

ENV_TEMPLATE = """# LLM Orchestrator Configuration
# Edit this file with your API credentials

LLM_API_KEY={llm_key}
SERPER_API_KEY={serper_key}
LLM_API_BASE={llm_base}
SD_API_BASE={sd_base}
LLM_MODEL={llm_model}
"""


def _base_dirs() -> list[Path]:
    dirs: list[Path] = []
    if getattr(sys, "frozen", False):
        dirs.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        dirs.append(Path(sys.executable).parent)
    else:
        dirs.append(Path(__file__).resolve().parent)
    return dirs


def _candidate_paths(rel_path: str) -> list[Path]:
    out: list[Path] = []
    for base in _base_dirs():
        out.append(base / rel_path)
    return out


def _find_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def resolve_payload() -> dict[str, Path | None]:
    exe = None
    if getattr(sys, "frozen", False):
        # We are the monolithic executable! Copy ourselves.
        exe = Path(sys.executable)
    else:
        exe_candidates = [
            PRIMARY_EXE_NAME,
            ALIAS_EXE_NAME,
            f"dist/{PRIMARY_EXE_NAME}",
            f"backend/dist/{PRIMARY_EXE_NAME}",
        ]
        for rel in exe_candidates:
            exe = _find_existing(_candidate_paths(rel))
            if exe:
                break

    config = _find_existing(_candidate_paths(CONFIG_FILE_NAME))
    banner = _find_existing(_candidate_paths(STARTUP_BANNER_NAME))
    return {"exe": exe, "config": config, "banner": banner}


def get_default_install_dir() -> Path:
    if IS_WINDOWS:
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_app_data) / INSTALL_DIR_NAME
    else:
        return Path.home() / ".local" / "share" / INSTALL_DIR_NAME


def _normalize_win_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path.strip()))


def _broadcast_env_change() -> None:
    if not IS_WINDOWS:
        return
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None
    )


def add_to_linux_path(install_dir: Path) -> bool:
    try:
        target = str(install_dir)
        line_to_add = f'\nexport PATH="$PATH:{target}"\n'
        
        rc_files = [Path.home() / ".bashrc", Path.home() / ".zshrc"]
        added = False
        for rc in rc_files:
            if rc.exists():
                content = rc.read_text(encoding="utf-8")
                if f'PATH="$PATH:{target}"' not in content and f'PATH="{target}:$PATH"' not in content:
                    with open(rc, "a", encoding="utf-8") as f:
                        f.write(line_to_add)
                added = True
        return added
    except Exception:
        return False


def remove_from_linux_path(install_dir: Path) -> bool:
    try:
        target = str(install_dir)
        rc_files = [Path.home() / ".bashrc", Path.home() / ".zshrc"]
        for rc in rc_files:
            if rc.exists():
                lines = rc.read_text(encoding="utf-8").splitlines()
                new_lines = [line for line in lines if target not in line]
                rc.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def add_to_user_path(install_dir: Path) -> bool:
    if not IS_WINDOWS:
        return add_to_linux_path(install_dir)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                user_path, _ = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                user_path = ""
            entries = [e for e in user_path.split(";") if e.strip()]
            normalized = {_normalize_win_path(e) for e in entries}
            if _normalize_win_path(str(install_dir)) not in normalized:
                entries.append(str(install_dir))
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, ";".join(entries))
        _broadcast_env_change()
        return True
    except Exception:
        return False


def remove_from_user_path(install_dir: Path) -> bool:
    if not IS_WINDOWS:
        return remove_from_linux_path(install_dir)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                user_path, _ = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                user_path = ""
            target = _normalize_win_path(str(install_dir))
            entries = [e for e in user_path.split(";") if e.strip()]
            kept = [e for e in entries if _normalize_win_path(e) != target]
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, ";".join(kept))
        _broadcast_env_change()
        return True
    except Exception:
        return False


def _write_env_file(target: Path, llm_key: str, serper_key: str, llm_base: str, sd_base: str, llm_model: str) -> None:
    target.write_text(
        ENV_TEMPLATE.format(
            llm_key=llm_key,
            serper_key=serper_key,
            llm_base=llm_base,
            sd_base=sd_base,
            llm_model=llm_model,
        ),
        encoding="utf-8",
    )


def install_to_dir(
    install_dir: Path,
    llm_key: str,
    serper_key: str,
    llm_base: str,
    sd_base: str,
    llm_model: str,
    add_path: bool,
) -> tuple[Path, bool]:
    payload = resolve_payload()
    exe_src = payload["exe"]
    if exe_src is None:
        raise RuntimeError(
            f"Could not find {PRIMARY_EXE_NAME}. Build it first (dist/{PRIMARY_EXE_NAME}) "
            "or place it next to the installer."
        )
    if payload["config"] is None:
        raise RuntimeError("Could not find config.json required by the orchestrator.")

    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe_src, install_dir / PRIMARY_EXE_NAME)
    shutil.copy2(exe_src, install_dir / ALIAS_EXE_NAME)
    shutil.copy2(payload["config"], install_dir / CONFIG_FILE_NAME)
    if payload["banner"] is not None:
        shutil.copy2(payload["banner"], install_dir / STARTUP_BANNER_NAME)

    _write_env_file(install_dir / ".env", llm_key, serper_key, llm_base, sd_base, llm_model)
    path_ok = add_to_user_path(install_dir) if add_path else True
    return install_dir, path_ok


def uninstall_from_dir(install_dir: Path) -> None:
    remove_from_user_path(install_dir)
    if install_dir.exists():
        shutil.rmtree(install_dir)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        values[k.strip()] = v.strip()
    return values


class InstallerWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} Setup")
        self.root.geometry("640x500")
        self.root.resizable(False, False)
        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text=f"{APP_NAME} Setup", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(main, text="Install and configure your local agent runtime.").pack(anchor="w", pady=(0, 14))

        grid = ttk.Frame(main)
        grid.pack(fill=tk.X)
        grid.columnconfigure(1, weight=1)

        self.vars = {
            "install_dir": tk.StringVar(value=str(get_default_install_dir())),
            "llm_key": tk.StringVar(),
            "serper_key": tk.StringVar(),
            "llm_base": tk.StringVar(value=DEFAULT_LLM_BASE),
            "sd_base": tk.StringVar(value=DEFAULT_SD_BASE),
            "llm_model": tk.StringVar(value=DEFAULT_LLM_MODEL),
            "add_path": tk.BooleanVar(value=True),
        }

        self._row(grid, 0, "Install Directory", "install_dir", browse=True)
        self._row(grid, 1, "LLM API Key", "llm_key", secret=True)
        self._row(grid, 2, "Serper API Key", "serper_key", secret=True)
        self._row(grid, 3, "LLM API Base", "llm_base")
        self._row(grid, 4, "SD API Base", "sd_base")
        self._row(grid, 5, "LLM Model", "llm_model")

        ttk.Checkbutton(
            main,
            variable=self.vars["add_path"],
            text="Add install directory to user PATH (recommended)",
        ).pack(anchor="w", pady=(10, 6))

        self.status = ttk.Label(main, text="")
        self.status.pack(anchor="w", pady=(6, 8))

        buttons = ttk.Frame(main)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Install", command=self._on_install).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Uninstall", command=self._on_uninstall).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Close", command=self.root.destroy).pack(side=tk.RIGHT)

    def _row(self, parent: ttk.Frame, idx: int, label: str, key: str, secret: bool = False, browse: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=idx, column=0, sticky="w", padx=(0, 8), pady=5)
        entry = ttk.Entry(parent, textvariable=self.vars[key], show="*" if secret else "")
        entry.grid(row=idx, column=1, sticky="ew", pady=5)
        if browse:
            ttk.Button(parent, text="Browse...", command=self._browse_install_dir).grid(row=idx, column=2, padx=(8, 0))

    def _browse_install_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Choose installation directory")
        if chosen:
            self.vars["install_dir"].set(chosen)

    def _on_install(self) -> None:
        llm_key = self.vars["llm_key"].get().strip()
        llm_model = self.vars["llm_model"].get().strip()
        install_dir_raw = self.vars["install_dir"].get().strip()
        if not install_dir_raw:
            messagebox.showwarning("Validation", "Install directory is required.")
            return
        if not llm_key:
            messagebox.showwarning("Validation", "LLM API Key is required.")
            return
        if not llm_model:
            messagebox.showwarning("Validation", "LLM Model is required.")
            return

        self.status.config(text="Installing...")
        self.root.update_idletasks()

        try:
            install_dir, path_ok = install_to_dir(
                install_dir=Path(install_dir_raw),
                llm_key=llm_key,
                serper_key=self.vars["serper_key"].get().strip(),
                llm_base=self.vars["llm_base"].get().strip(),
                sd_base=self.vars["sd_base"].get().strip(),
                llm_model=llm_model,
                add_path=self.vars["add_path"].get(),
            )
        except Exception as e:
            self.status.config(text="Install failed.")
            messagebox.showerror("Install failed", str(e))
            return

        extra = "" if path_ok else "\n\nWarning: failed to modify PATH automatically."
        self.status.config(text="Install completed.")
        messagebox.showinfo(
            "Success",
            f"{APP_NAME} installed successfully.\n\nInstall dir:\n{install_dir}"
            f"{extra}\n\nOpen a new terminal and run:\norchestrator [workspace_path]",
        )

    def _on_uninstall(self) -> None:
        install_dir = Path(self.vars["install_dir"].get().strip() or str(get_default_install_dir()))
        if not messagebox.askyesno(
            "Confirm uninstall",
            f"Remove {APP_NAME} from:\n{install_dir}\n\nThis also removes it from user PATH.",
        ):
            return
        try:
            uninstall_from_dir(install_dir)
        except Exception as e:
            messagebox.showerror("Uninstall failed", str(e))
            return
        self.status.config(text="Uninstall completed.")
        messagebox.showinfo("Uninstalled", f"Removed installation from:\n{install_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Installer")
    parser.add_argument("--silent", action="store_true", help="Run non-interactive install.")
    parser.add_argument("--env-file", type=str, help="Path to .env values for silent install.")
    parser.add_argument("--install-dir", type=str, default=str(get_default_install_dir()))
    parser.add_argument("--no-path", action="store_true", help="Do not add install directory to user PATH.")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall from --install-dir.")
    args = parser.parse_args()

    if args.uninstall:
        target = Path(args.install_dir)
        uninstall_from_dir(target)
        print(f"Uninstalled from: {target}")
        return

    if args.silent:
        if not args.env_file:
            raise SystemExit("ERROR: --silent requires --env-file")
        env_values = _read_env_file(Path(args.env_file))
        install_dir, path_ok = install_to_dir(
            install_dir=Path(args.install_dir),
            llm_key=env_values.get("LLM_API_KEY", ""),
            serper_key=env_values.get("SERPER_API_KEY", ""),
            llm_base=env_values.get("LLM_API_BASE", DEFAULT_LLM_BASE),
            sd_base=env_values.get("SD_API_BASE", DEFAULT_SD_BASE),
            llm_model=env_values.get("LLM_MODEL", DEFAULT_LLM_MODEL),
            add_path=not args.no_path,
        )
        print(f"Installed to: {install_dir}")
        print("PATH updated." if path_ok else "WARNING: failed to update PATH.")
        return

    InstallerWindow().root.mainloop()


if __name__ == "__main__":
    main()
