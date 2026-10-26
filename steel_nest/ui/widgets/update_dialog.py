"""
WafraCut Pro - Update Center Widget & Dialog
Provides user-facing interface for checking, reviewing changelogs,
downloading, and installing software updates both as an embedded tab
and as an interactive popup dialog.
"""
import os
import sys
import webbrowser
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QCheckBox, QLineEdit,
    QMessageBox, QGroupBox, QInputDialog
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon

from steel_nest.config import APP_VERSION, APP_NAME
from steel_nest.updater.update_manager import (
    UpdateManager, UpdateInfo, UpdateCheckerThread, UpdateDownloaderThread
)
from steel_nest.ui.icon_manager import IconManager


class UpdateCenterWidget(QWidget):
    """
    Embedded widget providing full update center capabilities:
    version status cards, rich changelog viewing, check trigger,
    progress tracking, and one-click self-updating.
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
                padding: 12px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(14, 10, 14, 10)

        lbl_icon = QLabel("🚀")
        lbl_icon.setFont(QFont("Segoe UI Emoji", 26))
        h_layout.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        lbl_title = QLabel("مركز التحديثات الذكي — WafraCut Pro Update Center")
        lbl_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF;")
        lbl_sub = QLabel("تحقق تلقائي وسلس من أحدث الميزات، التحسينات الهندسية، وتحديثات الخوارزميات")
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

        # Card 1: Current Version
        self.card_cur = self._create_card(
            "الإصدار المثبت (Installed)",
            f"v{self.mgr.current_version}",
            "#F1F5F9", "#334155"
        )
        cards_layout.addWidget(self.card_cur)

        # Card 2: Latest Version Available
        self.card_latest = self._create_card(
            "أحدث إصدار (Latest)",
            "—",
            "#FEF3C7", "#92400E"
        )
        cards_layout.addWidget(self.card_latest)

        # Card 3: Status Badge
        self.card_status = self._create_card(
            "حالة التحديث (Status)",
            "جاهز للفحص",
            "#E0E7FF", "#3730A3"
        )
        cards_layout.addWidget(self.card_status)

        main_layout.addLayout(cards_layout)

        # 3. Changelog / Release Notes
        lbl_notes = QLabel("📋 سجل التحديثات والميزات الجديدة (What's New in this Release):")
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
            "اضغط على زر 'التحقق الآن' للبحث عن تحديثات جديدة وسير التغييرات..."
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

        # 5. Options (Auto-check checkbox & Manifest URL)
        opt_layout = QHBoxLayout()
        self.chk_auto = QCheckBox("التحقق التلقائي من التحديثات عند بدء تشغيل البرنامج (Auto-check on startup)", self)
        self.chk_auto.setChecked(self.mgr.auto_check)
        self.chk_auto.toggled.connect(self._on_auto_check_toggled)
        opt_layout.addWidget(self.chk_auto)

        opt_layout.addStretch()

        btn_config_url = QPushButton("⚙️ تخصيص رابط الخادم (Manifest URL)", self)
        btn_config_url.setStyleSheet("""
            QPushButton {
                background: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                color: #334155;
            }
            QPushButton:hover {
                background: #E2E8F0;
            }
        """)
        btn_config_url.clicked.connect(self._configure_manifest_url)
        opt_layout.addWidget(btn_config_url)

        main_layout.addLayout(opt_layout)

        # 6. Action Buttons Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_check = QPushButton("🔄 فحص التحديثات (Check Now)", self)
        self.btn_check.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                padding: 8px 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_check.clicked.connect(self._check_updates)
        btn_bar.addWidget(self.btn_check)

        self.btn_browser = QPushButton("🌐 صفحة الإصدار (Release Page)", self)
        self.btn_browser.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                padding: 8px 12px;
                border-radius: 5px;
                color: #1E293B;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        self.btn_browser.setEnabled(False)
        self.btn_browser.clicked.connect(self._open_in_browser)
        btn_bar.addWidget(self.btn_browser)

        btn_bar.addStretch()

        self.btn_install = QPushButton("⬇️ تنزيل وتثبيت التحديث (Install)", self)
        self.btn_install.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: #FFFFFF;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #15803D;
            }
            QPushButton:disabled {
                background-color: #94A3B8;
                color: #E2E8F0;
            }
        """)
        self.btn_install.setEnabled(False)
        self.btn_install.clicked.connect(self._start_download)
        btn_bar.addWidget(self.btn_install)

        main_layout.addLayout(btn_bar)

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
        v.addWidget(lbl_v)
        return card

    def _set_card_val(self, card: QFrame, val: str, fg: str = None):
        lbl = card.findChild(QLabel, "val")
        if lbl:
            lbl.setText(val)
            if fg:
                lbl.setStyleSheet(f"color: {fg};")

    def _on_auto_check_toggled(self, checked: bool):
        self.mgr.set_auto_check(checked)

    def _configure_manifest_url(self):
        cur_url = self.mgr.manifest_url
        new_url, ok = QInputDialog.getText(
            self,
            "تخصيص رابط التحديثات (Update Manifest URL)",
            "أدخل رابط ملف version.json على خادمك أو GitHub:\n"
            "(مثال: https://raw.githubusercontent.com/user/repo/main/version.json)",
            QLineEdit.EchoMode.Normal,
            cur_url
        )
        if ok and new_url.strip():
            self.mgr.set_custom_manifest_url(new_url.strip())
            QMessageBox.information(
                self,
                "تم حفظ الرابط",
                f"تم تحديث رابط خادم التحديثات بنجاح إلى:\n{new_url.strip()}"
            )

    def refresh_view(self):
        """Called when opening or switching to the tab."""
        if self.mgr.cached_latest_info:
            self._display_update_info(self.mgr.cached_latest_info)
        else:
            self._check_updates()

    def _check_updates(self):
        self._set_card_val(self.card_status, "جاري الفحص...", "#2563EB")
        self._set_card_val(self.card_latest, "جاري الاتصال...", "#64748B")
        self.btn_check.setEnabled(False)
        self.btn_install.setEnabled(False)

        self.checker = UpdateCheckerThread(self.mgr, parent=self)
        self.checker.check_finished.connect(self._on_check_finished)
        self.checker.check_failed.connect(self._on_check_failed)
        self.checker.start()

    def _on_check_finished(self, info: UpdateInfo):
        self.btn_check.setEnabled(True)
        self.latest_info = info
        self._display_update_info(info)

    def _on_check_failed(self, err_msg: str):
        self.btn_check.setEnabled(True)
        self._set_card_val(self.card_status, "فشل الاتصال بالخادم", "#DC2626")
        self._set_card_val(self.card_latest, "غير متاح", "#64748B")
        self.txt_changelog.setHtml(
            f"<div style='color: #DC2626; padding: 10px; font-family: Segoe UI;'>"
            f"<b>تعذر التحقق من التحديثات:</b><br>{err_msg}<br><br>"
            f"تأكد من الاتصال بالإنترنت أو صحة رابط الخادم في الإعدادات."
            f"</div>"
        )

    def _display_update_info(self, info: UpdateInfo):
        self._set_card_val(self.card_latest, f"v{info.version}", "#047857")

        if info.has_update:
            self._set_card_val(self.card_status, "🚀 يوجد تحديث جديد متاح!", "#16A34A")
            self.btn_install.setEnabled(bool(info.download_url))
            self.btn_browser.setEnabled(bool(info.release_url or info.download_url))
            self.update_detected.emit(info)

            # Build formatted changelog HTML
            html = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Arial; color: #0F172A; padding: 8px;">
                <h3 style="color: #1E3A8A; margin-bottom: 4px;">
                    🎉 إصدار جديد متاح الآن: WafraCut Pro v{info.version}
                </h3>
                <p style="color: #64748B; font-size: 11px; margin-top: 0px;">
                    تاريخ الإصدار: {info.release_date or 'الآن'} | الحجم التقريبي: {info.file_size_mb:.1f} MB
                </p>
                <hr style="border: 0; border-top: 1px solid #E2E8F0;" />
                <h4 style="color: #0F766E;">ما الجديد في هذا التحديث (Changelog):</h4>
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-top: 6px;">
                    {info.changelog_ar.replace(chr(10), '<br>') if info.changelog_ar else 'تحسينات في الأداء وإصلاحات برمجية شاملة.'}
                </div>
            """
            if info.changelog_en:
                html += f"""
                <h4 style="color: #334155; margin-top: 12px;">English Release Notes:</h4>
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-top: 6px;">
                    {info.changelog_en.replace(chr(10), '<br>')}
                </div>
                """
            html += "</div>"
            self.txt_changelog.setHtml(html)

        else:
            self._set_card_val(self.card_status, "✅ البرنامج بأحدث إصدار", "#059669")
            self.btn_install.setEnabled(False)
            self.btn_browser.setEnabled(bool(info.release_url))

            html = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Arial; color: #0F172A; padding: 12px; text-align: center;">
                <h3 style="color: #059669; margin-bottom: 8px;">
                    ✅ أنت تستخدم أحدث إصدار من البرنامج (v{self.mgr.current_version})
                </h3>
                <p style="color: #64748B;">
                    نظام القص وتقطيع الشيتات والقطاعات يعمل بأحدث كفاءة وخوارزميات محسنة.
                </p>
                <div style="text-align: right; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-top: 14px;">
                    <b>سجل الإصدار الحالي v{info.version}:</b><br>
                    {info.changelog_ar.replace(chr(10), '<br>') if info.changelog_ar else 'إصدار مستقر بكافة الميزات المتطورة.'}
                </div>
            </div>
            """
            self.txt_changelog.setHtml(html)

    def _open_in_browser(self):
        if not self.latest_info:
            return
        url = self.latest_info.release_url or self.latest_info.download_url
        if url:
            webbrowser.open(url)

    def _start_download(self):
        if not self.latest_info or not self.latest_info.download_url:
            QMessageBox.warning(self, "خطأ", "لا يوجد رابط تنزيل مباشر متاح لهذا التحديث.")
            return

        self.btn_install.setEnabled(False)
        self.btn_check.setEnabled(False)
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
        ans = QMessageBox.question(
            self,
            "تثبيت التحديث",
            f"تم تنزيل التحديث بنجاح (v{self.latest_info.version})!\n\n"
            f"هل تريد إغلاق البرنامج الآن وتطبيق التحديث وإعادة تشغيله تلقائياً؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            UpdateManager.apply_update_and_restart(file_path)
        else:
            QMessageBox.information(
                self,
                "تم حفظ الملف",
                f"تم حفظ ملف التحديث في المسار التالي:\n{file_path}\n\nيمكنك تثبيته يدوياً في أي وقت."
            )
            self.btn_install.setEnabled(True)
            self.btn_check.setEnabled(True)

    def _on_download_failed(self, err_msg: str):
        self.lbl_progress_status.setText(f"❌ فشل التنزيل: {err_msg}")
        self.btn_install.setEnabled(True)
        self.btn_check.setEnabled(True)
        QMessageBox.critical(self, "خطأ في التنزيل", f"تعذر تنزيل ملف التحديث:\n{err_msg}")


class UpdateDialog(QDialog):
    """Popup modal dialog version of the Update Center."""
    def __init__(self, update_manager: UpdateManager, preloaded_info: UpdateInfo = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WafraCut Pro — مركز التحديثات (Update Center)")
        self.resize(680, 580)
        self.setMinimumSize(600, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.center_widget = UpdateCenterWidget(update_manager, preloaded_info=preloaded_info, parent=self)
        layout.addWidget(self.center_widget)

        # Dialog close button row
        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("إغلاق (Close)", self)
        btn_close.setStyleSheet("padding: 7px 18px; font-weight: bold;")
        btn_close.clicked.connect(self.close)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)
