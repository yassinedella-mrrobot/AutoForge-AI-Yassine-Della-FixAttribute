import os
import sys
import time
import json
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure PYTHONHOME doesn't poison standalone interpreter if set
os.environ.pop("PYTHONHOME", None)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import SettingsManager, get_apps_dir, get_base_dir, get_config_path
from src.core.registry_scanner import RegistryScanner
from src.core.installer_engine import InstallerEngine
from src.ai.gemini_service import GeminiService
from src.ui.components import TRANSLATIONS
import customtkinter as ctk

class TestAutoForgeSuite(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.apps_dir = os.path.join(self.test_dir, "Apps")
        os.makedirs(self.apps_dir, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    # -------------------------------------------------------------
    # 1. SettingsManager Tests
    # -------------------------------------------------------------
    def test_settings_manager_defaults_and_persistence(self):
        cfg_path = os.path.join(self.test_dir, "autoforge_config.json")
        with patch("src.config.settings.get_config_path", return_value=cfg_path):
            sm = SettingsManager()
            self.assertEqual(sm.get("gemini_model"), "gemini-2.5-flash")
            self.assertTrue(sm.get("auto_skip_installed"))
            
            # Modify and save
            sm.set("theme", "light")
            sm.set("language", "FR")
            sm.set_api_key("TEST_KEY_123")
            
            # Reload in new instance
            sm2 = SettingsManager()
            self.assertEqual(sm2.get("theme"), "light")
            self.assertEqual(sm2.get("language"), "FR")
            self.assertEqual(sm2.get_api_key(), "TEST_KEY_123")

    # -------------------------------------------------------------
    # 2. Registry Scanner Tests
    # -------------------------------------------------------------
    def test_registry_scanner_clean_and_fuzzy(self):
        fake_installed = {
            "google chrome": {"display_name": "Google Chrome", "version": "125.0.1", "publisher": "Google LLC"},
            "hansaton fitting suite": {"display_name": "Hansaton Fitting Suite 5", "version": "5.2.0", "publisher": "Hansaton"},
            "microsoft visual c++ 2015-2022 redistributable (x64)": {
                "display_name": "Microsoft Visual C++ 2015-2022 Redistributable (x64) - 14.38.33135",
                "version": "14.38.33135",
                "publisher": "Microsoft Corporation"
            }
        }
        
        # Exact/Substring match
        inst, ver, name = RegistryScanner.check_is_installed("GoogleChromeSetup.exe", fake_installed)
        self.assertTrue(inst)
        self.assertEqual(ver, "125.0.1")
        
        # Token fuzzy match
        inst, ver, name = RegistryScanner.check_is_installed("Hansaton_Fitting_Suite_v5.2.exe", fake_installed)
        self.assertTrue(inst)
        self.assertEqual(ver, "5.2.0")

        # Non-installed app
        inst, ver, name = RegistryScanner.check_is_installed("NonExistentApp_Setup.exe", fake_installed)
        self.assertFalse(inst)
        self.assertEqual(ver, "")

    # -------------------------------------------------------------
    # 3. Installer Engine Tests
    # -------------------------------------------------------------
    def test_installer_engine_rules_and_categories(self):
        engine = InstallerEngine()
        
        # Check rule loading
        self.assertIn("audiology", engine.rules["categories"])
        self.assertIn("drivers", engine.rules["categories"])
        self.assertIn("runtimes", engine.rules["categories"])
        
        # Category classification
        cat_audiology = engine.get_category_info("Oticon_Genie_2024.exe")
        self.assertEqual(cat_audiology["id"], "audiology")

        cat_runtime = engine.get_category_info("VC_redist.x64.exe")
        self.assertEqual(cat_runtime["id"], "runtimes")
        self.assertEqual(cat_runtime["priority"], 100)

        cat_driver = engine.get_category_info("HiPro2_Driver.exe")
        self.assertEqual(cat_driver["id"], "drivers")

        # MSI installer command
        msi_path = os.path.join(self.test_dir, "Package.msi")
        exe, args, wdir, is_msi = engine.build_install_command(msi_path)
        self.assertTrue(is_msi)
        self.assertEqual(exe, "msiexec.exe")
        self.assertIn("/qn", args)
        self.assertIn("/norestart", args)

        # Folder containing installer
        folder_app = os.path.join(self.test_dir, "AppFolder")
        os.makedirs(folder_app, exist_ok=True)
        setup_exe = os.path.join(folder_app, "setup.exe")
        with open(setup_exe, "w") as f:
            f.write("dummy")
        
        found_target, ftype = engine.find_installer_in_folder(folder_app)
        self.assertEqual(os.path.abspath(found_target), os.path.abspath(setup_exe))
        self.assertEqual(ftype, "exe")

    # -------------------------------------------------------------
    # 4. Gemini AI Service Tests
    # -------------------------------------------------------------
    def test_gemini_service_no_key(self):
        gs = GeminiService(api_key="")
        success, msg = gs.test_connection()
        self.assertFalse(success)
        self.assertIn("Aucune clé API", msg)

        with self.assertRaises(ValueError):
            gs.select_packages("install audiology", ["app1.exe", "app2.exe"])

    @patch("src.ai.gemini_service.genai.Client")
    def test_gemini_service_mock_selection(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = '["Hansaton.exe", "Oticon.exe"]'
        mock_client.models.generate_content.return_value = mock_response

        gs = GeminiService(api_key="AIzaSyDummyKeyForTest")
        result = gs.select_packages("prepare audiology apps", ["Hansaton.exe", "Oticon.exe", "Chrome.exe"])
        self.assertEqual(result, ["Hansaton.exe", "Oticon.exe"])

    # -------------------------------------------------------------
    # 5. Full UI / MainWindow Integration Tests (Headless)
    # -------------------------------------------------------------
    def test_main_window_full_lifecycle(self):
        from src.ui.main_window import MainWindow
        from src.ui.settings_dialog import SettingsDialog

        cfg_path = os.path.join(self.test_dir, "autoforge_config.json")
        with patch("src.config.settings.get_config_path", return_value=cfg_path), \
             patch("src.ui.main_window.get_apps_dir", return_value=self.apps_dir), \
             patch("src.config.settings.get_apps_dir", return_value=self.apps_dir):

            # Create dummy sample apps in Apps dir
            app1 = os.path.join(self.apps_dir, "Hansaton_Fitting.exe")
            app2 = os.path.join(self.apps_dir, "HiPro_Driver.exe")
            app3 = os.path.join(self.apps_dir, "vcredist_x64.exe")
            for p in [app1, app2, app3]:
                with open(p, "w") as f:
                    f.write("dummy")

            # Initialize MainWindow
            app = MainWindow()
            app.withdraw()  # keep hidden during headless tests
            app.update()

            # Verify apps loaded
            self.assertEqual(len(app.all_items), 3)
            self.assertIn("Hansaton_Fitting.exe", app.all_items)
            self.assertIn("vcredist_x64.exe", app.all_items)

            # Test Language Toggle (AR -> FR -> AR)
            initial_lang = app.current_lang
            app.toggle_language()
            self.assertNotEqual(app.current_lang, initial_lang)
            app.update()
            app.toggle_language()
            self.assertEqual(app.current_lang, initial_lang)
            app.update()

            # Test Theme Toggle (dark -> light -> dark)
            initial_theme = app.current_theme
            app.toggle_theme()
            self.assertNotEqual(app.current_theme, initial_theme)
            app.update()
            app.toggle_theme()
            self.assertEqual(app.current_theme, initial_theme)
            app.update()

            # Test Category Filtering
            app.set_category_filter("audiology")
            app.update()
            self.assertEqual(app.selected_category, "audiology")

            app.set_category_filter("all")
            app.update()
            self.assertEqual(app.selected_category, "all")

            # Test Live Search Filter
            app.filter_entry.insert(0, "hipro")
            app.on_filter_changed()
            app.update()
            self.assertEqual(app.current_filter, "hipro")

            app.filter_entry.delete(0, "end")
            app.on_filter_changed()
            app.update()
            self.assertEqual(app.current_filter, "")

            # Test Selection controls
            app.select_all()
            for var in app.check_vars.values():
                self.assertTrue(var.get())

            app.deselect_all()
            for var in app.check_vars.values():
                self.assertFalse(var.get())

            app.select_uninstalled_only()
            for name, data in app.all_items.items():
                self.assertEqual(app.check_vars[name].get(), not data["installed"])

            # Test Badge State Changes
            app.set_badge_state("Hansaton_Fitting.exe", "installing")
            app.update()
            app.set_badge_state("Hansaton_Fitting.exe", "success")
            app.update()
            app.set_badge_state("Hansaton_Fitting.exe", "failed")
            app.update()
            app.set_badge_state("Hansaton_Fitting.exe", "waiting")
            app.update()

            # Test Logging
            app.log("Test log entry message")
            log_content = app.log_box.get("1.0", "end")
            self.assertIn("Test log entry message", log_content)

            # Test Settings Dialog
            dialog = SettingsDialog(app, app.settings_manager)
            dialog.withdraw()
            dialog.update()
            dialog.api_entry.insert(0, "AIzaSyTestKey")
            dialog.model_combo.set("gemini-2.5-pro")
            dialog.save_settings()
            app.update()
            
            self.assertEqual(app.settings_manager.get("gemini_model"), "gemini-2.5-pro")

            # Cleanup and close
            app.destroy()

if __name__ == "__main__":
    unittest.main(verbosity=2)
