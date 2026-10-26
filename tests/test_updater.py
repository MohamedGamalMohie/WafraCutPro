"""
Tests for WafraCut Pro Updater Subsystem.
Verifies version parsing, manifest handling, UI widget state, and notifications.
"""
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

from steel_nest.updater.update_manager import (
    UpdateManager, UpdateInfo, parse_version
)
from steel_nest.ui.widgets.update_dialog import UpdateCenterWidget, UpdateDialog
from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView


def test_version_parsing_and_comparison():
    assert parse_version("1.0.0") < parse_version("1.1.0")
    assert parse_version("1.0.9") < parse_version("1.1.0")
    assert parse_version("1.2.0") > parse_version("1.1.99")
    assert parse_version("2.0.0") > parse_version("1.9.9")
    assert parse_version("v1.0.0") == (1, 0, 0)
    assert parse_version("1.0") == (1, 0, 0)


def test_update_info_detection():
    info_old = UpdateInfo(
        version="1.0.0",
        release_date="2026-10-26",
        download_url="https://example.com/WafraCutPro.exe",
        has_update=False
    )
    assert not info_old.has_update

    info_new = UpdateInfo(
        version="1.1.0",
        release_date="2026-10-26",
        download_url="https://example.com/WafraCutPro.exe",
        changelog_ar="إضافة ميزات متطورة",
        has_update=True
    )
    assert info_new.has_update
    assert "متطورة" in info_new.changelog_ar


def test_update_manager_configuration(tmp_path, monkeypatch):
    test_cfg_file = tmp_path / "test_updater_config.json"
    monkeypatch.setattr("steel_nest.updater.update_manager.CONFIG_FILE", test_cfg_file)
    monkeypatch.setattr("steel_nest.updater.update_manager.CONFIG_DIR", tmp_path)

    mgr = UpdateManager(current_version="1.0.0")
    assert mgr.auto_check is True
    mgr.set_auto_check(False)
    assert mgr.auto_check is False

    # Check persistence
    mgr2 = UpdateManager(current_version="1.0.0")
    assert mgr2.auto_check is False

    mgr.set_custom_manifest_url("https://my-server.com/version.json")
    assert mgr.manifest_url == "https://my-server.com/version.json"


def test_update_center_widget_ui(qapp):
    mgr = UpdateManager(current_version="1.0.0")
    info = UpdateInfo(
        version="1.1.0",
        release_date="2026-10-26",
        download_url="https://github.com/WafraCut/releases/download/v1.1.0/WafraCutPro.exe",
        changelog_ar="• إضافة نظام التحديث التلقائي\n• تحسين استهلاك الذاكرة",
        changelog_en="• Auto-updater added\n• RAM optimization",
        has_update=True,
        file_size_mb=45.2
    )
    widget = UpdateCenterWidget(update_manager=mgr, preloaded_info=info)
    assert widget.btn_install.isEnabled()
    assert "v1.1.0" in widget.card_latest.findChild(type(widget.lbl_progress_status), "val").text()
    assert "التحديث التلقائي" in widget.txt_changelog.toPlainText() or "التحديث التلقائي" in widget.txt_changelog.toHtml()


def test_cutting_view_update_tab_integration(qapp):
    view = CuttingOptimizationView()
    # Check that the 4th tab is Update
    assert view.res_tabs.count() == 4
    assert "Update" in view.res_tabs.tabText(3)

    # Switch to update tab
    view.res_tabs.setCurrentIndex(3)
    assert view.right_stack.currentIndex() == 3

    # Simulate update notification signal
    info = UpdateInfo(version="1.2.0", download_url="http://x.com", has_update=True)
    view._on_update_detected_in_view(info)
    assert "v1.2.0" in view.res_tabs.tabText(3)
