import os
import sys
import json
import time
import threading
import subprocess
import re
import ctypes
import winreg
import customtkinter as ctk
from tkinter import filedialog
from google import genai
from google.genai import types

# -------------------------------------------------------------
# التحقق الإجباري الصارم من صلاحيات المسؤول (Run as Administrator)
# -------------------------------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def enforce_admin_privileges():
    if not is_admin():
        try:
            if getattr(sys, 'frozen', False):
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv[1:]), None, 1
                )
            else:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1
                )
        except Exception:
            pass
        sys.exit(0)

enforce_admin_privileges()

# -------------------------------------------------------------
# مسار التشغيل الفعلي (يعمل بدقة كملف EXE مجمّع أو كملف بايثون)
# -------------------------------------------------------------
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
    if not os.path.exists(os.path.join(BASE_DIR, "Apps")):
        BASE_DIR = os.getcwd()
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APPS_DIR = os.path.join(BASE_DIR, "Apps")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6JnVm4w7EtRgFzVpAzmx7WdG0yPX09fzEeHkFUkJdaakW")

# -------------------------------------------------------------
# تحديد الأيقونة المناسبة لكل نوع برنامج أو مجلد
# -------------------------------------------------------------
def get_app_icon(name, is_dir):
    n = name.lower()
    if any(k in n for k in ["hansaton", "audifon", "audiserv", "hearing", "acoust"]):
        return "🦻"
    elif any(k in n for k in ["hipro", "driver", "usb", "nlw", "ftdi", "com"]):
        return "🔌"
    elif any(k in n for k in ["xploview", "microscope", "cam", "view"]):
        return "🔬"
    elif any(k in n for k in ["winrar", "rar", "7z", "7zip", "zip"]):
        return "📦"
    elif any(k in n for k in ["anydesk", "teamviewer", "rustdesk", "remote"]):
        return "🖥️"
    elif any(k in n for k in ["chrome", "firefox", "edge", "brave", "opera"]):
        return "🌐"
    elif any(k in n for k in ["vlc", "player", "media", "codec"]):
        return "🎬"
    elif any(k in n for k in ["pdf", "acrobat", "reader"]):
        return "📄"
    elif any(k in n for k in ["vcredist", "dotnet", "directx", "runtime", "c++"]):
        return "⚙️"
    elif is_dir:
        return "📁"
    elif n.endswith('.msi'):
        return "🛡️"
    else:
        return "💾"

# -------------------------------------------------------------
# فحص سجل الويندوز للكشف عن البرامج المثبتة مسبقاً
# -------------------------------------------------------------
def get_installed_programs():
    installed_names = set()
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for root_key, subkey_path in registry_paths:
        try:
            with winreg.OpenKey(root_key, subkey_path, 0, winreg.KEY_READ) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub_key_name) as sub_key:
                            try:
                                name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                                if name:
                                    installed_names.add(name.strip().lower())
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass
    return installed_names

def clean_name_for_match(name):
    cleaned = re.sub(r'[\._\-\(\)]', ' ', name)
    cleaned = re.sub(r'\b(setup|installer|zip|win|v\d+|\d+|x86|x64|fr|en)\b', '', cleaned, flags=re.IGNORECASE)
    return [w.lower() for w in cleaned.split() if len(w) > 2]

def is_already_installed(item_name, installed_list):
    name_low = item_name.lower().replace(".exe", "").replace(".msi", "")
    for inst in installed_list:
        if name_low in inst or inst in name_low:
            return True
    keywords = clean_name_for_match(item_name)
    if keywords:
        for inst in installed_list:
            if all(kw in inst for kw in keywords):
                return True
    return False

# -------------------------------------------------------------
# محرك البحث الشامل عن ملف التثبيت الحقيقي داخل المجلدات (Deep Search)
# -------------------------------------------------------------
def find_installer_in_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith('.msi'):
                return os.path.join(root, f), "msi"

    for root, dirs, files in os.walk(folder_path):
        for candidate in ["setup.exe", "install.exe", "autorun.exe", "start.exe"]:
            for f in files:
                if f.lower() == candidate:
                    return os.path.join(root, f), "exe"

    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith('.exe') and not f.lower().startswith('uninstall'):
                return os.path.join(root, f), "exe"

    return None, None

