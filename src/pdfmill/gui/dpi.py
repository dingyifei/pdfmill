"""High-DPI awareness utilities for Windows."""

import ctypes
import platform


def enable_high_dpi():
    """Enable high DPI awareness on Windows for crisp rendering."""
    if platform.system() == "Windows":
        try:
            # Windows 10 1703+ (Per-Monitor V2 DPI awareness)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                # Windows 8.1+ (Per-Monitor DPI awareness)
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                try:
                    # Windows Vista+ (System DPI awareness)
                    ctypes.windll.user32.SetProcessDPIAware()
                except (AttributeError, OSError):
                    pass
