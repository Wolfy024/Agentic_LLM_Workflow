import os
import sys
import shutil
import tkinter as tk
from tkinter import messagebox

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def add_to_path(install_dir):
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            user_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            user_path = ""
        
        if install_dir not in user_path:
            new_path = user_path
            if new_path and not new_path.endswith(";"):
                new_path += ";"
            new_path += install_dir
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
            
            # Broadcast WM_SETTINGCHANGE to apply PATH immediately for new explorer/cmd windows
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None)
            return True
        else:
            return True # Already in path
    except Exception as e:
        print(f"Failed to add to PATH automatically: {e}")
        return False

def install_app(llm_key, serper_key, llm_base, sd_base, do_add_path):
    base_path = get_base_path()
    if getattr(sys, 'frozen', False):
        exe_path = os.path.join(base_path, "llm-orchestrator.exe")
    else:
        exe_path = os.path.join(base_path, "backend", "dist", "llm-orchestrator.exe")

    if not os.path.exists(exe_path):
        messagebox.showerror("Error", f"Could not find {exe_path}.\n\nPlease build the main application first.")
        sys.exit(1)

    # 1. Determine installation directory
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    install_dir = os.path.join(local_app_data, "LLM_Orchestrator")
    
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)

    # 2. Copy the executable and rename to "orchestrator.exe"
    target_exe = os.path.join(install_dir, "orchestrator.exe")
    try:
        shutil.copy2(exe_path, target_exe)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to copy executable to {install_dir}:\n{e}")
        return

    # 3. Create .env
    env_content = f"""LLM_API_KEY={llm_key}
SERPER_API_KEY={serper_key}
LLM_API_BASE={llm_base}
SD_API_BASE={sd_base}
"""
    try:
        with open(os.path.join(install_dir, ".env"), "w", encoding="utf-8") as f:
            f.write(env_content)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to write .env file:\n{e}")
        return

    # 4. PATH
    path_msg = ""
    if do_add_path:
        success = add_to_path(install_dir)
        if success:
            path_msg = f"\n\nAdded {install_dir} to User PATH."
        else:
            path_msg = f"\n\nFailed to add to PATH automatically.\nPlease add {install_dir} to your PATH manually."

    messagebox.showinfo(
        "Installation Complete", 
        f"LLM Orchestrator was successfully installed!\n\nInstalled to: {install_dir}{path_msg}\n\nYou can now start the application by typing 'orchestrator' in a NEW command prompt or PowerShell window."
    )
    sys.exit(0)

def main():
    root = tk.Tk()
    root.title("LLM Orchestrator Installer")
    
    # Calculate screen center for 500x350 window
    window_width = 500
    window_height = 350
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_cordinate = int((screen_width/2) - (window_width/2))
    y_cordinate = int((screen_height/2) - (window_height/2))
    
    root.geometry(f"{window_width}x{window_height}+{x_cordinate}+{y_cordinate}")
    root.resizable(False, False)

    # Title label
    lbl_title = tk.Label(root, text="LLM Orchestrator Setup", font=("Arial", 16, "bold"))
    lbl_title.pack(pady=(15, 10))

    # Main Frame
    frame = tk.Frame(root, padx=20, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    # API Keys
    tk.Label(frame, text="LLM API Key:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=8, padx=5)
    ent_llm_key = tk.Entry(frame, width=42, font=("Arial", 10))
    ent_llm_key.grid(row=0, column=1, pady=8, padx=5)

    tk.Label(frame, text="Serper API Key:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=8, padx=5)
    ent_serper_key = tk.Entry(frame, width=42, font=("Arial", 10))
    ent_serper_key.grid(row=1, column=1, pady=8, padx=5)

    # API Endpoints
    tk.Label(frame, text="LLM API Base:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=8, padx=5)
    ent_llm_base = tk.Entry(frame, width=42, font=("Arial", 10))
    ent_llm_base.insert(0, "https://chat.neuralnote.online/chat/v1")
    ent_llm_base.grid(row=2, column=1, pady=8, padx=5)

    tk.Label(frame, text="SD API Base:", font=("Arial", 10)).grid(row=3, column=0, sticky="w", pady=8, padx=5)
    ent_sd_base = tk.Entry(frame, width=42, font=("Arial", 10))
    ent_sd_base.insert(0, "https://chat.neuralnote.online/sd")
    ent_sd_base.grid(row=3, column=1, pady=8, padx=5)

    # Path Checkbox
    var_path = tk.BooleanVar(value=True)
    chk_path = tk.Checkbutton(frame, text="Add application to User PATH", variable=var_path, font=("Arial", 10))
    chk_path.grid(row=4, column=0, columnspan=2, sticky="w", pady=(15, 5), padx=5)

    def on_install():
        install_app(
            ent_llm_key.get().strip(),
            ent_serper_key.get().strip(),
            ent_llm_base.get().strip(),
            ent_sd_base.get().strip(),
            var_path.get()
        )

    btn_install = tk.Button(frame, text="Install", command=on_install, width=15, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), relief="raised", bd=2)
    btn_install.grid(row=5, column=0, columnspan=2, pady=20)

    root.mainloop()

if __name__ == "__main__":
    main()
