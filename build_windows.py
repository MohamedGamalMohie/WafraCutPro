"""
WafraCut Pro - Windows PyInstaller Packaging Script
Builds a standalone Windows executable with full OR-Tools binary support.
"""
import os
import sys
import shutil
from pathlib import Path

def build():
    root_dir = Path(__file__).resolve().parent
    main_script = root_dir / "main.py"
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"

    print("=" * 60)
    print("WafraCut Pro — Windows Standalone Executable Packaging")
    print("=" * 60)

    # Safely clear read-only flags from prior desktop.ini/dist
    import stat
    def remove_readonly(func, p, excinfo):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    for d in [dist_dir, build_dir]:
        if d.exists():
            for root, dirs, files in os.walk(d):
                for f in files:
                    try:
                        os.chmod(os.path.join(root, f), stat.S_IWRITE)
                    except Exception:
                        pass
            try:
                shutil.rmtree(d, onerror=remove_readonly)
            except Exception:
                pass

    # Locate ortools .libs directory if present
    import ortools
    ortools_path = Path(ortools.__file__).parent
    ortools_libs = ortools_path / ".libs"

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=WafraCutPro",
        "--noconfirm",
        "--clean",
        "--windowed",                 # Desktop GUI without console
        "--onedir",                   # Folder containing exe and dependencies
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        "--icon=resources/icon.ico",
        "--add-data=resources;resources",
        "--add-data=sample_data;sample_data",
        "--collect-all=ortools",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtPrintSupport",
        "--hidden-import=openpyxl",
        "--hidden-import=xlsxwriter",
    ]

    # Explicitly add ortools dlls to root and ortools/.libs
    if ortools_libs.exists():
        for dll in ortools_libs.glob("*.dll"):
            cmd.append(f"--add-binary={dll};.")
            cmd.append(f"--add-binary={dll};ortools/.libs")

    cmd.append(str(main_script))

    print("Executing PyInstaller command:\n" + " ".join(cmd))
    import subprocess
    result = subprocess.run(cmd, cwd=str(root_dir))

    if result.returncode == 0:
        exe_dir = dist_dir / "WafraCutPro"
        exe_path = exe_dir / "WafraCutPro.exe"

        # Copy any missing ortools .libs DLLs directly to output folder as safeguard
        if ortools_libs.exists():
            for dll in ortools_libs.glob("*.dll"):
                dest = exe_dir / dll.name
                if not dest.exists():
                    shutil.copy2(dll, dest)
                dest_sub = exe_dir / "ortools" / ".libs" / dll.name
                dest_sub.parent.mkdir(parents=True, exist_ok=True)
                if not dest_sub.exists():
                    shutil.copy2(dll, dest_sub)

        # Copy resources folder
        res_dest = exe_dir / "resources"
        if (root_dir / "resources").exists():
            shutil.copytree(root_dir / "resources", res_dest, dirs_exist_ok=True)

        # Setup shortcuts and folder icons
        try:
            from create_shortcuts import setup_shortcuts_and_folder_icon
            setup_shortcuts_and_folder_icon()
        except Exception as e:
            print("Notice: shortcut setup skipped:", e)

        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Executable generated at: {exe_path}")
        print("=" * 60)
    else:
        print("\nPackaging failed with exit code:", result.returncode)

if __name__ == "__main__":
    build()
