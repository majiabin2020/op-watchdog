# assets/icon.py
import os
import sys

from PIL import Image


def _ico_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", "icon.ico")


def create_icon(size: int = 64) -> Image.Image:
    """Load icon.ico for use as tray/window icon."""
    return Image.open(_ico_path()).resize((size, size), Image.LANCZOS)


def ico_path() -> str:
    """Return absolute path to icon.ico (for tkinter iconbitmap)."""
    return _ico_path()
