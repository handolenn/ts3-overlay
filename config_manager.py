import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(SCRIPT_DIR, "config.json")

DEFAULT_CONFIG = {
    "api_key": "",
    "host": "127.0.0.1",
    "port": 25639,
    "demo_mode": False,  # Connects to live TS3 by default
    "font_family": "Segoe UI",
    "channel_font_size": 14,
    "user_font_size": 11,
    "channel_color": "#F5E663",  # Yellow header matching screenshot
    "user_color": "#FFFFFF",
    "talking_color": "#55FF55",
    "alignment": "right",  # "right", "left"
    "x_offset": 0,  # Distance from right screen edge
    "y_offset": 220,  # Distance from top edge
    "click_through": True,
    "text_shadow": True,
    "card_opacity": 0.0,  # 0.0 = fully transparent background
    "overlay_enabled": True,
    "show_chat_messages": True,
    "max_chat_messages": 4,
    "chat_font_size": 11,
    "chat_color": "#E0E0E0",
    "chat_sender_color": "#F5E663"
}

class ConfigManager:
    def __init__(self, config_file=CONFIG_FILE_PATH):
        self.config_file = config_file
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"[ConfigManager] Error loading config: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
