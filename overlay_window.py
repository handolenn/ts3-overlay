import sys
import os
import re
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect, QFrame, QGraphicsOpacityEffect
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MIC_MUTE_ICON_PATH = os.path.join(SCRIPT_DIR, "icon", "mikrofon_mute.png")
HEADPHONE_MUTE_ICON_PATH = os.path.join(SCRIPT_DIR, "icon", "kulaklik_mute.png")
OVERLAY_FIXED_WIDTH = 320


def create_circle_pixmap(color_hex: str, size: int = 10) -> QPixmap:
    """Create a crisp, perfectly round anti-aliased vector circle icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    color = QColor(color_hex)
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(QColor(0, 0, 0, 140), 1))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return pix


def break_long_words(text: str, max_len: int = 28) -> str:
    """Break long unspaced character sequences (e.g., aaaaaa...) so Qt layout wraps them cleanly."""
    words = text.split(" ")
    processed_words = []
    for w in words:
        if len(w) > max_len:
            chunks = [w[i:i+max_len] for i in range(0, len(w), max_len)]
            processed_words.append(" ".join(chunks))
        else:
            processed_words.append(w)
    return " ".join(processed_words)


class AnimatedChatLabel(QLabel):
    """Custom Label with smooth Fade-In, 3-Second display, and Fade-Out animations in a bounded box."""
    def __init__(self, html_text, font, text_shadow=True, duration_ms=3000, on_destroy_cb=None, parent=None):
        super().__init__(html_text, parent)
        self.on_destroy_cb = on_destroy_cb
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setWordWrap(True)
        self.setFixedWidth(OVERLAY_FIXED_WIDTH)
        self.setStyleSheet("background: transparent;")

        if text_shadow:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(6)
            shadow.setColor(QColor(0, 0, 0, 240))
            shadow.setOffset(1, 1)
            self.setGraphicsEffect(shadow)

        # Opacity Effect for Fade In / Out
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        # Fade In Animation (300 ms)
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Fade Out Animation (500 ms)
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(500)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_out.finished.connect(self._on_fade_out_finished)

        # 3-Second Display Timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out.start)

    def start_animation(self, duration_ms=3000):
        self.fade_in.start()
        self.timer.start(duration_ms)

    def _on_fade_out_finished(self):
        if self.on_destroy_cb:
            self.on_destroy_cb(self)
        self.setParent(None)
        self.deleteLater()


class OverlayWindow(QWidget):
    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.channel_name = "Kanal"
        self.users = []
        self.active_chat_labels = []
        self.drag_position = QPoint()
        self.is_unlocked = False  # When True, user can drag window

        self.init_ui()
        self.apply_config()

    def init_ui(self):
        # Frameless, Always on Top, Tool Window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(OVERLAY_FIXED_WIDTH)

        # Main Layout (0 margins so text aligns flush to right screen edge)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        # Container Frame
        self.container = QFrame(self)
        self.container.setFixedWidth(OVERLAY_FIXED_WIDTH)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Dedicated Fixed-Height Container for Whisper Warning (Prevents downward layout shift)
        self.whisper_widget = QWidget(self.container)
        self.whisper_widget.setFixedWidth(OVERLAY_FIXED_WIDTH)
        self.whisper_widget.setFixedHeight(22)
        
        self.whisper_layout = QVBoxLayout(self.whisper_widget)
        self.whisper_layout.setContentsMargins(0, 0, 0, 0)
        self.whisper_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.whisper_label = QLabel("WHISPER BASIYORSUN", self.whisper_widget)
        self.whisper_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.whisper_label.setFixedWidth(OVERLAY_FIXED_WIDTH)
        whisper_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        self.whisper_label.setFont(whisper_font)
        self.whisper_label.setStyleSheet("color: #FF3333; background: transparent; font-weight: bold;")
        self.whisper_label.hide()

        self.whisper_layout.addWidget(self.whisper_label)

        # Channel Header Label
        self.channel_label = QLabel(self.channel_name, self.container)
        self.channel_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.channel_label.setFixedWidth(OVERLAY_FIXED_WIDTH)

        # Users Container Widget
        self.users_widget = QWidget(self.container)
        self.users_widget.setFixedWidth(OVERLAY_FIXED_WIDTH)
        self.users_layout = QVBoxLayout(self.users_widget)
        self.users_layout.setContentsMargins(0, 0, 0, 0)
        self.users_layout.setSpacing(4)
        self.users_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Chat Container Widget (Bounded Box Container fixed width 320px)
        self.chat_widget = QWidget(self.container)
        self.chat_widget.setFixedWidth(OVERLAY_FIXED_WIDTH)
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(0, 4, 0, 0)
        self.chat_layout.setSpacing(3)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.container_layout.addWidget(self.whisper_widget)
        self.container_layout.addWidget(self.channel_label)
        self.container_layout.addWidget(self.users_widget)
        self.container_layout.addWidget(self.chat_widget)
        self.main_layout.addWidget(self.container)

        self.setLayout(self.main_layout)

    def apply_config(self):
        font_family = self.config.get("font_family", "Segoe UI")
        chan_size = self.config.get("channel_font_size", 14)
        chan_color = self.config.get("channel_color", "#F5E663")

        # Channel header style
        chan_font = QFont(font_family, chan_size, QFont.Weight.Bold)
        self.channel_label.setFont(chan_font)
        self.channel_label.setStyleSheet(f"color: {chan_color}; background: transparent;")

        # Drop shadow for header readability
        if self.config.get("text_shadow", True):
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(8)
            shadow.setColor(QColor(0, 0, 0, 240))
            shadow.setOffset(1, 2)
            self.channel_label.setGraphicsEffect(shadow)

            w_shadow = QGraphicsDropShadowEffect(self.whisper_label)
            w_shadow.setBlurRadius(8)
            w_shadow.setColor(QColor(0, 0, 0, 240))
            w_shadow.setOffset(1, 2)
            self.whisper_label.setGraphicsEffect(w_shadow)

        self.channel_label.show()
        self.reposition_window()
        self.update_click_through()
        self.render_users()

    def reposition_window(self):
        """Fixed width positioning: window X position stays 100% constant to prevent any inward sliding."""
        screen = self.screen().availableGeometry()
        x_offset = self.config.get("x_offset", 0)
        y_offset = self.config.get("y_offset", 220)

        win_w = OVERLAY_FIXED_WIDTH
        self.setFixedWidth(win_w)
        self.adjustSize()

        x = max(0, screen.width() - win_w - x_offset)
        y = max(0, min(y_offset, screen.height() - 50))
        self.move(x, y)

    def set_unlocked(self, unlocked: bool):
        self.is_unlocked = unlocked
        self.update_click_through()
        self.update()

    def update_click_through(self):
        click_through = self.config.get("click_through", True) and not self.is_unlocked
        if HAS_WIN32:
            hwnd = int(self.winId())
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if click_through:
                style |= (win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE)
            else:
                style &= ~win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

    def update_channel(self, channel_name: str):
        if channel_name:
            self.channel_name = channel_name
            self.channel_label.setText(channel_name)
            self.channel_label.show()
            self.reposition_window()

    def update_whisper_state(self, is_whispering: bool):
        """Show or hide the red WHISPER BASIYORSUN warning banner in its fixed container."""
        show_warning = self.config.get("show_whisper_warning", True)
        if is_whispering and show_warning:
            self.whisper_label.show()
        else:
            self.whisper_label.hide()
        self.reposition_window()

    def update_users(self, users: list):
        self.users = users
        self.render_users()

    def add_chat_message(self, sender: str, text: str):
        """Append incoming chat message or movement notification with 3-second Fade-In / Fade-Out animation in bounded box."""
        if not self.config.get("show_chat_messages", True):
            return

        font_family = self.config.get("font_family", "Segoe UI")
        chat_size = self.config.get("chat_font_size", 10)
        chat_font = QFont(font_family, chat_size)

        sender_color = self.config.get("chat_sender_color", "#F5E663")
        msg_color = self.config.get("chat_color", "#FFFFFF")
        text_shadow = self.config.get("text_shadow", True)

        if text:
            # Truncate long messages to max 120 characters with '...' preview
            if len(text) > 120:
                text = text[:120] + "..."
            text = break_long_words(text, max_len=28)
            msg_body = f": <span style='color:{msg_color};'>{text}</span>"
        else:
            msg_body = ""

        # Bounded Divbox HTML Format
        html_text = (
            f"<div style='width: 310px; word-wrap: break-word; text-align: right;'>"
            f"<span style='color:{sender_color}; font-weight:bold;'>{sender}</span>{msg_body}"
            f"</div>"
        )

        msg_label = AnimatedChatLabel(
            html_text,
            chat_font,
            text_shadow=text_shadow,
            duration_ms=3000,
            on_destroy_cb=self._on_chat_label_destroyed,
            parent=self.chat_widget
        )

        self.active_chat_labels.append(msg_label)
        self.chat_layout.addWidget(msg_label)
        self.reposition_window()

        # Start 3-second animation
        msg_label.start_animation(3000)

    def _on_chat_label_destroyed(self, label_widget):
        if label_widget in self.active_chat_labels:
            self.active_chat_labels.remove(label_widget)
        self.reposition_window()

    def render_users(self):
        # Render Users List
        while self.users_layout.count():
            item = self.users_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        font_family = self.config.get("font_family", "Segoe UI")
        user_size = self.config.get("user_font_size", 11)
        user_color = self.config.get("user_color", "#FFFFFF")
        user_font = QFont(font_family, user_size, QFont.Weight.Bold)
        cc_idle_color = self.config.get("cc_color", "#FF8A00")

        for u in self.users:
            nick = u.get("nickname", "")
            is_talking = u.get("is_talking", False)
            is_whispering = u.get("is_whispering", False)
            is_mic_muted = u.get("is_mic_muted", False)
            is_output_muted = u.get("is_output_muted", False)
            is_channel_commander = u.get("is_channel_commander", False)

            user_row = QWidget(self.users_widget)
            user_row.setFixedWidth(OVERLAY_FIXED_WIDTH)
            row_layout = QHBoxLayout(user_row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

            # Mute Icons (To the left of nickname)
            if is_output_muted and os.path.exists(HEADPHONE_MUTE_ICON_PATH):
                hp_lbl = QLabel(user_row)
                pix = QPixmap(HEADPHONE_MUTE_ICON_PATH).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                hp_lbl.setPixmap(pix)
                hp_lbl.setStyleSheet("background: transparent;")
                row_layout.addWidget(hp_lbl)

            if is_mic_muted and os.path.exists(MIC_MUTE_ICON_PATH):
                mic_lbl = QLabel(user_row)
                pix = QPixmap(MIC_MUTE_ICON_PATH).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                mic_lbl.setPixmap(pix)
                mic_lbl.setStyleSheet("background: transparent;")
                row_layout.addWidget(mic_lbl)

            # Ball Indicator: Red (#FF3333) for Whisper, Yellow (#FFE500) for CC Talking, Configurable (#FF8A00) for CC Idle
            if is_whispering or is_channel_commander:
                cc_lbl = QLabel(user_row)
                if is_whispering:
                    ball_color = "#FF3333"
                elif is_talking:
                    ball_color = "#FFE500"
                else:
                    ball_color = cc_idle_color

                cc_pix = create_circle_pixmap(ball_color, size=10)
                cc_lbl.setPixmap(cc_pix)
                cc_lbl.setStyleSheet("background: transparent;")
                row_layout.addWidget(cc_lbl)

            # User Nickname Color:
            # - Whisper: Red (#FF3333)
            # - CC Talking: Yellow (#FFE500)
            # - Normal Talking: Light Blue (#00CCFF)
            # - Idle: White (#FFFFFF)
            if is_whispering:
                color = "#FF3333"
            elif is_talking:
                color = "#FFE500" if is_channel_commander else "#00CCFF"
            else:
                color = user_color

            lbl = QLabel(f"{nick}", user_row)
            lbl.setFont(user_font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl.setStyleSheet(f"color: {color}; background: transparent;")

            if self.config.get("text_shadow", True):
                shadow = QGraphicsDropShadowEffect(lbl)
                shadow.setBlurRadius(6)
                shadow.setColor(QColor(0, 0, 0, 240))
                shadow.setOffset(1, 1)
                lbl.setGraphicsEffect(shadow)

            row_layout.addWidget(lbl)
            self.users_layout.addWidget(user_row)
            user_row.show()

        self.users_widget.show()
        self.reposition_window()

    # --- Mouse Events for Dragging when Unlocked ---
    def mousePressEvent(self, event):
        if self.is_unlocked and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_unlocked and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.is_unlocked and event.button() == Qt.MouseButton.LeftButton:
            screen = self.screen().availableGeometry()
            win_w = OVERLAY_FIXED_WIDTH
            new_x_offset = max(0, screen.width() - win_w - self.x())
            new_y_offset = max(0, self.y())
            self.config.set("x_offset", new_x_offset)
            self.config.set("y_offset", new_y_offset)
            print(f"[Overlay] Saved position: X_offset={new_x_offset}, Y_offset={new_y_offset}")
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw drag border & hint when unlocked
        if self.is_unlocked:
            pen = QPen(QColor(245, 230, 99, 220), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(10, 20, "Sürükleyerek Taşıyın")
        else:
            # Draw semi-transparent card background if card_opacity > 0
            opacity = self.config.get("card_opacity", 0.0)
            if opacity > 0:
                bg_color = QColor(0, 0, 0, int(opacity * 255))
                painter.setBrush(QBrush(bg_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(self.rect(), 8, 8)

        super().paintEvent(event)
