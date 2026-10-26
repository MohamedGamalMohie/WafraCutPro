"""
WafraCut Pro - Streamlined Update Center
Provides a clean, single-click update interface with embedded GitHub link.
No manual URL configuration required — one button to check and update.
"""
import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from steel_nest.config import APP_VERSION, APP_NAME
from steel_nest.updater.update_manager import (
    UpdateManager, UpdateInfo, UpdateCheckerThread, UpdateDownloaderThread
)


class UpdateCenterWidget(QWidget):
    """
    Clean, one-click update widget:
    - Pre-linked directly to GitHub repo.
    - Single action button: 'Check & Update'.
    - Displays version info, changelog, and live download progress.
    """
    update_detected = pyqtSignal(object)

    def __init__(self, update_manager: UpdateManager = None, preloaded_info: UpdateInfo = None, parent=None):
        super().__init__(parent)
        self.mgr = update_manager or UpdateManager(parent=self)
        self.latest_info: UpdateInfo = preloaded_info
        self.downloader: UpdateDownloaderThread = None
        self.checker: UpdateCheckerThread = None

        self._init_ui()

        if self.latest_info:
            self._display_update_info(self.latest_info)
        elif getattr(self.mgr, 'cached_latest_info', None):
            self._display_update_info(self.mgr.cached_latest_info)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # 1. Header Banner
        header_frame = QFrame(self)
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3A8A, stop:1 #2563EB);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(14, 8, 14, 8)

        lbl_icon = QLabel("🚀")
        lbl_icon.setFont(QFont("Segoe UI Emoji", 26))
        h_layout.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        lbl_title = QLabel("تحديث البرنامج — WafraCut Pro Updater")
        lbl_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF;")
        lbl_sub = QLabel("تحديث تلقائي بضغطة زر واحدة لأحدث إصدار وميزات البرنامج")
        lbl_sub.setFont(QFont("Segoe UI", 9))
        lbl_sub.setStyleSheet("color: #DBEAFE;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch()

        main_layout.addWidget(header_frame)

        # 2. Status & Version Cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        # Card 1: Current Installed Version
        self.card_cur = self._create_card(
            "الإصدار المثبت حالياً",
            f"v{self.mgr.current_version}",
            "#F1F5F9", "#334155"
        )
        cards_layout.addWidget(self.card_cur)

        # Card 2: Latest Available Version
        self.card_latest = self._create_card(
            "أحدث إصدار متاح",
            "—",
            "#FEF3C7", "#92400E"
        )
        cards_layout.addWidget(self.card_latest)

        # Card 3: Status
        self.card_status = self._create_card(
            "حالة النظام",
            "جاهز للفحص",
            "#E0E7FF", "#3730A3"
        )
        cards_layout.addWidget(self.card_status)

        main_layout.addLayout(cards_layout)

        # 3. Changelog / Release Notes
        lbl_notes = QLabel("📋 تفاصيل وما الجديد في التحديث:")
        lbl_notes.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_notes.setStyleSheet("color: #1E293B;")
        main_layout.addWidget(lbl_notes)

        self.txt_changelog = QTextEdit(self)
        self.txt_changelog.setReadOnly(True)
        self.txt_changelog.setFont(QFont("Segoe UI", 10))
        self.txt_changelog.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 10px;
                color: #0F172A;
                line-height: 1.5;
            }
        """)
        self.txt_changelog.setPlaceholderText(
            "اضغط على زر التحديث بالأسفل للبحث عن أي إصدار جديد وتنزيله تلقائياً..."
        )
        main_layout.addWidget(self.txt_changelog, 1)

        # 4. Progress Bar (hidden by default)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                text-align: center;
                height: 24px;
                font-weight: bold;
                background-color: #F1F5F9;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 4px;
            }
        """)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setFont(QFont("Segoe UI", 9))
        self.lbl_progress_status.setStyleSheet("color: #475569; font-weight: bold;")
        self.lbl_progress_status.hide()
        main_layout.addWidget(self.lbl_progress_status)

        # 5. Single Prominent Action Button
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_action = QPushButton("🔄 البحث عن تحديثات وتثبيتها الآن", self)
        self.btn_action.setFixedHeight(42)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 32px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #94A3B8;
                color: #E2E8F0;
            }
        """)
        self.btn_action.clicked.connect(self._on_action_clicked)
        btn_box.addWidget(self.btn_action)
        btn_box.addStretch()

        main_layout.addLayout(btn_box)

    def _create_card(self, title: str, val: str, bg: str, fg: str) -> QFrame:
        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setFont(QFont("Segoe UI", 8))
        lbl_t.setStyleSheet("color: #64748B; font-weight: 600;")
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_t.setWordWrap(True)
        v.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setObjectName("val")
        lbl_v.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_v.setStyleSheet(f"color: {fg};")
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_v.setWordWrap(True)
        v.addWidget(lbl_v)
        return card

    def _set_card_val(self, card: QFrame, val: str, fg: str = None):
        lbl = card.findChild(QLabel, "val")
        if lbl:
            lbl.setText(val)
            if fg:
                lbl.setStyleSheet(f"color: {fg};")

    def refresh_view(self):
        """Called when opening or switching to the tab."""
        if getattr(self.mgr, 'cached_latest_info', None):
            self._display_update_info(self.mgr.cached_latest_info)
        else:
            self._check_updates()

    def _on_action_clicked(self):
        # If an update is ready to download/install, start download
        if self.latest_info and self.latest_info.has_update and self.latest_info.download_url:
            self._start_download()
        else:
            # Otherwise perform a fresh check
            self._check_updates()

    def _check_updates(self):
        self._set_card_val(self.card_status, "جاري الفحص من السيرفر...", "#2563EB")
        self._set_card_val(self.card_latest, "اتصال...", "#64748B")
        self.btn_action.setEnabled(False)
        self.btn_action.setText("⏳ جاري التحقق من التحديثات...")

        self.checker = UpdateCheckerThread(self.mgr.manifest_url, self.mgr.current_version, parent=self)
        self.checker.check_finished.connect(self._on_check_finished)
        self.checker.check_failed.connect(self._on_check_failed)
        self.checker.start()

    def _on_check_finished(self, info: UpdateInfo):
        self.latest_info = info
        self._display_update_info(info)

    def _on_check_failed(self, err_msg: str):
        self.btn_action.setEnabled(True)
        self.btn_action.setText("🔄 إعادة المحاولة")
        self.btn_action.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 32px;
                border-radius: 6px;
            }
        """)
        self._set_card_val(self.card_status, "تعذر الاتصال", "#DC2626")
        self._set_card_val(self.card_latest, "غير متاح", "#64748B")
        self.txt_changelog.setHtml(
            f"<div style='color: #DC2626; padding: 10px; font-family: Segoe UI; text-align: center;'>"
            f"<b>تعذر التحقق من التحديثات حالياً:</b><br>{err_msg}<br><br>"
            f"تأكد من الاتصال بالإنترنت ثم اضغط على زر إعادة المحاولة."
            f"</div>"
        )

    def _display_update_info(self, info: UpdateInfo):
        self.latest_info = info
        self._set_card_val(self.card_latest, f"v{info.version}", "#047857")

        if info.has_update:
            self._set_card_val(self.card_status, "🚀 يوجد تحديث جديد!", "#16A34A")
            self.btn_action.setEnabled(True)
            self.btn_action.setText(f"⬇️ تحديث البرنامج الآن إلى الإصدار (v{info.version})")
            self.btn_action.setStyleSheet("""
                QPushButton {
                    background-color: #16A34A;
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 32px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #15803D;
                }
            """)
            self.update_detected.emit(info)

            # Changelog HTML
            html = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Arial; color: #0F172A; padding: 6px;">
                <h3 style="color: #1E3A8A; margin-bottom: 4px;">
                    🎉 يتوفر إصدار جديد جاهز للتحميل: WafraCut Pro v{info.version}
                </h3>
                <p style="color: #64748B; font-size: 11px; margin-top: 0px;">
                    تاريخ الإصدار: {info.release_date or 'الآن'} | الحجم التقريبي: {info.file_size_mb:.1f} MB
                </p>
                <hr style="border: 0; border-top: 1px solid #E2E8F0;" />
                <h4 style="color: #0F766E;">ما الجديد في هذا الإصدار:</h4>
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-top: 6px; font-size: 12px; line-height: 1.6;">
                    {info.changelog_ar.replace(chr(10), '<br>') if info.changelog_ar else 'تحسينات في الأداء وإصلاحات شاملة.'}
                </div>
            </div>
            """
            self.txt_changelog.setHtml(html)

        else:
            self._set_card_val(self.card_status, "✅ أنت على أحدث إصدار", "#059669")
            self.btn_action.setEnabled(True)
            self.btn_action.setText("🔄 التحقق من وجود تحديثات جديدة")
            self.btn_action.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 32px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1D4ED8;
                }
            """)

            html = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Arial; color: #0F172A; padding: 14px; text-align: center;">
                <h3 style="color: #059669; margin-bottom: 8px;">
                    ✅ برنامج WafraCut Pro محدّث بالكامل (v{self.mgr.current_version})
                </h3>
                <p style="color: #64748B; font-size: 12px;">
                    أنت تستخدم آخر إصدار مستقر من محرك التقطيع والتحسين الرياضي.
                </p>
            </div>
            """
            self.txt_changelog.setHtml(html)

    def _start_download(self):
        if not self.latest_info or not self.latest_info.download_url:
            QMessageBox.warning(self, "خطأ", "لا يوجد رابط تنزيل مباشر متاح لهذا التحديث.")
            return

        self.btn_action.setEnabled(False)
        self.btn_action.setText("⏳ جاري تنزيل التحديث...")
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.lbl_progress_status.show()
        self.lbl_progress_status.setText("بدء تنزيل حزمة التحديث...")

        updates_dir = Path.home() / ".steelnest_pro" / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        file_ext = ".exe"
        if ".zip" in self.latest_info.download_url.lower():
            file_ext = ".zip"
        target_file = updates_dir / f"WafraCutPro_v{self.latest_info.version}{file_ext}"

        self.downloader = UpdateDownloaderThread(
            download_url=self.latest_info.download_url,
            target_path=str(target_file),
            parent=self
        )
        self.downloader.progress_changed.connect(self._on_download_progress)
        self.downloader.download_finished.connect(self._on_download_finished)
        self.downloader.download_failed.connect(self._on_download_failed)
        self.downloader.start()

    def _on_download_progress(self, pct: int, downloaded: int, total: int):
        self.progress_bar.setValue(pct)
        mb_down = downloaded / (1024 * 1024)
        mb_tot = total / (1024 * 1024) if total > 0 else 0
        if total > 0:
            self.lbl_progress_status.setText(f"تم تنزيل {mb_down:.1f} MB من {mb_tot:.1f} MB ({pct}%)")
        else:
            self.lbl_progress_status.setText(f"تم تنزيل {mb_down:.1f} MB...")

    def _on_download_finished(self, file_path: str):
        self.lbl_progress_status.setText("✅ اكتمل التنزيل بنجاح!")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("🚀 تثبيت التحديث الآن وإعادة التشغيل")
        ans = QMessageBox.question(
            self,
            "تثبيت التحديث",
            f"تم تنزيل التحديث بنجاح (v{self.latest_info.version})!\n\n"
            f"هل تريد إغلاق البرنامج وتطبيق التحديث وإعادة تشغيله تلقائياً الآن؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            UpdateManager.apply_update_and_restart(file_path)
        else:
            QMessageBox.information(
                self,
                "تم حفظ الملف",
                f"تم حفظ ملف التحديث في:\n{file_path}\n\nيمكنك تثبيته في أي وقت."
            )

    def _on_download_failed(self, err_msg: str):
        self.lbl_progress_status.setText(f"❌ فشل التنزيل: {err_msg}")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("🔄 إعادة المحاولة")
        QMessageBox.critical(self, "خطأ في التنزيل", f"تعذر تنزيل ملف التحديث:\n{err_msg}")


class UpdateDialog(QDialog):
    """Popup modal dialog version of the Update Center."""
    def __init__(self, update_manager: UpdateManager, preloaded_info: UpdateInfo = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WafraCut Pro — تحديث البرنامج")
        self.resize(640, 520)
        self.setMinimumSize(560, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.center_widget = UpdateCenterWidget(update_manager, preloaded_info=preloaded_info, parent=self)
        layout.addWidget(self.center_widget)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("إغلاق (Close)", self)
        btn_close.setStyleSheet("padding: 6px 18px; font-weight: bold;")
        btn_close.clicked.connect(self.close)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)
