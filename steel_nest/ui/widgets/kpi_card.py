"""
KPI Metric Card Widget for Dashboard and Analytics
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt

class KPICard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", accent_color: str = "#2563EB", parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1E2738;
                border: 1px solid #2D3748;
                border-top: 3px solid {accent_color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #94A3B8; letter-spacing: 0.5px;")

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #F8FAFC;")

        self.sub_label = QLabel(subtitle)
        self.sub_label.setFont(QFont("Segoe UI", 9))
        self.sub_label.setStyleSheet("color: #64748B;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        if subtitle:
            layout.addWidget(self.sub_label)

    def update_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(value)
        if subtitle:
            self.sub_label.setText(subtitle)
