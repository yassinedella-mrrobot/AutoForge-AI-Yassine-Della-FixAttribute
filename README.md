# ⚡ AutoForge AI - Enterprise Edition
**Architect & Developer : Yassine Della**

AutoForge AI est une application Windows moderne et intelligente d'automatisation de déploiement logiciel et d'installation silencieuse assistée par l'Intelligence Artificielle (**Google Gemini**).

---

## 🌟 Nouvelles Fonctionnalités & Améliorations

### 1. 🔒 Sécurité et Gestion de la Clé API
* **Zéro clé en dur** : Fin des clés API stockées dans le code source.
* **Fenêtre Paramètres (`⚙️`)** : Permet de saisir, afficher/masquer, tester la connexion avec l'IA et choisir le modèle Gemini (`gemini-2.5-flash`, `gemini-2.5-pro`).
* **Persistance locale** : Paramètres sauvegardés proprement dans `autoforge_config.json`.

### 2. ⚙️ Moteur d'Installation Silencieuse Robuste
* **Arrêt d'urgence instantané (`⏹`)** : Suivi des sous-processus (`Popen` et `taskkill /F /T /PID`) permettant d'interrompre immédiatement un installeur bloqué.
* **Ordonnancement prioritaire** : Installation prioritaire automatique des dépendances et runtimes (Visual C++, .NET Framework, DirectX).
* **Règles configurables** : Base JSON (`src/config/installer_rules.json`) pour personnaliser les commutateurs silencieux et catégories.

### 3. 🔍 Recherche Instantanée & Catégories
* **Filtre en direct** : Champ de recherche dynamique pour filtrer instantanément les logiciels par nom ou type.
* **Filtres par catégories** : Boutons rapides pour isoler les paquets :
  * 🦻 **Audiologie & Prothèses** (Hansaton, Audifon, Oticon, Phonak, Signia...)
  * 🔌 **Pilotes & Interfaces** (HiPro, USB, FTDI, Drivers...)
  * ⚙️ **Runtimes & Dépendances** (VC++, .NET, DirectX...)
  * 🌐 **Navigateurs Web** (Chrome, Firefox, Edge, Opera...)
  * 📦 **Utilitaires & Compression** (WinRAR, 7-Zip, AnyDesk...)

### 4. 📊 Détection Avancée du Registre Windows
* Scan précis du registre Windows (HKLM 64-bit, HKLM 32-bit / WOW6432Node, HKCU).
* Détection du statut d'installation et de la version exacte installée (`DisplayVersion`).

### 5. 📋 Exportation des Journaux & Diagnostics
* Bouton d'exportation directe (`📋 Exporter Journal`) pour sauvegarder les rapports d'installation avec horodatage et codes de sortie.

---

## 🏗️ Architecture du Projet

```text
AutoForge-AI/
├── Apps/                           # Dossier où déposer vos installeurs (.exe, .msi)
├── src/
│   ├── autoforge_app.py            # Point d'entrée principal & Élévation UAC
│   ├── config/
│   │   ├── settings.py             # Gestionnaire de configuration (API Key, Thème, Langue)
│   │   └── installer_rules.json    # Règles de détection, drapeaux silencieux et catégories
│   ├── core/
│   │   ├── registry_scanner.py     # Scanner du Registre Windows & Détection de versions
│   │   └── installer_engine.py     # Exécution Popen, Process Tree Kill & Ordonnancement
│   ├── ai/
│   │   └── gemini_service.py       # Client Google Gemini & Test de connexion
│   └── ui/
│       ├── components.py           # Textes multilingues (Arabe / Français) & Éléments UI
│       ├── settings_dialog.py      # Boîte de dialogue des Paramètres
│       └── main_window.py          # Fenêtre principale CustomTkinter
├── tests/
│   └── test_modules.py             # Tests unitaires des composants
├── build.bat                       # Script de compilation PyInstaller (Onefile + UAC Admin)
└── requirements.txt                # Dépendances Python
```

---

## 🚀 Utilisation & Lancement

### Lancement direct :
```bash
python src/autoforge_app.py
```

### Compilation en Exécutable Autonome (`.exe`) :
Double-cliquez sur `build.bat` ou exécutez :
```bash
pyinstaller --noconsole --onefile --uac-admin --add-data "src/config/installer_rules.json;src/config" --name "AutoForge-AI" --distpath ./build_output src/autoforge_app.py
```
L'exécutable final sera généré dans `build_output/AutoForge-AI.exe`.
