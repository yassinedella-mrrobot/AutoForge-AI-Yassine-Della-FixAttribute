import os
import json
import subprocess
import threading

class InstallerEngine:
    def __init__(self, rules_path=None):
        self.current_process = None
        self.lock = threading.Lock()
        self.rules = self.load_rules(rules_path)

    def load_rules(self, rules_path):
        if not rules_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.join(base_dir, "config", "installer_rules.json")
        
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"categories": {}, "installer_flags": {}}

    def get_category_info(self, item_name, is_dir=False):
        name_lower = item_name.lower()
        categories = self.rules.get("categories", {})
        
        for cat_id, cat_data in categories.items():
            keywords = cat_data.get("keywords", [])
            if any(k in name_lower for k in keywords):
                return {
                    "id": cat_id,
                    "icon": cat_data.get("icon", "💾"),
                    "label_ar": cat_data.get("label_ar", cat_id),
                    "label_fr": cat_data.get("label_fr", cat_id),
                    "priority": cat_data.get("priority", 10)
                }
        
        if is_dir:
            return {"id": "directory", "icon": "📁", "label_ar": "مجلد برامج", "label_fr": "Dossier", "priority": 10}
        elif name_lower.endswith('.msi'):
            return {"id": "msi", "icon": "🛡️", "label_ar": "حزمة MSI", "label_fr": "Paquet MSI", "priority": 10}
        
        return {"id": "default", "icon": "💾", "label_ar": "تطبيق تنفيذي", "label_fr": "Application", "priority": 10}

    def find_installer_in_folder(self, folder_path):
        for root, _, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith('.msi'):
                    return os.path.join(root, f), "msi"

        for candidate in ["setup.exe", "install.exe", "autorun.exe", "start.exe"]:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.lower() == candidate:
                        return os.path.join(root, f), "exe"

        for root, _, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith('.exe') and not f.lower().startswith('uninstall'):
                    return os.path.join(root, f), "exe"

        return None, None

    def build_install_command(self, full_path):
        """
        Determines the executable file and argument list.
        Returns (target_exe: str, args_list: list, working_dir: str, is_msi: bool)
        """
        if os.path.isdir(full_path):
            target_file, ftype = self.find_installer_in_folder(full_path)
            if not target_file:
                return None, [], "", False
            working_dir = os.path.dirname(target_file)
            is_msi = (ftype == "msi")
        else:
            target_file = full_path
            working_dir = os.path.dirname(full_path)
            is_msi = full_path.lower().endswith(('.msi', '.msp'))

        name_lower = os.path.basename(target_file).lower()

        if is_msi:
            args = ["msiexec.exe", "/i", target_file, "/qn", "/norestart", "ALLUSERS=1", "ACCEPT_EULA=1", "LIMITUI=ALL"]
            return "msiexec.exe", args, working_dir, True

        # Check configured rules
        flag_rules = self.rules.get("installer_flags", {})
        for rule_id, rule_data in flag_rules.items():
            matches = rule_data.get("match", [])
            if any(m in name_lower for m in matches):
                custom_args = [target_file] + list(rule_data.get("args", []))
                return target_file, custom_args, working_dir, False

        # Default standard Inno/NSIS/InstallShield arguments
        default_args = [target_file, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]
        return target_file, default_args, working_dir, False

    def execute_installer(self, full_path, on_log=None):
        """
        Executes an installer synchronously while storing the process reference
        for thread-safe instant cancellation via taskkill.
        """
        target_exe, args, working_dir, is_msi = self.build_install_command(full_path)
        if not target_exe:
            return False, "Aucun fichier exécutable valide trouvé dans le dossier"

        if on_log:
            on_log(f"  → Exécution: {' '.join(args if is_msi else [os.path.basename(target_exe)] + args[1:])}")

        try:
            with self.lock:
                # Launch process without shell=True to track exact PID
                cmd = args if is_msi else args
                self.current_process = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

            stdout, stderr = self.current_process.communicate()
            exit_code = self.current_process.returncode

            with self.lock:
                self.current_process = None

            # Standard successful exit codes: 0 (Success), 3010 (Success - Reboot Required)
            if exit_code in [0, 3010]:
                return True, f"Succès (Code {exit_code})"
            else:
                return False, f"Code de sortie {exit_code}"

        except Exception as e:
            with self.lock:
                self.current_process = None
            return False, f"Exception: {str(e)}"

    def kill_current_process(self):
        """
        Immediately and forcefully terminates the active installer and all of its child processes.
        """
        with self.lock:
            if self.current_process and self.current_process.poll() is None:
                pid = self.current_process.pid
                try:
                    # Windows process tree kill
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                except Exception:
                    try:
                        self.current_process.kill()
                    except Exception:
                        pass
                self.current_process = None
                return True
        return False
