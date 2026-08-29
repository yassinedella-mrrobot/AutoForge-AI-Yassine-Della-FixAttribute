import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import SettingsManager
from src.core.registry_scanner import RegistryScanner
from src.core.installer_engine import InstallerEngine
from src.ai.gemini_service import GeminiService

def test_settings_manager():
    print("[TEST] Testing SettingsManager...")
    sm = SettingsManager()
    assert sm.get("gemini_model") == "gemini-2.5-flash", f"Model mismatch: {sm.get('gemini_model')}"
    sm.set("theme", "dark")
    assert sm.get("theme") == "dark"
    print("  [OK] SettingsManager passed")

def test_registry_scanner():
    print("[TEST] Testing RegistryScanner...")
    apps = RegistryScanner.get_installed_applications()
    print(f"  Found {len(apps)} installed programs in Windows Registry.")
    assert isinstance(apps, dict)
    
    # Test fuzzy check
    is_inst, ver, name = RegistryScanner.check_is_installed("GoogleChromeSetup.exe", apps)
    print(f"  Chrome match test: installed={is_inst}, ver='{ver}', name='{name}'")
    print("  [OK] RegistryScanner passed")

def test_installer_engine():
    print("[TEST] Testing InstallerEngine...")
    engine = InstallerEngine()
    
    # Test category detection
    audio_cat = engine.get_category_info("Hansaton_Fitting_Suite.exe")
    assert audio_cat["id"] == "audiology", f"Expected audiology, got {audio_cat['id']}"
    
    driver_cat = engine.get_category_info("HiPro2_Driver_Setup.exe")
    assert driver_cat["id"] == "drivers", f"Expected drivers, got {driver_cat['id']}"

    runtime_cat = engine.get_category_info("vcredist_x64.exe")
    assert runtime_cat["id"] == "runtimes", f"Expected runtimes, got {runtime_cat['id']}"
    assert runtime_cat["priority"] == 100, f"Expected priority 100, got {runtime_cat['priority']}"
    
    # Test command builder
    exe, args, wdir, is_msi = engine.build_install_command("C:\\Test\\AnyDesk.exe")
    assert any("--silent" in a or "/s" in a for a in args), f"Expected silent args: {args}"
    
    exe_msi, args_msi, wdir_msi, is_msi_flag = engine.build_install_command("C:\\Test\\App.msi")
    assert is_msi_flag is True
    assert "/qn" in args_msi
    
    print("  [OK] InstallerEngine passed")

def test_gemini_service():
    print("[TEST] Testing GeminiService structure...")
    gs = GeminiService(api_key="")
    success, msg = gs.test_connection()
    assert success is False
    assert "Aucune" in msg or "clé API" in msg
    print("  [OK] GeminiService structure passed")

if __name__ == "__main__":
    test_settings_manager()
    test_registry_scanner()
    test_installer_engine()
    test_gemini_service()
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")
