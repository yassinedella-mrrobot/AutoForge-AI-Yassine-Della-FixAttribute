import os
import sys
import json

CONFIG_FILE_NAME = "autoforge_config.json"

def get_base_dir():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if not os.path.exists(os.path.join(base_dir, "Apps")):
            return os.getcwd()
        return base_dir
    else:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_apps_dir():
    return os.path.join(get_base_dir(), "Apps")

def get_config_path():
    return os.path.join(get_base_dir(), CONFIG_FILE_NAME)

class SettingsManager:
    DEFAULT_SETTINGS = {
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "language": "AR",
        "theme": "dark",
        "auto_skip_installed": True,
        "custom_paths": [],
        "enable_animations": True
    }

    def __init__(self):
        self.config_path = get_config_path()
        self.settings = self.load_settings()

    def load_settings(self):
        settings = dict(self.DEFAULT_SETTINGS)
        # Check environment variable first for API key if available
        env_key = os.getenv("GEMINI_API_KEY", "").strip()
        if env_key:
            settings["gemini_api_key"] = env_key

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    settings.update(data)
            except Exception:
                pass
        return settings

    def save_settings(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def get_api_key(self):
        # Priority: Environment variable -> Saved config
        return os.getenv("GEMINI_API_KEY", self.settings.get("gemini_api_key", "")).strip()

    def set_api_key(self, api_key):
        self.set("gemini_api_key", api_key.strip())
