"""
SteelNest Pro - Windows Launcher
"""
import sys
import os
from pathlib import Path

# Fix Windows DLL search path for PyInstaller frozen app (OR-Tools, C++ runtime DLLs)
if getattr(sys, 'frozen', False):
    app_dir = Path(sys.executable).resolve().parent
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(str(app_dir))
        except Exception:
            pass
        ortools_libs = app_dir / "ortools" / ".libs"
        if ortools_libs.exists():
            try:
                os.add_dll_directory(str(ortools_libs))
            except Exception:
                pass
    os.environ["PATH"] = str(app_dir) + os.pathsep + os.environ.get("PATH", "")

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from steel_nest.app import run_app

if __name__ == "__main__":
    run_app()