# -------------------------------------------------------------
# بناء الأوامر الصامتة الدقيقة وتفادي مشاكل المسافات في ويندوز
# -------------------------------------------------------------
def execute_silent_installer(full_path):
    if os.path.isdir(full_path):
        target_file, ftype = find_installer_in_folder(full_path)
        if not target_file:
            return False, "لم يتم العثور على ملف تنفيذي صالح داخل المجلد"
            
        working_dir = os.path.dirname(target_file)
        
        if ftype == "msi":
            args = ["msiexec.exe", "/i", target_file, "/qn", "/norestart", "ALLUSERS=1", "ACCEPT_EULA=1", "LIMITUI=ALL"]
            res = subprocess.run(args, cwd=working_dir, capture_output=True, text=True)
            return (res.returncode in [0, 3010]), f"MSI Exit: {res.returncode}"
        else:
            cmd = f'start "" /wait "{target_file}" /s /v"/qn /norestart ALLUSERS=1 ACCEPT_EULA=1 LIMITUI=ALL"'
            res = subprocess.run(cmd, cwd=working_dir, shell=True, capture_output=True, text=True)
            return True, "InstallShield Executed"

    else:
        working_dir = os.path.dirname(full_path)
        if full_path.lower().endswith(('.msi', '.msp')):
            args = ["msiexec.exe", "/i", full_path, "/qn", "/norestart", "ALLUSERS=1", "ACCEPT_EULA=1", "LIMITUI=ALL"]
            res = subprocess.run(args, cwd=working_dir, capture_output=True, text=True)
            return (res.returncode in [0, 3010]), f"MSI Exit: {res.returncode}"

        name = os.path.basename(full_path).lower()
        
        if "winrar" in name or "rar" in name:
            cmd = f'start "" /wait "{full_path}" /s'
        elif "anydesk" in name:
            cmd = f'start "" /wait "{full_path}" --install "C:\\Program Files (x86)\\AnyDesk" --start-with-win --silent'
        elif "rustdesk" in name:
            cmd = f'start "" /wait "{full_path}" --silent-install'
        elif "chrome" in name:
            cmd = f'start "" /wait "{full_path}" /silent /install'
        elif "7z" in name or "7zip" in name:
            cmd = f'start "" /wait "{full_path}" /S'
        elif any(k in name for k in ["driver", "hipro", "vlc", "k-lite", "xploview"]):
            cmd = f'start "" /wait "{full_path}" /S /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'
        elif any(k in name for k in ["vcredist", "vc_redist", "dotnet", "directx"]):
            cmd = f'start "" /wait "{full_path}" /q /norestart /passive'
        else:
            cmd = f'start "" /wait "{full_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'

        res = subprocess.run(cmd, cwd=working_dir, shell=True, capture_output=True, text=True)
        return True, "Executed"


