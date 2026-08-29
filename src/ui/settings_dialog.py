import customtkinter as ctk
import threading
from src.ai.gemini_service import GeminiService

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, settings_manager, on_save_callback=None):
        super().__init__(parent)

        self.parent = parent
        self.settings_manager = settings_manager
        self.on_save_callback = on_save_callback
        lang = self.settings_manager.get("language", "AR")

        self.title("Paramètres / الإعدادات - AutoForge AI")
        self.geometry("520x450")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Labels by language
        self.texts = {
            "AR": {
                "title": "⚙️ إعدادات النظام والذكاء الاصطناعي",
                "api_key_label": "مفتاح Gemini API Key الخاص بك:",
                "show_key": "إظهار المفتاح",
                "test_btn": "🔌 فحص وتجربة الاتصال",
                "model_label": "نموذج الذكاء الاصطناعي:",
                "skip_label": "تخطي البرامج المثبتة مسبقاً تلقائياً",
                "save_btn": "💾 حفظ الإعدادات",
                "cancel_btn": "إلغاء",
                "testing": "جاري التحقق من الاتصال...",
                "test_ok": "✓ تم التحقق من المفتاح والاتصال بنجاح!",
                "test_err": "✗ فشل الاتصال: "
            },
            "FR": {
                "title": "⚙️ Paramètres Système & IA",
                "api_key_label": "Votre Clé API Google Gemini :",
                "show_key": "Afficher la clé",
                "test_btn": "🔌 Tester la Connexion",
                "model_label": "Modèle d'IA :",
                "skip_label": "Ignorer automatiquement les logiciels déjà installés",
                "save_btn": "💾 Enregistrer",
                "cancel_btn": "Annuler",
                "testing": "Vérification en cours...",
                "test_ok": "✓ Connexion réussie à Google Gemini !",
                "test_err": "✗ Échec : "
            }
        }[lang]

        self.build_ui()

    def build_ui(self):
        t = self.texts

        # Header Title
        lbl_title = ctk.CTkLabel(
            self,
            text=t["title"],
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color="#00ffcc"
        )
        lbl_title.pack(pady=(18, 12))

        # API Key Section
        api_frame = ctk.CTkFrame(self, fg_color="transparent")
        api_frame.pack(fill="x", padx=25, pady=6)

        lbl_api = ctk.CTkLabel(api_frame, text=t["api_key_label"], font=ctk.CTkFont(size=12, weight="bold"))
        lbl_api.pack(anchor="w", pady=(0, 4))

        self.api_entry = ctk.CTkEntry(
            api_frame,
            width=470,
            height=36,
            show="*",
            placeholder_text="AIzaSy..."
        )
        self.api_entry.pack(fill="x")
        self.api_entry.insert(0, self.settings_manager.get_api_key())

        # Toggle Show Key
        self.show_var = ctk.BooleanVar(value=False)
        chk_show = ctk.CTkCheckBox(
            api_frame,
            text=t["show_key"],
            variable=self.show_var,
            command=self.toggle_show_key,
            font=ctk.CTkFont(size=11)
        )
        chk_show.pack(anchor="w", pady=(6, 4))

        # Test Connection Button & Status
        test_frame = ctk.CTkFrame(self, fg_color="transparent")
        test_frame.pack(fill="x", padx=25, pady=4)

        self.btn_test = ctk.CTkButton(
            test_frame,
            text=t["test_btn"],
            command=self.test_api_key,
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=30
        )
        self.btn_test.pack(side="left")

        self.lbl_test_status = ctk.CTkLabel(
            test_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.lbl_test_status.pack(side="left", padx=10)

        # Model Selector & Options
        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.pack(fill="x", padx=25, pady=12)

        lbl_model = ctk.CTkLabel(opt_frame, text=t["model_label"], font=ctk.CTkFont(size=12, weight="bold"))
        lbl_model.pack(anchor="w", pady=(0, 4))

        self.model_combo = ctk.CTkComboBox(
            opt_frame,
            values=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
            width=470,
            height=32
        )
        self.model_combo.pack(fill="x")
        self.model_combo.set(self.settings_manager.get("gemini_model", "gemini-2.5-flash"))

        self.skip_var = ctk.BooleanVar(value=self.settings_manager.get("auto_skip_installed", True))
        chk_skip = ctk.CTkCheckBox(
            self,
            text=t["skip_label"],
            variable=self.skip_var,
            font=ctk.CTkFont(size=12)
        )
        chk_skip.pack(padx=25, pady=(8, 12), anchor="w")

        # Action Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(15, 10))

        btn_save = ctk.CTkButton(
            btn_frame,
            text=t["save_btn"],
            command=self.save_settings,
            fg_color="#00a86b",
            hover_color="#007a4e",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=220,
            height=36
        )
        btn_save.pack(side="left")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text=t["cancel_btn"],
            command=self.destroy,
            fg_color="#334155",
            hover_color="#475569",
            width=220,
            height=36
        )
        btn_cancel.pack(side="right")

    def toggle_show_key(self):
        self.api_entry.configure(show="" if self.show_var.get() else "*")

    def test_api_key(self):
        key = self.api_entry.get().strip()
        model = self.model_combo.get().strip()
        t = self.texts

        self.btn_test.configure(state="disabled")
        self.lbl_test_status.configure(text=t["testing"], text_color="#38bdf8")

        def _worker():
            service = GeminiService(api_key=key, model=model)
            success, msg = service.test_connection()
            if success:
                self.after(0, lambda: self.lbl_test_status.configure(text=t["test_ok"], text_color="#22c55e"))
            else:
                self.after(0, lambda: self.lbl_test_status.configure(text=f"{t['test_err']}{msg[:35]}...", text_color="#ef4444"))
            self.after(0, lambda: self.btn_test.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def save_settings(self):
        key = self.api_entry.get().strip()
        model = self.model_combo.get().strip()
        skip = self.skip_var.get()

        self.settings_manager.set_api_key(key)
        self.settings_manager.set("gemini_model", model)
        self.settings_manager.set("auto_skip_installed", skip)

        if self.on_save_callback:
            self.on_save_callback()

        self.destroy()
