"""PDF transformation operations for pdfpipe."""

import io
import re
from typing import Literal

from pypdf import PageObject, Transformation


class TransformError(Exception):
    """Raised when a transformation fails."""


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
        import fitz  # pymupdf
    except ImportError:
        raise TransformError(
            "pymupdf is required for auto rotation. Install with: pip install pymupdf"
        )

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise TransformError(
            "pytesseract and Pillow are required for auto rotation. "
            "Install with: pip install pytesseract Pillow"
        )

    try:
        # Render PDF page to image
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        # Render at 150 DPI for good OCR accuracy without being too slow
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        doc.close()

        # Convert to PIL Image
        image = Image.open(io.BytesIO(img_data))

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
        raise TransformError(f"Invalid dimension format: {value}. Use format like '100mm', '4in', '288pt'")

    number = float(match.group(1))
    unit = match.group(2)
    return number * UNIT_TO_POINTS[unit]


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


def rotate_page(
    page: PageObject,
    angle: int | str,
    pdf_path: str | None = None,
    page_num: int | None = None,
) -> PageObject:
    """
    Rotate a page by the specified angle or to a target orientation.

    Args:
        page: The page to rotate
        angle: Rotation angle (0, 90, 180, 270) or orientation
               ("landscape", "portrait", "auto")
        pdf_path: Path to source PDF (required for "auto" mode)
        page_num: 0-indexed page number (required for "auto" mode)

    Returns:
        The rotated page (mutates in place and returns)

    Raises:
        TransformError: If angle is invalid or auto mode requirements not met
    """
    if isinstance(angle, str):
        angle_lower = angle.lower()
        if angle_lower == "landscape":
            if not is_landscape(page):
                page.rotate(90)
        elif angle_lower == "portrait":
            if is_landscape(page):
                page.rotate(90)
        elif angle_lower == "auto":
            if pdf_path is None or page_num is None:
                raise TransformError(
                    "pdf_path and page_num are required for auto rotation"
                )
            detected_angle = detect_page_orientation(pdf_path, page_num)
            if detected_angle != 0:
                page.rotate(detected_angle)
        else:
            raise TransformError(f"Unknown rotation orientation: {angle}")
    else:
        if angle not in (0, 90, 180, 270):
            raise TransformError(f"Rotation angle must be 0, 90, 180, or 270, got {angle}")
        if angle != 0:
            page.rotate(angle)

    return page


def crop_page(
    page: PageObject,
    lower_left: tuple[float, float],
    upper_right: tuple[float, float],
) -> PageObject:
    """
    Crop a page to the specified coordinates.

    Args:
        page: The page to crop
        lower_left: (x, y) coordinates of lower-left corner in points
        upper_right: (x, y) coordinates of upper-right corner in points

    Returns:
        The cropped page (mutates in place and returns)

    Raises:
        TransformError: If coordinates are invalid
    """
    if lower_left[0] >= upper_right[0]:
        raise TransformError(
            f"Invalid crop: left ({lower_left[0]}) must be less than right ({upper_right[0]})"
        )
    if lower_left[1] >= upper_right[1]:
        raise TransformError(
            f"Invalid crop: bottom ({lower_left[1]}) must be less than top ({upper_right[1]})"
        )

    page.mediabox.lower_left = lower_left
    page.mediabox.upper_right = upper_right
    return page


def resize_page(
    page: PageObject,
    width: str,
    height: str,
    fit: Literal["contain", "cover", "stretch"] = "contain",
) -> PageObject:
    """
    Resize a page to the target dimensions.

    Args:
        page: The page to resize
        width: Target width (e.g., "100mm", "4in")
        height: Target height (e.g., "150mm", "6in")
        fit: How to fit content:
            - "contain": Scale uniformly to fit within target, centered (may have whitespace)
            - "cover": Scale uniformly to fill target, centered (may crop edges)
            - "stretch": Stretch non-uniformly to exactly match target

    Returns:
        The resized page (mutates in place and returns)
    """
    target_width = parse_dimension(width)
    target_height = parse_dimension(height)

    current_width, current_height = get_page_dimensions(page)

    if fit == "stretch":
        # Non-uniform scaling using transformation matrix
        scale_x = target_width / current_width
        scale_y = target_height / current_height

        # Apply non-uniform scale transformation
        transform = Transformation().scale(sx=scale_x, sy=scale_y)
        page.add_transformation(transform)

        # Update mediabox to target dimensions
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (target_width, target_height)
    elif fit in ("contain", "cover"):
        # Uniform scaling
        scale_x = target_width / current_width
        scale_y = target_height / current_height

        if fit == "contain":
            scale = min(scale_x, scale_y)
        else:  # cover
            scale = max(scale_x, scale_y)

        # Calculate scaled dimensions
        scaled_width = current_width * scale
        scaled_height = current_height * scale

        # Calculate centering offsets
        offset_x = (target_width - scaled_width) / 2
        offset_y = (target_height - scaled_height) / 2

        # Apply scale and translation to center the content
        transform = Transformation().scale(sx=scale, sy=scale).translate(tx=offset_x, ty=offset_y)
        page.add_transformation(transform)

        # Set final mediabox to target size
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (target_width, target_height)
    else:
        raise TransformError(f"Unknown fit mode: {fit}")

    return page
