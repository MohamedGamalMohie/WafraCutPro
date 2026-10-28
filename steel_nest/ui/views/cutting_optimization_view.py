"""
Cutting Optimization Pro View for SteelNest Pro
Faithfully replicates the dual-pane workflow and classic desktop interface of Cutting Optimization Pro:
- Left Pane: Pieces Table (Top) & Stock Table (Bottom) with full toolbar actions.
- Right Pane: Big Green Start Button, Results (2D), Results (1D), Statistics, Pattern Tabs (#1, #2...),
  Interactive Diagram with dimensions, green cut lines, and hatched offcuts.
"""
import sys
import os
import re
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from collections import defaultdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame, QCheckBox, QComboBox,
    QTabWidget, QTabBar, QMessageBox, QFileDialog, QDialog, QFormLayout,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QScrollArea, QMenu, QToolButton,
    QStackedWidget, QSlider, QApplication, QGroupBox, QAbstractItemView,
    QLineEdit, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QPainter, QKeySequence, QShortcut, QCursor
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem, RemnantItem
from steel_nest.models.project import Project, ProjectSettings
from steel_nest.config import LinearOptimizationMode, NestingObjective, MaterialType, RemnantStatus, APP_VERSION
from steel_nest.database.repositories import CutListRepository, StockRepository, ProjectRepository, RemnantRepository
from steel_nest.reporting.excel_importer import ExcelDataImporter
from steel_nest.reporting.template_generator import TemplateGenerator
from steel_nest.reporting.excel_exporter import ExcelReportExporter
from steel_nest.reporting.dxf_exporter import DXFExporter
from steel_nest.core.fractional_parser import parse_fractional_value, format_fractional_display
from steel_nest.ui.icon_manager import IconManager
from steel_nest.ui.widgets.cutting_canvas import CuttingCanvas
from steel_nest.ui.widgets.statistics_dashboard import StatisticsDashboard, TabularCutDialog, StickersDialog
from steel_nest.ui.widgets.product_generator_dialog import ProductGeneratorDialog
from steel_nest.ui.widgets.multi_layout_printer import (
    MultiLayoutPrintDialog, BatchImageExportDialog, CNCCutSequenceDialog, CuttingPrintPdfDialog
)
from steel_nest.ui.i18n import t, set_current_language, get_current_language, SUPPORTED_LANGUAGES
from steel_nest.ui.workers.optimization_worker import OptimizationWorker
from steel_nest.models.nesting_plan import OptimizationResult
from steel_nest.updater.update_manager import UpdateManager, UpdateInfo
from steel_nest.ui.widgets.update_dialog import UpdateCenterWidget

class CuttingSettingsDialog(QDialog):
    """
    Cutting Rules, Guillotine, Nesting Modes, and Optimization Settings Dialog.
    Fully replicates and extends Cutting Optimization Pro settings.
    """
    def __init__(self, settings: ProjectSettings, current_mode: LinearOptimizationMode, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.resize(560, 480)
        self.settings = settings
        self.selected_mode = current_mode

        main_vbox = QVBoxLayout(self)
        main_vbox.setSpacing(10)

        # Tabbed settings for clean organization
        self.tabs = QTabWidget()
        main_vbox.addWidget(self.tabs)

        # --- TAB 1: General & Blade Kerf ---
        tab_general = QWidget()
        f_gen = QFormLayout(tab_general)
        f_gen.setSpacing(10)

        self.spin_kerf = QDoubleSpinBox()
        self.spin_kerf.setRange(0.0, 50.0)
        self.spin_kerf.setSingleStep(0.5)
        self.spin_kerf.setValue(settings.kerf_mm)
        self.spin_kerf.setSuffix(" mm")
        f_gen.addRow(t("kerf_thickness"), self.spin_kerf)

        self.spin_trim = QDoubleSpinBox()
        self.spin_trim.setRange(0.0, 200.0)
        self.spin_trim.setValue(settings.trim_start_mm)
        self.spin_trim.setSuffix(" mm")
        f_gen.addRow(t("end_trimming"), self.spin_trim)

        self.spin_margin = QDoubleSpinBox()
        self.spin_margin.setRange(0.0, 100.0)
        self.spin_margin.setValue(settings.plate_margin_mm)
        self.spin_margin.setSuffix(" mm")
        f_gen.addRow(t("plate_margin"), self.spin_margin)

        self.spin_useful_waste = QDoubleSpinBox()
        self.spin_useful_waste.setRange(0.0, 10000.0)
        self.spin_useful_waste.setValue(getattr(settings, "min_usable_waste_mm", 100.0))
        self.spin_useful_waste.setSuffix(" mm")
        f_gen.addRow(t("useful_waste"), self.spin_useful_waste)

        self.combo_unit = QComboBox()
        self.combo_unit.addItems(["General / Unitless (عام)", "Millimeters (مم)", "Inches (بوصة)"])
        f_gen.addRow(t("metric_unit"), self.combo_unit)

        self.chk_group_layouts = QCheckBox(t("group_layouts"))
        self.chk_group_layouts.setChecked(getattr(settings, "group_identical_layouts", True))
        f_gen.addRow("", self.chk_group_layouts)

        self.tabs.addTab(tab_general, "General & Kerf")

        # --- TAB 2: 2D Cutting Engine (Guillotine vs Nested) ---
        tab_2d = QWidget()
        l_2d = QVBoxLayout(tab_2d)
        l_2d.setSpacing(8)

        # Cut Type Selection
        grp_cut_type = QGroupBox("Cutting Technology / نوع الماكينة")
        v_ct = QVBoxLayout(grp_cut_type)
        self.rb_nested = QRadioButton(f"{t('nested_opt')} (Laser, Plasma, Waterjet, Flame)")
        self.rb_guillotine = QRadioButton(f"{t('guillotine_opt')} (Shears, Glass, Wood Panel Saws)")
        if getattr(settings, "guillotine_cuts_only", False):
            self.rb_guillotine.setChecked(True)
        else:
            self.rb_nested.setChecked(True)
        v_ct.addWidget(self.rb_nested)
        v_ct.addWidget(self.rb_guillotine)
        l_2d.addWidget(grp_cut_type)

        f_2d = QFormLayout()
        f_2d.setSpacing(8)

        # First cut direction
        self.combo_first_cut = QComboBox()
        self.combo_first_cut.addItems(["AUTO", "HORIZONTAL", "VERTICAL"])
        curr_fc = getattr(settings, "guillotine_first_cut", "AUTO")
        idx_fc = self.combo_first_cut.findText(curr_fc)
        if idx_fc >= 0:
            self.combo_first_cut.setCurrentIndex(idx_fc)
        f_2d.addRow(t("first_cut_dir"), self.combo_first_cut)

        # Stages
        self.combo_stages = QComboBox()
        self.combo_stages.addItems(["2-Stage Guillotine", "3-Stage Guillotine", "4-Stage / Multi-Stage"])
        curr_stg = getattr(settings, "guillotine_stages", 2)
        if curr_stg == 3:
            self.combo_stages.setCurrentIndex(1)
        elif curr_stg >= 4:
            self.combo_stages.setCurrentIndex(2)
        else:
            self.combo_stages.setCurrentIndex(0)
        f_2d.addRow(t("multi_stage"), self.combo_stages)

        # Optimization level slider (1 to 10)
        h_opt = QHBoxLayout()
        self.slider_opt = QSlider(Qt.Orientation.Horizontal)
        self.slider_opt.setRange(1, 10)
        curr_lvl = getattr(settings, "optimization_level", 5)
        self.slider_opt.setValue(curr_lvl)
        self.lbl_opt_val = QLabel(f"Level {curr_lvl}")
        self.slider_opt.valueChanged.connect(lambda v: self.lbl_opt_val.setText(f"Level {v}"))
        h_opt.addWidget(self.slider_opt)
        h_opt.addWidget(self.lbl_opt_val)
        f_2d.addRow(t("optimization_level"), h_opt)

        # Max Cut Length Limit
        self.spin_max_cut = QDoubleSpinBox()
        self.spin_max_cut.setRange(0.0, 50000.0)
        self.spin_max_cut.setValue(getattr(settings, "max_cut_length_mm", 0.0))
        self.spin_max_cut.setSuffix(" mm (0 = no limit)")
        f_2d.addRow(t("max_cut_length"), self.spin_max_cut)

        # Breakable parts limit
        self.spin_breakable = QDoubleSpinBox()
        self.spin_breakable.setRange(0.0, 1000.0)
        self.spin_breakable.setValue(getattr(settings, "min_breakable_waste_mm", 0.0))
        self.spin_breakable.setSuffix(" mm")
        f_2d.addRow(t("breakable_limit"), self.spin_breakable)

        l_2d.addLayout(f_2d)
        self.tabs.addTab(tab_2d, "2D Engine & Guillotine")

        # --- TAB 3: 1D Modes & Language ---
        tab_1d = QWidget()
        l_1d = QVBoxLayout(tab_1d)
        l_1d.setSpacing(10)

        lbl_1d = QLabel("1D Bar Nesting Mode (طريقة تقطيع الأعواد والمقاطع):")
        lbl_1d.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        l_1d.addWidget(lbl_1d)

        self.mode_group = QButtonGroup(self)
        self.rb_free = QRadioButton("Mode 1: Free Nesting — Minimum Scrap (أقل هالك دمج حر)")
        self.rb_single = QRadioButton("Mode 2: Single Cut Length per Bar (قطعية واحدة بالعود 400, 400...)")
        self.rb_double = QRadioButton("Mode 3: Double Cut Lengths per Bar (قطعيتين كحد أقصى بالعود)")

        self.mode_group.addButton(self.rb_free, 1)
        self.mode_group.addButton(self.rb_single, 2)
        self.mode_group.addButton(self.rb_double, 3)

        if current_mode == LinearOptimizationMode.SINGLE_CUT:
            self.rb_single.setChecked(True)
        elif current_mode == LinearOptimizationMode.DOUBLE_CUT:
            self.rb_double.setChecked(True)
        else:
            self.rb_free.setChecked(True)

        l_1d.addWidget(self.rb_free)
        l_1d.addWidget(self.rb_single)
        l_1d.addWidget(self.rb_double)
        l_1d.addSpacing(10)

        # Language Selection
        f_lang = QFormLayout()
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["العربية (Arabic)", "English", "Français (French)"])
        cur_lang = get_current_language()
        if cur_lang == "EN":
            self.combo_lang.setCurrentIndex(1)
        elif cur_lang == "FR":
            self.combo_lang.setCurrentIndex(2)
        else:
            self.combo_lang.setCurrentIndex(0)
        f_lang.addRow("Interface Language (اللغة):", self.combo_lang)
        l_1d.addLayout(f_lang)

        l_1d.addStretch()
        self.tabs.addTab(tab_1d, "1D Modes & Language")

        # Dialog Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.setIcon(IconManager.get_icon("accept", 16))
        btn_ok.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 18px; border-radius: 4px;")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        main_vbox.addLayout(btns)

    def get_values(self):
        mode = LinearOptimizationMode.FREE_NESTING
        if self.rb_single.isChecked():
            mode = LinearOptimizationMode.SINGLE_CUT
        elif self.rb_double.isChecked():
            mode = LinearOptimizationMode.DOUBLE_CUT

        stg_idx = self.combo_stages.currentIndex()
        stages = 2 if stg_idx == 0 else (3 if stg_idx == 1 else 4)

        lang_idx = self.combo_lang.currentIndex()
        lang_code = "AR" if lang_idx == 0 else ("EN" if lang_idx == 1 else "FR")

        return {
            "kerf": self.spin_kerf.value(),
            "trim": self.spin_trim.value(),
            "margin": self.spin_margin.value(),
            "useful_waste": self.spin_useful_waste.value(),
            "guillotine_cuts_only": self.rb_guillotine.isChecked(),
            "guillotine_first_cut": self.combo_first_cut.currentText(),
            "guillotine_stages": stages,
            "optimization_level": self.slider_opt.value(),
            "max_cut_length": self.spin_max_cut.value(),
            "breakable_limit": self.spin_breakable.value(),
            "group_identical": self.chk_group_layouts.isChecked(),
            "mode": mode,
            "language": lang_code
        }

