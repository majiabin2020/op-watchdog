# main.py
import ctypes
import sys

# ── Single-instance guard ─────────────────────────────────────────────────────
# CreateMutexW returns ERROR_ALREADY_EXISTS (183) if another instance holds it.
_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, True, "LaomaClawWatchdog_SingleInstance")
if ctypes.windll.kernel32.GetLastError() == 183:
    ctypes.windll.user32.MessageBoxW(
        0,
        "老马OpenClaw小龙虾看门狗已经在运行中。",
        "已在运行",
        0x30,  # MB_ICONWARNING
    )
    sys.exit(0)

# ── DPI awareness — must be called before tkinter starts ──────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # System DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from core.gateway import GatewayManager
from core.watchdog import WatchdogThread, WatchdogState
from ui.main_window import MainWindow
from utils.autostart import AutostartManager
from utils.notifier import Notifier
from utils.tray import TrayManager


def main():
    # ── Instantiate all components ────────────────────────────────────
    gateway = GatewayManager()
    watchdog = WatchdogThread(gateway=gateway)
    notifier = Notifier()
    autostart = AutostartManager()

    # ── Create main window first (it owns the tk.Tk root) ─────────────
    window = MainWindow(
        on_start=watchdog.start_watching,
        on_stop=watchdog.stop,
        on_hide=lambda: window.hide(),
        on_exit=lambda: _exit(watchdog, tray),
    )

    # ── Create tray — pass main_thread_dispatch for thread safety ─────
    tray = TrayManager(
        on_show_window=window.show,
        on_exit=lambda: _exit(watchdog, tray),
        notifier=notifier,
        autostart=autostart,
        main_thread_dispatch=lambda fn: window.get_root().after(0, fn),
    )

    # ── Wire watchdog callbacks → UI ──────────────────────────────────
    watchdog.on_status_change = window.on_state_change
    watchdog.on_log = window.append_log
    watchdog.on_notify = notifier.send
    watchdog.on_restart_count = window.on_restart_count

    # ── Start ─────────────────────────────────────────────────────────
    tray.start()
    window.run()  # Blocks until mainloop exits


def _exit(watchdog: WatchdogThread, tray: TrayManager) -> None:
    """Clean shutdown: stop monitoring and exit."""
    watchdog.stop()
    tray.stop()
    sys.exit(0)


if __name__ == "__main__":
    main()
