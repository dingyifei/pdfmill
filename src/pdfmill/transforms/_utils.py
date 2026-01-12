"""Shared utilities for transforms."""

import re

from pypdf import PageObject


class TransformError(Exception):
    """Raised when a transformation fails."""


# Conversion factors to points (72 points per inch)
UNIT_TO_POINTS = {
    "pt": 1.0,
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
}


def parse_dimension(value: str) -> float:
    """
    Parse a dimension string to points.

    Supports: "100mm", "4in", "288pt", "10cm"

    Args:
        value: Dimension string with unit

    Returns:
        Value in points
    """
    if not value:
        raise TransformError("Empty dimension value")

    value = value.strip().lower()
    match = re.match(r"^([\d.]+)\s*(mm|in|pt|cm)$", value)
    if not match:
        raise TransformError(
            f"Invalid dimension format: {value}. Use format like '100mm', '4in', '288pt'"
        )

    number = float(match.group(1))
    unit = match.group(2)
    return number * UNIT_TO_POINTS[unit]


def parse_coordinate(value: float | str) -> float:
    """
    Parse a coordinate value (float or string with units) to points.

    Args:
        value: Coordinate value (float in points, or string with units)

    Returns:
        Value in points
    """
    if isinstance(value, (int, float)):
        return float(value)
    return parse_dimension(value)


def get_page_dimensions(page: PageObject) -> tuple[float, float]:
    """Get page width and height in points."""
    mediabox = page.mediabox
    width = float(mediabox.width)
    height = float(mediabox.height)
    return width, height


def is_landscape(page: PageObject) -> bool:
    """Check if a page is in landscape orientation."""
    width, height = get_page_dimensions(page)
    return width > height


def detect_page_orientation(pdf_path: str, page_num: int = 0) -> int:
    """
    Detect the rotation needed to make text upright using OCR.

    Uses Tesseract's OSD (Orientation Script Detection) to determine
    the rotation angle needed to correct page orientation.

    Args:
        pdf_path: Path to the PDF file
        page_num: 0-indexed page number to analyze

    Returns:
        Rotation angle needed (0, 90, 180, or 270)

    Raises:
        TransformError: If OCR dependencies are not installed or detection fails
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise TransformError(
            "pdf2image is required for auto rotation. Install with: pip install pdf2image"
        )

    try:
        import pytesseract
    except ImportError:
        raise TransformError(
            "pytesseract is required for auto rotation. "
            "Install with: pip install pytesseract"
        )

    try:
        # Render PDF page to image at 150 DPI for good OCR accuracy
        images = convert_from_path(
            pdf_path,
            first_page=page_num + 1,  # pdf2image uses 1-indexed pages
            last_page=page_num + 1,
            dpi=150,
        )

        if not images:
            raise TransformError(f"Failed to render page {page_num} from {pdf_path}")

        image = images[0]

        # Use Tesseract OSD to detect orientation
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
        detected_rotation = osd.get("rotate", 0)

        # Return the rotation needed to correct (Tesseract tells us current rotation)
        return detected_rotation

    except pytesseract.TesseractNotFoundError:
        raise TransformError(
            "Tesseract OCR is not installed. Install from: "
            "https://github.com/tesseract-ocr/tesseract"
        )
    except Exception as e:
        raise TransformError(f"OCR orientation detection failed: {e}")