# -------------------------------------------------------------
# قواميس اللغتين
# -------------------------------------------------------------
TRANSLATIONS = {
    "AR": {
        "title": "AutoForge AI",
        "subtitle": "⚡ نظام النشر الذكي المتقدم وأتمتة البيئات البرمجية",
        "placeholder": "اكتب طلبك باللغة الطبيعية (مثال: جهز برامج السمعيات والتصفح)...",
        "ask_ai": "⚡ تحليل واستخراج الحزم عبر الذكاء الاصطناعي",
        "select_uninstalled": "تحديد غير المثبت",
        "select_all": "تحديد الكل",
        "deselect_all": "إلغاء التحديد",
        "refresh": "🔄 إعادة الفحص",
        "add_custom": "📁 إضافة ملفات/مجلد من الحاسوب",
        "frame_title": "الحزم والمجلدات البرمجية المكتشفة",
        "total_count": "إجمالي البرامج: {count} حزمة",
        "installed_tag": "(مثبت مسبقاً)",
        "btn_install": "▶ تشغيل خطة التثبيت الصامت الفوري",
        "btn_stop": "⏹ إيقاف العملية فوراً",
        "time_status": "المنقضي: {elapsed} | المتبقي التقديري: {eta}",
        "empty_apps": "لا توجد برامج داخل المجلدات المحددة!",
        "status_waiting": "في الانتظار...",
        "status_installing": "⏳ جاري التثبيت...",
        "status_success": "✓ تم بنجاح",
        "status_failed": "✗ فشل / خطأ",
        "system_ready": "[AI Core] المحرك العصبي جاهز وبانتظار الأوامر يا ياسين...\n",
        "finish_msg": "--- [FINISH] اكتملت كافة عمليات التثبيت بنجاح تام يا ياسين! ---"
    },
    "FR": {
        "title": "AutoForge AI",
        "subtitle": "⚡ Système Intelligent de Déploiement et d'Automatisation",
        "placeholder": "Tapez votre demande (ex: logiciels audio et navigateurs)...",
        "ask_ai": "⚡ Analyse et Sélection par IA",
        "select_uninstalled": "Non Installés",
        "select_all": "Tout Cocher",
        "deselect_all": "Tout Décocher",
        "refresh": "🔄 Actualiser",
        "add_custom": "📁 Ajouter Fichiers/Dossiers du PC",
        "frame_title": "Packages et Dossiers Détectés",
        "total_count": "Total programmes: {count} paquets",
        "installed_tag": "(Déjà installé)",
        "btn_install": "▶ Lancer l'Installation Silencieuse",
        "btn_stop": "⏹ Arrêter l'Opération",
        "time_status": "Écoulé: {elapsed} | Restant estimé: {eta}",
        "empty_apps": "Aucun programme trouvé dans les dossiers spécifiés!",
        "status_waiting": "En attente...",
        "status_installing": "⏳ En cours...",
        "status_success": "✓ Installé",
        "status_failed": "✗ Erreur",
        "system_ready": "[AI Core] Moteur neuronal prêt, en attente de commandes Yassine...\n",
        "finish_msg": "--- [FINISH] Installations terminées avec succès Yassine! ---"
    }
}


