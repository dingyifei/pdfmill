"""Tests for pdfmill.pipeline.safety module."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from pdfmill.config import PrintConfig, SafetyAction
from pdfmill.pipeline.safety import (
    PrintSafetyError,
    SafetyCheckResult,
    check_print_safety,
    enforce_print_safety,
)


def create_test_pdf(path: Path, num_pages: int = 1, width: float = 612, height: float = 792) -> Path:
    """Create a test PDF with specified dimensions."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=width, height=height)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        writer.write(f)
    return path


class TestSafetyCheckResult:
    """Test SafetyCheckResult dataclass."""

    def test_empty_result(self):
        result = SafetyCheckResult()
        assert result.passed
        assert len(result.violations) == 0

    def test_add_violation(self):
        result = SafetyCheckResult()
        result.add_violation("Page count exceeded")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0] == "Page count exceeded"

    def test_multiple_violations(self):
        result = SafetyCheckResult()
        result.add_violation("Violation 1")
        result.add_violation("Violation 2")
        assert not result.passed
        assert len(result.violations) == 2


class TestCheckPrintSafetyMaxPages:
    """Test max_pages safety check."""

    def test_no_limits_passes(self, tmp_path):
        """Test that no safety limits configured always passes."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=100)
        config = PrintConfig()  # No limits set

        result = check_print_safety([pdf_path], config, "test")
        assert result.passed

    def test_under_max_pages_passes(self, tmp_path):
        """Test that page count under limit passes."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=5)
        config = PrintConfig(max_pages=10)

        result = check_print_safety([pdf_path], config, "test")
        assert result.passed

    def test_exact_max_pages_passes(self, tmp_path):
        """Test that page count at limit passes."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=10)
        config = PrintConfig(max_pages=10)

        result = check_print_safety([pdf_path], config, "test")
        assert result.passed

    def test_over_max_pages_fails(self, tmp_path):
        """Test that page count over limit fails."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=15)
        config = PrintConfig(max_pages=10)

        result = check_print_safety([pdf_path], config, "test")
        assert not result.passed
        assert len(result.violations) == 1
        assert "15" in result.violations[0]
        assert "10" in result.violations[0]

    def test_multiple_pdfs_total_pages(self, tmp_path):
        """Test that total pages across multiple PDFs is checked."""
        pdf1 = create_test_pdf(tmp_path / "test1.pdf", num_pages=5)
        pdf2 = create_test_pdf(tmp_path / "test2.pdf", num_pages=6)
        config = PrintConfig(max_pages=10)

        result = check_print_safety([pdf1, pdf2], config, "test")
        assert not result.passed
        assert "11" in result.violations[0]


class TestCheckPrintSafetyMaxPageSize:
    """Test max_page_size safety check."""

    def test_page_within_size_passes(self, tmp_path):
        """Test that page within size limit passes."""
        # Letter size: 612x792 points (8.5x11 inches)
        pdf_path = create_test_pdf(tmp_path / "test.pdf", width=612, height=792)
        config = PrintConfig(max_page_size=("8.5in", "11in"))

        result = check_print_safety([pdf_path], config, "test")
        assert result.passed

    def test_page_exceeds_size_fails(self, tmp_path):
        """Test that page exceeding size limit fails."""
        # Create A3 size page (larger than letter)
        pdf_path = create_test_pdf(tmp_path / "test.pdf", width=842, height=1191)
        config = PrintConfig(max_page_size=("8.5in", "11in"))

        result = check_print_safety([pdf_path], config, "test")
        assert not result.passed
        assert len(result.violations) == 1
        assert "exceeds" in result.violations[0]

    def test_rotated_page_fits(self, tmp_path):
        """Test that rotated page is checked in both orientations."""
        # Landscape letter: 792x612 should fit within 8.5x11
        pdf_path = create_test_pdf(tmp_path / "test.pdf", width=792, height=612)
        config = PrintConfig(max_page_size=("8.5in", "11in"))

        result = check_print_safety([pdf_path], config, "test")
        assert result.passed

    def test_size_with_mm_units(self, tmp_path):
        """Test max_page_size with mm units."""
        # 4x6 inches = 101.6x152.4 mm
        pdf_path = create_test_pdf(tmp_path / "test.pdf", width=288, height=432)  # 4x6 inches in points
        config = PrintConfig(max_page_size=("102mm", "153mm"))

        result = check_print_safety([pdf_path], config, "test")
        assert result.passed

    def test_multiple_pages_checked(self, tmp_path):
        """Test that all pages in PDF are checked."""
        writer = PdfWriter()
        # First page fits
        writer.add_blank_page(width=612, height=792)
        # Second page is too large
        writer.add_blank_page(width=1000, height=1000)
        pdf_path = tmp_path / "test.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)

        config = PrintConfig(max_page_size=("8.5in", "11in"))
        result = check_print_safety([pdf_path], config, "test")
        assert not result.passed
        assert "page 2" in result.violations[0]


class TestEnforcePrintSafety:
    """Test enforce_print_safety behavior."""

    def test_no_limits_returns_true(self, tmp_path):
        """Test that no limits configured returns True."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=100)
        config = PrintConfig()

        result = enforce_print_safety([pdf_path], config, "test")
        assert result is True

    def test_block_action_raises(self, tmp_path):
        """Test that block action raises PrintSafetyError."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=100)
        config = PrintConfig(max_pages=10, action=SafetyAction.BLOCK)

        with pytest.raises(PrintSafetyError) as exc_info:
            enforce_print_safety([pdf_path], config, "test")

        assert "test" in str(exc_info.value)
        assert len(exc_info.value.violations) == 1

    def test_warn_action_returns_true(self, tmp_path):
        """Test that warn action logs warning and returns True."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=100)
        config = PrintConfig(max_pages=10, action=SafetyAction.WARN)

        # Should not raise, just warn
        result = enforce_print_safety([pdf_path], config, "test")
        assert result is True

    def test_passes_with_valid_pages(self, tmp_path):
        """Test that valid pages return True with no error."""
        pdf_path = create_test_pdf(tmp_path / "test.pdf", num_pages=5)
        config = PrintConfig(max_pages=10, action=SafetyAction.BLOCK)

        result = enforce_print_safety([pdf_path], config, "test")
        assert result is True


class TestPrintSafetyError:
    """Test PrintSafetyError exception."""

    def test_error_message(self):
        error = PrintSafetyError("Test message", ["violation 1", "violation 2"])
        assert error.message == "Test message"
        assert len(error.violations) == 2
        assert "Test message" in str(error)

    def test_error_with_empty_violations(self):
        error = PrintSafetyError("No violations", [])
        assert len(error.violations) == 0
