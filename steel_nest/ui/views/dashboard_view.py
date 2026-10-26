"""
Dashboard View - Overview KPIs, Recent Projects, and Shortages
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QScrollArea
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal

from steel_nest.ui.widgets.kpi_card import KPICard
from steel_nest.database.repositories import ProjectRepository, StockRepository, RemnantRepository

class DashboardView(QWidget):
    project_selected = pyqtSignal(str)   # project_id
    navigate_to = pyqtSignal(str)        # tab name e.g. "linear_nesting", "cut_list"

    def __init__(self, project_repo: ProjectRepository, stock_repo: StockRepository, remnant_repo: RemnantRepository, parent=None):
        super().__init__(parent)
        self.project_repo = project_repo
        self.stock_repo = stock_repo
        self.remnant_repo = remnant_repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        h_title = QLabel("Fabrication & Nesting Dashboard")
        h_title.setObjectName("viewTitle")
        h_sub = QLabel("Overview of steel fabrication projects, inventory availability, and cutting optimization.")
        h_sub.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        layout.addLayout(title_box)

        # KPI Cards Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(14)
        self.kpi_projects = KPICard("Active Projects", "0", "Managed projects", "#2563EB")
        self.kpi_stock = KPICard("Stock Inventory", "0 pcs", "Available raw stock", "#10B981")
        self.kpi_remnants = KPICard("Reusable Remnants", "0 pcs", "Usable offcuts", "#F59E0B")
        self.kpi_efficiency = KPICard("Target Utilization", "95.0%", "Production benchmark", "#8B5CF6")
        
        kpi_row.addWidget(self.kpi_projects)
        kpi_row.addWidget(self.kpi_stock)
        kpi_row.addWidget(self.kpi_remnants)
        kpi_row.addWidget(self.kpi_efficiency)
        layout.addLayout(kpi_row)

        # Quick Actions Row
        actions_frame = QFrame()
        actions_frame.setProperty("class", "card")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 12, 16, 12)
        
        lbl_quick = QLabel("Quick Actions:")
        lbl_quick.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        actions_layout.addWidget(lbl_quick)

        btn_new_proj = QPushButton("+ New Project")
        btn_new_proj.setProperty("class", "primaryBtn")
        btn_new_proj.clicked.connect(lambda: self.navigate_to.emit("projects"))
        actions_layout.addWidget(btn_new_proj)

        btn_import_list = QPushButton("Import Cut List")
        btn_import_list.setProperty("class", "secondaryBtn")
        btn_import_list.clicked.connect(lambda: self.navigate_to.emit("cut_list"))
        actions_layout.addWidget(btn_import_list)

        btn_run_linear = QPushButton("Run 1D Linear Nesting")
        btn_run_linear.setProperty("class", "primaryBtn")
        btn_run_linear.clicked.connect(lambda: self.navigate_to.emit("linear_nesting"))
        actions_layout.addWidget(btn_run_linear)

        btn_run_plate = QPushButton("Run 2D Plate Nesting")
        btn_run_plate.setProperty("class", "secondaryBtn")
        btn_run_plate.clicked.connect(lambda: self.navigate_to.emit("plate_nesting"))
        actions_layout.addWidget(btn_run_plate)

        actions_layout.addStretch()
        layout.addWidget(actions_frame)

        # Content Split: Recent Projects & Low Inventory Alerts
        tables_row = QHBoxLayout()
        tables_row.setSpacing(16)

        # Left: Recent Projects
        left_box = QVBoxLayout()
        lbl_proj = QLabel("Recent Projects")
        lbl_proj.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        left_box.addWidget(lbl_proj)

        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(4)
        self.projects_table.setHorizontalHeaderLabels(["Code", "Project Name", "Client", "Updated"])
        self.projects_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.cellDoubleClicked.connect(self._on_project_double_clicked)
        left_box.addWidget(self.projects_table)
        tables_row.addLayout(left_box, 3)

        # Right: Stock Summary & Remnants
        right_box = QVBoxLayout()
        lbl_inv = QLabel("Stock Inventory Highlights")
        lbl_inv.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        right_box.addWidget(lbl_inv)

        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(3)
        self.stock_table.setHorizontalHeaderLabels(["Profile / Plate", "Grade", "Available"])
        self.stock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        right_box.addWidget(self.stock_table)
        tables_row.addLayout(right_box, 2)

        layout.addLayout(tables_row)

        self.refresh_data()

    def refresh_data(self):
        projects = self.project_repo.list_all()
        stock = self.stock_repo.list_all()
        remnants = self.remnant_repo.list_all()

        self.kpi_projects.update_value(str(len(projects)), "Projects in database")
        total_avail_stock = sum(s.available_qty - s.used_qty for s in stock)
        self.kpi_stock.update_value(f"{total_avail_stock} pcs", "Stock bars & plates")
        self.kpi_remnants.update_value(f"{len(remnants)} pcs", "Available offcuts")

        # Fill projects table
        self.projects_table.setRowCount(len(projects[:8]))
        for row, p in enumerate(projects[:8]):
            self.projects_table.setItem(row, 0, QTableWidgetItem(p.code))
            self.projects_table.setItem(row, 1, QTableWidgetItem(p.name))
            self.projects_table.setItem(row, 2, QTableWidgetItem(p.client))
            self.projects_table.setItem(row, 3, QTableWidgetItem(p.updated_at[:10]))
            self.projects_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

        # Fill stock highlights
        self.stock_table.setRowCount(min(8, len(stock)))
        for row, s in enumerate(stock[:8]):
            dims = f"{s.designation} ({s.length_mm:.0f}mm)"
            rem_qty = s.available_qty - s.used_qty
            self.stock_table.setItem(row, 0, QTableWidgetItem(dims))
            self.stock_table.setItem(row, 1, QTableWidgetItem(s.grade))
            self.stock_table.setItem(row, 2, QTableWidgetItem(f"{rem_qty} pcs"))

    def _on_project_double_clicked(self, row, col):
        item = self.projects_table.item(row, 0)
        if item:
            pid = item.data(Qt.ItemDataRole.UserRole)
            self.project_selected.emit(pid)