class CuttingOptimizationView(QWidget):
    optimization_finished = pyqtSignal(object)

    def __init__(
        self,
        cut_repo: Optional[CutListRepository] = None,
        stock_repo: Optional[StockRepository] = None,
        project_repo: Optional[ProjectRepository] = None,
        remnant_repo: Optional[RemnantRepository] = None,
        parent=None
    ):
        super().__init__(parent)
        from steel_nest.database.db_manager import DatabaseManager
        db = DatabaseManager()
        self.cut_repo = cut_repo or CutListRepository(db)
        self.stock_repo = stock_repo or StockRepository(db)
        self.project_repo = project_repo or ProjectRepository(db)
        self.remnant_repo = remnant_repo or RemnantRepository(db)

        self.active_project_id: Optional[str] = None
        self.current_project_file: Optional[str] = None
        self.current_result: Optional[OptimizationResult] = None
        self.worker: Optional[OptimizationWorker] = None

        # Settings defaults
        self.settings = ProjectSettings()
        self.linear_mode = LinearOptimizationMode.FREE_NESTING

        self.update_manager = getattr(parent, 'update_manager', None) or UpdateManager(parent=self)
        self.update_manager.update_detected.connect(self._on_update_detected_in_view)

        self._init_ui()
        self._load_last_stock()
        self.pieces_table.setRowCount(0)
        self.stock_table.itemChanged.connect(self._on_stock_table_changed)

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # Central Horizontal Splitter dividing Left (Inputs) and Right (Results & Drawing)
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.h_splitter.setHandleWidth(8)
        self.h_splitter.setChildrenCollapsible(False)
        self.h_splitter.setOpaqueResize(True)
        self.h_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background-color: #CBD5E1;
                border-left: 1px solid #94A3B8;
                border-right: 1px solid #94A3B8;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #2563EB;
            }
        """)

        # -------------------------------------------------------------
        # 1. LEFT PANE: PIECES & STOCK (Vertical Splitter)
        # -------------------------------------------------------------
        left_container = QWidget()
        left_container.setMinimumWidth(320)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.setHandleWidth(5)

        # --- TOP SECTION: PIECES ---
        pieces_widget = QWidget()
        pw_layout = QVBoxLayout(pieces_widget)
        pw_layout.setContentsMargins(4, 4, 4, 4)
        pw_layout.setSpacing(4)

        # PIECES Toolbar - 2 Organized Rows for Clear & Readable Labels
        p_toolbar_1 = QHBoxLayout()
        p_toolbar_1.setSpacing(4)

        lbl_pieces_badge = QLabel(" PIECES ")
        lbl_pieces_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_pieces_badge.setStyleSheet("background-color: #2563EB; color: white; padding: 3px 6px; border-radius: 3px;")
        p_toolbar_1.addWidget(lbl_pieces_badge)

        btn_style_compact = "QPushButton { padding: 4px 6px; font-size: 11px; }"

        btn_p_append = QPushButton("+ Append")
        btn_p_append.setStyleSheet(btn_style_compact)
        btn_p_append.setIcon(IconManager.get_icon("append", 14))
        btn_p_append.setToolTip("Add new required piece row")
        btn_p_append.clicked.connect(self._add_piece_row)
        p_toolbar_1.addWidget(btn_p_append)

        btn_p_delete = QPushButton("Delete")
        btn_p_delete.setStyleSheet(btn_style_compact)
        btn_p_delete.setIcon(IconManager.get_icon("delete", 14))
        btn_p_delete.setToolTip("Delete selected piece row")
        btn_p_delete.clicked.connect(self._delete_piece_row)
        p_toolbar_1.addWidget(btn_p_delete)

        btn_p_clear = QPushButton("Clear")
        btn_p_clear.setStyleSheet(btn_style_compact)
        btn_p_clear.setIcon(IconManager.get_icon("clear", 14))
        btn_p_clear.setToolTip("Clear all pieces")
        btn_p_clear.clicked.connect(self._clear_pieces)
        p_toolbar_1.addWidget(btn_p_clear)

        btn_p_sort = QPushButton("Sort")
        btn_p_sort.setStyleSheet(btn_style_compact)
        btn_p_sort.setIcon(IconManager.get_icon("sort", 14))
        btn_p_sort.setToolTip("Sort pieces by length, width, quantity, or material")
        btn_p_sort.clicked.connect(self._sort_pieces)
        p_toolbar_1.addWidget(btn_p_sort)
        p_toolbar_1.addStretch()
        pw_layout.addLayout(p_toolbar_1)

        # Row 2: Secondary actions (Paste, Import, Open, Save, More)
        p_toolbar_2 = QHBoxLayout()
        p_toolbar_2.setSpacing(4)

        btn_p_paste = QPushButton("Paste")
        btn_p_paste.setStyleSheet(btn_style_compact)
        btn_p_paste.setIcon(IconManager.get_icon("paste", 14))
        btn_p_paste.setToolTip("Paste copied table columns from Excel (Ctrl+V)")
        btn_p_paste.clicked.connect(lambda: self._handle_clipboard_paste(self.pieces_table, is_stock=False))
        p_toolbar_2.addWidget(btn_p_paste)

        btn_p_import = QPushButton("Import")
        btn_p_import.setStyleSheet(btn_style_compact)
        btn_p_import.setIcon(IconManager.get_icon("excel", 14))
        btn_p_import.setToolTip("Import pieces from Excel / CSV")
        btn_p_import.clicked.connect(self._import_excel)
        p_toolbar_2.addWidget(btn_p_import)

        btn_p_open = QPushButton("Open")
        btn_p_open.setStyleSheet(btn_style_compact)
        btn_p_open.setIcon(IconManager.get_icon("open", 14))
        btn_p_open.setToolTip("Open / Load saved project file (*.wcp)")
        btn_p_open.clicked.connect(lambda: self.open_project_from_file(None))
        p_toolbar_2.addWidget(btn_p_open)

        btn_p_save = QPushButton("Save")
        btn_p_save.setStyleSheet(btn_style_compact)
        btn_p_save.setIcon(IconManager.get_icon("save", 14))
        btn_p_save.setToolTip("Save project file (*.wcp)")
        btn_p_save.clicked.connect(self._save_project)
        p_toolbar_2.addWidget(btn_p_save)

        btn_p_more = QPushButton("More...")
        btn_p_more.setStyleSheet(btn_style_compact)
        btn_p_more.setToolTip("More options & templates")
        btn_p_more.clicked.connect(self._show_pieces_menu)
        p_toolbar_2.addWidget(btn_p_more)
        p_toolbar_2.addStretch()
        pw_layout.addLayout(p_toolbar_2)

        # Columns selector filter row
        p_cols_row = QHBoxLayout()
        p_cols_row.setSpacing(12)
        lbl_p_cols = QLabel("Columns:")
        lbl_p_cols.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.chk_p_idx = QCheckBox("Index")
        self.chk_p_idx.setChecked(True)
        self.chk_p_idx.stateChanged.connect(lambda s: self.pieces_table.setColumnHidden(0, s == 0))
        self.chk_p_grade = QCheckBox("Material")
        self.chk_p_grade.setChecked(True)
        self.chk_p_grade.stateChanged.connect(lambda s: self.pieces_table.setColumnHidden(4, s == 0))
        self.chk_p_rot = QCheckBox("Rotation")
        self.chk_p_rot.setChecked(True)
        self.chk_p_rot.stateChanged.connect(lambda s: self.pieces_table.setColumnHidden(5, s == 0))

        p_cols_row.addWidget(lbl_p_cols)
        p_cols_row.addWidget(self.chk_p_idx)
        p_cols_row.addWidget(self.chk_p_grade)
        p_cols_row.addWidget(self.chk_p_rot)
        p_cols_row.addStretch()
        pw_layout.addLayout(p_cols_row)

        # Pieces Table
        self.pieces_table = QTableWidget()
        self.pieces_table.setColumnCount(7)
        self.pieces_table.setHorizontalHeaderLabels([
            "#", "Length ▲", "Width", "Quantity", "Material", "Rotation", "Label"
        ])
        self.pieces_table.verticalHeader().setVisible(False)
        self.pieces_table.setColumnWidth(0, 36)
        self.pieces_table.setColumnWidth(1, 68)
        self.pieces_table.setColumnWidth(2, 58)
        self.pieces_table.setColumnWidth(3, 54)
        self.pieces_table.setColumnWidth(4, 78)
        self.pieces_table.setColumnWidth(5, 58)
        self.pieces_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.pieces_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #D1D5DB;
                background-color: #FFFFFF;
                color: #000000;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #F3F4F6;
                color: #111827;
                font-weight: bold;
                border: 1px solid #D1D5DB;
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #FEE2E2;
                color: #991B1B;
            }
        """)
        self.pieces_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pieces_table.customContextMenuRequested.connect(
            lambda pos: self._show_table_context_menu(self.pieces_table, pos, is_stock=False)
        )
        pw_layout.addWidget(self.pieces_table)
        self.v_splitter.addWidget(pieces_widget)

        # --- BOTTOM SECTION: STOCK ---
        stock_widget = QWidget()
        sw_layout = QVBoxLayout(stock_widget)
        sw_layout.setContentsMargins(4, 4, 4, 4)
        sw_layout.setSpacing(4)

        # STOCK Toolbar - 2 Organized Rows for Clear & Readable Labels
        s_toolbar_1 = QHBoxLayout()
        s_toolbar_1.setSpacing(4)

        lbl_stock_badge = QLabel(" STOCK ")
        lbl_stock_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_stock_badge.setStyleSheet("background-color: #15803D; color: white; padding: 3px 6px; border-radius: 3px;")
        s_toolbar_1.addWidget(lbl_stock_badge)

        btn_s_append = QPushButton("+ Append")
        btn_s_append.setStyleSheet(btn_style_compact)
        btn_s_append.setIcon(IconManager.get_icon("append", 14))
        btn_s_append.setToolTip("Add new raw stock bar/plate")
        btn_s_append.clicked.connect(self._add_stock_row)
        s_toolbar_1.addWidget(btn_s_append)

        btn_s_delete = QPushButton("Delete")
        btn_s_delete.setStyleSheet(btn_style_compact)
        btn_s_delete.setIcon(IconManager.get_icon("delete", 14))
        btn_s_delete.setToolTip("Delete selected stock row")
        btn_s_delete.clicked.connect(self._delete_stock_row)
        s_toolbar_1.addWidget(btn_s_delete)

        btn_s_clear = QPushButton("Clear")
        btn_s_clear.setStyleSheet(btn_style_compact)
        btn_s_clear.setIcon(IconManager.get_icon("clear", 14))
        btn_s_clear.setToolTip("Clear all stock")
        btn_s_clear.clicked.connect(self._clear_stock)
        s_toolbar_1.addWidget(btn_s_clear)

        btn_s_sort = QPushButton("Sort")
        btn_s_sort.setStyleSheet(btn_style_compact)
        btn_s_sort.setIcon(IconManager.get_icon("sort", 14))
        btn_s_sort.setToolTip("Sort stock by length, width, quantity, or material")
        btn_s_sort.clicked.connect(self._sort_stock)
        s_toolbar_1.addWidget(btn_s_sort)
        s_toolbar_1.addStretch()
        sw_layout.addLayout(s_toolbar_1)

        # Row 2: Secondary actions (Paste, Import, Presets, More)
        s_toolbar_2 = QHBoxLayout()
        s_toolbar_2.setSpacing(4)

        btn_s_paste = QPushButton("Paste")
        btn_s_paste.setStyleSheet(btn_style_compact)
        btn_s_paste.setIcon(IconManager.get_icon("paste", 14))
        btn_s_paste.setToolTip("Paste copied table columns from Excel (Ctrl+V)")
        btn_s_paste.clicked.connect(lambda: self._handle_clipboard_paste(self.stock_table, is_stock=True))
        s_toolbar_2.addWidget(btn_s_paste)

        btn_s_import = QPushButton("Import")
        btn_s_import.setStyleSheet(btn_style_compact)
        btn_s_import.setIcon(IconManager.get_icon("excel", 14))
        btn_s_import.setToolTip("Import stock from Excel / CSV")
        btn_s_import.clicked.connect(self._import_stock_excel)
        s_toolbar_2.addWidget(btn_s_import)

        btn_s_presets = QPushButton("Presets")
        btn_s_presets.setStyleSheet(btn_style_compact)
        btn_s_presets.setIcon(IconManager.get_icon("settings", 14))
        btn_s_presets.setToolTip("Quick add 12m, 6m, or 2x6m plate")
        btn_s_presets.clicked.connect(self._show_presets_menu)
        s_toolbar_2.addWidget(btn_s_presets)

        btn_s_more = QPushButton("More...")
        btn_s_more.setStyleSheet(btn_style_compact)
        btn_s_more.clicked.connect(self._show_stock_menu)
        s_toolbar_2.addWidget(btn_s_more)
        s_toolbar_2.addStretch()
        sw_layout.addLayout(s_toolbar_2)

        # Columns selector filter row for stock
        s_cols_row = QHBoxLayout()
        s_cols_row.setSpacing(12)
        lbl_s_cols = QLabel("Columns:")
        lbl_s_cols.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.chk_s_idx = QCheckBox("Index")
        self.chk_s_idx.setChecked(True)
        self.chk_s_idx.stateChanged.connect(lambda s: self.stock_table.setColumnHidden(0, s == 0))
        self.chk_s_price = QCheckBox("Price")
        self.chk_s_price.setChecked(True)
        self.chk_s_price.stateChanged.connect(lambda s: self.stock_table.setColumnHidden(6, s == 0))

        s_cols_row.addWidget(lbl_s_cols)
        s_cols_row.addWidget(self.chk_s_idx)
        s_cols_row.addWidget(self.chk_s_price)
        s_cols_row.addStretch()
        sw_layout.addLayout(s_cols_row)

        # Stock Table with signature Green-tinted headers from Cutting Optimization Pro
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(7)
        self.stock_table.setHorizontalHeaderLabels([
            "#", "Length ▲", "Width", "Quantity", "Material", "Label", "Price"
        ])
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.setColumnWidth(0, 36)
        self.stock_table.setColumnWidth(1, 68)
        self.stock_table.setColumnWidth(2, 58)
        self.stock_table.setColumnWidth(3, 54)
        self.stock_table.setColumnWidth(4, 78)
        self.stock_table.setColumnWidth(5, 68)
        self.stock_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.stock_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #D1D5DB;
                background-color: #FFFFFF;
                color: #000000;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #D4EDDA;
                color: #166534;
                font-weight: bold;
                border: 1px solid #A7F3D0;
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #DCFCE7;
                color: #166534;
            }
        """)
        self.stock_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.stock_table.customContextMenuRequested.connect(
            lambda pos: self._show_table_context_menu(self.stock_table, pos, is_stock=True)
        )
        sw_layout.addWidget(self.stock_table)
        self.v_splitter.addWidget(stock_widget)

        self.v_splitter.setSizes([380, 300])
        left_layout.addWidget(self.v_splitter)
        self.h_splitter.addWidget(left_container)

        # -------------------------------------------------------------
        # 2. RIGHT PANE: RESULTS, ACTIONS & INTERACTIVE CANVAS
        # -------------------------------------------------------------
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)

        # Top Action Toolbar - Row 1 (Core Optimization Actions)
        r_toolbar_1 = QHBoxLayout()
        r_toolbar_1.setSpacing(6)

        btn_r_style = "QPushButton { padding: 5px 10px; font-size: 11px; font-weight: 500; }"

        # 1. Big Green Start Button
        self.btn_start = QPushButton("▶ Start Optimization")
        self.btn_start.setIcon(IconManager.get_icon("start", 16))
        self.btn_start.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: #FFFFFF;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
                border: 1px solid #15803D;
            }
            QPushButton:hover {
                background-color: #15803D;
            }
            QPushButton:pressed {
                background-color: #166534;
            }
        """)
        self.btn_start.clicked.connect(self._run_optimization)
        r_toolbar_1.addWidget(self.btn_start)

        # Primary workflow actions
        btn_accept = QPushButton("Accept Solution")
        btn_accept.setStyleSheet(btn_r_style)
        btn_accept.setIcon(IconManager.get_icon("accept", 15))
        btn_accept.setToolTip("Accept solution, deduct stock, and record reusable remnants")
        btn_accept.clicked.connect(self._accept_solution)
        r_toolbar_1.addWidget(btn_accept)

        btn_products = QPushButton("Products Generator")
        btn_products.setStyleSheet(btn_r_style)
        btn_products.setIcon(IconManager.get_icon("products", 15))
        btn_products.setToolTip("Parametric Complex Product Definition (Cabinets, Cupboards, Desks)")
        btn_products.clicked.connect(self._open_product_generator)
        r_toolbar_1.addWidget(btn_products)

        btn_settings = QPushButton("Settings")
        btn_settings.setStyleSheet(btn_r_style)
        btn_settings.setIcon(IconManager.get_icon("settings", 15))
        btn_settings.setToolTip("Cutting rules, saw kerf, trim, and nesting modes")
        btn_settings.clicked.connect(self._open_settings)
        r_toolbar_1.addWidget(btn_settings)

        r_toolbar_1.addStretch()
        right_layout.addLayout(r_toolbar_1)

        # Top Action Toolbar - Row 2 (Export & Documentation Actions)
        r_toolbar_2 = QHBoxLayout()
        r_toolbar_2.setSpacing(6)

        btn_images = QPushButton("Export Images")
        btn_images.setStyleSheet(btn_r_style)
        btn_images.setIcon(IconManager.get_icon("images", 15))
        btn_images.setToolTip("Batch export all cutting diagrams as high-resolution images")
        btn_images.clicked.connect(self._export_all_images)
        r_toolbar_2.addWidget(btn_images)

        btn_cnc = QPushButton("CNC Cuts")
        btn_cnc.setStyleSheet(btn_r_style)
        btn_cnc.setIcon(IconManager.get_icon("cnc", 15))
        btn_cnc.setToolTip("Export CNC cut sequence text coordinates and total cutting distance")
        btn_cnc.clicked.connect(self._export_cnc_cuts)
        r_toolbar_2.addWidget(btn_cnc)

        btn_excel = QPushButton("Excel BOM")
        btn_excel.setStyleSheet(btn_r_style)
        btn_excel.setIcon(IconManager.get_icon("excel", 15))
        btn_excel.setToolTip("Export complete workshop Excel workbook with BOM")
        btn_excel.clicked.connect(self._export_excel)
        r_toolbar_2.addWidget(btn_excel)

        btn_dxf = QPushButton("AutoCAD DXF")
        btn_dxf.setStyleSheet(btn_r_style)
        btn_dxf.setIcon(IconManager.get_icon("dxf", 15))
        btn_dxf.setToolTip("Export AutoCAD DXF cutting layout")
        btn_dxf.clicked.connect(self._export_dxf)
        r_toolbar_2.addWidget(btn_dxf)

        btn_print = QPushButton("Print")
        btn_print.setStyleSheet(btn_r_style)
        btn_print.setIcon(IconManager.get_icon("print", 15))
        btn_print.setToolTip("Print cutting diagrams & reports")
        btn_print.clicked.connect(self._print_results)
        r_toolbar_2.addWidget(btn_print)

        btn_save_sol = QPushButton("Save Solution")
        btn_save_sol.setStyleSheet(btn_r_style)
        btn_save_sol.setIcon(IconManager.get_icon("save", 15))
        btn_save_sol.setToolTip("Save solution to project database")
        btn_save_sol.clicked.connect(self._save_solution)
        r_toolbar_2.addWidget(btn_save_sol)

        r_toolbar_2.addStretch()
        right_layout.addLayout(r_toolbar_2)

        # Results Tabs: Results (2D) | Results (1D) | Statistics
        self.res_tabs = QTabWidget()
        self.res_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.res_tabs.addTab(QWidget(), "📄 Results (2D)")
        self.res_tabs.addTab(QWidget(), "📊 Results (1D)")
        self.res_tabs.addTab(QWidget(), "📈 Statistics")
        self.res_tabs.currentChanged.connect(self._on_res_tab_changed)
        right_layout.addWidget(self.res_tabs)

        # Diagram Controls Row: Sizes (Piece) | Label (Piece) | B&W Mode | Additional... | Zoom
        self.ctrl_frame = QWidget()
        ctrl_row = QHBoxLayout(self.ctrl_frame)
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(12)

        self.chk_sizes = QCheckBox("Sizes (Piece)")
        self.chk_sizes.setChecked(True)
        self.chk_sizes.stateChanged.connect(self._update_canvas_display)
        ctrl_row.addWidget(self.chk_sizes)

        self.chk_labels = QCheckBox("Label (Piece)")
        self.chk_labels.setChecked(True)
        self.chk_labels.stateChanged.connect(self._update_canvas_display)
        ctrl_row.addWidget(self.chk_labels)

        self.chk_as_text = QCheckBox("As text")
        self.chk_as_text.setChecked(False)
        self.chk_as_text.stateChanged.connect(self._on_as_text_toggled)
        ctrl_row.addWidget(self.chk_as_text)

        self.chk_bw = QCheckBox("🎨 B&W Mode")
        self.chk_bw.setChecked(False)
        self.chk_bw.stateChanged.connect(self._update_canvas_display)
        ctrl_row.addWidget(self.chk_bw)

        btn_additional = QPushButton("Additional...")
        btn_additional.clicked.connect(self._open_settings)
        ctrl_row.addWidget(btn_additional)

        btn_columns = QPushButton("Columns")
        btn_columns.clicked.connect(self._show_results_columns_menu)
        ctrl_row.addWidget(btn_columns)

        btn_fit_cols = QPushButton("⬌ Fit / Expand")
        btn_fit_cols.setToolTip("توسيع أعمدة الجدول لمنع اختصار العمليات بالنقاط (Expand all columns to fit full text)")
        btn_fit_cols.clicked.connect(self._expand_results_columns)
        ctrl_row.addWidget(btn_fit_cols)

        self.chk_xy = QCheckBox("XY")
        self.chk_xy.setChecked(False)
        ctrl_row.addWidget(self.chk_xy)

        ctrl_row.addStretch()

        lbl_zoom = QLabel("Zoom:")
        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["Fit to Window", "50%", "75%", "100%", "125%", "150%", "200%", "300%"])
        self.combo_zoom.currentIndexChanged.connect(self._update_canvas_display)
        ctrl_row.addWidget(lbl_zoom)
        ctrl_row.addWidget(self.combo_zoom)

        right_layout.addWidget(self.ctrl_frame)

        # Pattern Tabs Bar (#1, #2, #3 ...)
        self.pattern_tabs = QTabBar()
        self.pattern_tabs.setDrawBase(False)
        self.pattern_tabs.setExpanding(False)
        self.pattern_tabs.setStyleSheet("""
            QTabBar::tab {
                background: #E5E7EB;
                color: #1F2937;
                padding: 4px 14px;
                border: 1px solid #D1D5DB;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #2563EB;
                border-color: #9CA3AF;
            }
        """)
        self.pattern_tabs.currentChanged.connect(self._on_pattern_tab_changed)
        right_layout.addWidget(self.pattern_tabs)

        # Stacked Widget:
        # Page 0 -> Interactive Canvas Diagram
        # Page 1 -> Results Table (As text mode matching Cutting Optimization Pro Image 1)
        # Page 2 -> Rich Statistics Dashboard matching Cutting Optimization Pro Image 2
        self.right_stack = QStackedWidget()

        # Page 0: Interactive Canvas embedded in a scrollable frame
        self.scroll_canvas = QScrollArea()
        self.scroll_canvas.setWidgetResizable(True)
        self.scroll_canvas.setStyleSheet("border: 1px solid #D1D5DB; background-color: #FFFFFF;")

        self.canvas = CuttingCanvas()
        self.scroll_canvas.setWidget(self.canvas)
        self.right_stack.addWidget(self.scroll_canvas)

        # Page 1: Results Table (As text mode)
        self.table_results_text = QTableWidget()
        self.table_results_text.setAlternatingRowColors(True)
        self.table_results_text.verticalHeader().setVisible(False)
        self.table_results_text.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_results_text.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_results_text.setWordWrap(True)
        self.table_results_text.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_results_text.setStyleSheet("""
            QTableWidget {
                gridline-color: #A0B0C8;
                background-color: #FFFFFF;
                alternate-background-color: #F8FAFC;
                color: #000000;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #C6D9F1;
                color: #000000;
                font-weight: bold;
                border: 1px solid #94A8C6;
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #B8D0EC;
                color: #000000;
            }
        """)
        self.right_stack.addWidget(self.table_results_text)
        self.table_results_text.cellClicked.connect(self._on_results_text_row_clicked)
        self.table_results_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_results_text.customContextMenuRequested.connect(
            self._show_results_table_context_menu
        )

        # Page 2: Rich Statistics Dashboard
        self.stats_dashboard = StatisticsDashboard()
        self.right_stack.addWidget(self.stats_dashboard)

        right_layout.addWidget(self.right_stack, 1)

        # Right Pane Bottom Status Bar
        self.right_status_frame = QFrame()
        self.right_status_frame.setStyleSheet("""
            QFrame {
                background-color: #F1F5F9;
                border-top: 1px solid #CBD5E1;
                padding: 3px 8px;
            }
            QLabel {
                color: #0F172A;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        rs_layout = QHBoxLayout(self.right_status_frame)
        rs_layout.setContentsMargins(6, 3, 6, 3)

        self.lbl_status_util = QLabel("Utilization: 0.00 %")
        self.lbl_status_scrap = QLabel("Scrap: 0.00 %")
        self.lbl_status_qty = QLabel("Quantity: 0")
        self.lbl_status_coords = QLabel("(0, 0)")

        rs_layout.addWidget(self.lbl_status_util)
        rs_layout.addSpacing(16)
        rs_layout.addWidget(self.lbl_status_scrap)
        rs_layout.addSpacing(16)
        rs_layout.addWidget(self.lbl_status_qty)
        rs_layout.addStretch()
        rs_layout.addWidget(self.lbl_status_coords)

        right_layout.addWidget(self.right_status_frame)
        self.h_splitter.addWidget(right_container)

        # Set comfortable initial split (left inputs: 455px, right results: 945px)
        self.h_splitter.setSizes([455, 945])
        handle = self.h_splitter.handle(1)
        if handle:
            handle.setCursor(QCursor(Qt.CursorShape.SplitHCursor))
        main_layout.addWidget(self.h_splitter)

        # Results tabs and diagram controls are hidden initially until Start Optimization is clicked
        self.res_tabs.setVisible(False)
        self.ctrl_frame.setVisible(False)
        self.pattern_tabs.setVisible(False)
        self.right_status_frame.setVisible(False)

        # Install universal table keyboard event filters (Ctrl+C, Ctrl+V, Delete)
        self._install_table_clipboard_filters()

    # -------------------------------------------------------------
    # Initial Data & Helpers
    # -------------------------------------------------------------
    def _load_initial_defaults(self):
        """Pre-populates demo rows matching the user's Cutting Optimization Pro reference screenshot."""
        self.pieces_table.setRowCount(0)
        demo_pieces = [
            (620.0, 570.0, 3, "wood", True, "john"),
            (600.0, 500.0, 5, "wood", True, "mike"),
            (650.0, 540.0, 7, "wood", True, "jenny"),
            (890.0, 510.0, 6, "wood", True, "alice"),
            (740.0, 680.0, 3, "wood", True, "jason"),
            (457.0, 0.0,   30, "pipe", True, "1D"),
        ]
        self.pieces_table.setRowCount(len(demo_pieces))
        for r, (l, w, q, mat, rot, lbl) in enumerate(demo_pieces):
            self._set_piece_row(r, l, w, q, mat, rot, lbl)

        self.stock_table.setRowCount(0)
        demo_stock = [
            (3000.0, 2000.0, 10, "wood", "2D", 0.0),
            (2800.0, 0.0,    100, "pipe", "1D", 0.0),
        ]
        self.stock_table.setRowCount(len(demo_stock))
        for r, (l, w, q, mat, lbl, pr) in enumerate(demo_stock):
            self._set_stock_row(r, l, w, q, mat, lbl, pr)

    def _set_piece_row(self, row: int, length, width, qty, mat: str, rot: bool = True, label: str = ""):
        # 0: # (Index with checkbox)
        chk_item = QTableWidgetItem(f"{row + 1}")
        chk_item.setCheckState(Qt.CheckState.Checked)
        chk_item.setToolTip(f"Row #{row + 1}")
        self.pieces_table.setItem(row, 0, chk_item)

        # 1: Length
        if isinstance(length, (int, float)):
            l_str = str(int(length) if float(length).is_integer() else length)
        else:
            l_str = str(length).strip()
        it_l = QTableWidgetItem(l_str)
        it_l.setToolTip(f"Length: {l_str} mm")
        self.pieces_table.setItem(row, 1, it_l)

        # 2: Width
        if isinstance(width, (int, float)):
            w_str = str(int(width) if float(width).is_integer() else width) if width > 0 else ""
        else:
            w_str = str(width).strip() if str(width).strip() not in ("0", "0.0") else ""
        it_w = QTableWidgetItem(w_str)
        it_w.setToolTip(f"Width: {w_str} mm" if w_str else "1D Linear Part")
        self.pieces_table.setItem(row, 2, it_w)

        # 3: Quantity
        q_str = str(qty).strip()
        it_q = QTableWidgetItem(q_str)
        it_q.setToolTip(f"Quantity: {q_str}")
        self.pieces_table.setItem(row, 3, it_q)

        # 4: Material
        m_str = str(mat).strip()
        it_m = QTableWidgetItem(m_str)
        it_m.setToolTip(f"Material: {m_str}")
        self.pieces_table.setItem(row, 4, it_m)

        # 5: Rotation Checkbox
        rot_item = QTableWidgetItem()
        rot_item.setCheckState(Qt.CheckState.Checked if rot else Qt.CheckState.Unchecked)
        rot_item.setToolTip("Allow 90° rotation" if rot else "Fixed orientation")
        self.pieces_table.setItem(row, 5, rot_item)

        # 6: Label
        lbl_str = str(label).strip()
        it_lbl = QTableWidgetItem(lbl_str)
        it_lbl.setToolTip(f"Part Label / Mark: {lbl_str}")
        self.pieces_table.setItem(row, 6, it_lbl)

    def _set_stock_row(self, row: int, length, width, qty, mat: str, label: str, price = 0.0):
        # 0: #
        chk_item = QTableWidgetItem(f"{row + 1}")
        chk_item.setCheckState(Qt.CheckState.Checked)
        chk_item.setToolTip(f"Stock Row #{row + 1}")
        self.stock_table.setItem(row, 0, chk_item)

        # 1: Length
        if isinstance(length, (int, float)):
            l_str = str(int(length) if float(length).is_integer() else length)
        else:
            l_str = str(length).strip()
        it_l = QTableWidgetItem(l_str)
        it_l.setToolTip(f"Stock Length: {l_str} mm")
        self.stock_table.setItem(row, 1, it_l)

        # 2: Width
        if isinstance(width, (int, float)):
            w_str = str(int(width) if float(width).is_integer() else width) if width > 0 else ""
        else:
            w_str = str(width).strip() if str(width).strip() not in ("0", "0.0") else ""
        it_w = QTableWidgetItem(w_str)
        it_w.setToolTip(f"Stock Width: {w_str} mm" if w_str else "1D Bar")
        self.stock_table.setItem(row, 2, it_w)

        # 3: Quantity
        q_str = str(qty).strip()
        it_q = QTableWidgetItem(q_str)
        it_q.setToolTip(f"Available Quantity: {q_str}")
        self.stock_table.setItem(row, 3, it_q)

        # 4: Material
        m_str = str(mat).strip()
        it_m = QTableWidgetItem(m_str)
        it_m.setToolTip(f"Material: {m_str}")
        self.stock_table.setItem(row, 4, it_m)

        # 5: Label
        lbl_str = str(label).strip()
        it_lbl = QTableWidgetItem(lbl_str)
        it_lbl.setToolTip(f"Stock Label / Tag: {lbl_str}")
        self.stock_table.setItem(row, 5, it_lbl)

        # 6: Price
        p_str = str(price).strip()
        it_p = QTableWidgetItem(p_str)
        it_p.setToolTip(f"Unit Price: {p_str}")
        self.stock_table.setItem(row, 6, it_p)

    def _toggle_expand_tables(self):
        """Toggles between expanded tables (72% screen) and balanced split (48%)."""
        sizes = self.h_splitter.sizes()
        total = sum(sizes) if sum(sizes) > 0 else 1300
        if sizes[0] < total * 0.58:
            self.h_splitter.setSizes([int(total * 0.72), int(total * 0.28)])
        else:
            self.h_splitter.setSizes([int(total * 0.48), int(total * 0.52)])
        self.pieces_table.resizeColumnsToContents()
        self.stock_table.resizeColumnsToContents()

    # -------------------------------------------------------------
    # Table Manipulations
    # -------------------------------------------------------------
    def _set_empty_piece_row(self, row: int):
        chk_item = QTableWidgetItem(f"{row + 1}")
        chk_item.setCheckState(Qt.CheckState.Checked)
        chk_item.setToolTip(f"Piece Row #{row + 1}")
        self.pieces_table.setItem(row, 0, chk_item)
        self.pieces_table.setItem(row, 1, QTableWidgetItem(""))
        self.pieces_table.setItem(row, 2, QTableWidgetItem(""))
        self.pieces_table.setItem(row, 3, QTableWidgetItem(""))
        self.pieces_table.setItem(row, 4, QTableWidgetItem(""))
        rot_item = QTableWidgetItem()
        rot_item.setCheckState(Qt.CheckState.Checked)
        self.pieces_table.setItem(row, 5, rot_item)
        self.pieces_table.setItem(row, 6, QTableWidgetItem(""))

    def _add_piece_row(self):
        r = self.pieces_table.rowCount()
        self.pieces_table.insertRow(r)
        self._set_empty_piece_row(r)
        self.pieces_table.setCurrentCell(r, 1)

    def _delete_piece_row(self):
        r = self.pieces_table.currentRow()
        if r >= 0:
            self.pieces_table.removeRow(r)
            self._reindex_table(self.pieces_table)

    def _clear_pieces(self):
        self.pieces_table.setRowCount(0)

    def _set_empty_stock_row(self, row: int):
        chk_item = QTableWidgetItem(f"{row + 1}")
        chk_item.setCheckState(Qt.CheckState.Checked)
        chk_item.setToolTip(f"Stock Row #{row + 1}")
        self.stock_table.setItem(row, 0, chk_item)
        self.stock_table.setItem(row, 1, QTableWidgetItem(""))
        self.stock_table.setItem(row, 2, QTableWidgetItem(""))
        self.stock_table.setItem(row, 3, QTableWidgetItem(""))
        self.stock_table.setItem(row, 4, QTableWidgetItem(""))
        self.stock_table.setItem(row, 5, QTableWidgetItem(""))
        self.stock_table.setItem(row, 6, QTableWidgetItem(""))

    def _add_stock_row(self):
        r = self.stock_table.rowCount()
        self.stock_table.insertRow(r)
        self._set_empty_stock_row(r)
        self.stock_table.setCurrentCell(r, 1)

    def _delete_stock_row(self):
        r = self.stock_table.currentRow()
        if r >= 0:
            self.stock_table.removeRow(r)
            self._reindex_table(self.stock_table)

    def _clear_stock(self):
        self.stock_table.setRowCount(0)

    def _reindex_table(self, table: QTableWidget):
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item:
                item.setText(f"{r + 1}")

    def _show_pieces_menu(self):
        menu = QMenu(self)
        a_open = menu.addAction("📂 Open Project... (فتح مشروع)")
        a_open.triggered.connect(lambda: self.open_project_from_file(None))
        a_save = menu.addAction("💾 Save Project (حفظ المشروع)")
        a_save.triggered.connect(self._save_project)
        a_save_as = menu.addAction("💾 Save Project As... (حفظ المشروع باسم)")
        a_save_as.triggered.connect(self._save_project_as)
        menu.addSeparator()
        a_import = menu.addAction("📥 Import from Excel / CSV")
        a_import.triggered.connect(self._import_excel)
        a_tmpl = menu.addAction("📄 Download Excel Template")
        a_tmpl.triggered.connect(self._download_template)
        a_demo = menu.addAction("✨ Load Demo Data (Wood & Pipe)")
        a_demo.triggered.connect(self._load_initial_defaults)
        a_steel = menu.addAction("🏗️ Load Steel Demo (Beams & Plates)")
        a_steel.triggered.connect(self._load_steel_demo)
        menu.exec(self.cursor().pos())

    def _show_stock_menu(self):
        menu = QMenu(self)
        a_add_12m = menu.addAction("+ Quick 12m Stock Bar (12000 mm)")
        a_add_12m.triggered.connect(lambda: self._add_preset_stock(12000.0, 0.0, "STK-12M"))
        a_add_6m = menu.addAction("+ Quick 6m Stock Bar (6000 mm)")
        a_add_6m.triggered.connect(lambda: self._add_preset_stock(6000.0, 0.0, "STK-6M"))
        a_add_pl = menu.addAction("+ Quick Plate 2x6m (6000 x 2000 mm)")
        a_add_pl.triggered.connect(lambda: self._add_preset_stock(6000.0, 2000.0, "STK-PL2x6"))
        menu.exec(self.cursor().pos())

    def _show_presets_menu(self):
        self._show_stock_menu()

    def _add_preset_stock(self, l: float, w: float, lbl: str):
        r = self.stock_table.rowCount()
        self.stock_table.insertRow(r)
        first_mat = self.pieces_table.item(0, 4).text() if self.pieces_table.rowCount() > 0 and self.pieces_table.item(0, 4) else "wood"
        self._set_stock_row(r, l, w, 20, first_mat, lbl, 0.0)

    def _load_steel_demo(self):
        self.pieces_table.setRowCount(0)
        demo_steel_parts = [
            (5400.0, 0.0,   4, "IPE 300", False, "B-101"),
            (6200.0, 0.0,   6, "IPE 300", False, "B-102"),
            (4500.0, 0.0,   8, "HEA 200", False, "C-201"),
            (600.0,  400.0, 8, "PL 12mm", True,  "BP-1"),
            (350.0,  250.0, 16,"PL 12mm", True,  "GUS-1"),
            (280.0,  150.0, 24,"PL 10mm", True,  "STF-1"),
        ]
        self.pieces_table.setRowCount(len(demo_steel_parts))
        for r, (l, w, q, mat, rot, lbl) in enumerate(demo_steel_parts):
            self._set_piece_row(r, l, w, q, mat, rot, lbl)

        self.stock_table.setRowCount(0)
        demo_steel_stock = [
            (12000.0, 0.0,    20, "IPE 300", "STK-12M", 0.0),
            (12000.0, 0.0,    15, "HEA 200", "STK-12M", 0.0),
            (6000.0,  2000.0, 5,  "PL 12mm", "PL-2x6", 0.0),
            (6000.0,  2000.0, 5,  "PL 10mm", "PL-2x6", 0.0),
        ]
        self.stock_table.setRowCount(len(demo_steel_stock))
        for r, (l, w, q, mat, lbl, pr) in enumerate(demo_steel_stock):
            self._set_stock_row(r, l, w, q, mat, lbl, pr)

    # -------------------------------------------------------------
    # Import / Export / Settings
    # -------------------------------------------------------------
    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Cut List", "", "Excel / CSV Files (*.xlsx *.csv)")
        if not path:
            return
        parts_1d, parts_2d, errs = ExcelDataImporter.import_unified_cut_list(path)
        total = len(parts_1d) + len(parts_2d)
        if total == 0:
            QMessageBox.warning(self, "Notice", "No valid parts found in file.")
            return

        curr_r = self.pieces_table.rowCount()
        self.pieces_table.setRowCount(curr_r + total)
        idx = 0
        for p in parts_1d:
            self._set_piece_row(curr_r + idx, p.length_mm, 0.0, p.quantity, p.designation, False, p.mark)
            idx += 1
        for pl in parts_2d:
            sec_name = f"PL {int(pl.thickness_mm) if pl.thickness_mm.is_integer() else pl.thickness_mm}mm"
            self._set_piece_row(curr_r + idx, pl.length_mm, pl.width_mm, pl.quantity, sec_name, pl.allow_rotation, pl.mark)
            idx += 1

        QMessageBox.information(self, "Import Complete", f"Successfully imported {total} items ({len(parts_1d)} 1D, {len(parts_2d)} 2D).")

    def _import_stock_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Stock Inventory", "", "Excel / CSV Files (*.xlsx *.csv)")
        if not path:
            return
        stock_items, errs = ExcelDataImporter.import_stock_inventory(path)
        if not stock_items:
            QMessageBox.warning(self, "Notice", "No valid stock items found.")
            return

        curr_r = self.stock_table.rowCount()
        self.stock_table.setRowCount(curr_r + len(stock_items))
        for idx, s in enumerate(stock_items):
            self._set_stock_row(curr_r + idx, s.length_mm, s.width_mm, s.available_qty, s.designation, s.id, s.cost_per_unit)
        QMessageBox.information(self, "Import Complete", f"Successfully imported {len(stock_items)} stock records.")

    def _download_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel Template", "WafraCut_CutList_Template.xlsx", "Excel Files (*.xlsx)")
        if path:
            TemplateGenerator.generate_unified_cut_list_template(path)
            QMessageBox.information(self, "Template Saved", f"Excel template saved at:\n{path}")

    def _open_settings(self):
        dlg = CuttingSettingsDialog(self.settings, self.linear_mode, self)
        if dlg.exec():
            vals = dlg.get_values()
            self.settings.kerf_mm = vals["kerf"]
            self.settings.plate_kerf_mm = vals["kerf"]
            self.settings.trim_start_mm = vals["trim"]
            self.settings.trim_end_mm = vals["trim"]
            self.settings.plate_margin_mm = vals["margin"]
            self.settings.min_usable_waste_mm = vals["useful_waste"]
            self.settings.min_remnant_length_mm = vals["useful_waste"]
            self.settings.guillotine_cuts_only = vals["guillotine_cuts_only"]
            self.settings.guillotine_first_cut = vals["guillotine_first_cut"]
            self.settings.guillotine_stages = vals["guillotine_stages"]
            self.settings.optimization_level = vals["optimization_level"]
            self.settings.max_cut_length_mm = vals["max_cut_length"]
            self.settings.min_breakable_waste_mm = vals["breakable_limit"]
            self.settings.group_identical_layouts = vals["group_identical"]
            self.linear_mode = vals["mode"]
            set_current_language(vals["language"])

    def save_project_as_file(self, filepath: Optional[str] = None):
        """Saves entire project (Pieces, Stock, Settings) to a .wcp file."""
        if not filepath:
            initial_path = str(Path.home() / "Documents" / "CuttingProject.wcp")
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "حفظ المشروع باسم (Save Project As)",
                initial_path,
                "WafraCut Project (*.wcp);;JSON Files (*.json);;All Files (*.*)"
            )
            if not filepath:
                return

        pieces_data = []
        for r in range(self.pieces_table.rowCount()):
            chk = self.pieces_table.item(r, 0)
            checked = (chk.checkState() == Qt.CheckState.Checked) if chk else True
            l_str = self.pieces_table.item(r, 1).text().strip() if self.pieces_table.item(r, 1) else ""
            w_str = self.pieces_table.item(r, 2).text().strip() if self.pieces_table.item(r, 2) else ""
            q_str = self.pieces_table.item(r, 3).text().strip() if self.pieces_table.item(r, 3) else ""
            m_str = self.pieces_table.item(r, 4).text().strip() if self.pieces_table.item(r, 4) else ""
            rot_item = self.pieces_table.item(r, 5)
            rot = (rot_item.checkState() == Qt.CheckState.Checked) if rot_item else True
            lbl = self.pieces_table.item(r, 6).text().strip() if self.pieces_table.item(r, 6) else ""
            if any([l_str, w_str, q_str, m_str, lbl]):
                pieces_data.append({
                    "checked": checked,
                    "length": l_str,
                    "width": w_str,
                    "quantity": q_str,
                    "material": m_str,
                    "rotation": rot,
                    "label": lbl
                })

        stock_data = []
        for r in range(self.stock_table.rowCount()):
            chk = self.stock_table.item(r, 0)
            checked = (chk.checkState() == Qt.CheckState.Checked) if chk else True
            l_str = self.stock_table.item(r, 1).text().strip() if self.stock_table.item(r, 1) else ""
            w_str = self.stock_table.item(r, 2).text().strip() if self.stock_table.item(r, 2) else ""
            q_str = self.stock_table.item(r, 3).text().strip() if self.stock_table.item(r, 3) else ""
            m_str = self.stock_table.item(r, 4).text().strip() if self.stock_table.item(r, 4) else ""
            lbl = self.stock_table.item(r, 5).text().strip() if self.stock_table.item(r, 5) else ""
            pr = self.stock_table.item(r, 6).text().strip() if self.stock_table.item(r, 6) else "0.0"
            if any([l_str, w_str, q_str, m_str, lbl]):
                stock_data.append({
                    "checked": checked,
                    "length": l_str,
                    "width": w_str,
                    "quantity": q_str,
                    "material": m_str,
                    "label": lbl,
                    "price": pr
                })

        settings_dict = {
            "blade_kerf_linear": getattr(self.settings, 'blade_kerf_linear', 3.0),
            "blade_kerf_plate": getattr(self.settings, 'blade_kerf_plate', 3.0),
            "trim_left": getattr(self.settings, 'trim_left', 5.0),
            "trim_right": getattr(self.settings, 'trim_right', 5.0),
            "trim_top": getattr(self.settings, 'trim_top', 5.0),
            "trim_bottom": getattr(self.settings, 'trim_bottom', 5.0),
            "min_remnant_length": getattr(self.settings, 'min_remnant_length', 300.0),
            "min_remnant_width": getattr(self.settings, 'min_remnant_width', 300.0),
            "linear_mode": self.linear_mode.value if hasattr(self.linear_mode, 'value') else str(self.linear_mode)
        }

        payload = {
            "format": "WafraCutPro_Project",
            "version": APP_VERSION,
            "saved_at": datetime.now().isoformat(),
            "pieces": pieces_data,
            "stock": stock_data,
            "settings": settings_dict
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.current_project_file = filepath
            self._save_last_stock()
            QMessageBox.information(
                self,
                "حفظ المشروع",
                f"تم حفظ المشروع بالكامل بنجاح في:\n{filepath}"
            )
        except Exception as e:
            QMessageBox.critical(self, "خطأ في الحفظ", f"فشل حفظ ملف المشروع:\n{e}")

    def open_project_from_file(self, filepath: Optional[str] = None):
        """Loads entire project (Pieces, Stock, Settings) from a .wcp file."""
        if not filepath:
            initial_path = str(Path.home() / "Documents")
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "فتح مشروع (Open Project)",
                initial_path,
                "WafraCut Project (*.wcp *.json);;All Files (*.*)"
            )
            if not filepath:
                return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            pieces = data.get("pieces", [])
            self.pieces_table.setRowCount(len(pieces))
            for r, p in enumerate(pieces):
                self._set_piece_row(
                    r,
                    p.get("length", ""),
                    p.get("width", ""),
                    p.get("quantity", 1),
                    p.get("material", "wood"),
                    p.get("rotation", True),
                    p.get("label", "")
                )
                chk = self.pieces_table.item(r, 0)
                if chk:
                    chk.setCheckState(Qt.CheckState.Checked if p.get("checked", True) else Qt.CheckState.Unchecked)

            stock = data.get("stock", [])
            self._is_loading_stock = True
            self.stock_table.setRowCount(len(stock))
            for r, s in enumerate(stock):
                self._set_stock_row(
                    r,
                    s.get("length", ""),
                    s.get("width", ""),
                    s.get("quantity", 1),
                    s.get("material", "wood"),
                    s.get("label", ""),
                    s.get("price", 0.0)
                )
                chk = self.stock_table.item(r, 0)
                if chk:
                    chk.setCheckState(Qt.CheckState.Checked if s.get("checked", True) else Qt.CheckState.Unchecked)
            self._is_loading_stock = False

            settings_dict = data.get("settings", {})
            for k, v in settings_dict.items():
                if hasattr(self.settings, k):
                    setattr(self.settings, k, v)

            self.current_project_file = filepath
            self._save_last_stock()
            self._reset_results_view()
            QMessageBox.information(
                self,
                "فتح المشروع",
                f"تم فتح المشروع بنجاح من:\n{filepath}\n"
                f"تم تحميل {len(pieces)} قطعة و {len(stock)} استوك."
            )
        except Exception as e:
            QMessageBox.critical(self, "خطأ في فتح الملف", f"فشل فتح ملف المشروع:\n{e}")

    def _save_project(self):
        if self.current_project_file:
            self.save_project_as_file(self.current_project_file)
        else:
            self.save_project_as_file(None)

    def _save_project_as(self):
        self.save_project_as_file(None)

    def _open_project(self):
        self.open_project_from_file(None)

    def _reset_results_view(self):
        self.current_result = None
        self.canvas.set_plan(None)
        self.table_results_text.setRowCount(0)
        self.res_tabs.setVisible(False)
        self.ctrl_frame.setVisible(False)
        self.pattern_tabs.setVisible(False)
        self.right_status_frame.setVisible(False)
        self.right_stack.setCurrentIndex(0)
        self.lbl_status_util.setText("Utilization: 0.00 %")
        self.lbl_status_scrap.setText("Scrap: 0.00 %")
        self.lbl_status_qty.setText("Quantity: 0")
        self.lbl_status_coords.setText("(0, 0)")

    # -------------------------------------------------------------
    # OPTIMIZATION ENGINE & RESULTS
    # -------------------------------------------------------------
    def _run_optimization(self):
        parts_1d, parts_2d, stock_1d, stock_2d = self._collect_data()

        if not parts_1d and not parts_2d:
            QMessageBox.warning(self, "Notice", "Please enter at least one piece to cut.")
            return

        self._save_last_stock()
        self.btn_start.setEnabled(False)
        self.btn_start.setText("⏳ Calculating...")

        self.settings.linear_mode = self.linear_mode

        self.worker = OptimizationWorker(
            mode_type="AUTO",
            settings=self.settings,
            parts_1d=parts_1d,
            parts_2d=parts_2d,
            stock=stock_1d + stock_2d,
            project_id=self.active_project_id or "PRJ-CURRENT",
            parent=self
        )
        self.worker.progress.connect(self._on_optimization_progress)
        self.worker.finished.connect(self._on_optimization_done)
        self.worker.error.connect(self._on_optimization_error)
        self.worker.start()

    def _on_optimization_progress(self, percent: int, msg: str):
        self.btn_start.setText(f"⏳ {percent}%...")

    def _on_optimization_done(self, result: OptimizationResult):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("▶ Start Optimization")
        self.current_result = result
        self.stats_dashboard.update_statistics(result)
        self.optimization_finished.emit(result)

        # Free unused RAM immediately back to OS
        import gc
        gc.collect()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
            except Exception:
                pass

        # Reveal results tabs and controls now that optimization has completed
        self.res_tabs.setVisible(True)
        self.ctrl_frame.setVisible(True)
        self.right_status_frame.setVisible(True)

        # Select matching result tab
        if result.plate_plans:
            self.res_tabs.setCurrentIndex(0) # 2D
        elif result.linear_plans:
            self.res_tabs.setCurrentIndex(1) # 1D
        else:
            self.res_tabs.setCurrentIndex(2) # Stats

        self._on_res_tab_changed(self.res_tabs.currentIndex())
        self._update_status_bar()

    def _on_optimization_error(self, err_msg: str):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("▶ Start")
        QMessageBox.critical(self, "Optimization Error", f"Optimization encountered an issue:\n{err_msg}")

    def _parse_mat_thickness(self, mat_str: str) -> float:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm)?', mat_str, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                if val > 0:
                    return val
            except ValueError:
                pass
        return 10.0

    def _collect_data(self):
        parts_1d: List[PartCutItem] = []
        parts_2d: List[PlatePartItem] = []
        stock_1d: List[StockItem] = []
        stock_2d: List[StockItem] = []

        # Collect Pieces
        for r in range(self.pieces_table.rowCount()):
            # check if checked in # column
            chk = self.pieces_table.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Unchecked:
                continue

            try:
                l_str = self.pieces_table.item(r, 1).text().strip() if self.pieces_table.item(r, 1) else "0"
                w_str = self.pieces_table.item(r, 2).text().strip() if self.pieces_table.item(r, 2) else "0"
                q_str = self.pieces_table.item(r, 3).text().strip() if self.pieces_table.item(r, 3) else "1"
                mat = self.pieces_table.item(r, 4).text().strip() if self.pieces_table.item(r, 4) else "wood"
                rot_item = self.pieces_table.item(r, 5)
                rot = rot_item.checkState() == Qt.CheckState.Checked if rot_item else True
                lbl = self.pieces_table.item(r, 6).text().strip() if self.pieces_table.item(r, 6) else f"P{r+1}"

                length = parse_fractional_value(l_str)
                width = parse_fractional_value(w_str) if w_str else 0.0
                qty = int(parse_fractional_value(q_str)) if q_str else 1

                if length <= 0 or qty <= 0:
                    continue

                if width > 0:
                    # 2D Plate item
                    thk = self._parse_mat_thickness(mat)
                    parts_2d.append(PlatePartItem(
                        id=str(uuid.uuid4()),
                        mark=lbl,
                        thickness_mm=thk,
                        grade=mat,
                        width_mm=width,
                        length_mm=length,
                        quantity=qty,
                        allow_rotation=rot
                    ))
                else:
                    # 1D Linear item
                    parts_1d.append(PartCutItem(
                        id=str(uuid.uuid4()),
                        mark=lbl,
                        designation=mat,
                        grade="Standard",
                        length_mm=length,
                        quantity=qty
                    ))
            except Exception:
                continue

        # Collect Stock
        for r in range(self.stock_table.rowCount()):
            chk = self.stock_table.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Unchecked:
                continue

            try:
                l_str = self.stock_table.item(r, 1).text().strip() if self.stock_table.item(r, 1) else "0"
                w_str = self.stock_table.item(r, 2).text().strip() if self.stock_table.item(r, 2) else "0"
                q_str = self.stock_table.item(r, 3).text().strip() if self.stock_table.item(r, 3) else "1"
                mat = self.stock_table.item(r, 4).text().strip() if self.stock_table.item(r, 4) else "wood"
                lbl = self.stock_table.item(r, 5).text().strip() if self.stock_table.item(r, 5) else f"STK{r+1}"
                pr_str = self.stock_table.item(r, 6).text().strip() if self.stock_table.item(r, 6) else "0"

                length = parse_fractional_value(l_str)
                width = parse_fractional_value(w_str) if w_str else 0.0
                qty = int(parse_fractional_value(q_str)) if q_str else 1
                price = float(pr_str) if pr_str else 0.0

                if length <= 0 or qty <= 0:
                    continue

                if width > 0:
                    thk = self._parse_mat_thickness(mat)
                    stock_2d.append(StockItem(
                        id=lbl,
                        designation=mat,
                        grade=mat,
                        length_mm=length,
                        width_mm=width,
                        thickness_mm=thk,
                        available_qty=qty,
                        material_type=MaterialType.PLATE,
                        cost_per_unit=price
                    ))
                else:
                    stock_1d.append(StockItem(
                        id=lbl,
                        designation=mat,
                        grade="Standard",
                        length_mm=length,
                        width_mm=0.0,
                        thickness_mm=0.0,
                        available_qty=qty,
                        material_type=MaterialType.LINEAR,
                        cost_per_unit=price
                    ))
            except Exception:
                continue

        return parts_1d, parts_2d, stock_1d, stock_2d

    # -------------------------------------------------------------
    # Pattern Tabs & Canvas Navigation
    # -------------------------------------------------------------
    def _on_res_tab_changed(self, idx: int):
        if idx == 2:  # Statistics
            self.ctrl_frame.hide()
            self.pattern_tabs.hide()
            self.right_stack.setCurrentIndex(2)  # Page 2: Statistics Dashboard
            self.right_status_frame.hide()
            self.stats_dashboard.update_statistics(self.current_result)
        else:  # 2D (0) or 1D (1)
            if self.res_tabs.isVisible():
                self.ctrl_frame.show()
                self.pattern_tabs.show()
                self.right_status_frame.show()
            if self.chk_as_text.isChecked():
                self.right_stack.setCurrentIndex(1)
                self._update_results_text_table()
            else:
                self.right_stack.setCurrentIndex(0)
            self._populate_pattern_tabs()

    def _on_update_detected_in_view(self, info: UpdateInfo):
        pass

    def _on_as_text_toggled(self, checked: bool):
        if self.res_tabs.currentIndex() == 2:
            return
        if checked:
            self.right_stack.setCurrentIndex(1)
            self._update_results_text_table()
        else:
            self.right_stack.setCurrentIndex(0)
            self._update_canvas_display()

    def _on_results_text_row_clicked(self, row: int, col: int):
        if 0 <= row < self.pattern_tabs.count():
            self.pattern_tabs.blockSignals(True)
            self.pattern_tabs.setCurrentIndex(row)
            self.pattern_tabs.blockSignals(False)

    def _show_results_columns_menu(self):
        menu = QMenu(self)
        for col_idx in range(self.table_results_text.columnCount()):
            header_item = self.table_results_text.horizontalHeaderItem(col_idx)
            title = header_item.text() if header_item else f"Col {col_idx+1}"
            act = menu.addAction(title)
            act.setCheckable(True)
            act.setChecked(not self.table_results_text.isColumnHidden(col_idx))
            def _toggle(state, c=col_idx):
                self.table_results_text.setColumnHidden(c, not state)
            act.toggled.connect(_toggle)
        menu.exec(QCursor.pos())

    def _update_results_text_table(self):
        if not self.current_result:
            self.table_results_text.setRowCount(0)
            return

        active_tab = self.res_tabs.currentIndex()
        if active_tab == 1:  # 1D Bar Nesting Results
            headers = ["#", "Length ▲", "Material", "Quantity", "Waste", "Pieces"]
            self.table_results_text.setColumnCount(len(headers))
            self.table_results_text.setHorizontalHeaderLabels(headers)

            plans = self.current_result.linear_plans
            self.table_results_text.setRowCount(len(plans))
            for r, plan in enumerate(plans):
                piece_counts = defaultdict(int)
                segs = getattr(plan, 'segments', getattr(plan, 'cuts', []))
                for cut in segs:
                    l_val = getattr(cut, 'length', getattr(cut, 'cut_length', 0.0))
                    piece_counts[l_val] += 1
                pieces_str = " + ".join([
                    f"{count}x{int(l) if float(l).is_integer() else l}"
                    for l, count in sorted(piece_counts.items(), reverse=True)
                ])
                if not pieces_str:
                    pieces_str = "-"

                mat_name = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or getattr(plan, 'stock_material', None) or "Steel"
                rem_len = getattr(plan, 'raw_remnant_length', getattr(plan, 'waste_length', 0.0))
                reps = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))

                items = [
                    f"{r + 1}",
                    f"{int(plan.stock_length) if float(plan.stock_length).is_integer() else plan.stock_length}",
                    str(mat_name),
                    f"{reps}",
                    f"{int(rem_len) if float(rem_len).is_integer() else round(rem_len, 1)}",
                    pieces_str
                ]
                for c, val in enumerate(items):
                    item = QTableWidgetItem(val)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setToolTip(str(val))
                    if c == 0:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setBackground(QColor("#DCE6F1"))
                        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    elif c in (1, 3, 4):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    else:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.table_results_text.setItem(r, c, item)

            self.table_results_text.setColumnWidth(0, 45)
            self.table_results_text.setColumnWidth(1, 95)
            self.table_results_text.setColumnWidth(2, 100)
            self.table_results_text.setColumnWidth(3, 75)
            self.table_results_text.setColumnWidth(4, 85)
            self.table_results_text.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        else:  # 2D Plate Nesting Results
            headers = ["#", "Length ▲", "Width", "Material", "Quantity", "Waste", "Waste %", "Pieces"]
            self.table_results_text.setColumnCount(len(headers))
            self.table_results_text.setHorizontalHeaderLabels(headers)

            plans = self.current_result.plate_plans
            self.table_results_text.setRowCount(len(plans))
            for r, plan in enumerate(plans):
                piece_counts = defaultdict(int)
                pts = getattr(plan, 'parts', getattr(plan, 'placed_parts', []))
                for pt in pts:
                    piece_counts[(pt.width, pt.length)] += 1
                pieces_str = " + ".join([
                    f"{count}x({int(w) if float(w).is_integer() else w}×{int(l) if float(l).is_integer() else l})"
                    for (w, l), count in sorted(piece_counts.items(), reverse=True)
                ])
                if not pieces_str:
                    pieces_str = "-"

                mat_name = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")
                reps = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))

                items = [
                    f"{r + 1}",
                    f"{int(plan.plate_length) if float(plan.plate_length).is_integer() else plan.plate_length}",
                    f"{int(plan.plate_width) if float(plan.plate_width).is_integer() else plan.plate_width}",
                    str(mat_name),
                    f"{reps}",
                    f"{int(plan.waste_area) if float(plan.waste_area).is_integer() else round(plan.waste_area, 1)}",
                    f"{100.0 - plan.utilization_pct:.2f}%",
                    pieces_str
                ]
                for c, val in enumerate(items):
                    item = QTableWidgetItem(val)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setToolTip(str(val))
                    if c == 0:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setBackground(QColor("#DCE6F1"))
                        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    elif c in (1, 2, 4, 5, 6):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    else:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.table_results_text.setItem(r, c, item)

            self.table_results_text.setColumnWidth(0, 45)
            self.table_results_text.setColumnWidth(1, 85)
            self.table_results_text.setColumnWidth(2, 85)
            self.table_results_text.setColumnWidth(3, 95)
            self.table_results_text.setColumnWidth(4, 75)
            self.table_results_text.setColumnWidth(5, 85)
            self.table_results_text.setColumnWidth(6, 85)
            self.table_results_text.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

    def _expand_results_columns(self):
        """Expands all columns and rows to fit contents, eliminating '...' dots."""
        self.table_results_text.resizeColumnsToContents()
        self.table_results_text.resizeRowsToContents()

    def _populate_pattern_tabs(self):
        self.pattern_tabs.blockSignals(True)
        # Clear existing tabs
        while self.pattern_tabs.count() > 0:
            self.pattern_tabs.removeTab(0)

        if not self.current_result:
            self.pattern_tabs.blockSignals(False)
            self.canvas.set_2d_plan(None)
            return

        active_tab = self.res_tabs.currentIndex()
        if active_tab == 0: # 2D
            plans = self.current_result.plate_plans
            for i in range(len(plans)):
                self.pattern_tabs.addTab(f"#{i + 1}")
        elif active_tab == 1: # 1D
            plans = self.current_result.linear_plans
            for i, p in enumerate(plans):
                rep = getattr(p, 'repetition_count', getattr(p, 'repetitions', 1))
                tab_title = f"#{i + 1} (x{rep})" if rep > 1 else f"#{i + 1}"
                self.pattern_tabs.addTab(tab_title)
        else: # Statistics
            self.pattern_tabs.addTab("Summary")

        self.pattern_tabs.blockSignals(False)

        if self.pattern_tabs.count() > 0:
            self.pattern_tabs.setCurrentIndex(0)
            self._on_pattern_tab_changed(0)
        else:
            self.canvas.set_2d_plan(None)

    def _on_pattern_tab_changed(self, tab_idx: int):
        if not self.current_result or tab_idx < 0:
            return

        active_tab = self.res_tabs.currentIndex()
        if active_tab == 0: # 2D Plate
            if tab_idx < len(self.current_result.plate_plans):
                plan = self.current_result.plate_plans[tab_idx]
                rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
                self.canvas.set_2d_plan(plan)
                self.lbl_status_util.setText(f"Utilization: {plan.utilization_pct:.2f} %")
                self.lbl_status_scrap.setText(f"Scrap: {100.0 - plan.utilization_pct:.2f} %")
                self.lbl_status_qty.setText(f"Quantity: {rep}")
                self.lbl_status_coords.setText(f"({plan.plate_length:.0f}, {plan.plate_width:.0f})")
        elif active_tab == 1: # 1D Bar
            if tab_idx < len(self.current_result.linear_plans):
                plan = self.current_result.linear_plans[tab_idx]
                rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
                self.canvas.set_1d_plan(plan)
                self.lbl_status_util.setText(f"Utilization: {plan.utilization_pct:.2f} %")
                self.lbl_status_scrap.setText(f"Scrap: {plan.waste_pct:.2f} %")
                self.lbl_status_qty.setText(f"Quantity: {rep}")
                self.lbl_status_coords.setText(f"({plan.stock_length:.0f}, 0)")

        # Sync table selection if in text mode
        if self.chk_as_text.isChecked() and tab_idx < self.table_results_text.rowCount():
            self.table_results_text.blockSignals(True)
            self.table_results_text.selectRow(tab_idx)
            self.table_results_text.blockSignals(False)

    def _update_canvas_display(self):
        show_sizes = self.chk_sizes.isChecked()
        show_labels = self.chk_labels.isChecked()
        is_bw = getattr(self, "chk_bw", None) and self.chk_bw.isChecked()
        color_mode = "BW" if is_bw else "COLOR"

        zoom_text = self.combo_zoom.currentText()
        fit = (zoom_text == "Fit to Window")
        zoom_val = 1.0
        if "50%" in zoom_text:
            zoom_val = 0.50
        elif "75%" in zoom_text:
            zoom_val = 0.75
        elif "125%" in zoom_text:
            zoom_val = 1.25
        elif "150%" in zoom_text:
            zoom_val = 1.50
        elif "200%" in zoom_text:
            zoom_val = 2.00
        elif "300%" in zoom_text:
            zoom_val = 3.00

        self.canvas.set_display_options(show_sizes, show_labels, zoom_val, fit, color_mode=color_mode)

    def _open_multi_print(self):
        if not self.current_result:
            QMessageBox.warning(self, "Multi-Print", "Please run optimization first.")
            return
        dlg = MultiLayoutPrintDialog(self.current_result, self)
        dlg.exec()

    def _export_all_images(self):
        if not self.current_result:
            QMessageBox.warning(self, "Export Images", "Please run optimization first.")
            return
        dlg = BatchImageExportDialog(self.current_result, self)
        dlg.exec()

    def _export_cnc_cuts(self):
        if not self.current_result:
            QMessageBox.warning(self, "CNC Cuts", "Please run optimization first.")
            return
        dlg = CNCCutSequenceDialog(self.current_result, self)
        dlg.exec()

    def _open_product_generator(self):
        dlg = ProductGeneratorDialog(self)
        if dlg.exec():
            parts = dlg.get_generated_parts()
            if parts:
                curr_r = self.pieces_table.rowCount()
                self.pieces_table.setRowCount(curr_r + len(parts))
                for i, p in enumerate(parts):
                    r = curr_r + i
                    self._set_piece_row(
                        r,
                        length=p["length"],
                        width=p["width"],
                        qty=p["quantity"],
                        mat=p.get("material", "wood"),
                        rot=True,
                        label=p.get("label", f"P-{r+1}")
                    )
                QMessageBox.information(
                    self,
                    "Product Added",
                    f"Successfully generated {len(parts)} component parts and added them to the Pieces cut list!"
                )

    def _install_table_clipboard_filters(self):
        """Installs universal keyboard event filters on all tables for rock-solid Ctrl+C, Ctrl+V, and Delete."""
        for table in (self.pieces_table, self.stock_table, self.table_results_text):
            table.installEventFilter(self)
            table.viewport().installEventFilter(self)

    def _get_table_for_widget(self, w):
        """Finds which table owns the event or currently focused widget."""
        for t in (self.pieces_table, self.stock_table, self.table_results_text):
            if w == t or w == t.viewport() or (w and w.parent() == t.viewport()):
                return t
        focus_w = QApplication.focusWidget()
        for t in (self.pieces_table, self.stock_table, self.table_results_text):
            if focus_w == t or focus_w == t.viewport() or (focus_w and focus_w.parent() == t.viewport()):
                return t
        return None

    def eventFilter(self, watched, event):
        """Universal event filter guaranteeing Ctrl+C, Ctrl+V, and Delete in all tables."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()

            # Universal Copy (Ctrl+C / Ctrl+Insert)
            is_copy = (mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C) or \
                      (mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Insert)
            if is_copy:
                table = self._get_table_for_widget(watched)
                if table:
                    focus_w = QApplication.focusWidget()
                    if isinstance(focus_w, (QLineEdit, QTextEdit)) and focus_w.parent() == table.viewport() and focus_w.hasSelectedText():
                        focus_w.copy()
                    else:
                        self._handle_clipboard_copy(table)
                    return True

            # Universal Paste (Ctrl+V / Shift+Insert)
            is_paste = (mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_V) or \
                       (mods == Qt.KeyboardModifier.ShiftModifier and key == Qt.Key.Key_Insert)
            if is_paste:
                table = self._get_table_for_widget(watched)
                if table:
                    is_stock = (table == self.stock_table)
                    focus_w = QApplication.focusWidget()
                    cb_text = QApplication.clipboard().text()
                    # If clipboard contains tabular data (multiple lines or tab characters), always paste into table grid
                    if "\t" in cb_text or "\n" in cb_text or "\r" in cb_text:
                        self._handle_clipboard_paste(table, is_stock=is_stock)
                        return True
                    elif isinstance(focus_w, (QLineEdit, QTextEdit)) and focus_w.parent() == table.viewport():
                        focus_w.paste()
                        return True
                    else:
                        self._handle_clipboard_paste(table, is_stock=is_stock)
                        return True

            # Delete key on selected rows/cells
            elif key == Qt.Key.Key_Delete and mods == Qt.KeyboardModifier.NoModifier:
                table = self._get_table_for_widget(watched)
                if table in (self.pieces_table, self.stock_table):
                    focus_w = QApplication.focusWidget()
                    if not isinstance(focus_w, (QLineEdit, QTextEdit)):
                        self._handle_delete_key(table)
                        return True

        return super().eventFilter(watched, event)

    def _handle_delete_key(self, table: QTableWidget):
        """Clears selected cells or removes rows on Delete key."""
        selected_ranges = table.selectedRanges()
        if not selected_ranges:
            curr_item = table.currentItem()
            if curr_item and curr_item.column() > 0:
                curr_item.setText("")
            return

        # Check if entire rows are selected
        selected_rows = set()
        for r in selected_ranges:
            if r.leftColumn() == 0 and r.rightColumn() >= table.columnCount() - 1:
                for row_idx in range(r.topRow(), r.bottomRow() + 1):
                    selected_rows.add(row_idx)

        if selected_rows and len(selected_rows) < table.rowCount():
            for row_idx in sorted(selected_rows, reverse=True):
                table.removeRow(row_idx)
            self._reindex_table(table)
        else:
            for item in table.selectedItems():
                if item.column() > 0:
                    if item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.text() == "":
                        item.setCheckState(Qt.CheckState.Unchecked)
                    else:
                        item.setText("")

    def _handle_clipboard_copy(self, table: QTableWidget):
        """Copies selected table cells/rows as clean tab-separated values to system clipboard (Ctrl+C)."""
        try:
            selected_items = table.selectedItems()
            if not selected_items:
                curr_item = table.currentItem()
                if curr_item:
                    is_check_col = (curr_item.column() == 0 or (table == self.pieces_table and curr_item.column() == 5))
                    val = ("YES" if curr_item.checkState() == Qt.CheckState.Checked else "NO") if is_check_col else curr_item.text()
                    QApplication.clipboard().setText(val)
                return

            rows = sorted(list(set(item.row() for item in selected_items)))
            cols = sorted(list(set(item.column() for item in selected_items)))

            min_r = min(rows)
            max_r = max(rows)
            min_c = min(cols)
            max_c = max(cols)

            # When copying whole rows or ranges starting from column 0,
            # omit the '#' row counter column (col 0) unless ONLY column 0 was selected.
            omit_index = (min_c == 0 and max_c > 0 and table != self.table_results_text)
            data_start_c = 1 if omit_index else min_c

            lines = []
            for r in rows:
                row_vals = []
                for c in range(data_start_c, max_c + 1):
                    item = table.item(r, c)
                    if not item:
                        row_vals.append("")
                    else:
                        is_check_col = (c == 0 or (table == self.pieces_table and c == 5))
                        if is_check_col:
                            row_vals.append("YES" if item.checkState() == Qt.CheckState.Checked else "NO")
                        else:
                            row_vals.append(item.text().strip())
                lines.append("\t".join(row_vals))

            tsv_data = "\n".join(lines)
            QApplication.clipboard().setText(tsv_data)
        except Exception as ex:
            import traceback
            traceback.print_exc()

    def _show_results_table_context_menu(self, pos):
        menu = QMenu(self)
        act_copy = menu.addAction("📋 Copy Selected (نسخ المخرجات المحددة - Ctrl+C)")
        act_copy.triggered.connect(lambda: self._handle_clipboard_copy(self.table_results_text))
        menu.exec(self.table_results_text.viewport().mapToGlobal(pos))

    def _show_table_context_menu(self, table: QTableWidget, pos, is_stock: bool):
        """Right-click context menu for tables providing Copy, Paste, Insert, and Delete."""
        menu = QMenu(self)
        act_copy = menu.addAction("📋 Copy (نسخ - Ctrl+C)")
        act_copy.triggered.connect(lambda: self._handle_clipboard_copy(table))

        act_paste = menu.addAction("📥 Paste (لصق - Ctrl+V)")
        act_paste.triggered.connect(lambda: self._handle_clipboard_paste(table, is_stock=is_stock))

        menu.addSeparator()
        act_append = menu.addAction("➕ Append Row (إضافة صف)")
        act_append.triggered.connect(self._add_stock_row if is_stock else self._add_piece_row)

        act_delete = menu.addAction("❌ Delete Selected (حذف الصف المحدد)")
        act_delete.triggered.connect(self._delete_stock_row if is_stock else self._delete_piece_row)

        menu.addSeparator()
        act_clear = menu.addAction("🧹 Clear All (مسح الكل)")
        act_clear.triggered.connect(self._clear_stock if is_stock else self._clear_pieces)

        menu.exec(table.viewport().mapToGlobal(pos))

    def _handle_clipboard_paste(self, table: QTableWidget, is_stock: bool = False, text_override: Optional[str] = None):
        """Pastes clipboard tabular data into table cell-by-cell matching professional spreadsheet behavior."""
        try:
            raw_text = text_override if text_override is not None else QApplication.clipboard().text()
            if not raw_text or not raw_text.strip():
                return

            # Split into non-empty lines
            raw_lines = [l for l in raw_text.splitlines() if l.strip()]
            if not raw_lines:
                return

            # Detect delimiter (\t from Excel/Sheets, or comma/semicolon from CSV)
            delim = '\t' if '\t' in raw_lines[0] else (',' if ',' in raw_lines[0] else ';')
            matrix = []
            for line in raw_lines:
                cells = [c.strip().strip('"').strip("'") for c in line.split(delim)]
                matrix.append(cells)

            if not matrix:
                return

            # Detect if first row is a header row (e.g. contains "length", "width", "qty", "#", etc.)
            first_row_lower = [c.lower() for c in matrix[0]]
            is_header = any(
                h in first_row_lower[0] or (len(first_row_lower) > 1 and h in first_row_lower[1])
                for h in ["len", "length", "طول", "width", "عرض", "mark", "id", "#", "item", "label", "qty", "material"]
            )
            data_matrix = matrix[1:] if (is_header and len(matrix) > 1) else matrix

            if not data_matrix:
                return

            # Determine target start row and column from selection or current cell
            selected_items = table.selectedItems()
            curr_r = table.currentRow()
            curr_c = table.currentColumn()

            if selected_items:
                start_r = min(it.row() for it in selected_items)
                sel_min_c = min(it.column() for it in selected_items)
                sel_max_c = max(it.column() for it in selected_items)
                if sel_min_c == 0 and sel_max_c > 0 and len(data_matrix[0]) < table.columnCount():
                    start_c = 1
                else:
                    start_c = sel_min_c
            elif curr_r >= 0 and curr_c >= 0:
                start_r = curr_r
                start_c = curr_c if curr_c > 0 else 1
            else:
                start_r = 0
                start_c = 1

            # Detect if data genuinely includes a leading numeric index column (e.g. "1", "2", "3"...)
            has_index_col = (
                len(data_matrix[0]) >= table.columnCount() and
                data_matrix[0][0].strip() == "1" and
                (len(data_matrix) == 1 or data_matrix[1][0].strip() in ("2", "1"))
            )
            if has_index_col and start_c >= 1:
                data_matrix = [r[1:] for r in data_matrix]

            # Ensure table has enough rows
            needed_rows = start_r + len(data_matrix)
            if needed_rows > table.rowCount():
                old_count = table.rowCount()
                table.setRowCount(needed_rows)
                for r in range(old_count, needed_rows):
                    if is_stock:
                        self._set_empty_stock_row(r)
                    else:
                        self._set_empty_piece_row(r)

            # Paste 2D cell by cell
            for i, row_cells in enumerate(data_matrix):
                target_r = start_r + i
                # Ensure row index item in col 0 is initialized and valid
                idx_item = table.item(target_r, 0)
                if not idx_item:
                    idx_item = QTableWidgetItem(f"{target_r + 1}")
                    idx_item.setCheckState(Qt.CheckState.Checked)
                    table.setItem(target_r, 0, idx_item)

                # Column mapping logic for full-row paste (Length, Width, Qty, Material, ...)
                if start_c == 1 and len(row_cells) >= 4:
                    if not is_stock:
                        # Pieces Table: [Length, Width, Qty, Material, Rotation, Label]
                        if len(row_cells) == 4:
                            row_cells = [row_cells[0], row_cells[1], row_cells[2], row_cells[3], "YES", ""]
                        elif len(row_cells) == 5:
                            if row_cells[4].upper() in ("YES", "NO", "TRUE", "FALSE", "1", "0"):
                                row_cells = [row_cells[0], row_cells[1], row_cells[2], row_cells[3], row_cells[4], ""]
                            else:
                                row_cells = [row_cells[0], row_cells[1], row_cells[2], row_cells[3], "YES", row_cells[4]]
                        elif len(row_cells) >= 6:
                            if not row_cells[4].upper() in ("YES", "NO", "TRUE", "FALSE", "1", "0"):
                                row_cells = [row_cells[0], row_cells[1], row_cells[2], row_cells[3], "YES", row_cells[4]]
                    else:
                        # Stock Table: [Length, Width, Qty, Material, Label, Price]
                        if len(row_cells) >= 6 and row_cells[4].upper() in ("YES", "NO", "TRUE", "FALSE", "1", "0"):
                            price_val = row_cells[6] if len(row_cells) > 6 else "0.0"
                            row_cells = [row_cells[0], row_cells[1], row_cells[2], row_cells[3], row_cells[5], price_val]

                for j, cell_str in enumerate(row_cells):
                    target_c = start_c + j
                    if target_c >= table.columnCount():
                        break

                    # Column 0: Index / Active Checkbox
                    if target_c == 0:
                        chk_val = cell_str.lower() not in ("no", "0", "false", "off", "لا")
                        idx_item.setCheckState(Qt.CheckState.Checked if chk_val else Qt.CheckState.Unchecked)
                        continue

                    # Pieces Table Column 5: Rotation Checkbox
                    if not is_stock and target_c == 5:
                        rot_chk = cell_str.lower() not in ("no", "0", "false", "off", "لا", "fixed")
                        rot_item = table.item(target_r, 5)
                        if not rot_item:
                            rot_item = QTableWidgetItem()
                            table.setItem(target_r, 5, rot_item)
                        rot_item.setCheckState(Qt.CheckState.Checked if rot_chk else Qt.CheckState.Unchecked)
                        continue

                    # Text cell (Length, Width, Qty, Material, Label, Price)
                    it = table.item(target_r, target_c)
                    if not it:
                        it = QTableWidgetItem()
                        table.setItem(target_r, target_c, it)
                    it.setText(cell_str)

            self._reindex_table(table)
            self._update_status_bar()

        except Exception as ex:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Paste Error", f"Error during clipboard paste:\n{str(ex)}")

    def _update_status_bar(self):
        if not self.current_result:
            return
        u = self.current_result.overall_utilization_pct
        w = self.current_result.overall_waste_pct
        self.lbl_status_util.setText(f"Utilization: {u:.2f} %")
        self.lbl_status_scrap.setText(f"Scrap: {w:.2f} %")

    # -------------------------------------------------------------
    # Exports & Solution Handlers
    # -------------------------------------------------------------
    def _export_excel(self):
        if not self.current_result:
            QMessageBox.warning(self, "Export", "Please run optimization first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Workshop Excel Workbook", "WafraCut_Cutting_Report.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return

        proj = Project(id="PRJ-CURRENT", name="Cutting Plan", code="CP-01", settings=self.settings)
        ExcelReportExporter.export_workshop_workbook(path, proj, self.current_result, results_only=True)
        QMessageBox.information(self, "Export Successful", f"Excel cutting results saved successfully at:\n{path}")

    def _export_dxf(self):
        if not self.current_result:
            QMessageBox.warning(self, "Export DXF", "Please run optimization first.")
            return

        active_tab = self.res_tabs.currentIndex()
        if active_tab == 0 and self.current_result.plate_plans:
            tab_idx = max(0, self.pattern_tabs.currentIndex())
            plan = self.current_result.plate_plans[tab_idx]
            path, _ = QFileDialog.getSaveFileName(self, "Export DXF Cutting Layout", f"Plate_Sheet_{tab_idx + 1}.dxf", "AutoCAD DXF Files (*.dxf)")
            if path:
                DXFExporter.export_plate_nest_dxf(path, plan)
                QMessageBox.information(self, "DXF Exported", f"AutoCAD DXF layout saved at:\n{path}")
        elif self.current_result.linear_plans:
            path, _ = QFileDialog.getSaveFileName(self, "Export DXF Bar Plans", "Linear_Bar_Plans.dxf", "AutoCAD DXF Files (*.dxf)")
            if path:
                DXFExporter.export_linear_dxf(path, self.current_result.linear_plans)
                QMessageBox.information(self, "DXF Exported", f"AutoCAD DXF bar layout saved at:\n{path}")
        else:
            QMessageBox.information(self, "Export DXF", "No plate or bar cutting patterns available to export.")

    def _show_tabular_cuts(self):
        if not self.current_result:
            QMessageBox.warning(self, "Tabular Cuts", "Please run optimization first.")
            return
        dlg = TabularCutDialog(self.current_result, self)
        dlg.exec()

    def _show_stickers(self):
        if not self.current_result:
            QMessageBox.warning(self, "Workshop Stickers", "Please run optimization first.")
            return
        dlg = StickersDialog(self.current_result, self)
        dlg.exec()

    def _accept_solution(self):
        if not self.current_result:
            QMessageBox.warning(self, "Accept Solution", "Please run optimization first.")
            return

        consumed_counts = defaultdict(int)
        remnants_created = []

        # Process Linear Plans
        for plan in self.current_result.linear_plans:
            consumed_counts[plan.stock_id] += 1
            if plan.raw_remnant_length >= self.settings.min_usable_remnant_linear_mm:
                rem = RemnantItem(
                    id=f"REM-{uuid.uuid4().hex[:6].upper()}",
                    original_stock_id=plan.stock_id,
                    designation=plan.designation,
                    grade=plan.grade,
                    length_mm=plan.raw_remnant_length,
                    material_type=MaterialType.LINEAR,
                    status=RemnantStatus.REUSABLE,
                    source_project=self.active_project_id or "PRJ-01",
                    notes=f"Reusable remnant from {plan.stock_id}"
                )
                remnants_created.append(rem)
                self.remnant_repo.add(rem)

        # Process Plate Plans
        for plan in self.current_result.plate_plans:
            consumed_counts[plan.stock_id] += 1
            rem_area = plan.total_plate_area_m2 - plan.used_parts_area_m2
            if rem_area >= 0.5:
                rem = RemnantItem(
                    id=f"REM-PL-{uuid.uuid4().hex[:6].upper()}",
                    original_stock_id=plan.stock_id,
                    designation=f"PL {plan.thickness_mm:.0f}mm",
                    grade=plan.grade,
                    length_mm=plan.plate_length,
                    width_mm=plan.plate_width,
                    thickness_mm=plan.thickness_mm,
                    material_type=MaterialType.PLATE,
                    status=RemnantStatus.REUSABLE,
                    source_project=self.active_project_id or "PRJ-01",
                    notes=f"Reusable plate offcut ({rem_area:.2f} m²)"
                )
                remnants_created.append(rem)
                self.remnant_repo.add(rem)

        # Deduct quantities in UI Stock Table
        total_deducted = 0
        for r in range(self.stock_table.rowCount()):
            lbl_item = self.stock_table.item(r, 5) # Label
            qty_item = self.stock_table.item(r, 3) # Quantity
            if lbl_item and qty_item:
                lbl = lbl_item.text().strip()
                deduct = consumed_counts.get(lbl, 0)
                if deduct > 0:
                    try:
                        curr_q = int(qty_item.text().strip())
                        new_q = max(0, curr_q - deduct)
                        qty_item.setText(str(new_q))
                        total_deducted += deduct
                    except ValueError:
                        pass

        # Insert new reusable remnants into stock table
        for rem in remnants_created:
            r = self.stock_table.rowCount()
            self.stock_table.insertRow(r)
            self._set_stock_row(
                r, rem.length_mm, rem.width_mm, 1,
                rem.designation, rem.id, 0.0
            )

        QMessageBox.information(
            self,
            "✅ Solution Accepted",
            f"Cutting plan successfully accepted and committed to workshop records!\n\n"
            f"• Total stock units deducted: {total_deducted}\n"
            f"• Reusable remnants stored to inventory: {len(remnants_created)}\n"
            f"• Stock inventory table refreshed with new quantities and remnants."
        )

    def _save_solution(self):
        self._save_project()

    def _print_results(self):
        if not self.current_result:
            QMessageBox.warning(self, "Print", "Please run optimization first.")
            return

        active_tab = self.res_tabs.currentIndex()
        active_mode = "1D" if active_tab == 1 else "2D"
        current_idx = max(0, self.pattern_tabs.currentIndex())
        dlg = CuttingPrintPdfDialog(self.current_result, active_mode=active_mode, current_idx=current_idx, parent=self)
        dlg.exec()

    def _sort_pieces(self):
        menu = QMenu(self)
        a_len_desc = menu.addAction("Sort by Length (High to Low)")
        a_len_desc.triggered.connect(lambda: self._sort_table_column(self.pieces_table, 1, reverse=True))
        a_len_asc = menu.addAction("Sort by Length (Low to High)")
        a_len_asc.triggered.connect(lambda: self._sort_table_column(self.pieces_table, 1, reverse=False))
        a_w_desc = menu.addAction("Sort by Width (High to Low)")
        a_w_desc.triggered.connect(lambda: self._sort_table_column(self.pieces_table, 2, reverse=True))
        a_qty_desc = menu.addAction("Sort by Quantity (High to Low)")
        a_qty_desc.triggered.connect(lambda: self._sort_table_column(self.pieces_table, 3, reverse=True))
        a_mat = menu.addAction("Sort by Material (A to Z)")
        a_mat.triggered.connect(lambda: self._sort_table_column(self.pieces_table, 4, reverse=False, is_str=True))
        menu.exec(self.cursor().pos())

    def _sort_stock(self):
        menu = QMenu(self)
        a_len_desc = menu.addAction("Sort by Length (High to Low)")
        a_len_desc.triggered.connect(lambda: self._sort_table_column(self.stock_table, 1, reverse=True))
        a_w_desc = menu.addAction("Sort by Width (High to Low)")
        a_w_desc.triggered.connect(lambda: self._sort_table_column(self.stock_table, 2, reverse=True))
        a_qty_desc = menu.addAction("Sort by Quantity (High to Low)")
        a_qty_desc.triggered.connect(lambda: self._sort_table_column(self.stock_table, 3, reverse=True))
        a_mat = menu.addAction("Sort by Material (A to Z)")
        a_mat.triggered.connect(lambda: self._sort_table_column(self.stock_table, 4, reverse=False, is_str=True))
        menu.exec(self.cursor().pos())

    def _sort_table_column(self, table: QTableWidget, col: int, reverse: bool = False, is_str: bool = False):
        rows = []
        for r in range(table.rowCount()):
            row_data = []
            for c in range(table.columnCount()):
                item = table.item(r, c)
                row_data.append(item.text() if item else "")
            rows.append(row_data)

        def key_fn(r_data):
            val = r_data[col]
            if is_str:
                return val.lower()
            try:
                return float(val) if val else 0.0
            except ValueError:
                return 0.0

        rows.sort(key=key_fn, reverse=reverse)
        table.setRowCount(0)
        table.setRowCount(len(rows))
        for r, r_data in enumerate(rows):
            for c, val in enumerate(r_data):
                item = QTableWidgetItem(f"{r + 1}" if c == 0 else val)
                if c == 0:
                    item.setCheckState(Qt.CheckState.Checked)
                table.setItem(r, c, item)

    # -------------------------------------------------------------
    # Database Persistence
    # -------------------------------------------------------------
    def load_project_data(self, project_id: str):
        self.active_project_id = project_id
        # load parts
        parts_1d = self.cut_repo.list_linear_by_project(project_id)
        parts_2d = self.cut_repo.list_plate_by_project(project_id)
        total = len(parts_1d) + len(parts_2d)
        if total > 0:
            self.pieces_table.setRowCount(total)
            idx = 0
            for p in parts_1d:
                self._set_piece_row(idx, p.length_mm, 0.0, p.quantity, p.designation, False, p.mark)
                idx += 1
            for pl in parts_2d:
                sec_name = f"PL {int(pl.thickness_mm) if pl.thickness_mm.is_integer() else pl.thickness_mm}mm"
                self._set_piece_row(idx, pl.length_mm, pl.width_mm, pl.quantity, sec_name, pl.allow_rotation, pl.mark)
                idx += 1

        # load stock
        stock = self.stock_repo.list_all()
        if stock:
            self.stock_table.setRowCount(len(stock))
            for r, s in enumerate(stock):
                self._set_stock_row(r, s.length_mm, s.width_mm, s.available_qty, s.designation, s.id, s.cost_per_unit)

    def save_project_data(self, project_id: str):
        self.active_project_id = project_id
        parts_1d, parts_2d, stock_1d, stock_2d = self._collect_data()
        self.cut_repo.clear_linear(project_id)
        self.cut_repo.clear_plate(project_id)
        for p in parts_1d:
            self.cut_repo.add_linear(p, project_id)
        for pl in parts_2d:
            self.cut_repo.add_plate(pl, project_id)
        for s in stock_1d + stock_2d:
            self.stock_repo.add(s)

    def _on_stock_table_changed(self, item=None):
        if getattr(self, '_is_loading_stock', False):
            return
        self._save_last_stock()

    def _save_last_stock(self):
        """Persists the current stock table rows so they are preserved across restarts."""
        try:
            app_dir = Path.home() / ".steelnest_pro"
            app_dir.mkdir(parents=True, exist_ok=True)
            stock_file = app_dir / "last_stock.json"
            rows = []
            for r in range(self.stock_table.rowCount()):
                chk = self.stock_table.item(r, 0)
                checked = (chk.checkState() == Qt.CheckState.Checked) if chk else True
                l_str = self.stock_table.item(r, 1).text().strip() if self.stock_table.item(r, 1) else ""
                w_str = self.stock_table.item(r, 2).text().strip() if self.stock_table.item(r, 2) else ""
                q_str = self.stock_table.item(r, 3).text().strip() if self.stock_table.item(r, 3) else ""
                m_str = self.stock_table.item(r, 4).text().strip() if self.stock_table.item(r, 4) else ""
                lbl_str = self.stock_table.item(r, 5).text().strip() if self.stock_table.item(r, 5) else ""
                p_str = self.stock_table.item(r, 6).text().strip() if self.stock_table.item(r, 6) else "0.0"
                if any([l_str, w_str, q_str, m_str, lbl_str]):
                    rows.append({
                        "checked": checked,
                        "length": l_str,
                        "width": w_str,
                        "quantity": q_str,
                        "material": m_str,
                        "label": lbl_str,
                        "price": p_str
                    })
            with open(stock_file, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_last_stock(self):
        """Loads the last saved stock table, or falls back to standard inventory."""
        self._is_loading_stock = True
        try:
            stock_file = Path.home() / ".steelnest_pro" / "last_stock.json"
            if stock_file.exists():
                with open(stock_file, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                if rows:
                    self.stock_table.setRowCount(len(rows))
                    for r, item in enumerate(rows):
                        self._set_stock_row(
                            r,
                            item.get("length", ""),
                            item.get("width", ""),
                            item.get("quantity", 1),
                            item.get("material", "wood"),
                            item.get("label", ""),
                            item.get("price", 0.0)
                        )
                        chk = self.stock_table.item(r, 0)
                        if chk:
                            chk.setCheckState(Qt.CheckState.Checked if item.get("checked", True) else Qt.CheckState.Unchecked)
                    return
        except Exception:
            pass
        finally:
            self._is_loading_stock = False

        # Fallback default initial stock if no saved stock exists yet
        demo_stock = [
            (12000.0, 0.0,    15, "HEA 200", "STK-HEA200", 0.0),
            (12000.0, 0.0,    10, "IPE 200", "STK-IPE200", 0.0),
            (12000.0, 0.0,    20, "IPE 300", "STK-IPE300", 0.0),
            (6000.0,  0.0,    20, "IPE 300", "STK-6M",     0.0),
            (6000.0,  2000.0, 5,  "PL 12mm", "STK-PL12",   0.0),
        ]
        self._is_loading_stock = True
        self.stock_table.setRowCount(len(demo_stock))
        for r, (l, w, q, mat, lbl, pr) in enumerate(demo_stock):
            self._set_stock_row(r, l, w, q, mat, lbl, pr)
        self._is_loading_stock = False
