"""Shared fixtures for pdfmill tests."""

import logging
from pathlib import Path

import pytest
from pypdf import PdfWriter

from pdfmill.printing import PrinterError


@pytest.fixture(autouse=True)
def reset_logging():
    """Keep handlers from leaking between tests (pytest closes captured streams)."""
    logger = logging.getLogger("pdfmill")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    yield
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())


def write_pdf(path: Path, sizes=((612, 792),), text: list[str] | None = None) -> Path:
    """Write a PDF with one page per (width, height). With ``text``, each page gets that text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is None:
        writer = PdfWriter()
        for w, h in sizes:
            writer.add_blank_page(width=w, height=h)
        with open(path, "wb") as f:
            writer.write(f)
        return path
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    for (w, h), line in zip(sizes, text, strict=True):
        c.setPageSize((w, h))
        c.drawString(72, 72, line)
        c.showPage()
    c.save()
    return path


@pytest.fixture
def make_pdf(tmp_path):
    def factory(name="doc.pdf", sizes=((612, 792),), text=None, directory=None):
        return write_pdf((directory or tmp_path) / name, sizes, text)

    return factory


class FakeBackend:
    """In-memory print backend. ``missing`` printers fail check_printer; ``failing`` fail print_file."""

    name = "fake"

    def __init__(self, printers=("Label", "Laser"), missing=(), failing=()):
        self.printers = list(printers)
        self.missing = set(missing)
        self.failing = set(failing)
        self.jobs: list[tuple[str, Path, int]] = []  # (printer, file name, page count)

    def list_printers(self):
        return self.printers

    def check_printer(self, printer):
        if printer in self.missing or printer not in self.printers:
            raise PrinterError(f"Printer '{printer}' not found")

    def command(self, path, target, title):
        return ["fakeprint", target.printer, str(path)]

    def print_file(self, path, target, title):
        if target.printer in self.failing:
            raise PrinterError(f"{target.printer} rejected the job")
        from pypdf import PdfReader

        self.jobs.append((target.printer, Path(path), len(PdfReader(path).pages)))
        return f"{target.printer}-{len(self.jobs)}"


@pytest.fixture
def backend():
    return FakeBackend()
