"""Internationalization support for pdfmill GUI."""

import gettext
import locale
from pathlib import Path


def _get_system_language() -> str:
    """Get the system's preferred language code."""
    try:
        lang, _ = locale.getdefaultlocale()
        if lang:
            return lang.split("_")[0]  # e.g., 'zh' from 'zh_CN'
    except Exception:
        pass
    return "en"


def _setup_translations():
    """Set up gettext translations based on system locale."""
    lang = _get_system_language()

    # locales/ is at project root, relative to this file:
    # src/pdfmill/gui/i18n.py -> ../../../../locales
    locales_dir = Path(__file__).parent.parent.parent.parent / "locales"

    try:
        translations = gettext.translation("pdfmill", locales_dir, languages=[lang])
        return translations.gettext
    except FileNotFoundError:
        # No translation found, return identity function
        return lambda s: s


# Global translation function
_ = _setup_translations()
