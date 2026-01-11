"""Printing package with backend abstraction for extensible print support."""

from pdfmill.printing.base import PrinterBackend
from pdfmill.printing.sumatra import SumatraBackend
from pdfmill.printing.mock import MockBackend
from pdfmill.printing.factory import get_default_backend, get_backend

__all__ = [
    "PrinterBackend",
    "SumatraBackend",
    "MockBackend",
    "get_default_backend",
    "get_backend",
]
