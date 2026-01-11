"""Printer interface for pdfmill using SumatraPDF.

This module re-exports from the printing package for backward compatibility.
New code should use pdfmill.printing directly.
"""

# Re-export everything from the printing package for backward compatibility
from pdfmill.printing.sumatra import (
    SUMATRA_VERSION,
    SUMATRA_URLS,
    get_architecture,
    get_cache_dir,
    get_sumatra_cache_path,
    get_sumatra_download_url,
    download_sumatra,
    remove_sumatra,
    get_sumatra_status,
    SumatraBackend,
)

# Re-export PrinterError for backward compatibility
from pdfmill.exceptions import PrinterError

# Re-export backend classes and factory
from pdfmill.printing import (
    PrinterBackend,
    MockBackend,
    get_default_backend,
    get_backend,
)

# Create module-level functions that delegate to SumatraBackend for backward compatibility
_default_backend = None


def _get_backend() -> SumatraBackend:
    """Get or create the default SumatraPDF backend."""
    global _default_backend
    if _default_backend is None:
        _default_backend = SumatraBackend()
    return _default_backend


def list_printers() -> list[str]:
    """List available printers on the system.

    Returns:
        List of printer names

    Raises:
        PrinterError: If printer enumeration fails
    """
    return _get_backend().list_printers()


def find_sumatra_pdf(auto_download: bool = True):
    """Find SumatraPDF executable.

    Search order:
    1. PDFPIPE_SUMATRA_PATH environment variable
    2. Current directory
    3. Cache directory
    4. PATH
    5. Auto-download to cache (if auto_download=True)

    Args:
        auto_download: If True, download SumatraPDF if not found

    Returns:
        Path to SumatraPDF.exe or None if not found
    """
    return _get_backend().find_sumatra_pdf(auto_download=auto_download)


def print_pdf(
    pdf_path,
    printer: str,
    copies: int = 1,
    extra_args: list[str] | None = None,
    sumatra_path=None,
    dry_run: bool = False,
) -> bool:
    """Print a PDF file using SumatraPDF.

    Args:
        pdf_path: Path to the PDF file
        printer: Name of the printer to use
        copies: Number of copies to print
        extra_args: Additional SumatraPDF command-line arguments
        sumatra_path: Path to SumatraPDF.exe (auto-detected if None)
        dry_run: If True, only show what would be done

    Returns:
        True if printing succeeded, False otherwise

    Raises:
        PrinterError: If SumatraPDF is not found or printing fails
    """
    return _get_backend().print_pdf(
        pdf_path=pdf_path,
        printer=printer,
        copies=copies,
        extra_args=extra_args,
        sumatra_path=sumatra_path,
        dry_run=dry_run,
    )


__all__ = [
    # Constants
    "SUMATRA_VERSION",
    "SUMATRA_URLS",
    # Utility functions
    "get_architecture",
    "get_cache_dir",
    "get_sumatra_cache_path",
    "get_sumatra_download_url",
    "download_sumatra",
    "remove_sumatra",
    "get_sumatra_status",
    "find_sumatra_pdf",
    # Main functions
    "list_printers",
    "print_pdf",
    # Exception
    "PrinterError",
    # Backend classes
    "PrinterBackend",
    "SumatraBackend",
    "MockBackend",
    "get_default_backend",
    "get_backend",
]
