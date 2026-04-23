r"""
LLM Orchestrator Windows Installer

A tkinter-based GUI installer that:
1. Copies the built orchestrator.exe to %LOCALAPPDATA%\LLM_Orchestrator\
2. Creates a .env file with user-provided API credentials
3. Optionally adds the install directory to the user PATH

Usage:
    python installer.py          # Interactive GUI installer
    python installer.py --silent # Silent mode (requires --env-file)
"""

import os
import sys
import shutil
import argparse
import tkinter as tk
from tkinter import messagebox, ttk
import winreg
import ctypes


# ── Constants ────────────────────────────────────────────────────────────────

INSTALL_DIR_NAME = "LLM_Orchestrator"
ENV_TEMPLATE = """# LLM Orchestrator Configuration
# Edit this file with your API credentials

LLM_API_KEY={llm_key}
SERPER_API_KEY={serper_key}
LLM_API_BASE={llm_base}
SD_API_BASE={sd_base}
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_base_path():
    """Get the directory where this script lives."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def find_orchestrator_exe():
    """
    Locate the built orchestrator.exe.

    Search order:
    1. If frozen (bundled): look in the same directory as the exe
    2. If not frozen: look in backend/dist/ relative to this script
    """
    base = get_base_path()

    # Frozen: exe is alongside this installer
    if getattr(sys, 'frozen', False):
        exe = os.path.join(base, "orchestrator.exe")
        if os.path.exists(exe):
            return exe

    # Development: backend/dist/llm-orchestrator.exe
    dev_exe = os.path.join(base, "backend", "dist", "llm-orchestrator.exe")
    if os.path.exists(dev_exe):
        return dev_exe

    # Fallback: same dir as installer (for bundled case)
    fallback = os.path.join(base, "llm-orchestrator.exe")
    if os.path.exists(fallback):
        return fallback

    return None


def add_to_path(install_dir):
    """
    Add install_dir to the user PATH environment variable.

    Returns True on success, False on failure.
    Broadcasts WM_SETTINGCHANGE so new terminals pick up the change.
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_ALL_ACCESS,
        )
        try:
            user_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            user_path = ""

        if install_dir not in user_path:
            separator = ";" if user_path and not user_path.endswith(";") else ""
            new_path = user_path + separator + install_dir
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)

            # Notify the system so new processes see the updated PATH
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                "Environment",
                SMTO_ABORTIFHUNG,
                5000,
                None,
            )

        key.Close()
        return True
    except Exception as e:
        print(f"Failed to add to PATH automatically: {e}")
        return False


def remove_from_path(install_dir):
    """Remove install_dir from the user PATH environment variable."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_ALL_ACCESS,
        )
        user_path, _ = winreg.QueryValueEx(key, "PATH")
        key.Close()

        entries = [e for e in user_path.split(";") if e != install_dir]
        new_path = ";".join(entries)
        if not new_path.startswith(";"):
            new_path = new_path.lstrip(";")

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_ALL_ACCESS,
        )
        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
        key.Close()

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            None,
        )
        return True
    except Exception as e:
        print(f"Failed to remove from PATH: {e}")
        return False


def is_installed():
    """Check if the orchestrator is already installed."""
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    install_dir = os.path.join(local_app_data, INSTALL_DIR_NAME)
    return os.path.exists(os.path.join(install_dir, "orchestrator.exe"))


def get_install_dir():
    """Get the standard installation directory."""
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    return os.path.join(local_app_data, INSTALL_DIR_NAME)


# ── Silent Installer ────────────────────────────────────────────────────────

def silent_install(llm_key, serper_key, llm_base, sd_base):
    """Non-interactive installation. Used by --silent flag."""
    exe_path = find_orchestrator_exe()
    if not exe_path:
        print("ERROR: Could not find orchestrator.exe. Build the app first.")
        sys.exit(1)

    install_dir = get_install_dir()
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)

    target_exe = os.path.join(install_dir, "orchestrator.exe")
    try:
        shutil.copy2(exe_path, target_exe)
    except Exception as e:
        print(f"ERROR: Failed to copy executable: {e}")
        sys.exit(1)

    env_path = os.path.join(install_dir, ".env")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(ENV_TEMPLATE.format(
                llm_key=llm_key,
                serper_key=serper_key,
                llm_base=llm_base,
                sd_base=sd_base,
            ))
    except Exception as e:
        print(f"ERROR: Failed to write .env: {e}")
        sys.exit(1)

    print(f"Installed to: {install_dir}")
    print(f"Config written to: {env_path}")
    sys.exit(0)


