"""
Application Entry Point for WafraCut Pro
"""
import sys
import os
import gc
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from steel_nest.ui.main_window import MainWindow
from steel_nest.ui.themes import LIGHT_THEME_QSS, DARK_THEME_QSS
from steel_nest.config import APP_NAME

def setup_crash_protection():
    """Catches any unhandled exceptions to prevent the application from abruptly closing."""
    def excepthook_handler(exctype, value, tb):
        import traceback
        err_msg = "".join(traceback.format_exception(exctype, value, tb))
        print("EXCEPTION CAUGHT:", err_msg, file=sys.stderr)
        try:
            log_dir = Path.home() / ".steelnest_pro"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "error.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now()} ---\n{err_msg}\n")
        except Exception:
            pass

        app = QApplication.instance()
        if app:
            try:
                QMessageBox.warning(
                    None,
                    "WafraCut Pro Notice",
                    f"A handled error occurred:\n{value}\n\nThe application will safely continue."
                )
            except Exception:
                pass

    sys.excepthook = excepthook_handler

def trim_memory():
    """Forces garbage collection and releases dormant working set pages back to Windows OS."""
    gc.collect()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass

def run_app():
    setup_crash_protection()

    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    # Fix taskbar icon grouping in Windows
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WafraCutPro.OptimizationApp.v1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(LIGHT_THEME_QSS)

    # Set Window / Taskbar Icon
    icon_paths = [
        Path(__file__).resolve().parent.parent / "resources" / "icon.png",
        Path(__file__).resolve().parent.parent / "resources" / "icon.ico",
        Path(sys.executable).parent / "resources" / "icon.png",
        Path(sys.executable).parent / "resources" / "icon.ico",
    ]
    for ip in icon_paths:
        if ip.exists():
            from PyQt6.QtGui import QIcon
            app.setWindowIcon(QIcon(str(ip)))
            break

    window = MainWindow()
    window.show()

    # Initial memory trim
    trim_memory()

    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
