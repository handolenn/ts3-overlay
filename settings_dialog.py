import os
import webbrowser
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSpinBox, QSlider, QCheckBox, QPushButton, QColorDialog, QTabWidget,
    QWidget, QLabel, QGroupBox, QFontComboBox
)
from PyQt6.QtGui import QColor, QFont, QIcon

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON_PATH = os.path.join(SCRIPT_DIR, "icon", "gecmisolsun.png")


class SettingsDialog(QDialog):
    def __init__(self, config_manager, overlay_window, ts3_thread=None, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.overlay = overlay_window
        self.ts3_thread = ts3_thread
        
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        if os.path.exists(APP_ICON_PATH):
            self.setWindowIcon(QIcon(APP_ICON_PATH))

        self.setWindowTitle("gecmisolsunun TS3 overlay'ı")
        self.setMinimumWidth(480)
        self.setMinimumHeight(550)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a46;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                background-color: #262630;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #f5e663;
            }
            QLabel {
                color: #d0d0d8;
            }
            QPushButton {
                background-color: #3a3a4c;
                color: #ffffff;
                border: 1px solid #525266;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a60;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #3a3a46;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f5e663;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a46;
                background: #23232c;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #181820;
                color: #a0a0b0;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #23232c;
                color: #f5e663;
                font-weight: bold;
            }
        """)

        self.init_ui()
        self.connect_signals()

        if self.ts3_thread:
            self.ts3_thread.connected_signal.connect(self.update_connection_status)

    def closeEvent(self, event):
        from PyQt6.QtWidgets import QApplication
        if self.ts3_thread:
            self.ts3_thread.stop()
        if self.overlay:
            self.overlay.close()
        app = QApplication.instance()
        if app:
            app.quit()
        event.accept()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Top Control Bar (Overlay Toggle & Status) ---
        top_box = QGroupBox("Genel Durum & Güç Kontrolü")
        top_layout = QHBoxLayout(top_box)
        
        self.toggle_overlay_btn = QPushButton()
        self.update_toggle_btn_state()
        
        self.status_label = QLabel("Bağlı" if self.config.get("overlay_enabled", True) else "Kapalı")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        top_layout.addWidget(self.toggle_overlay_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.status_label)
        main_layout.addWidget(top_box)

        # Tabs
        tabs = QTabWidget(self)

        # --- Tab 1: Görünüm & Boyutlar ---
        app_tab = QWidget()
        app_layout = QVBoxLayout(app_tab)
        app_layout.setSpacing(10)

        # Fonts & Sizes
        size_group = QGroupBox("Yazı Boyutları")
        size_layout = QFormLayout(size_group)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.config.get("font_family", "Segoe UI")))

        self.chan_size_spin = QSpinBox()
        self.chan_size_spin.setRange(5, 48)
        self.chan_size_spin.setValue(self.config.get("channel_font_size", 14))

        self.user_size_spin = QSpinBox()
        self.user_size_spin.setRange(4, 36)
        self.user_size_spin.setValue(self.config.get("user_font_size", 11))

        self.chat_size_spin = QSpinBox()
        self.chat_size_spin.setRange(4, 30)
        self.chat_size_spin.setValue(self.config.get("chat_font_size", 11))

        size_layout.addRow("Yazı Tipi (Font):", self.font_combo)
        size_layout.addRow("Kanal Yazı Boyutu:", self.chan_size_spin)
        size_layout.addRow("Kullanıcı Yazı Boyutu:", self.user_size_spin)
        size_layout.addRow("Chat Mesaj Boyutu:", self.chat_size_spin)
        app_layout.addWidget(size_group)

        # Colors
        color_group = QGroupBox("Renkler")
        color_layout = QFormLayout(color_group)

        self.chan_color_btn = QPushButton("Kanal Rengi Seç")
        self.chan_color = self.config.get("channel_color", "#F5E663")
        self.update_btn_color(self.chan_color_btn, self.chan_color)

        self.user_color_btn = QPushButton("Kullanıcı Rengi Seç")
        self.user_color = self.config.get("user_color", "#FFFFFF")
        self.update_btn_color(self.user_color_btn, self.user_color)

        self.talking_color_btn = QPushButton("Konuşma Rengi Seç")
        self.talking_color = self.config.get("talking_color", "#55FF55")
        self.update_btn_color(self.talking_color_btn, self.talking_color)

        self.cc_color_btn = QPushButton("CC İndikatör Rengi Seç")
        self.cc_color = self.config.get("cc_color", "#FF8A00")
        self.update_btn_color(self.cc_color_btn, self.cc_color)

        color_layout.addRow("Kanal Başlık Rengi:", self.chan_color_btn)
        color_layout.addRow("Kullanıcı Yazı Rengi:", self.user_color_btn)
        color_layout.addRow("Konuşan İndikatör Rengi:", self.talking_color_btn)
        color_layout.addRow("Channel Commander Rengi:", self.cc_color_btn)
        app_layout.addWidget(color_group)

        # Effects & Modes (Demo mode)
        fx_group = QGroupBox("Görsel Efektler & Modlar")
        fx_layout = QVBoxLayout(fx_group)

        self.whisper_warning_cb = QCheckBox("'WHISPER BASIYORSUN' Uyarısını Göster")
        self.whisper_warning_cb.setChecked(self.config.get("show_whisper_warning", True))

        self.demo_mode_cb = QCheckBox("Test / Demo Modunu Etkinleştir (Örnek Verileri Göster)")
        self.demo_mode_cb.setChecked(self.config.get("demo_mode", False))

        self.shadow_cb = QCheckBox("Metin Gölgesi / Kontrast Kaplama Açık")
        self.shadow_cb.setChecked(self.config.get("text_shadow", True))

        self.chat_msg_cb = QCheckBox("Gelen Chat Mesajlarını Altta Göster")
        self.chat_msg_cb.setChecked(self.config.get("show_chat_messages", True))

        fx_layout.addWidget(self.whisper_warning_cb)
        fx_layout.addWidget(self.demo_mode_cb)
        fx_layout.addWidget(self.shadow_cb)
        fx_layout.addWidget(self.chat_msg_cb)
        app_layout.addWidget(fx_group)

        tabs.addTab(app_tab, "Görünüm & Boyutlar")

        # --- Tab 2: Konum & Ekran Mesafe Ayarları ---
        pos_tab = QWidget()
        pos_layout = QVBoxLayout(pos_tab)
        pos_layout.setSpacing(10)

        pos_group = QGroupBox("Ekranda İnce Konumlandırma")
        pos_form = QFormLayout(pos_group)

        self.x_slider = QSlider(Qt.Orientation.Horizontal)
        self.x_slider.setRange(0, 2500)
        self.x_slider.setValue(self.config.get("x_offset", 30))

        self.y_slider = QSlider(Qt.Orientation.Horizontal)
        self.y_slider.setRange(0, 1500)
        self.y_slider.setValue(self.config.get("y_offset", 220))

        pos_form.addRow("Ekran Sağ Çerçeve Mesafesi (X):", self.x_slider)
        pos_form.addRow("Ekran Üst Çerçeve Mesafesi (Y):", self.y_slider)
        pos_layout.addWidget(pos_group)

        drag_group = QGroupBox("Serbest Sürükleme Modu")
        drag_box = QVBoxLayout(drag_group)

        self.drag_btn = QPushButton("Overlay Konumunu Farenizle Taşıyın")
        self.drag_btn.setCheckable(True)
        self.drag_btn.setChecked(self.overlay.is_unlocked)
        drag_box.addWidget(self.drag_btn)

        drag_info = QLabel("Sürükleme modunu açtıktan sonra ekranın sağ tarafındaki overlay kutusunu fare ile istediğiniz yere taşıyabilirsiniz.")
        drag_info.setWordWrap(True)
        drag_box.addWidget(drag_info)
        pos_layout.addWidget(drag_group)
        pos_layout.addStretch()

        tabs.addTab(pos_tab, "Konumlandırma")

        # --- Tab 3: Güncelleme ---
        update_tab = QWidget()
        update_layout = QVBoxLayout(update_tab)
        update_layout.setSpacing(12)

        update_group = QGroupBox("Sürüm & Güncelleme Kontrolü")
        update_box = QVBoxLayout(update_group)
        update_box.setSpacing(10)

        version_label = QLabel("Sürümü: v1.0.0")
        version_label.setStyleSheet("font-weight: bold; color: #55ff55; font-size: 13px;")
        update_box.addWidget(version_label)

        lorem_info = QLabel(
            "Projeye veri gönderen ve veri alan herhangi bir kod eklemediğim için"
            "projenin güncelliğini manuel olarak kendiniz kontrol etmelisiniz. "
            "En son güncellemeleri, performans iyileştirmelerini ve yeni sürümleri "
            "GitHub sayfamdan kontrol edebilirsiniz."
            "Projenin .exe'ye buildlenmiş herhangi bir dosyası yoktur, görürseniz de indirmeyin iyi geceler."
        )
        lorem_info.setWordWrap(True)
        lorem_info.setStyleSheet("color: #b0b0c0; line-height: 1.4;")
        update_box.addWidget(lorem_info)

        github_btn = QPushButton("GitHub Sayfasına Git ve Güncellemeleri Kontrol Et")
        github_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b5278;
                color: #ffffff;
                border: 1px solid #3b6898;
                padding: 10px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #38628e;
            }
        """)
        github_btn.clicked.connect(self.open_github_link)
        update_box.addWidget(github_btn)

        update_layout.addWidget(update_group)
        update_layout.addStretch()

        tabs.addTab(update_tab, "Güncelleme")

        main_layout.addWidget(tabs)

        # Bottom Close Button
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Kapat")
        close_btn.setStyleSheet("background-color: #525266; padding: 8px 24px;")
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

    def open_github_link(self):
        webbrowser.open("https://github.com/handolenn/ts3-overlay")

    def connect_signals(self):
        """Connect UI signals AFTER widgets are populated to avoid overwrite bugs."""
        self.toggle_overlay_btn.clicked.connect(self.toggle_overlay_power)
        self.font_combo.currentFontChanged.connect(self.on_live_change)
        self.chan_size_spin.valueChanged.connect(self.on_live_change)
        self.user_size_spin.valueChanged.connect(self.on_live_change)
        self.chat_size_spin.valueChanged.connect(self.on_live_change)
        self.chan_color_btn.clicked.connect(self.choose_chan_color)
        self.user_color_btn.clicked.connect(self.choose_user_color)
        self.talking_color_btn.clicked.connect(self.choose_talking_color)
        self.cc_color_btn.clicked.connect(self.choose_cc_color)
        self.whisper_warning_cb.toggled.connect(self.on_live_change)
        self.demo_mode_cb.toggled.connect(self.on_live_change)
        self.shadow_cb.toggled.connect(self.on_live_change)
        self.chat_msg_cb.toggled.connect(self.on_live_change)
        self.x_slider.valueChanged.connect(self.on_live_change)
        self.y_slider.valueChanged.connect(self.on_live_change)
        self.drag_btn.clicked.connect(self.toggle_drag_mode)

    def update_toggle_btn_state(self):
        enabled = self.config.get("overlay_enabled", True)
        if enabled:
            self.toggle_overlay_btn.setText("OVERLAY AÇIK (Kapatmak İçin Tıklayın)")
            self.toggle_overlay_btn.setStyleSheet("background-color: #2e7d32; color: #ffffff; font-size: 13px;")
        else:
            self.toggle_overlay_btn.setText("OVERLAY KAPALI (Açmak İçin Tıklayın)")
            self.toggle_overlay_btn.setStyleSheet("background-color: #c62828; color: #ffffff; font-size: 13px;")

    def toggle_overlay_power(self):
        current = self.config.get("overlay_enabled", True)
        new_state = not current
        self.config.set("overlay_enabled", new_state)
        self.update_toggle_btn_state()
        
        if new_state:
            self.overlay.show()
            self.status_label.setText("Aktif")
            self.status_label.setStyleSheet("color: #55ff55; font-weight: bold; font-size: 14px;")
        else:
            self.overlay.hide()
            self.status_label.setText("Kapalı")
            self.status_label.setStyleSheet("color: #ff5555; font-weight: bold; font-size: 14px;")

    def update_btn_color(self, btn, hex_color):
        btn.setStyleSheet(f"background-color: {hex_color}; color: #000000; font-weight: bold; border-radius: 4px;")

    def choose_chan_color(self):
        col = QColorDialog.getColor(QColor(self.chan_color), self, "Kanal Başlık Rengi")
        if col.isValid():
            self.chan_color = col.name()
            self.update_btn_color(self.chan_color_btn, self.chan_color)
            self.on_live_change()

    def choose_user_color(self):
        col = QColorDialog.getColor(QColor(self.user_color), self, "Kullanıcı Yazı Rengi")
        if col.isValid():
            self.user_color = col.name()
            self.update_btn_color(self.user_color_btn, self.user_color)
            self.on_live_change()

    def choose_talking_color(self):
        col = QColorDialog.getColor(QColor(self.talking_color), self, "Konuşan İndikatör Rengi")
        if col.isValid():
            self.talking_color = col.name()
            self.update_btn_color(self.talking_color_btn, self.talking_color)
            self.on_live_change()

    def choose_cc_color(self):
        col = QColorDialog.getColor(QColor(self.cc_color), self, "Channel Commander İndikatör Rengi")
        if col.isValid():
            self.cc_color = col.name()
            self.update_btn_color(self.cc_color_btn, self.cc_color)
            self.on_live_change()

    def toggle_drag_mode(self, checked):
        self.overlay.set_unlocked(checked)
        if checked:
            self.drag_btn.setText("Konumu Kilitle (Oyun Modu & Kaydet)")
        else:
            self.drag_btn.setText("Overlay Konumunu Farenizle Taşıyın")
            # Sync sliders with current dragged position
            self.x_slider.blockSignals(True)
            self.y_slider.blockSignals(True)
            self.x_slider.setValue(self.config.get("x_offset", 30))
            self.y_slider.setValue(self.config.get("y_offset", 220))
            self.x_slider.blockSignals(False)
            self.y_slider.blockSignals(False)

    def update_connection_status(self, is_connected, msg):
        if is_connected:
            self.status_label.setText(f"{msg}")
            self.status_label.setStyleSheet("color: #55ff55; font-weight: bold;")
        else:
            self.status_label.setText(f"{msg}")
            self.status_label.setStyleSheet("color: #ff5555; font-weight: bold;")

    def on_live_change(self):
        """Called immediately whenever any slider, input or setting is modified."""
        self.config.set("font_family", self.font_combo.currentFont().family())
        self.config.set("channel_font_size", self.chan_size_spin.value())
        self.config.set("user_font_size", self.user_size_spin.value())
        self.config.set("chat_font_size", self.chat_size_spin.value())
        self.config.set("channel_color", self.chan_color)
        self.config.set("user_color", self.user_color)
        self.config.set("talking_color", self.talking_color)
        self.config.set("cc_color", self.cc_color)
        self.config.set("show_whisper_warning", self.whisper_warning_cb.isChecked())
        self.config.set("demo_mode", self.demo_mode_cb.isChecked())
        self.config.set("text_shadow", self.shadow_cb.isChecked())
        self.config.set("show_chat_messages", self.chat_msg_cb.isChecked())
        self.config.set("x_offset", self.x_slider.value())
        self.config.set("y_offset", self.y_slider.value())

        # Instantly update overlay visually on screen
        self.overlay.apply_config()