class AutoForgeAI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.current_lang = "AR"
        self.current_theme = "dark"
        self.stop_requested = False
        self.custom_paths = []
        self.anim_step = 0

        # تعريف الهياكل البيانية أولاً
        self.check_vars = {}
        self.items_path_map = {}
        self.installed_status = {}
        self.status_badges = {}
        self.card_frames = {}

        self.title("AutoForge AI (by Yassine Della) - Precision Edition")
        self.geometry("800x940")
        ctk.set_appearance_mode(self.current_theme)
        ctk.set_default_color_theme("blue")

        if not os.path.exists(APPS_DIR):
            try:
                os.makedirs(APPS_DIR)
            except Exception:
                pass

        # الشريط العلوي لأزرار التحكم
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=(10, 0))

        self.lang_btn = ctk.CTkButton(
            self.top_bar, 
            text="🌐 Français", 
            width=90, 
            height=28, 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            command=self.toggle_language
        )
        self.lang_btn.pack(side="left", padx=5)

        self.theme_btn = ctk.CTkButton(
            self.top_bar, 
            text="☀️ الوضع النهاري", 
            width=110, 
            height=28, 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=5)

        self.admin_badge = ctk.CTkLabel(
            self.top_bar,
            text="🛡️ NEURAL ADMIN ACTIVE",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#00ffcc",
            fg_color="#064e3b",
            corner_radius=4,
            width=150,
            height=24
        )
        self.admin_badge.pack(side="left", padx=10)

        self.count_label = ctk.CTkLabel(
            self.top_bar,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.count_label.pack(side="right", padx=5)

        # الحاوية العلوية ذات الطابع السيبراني الذكي
        self.header_card = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#1e293b")
        self.header_card.pack(fill="x", padx=20, pady=(8, 4))

        self.title_label = ctk.CTkLabel(
            self.header_card, 
            text="AutoForge AI", 
            font=ctk.CTkFont(family="Consolas", size=24, weight="bold"),
            text_color="#00ffcc"
        )
        self.title_label.pack(pady=(8, 0))

        self.author_label = ctk.CTkLabel(
            self.header_card,
            text="⚡ ARCHITECT: YASSINE DELLA ⚡",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.author_label.pack(pady=(0, 2))

        self.subtitle_label = ctk.CTkLabel(
            self.header_card,
            text=TRANSLATIONS[self.current_lang]["subtitle"],
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.subtitle_label.pack(pady=(0, 6))

        # Prompt Entry Box
        self.prompt_entry = ctk.CTkEntry(
            self, 
            placeholder_text=TRANSLATIONS[self.current_lang]["placeholder"],
            width=740,
            height=42,
            font=ctk.CTkFont(size=13),
            border_color="#0284c7"
        )
        self.prompt_entry.pack(pady=4)

        # AI Action Button
        self.ask_ai_btn = ctk.CTkButton(
            self, 
            text=TRANSLATIONS[self.current_lang]["ask_ai"], 
            command=self.trigger_ai_selection,
            height=38,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.ask_ai_btn.pack(pady=4)

        # Quick Controls Frame
        self.tools_frame = ctk.CTkFrame(self, fg_color="transparent", width=740)
        self.tools_frame.pack(pady=4)

        self.btn_select_uninst = ctk.CTkButton(self.tools_frame, text=TRANSLATIONS[self.current_lang]["select_uninstalled"], width=115, height=26, font=ctk.CTkFont(size=11), command=self.select_uninstalled_only)
        self.btn_select_uninst.pack(side="left", padx=3)

        self.btn_select_all = ctk.CTkButton(self.tools_frame, text=TRANSLATIONS[self.current_lang]["select_all"], width=90, height=26, font=ctk.CTkFont(size=11), fg_color="#334155", command=self.select_all)
        self.btn_select_all.pack(side="left", padx=3)

        self.btn_deselect_all = ctk.CTkButton(self.tools_frame, text=TRANSLATIONS[self.current_lang]["deselect_all"], width=90, height=26, font=ctk.CTkFont(size=11), fg_color="#444", hover_color="#333", command=self.deselect_all)
        self.btn_deselect_all.pack(side="left", padx=3)

        self.btn_add_custom = ctk.CTkButton(self.tools_frame, text=TRANSLATIONS[self.current_lang]["add_custom"], width=165, height=26, font=ctk.CTkFont(size=11), fg_color="#0d9488", hover_color="#0f766e", command=self.add_custom_path)
        self.btn_add_custom.pack(side="left", padx=3)

        self.btn_refresh = ctk.CTkButton(self.tools_frame, text=TRANSLATIONS[self.current_lang]["refresh"], width=90, height=26, font=ctk.CTkFont(size=11), fg_color="#0284c7", hover_color="#0369a1", command=self.load_local_apps)
        self.btn_refresh.pack(side="right", padx=3)

        # إطار عرض الحزم والمجلدات
        self.list_frame = ctk.CTkScrollableFrame(self, width=740, height=220, label_text=TRANSLATIONS[self.current_lang]["frame_title"])
        self.list_frame.pack(pady=6)

        # إنشاء عناصر شريط النسبة والوقت أولاً قبل استدعاء load_local_apps
        self.status_info_frame = ctk.CTkFrame(self, fg_color="transparent", width=740)
        self.status_info_frame.pack(fill="x", padx=30, pady=(2, 2))

        self.percentage_label = ctk.CTkLabel(
            self.status_info_frame, 
            text="0% (0/0)", 
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#00ffcc"
        )
        self.percentage_label.pack(side="left")

        self.time_label = ctk.CTkLabel(
            self.status_info_frame, 
            text="المنقضي: 00:00 | المتبقي: --:--", 
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#94a3b8"
        )
        self.time_label.pack(side="right")

        # شريط التقدم
        self.progress_bar = ctk.CTkProgressBar(self, width=740, height=12)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(2, 4))

        # أزرار التشغيل والإيقاف
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent", width=740)
        self.actions_frame.pack(pady=4)

        self.install_btn = ctk.CTkButton(
            self.actions_frame, 
            text=TRANSLATIONS[self.current_lang]["btn_install"], 
            command=self.start_installation_thread,
            width=365,
            height=38,
            fg_color="#00a86b",
            hover_color="#007a4e",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.install_btn.pack(side="left", padx=4)

        self.stop_btn = ctk.CTkButton(
            self.actions_frame, 
            text=TRANSLATIONS[self.current_lang]["btn_stop"], 
            command=self.request_stop,
            width=365,
            height=38,
            fg_color="#b91c1c",
            hover_color="#7f1d1d",
            font=ctk.CTkFont(size=14, weight="bold"),
            state="disabled"
        )
        self.stop_btn.pack(side="right", padx=4)

        # صندوق السجل
        self.log_box = ctk.CTkTextbox(self, width=740, height=125, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.pack(pady=6)
        self.log_box.insert("end", f"[System Init] AutoForge AI Neural Engine (by Yassine Della) Initialized.\n[System Init] Directory: {APPS_DIR}\n" + TRANSLATIONS[self.current_lang]["system_ready"])

        # الآن يتم استدعاء تحميل البرامج بعد أن تم تهيئة كافة عناصر الواجهة بنجاح
        self.load_local_apps()
        self.run_dynamic_animations()

    def run_dynamic_animations(self):
        self.anim_step = (self.anim_step + 1) % 60
        neon_cyan_shades = ["#00ffcc", "#38bdf8", "#818cf8", "#c084fc", "#38bdf8", "#00ffcc"]
        neon_border_shades = ["#0284c7", "#0ea5e9", "#06b6d4", "#10b981", "#0284c7"]
        
        c_idx = (self.anim_step // 10) % len(neon_cyan_shades)
        b_idx = (self.anim_step // 12) % len(neon_border_shades)
        
        title_color = neon_cyan_shades[c_idx]
        border_glow = neon_border_shades[b_idx]
        
        dots = "·" * ((self.anim_step % 4) + 1)
        author_animated = f"⚡ NEURAL LINK: YASSINE DELLA [LIVE{dots}] ⚡"
        
        self.title_label.configure(text_color=title_color)
        self.author_label.configure(text=author_animated)
        self.header_card.configure(border_color=border_glow)

        self.after(120, self.run_dynamic_animations)

    def toggle_language(self):
        self.current_lang = "FR" if self.current_lang == "AR" else "AR"
        t = TRANSLATIONS[self.current_lang]
        
        self.lang_btn.configure(text="🌐 العربية" if self.current_lang == "FR" else "🌐 Français")
        self.subtitle_label.configure(text=t["subtitle"])
        self.prompt_entry.configure(placeholder_text=t["placeholder"])
        self.ask_ai_btn.configure(text=t["ask_ai"])
        self.btn_select_uninst.configure(text=t["select_uninstalled"])
        self.btn_select_all.configure(text=t["select_all"])
        self.btn_deselect_all.configure(text=t["deselect_all"])
        self.btn_add_custom.configure(text=t["add_custom"])
        self.btn_refresh.configure(text=t["refresh"])
        self.list_frame.configure(label_text=t["frame_title"])
        self.install_btn.configure(text=t["btn_install"])
        self.stop_btn.configure(text=t["btn_stop"])
        self.load_local_apps()

    def toggle_theme(self):
        if self.current_theme == "dark":
            self.current_theme = "light"
            ctk.set_appearance_mode("light")
            self.theme_btn.configure(text="🌙 الوضع الليلي", fg_color="#cbd5e1", text_color="#0f172a")
        else:
            self.current_theme = "dark"
            ctk.set_appearance_mode("dark")
            self.theme_btn.configure(text="☀️ الوضع النهاري", fg_color="#334155", text_color="#ffffff")

    def add_custom_path(self):
        choice = filedialog.askopenfilenames(
            title="اختر ملفات التثبيت من الكمبيوتر",
            filetypes=[("Installers", "*.exe;*.msi;*.msp"), ("All Files", "*.*")]
        )
        if choice:
            for f in choice:
                if f not in self.custom_paths:
                    self.custom_paths.append(f)
            self.load_local_apps()
            return
            
        folder_choice = filedialog.askdirectory(title="أو اختر مجلد برنامج كامل من الكمبيوتر")
        if folder_choice:
            if folder_choice not in self.custom_paths:
                self.custom_paths.append(folder_choice)
            self.load_local_apps()

    def load_local_apps(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()
        self.items_path_map.clear()
        self.installed_status.clear()
        self.status_badges.clear()
        self.card_frames.clear()

        installed_registry = get_installed_programs()
        items_map = {}

        if os.path.exists(APPS_DIR):
            for item in os.listdir(APPS_DIR):
                if item.startswith('.'):
                    continue
                full_path = os.path.join(APPS_DIR, item)
                if os.path.isfile(full_path) and item.lower().endswith(('.exe', '.msi', '.msp')):
                    items_map[item] = full_path
                elif os.path.isdir(full_path):
                    items_map[item] = full_path

        for c_path in self.custom_paths:
            base_name = os.path.basename(c_path)
            items_map[f"[PC] {base_name}"] = c_path

        total_count = len(items_map)
        t = TRANSLATIONS[self.current_lang]
        self.count_label.configure(text=t["total_count"].format(count=total_count))
        
        if hasattr(self, 'percentage_label'):
            self.percentage_label.configure(text=f"0% (0/{total_count})")

        if not items_map:
            lbl = ctk.CTkLabel(self.list_frame, text=t["empty_apps"], text_color="orange")
            lbl.pack(pady=20)
            return

        for name, full_path in items_map.items():
            self.items_path_map[name] = full_path
            clean_check_name = name.replace("[PC] ", "")
            is_dir = os.path.isdir(full_path)
            icon = get_app_icon(clean_check_name, is_dir)
            already_inst = is_already_installed(clean_check_name, installed_registry)
            self.installed_status[name] = already_inst

            card = ctk.CTkFrame(self.list_frame, fg_color="#1e293b" if self.current_theme == "dark" else "#f1f5f9", corner_radius=6)
            card.pack(fill="x", padx=5, pady=3)
            self.card_frames[name] = card

            icon_lbl = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=16), width=28)
            icon_lbl.pack(side="left", padx=(8, 2), pady=6)

            if already_inst:
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(card, text=f"{name} {t['installed_tag']}", variable=var, text_color="#f59e0b", font=ctk.CTkFont(size=12))
            else:
                var = ctk.BooleanVar(value=True)
                cb = ctk.CTkCheckBox(card, text=f"{name}", variable=var, text_color="#ffffff" if self.current_theme == "dark" else "#0f172a", font=ctk.CTkFont(size=12))
                
            cb.pack(side="left", padx=4, pady=6)
            self.check_vars[name] = var

            badge = ctk.CTkLabel(
                card, 
                text=t["status_waiting"], 
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                text_color="#94a3b8",
                fg_color="#0f172a" if self.current_theme == "dark" else "#e2e8f0",
                corner_radius=4,
                width=120,
                height=22
            )
            badge.pack(side="right", padx=10, pady=6)
            self.status_badges[name] = badge

    def set_badge_state(self, name, state):
        t = TRANSLATIONS[self.current_lang]
        badge = self.status_badges.get(name)
        card = self.card_frames.get(name)
        if not badge:
            return

        if state == "installing":
            badge.configure(text=t["status_installing"], text_color="#38bdf8", fg_color="#0369a1")
            if card:
                card.configure(border_width=1, border_color="#38bdf8")
        elif state == "success":
            badge.configure(text=t["status_success"], text_color="#ffffff", fg_color="#15803d")
            if card:
                card.configure(border_width=1, border_color="#22c55e")
        elif state == "failed":
            badge.configure(text=t["status_failed"], text_color="#ffffff", fg_color="#b91c1c")
            if card:
                card.configure(border_width=1, border_color="#ef4444")
        elif state == "waiting":
            badge.configure(text=t["status_waiting"], text_color="#94a3b8", fg_color="#0f172a" if self.current_theme == "dark" else "#e2e8f0")
            if card:
                card.configure(border_width=0)

    def select_uninstalled_only(self):
        for name, var in self.check_vars.items():
            var.set(not self.installed_status.get(name, False))

    def select_all(self):
        for var in self.check_vars.values():
            var.set(True)

    def deselect_all(self):
        for var in self.check_vars.values():
            var.set(False)

    def log(self, message):
        self.log_box.insert("end", f"{message}\n")
        self.log_box.see("end")

    def trigger_ai_selection(self):
        query = self.prompt_entry.get().strip()
        available_items = list(self.check_vars.keys())
        
        if not available_items:
            self.log("[AutoForge AI] لا توجد حزم لمعالجتها.")
            return
            
        if not query:
            self.log("[AutoForge AI] يرجى إدخال وصف البرامج المطلوبة.")
            return

        api_key = GEMINI_API_KEY.strip()
        self.ask_ai_btn.configure(state="disabled")
        self.log(f"[AutoForge AI] جاري استخراج الحزم المطلوبة وتجاوز المثبت منها...")

        threading.Thread(target=self._query_gemini, args=(query, available_items, api_key), daemon=True).start()

    def _query_gemini(self, user_prompt, available_items, api_key):
        try:
            client = genai.Client(api_key=api_key)
            system_instruction = (
                "You are an expert IT automation assistant for AutoForge AI. Given a user request and a list of local installer filenames/folders, "
                "return a pure JSON array containing ONLY the exact names of files or folders that strictly match the intent. "
                "Do not include commentary or markdown fences."
            )
            prompt = f"Available Packages: {json.dumps(available_items)}\nUser Request: {user_prompt}"
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json"
                )
            )
            selected_items = json.loads(response.text.strip())
            self.after(0, lambda: self._update_ui_after_ai(selected_items))
        except Exception as e:
            self.after(0, lambda: self.log(f"[AI Error] خطأ في الفرز: {str(e)}"))
            self.after(0, lambda: self.ask_ai_btn.configure(state="normal"))

    def _update_ui_after_ai(self, selected_items):
        for name, var in self.check_vars.items():
            if name in selected_items:
                if self.installed_status.get(name, False):
                    self.log(f"  ⓘ تم تخطي {name} لأنه مثبت مسبقاً على الجهاز.")
                    var.set(False)
                else:
                    var.set(True)
            else:
                var.set(False)
        self.log(f"[AutoForge AI] تم تحديث خطة التثبيت بنجاح يا ياسين.")
        self.ask_ai_btn.configure(state="normal")

    def request_stop(self):
        self.stop_requested = True
        self.log("[ALERT] تم إرسال أمر إيقاف فوري للعملية الجارية...")

    def start_installation_thread(self):
        selected_items = [name for name, var in self.check_vars.items() if var.get()]
        if not selected_items:
            self.log("[AutoForge Alert] لم يتم تحديد أي حزمة جديدة للتثبيت!")
            return

        for name in self.check_vars.keys():
            self.set_badge_state(name, "waiting")

        self.stop_requested = False
        self.progress_bar.set(0)
        self.install_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.ask_ai_btn.configure(state="disabled")
        threading.Thread(target=self._run_install, args=(selected_items,), daemon=True).start()

    def _run_install(self, items):
        total = len(items)
        start_time = time.time()
        self.log(f"--- [بدء التثبيت الصامت الفعلي لـ {total} حزمة] ---")

        for idx, item in enumerate(items, start=1):
            if self.stop_requested:
                self.log("[ABORTED] توقفت العملية بناءً على طلبك.")
                break

            full_path = self.items_path_map.get(item, os.path.join(APPS_DIR, item))
            self.log(f"[{idx}/{total}] جاري التثبيت الصامت الفعلي: {item} ...")
            
            self.after(0, lambda n=item: self.set_badge_state(n, "installing"))

            success, msg = execute_silent_installer(full_path)

            if not self.stop_requested:
                if success:
                    self.log(f"  ✓ اكتمل تثبيت {item} بنجاح.")
                    self.after(0, lambda n=item: self.set_badge_state(n, "success"))
                else:
                    self.log(f"  ✗ تعذر التثبيت: {item} ({msg})")
                    self.after(0, lambda n=item: self.set_badge_state(n, "failed"))

            elapsed_sec = int(time.time() - start_time)
            avg_per_item = elapsed_sec / idx if idx > 0 else 1
            remaining_sec = int(avg_per_item * (total - idx))

            elapsed_str = time.strftime("%M:%S", time.gmtime(elapsed_sec))
            remaining_str = time.strftime("%M:%S", time.gmtime(remaining_sec))

            pct = int((idx / total) * 100)
            progress = idx / total

            t = TRANSLATIONS[self.current_lang]
            time_text = t["time_status"].format(elapsed=elapsed_str, eta=remaining_str)
            pct_text = f"{pct}% ({idx}/{total})"

            self.after(0, lambda p=progress, pt=pct_text, tt=time_text: (
                self.progress_bar.set(p),
                self.percentage_label.configure(text=pt),
                self.time_label.configure(text=tt)
            ))

        if not self.stop_requested:
            self.log(TRANSLATIONS[self.current_lang]["finish_msg"])
            self.after(0, lambda: self.progress_bar.set(1.0))
        
        self.install_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.ask_ai_btn.configure(state="normal")

if __name__ == "__main__":
    app = AutoForgeAI()
    app.mainloop()
