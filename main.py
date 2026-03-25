# main.py
import sys

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
