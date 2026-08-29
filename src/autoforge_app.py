import os
import sys
import ctypes

# -------------------------------------------------------------
# Ensure Root and Source Path are available for imports
# -------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -------------------------------------------------------------
# UAC Administrator Elevation Check
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

# -------------------------------------------------------------
# Main Application Entry Point
# -------------------------------------------------------------
def main():
    enforce_admin_privileges()
    
    # Import UI after path setup
    from src.ui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
