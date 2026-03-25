# utils/notifier.py
from typing import Optional


class Notifier:
    """Sends Windows system tray balloon notifications via pystray."""

    def __init__(self):
        self._icon = None  # Set by TrayManager after tray is ready

    def set_icon(self, icon) -> None:
        self._icon = icon

    def send(self, title: str, message: str) -> None:
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass  # Notifications are best-effort
