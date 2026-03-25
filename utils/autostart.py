# utils/autostart.py
import sys
import winreg
from config import AUTOSTART_KEY

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutostartManager:
    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, AUTOSTART_KEY)
            return True
        except FileNotFoundError:
            return False

    def enable(self) -> None:
        """Write autostart registry entry. No-op if permission denied."""
        # sys.executable points to the bundled .exe when packaged with PyInstaller
        exe_path = sys.executable
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, AUTOSTART_KEY, 0, winreg.REG_SZ, exe_path)
        except (PermissionError, OSError):
            pass  # Silently fail if registry is locked (rare on HKCU but possible)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, AUTOSTART_KEY)
        except FileNotFoundError:
            pass
