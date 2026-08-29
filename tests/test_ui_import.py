import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("[TEST] Importing UI modules...")
from src.ui.components import TRANSLATIONS
from src.ui.settings_dialog import SettingsDialog
from src.ui.main_window import MainWindow

print(f"  Translations loaded: {list(TRANSLATIONS.keys())}")
assert "AR" in TRANSLATIONS and "FR" in TRANSLATIONS
print("  [OK] UI Modules import and syntax valid")
