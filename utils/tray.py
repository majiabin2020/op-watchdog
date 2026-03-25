# utils/tray.py
import threading
from typing import Callable, Optional

import pystray

from assets.icon import create_icon
from config import APP_NAME
from utils.autostart import AutostartManager
from utils.notifier import Notifier


class TrayManager:
    def __init__(
        self,
        on_show_window: Callable,
        on_exit: Callable,
        notifier: Notifier,
        autostart: AutostartManager,
        main_thread_dispatch: Optional[Callable[[Callable], None]] = None,
    ):
        self._on_show_window = on_show_window
        self._on_exit = on_exit
        self._notifier = notifier
        self._autostart = autostart
        # dispatch schedules a no-arg callable onto the main thread.
        # In production: lambda fn: root.after(0, fn)
        # In tests / fallback: call directly
        self._dispatch = main_thread_dispatch or (lambda fn: fn())
        self._icon: Optional[pystray.Icon] = None

    def _build_menu(self) -> pystray.Menu:
        autostart_label = (
            "开机自动启动  [●开]"
            if self._autostart.is_enabled()
            else "开机自动启动  [●关]"
        )
        return pystray.Menu(
            pystray.MenuItem(APP_NAME, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("显示主窗口", self._handle_show),
            pystray.MenuItem(autostart_label, self._handle_toggle_autostart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._handle_exit),
        )

    def _handle_show(self, icon, item) -> None:
        self._dispatch(self._on_show_window)

    def _handle_toggle_autostart(self, icon, item) -> None:
        if self._autostart.is_enabled():
            self._autostart.disable()
        else:
            self._autostart.enable()
        icon.menu = self._build_menu()

    def _handle_exit(self, icon, item) -> None:
        icon.stop()
        self._dispatch(self._on_exit)

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        icon_image = create_icon()
        self._icon = pystray.Icon(
            APP_NAME,
            icon_image,
            APP_NAME,
            menu=self._build_menu(),
        )
        self._icon.default_action = self._handle_show
        self._notifier.set_icon(self._icon)

        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            finally:
                self._icon = None
