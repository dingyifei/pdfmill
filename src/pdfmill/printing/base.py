"""Abstract base class for printer backends."""

from abc import ABC, abstractmethod
from pathlib import Path


class PrinterBackend(ABC):
    """Abstract base class for printer backends.

    Each printer backend (SumatraPDF, CUPS, lpr) implements this interface.
    This enables cross-platform printing and easier testing via MockBackend.

    Example:
        backend = get_default_backend()
        printers = backend.list_printers()
        backend.print_pdf(path, printers[0])
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier (e.g., 'sumatra', 'cups', 'mock')."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this backend is available on the current platform.

        Returns:
            True if the backend can be used
        """

    @abstractmethod
    def list_printers(self) -> list[str]:
        """List available printers.

        Returns:
            List of printer names

        Raises:
            PrinterError: If printer enumeration fails
        """

    @abstractmethod
    def print_pdf(
        self,
        pdf_path: Path,
        printer: str,
        copies: int = 1,
        extra_args: list[str] | None = None,
        dry_run: bool = False,
    ) -> bool:
        """Print a PDF file.

        Args:
            pdf_path: Path to the PDF file
            printer: Name of the printer to use
            copies: Number of copies to print
            extra_args: Additional backend-specific arguments
            dry_run: If True, only show what would be done

        Returns:
            True if printing succeeded, False otherwise

        Raises:
            PrinterError: If the PDF file is not found or printing fails
        """
