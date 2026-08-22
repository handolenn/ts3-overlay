import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from config_manager import ConfigManager
from overlay_window import OverlayWindow
from ts3_client import TS3ClientThread
from tray_icon import TrayIconManager
from settings_dialog import SettingsDialog

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON_PATH = os.path.join(SCRIPT_DIR, "icon", "gecmisolsun.png")


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    if os.path.exists(APP_ICON_PATH):
        app.setWindowIcon(QIcon(APP_ICON_PATH))

    # Initialize Config Manager
    config = ConfigManager()

    # Create Overlay Window
    overlay = OverlayWindow(config)
    if config.get("overlay_enabled", True):
        overlay.show()

    # Create TS3 Client Background Thread
    ts3_thread = TS3ClientThread(config)
    ts3_thread.channel_updated_signal.connect(overlay.update_channel)
    ts3_thread.users_updated_signal.connect(overlay.update_users)
    ts3_thread.message_received_signal.connect(overlay.add_chat_message)
    ts3_thread.whisper_state_signal.connect(overlay.update_whisper_state)
    ts3_thread.start()

    # Create System Tray Icon
    tray_icon = TrayIconManager(app, config, overlay, ts3_thread)
    tray_icon.show()

    # Automatically open Control Panel GUI on launch
    control_panel = SettingsDialog(config, overlay, ts3_thread)
    control_panel.show()
    tray_icon.settings_dialog = control_panel

    print("[TS3 Overlay] Control Panel GUI running...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
