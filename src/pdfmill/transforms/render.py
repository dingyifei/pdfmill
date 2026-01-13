"""Render transform for pdfmill."""

import io

from pypdf import PageObject, PdfReader, PdfWriter

from pdfmill.config import RenderTransform as RenderConfig
from pdfmill.config import Transform
from pdfmill.transforms._utils import TransformError
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.registry import register_transform


def render_page(page: PageObject, dpi: int = 150) -> PageObject:
    """
    Rasterize a page to an image and re-embed it as a new PDF page.

    This permanently removes any content outside the visible area (mediabox)
    and flattens all layers, annotations, and transparency. The result is
    a single image embedded in a PDF page.

    Args:
        page: The page to render
        dpi: Resolution for rasterization (default 150)

    Returns:
        A new PageObject containing the rasterized image

    Raises:
        TransformError: If pdf2image or Pillow are not installed
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        raise TransformError("pdf2image is required for render transform. Install with: pip install pdf2image")

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        raise TransformError("Pillow is required for render transform. Install with: pip install Pillow")

    # Write the single page to a temporary PDF in memory
    writer = PdfWriter()
    writer.add_page(page)

    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    # Render to image using pdf2image
    images = convert_from_bytes(pdf_bytes.read(), dpi=dpi)

    if not images:
        raise TransformError("Failed to render page to image")

    image = images[0]

    # Save the image as a PDF in memory
    img_pdf_bytes = io.BytesIO()
    image.save(img_pdf_bytes, format="PDF", resolution=dpi)
    img_pdf_bytes.seek(0)

    # Read the image PDF and return the page
    reader = PdfReader(img_pdf_bytes)
    return reader.pages[0]


@register_transform("render")
class RenderTransformHandler(BaseTransform):
    """Handler for render transforms."""

    def __init__(self, config: RenderConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "RenderTransformHandler":
        if not transform.render:
            raise ValueError("Render transform missing render config")
        return cls(transform.render)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        new_pages = []
        for page in pages:
            rendered = render_page(page, dpi=self.config.dpi)
            new_pages.append(rendered)
        return TransformResult(pages=new_pages, mode="replace")

    def describe(self) -> str:
        return f"render_{self.config.dpi}dpi"
