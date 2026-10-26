"""
Projects Management View
"""
import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox,
    QSpinBox, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from steel_nest.models.project import Project, ProjectSettings
from steel_nest.database.repositories import ProjectRepository
from steel_nest.config import LinearOptimizationMode, NestingObjective

class ProjectDialog(QDialog):
    def __init__(self, project: Project = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Details" if project else "New Project")
        self.setMinimumWidth(450)
        self.project = project

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(project.name if project else "")
        self.code_edit = QLineEdit(project.code if project else f"PRJ-{uuid.uuid4().hex[:4].upper()}")
        self.client_edit = QLineEdit(project.client if project else "")
        self.desc_edit = QTextEdit(project.description if project else "")
        self.desc_edit.setMaximumHeight(70)

        form.addRow("Project Name*:", self.name_edit)
        form.addRow("Project Code*:", self.code_edit)
        form.addRow("Client / Customer:", self.client_edit)
        form.addRow("Description:", self.desc_edit)
        layout.addLayout(form)

        # Settings Group
        settings_box = QGroupBox("Default Cutting Constraints")
        s_form = QFormLayout(settings_box)
        
        self.kerf_spin = QDoubleSpinBox()
        self.kerf_spin.setRange(0.0, 20.0)
        self.kerf_spin.setValue(project.settings.kerf_mm if project else 3.0)
        self.kerf_spin.setSuffix(" mm")

        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setRange(0.0, 100.0)
        self.trim_start_spin.setValue(project.settings.trim_start_mm if project else 15.0)
        self.trim_start_spin.setSuffix(" mm")

        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setRange(0.0, 100.0)
        self.trim_end_spin.setValue(project.settings.trim_end_mm if project else 15.0)
        self.trim_end_spin.setSuffix(" mm")

        self.remnant_spin = QDoubleSpinBox()
        self.remnant_spin.setRange(0.0, 3000.0)
        self.remnant_spin.setValue(project.settings.min_remnant_length_mm if project else 500.0)
        self.remnant_spin.setSuffix(" mm")

        s_form.addRow("Saw Blade Kerf:", self.kerf_spin)
        s_form.addRow("Start Trimming:", self.trim_start_spin)
        s_form.addRow("End Trimming:", self.trim_end_spin)
        s_form.addRow("Min Reusable Remnant:", self.remnant_spin)
        layout.addWidget(settings_box)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_save = QPushButton("Save Project")
        self.btn_save.setProperty("class", "primaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setProperty("class", "secondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _on_save(self):
        if not self.name_edit.text().strip() or not self.code_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Project Name and Project Code are required.")
            return
        self.accept()

    def get_project_data(self) -> Project:
        proj_id = self.project.id if self.project else str(uuid.uuid4())
        settings = ProjectSettings(
            kerf_mm=self.kerf_spin.value(),
            trim_start_mm=self.trim_start_spin.value(),
            trim_end_mm=self.trim_end_spin.value(),
            min_remnant_length_mm=self.remnant_spin.value()
        )
        return Project(
            id=proj_id,
            name=self.name_edit.text().strip(),
            code=self.code_edit.text().strip(),
            client=self.client_edit.text().strip(),
            description=self.desc_edit.toPlainText().strip(),
            settings=settings
        )

class ProjectsView(QWidget):
    project_changed = pyqtSignal(str) # project_id

    def __init__(self, project_repo: ProjectRepository, parent=None):
        super().__init__(parent)
        self.project_repo = project_repo
        self.active_project_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        h_box = QHBoxLayout()
        title_box = QVBoxLayout()
        h_title = QLabel("Projects Management")
        h_title.setObjectName("viewTitle")
        h_sub = QLabel("Create, duplicate, switch, and configure fabrication projects.")
        h_sub.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        h_box.addLayout(title_box)
        h_box.addStretch()

        btn_new = QPushButton("+ New Project")
        btn_new.setProperty("class", "primaryBtn")
        btn_new.clicked.connect(self._create_project)
        h_box.addWidget(btn_new)
        layout.addLayout(h_box)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Client", "Updated", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Action Buttons Row
        action_row = QHBoxLayout()
        self.btn_select = QPushButton("Set Active Project")
        self.btn_select.setProperty("class", "primaryBtn")
        self.btn_select.clicked.connect(self._select_active)
        
        self.btn_edit = QPushButton("Edit Project")
        self.btn_edit.setProperty("class", "secondaryBtn")
        self.btn_edit.clicked.connect(self._edit_project)

        self.btn_dup = QPushButton("Duplicate Project")
        self.btn_dup.setProperty("class", "secondaryBtn")
        self.btn_dup.clicked.connect(self._duplicate_project)

        self.btn_del = QPushButton("Delete Project")
        self.btn_del.setProperty("class", "secondaryBtn")
        self.btn_del.clicked.connect(self._delete_project)

        action_row.addWidget(self.btn_select)
        action_row.addWidget(self.btn_edit)
        action_row.addWidget(self.btn_dup)
        action_row.addWidget(self.btn_del)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.refresh_table()

    def refresh_table(self):
        projects = self.project_repo.list_all()
        self.table.setRowCount(len(projects))
        for row, p in enumerate(projects):
            is_active = (p.id == self.active_project_id)
            self.table.setItem(row, 0, QTableWidgetItem(p.code))
            self.table.setItem(row, 1, QTableWidgetItem(p.name))
            self.table.setItem(row, 2, QTableWidgetItem(p.client))
            self.table.setItem(row, 3, QTableWidgetItem(p.updated_at[:16].replace("T", " ")))
            self.table.setItem(row, 4, QTableWidgetItem("★ ACTIVE" if is_active else "Ready"))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

    def _get_selected_project_id(self) -> str:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _select_active(self):
        pid = self._get_selected_project_id()
        if pid:
            self.active_project_id = pid
            self.refresh_table()
            self.project_changed.emit(pid)

    def _create_project(self):
        dlg = ProjectDialog(parent=self)
        if dlg.exec():
            proj = dlg.get_project_data()
            self.project_repo.create(proj)
            self.active_project_id = proj.id
            self.refresh_table()
            self.project_changed.emit(proj.id)

    def _edit_project(self):
        pid = self._get_selected_project_id()
        if not pid:
            return
        proj = self.project_repo.get(pid)
        if not proj:
            return
        dlg = ProjectDialog(project=proj, parent=self)
        if dlg.exec():
            updated = dlg.get_project_data()
            self.project_repo.update(updated)
            self.refresh_table()
            self.project_changed.emit(pid)

    def _duplicate_project(self):
        pid = self._get_selected_project_id()
        if not pid:
            return
        proj = self.project_repo.get(pid)
        if not proj:
            return
        new_name = f"{proj.name} (Copy)"
        new_code = f"{proj.code}-CP"
        dup = self.project_repo.duplicate(pid, new_name, new_code)
        if dup:
            self.active_project_id = dup.id
            self.refresh_table()
            self.project_changed.emit(dup.id)

    def _delete_project(self):
        pid = self._get_selected_project_id()
        if not pid:
            return
        if QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this project and its cut lists?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.project_repo.delete(pid)
            if self.active_project_id == pid:
                self.active_project_id = None
            self.refresh_table()
