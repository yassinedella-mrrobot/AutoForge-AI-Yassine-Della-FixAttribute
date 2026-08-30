import os
import time
import json
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from src.config.settings import SettingsManager, get_apps_dir
from src.core.registry_scanner import RegistryScanner
from src.core.installer_engine import InstallerEngine
from src.ai.gemini_service import GeminiService
from src.ui.settings_dialog import SettingsDialog
from src.ui.components import TRANSLATIONS

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings_manager = SettingsManager()
        self.installer_engine = InstallerEngine()
        self.gemini_service = GeminiService(
            api_key=self.settings_manager.get_api_key(),
            model=self.settings_manager.get("gemini_model", "gemini-2.5-flash")
        )

        self.current_lang = self.settings_manager.get("language", "AR")
        self.current_theme = self.settings_manager.get("theme", "dark")
        self.stop_requested = False
        self.custom_paths = list(self.settings_manager.get("custom_paths", []))
        self.anim_step = 0
        self.current_filter = ""
        self.selected_category = "all"

        # Data maps
        self.all_items = {}          # {name: {"path": path, "category": cat, "installed": bool, "ver": str, "priority": int}}
        self.check_vars = {}         # {name: BooleanVar}
        self.status_badges = {}      # {name: CTkLabel}
        self.card_frames = {}        # {name: CTkFrame}

        # Window Setup
        self.title("AutoForge AI - Enterprise Edition (by Yassine Della)")
        self.geometry("820x960")
        self.minsize(780, 850)
        ctk.set_appearance_mode(self.current_theme)
        ctk.set_default_color_theme("blue")

        apps_dir = get_apps_dir()
        if not os.path.exists(apps_dir):
            try:
                os.makedirs(apps_dir)
            except Exception:
                pass

        self.build_ui()
        self.load_local_apps()
        self.run_dynamic_animations()

    def build_ui(self):
        t = TRANSLATIONS[self.current_lang]

        # 1. Top Bar
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=(10, 0))

        self.lang_btn = ctk.CTkButton(
            self.top_bar,
            text="🌐 Français" if self.current_lang == "AR" else "🌐 العربية",
            width=90,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            command=self.toggle_language
        )
        self.lang_btn.pack(side="left", padx=4)

        self.theme_btn = ctk.CTkButton(
            self.top_bar,
            text="☀️ Mode Clair" if self.current_theme == "dark" else "🌙 Mode Sombre",
            width=110,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=4)

        self.btn_settings = ctk.CTkButton(
            self.top_bar,
            text=t["settings"],
            width=95,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.open_settings
        )
        self.btn_settings.pack(side="left", padx=4)

        self.admin_badge = ctk.CTkLabel(
            self.top_bar,
            text="🛡️ ADMIN UAC ACTIVE",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#00ffcc",
            fg_color="#064e3b",
            corner_radius=4,
            width=140,
            height=24
        )
        self.admin_badge.pack(side="left", padx=8)

        self.count_label = ctk.CTkLabel(
            self.top_bar,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.count_label.pack(side="right", padx=5)

        # 2. Header Card
        self.header_card = ctk.CTkFrame(
            self,
            fg_color="#0f172a" if self.current_theme == "dark" else "#e2e8f0",
            corner_radius=12,
            border_width=1,
            border_color="#1e293b"
        )
        self.header_card.pack(fill="x", padx=20, pady=(8, 4))

        self.title_label = ctk.CTkLabel(
            self.header_card,
            text=t["title"],
            font=ctk.CTkFont(family="Consolas", size=24, weight="bold"),
            text_color="#00ffcc"
        )
        self.title_label.pack(pady=(6, 0))

        self.author_label = ctk.CTkLabel(
            self.header_card,
            text=t["author"],
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.author_label.pack(pady=(0, 2))

        self.subtitle_label = ctk.CTkLabel(
            self.header_card,
            text=t["subtitle"],
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.subtitle_label.pack(pady=(0, 6))

        # 3. AI Search Bar
        ai_frame = ctk.CTkFrame(self, fg_color="transparent")
        ai_frame.pack(fill="x", padx=20, pady=2)

        self.prompt_entry = ctk.CTkEntry(
            ai_frame,
            placeholder_text=t["placeholder"],
            height=40,
            font=ctk.CTkFont(size=13),
            border_color="#0284c7"
        )
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.ask_ai_btn = ctk.CTkButton(
            ai_frame,
            text=t["ask_ai"],
            command=self.trigger_ai_selection,
            height=40,
            width=220,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.ask_ai_btn.pack(side="right")

        # 4. Quick Action Tools & Preset Bar
        self.tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tools_frame.pack(fill="x", padx=20, pady=3)

        self.btn_select_uninst = ctk.CTkButton(
            self.tools_frame,
            text=t["select_uninstalled"],
            width=110,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.select_uninstalled_only
        )
        self.btn_select_uninst.pack(side="left", padx=2)

        self.btn_select_all = ctk.CTkButton(
            self.tools_frame,
            text=t["select_all"],
            width=85,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            command=self.select_all
        )
        self.btn_select_all.pack(side="left", padx=2)

        self.btn_deselect_all = ctk.CTkButton(
            self.tools_frame,
            text=t["deselect_all"],
            width=85,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#475569",
            hover_color="#334155",
            command=self.deselect_all
        )
        self.btn_deselect_all.pack(side="left", padx=2)

        self.btn_add_custom = ctk.CTkButton(
            self.tools_frame,
            text=t["add_custom"],
            width=150,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#0d9488",
            hover_color="#0f766e",
            command=self.add_custom_path
        )
        self.btn_add_custom.pack(side="left", padx=2)

        self.btn_refresh = ctk.CTkButton(
            self.tools_frame,
            text=t["refresh"],
            width=80,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.load_local_apps
        )
        self.btn_refresh.pack(side="right", padx=2)

        # 5. Live Search / Filter & Category Bar
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.pack(fill="x", padx=20, pady=2)

        self.filter_entry = ctk.CTkEntry(
            self.filter_frame,
            placeholder_text=t["filter_placeholder"],
            height=28,
            font=ctk.CTkFont(size=11),
            border_color="#334155"
        )
        self.filter_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.filter_entry.bind("<KeyRelease>", self.on_filter_changed)

        # Category buttons
        self.cat_btns_frame = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        self.cat_btns_frame.pack(side="right")

        self.cat_all_btn = ctk.CTkButton(
            self.cat_btns_frame,
            text=t["preset_all"],
            width=45,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#0284c7",
            command=lambda: self.set_category_filter("all")
        )
        self.cat_all_btn.pack(side="left", padx=1)

        self.cat_audio_btn = ctk.CTkButton(
            self.cat_btns_frame,
            text=t["preset_audio"],
            width=70,
            height=26,
            font=ctk.CTkFont(size=10),
            fg_color="#1e293b",
            command=lambda: self.set_category_filter("audiology")
        )
        self.cat_audio_btn.pack(side="left", padx=1)

        self.cat_drivers_btn = ctk.CTkButton(
            self.cat_btns_frame,
            text=t["preset_drivers"],
            width=70,
            height=26,
            font=ctk.CTkFont(size=10),
            fg_color="#1e293b",
            command=lambda: self.set_category_filter("drivers")
        )
        self.cat_drivers_btn.pack(side="left", padx=1)

        self.cat_runtimes_btn = ctk.CTkButton(
            self.cat_btns_frame,
            text=t["preset_runtimes"],
            width=75,
            height=26,
            font=ctk.CTkFont(size=10),
            fg_color="#1e293b",
            command=lambda: self.set_category_filter("runtimes")
        )
        self.cat_runtimes_btn.pack(side="left", padx=1)

        # 6. Scrollable Apps List Frame
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            height=230,
            label_text=t["frame_title"],
            label_font=ctk.CTkFont(size=12, weight="bold")
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=4)

        # 7. Status, Time & Progress Bar
        self.status_info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_info_frame.pack(fill="x", padx=25, pady=(2, 1))

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

        self.progress_bar = ctk.CTkProgressBar(self, height=12)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(2, 4))

        # 8. Action Buttons (Install / Stop)
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.pack(fill="x", padx=20, pady=3)

        self.install_btn = ctk.CTkButton(
            self.actions_frame,
            text=t["btn_install"],
            command=self.start_installation_thread,
            height=40,
            fg_color="#00a86b",
            hover_color="#007a4e",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.install_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.stop_btn = ctk.CTkButton(
            self.actions_frame,
            text=t["btn_stop"],
            command=self.request_stop,
            height=40,
            fg_color="#b91c1c",
            hover_color="#7f1d1d",
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled"
        )
        self.stop_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # 9. Logs & Export Frame
        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(2, 0))

        lbl_log = ctk.CTkLabel(log_header, text="📜 Journal d'exécution / سجل العمليات", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_log.pack(side="left")

        self.btn_export = ctk.CTkButton(
            log_header,
            text=t["export_log"],
            width=110,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color="#334155",
            hover_color="#475569",
            command=self.export_logs
        )
        self.btn_export.pack(side="right")

        self.log_box = ctk.CTkTextbox(self, height=110, font=ctk.CTkFont(family="Consolas", size=10))
        self.log_box.pack(fill="x", padx=20, pady=(2, 8))
        self.log_box.insert("end", f"[System Init] AutoForge AI Engine Initialized.\n" + t["system_ready"])

    def open_settings(self):
        SettingsDialog(self, self.settings_manager, on_save_callback=self.on_settings_saved)

    def on_settings_saved(self):
        self.gemini_service.set_api_key(self.settings_manager.get_api_key())
        self.gemini_service.model = self.settings_manager.get("gemini_model", "gemini-2.5-flash")
        self.log("[Settings] Paramètres mis à jour avec succès.")

    def run_dynamic_animations(self):
        if not self.winfo_exists():
            return
        self.anim_step = (self.anim_step + 1) % 60
        neon_cyan_shades = ["#00ffcc", "#38bdf8", "#818cf8", "#c084fc", "#38bdf8", "#00ffcc"]
        neon_border_shades = ["#0284c7", "#0ea5e9", "#06b6d4", "#10b981", "#0284c7"]

        c_idx = (self.anim_step // 10) % len(neon_cyan_shades)
        b_idx = (self.anim_step // 12) % len(neon_border_shades)

        title_color = neon_cyan_shades[c_idx]
        border_glow = neon_border_shades[b_idx]

        dots = "·" * ((self.anim_step % 4) + 1)
        author_animated = f"⚡ NEURAL LINK: YASSINE DELLA [LIVE{dots}] ⚡"

        try:
            self.title_label.configure(text_color=title_color)
            self.author_label.configure(text=author_animated)
            self.header_card.configure(border_color=border_glow)
            self.after(120, self.run_dynamic_animations)
        except Exception:
            pass

    def toggle_language(self):
        self.current_lang = "FR" if self.current_lang == "AR" else "AR"
        self.settings_manager.set("language", self.current_lang)
        t = TRANSLATIONS[self.current_lang]

        self.lang_btn.configure(text="🌐 العربية" if self.current_lang == "FR" else "🌐 Français")
        self.subtitle_label.configure(text=t["subtitle"])
        self.prompt_entry.configure(placeholder_text=t["placeholder"])
        self.filter_entry.configure(placeholder_text=t["filter_placeholder"])
        self.ask_ai_btn.configure(text=t["ask_ai"])
        self.btn_select_uninst.configure(text=t["select_uninstalled"])
        self.btn_select_all.configure(text=t["select_all"])
        self.btn_deselect_all.configure(text=t["deselect_all"])
        self.btn_refresh.configure(text=t["refresh"])
        self.btn_settings.configure(text=t["settings"])
        self.btn_export.configure(text=t["export_log"])
        self.btn_add_custom.configure(text=t["add_custom"])
        self.list_frame.configure(label_text=t["frame_title"])
        self.install_btn.configure(text=t["btn_install"])
        self.stop_btn.configure(text=t["btn_stop"])

        self.cat_all_btn.configure(text=t["preset_all"])
        self.cat_audio_btn.configure(text=t["preset_audio"])
        self.cat_drivers_btn.configure(text=t["preset_drivers"])
        self.cat_runtimes_btn.configure(text=t["preset_runtimes"])

        self.render_app_cards()

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.settings_manager.set("theme", self.current_theme)
        ctk.set_appearance_mode(self.current_theme)
        self.theme_btn.configure(text="☀️ Mode Clair" if self.current_theme == "dark" else "🌙 Mode Sombre")
        self.header_card.configure(fg_color="#0f172a" if self.current_theme == "dark" else "#e2e8f0")
        self.render_app_cards()

    def on_filter_changed(self, event=None):
        self.current_filter = self.filter_entry.get().strip().lower()
        self.render_app_cards()

    def set_category_filter(self, cat_id):
        self.selected_category = cat_id
        btns = [
            (self.cat_all_btn, "all"),
            (self.cat_audio_btn, "audiology"),
            (self.cat_drivers_btn, "drivers"),
            (self.cat_runtimes_btn, "runtimes")
        ]
        for btn, c_id in btns:
            if c_id == cat_id:
                btn.configure(fg_color="#0284c7")
            else:
                btn.configure(fg_color="#1e293b" if self.current_theme == "dark" else "#94a3b8")
        self.render_app_cards()

    def load_local_apps(self):
        """Scans Apps folder and Windows registry to build app metadata."""
        apps_dir = get_apps_dir()
        installed_dict = RegistryScanner.get_installed_applications()
        auto_skip = self.settings_manager.get("auto_skip_installed", True)

        new_items = {}

        if os.path.exists(apps_dir):
            for item in os.listdir(apps_dir):
                if item.startswith('.'):
                    continue
                full_path = os.path.join(apps_dir, item)
                is_dir = os.path.isdir(full_path)
                if (os.path.isfile(full_path) and item.lower().endswith(('.exe', '.msi', '.msp'))) or is_dir:
                    cat_info = self.installer_engine.get_category_info(item, is_dir)
                    is_inst, ver, matched_name = RegistryScanner.check_is_installed(item, installed_dict)
                    new_items[item] = {
                        "path": full_path,
                        "category": cat_info,
                        "installed": is_inst,
                        "version": ver,
                        "matched_name": matched_name,
                        "priority": cat_info.get("priority", 10)
                    }

        for c_path in self.custom_paths:
            base_name = f"[PC] {os.path.basename(c_path)}"
            is_dir = os.path.isdir(c_path)
            cat_info = self.installer_engine.get_category_info(base_name, is_dir)
            is_inst, ver, matched_name = RegistryScanner.check_is_installed(base_name.replace("[PC] ", ""), installed_dict)
            new_items[base_name] = {
                "path": c_path,
                "category": cat_info,
                "installed": is_inst,
                "version": ver,
                "matched_name": matched_name,
                "priority": cat_info.get("priority", 10)
            }

        self.all_items = new_items
        
        # Initialize checkboxes
        for name, data in self.all_items.items():
            if name not in self.check_vars:
                # If auto_skip is enabled, leave installed apps unchecked by default
                self.check_vars[name] = ctk.BooleanVar(value=not data["installed"] if auto_skip else True)

        self.render_app_cards()

    def render_app_cards(self):
        """Renders filtered cards into list_frame."""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        self.status_badges.clear()
        self.card_frames.clear()

        t = TRANSLATIONS[self.current_lang]
        total_count = len(self.all_items)
        self.count_label.configure(text=t["total_count"].format(count=total_count))
        self.percentage_label.configure(text=f"0% (0/{total_count})")

        filtered_items = []
        for name, data in self.all_items.items():
            # 1. Filter by category
            if self.selected_category != "all":
                if data["category"]["id"] != self.selected_category:
                    continue
            
            # 2. Filter by search text
            if self.current_filter:
                if self.current_filter not in name.lower() and self.current_filter not in data["category"]["id"].lower():
                    continue

            filtered_items.append((name, data))

        if not filtered_items:
            lbl = ctk.CTkLabel(self.list_frame, text=t["empty_apps"], text_color="orange")
            lbl.pack(pady=25)
            return

        for name, data in filtered_items:
            cat = data["category"]
            icon = cat["icon"]
            is_inst = data["installed"]
            ver = data.get("version", "")

            card = ctk.CTkFrame(
                self.list_frame,
                fg_color="#1e293b" if self.current_theme == "dark" else "#f1f5f9",
                corner_radius=6
            )
            card.pack(fill="x", padx=5, pady=3)
            self.card_frames[name] = card

            # Icon
            icon_lbl = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=16), width=28)
            icon_lbl.pack(side="left", padx=(8, 2), pady=6)

            # Checkbox
            var = self.check_vars[name]
            if is_inst:
                tag_text = t["installed_tag"].format(ver=ver if ver else "✓")
                cb_text = f"{name} {tag_text}"
                cb_color = "#f59e0b"
            else:
                cb_text = f"{name}"
                cb_color = "#ffffff" if self.current_theme == "dark" else "#0f172a"

            cb = ctk.CTkCheckBox(
                card,
                text=cb_text,
                variable=var,
                text_color=cb_color,
                font=ctk.CTkFont(size=12)
            )
            cb.pack(side="left", padx=4, pady=6)

            # Status Badge
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
        for name, data in self.all_items.items():
            if name in self.check_vars:
                self.check_vars[name].set(not data["installed"])

    def select_all(self):
        for var in self.check_vars.values():
            var.set(True)

    def deselect_all(self):
        for var in self.check_vars.values():
            var.set(False)

    def add_custom_path(self):
        paths = filedialog.askopenfilenames(
            title="Choisir des installeurs / اختر ملفات التثبيت",
            filetypes=[("Installers", "*.exe;*.msi;*.msp"), ("All Files", "*.*")]
        )
        if not paths:
            folder = filedialog.askdirectory(title="Choisir un dossier d'installation / اختر مجلد تثبيت")
            if folder:
                paths = [folder]

        for p in paths:
            if p and p not in self.custom_paths:
                self.custom_paths.append(p)

        self.settings_manager.set("custom_paths", self.custom_paths)
        self.load_local_apps()

    def log(self, message):
        self.log_box.insert("end", f"{message}\n")
        self.log_box.see("end")

    def export_logs(self):
        logs = self.log_box.get("1.0", "end")
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Log", "*.txt"), ("All Files", "*.*")],
            initialfile=f"autoforge_log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(logs)
                messagebox.showinfo("Export", "Journal exporté avec succès !")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de l'exportation : {str(e)}")

    def trigger_ai_selection(self):
        query = self.prompt_entry.get().strip()
        available_items = list(self.all_items.keys())

        if not available_items:
            self.log("[AutoForge AI] Aucun paquet disponible.")
            return

        if not query:
            self.log("[AutoForge AI] Veuillez saisir votre demande dans le champ IA.")
            return

        self.ask_ai_btn.configure(state="disabled")
        self.log(f"[AutoForge AI] Analyse neuronale de la requête : '{query}'...")

        def _worker():
            try:
                selected_items = self.gemini_service.select_packages(query, available_items)
                self.after(0, lambda: self._update_ui_after_ai(selected_items))
            except Exception as e:
                self.after(0, lambda: self.log(f"[AI Error] {str(e)}"))
                self.after(0, lambda: self.ask_ai_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_ui_after_ai(self, selected_items):
        auto_skip = self.settings_manager.get("auto_skip_installed", True)
        count_selected = 0

        for name, data in self.all_items.items():
            var = self.check_vars.get(name)
            if not var:
                continue

            if name in selected_items:
                if data["installed"] and auto_skip:
                    self.log(f"  ⓘ Ignoré : {name} (déjà présent sur la machine)")
                    var.set(False)
                else:
                    var.set(True)
                    count_selected += 1
            else:
                var.set(False)

        self.log(f"[AutoForge AI] Plan mis à jour : {count_selected} paquets sélectionnés.")
        self.ask_ai_btn.configure(state="normal")

    def request_stop(self):
        self.stop_requested = True
        self.log("[ALERT] Arrêt d'urgence demandé ! Interruption immédiate du processus...")
        # Forcefully terminate active installer process tree immediately
        self.installer_engine.kill_current_process()

    def start_installation_thread(self):
        # Gather selected items sorted by priority (higher priority first, e.g., runtimes)
        selected_pairs = []
        for name, data in self.all_items.items():
            var = self.check_vars.get(name)
            if var and var.get():
                selected_pairs.append((data["priority"], name, data["path"]))

        if not selected_pairs:
            self.log("[AutoForge Alert] Aucun paquet coché pour l'installation !")
            return

        # Sort descending by priority
        selected_pairs.sort(key=lambda x: x[0], reverse=True)
        items_to_install = [(name, path) for _, name, path in selected_pairs]

        for name in self.all_items.keys():
            self.set_badge_state(name, "waiting")

        self.stop_requested = False
        self.progress_bar.set(0)
        self.install_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.ask_ai_btn.configure(state="disabled")

        threading.Thread(target=self._run_install, args=(items_to_install,), daemon=True).start()

    def _run_install(self, items):
        total = len(items)
        start_time = time.time()
        self.log(f"\n========================================================")
        self.log(f"--- [DÉBUT DE L'INSTALLATION SILENCIEUSE : {total} PAQUET(S)] ---")
        self.log(f"========================================================")

        for idx, (item_name, full_path) in enumerate(items, start=1):
            if self.stop_requested:
                self.log("[ABORTED] Processus arrêté suite à votre demande.")
                break

            self.log(f"\n[{idx}/{total}] Installation silencieuse : {item_name} ...")
            self.after(0, lambda n=item_name: self.set_badge_state(n, "installing"))

            success, msg = self.installer_engine.execute_installer(
                full_path,
                on_log=lambda m: self.after(0, lambda msg=m: self.log(msg))
            )

            if not self.stop_requested:
                if success:
                    self.log(f"  ✓ {item_name} : {msg}")
                    self.after(0, lambda n=item_name: self.set_badge_state(n, "success"))
                else:
                    self.log(f"  ✗ {item_name} : {msg}")
                    self.after(0, lambda n=item_name: self.set_badge_state(n, "failed"))

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
            self.log(f"\n{TRANSLATIONS[self.current_lang]['finish_msg']}\n")
            self.after(0, lambda: self.progress_bar.set(1.0))

        self.after(0, self._cleanup_after_install)

    def _cleanup_after_install(self):
        self.install_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.ask_ai_btn.configure(state="normal")
        # Re-scan to update installed statuses
        self.load_local_apps()
