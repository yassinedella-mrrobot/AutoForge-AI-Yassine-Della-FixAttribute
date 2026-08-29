import re
import winreg

class RegistryScanner:
    """
    Scanner for querying installed Windows applications from registry keys
    (HKLM 64-bit, HKLM 32-bit / WOW6432Node, and HKCU).
    """

    @staticmethod
    def get_installed_applications():
        """
        Returns a dictionary mapping lowercase display names to application metadata
        {
            "google chrome": {"version": "120.0.0", "publisher": "Google LLC", "location": "..."},
            ...
        }
        """
        installed = {}
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for root_key, subkey_path in registry_paths:
            try:
                with winreg.OpenKey(root_key, subkey_path, 0, winreg.KEY_READ) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        try:
                            sub_key_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub_key_name) as sub_key:
                                try:
                                    name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                                    if not name or not str(name).strip():
                                        continue
                                    
                                    name_clean = str(name).strip()
                                    name_lower = name_clean.lower()
                                    
                                    version = ""
                                    try:
                                        version, _ = winreg.QueryValueEx(sub_key, "DisplayVersion")
                                        version = str(version).strip()
                                    except Exception:
                                        pass

                                    publisher = ""
                                    try:
                                        publisher, _ = winreg.QueryValueEx(sub_key, "Publisher")
                                        publisher = str(publisher).strip()
                                    except Exception:
                                        pass

                                    installed[name_lower] = {
                                        "display_name": name_clean,
                                        "version": version,
                                        "publisher": publisher
                                    }
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
        return installed

    @staticmethod
    def clean_name_tokens(name):
        cleaned = re.sub(r'[\._\-\(\)\[\]]', ' ', name)
        cleaned = re.sub(r'\b(setup|installer|install|zip|win|v\d+(\.\d+)*|\d+|x86|x64|fr|en|final|stable|beta)\b', '', cleaned, flags=re.IGNORECASE)
        return [w.lower() for w in cleaned.split() if len(w) > 2]

    @classmethod
    def check_is_installed(cls, package_name, installed_dict):
        """
        Determines if a package filename/folder is already installed.
        Returns a tuple: (is_installed: bool, installed_version: str, matched_name: str)
        """
        pkg_lower = package_name.lower().replace(".exe", "").replace(".msi", "").replace(".msp", "")
        
        # 1. Exact or direct substring match
        for installed_name_lower, meta in installed_dict.items():
            if pkg_lower == installed_name_lower:
                return True, meta.get("version", ""), meta.get("display_name", "")
            if len(pkg_lower) > 3 and pkg_lower in installed_name_lower:
                return True, meta.get("version", ""), meta.get("display_name", "")
            if len(installed_name_lower) > 3 and installed_name_lower in pkg_lower:
                return True, meta.get("version", ""), meta.get("display_name", "")

        # 2. Token based fuzzy match
        tokens = cls.clean_name_tokens(package_name)
        if tokens:
            for installed_name_lower, meta in installed_dict.items():
                if all(tok in installed_name_lower for tok in tokens):
                    return True, meta.get("version", ""), meta.get("display_name", "")

        return False, "", ""
