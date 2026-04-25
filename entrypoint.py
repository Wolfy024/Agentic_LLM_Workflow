import sys
import os
from pathlib import Path

# Add backend to path so we can import orchestrator modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

def main():
    exe_name = Path(sys.executable).name.lower()
    
    # Check if we should run the installer or the main app
    is_installer = False
    
    # If the executable name contains 'setup' or 'install', run the installer
    if "setup" in exe_name or "install" in exe_name:
        is_installer = True
        
    # Also support a --setup or --install flag
    if len(sys.argv) > 1 and sys.argv[1] in ("--setup", "--install"):
        is_installer = True
        # Remove the flag so installer arguments parser doesn't choke
        sys.argv.pop(1)
        
    if is_installer:
        import installer
        installer.main()
    else:
        from backend.main import main as orchestrator_main
        orchestrator_main()

if __name__ == "__main__":
    main()
