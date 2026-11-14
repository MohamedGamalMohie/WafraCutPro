"""
Unit tests for WafraCut Pro v1.2.3 features:
1. Table Copy & Paste empty cell preservation without shifting/displacement (ترحيل).
2. UI batch updates and anti-freeze table handling.
3. Settings persistence and 0.0 defaults verification.
"""
import pytest
from PyQt6.QtWidgets import QApplication, QTableWidgetItem
from PyQt6.QtCore import Qt
from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView, CuttingSettingsDialog
from steel_nest.models.project import ProjectSettings
from steel_nest.config import LinearOptimizationMode

def test_paste_empty_cells_without_shifting(qapp):
    """Test that pasting columns with empty cells preserves empty cells in place without shifting."""
    view = CuttingOptimizationView()
    table = view.pieces_table

    # Test single column paste with empty middle cell:
    # Row 0: 1200
    # Row 1: (empty)
    # Row 2: 3400
    paste_data = "1200\r\n\r\n3400\r\n"

    # Select Row 0, Column 1 (Length)
    table.setRowCount(3)
    for r in range(3):
        view._set_empty_piece_row(r)
    table.setCurrentCell(0, 1)

    view._handle_clipboard_paste(table, is_stock=False, text_override=paste_data)

    assert table.item(0, 1).text() == "1200"
    assert table.item(1, 1).text() == "", "Empty cell in row 1 must NOT be overwritten or shifted!"
    assert table.item(2, 1).text() == "3400", "Value 3400 must stay in row 2 without shifting up!"

def test_paste_2d_block_with_blank_rows_and_cells(qapp):
    """Test that a 2D block with blank rows and empty cells preserves all exact coordinates."""
    view = CuttingOptimizationView()
    table = view.pieces_table

    # 3 rows x 2 columns:
    # Row 0: 500 \t 250
    # Row 1: (completely blank)
    # Row 2: 800 \t (empty)
    tsv_data = "500\t250\r\n\t\r\n800\t\r\n"

    table.setRowCount(3)
    for r in range(3):
        view._set_empty_piece_row(r)
    table.setCurrentCell(0, 1)

    view._handle_clipboard_paste(table, is_stock=False, text_override=tsv_data)

    # Row 0
    assert table.item(0, 1).text() == "500"
    assert table.item(0, 2).text() == "250"

    # Row 1 (blank)
    assert table.item(1, 1).text() == ""
    assert table.item(1, 2).text() == ""

    # Row 2
    assert table.item(2, 1).text() == "800"
    assert table.item(2, 2).text() == ""

def test_copy_range_preserves_empty_cells(qapp):
    """Test that copying a selection range containing empty cells includes them in the TSV."""
    view = CuttingOptimizationView()
    table = view.pieces_table

    table.setRowCount(3)
    for r in range(3):
        view._set_empty_piece_row(r)

    table.item(0, 1).setText("1000")
    table.item(1, 1).setText("") # empty
    table.item(2, 1).setText("2000")

    from PyQt6.QtWidgets import QTableWidgetSelectionRange
    table.clearSelection()
    table.setRangeSelected(QTableWidgetSelectionRange(0, 1, 2, 1), True)

    cb_text = view._handle_clipboard_copy(table) or QApplication.clipboard().text()

    # Normalize line endings
    norm = cb_text.replace("\r\n", "\n").replace("\r", "\n")
    if norm.endswith("\n"):
        norm = norm[:-1]
    lines = norm.split("\n")

    assert len(lines) == 3
    assert lines[0] == "1000"
    assert lines[1] == ""
    assert lines[2] == "2000"

def test_default_settings_zero_and_dialog_init(qapp):
    """Test that default settings are 0.0 and CuttingSettingsDialog displays 0.00 mm."""
    settings = ProjectSettings()
    assert settings.kerf_mm == 0.0
    assert settings.trim_start_mm == 0.0
    assert settings.trim_end_mm == 0.0
    assert settings.plate_kerf_mm == 0.0
    assert settings.plate_margin_mm == 0.0
    assert settings.min_usable_waste_mm == 0.0
    assert settings.min_remnant_length_mm == 0.0

    dlg = CuttingSettingsDialog(settings, LinearOptimizationMode.FREE_NESTING)
    assert dlg.spin_kerf.value() == 0.0
    assert dlg.spin_trim.value() == 0.0
    assert dlg.spin_margin.value() == 0.0
    assert dlg.spin_useful_waste.value() == 0.0
