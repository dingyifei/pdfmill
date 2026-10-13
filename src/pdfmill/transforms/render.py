"""Rasterize pages and re-embed them as images (flattens everything, drops hidden content).

    - render: 300          # DPI
    - render: {dpi: 200}
    - render: true         # 150 DPI

Needs poppler (macOS: brew install poppler) and the OCR extra (pdf2image, Pillow).
"""

import io
from dataclasses import dataclass

from pypdf import PageObject, PdfReader, PdfWriter

from pdfmill.schema import ConfigError, check_keys, typed
from pdfmill.transforms._page import TransformError, set_box, size

NAME = "render"


@dataclass
class Options:
    dpi: int = 150


def parse(value, where: str) -> Options:
    if value is True or value is None:
        return Options()
    if isinstance(value, dict):
        check_keys(value, ("dpi",), where)
        value = value.get("dpi", 150)
    dpi = typed(value, int, where)
    if not 36 <= dpi <= 1200:
        raise ConfigError(f"{where}: dpi must be between 36 and 1200, got {dpi}")
    return Options(dpi=dpi)


def describe(opts: Options) -> str:
    return f"render_{opts.dpi}dpi"


def apply(pages: list[PageObject], opts: Options, fields: dict[str, str]) -> list[PageObject]:
    return [render_page(page, opts.dpi) for page in pages]


def rasterize(page: PageObject, dpi: int):
    """Render one page to a PIL image."""
    try:
        from pdf2image import convert_from_bytes
        from pdf2image.exceptions import PDFInfoNotInstalledError
    except ImportError:
        raise TransformError("Rendering needs the OCR extra: pip install 'pdfmill[ocr]'")
    writer = PdfWriter()
    writer.add_page(page)
    buffer = io.BytesIO()
    writer.write(buffer)
    try:
        images = convert_from_bytes(buffer.getvalue(), dpi=dpi)
    except PDFInfoNotInstalledError:
        raise TransformError("poppler is not installed (macOS: brew install poppler)")
    if not images:
        raise TransformError("Failed to render page to an image")
    return images[0]


def render_page(page: PageObject, dpi: int = 150) -> PageObject:
    """Return a new page containing ``page`` rasterized at ``dpi``, at the same size."""
    width, height = size(page)
    image = rasterize(page, dpi)
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=dpi)
    buffer.seek(0)
    rendered = PdfReader(buffer).pages[0]
    set_box(rendered, width, height)
    return rendered
