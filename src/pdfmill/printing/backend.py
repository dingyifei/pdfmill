"""Printer backend interface."""

import sys
from pathlib import Path
from typing import Protocol

from pdfmill.config import PrintTarget


class PrinterError(Exception):
    """Raised when a printer is unavailable or a print job is rejected."""


class Backend(Protocol):
    name: str

    def list_printers(self) -> list[str]:
        """Names usable as ``printer:`` in a config."""

    def check_printer(self, printer: str) -> None:
        """Raise PrinterError unless ``printer`` exists and will print jobs now."""

    def command(self, path: Path, target: PrintTarget, title: str) -> list[str]:
        """The command line that prints ``path`` (also shown in dry runs)."""

    def print_file(self, path: Path, target: PrintTarget, title: str) -> str:
        """Submit a job and return its id. Raise PrinterError if it was not accepted."""


def get_backend(name: str = "auto") -> Backend:
    """Return the backend for ``settings.print_backend`` (auto: SumatraPDF on Windows, else CUPS)."""
    if name == "auto":
        name = "sumatra" if sys.platform == "win32" else "cups"
    if name == "cups":
        from pdfmill.printing.cups import CupsBackend

        return CupsBackend()
    if name == "sumatra":
        from pdfmill.printing.sumatra import SumatraBackend

        return SumatraBackend()
    raise ValueError(f"Unknown print backend: {name}")
