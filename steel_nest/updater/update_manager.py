"""
WafraCut Pro - Automated Software Update Manager
Handles version manifest checking, background downloading, changelog display,
and in-place self-updating for Windows standalone executables.
"""
import os
import sys
import json
import ssl
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from steel_nest.config import APP_VERSION, APP_NAME

CONFIG_DIR = Path.home() / ".steelnest_pro"
CONFIG_FILE = CONFIG_DIR / "updater_config.json"

DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/MohamedGamalMohie/WafraCutPro/main/version.json"


def parse_version(v_str: str) -> Tuple[int, ...]:
    """Parses version strings like '1.0.0', 'v1.2.3', '2.0-beta' into integer tuples for comparison."""
    clean = v_str.strip().lstrip("vV")
    # Take numeric parts before any hyphen or text suffix
    base = clean.split("-")[0].split("+")[0]
    parts = []
    for p in base.split("."):
        digits = "".join(filter(str.isdigit, p))
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


@dataclass
class UpdateInfo:
    version: str
    release_date: str = ""
    download_url: str = ""
    release_url: str = ""
    changelog_ar: str = ""
    changelog_en: str = ""
    mandatory: bool = False
    file_size_mb: float = 0.0
    sha256: str = ""
    has_update: bool = False

    def is_newer_than(self, current_version: str) -> bool:
        return parse_version(self.version) > parse_version(current_version)


class UpdateCheckerThread(QThread):
    """Asynchronous worker to check for updates without freezing the user interface."""
    update_available = pyqtSignal(object)  # UpdateInfo
    up_to_date = pyqtSignal(str)           # current_version
    check_finished = pyqtSignal(object)    # UpdateInfo
    check_failed = pyqtSignal(str)         # error message

    def __init__(self, manifest_url: str, current_version: str = APP_VERSION, parent=None):
        super().__init__(parent)
        self.manifest_url = manifest_url
        self.current_version = current_version

    def run(self):
        try:
            # Support local file path for testing or offline company network
            if os.path.exists(self.manifest_url):
                with open(self.manifest_url, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                req = urllib.request.Request(
                    self.manifest_url,
                    headers={"User-Agent": f"WafraCutPro-Updater/{self.current_version}"}
                )
                with urllib.request.urlopen(req, timeout=6, context=ctx) as response:
                    raw = response.read().decode("utf-8")
                    data = json.loads(raw)

            latest_v = str(data.get("latest_version", "1.0.0"))
            info = UpdateInfo(
                version=latest_v,
                release_date=data.get("release_date", ""),
                download_url=data.get("download_url", ""),
                changelog_ar=data.get("changelog_ar", ""),
                changelog_en=data.get("changelog_en", ""),
                mandatory=bool(data.get("mandatory", False)),
                file_size_mb=float(data.get("file_size_mb", 0.0)),
                sha256=data.get("sha256", "")
            )

            info.has_update = info.is_newer_than(self.current_version)
            self.check_finished.emit(info)

            if info.has_update:
                self.update_available.emit(info)
            else:
                self.up_to_date.emit(self.current_version)

        except Exception as ex:
            self.check_failed.emit(str(ex))


class UpdateDownloaderThread(QThread):
    """Asynchronous worker to download update executable with live progress feedback."""
    progress_changed = pyqtSignal(int, int, int)  # percent, downloaded_bytes, total_bytes
    download_finished = pyqtSignal(str)           # target_file_path
    download_failed = pyqtSignal(str)             # error message

    def __init__(self, download_url: str, target_path: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.target_path = target_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            target_dir = os.path.dirname(self.target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": f"WafraCutPro-Downloader/{APP_VERSION}"}
            )

            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB

                with open(self.target_path, "wb") as f_out:
                    while True:
                        if self._is_cancelled:
                            return
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)
                        pct = int((downloaded / total_size) * 100) if total_size > 0 else 0
                        self.progress_changed.emit(pct, downloaded, total_size)

            if not self._is_cancelled:
                self.download_finished.emit(self.target_path)

        except Exception as ex:
            self.download_failed.emit(str(ex))


class UpdateManager(QObject):
    """Facade for managing application update settings and operations."""
    update_detected = pyqtSignal(object)  # UpdateInfo

    def __init__(self, current_version: str = APP_VERSION, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.config = self._load_config()
        self.cached_latest_info: Optional[UpdateInfo] = None
        self.checker_thread: Optional[UpdateCheckerThread] = None
        self.downloader_thread: Optional[UpdateDownloaderThread] = None

    def _load_config(self) -> dict:
        default_cfg = {
            "auto_check_on_startup": True,
            "manifest_url": DEFAULT_MANIFEST_URL,
            "last_check_timestamp": "",
            "skipped_versions": []
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    default_cfg.update(cfg)
            except Exception:
                pass
        return default_cfg

    def save_config(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    @property
    def auto_check(self) -> bool:
        return self.config.get("auto_check_on_startup", True)

    @auto_check.setter
    def auto_check(self, val: bool):
        self.config["auto_check_on_startup"] = bool(val)
        self.save_config()

    @property
    def manifest_url(self) -> str:
        return self.config.get("manifest_url", DEFAULT_MANIFEST_URL)

    @manifest_url.setter
    def manifest_url(self, val: str):
        self.config["manifest_url"] = str(val).strip()
        self.save_config()

    def set_auto_check(self, val: bool):
        self.auto_check = val

    def set_custom_manifest_url(self, val: str):
        self.manifest_url = val

    def check_for_updates_async(self):
        """Starts background checking thread."""
        if self.checker_thread and self.checker_thread.isRunning():
            return
        self.checker_thread = UpdateCheckerThread(
            manifest_url=self.manifest_url,
            current_version=self.current_version,
            parent=self
        )
        self.checker_thread.update_available.connect(self._on_update_found)
        self.checker_thread.start()

    def _on_update_found(self, info: UpdateInfo):
        self.cached_latest_info = info
        self.update_detected.emit(info)

    @staticmethod
    def apply_update_and_restart(new_file_path: str):
        """
        Creates a detached Windows batch script that waits for current process PID
        to terminate, replaces the running executable, and launches the updated version.
        """
        current_exe = sys.executable
        if not getattr(sys, "frozen", False):
            # Running in dev mode (.py), simply inform
            print(f"Dev mode update downloaded to: {new_file_path}")
            return

        pid = os.getpid()
        bat_path = Path(os.environ.get("TEMP", ".")) / f"wafracut_update_{pid}.bat"

        app_dir = os.path.dirname(current_exe)
        is_zip = str(new_file_path).lower().endswith(".zip")
        if is_zip:
            replace_cmd = f'tar -xf "{new_file_path}" -C "{app_dir}" >nul 2>&1 || powershell -command "Expand-Archive -Force \'{new_file_path}\' \'{app_dir}\'"'
        else:
            replace_cmd = f'copy /Y "{new_file_path}" "{current_exe}" >nul'

        # Batch script that loops until old PID dies, then replaces and starts exe
        bat_script = f"""@echo off
setlocal
echo Updating WafraCut Pro...
:wait_loop
tasklist /FI "PID eq {pid}" | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

{replace_cmd}
if errorlevel 1 (
    echo Update failed to overwrite executable.
    pause
    exit /b 1
)

start "" "{current_exe}"
del "{new_file_path}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
        with open(bat_path, "w", encoding="ansi") as f:
            f.write(bat_script)

        # Launch detached updater script and terminate current process
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)],
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
            close_fds=True
        )
        sys.exit(0)
