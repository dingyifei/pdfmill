"""Shared fixtures for pdfmill tests."""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# === Path/Directory Fixtures ===

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# === PDF Fixtures ===

@pytest.fixture
def temp_pdf(temp_dir):
    """Create a temporary single-page PDF for testing."""
    from pypdf import PdfWriter

    pdf_path = temp_dir / "test.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # Letter size
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def temp_multi_page_pdf(temp_dir):
    """Create a temporary 6-page PDF for testing."""
    from pypdf import PdfWriter

    pdf_path = temp_dir / "multi_page.pdf"
    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def temp_landscape_pdf(temp_dir):
    """Create a temporary landscape PDF for testing."""
    from pypdf import PdfWriter

    pdf_path = temp_dir / "landscape.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=792, height=612)  # Swapped dimensions
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


# === Mock pypdf PageObject Fixtures ===

@pytest.fixture
def mock_page():
    """Create a mock pypdf PageObject (portrait letter size)."""
    page = MagicMock()
    mediabox = MagicMock()
    mediabox.width = 612.0
    mediabox.height = 792.0
    mediabox.lower_left = (0, 0)
    mediabox.upper_right = (612, 792)
    page.mediabox = mediabox
    return page


@pytest.fixture
def mock_landscape_page():
    """Create a mock landscape PageObject."""
    page = MagicMock()
    mediabox = MagicMock()
    mediabox.width = 792.0
    mediabox.height = 612.0
    mediabox.lower_left = (0, 0)
    mediabox.upper_right = (792, 612)
    page.mediabox = mediabox
    return page


# === Config Fixtures ===

@pytest.fixture
def minimal_config_dict():
    """Minimal valid configuration dictionary."""
    return {
        "version": 1,
        "outputs": {
            "default": {
                "pages": "all",
            }
        }
    }


@pytest.fixture
def full_config_dict():
    """Full configuration dictionary with all options."""
    return {
        "version": 1,
        "settings": {
            "on_error": "continue",
            "cleanup_source": False,
            "cleanup_output_after_print": False,
        },
        "input": {
            "path": "./input",
            "pattern": "*.pdf",
        },
        "outputs": {
            "profile1": {
                "pages": "last",
                "output_dir": "./output",
                "filename_prefix": "pre_",
                "filename_suffix": "_suf",
                "transforms": [
                    {"rotate": 90},
                    {"crop": {"lower_left": [0, 0], "upper_right": [400, 400]}},
                ],
                "print": {
                    "enabled": True,
                    "printer": "Test Printer",
                    "copies": 2,
                    "args": ["-silent"],
                },
            }
        }
    }


@pytest.fixture
def temp_config_file(temp_dir, minimal_config_dict):
    """Create a temporary config file."""
    config_path = temp_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(minimal_config_dict, f)
    return config_path


@pytest.fixture
def full_config_file(temp_dir, full_config_dict):
    """Create a temporary full config file."""
    config_path = temp_dir / "full_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(full_config_dict, f)
    return config_path


# === Mock win32print ===

@pytest.fixture
def mock_win32print():
    """Mock win32print module for printer tests."""
    mock = MagicMock()
    mock.PRINTER_ENUM_LOCAL = 2
    mock.PRINTER_ENUM_CONNECTIONS = 4
    mock.EnumPrinters.return_value = [
        (0, "", "Printer 1", ""),
        (0, "", "Printer 2", ""),
        (0, "", "Label Printer", ""),
    ]
    with patch.dict("sys.modules", {"win32print": mock}):
        yield mock


# === Mock subprocess ===

@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for SumatraPDF calls."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


# === Session-scoped PDF fixtures for integration tests ===

@pytest.fixture(scope="session")
def session_fixtures_dir(tmp_path_factory):
    """Create fixture PDFs for the entire test session."""
    from pypdf import PdfWriter

    fixtures = tmp_path_factory.mktemp("fixtures")

    # Single page
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    sample = fixtures / "sample.pdf"
    with open(sample, "wb") as f:
        writer.write(f)

    # Multi-page (6 pages)
    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(612, 792)
    multi = fixtures / "multi_page.pdf"
    with open(multi, "wb") as f:
        writer.write(f)

    # Landscape
    writer = PdfWriter()
    writer.add_blank_page(792, 612)
    landscape = fixtures / "landscape.pdf"
    with open(landscape, "wb") as f:
        writer.write(f)

    return {
        "sample": sample,
        "multi_page": multi,
        "landscape": landscape,
        "dir": fixtures,
    }
