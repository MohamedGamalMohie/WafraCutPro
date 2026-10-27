import os
import json
import pytest
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView
from steel_nest.models.part import PartCutItem
from steel_nest.models.stock import StockItem
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.config import LinearOptimizationMode

def test_v120_toolbar_fit_expand_removed(qapp):
    """Verify Fit and Expand buttons are removed from Pieces and Stock toolbars."""
    view = CuttingOptimizationView()
    p_buttons = [b.text() for b in view.findChildren(type(view.btn_start)) if b.text()]
    assert not any("Fit" in t and "Zoom" not in t and "Expand" not in t for t in p_buttons)

def test_v120_results_tabs_initially_hidden(qapp):
    """Verify Results tabs and controls are hidden before optimization runs."""
    view = CuttingOptimizationView()
    assert view.res_tabs.isHidden()
    assert view.ctrl_frame.isHidden()
    assert view.pattern_tabs.isHidden()
    assert view.right_status_frame.isHidden()

    # Simulate optimization done
    stock = [StockItem(id="S1", designation="IPE 300", grade="S235JR", length_mm=6000.0, available_qty=5)]
    parts = [PartCutItem(id="P1", mark="P1", designation="IPE 300", grade="S235JR", length_mm=1500.0, quantity=4)]
    res = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING).optimize(parts, stock)
    view._on_optimization_done(res)

    # Now results tabs should be revealed
    assert not view.res_tabs.isHidden()
    assert not view.ctrl_frame.isHidden()
    assert not view.right_status_frame.isHidden()
    assert view.res_tabs.currentIndex() == 1 # 1D linear result

def test_v120_project_save_as_and_open(qapp, tmp_path, monkeypatch):
    """Verify full project save (.wcp) and open functionality."""
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    view = CuttingOptimizationView()
    view.pieces_table.setRowCount(2)
    view._set_piece_row(0, 5400, 0, 4, "IPE 300", False, "B-101")
    view._set_piece_row(1, 600, 400, 8, "PL 12mm", True, "BP-1")

    view.stock_table.setRowCount(1)
    view._set_stock_row(0, 12000, 0, 15, "HEA 200", "STK-1", 50.0)

    save_file = str(tmp_path / "test_project.wcp")
    view.save_project_as_file(save_file)
    assert os.path.exists(save_file)

    # Verify JSON content
    with open(save_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["format"] == "WafraCutPro_Project"
    assert len(data["pieces"]) == 2
    assert len(data["stock"]) == 1
    assert data["pieces"][0]["length"] == "5400"
    assert data["stock"][0]["material"] == "HEA 200"

    # Reset and reload
    view.pieces_table.setRowCount(0)
    view.stock_table.setRowCount(0)
    view.open_project_from_file(save_file)
    assert view.pieces_table.rowCount() == 2
    assert view.stock_table.rowCount() == 1
    assert view.pieces_table.item(0, 1).text() == "5400"
    assert view.stock_table.item(0, 4).text() == "HEA 200"

def test_v120_stock_persistence_and_pieces_empty(qapp):
    """Verify stock is remembered across sessions and pieces table starts empty."""
    view = CuttingOptimizationView()
    # Pieces starts empty
    assert view.pieces_table.rowCount() == 0
    # Stock has items
    assert view.stock_table.rowCount() > 0

    # Edit stock and save
    view.stock_table.setRowCount(1)
    view._set_stock_row(0, 9999, 0, 99, "TEST_MAT", "TEST_LBL", 0.0)
    view._save_last_stock()

    # Recreate view
    view2 = CuttingOptimizationView()
    assert view2.pieces_table.rowCount() == 0
    assert view2.stock_table.rowCount() == 1
    assert view2.stock_table.item(0, 1).text() == "9999"
    assert view2.stock_table.item(0, 4).text() == "TEST_MAT"
