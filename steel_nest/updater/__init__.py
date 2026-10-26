"""
Updater package for WafraCut Pro
Provides automatic and manual software update checks, background downloads, and seamless self-updating.
"""
from steel_nest.updater.update_manager import (
    UpdateInfo,
    UpdateManager,
    UpdateCheckerThread,
    UpdateDownloaderThread,
    parse_version,
)

__all__ = [
    "UpdateInfo",
    "UpdateManager",
    "UpdateCheckerThread",
    "UpdateDownloaderThread",
    "parse_version",
]
