"""Mock printer backend for testing."""

from pathlib import Path

from pdfmill.printing.base import PrinterBackend


class MockBackend(PrinterBackend):
    """Mock printer backend for testing.

    Records all print calls for verification in tests.
    Always returns success unless configured otherwise.

    Example:
        backend = MockBackend()
        backend.print_pdf(path, "Test Printer")
        assert len(backend.print_calls) == 1
    """

    name = "mock"

    def __init__(self, printers: list[str] | None = None, fail_on_print: bool = False):
        """Initialize mock backend.

        Args:
            printers: List of printer names to return from list_printers()
            fail_on_print: If True, print_pdf() returns False
        """
        self.printers = printers or ["Mock Printer 1", "Mock Printer 2"]
        self.fail_on_print = fail_on_print
        self.print_calls: list[dict] = []

    @classmethod
    def is_available(cls) -> bool:
        """Mock backend is always available."""
        return True

    def list_printers(self) -> list[str]:
        """Return configured list of mock printers."""
        return self.printers

    def print_pdf(
        self,
        pdf_path: Path,
        printer: str,
        copies: int = 1,
        extra_args: list[str] | None = None,
        dry_run: bool = False,
    ) -> bool:
        """Record print call and return configured result.

        Args:
            pdf_path: Path to the PDF file
            printer: Name of the printer to use
            copies: Number of copies to print
            extra_args: Additional arguments (recorded)
            dry_run: If True, only records the call

        Returns:
            False if fail_on_print is True, otherwise True
        """
        self.print_calls.append({
            "pdf_path": pdf_path,
            "printer": printer,
            "copies": copies,
            "extra_args": extra_args or [],
            "dry_run": dry_run,
        })

        if dry_run:
            print(f"[dry-run] Would print {pdf_path} to {printer} (copies={copies})")
            return True

        return not self.fail_on_print

    def reset(self) -> None:
        """Clear recorded print calls."""
        self.print_calls.clear()
