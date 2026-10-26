"""
Modern Steel Engineering UI Theme & Stylesheets
"""

LIGHT_THEME_QSS = """
/* Classic Windows Engineering Theme (Cutting Optimization Pro Style) */
QWidget {
    background-color: #F0F2F5;
    color: #111827;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 12px;
}

QMainWindow {
    background-color: #F0F2F5;
}

QDialog {
    background-color: #F0F2F5;
}

QMenuBar {
    background-color: #FFFFFF;
    color: #111827;
    border-bottom: 1px solid #D1D5DB;
    padding: 2px 4px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
    border-radius: 3px;
    color: #111827;
}

QMenuBar::item:selected {
    background-color: #E5E7EB;
}

QMenu {
    background-color: #FFFFFF;
    color: #111827;
    border: 1px solid #D1D5DB;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    background-color: transparent;
}

QMenu::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background: #E5E7EB;
    margin: 4px 8px;
}

/* Toolbars & Action Buttons */
QPushButton {
    background-color: #FFFFFF;
    color: #1F2937;
    border: 1px solid #D1D5DB;
    border-radius: 3px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #F9FAFB;
    border-color: #9CA3AF;
}

QPushButton:pressed {
    background-color: #E5E7EB;
}

QCheckBox {
    spacing: 5px;
    font-size: 11px;
    color: #374151;
    font-weight: 500;
}

/* Tables */
QTableWidget, QTableView {
    background-color: #FFFFFF;
    color: #000000;
    gridline-color: #E5E7EB;
    border: 1px solid #CBD5E1;
    border-radius: 0px;
    selection-background-color: #FEE2E2;
    selection-color: #991B1B;
    font-size: 12px;
}

QHeaderView::section {
    background-color: #F3F4F6;
    color: #1F2937;
    font-weight: bold;
    border: 1px solid #E5E7EB;
    padding: 5px 6px;
    font-size: 11px;
}

/* Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    color: #111827;
    border: 1px solid #D1D5DB;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 12px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #2563EB;
}

/* Tab Widgets */
QTabWidget::pane {
    border: 1px solid #CBD5E1;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background-color: #E2E8F0;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #2563EB;
    border-bottom: 1px solid #FFFFFF;
}

QScrollBar:vertical {
    border: none;
    background: #F1F5F9;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}

QScrollBar:horizontal {
    border: none;
    background: #F1F5F9;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #CBD5E1;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #94A3B8;
}

QStatusBar {
    background-color: #F3F4F6;
    color: #4B5563;
    border-top: 1px solid #E5E7EB;
    font-size: 11px;
}
"""

DARK_THEME_QSS = """
/* Dark Theme */
QWidget {
    background-color: #1A1F29;
    color: #E2E8F0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 12px;
}

QMainWindow, QDialog {
    background-color: #1A1F29;
}

QMenuBar {
    background-color: #11151C;
    color: #E2E8F0;
    border-bottom: 1px solid #232B3B;
}

QMenu {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
}

QTableWidget {
    background-color: #1A212E;
    color: #F8FAFC;
    gridline-color: #2D3748;
    border: 1px solid #334155;
}

QHeaderView::section {
    background-color: #11151C;
    color: #94A3B8;
    border: 1px solid #232B3B;
    padding: 4px;
}
"""
