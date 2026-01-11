"""Unified exception hierarchy for pdfmill.

All pdfmill exceptions inherit from PdfMillError, enabling:
- Catching all pdfmill errors with `except PdfMillError`
- Error context preservation via the `context` attribute
- Causality chains via `raise ... from e` patterns
"""

from typing import Any


class PdfMillError(Exception):
    """Base exception for all pdfmill errors.

    Args:
        message: Human-readable error description
        context: Optional dict of contextual information (file, step, etc.)
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.context = context or {}

    def __str__(self) -> str:
        base = super().__str__()
        if self.context:
            details = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base} [{details}]"
        return base


class ConfigError(PdfMillError):
    """Raised when configuration is invalid or cannot be loaded."""


class TransformError(PdfMillError):
    """Raised when a page transformation fails."""


class PageSelectionError(PdfMillError):
    """Raised when a page selection specification is invalid."""


class ProcessingError(PdfMillError):
    """Raised when PDF processing fails."""


class PrinterError(PdfMillError):
    """Raised when printing operations fail."""
