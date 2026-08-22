import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt
from settings_dialog import SettingsDialog

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON_PATH = os.path.join(SCRIPT_DIR, "icon", "gecmisolsun.png")


def create_tray_pixmap():
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw rounded shield / square badge
    painter.setBrush(QColor(30, 30, 30))
    painter.setPen(QColor(245, 230, 99))
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)

    # Draw TS text
    painter.setPen(QColor(245, 230, 99))
    painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "TS")
    painter.end()

    return pixmap


class TrayIconManager(QSystemTrayIcon):
    def __init__(self, app, config_manager, overlay_window, ts3_thread):
        if os.path.exists(APP_ICON_PATH):
            icon = QIcon(APP_ICON_PATH)
        else:
            icon = QIcon(create_tray_pixmap())

        super().__init__(icon, app)

        self.app = app
        self.config = config_manager
        self.overlay = overlay_window
        self.ts3_thread = ts3_thread
        self.settings_dialog = None

        self.setToolTip("TS3 Overlay Kontrol Paneli")
        self.init_menu()

    def init_menu(self):
        menu = QMenu()

        self.power_action = menu.addAction("Overlay Açık")
        self.power_action.setCheckable(True)
        self.power_action.setChecked(self.config.get("overlay_enabled", True))
        self.power_action.triggered.connect(self.toggle_power)

        menu.addSeparator()

        settings_action = menu.addAction("Kontrol Paneli (Ayarlar & Önizleme)")
        settings_action.triggered.connect(self.open_settings)

        self.drag_action = menu.addAction("Konumu Taşı (Sürükleme Modu)")
        self.drag_action.setCheckable(True)
        self.drag_action.setChecked(self.overlay.is_unlocked)
        self.drag_action.triggered.connect(self.toggle_drag)

        self.demo_action = menu.addAction("Demo Modu (Örnek Görünüm)")
        self.demo_action.setCheckable(True)
        self.demo_action.setChecked(self.config.get("demo_mode", False))
        self.demo_action.triggered.connect(self.toggle_demo)

        menu.addSeparator()

        quit_action = menu.addAction("Çıkış")
        quit_action.triggered.connect(self.quit_app)

        self.setContextMenu(menu)
        self.activated.connect(self.on_tray_activated)

    def toggle_power(self, checked):
        self.config.set("overlay_enabled", checked)
        if checked:
            self.overlay.show()
            self.power_action.setText("Overlay Açık")
        else:
            self.overlay.hide()
            self.power_action.setText("Overlay Kapalı")
            
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.update_toggle_btn_state()

    def toggle_drag(self, checked):
        self.overlay.set_unlocked(checked)
        self.drag_action.setChecked(checked)

    def toggle_demo(self, checked):
        self.config.set("demo_mode", checked)
        self.demo_action.setChecked(checked)
        self.overlay.apply_config()

    def open_settings(self):
        if not self.settings_dialog or not self.settings_dialog.isVisible():
            self.settings_dialog = SettingsDialog(self.config, self.overlay, self.ts3_thread)
            self.settings_dialog.show()
        else:
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.open_settings()

    def quit_app(self):
        self.ts3_thread.stop()
        self.overlay.close()
        self.app.quit()
