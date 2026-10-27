"""
SteelNest Pro - Main Application Window
Replicates the functional layout and workflow of Cutting Optimization Pro:
- Top Menu Bar (File, Settings, Materials, Project, Help)
- Left Pane: Pieces Table (Top) & Stock Table (Bottom) with full toolbar actions.
- Right Pane: Big Green Start Button, Results (2D), Results (1D), Statistics, Pattern Tabs (#1, #2...),
  Interactive Diagram with dimensions, green cut lines, and hatched offcuts.
"""
import sys
from typing import Optional
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMessageBox, QDialog, QPushButton
)
from PyQt6.QtGui import QIcon, QAction, QCursor
from PyQt6.QtCore import Qt, QTimer

from steel_nest.config import APP_NAME, APP_VERSION
from steel_nest.database.db_manager import DatabaseManager
from steel_nest.database.repositories import (
    ProjectRepository, StockRepository, CutListRepository, RemnantRepository
)
from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView
from steel_nest.ui.views.database_view import DatabaseView
from steel_nest.ui.themes import LIGHT_THEME_QSS, DARK_THEME_QSS
from steel_nest.updater.update_manager import UpdateManager, UpdateInfo
from steel_nest.ui.widgets.update_dialog import UpdateDialog

class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1400, 890)
        self.setMinimumSize(1080, 680)

        # Set Window and Taskbar Icon
        icon_paths = [
            Path(__file__).resolve().parent.parent.parent / "resources" / "icon.png",
            Path(__file__).resolve().parent.parent.parent / "resources" / "icon.ico",
            Path(sys.executable).parent / "resources" / "icon.png",
            Path(sys.executable).parent / "resources" / "icon.ico",
        ]
        self.app_icon = None
        for ip in icon_paths:
            if ip.exists():
                self.app_icon = QIcon(str(ip))
                self.setWindowIcon(self.app_icon)
                break

        # Database initialization
        self.db = db_manager or DatabaseManager()
        self.project_repo = ProjectRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.cut_repo = CutListRepository(self.db)
        self.remnant_repo = RemnantRepository(self.db)

        self.active_project_id = None

        # Update Manager
        self.update_manager = UpdateManager(current_version=APP_VERSION, parent=self)
        self.latest_update_info: Optional[UpdateInfo] = None
        self.update_manager.update_detected.connect(self._on_update_detected)

        self._setup_ui()
        self._setup_menus()
        self._ensure_default_project()

        # Trigger background check 1.5s after launch if enabled
        if self.update_manager.auto_check:
            QTimer.singleShot(1500, self.update_manager.check_for_updates_async)

    def _setup_ui(self):
        # The central widget is the unified dual-pane CuttingOptimizationView
        self.cutting_view = CuttingOptimizationView(
            self.cut_repo,
            self.stock_repo,
            self.project_repo,
            self.remnant_repo,
            self
        )
        self.setCentralWidget(self.cutting_view)

        # Bottom Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"Ready | {APP_NAME} v{APP_VERSION} — Optimization Engine Active")

    def _setup_menus(self):
        menubar = self.menuBar()

        # 1. File Menu
        menu_file = menubar.addMenu("File")

        act_new = QAction("New Project", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._on_new_project)
        menu_file.addAction(act_new)

        act_open = QAction("Open Project...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(lambda: self.cutting_view.open_project_from_file(None))
        menu_file.addAction(act_open)

        act_save = QAction("Save Project", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.cutting_view._save_project)
        menu_file.addAction(act_save)

        act_save_as = QAction("Save Project As...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self.cutting_view._save_project_as)
        menu_file.addAction(act_save_as)

        menu_file.addSeparator()

        act_import_p = QAction("Import Pieces (Excel/CSV)...", self)
        act_import_p.triggered.connect(self.cutting_view._import_excel)
        menu_file.addAction(act_import_p)

        act_import_s = QAction("Import Stock (Excel/CSV)...", self)
        act_import_s.triggered.connect(self.cutting_view._import_stock_excel)
        menu_file.addAction(act_import_s)

        act_tmpl = QAction("Download Blank Excel Template...", self)
        act_tmpl.triggered.connect(self.cutting_view._download_template)
        menu_file.addAction(act_tmpl)

        menu_file.addSeparator()

        act_export_excel = QAction("Save Table (Excel BOM)...", self)
        act_export_excel.triggered.connect(self.cutting_view._export_excel)
        menu_file.addAction(act_export_excel)

        act_export_dxf = QAction("Save DXF (AutoCAD)...", self)
        act_export_dxf.triggered.connect(self.cutting_view._export_dxf)
        menu_file.addAction(act_export_dxf)

        act_export_images = QAction("Batch Export Images (PNG)...", self)
        act_export_images.triggered.connect(self.cutting_view._export_all_images)
        menu_file.addAction(act_export_images)

        act_export_cnc = QAction("Export CNC Cut Coordinates...", self)
        act_export_cnc.triggered.connect(self.cutting_view._export_cnc_cuts)
        menu_file.addAction(act_export_cnc)

        act_multi_print = QAction("Multi-Layout Print (1, 2, 4, 6 per page)...", self)
        act_multi_print.triggered.connect(self.cutting_view._open_multi_print)
        menu_file.addAction(act_multi_print)

        menu_file.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # 2. Settings Menu
        menu_settings = menubar.addMenu("Settings")

        act_rules = QAction("Cutting Rules & Saw Kerf...", self)
        act_rules.triggered.connect(self.cutting_view._open_settings)
        menu_settings.addAction(act_rules)

        menu_settings.addSeparator()

        act_light = QAction("Theme: Classic Light", self)
        act_light.setCheckable(True)
        act_light.setChecked(True)
        act_light.triggered.connect(lambda: self._set_theme(LIGHT_THEME_QSS))
        menu_settings.addAction(act_light)

        act_dark = QAction("Theme: Dark Mode", self)
        act_dark.setCheckable(True)
        act_dark.triggered.connect(lambda: self._set_theme(DARK_THEME_QSS))
        menu_settings.addAction(act_dark)

        # 3. Materials Menu
        menu_mat = menubar.addMenu("Materials")

        act_catalog = QAction("Steel Sections & Profiles Catalog...", self)
        act_catalog.triggered.connect(self._open_steel_catalog)
        menu_mat.addAction(act_catalog)

        # 4. Project Menu
        menu_proj = menubar.addMenu("Project")

        act_products = QAction("Parametric Product Definition (Cabinets, Cupboards, Desks)...", self)
        act_products.triggered.connect(self.cutting_view._open_product_generator)
        menu_proj.addAction(act_products)

        menu_proj.addSeparator()

        act_load_demo = QAction("Load Demo Data (Wood & Pipe from Screenshot)", self)
        act_load_demo.triggered.connect(self.cutting_view._load_initial_defaults)
        menu_proj.addAction(act_load_demo)

        act_load_steel = QAction("Load Steel Fabrication Demo (Beams & Plates)", self)
        act_load_steel.triggered.connect(self.cutting_view._load_steel_demo)
        menu_proj.addAction(act_load_steel)

        # 5. Help Menu
        menu_help = menubar.addMenu("Help")

        act_update_help = QAction("🔄 Check for Updates... (التحقق من التحديثات)", self)
        act_update_help.triggered.connect(lambda: self._open_update_dialog())
        menu_help.addAction(act_update_help)
        menu_help.addSeparator()

        act_about = QAction(f"About {APP_NAME}...", self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

        # 6. Menubar Corner Update Button
        self.btn_update_corner = QPushButton("🔄 Updates", self)
        self.btn_update_corner.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_update_corner.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 10px;
                border-radius: 4px;
                margin: 2px 8px;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
        """)
        self.btn_update_corner.clicked.connect(lambda: self._open_update_dialog())
        menubar.setCornerWidget(self.btn_update_corner, Qt.Corner.TopRightCorner)

    def _open_update_dialog(self):
        dlg = UpdateDialog(self.update_manager, preloaded_info=self.latest_update_info, parent=self)
        dlg.exec()

    def _on_update_detected(self, info: UpdateInfo):
        self.latest_update_info = info
        self.btn_update_corner.setText(f"🚀 تحديث متاح: v{info.version} (اضغط هنا)")
        self.btn_update_corner.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 12px;
                border-radius: 4px;
                border: 1px solid #15803D;
                margin: 2px 8px;
            }
            QPushButton:hover {
                background-color: #15803D;
            }
        """)
        self.statusBar().showMessage(
            f"🎉 يتوفر إصدار جديد من WafraCut Pro (الإصدار v{info.version}) — انقر على زر التحديث بالأعلى للاطلاع والتثبيت.",
            20000
        )

    def _set_theme(self, qss: str):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

    def _open_steel_catalog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Steel Profiles & Materials Catalog — دليل قطاعات الحديد")
        dlg.resize(950, 600)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(10, 10, 10, 10)
        db_view = DatabaseView(self.db, dlg)
        dlg_layout.addWidget(db_view)
        dlg.exec()

    def _on_new_project(self):
        res = QMessageBox.question(
            self, "New Project",
            "Clear current pieces to start a new project? (Stock inventory will be preserved)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.cutting_view.pieces_table.setRowCount(0)
            self.cutting_view._reset_results_view()
            self.cutting_view.current_project_file = None
            self.status_bar.showMessage("New project started — Pieces cleared, Stock preserved.", 4000)

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME} v{APP_VERSION}</b><br>"
            f"Professional Steel Nesting & Cutting Optimization Software for Windows.<br><br>"
            f"Compatible with 1D linear profiles (IPE, HEA, Channels, Angles, Pipes) and 2D steel plates.<br>"
            f"Equipped with Free Nesting, Single Cut, and Double Cut modes.<br>"
            f"Offline calculation engine with Excel BOM & AutoCAD DXF exports.<br><br>"
            f"<b>جميع الحقوق محفوظة (المهندس محمد جمال محي)</b><br>"
            f"All Rights Reserved &copy; Eng. Mohamed Gamal Mohy"
        )

    def _ensure_default_project(self):
        projects = self.project_repo.list_all()
        if not projects:
            from steel_nest.models.project import Project, ProjectSettings
            default_proj = Project(
                id="PRJ-DEFAULT-01",
                name="Cutting Project",
                code="PRJ-01",
                settings=ProjectSettings()
            )
            self.project_repo.create(default_proj)
            self.active_project_id = default_proj.id
        else:
            self.active_project_id = projects[0].id
