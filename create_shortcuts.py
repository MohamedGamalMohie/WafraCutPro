"""
Create Desktop & Project Root Shortcuts with Custom Icon
and configure desktop.ini for the dist/WafraCutPro folder.
"""
import os
import sys
import ctypes
import subprocess
from pathlib import Path

def setup_shortcuts_and_folder_icon():
    root_dir = Path(__file__).resolve().parent
    icon_path = root_dir / "resources" / "icon.ico"
    exe_path = root_dir / "dist" / "WafraCutPro" / "WafraCutPro.exe"
    dist_folder = root_dir / "dist" / "WafraCutPro"

    print("Configuring icons and shortcuts...")

    # 1. Configure folder icon for dist/WafraCutPro
    if dist_folder.exists() and icon_path.exists():
        ini_path = dist_folder / "desktop.ini"
        os.system(f'attrib -h -s "{ini_path}" 2>nul')
        with open(ini_path, "w", encoding="ansi") as f:
            f.write("[.ShellClassInfo]\n")
            f.write(f"IconResource={icon_path},0\n")
            f.write("[ViewState]\nMode=\nVid=\nFolderType=Generic\n")
        os.system(f'attrib +h +s "{ini_path}"')
        os.system(f'attrib +r "{dist_folder}"')
        print(f"Folder icon configured for: {dist_folder}")

    # 2. Configure folder icon for root_dir as well
    root_ini = root_dir / "desktop.ini"
    os.system(f'attrib -h -s "{root_ini}" 2>nul')
    with open(root_ini, "w", encoding="ansi") as f:
        f.write("[.ShellClassInfo]\n")
        f.write(f"IconResource={icon_path},0\n")
        f.write("[ViewState]\nMode=\nVid=\nFolderType=Generic\n")
    os.system(f'attrib +h +s "{root_ini}"')
    os.system(f'attrib +r "{root_dir}"')

    # 3. Create Windows Shortcuts via PowerShell
    desktop_dir = Path(os.environ.get("USERPROFILE", "C:/Users/Mohamed")) / "Desktop"
    
    # Remove any old SteelNest shortcuts if still on desktop
    old_desktop_sc = desktop_dir / "SteelNest Pro.lnk"
    if old_desktop_sc.exists():
        try:
            old_desktop_sc.unlink()
        except Exception:
            pass

    shortcuts = [
        (root_dir / "WafraCut Pro.lnk", "Root Shortcut"),
        (desktop_dir / "WafraCut Pro.lnk", "Desktop Shortcut")
    ]

    ps_code = "$WshShell = New-Object -comObject WScript.Shell\n"
    for sc_path, name in shortcuts:
        s_clean = str(sc_path).replace("\\", "\\\\")
        e_clean = str(exe_path).replace("\\", "\\\\")
        d_clean = str(dist_folder).replace("\\", "\\\\")
        i_clean = str(icon_path).replace("\\", "\\\\")
        ps_code += f"""
if (Test-Path "{s_clean}") {{
    Remove-Item "{s_clean}" -Force -ErrorAction SilentlyContinue
}}
$sc = $WshShell.CreateShortcut("{s_clean}")
$sc.TargetPath = "{e_clean}"
$sc.WorkingDirectory = "{d_clean}"
$sc.IconLocation = "{e_clean},0"
$sc.Description = "WafraCut Pro - Advanced Cutting Optimization"
$sc.Save()
Write-Host "Created {name} at: {s_clean}"
"""
    ps_file = root_dir / "make_sc.ps1"
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_code)

    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)], capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("PowerShell warning/error:", res.stderr)

    if ps_file.exists():
        ps_file.unlink()

    # 4. Notify Windows Shell to instantly refresh icon cache
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0)
        subprocess.run(["powershell", "-Command", "ie4uinit.exe -show"], capture_output=True)
    except Exception:
        pass

    print("Shortcuts setup complete and icon cache refreshed!")

if __name__ == "__main__":
    setup_shortcuts_and_folder_icon()
