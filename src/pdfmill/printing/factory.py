"""Factory functions for printer backend selection."""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdfmill.printing.base import PrinterBackend


def get_default_backend() -> "PrinterBackend":
    """Get the appropriate printer backend for the current platform.

    Returns:
        PrinterBackend instance appropriate for the current OS

    Platform support:
        - Windows: SumatraBackend
        - Other: MockBackend (placeholder for future CUPS/lpr support)
    """
    if sys.platform == "win32":
        from pdfmill.printing.sumatra import SumatraBackend
        return SumatraBackend()
    else:
        # For non-Windows platforms, return mock backend for now
        # Future: Add CupsBackend for Linux, LprBackend for macOS
        from pdfmill.printing.mock import MockBackend
        return MockBackend(
            printers=["Platform printing not supported"],
            fail_on_print=True,
        )


def get_backend(name: str) -> "PrinterBackend":
    """Get a specific printer backend by name.

    Args:
        name: Backend name ('sumatra', 'mock')

    Returns:
        PrinterBackend instance

    Raises:
        ValueError: If backend name is not recognized
    """
    backends = {
        "sumatra": lambda: _get_sumatra(),
        "mock": lambda: _get_mock(),
    }

    if name not in backends:
        available = ", ".join(sorted(backends.keys()))
        raise ValueError(f"Unknown printer backend: '{name}'. Available: {available}")

    return backends[name]()


def _get_sumatra() -> "PrinterBackend":
    from pdfmill.printing.sumatra import SumatraBackend
    return SumatraBackend()


def _get_mock() -> "PrinterBackend":
    from pdfmill.printing.mock import MockBackend
    return MockBackend()
