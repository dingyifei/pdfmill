"""PDF transformation operations for pdfmill."""

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

    This performs a "real" rotation using coordinate transformations,
    not just the /Rotate flag. This ensures subsequent transforms
    (crop, resize) work in the rotated coordinate space.

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
    # Determine the actual rotation angle
    actual_angle = 0

    if isinstance(angle, str):
        angle_lower = angle.lower()
        if angle_lower == "landscape":
            if not is_landscape(page):
                actual_angle = 90
        elif angle_lower == "portrait":
            if is_landscape(page):
                actual_angle = 90
        elif angle_lower == "auto":
            if pdf_path is None or page_num is None:
                raise TransformError(
                    "pdf_path and page_num are required for auto rotation"
                )
            actual_angle = detect_page_orientation(pdf_path, page_num)
        else:
            raise TransformError(f"Unknown rotation orientation: {angle}")
    else:
        if angle not in (0, 90, 180, 270):
            raise TransformError(f"Rotation angle must be 0, 90, 180, or 270, got {angle}")
        actual_angle = angle

    if actual_angle == 0:
        return page

    # Get current dimensions
    width, height = get_page_dimensions(page)

    # Clear any existing rotation flag since we're doing a real rotation
    if "/Rotate" in page:
        del page["/Rotate"]

    # Calculate translation needed to keep content in positive quadrant
    # after rotation (rotation is counter-clockwise around origin)
    if actual_angle == 90:
        # 90° CCW: (x,y) -> (-y, x), need to translate by (height, 0)
        tx, ty = height, 0
        new_width, new_height = height, width
    elif actual_angle == 180:
        # 180°: (x,y) -> (-x, -y), need to translate by (width, height)
        tx, ty = width, height
        new_width, new_height = width, height
    elif actual_angle == 270:
        # 270° CCW: (x,y) -> (y, -x), need to translate by (0, width)
        tx, ty = 0, width
        new_width, new_height = height, width

    # Apply rotation then translation to keep content visible
    transform = Transformation().rotate(actual_angle).translate(tx=tx, ty=ty)
    page.add_transformation(transform)

    # Update mediabox to reflect new dimensions
    page.mediabox.lower_left = (0, 0)
    page.mediabox.upper_right = (new_width, new_height)

    return page


def _parse_coordinate(value: float | str) -> float:
    """Parse a coordinate value to points.

    Args:
        value: Either a float (already in points) or a string with unit (e.g., "100mm")

    Returns:
        Value in points
    """
    if isinstance(value, str):
        return parse_dimension(value)
    return float(value)


def crop_page(
    page: PageObject,
    lower_left: tuple[float | str, float | str],
    upper_right: tuple[float | str, float | str],
) -> PageObject:
    """
    Crop a page to the specified coordinates.

    Translates the content so the cropped region starts at origin (0, 0).
    This ensures subsequent transforms (resize, etc.) work correctly.

    Args:
        page: The page to crop
        lower_left: (x, y) coordinates of lower-left corner (points or strings like "100mm")
        upper_right: (x, y) coordinates of upper-right corner (points or strings like "100mm")

    Returns:
        The cropped page (mutates in place and returns)

    Raises:
        TransformError: If coordinates are invalid
    """
    # Parse coordinates to points
    ll_x = _parse_coordinate(lower_left[0])
    ll_y = _parse_coordinate(lower_left[1])
    ur_x = _parse_coordinate(upper_right[0])
    ur_y = _parse_coordinate(upper_right[1])

    if ll_x >= ur_x:
        raise TransformError(
            f"Invalid crop: left ({ll_x}) must be less than right ({ur_x})"
        )
    if ll_y >= ur_y:
        raise TransformError(
            f"Invalid crop: bottom ({ll_y}) must be less than top ({ur_y})"
        )

    # Calculate cropped dimensions
    crop_width = ur_x - ll_x
    crop_height = ur_y - ll_y

    # Translate content so cropped region moves to origin (0, 0)
    # This ensures subsequent transforms work correctly
    transform = Transformation().translate(tx=-ll_x, ty=-ll_y)
    page.add_transformation(transform)

    # Set mediabox to cropped size at origin
    page.mediabox.lower_left = (0, 0)
    page.mediabox.upper_right = (crop_width, crop_height)
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