# ── GUI Installer ───────────────────────────────────────────────────────────

class InstallerWindow:
    """Main installer GUI window."""

    WINDOW_WIDTH = 520
    WINDOW_HEIGHT = 420

    DEFAULT_LLM_BASE = "https://chat.neuralnote.online/chat/v1"
    DEFAULT_SD_BASE = "https://chat.neuralnote.online/sd"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LLM Orchestrator Installer")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = int((screen_w / 2) - (self.WINDOW_WIDTH / 2))
        y = int((screen_h / 2) - (self.WINDOW_HEIGHT / 2))
        self.root.geometry(
            f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{x}+{y}"
        )
        self.root.resizable(False, False)

        # Center the window after it's been mapped
        self.root.after(10, self._center_window)

        self._build_ui()

    def _center_window(self):
        """Re-center the window after initial mapping (handles DPI)."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = int((screen_w / 2) - (self.WINDOW_WIDTH / 2))
        y = int((screen_h / 2) - (self.WINDOW_HEIGHT / 2))
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Construct the installer UI."""
        # Title
        lbl_title = tk.Label(
            self.root,
            text="LLM Orchestrator Setup",
            font=("Segoe UI", 16, "bold"),
        )
        lbl_title.pack(pady=(18, 6))

        # Subtitle
        lbl_subtitle = tk.Label(
            self.root,
            text="Enter your API credentials to get started",
            font=("Segoe UI", 9),
            fg="gray",
        )
        lbl_subtitle.pack(pady=(0, 10))

        # Main frame
        frame = tk.Frame(self.root, padx=24, pady=8)
        frame.pack(fill=tk.BOTH, expand=True)

        # ── Input fields ────────────────────────────────────────────────
        row = 0
        self.entries = {}

        fields = [
            ("LLM API Key:", "llm_key", True),
            ("Serper API Key:", "serper_key", True),
            ("LLM API Base:", "llm_base", False, self.DEFAULT_LLM_BASE),
            ("SD API Base:", "sd_base", False, self.DEFAULT_SD_BASE),
        ]

        for label_text, var_name, is_password, *default in fields:
            tk.Label(
                frame, text=label_text, font=("Segoe UI", 9)
            ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))

            ent = tk.Entry(
                frame,
                width=48,
                font=("Segoe UI", 9),
                show="*" if is_password else "",
            )
            ent.grid(row=row, column=1, pady=4, padx=(0, 8))
            if default:
                ent.insert(0, default[0])

            self.entries[var_name] = ent
            row += 1

        # ── Options ───────────────────────────────────────────────────────
        self.var_path = tk.BooleanVar(value=True)
        self.var_uninstall = tk.BooleanVar(value=False)

        chk_path = tk.Checkbutton(
            frame,
            text="Add to User PATH (run 'orchestrator' from any terminal)",
            variable=self.var_path,
            font=("Segoe UI", 9),
        )
        chk_path.grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 2), padx=(0, 8))
        row += 1

        chk_uninstall = tk.Checkbutton(
            frame,
            text="Uninstall previous installation",
            variable=self.var_uninstall,
            font=("Segoe UI", 9),
            fg="red",
        )
        chk_uninstall.grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 2), padx=(0, 8))
        row += 1

        # ── Status label ──────────────────────────────────────────────────
        self.lbl_status = tk.Label(
            frame, text="", font=("Segoe UI", 9), fg="gray"
        )
        self.lbl_status.grid(row=row, column=0, columnspan=2, pady=(4, 0))

        # ── Buttons ───────────────────────────────────────────────────────
        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=row + 1, column=0, columnspan=2, pady=(14, 0))

        btn_install = tk.Button(
            btn_frame,
            text="Install",
            command=self._on_install,
            width=14,
            bg="#4CAF50",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=2,
        )
        btn_install.pack(side=tk.LEFT, padx=(0, 8))

        btn_uninstall = tk.Button(
            btn_frame,
            text="Uninstall",
            command=self._on_uninstall,
            width=14,
            bg="#f44336",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=2,
        )
        btn_uninstall.pack(side=tk.LEFT)

    def _on_install(self):
        """Handle the Install button click."""
        llm_key = self.entries["llm_key"].get().strip()
        serper_key = self.entries["serper_key"].get().strip()
        llm_base = self.entries["llm_base"].get().strip()
        sd_base = self.entries["sd_base"].get().strip()

        if not llm_key:
            messagebox.showwarning("Warning", "LLM API Key is required.")
            return

        self.lbl_status.config(text="Installing…", fg="blue")
        self.root.update()

        try:
            self._do_install(llm_key, serper_key, llm_base, sd_base)
        except Exception as e:
            messagebox.showerror("Error", f"Installation failed:\n{e}")
            self.lbl_status.config(text="Failed", fg="red")

    def _do_install(self, llm_key, serper_key, llm_base, sd_base):
        """Perform the actual installation steps."""
        exe_path = find_orchestrator_exe()
        if not exe_path:
            raise RuntimeError(
                "Could not find orchestrator.exe.\n\n"
                "Please build the main application first:\n"
                "  cd backend\n"
                "  pyinstaller llm-orchestrator.spec"
            )

        install_dir = get_install_dir()
        if not os.path.exists(install_dir):
            os.makedirs(install_dir)

        # Copy executable
        target_exe = os.path.join(install_dir, "orchestrator.exe")
        shutil.copy2(exe_path, target_exe)

        # Write .env
        env_path = os.path.join(install_dir, ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(ENV_TEMPLATE.format(
                llm_key=llm_key,
                serper_key=serper_key,
                llm_base=llm_base,
                sd_base=sd_base,
            ))

        # PATH
        path_msg = ""
        if self.var_path.get():
            if add_to_path(install_dir):
                path_msg = f"\n\nAdded to PATH: {install_dir}"
            else:
                path_msg = (
                    f"\n\n⚠ Failed to add to PATH automatically.\n"
                    f"Please add {install_dir} to your PATH manually."
                )

        self.lbl_status.config(text="Done!", fg="green")
        messagebox.showinfo(
            "Installation Complete",
            f"LLM Orchestrator installed successfully!\n\n"
            f"Installed to: {install_dir}{path_msg}\n\n"
            f"Open a NEW terminal and run:\n"
            f"  orchestrator [workspace_path]",
        )

    def _on_uninstall(self):
        """Handle the Uninstall button click."""
        if not messagebox.askyesno(
            "Confirm Uninstall",
            "Remove LLM Orchestrator installation?\n\n"
            "This will delete the installed files and remove the PATH entry.",
        ):
            return

        install_dir = get_install_dir()
        try:
            # Remove from PATH
            if self.var_path.get():
                remove_from_path(install_dir)

            # Delete install directory
            if os.path.exists(install_dir):
                shutil.rmtree(install_dir)

            messagebox.showinfo(
                "Uninstall Complete",
                f"LLM Orchestrator has been removed.\n\n"
                f"Deleted: {install_dir}",
            )
        except Exception as e:
            messagebox.showerror("Error", f"Uninstall failed:\n{e}")


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LLM Orchestrator Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python installer.py                          # Interactive GUI
  python installer.py --silent                 # Silent install (requires --env-file)
  python installer.py --silent --env-file .env # Silent install with .env
  python installer.py --uninstall              # Uninstall
""",
    )
    parser.add_argument(
        "--silent", action="store_true", help="Run in silent (non-interactive) mode"
    )
    parser.add_argument(
        "--env-file",
        type=str,
        help="Path to a .env file to read credentials from (used with --silent)",
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="Uninstall LLM Orchestrator"
    )
    args = parser.parse_args()

    # ── Uninstall mode ──────────────────────────────────────────────────
    if args.uninstall:
        install_dir = get_install_dir()
        if not os.path.exists(install_dir):
            print(f"Not installed: {install_dir}")
            sys.exit(0)

        if args.silent or messagebox.askyesno(
            "Confirm Uninstall",
            "Remove LLM Orchestrator installation?",
        ):
            remove_from_path(install_dir)
            shutil.rmtree(install_dir)
            print(f"Uninstalled: {install_dir}")
            sys.exit(0)
        else:
            print("Uninstall cancelled.")
            sys.exit(0)

    # ── Silent install mode ─────────────────────────────────────────────
    if args.silent:
        if args.env_file:
            # Read from .env file
            if not os.path.exists(args.env_file):
                print(f"ERROR: .env file not found: {args.env_file}")
                sys.exit(1)
            creds = {}
            with open(args.env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        creds[key.strip()] = value.strip()

            silent_install(
                llm_key=creds.get("LLM_API_KEY", ""),
                serper_key=creds.get("SERPER_API_KEY", ""),
                llm_base=creds.get("LLM_API_BASE", ""),
                sd_base=creds.get("SD_API_BASE", ""),
            )
        else:
            print("ERROR: --silent requires --env-file")
            sys.exit(1)

    # ── Interactive GUI mode ────────────────────────────────────────────
    app = InstallerWindow()
    app.root.mainloop()


if __name__ == "__main__":
    main()
