"""Page geometry helpers shared by all transforms.

Every transform works in a normalized coordinate space: no ``/Rotate`` flag,
the visible area starts at (0, 0), and MediaBox == CropBox == TrimBox.
Keeping the boxes identical matters when printing through CUPS, which uses
the CropBox to decide what to rasterize.
"""

import io
import logging

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject


class TransformError(Exception):
    """Raised when a transform cannot be applied to a page."""


def normalize(page: PageObject) -> PageObject:
    """Bake ``/Rotate`` into the content and move the visible box to the origin."""
    if page.rotation:
        page.transfer_rotation_to_content()
    box = page.cropbox
    left, bottom = float(box.left), float(box.bottom)
    width, height = float(box.width), float(box.height)
    if left or bottom:
        page.add_transformation(Transformation().translate(tx=-left, ty=-bottom))
    set_box(page, width, height)
    return page


def set_box(page: PageObject, width: float, height: float) -> None:
    """Set every page box to ``[0, 0, width, height]``."""
    if width <= 0 or height <= 0:
        raise TransformError(f"Page size must be positive, got {width:.1f}x{height:.1f} pt")
    rect = RectangleObject([0, 0, width, height])
    page.mediabox = rect
    page.cropbox = rect
    page.trimbox = rect
    page.bleedbox = rect
    page.artbox = rect


def size(page: PageObject) -> tuple[float, float]:
    """Width and height of the (normalized) page in points."""
    return float(page.mediabox.width), float(page.mediabox.height)


def clone(page: PageObject) -> PageObject:
    """Return an independent deep copy of a page.

    pypdf copies can share the same ``/Contents`` stream, so transforming one
    copy would also change the other. A write/read round trip avoids that.
    """
    writer = PdfWriter()
    writer.add_page(page)
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    # Re-reading a single-page PDF can log harmless xref warnings.
    pypdf_logger = logging.getLogger("pypdf")
    level = pypdf_logger.level
    pypdf_logger.setLevel(logging.ERROR)
    try:
        return PdfReader(buffer).pages[0]
    finally:
        pypdf_logger.setLevel(level)
