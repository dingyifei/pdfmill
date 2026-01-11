"""PDF transformation operations for pdfmill."""

import io
import re
import tempfile
from copy import deepcopy
from datetime import datetime
from typing import Literal

from pypdf import PageObject, PdfReader, PdfWriter, Transformation


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


# Valid position presets for stamp transform
STAMP_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center", "custom"}


def _create_text_overlay(
    text: str,
    width: float,
    height: float,
    x: float,
    y: float,
    font_name: str,
    font_size: int,
) -> bytes:
    """
    Create a PDF page with text overlay using reportlab.

    Args:
        text: Text to render
        width: Page width in points
        height: Page height in points
        x: X position in points
        y: Y position in points
        font_name: Font name (PDF standard fonts)
        font_size: Font size in points

    Returns:
        PDF bytes containing the text overlay
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        raise TransformError(
            "reportlab is required for stamp transform. Install with: pip install reportlab"
        )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont(font_name, font_size)
    c.drawString(x, y, text)
    c.save()
    buffer.seek(0)
    return buffer.read()


def _calculate_stamp_position(
    position: str,
    page_width: float,
    page_height: float,
    text: str,
    font_size: int,
    margin: float,
    custom_x: float = 0,
    custom_y: float = 0,
) -> tuple[float, float]:
    """
    Calculate x, y coordinates for stamp based on position preset.

    Args:
        position: Position preset or "custom"
        page_width: Page width in points
        page_height: Page height in points
        text: Text to stamp (for width estimation)
        font_size: Font size in points
        margin: Margin from edge in points
        custom_x: Custom X coordinate (used when position="custom")
        custom_y: Custom Y coordinate (used when position="custom")

    Returns:
        (x, y) coordinates in points
    """
    # Estimate text width (approximately 0.5 * font_size per character for Helvetica)
    text_width = len(text) * font_size * 0.5
    text_height = font_size

    if position == "custom":
        return custom_x, custom_y
    elif position == "top-left":
        return margin, page_height - margin - text_height
    elif position == "top-right":
        return page_width - margin - text_width, page_height - margin - text_height
    elif position == "bottom-left":
        return margin, margin
    elif position == "bottom-right":
        return page_width - margin - text_width, margin
    elif position == "center":
        return (page_width - text_width) / 2, (page_height - text_height) / 2
    else:
        raise TransformError(f"Unknown stamp position: {position}. Valid options: {STAMP_POSITIONS}")


def _format_stamp_text(
    text: str,
    page_num: int,
    total_pages: int,
    datetime_format: str,
) -> str:
    """
    Replace placeholders in stamp text.

    Args:
        text: Text with placeholders
        page_num: Current page number (1-indexed)
        total_pages: Total number of pages
        datetime_format: strftime format for datetime

    Returns:
        Formatted text with placeholders replaced
    """
    now = datetime.now()

    result = text
    result = result.replace("{page}", str(page_num))
    result = result.replace("{total}", str(total_pages))
    result = result.replace("{datetime}", now.strftime(datetime_format))
    result = result.replace("{date}", now.strftime("%Y-%m-%d"))
    result = result.replace("{time}", now.strftime("%H:%M:%S"))

    return result


def stamp_page(
    page: PageObject,
    text: str,
    position: str = "bottom-right",
    x: float | str = 0,
    y: float | str = 0,
    font_size: int = 10,
    font_name: str = "Helvetica",
    margin: float | str = 10,
    page_num: int = 1,
    total_pages: int = 1,
    datetime_format: str = "%Y-%m-%d %H:%M:%S",
) -> PageObject:
    """
    Add a text stamp/overlay to a page.

    Supports placeholders:
      - {page}: Current page number (1-indexed)
      - {total}: Total page count
      - {datetime}: Current datetime
      - {date}: Current date
      - {time}: Current time

    Args:
        page: The page to stamp
        text: Text to stamp (with placeholder support)
        position: Position preset or "custom"
        x: X coordinate (used when position="custom")
        y: Y coordinate (used when position="custom")
        font_size: Font size in points
        font_name: Font name (PDF standard font)
        margin: Margin from edge for preset positions
        page_num: Current page number (1-indexed)
        total_pages: Total number of pages
        datetime_format: strftime format for {datetime} placeholder

    Returns:
        The stamped page (mutates in place and returns)
    """
    if position not in STAMP_POSITIONS:
        raise TransformError(f"Unknown stamp position: {position}. Valid options: {STAMP_POSITIONS}")

    # Parse coordinates and margin
    margin_pts = _parse_coordinate(margin)
    x_pts = _parse_coordinate(x) if position == "custom" else 0
    y_pts = _parse_coordinate(y) if position == "custom" else 0

    # Get page dimensions
    page_width, page_height = get_page_dimensions(page)

    # Format text with placeholders
    formatted_text = _format_stamp_text(text, page_num, total_pages, datetime_format)

    # Calculate position
    stamp_x, stamp_y = _calculate_stamp_position(
        position, page_width, page_height,
        formatted_text, font_size, margin_pts,
        x_pts, y_pts
    )

    # Create overlay PDF
    overlay_bytes = _create_text_overlay(
        formatted_text, page_width, page_height,
        stamp_x, stamp_y, font_name, font_size
    )

    # Merge overlay onto page
    overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]
    page.merge_page(overlay_page)

    return page


def split_page(
    page: PageObject,
    regions: list[tuple[tuple[float | str, float | str], tuple[float | str, float | str]]],
) -> list[PageObject]:
    """
    Split a single page into multiple pages by extracting different regions.

    Each region becomes a new page. This is useful for extracting multiple
    labels or sections from a single source page.

    Args:
        page: The source page to split
        regions: List of (lower_left, upper_right) coordinate tuples.
                 Each tuple defines a crop region.

    Returns:
        List of new pages, one for each region

    Example:
        # Split a page with two labels side by side
        regions = [
            ((0, 0), ("4in", "6in")),      # Left label
            (("4in", 0), ("8in", "6in")),  # Right label
        ]
        pages = split_page(source_page, regions)
    """
    result_pages = []

    for lower_left, upper_right in regions:
        # Create a deep copy of the page for each region
        page_copy = deepcopy(page)
        # Apply crop to extract the region
        crop_page(page_copy, lower_left, upper_right)
        result_pages.append(page_copy)

    return result_pages


def combine_pages(
    pages: list[PageObject],
    page_size: tuple[str, str],
    layout: list[dict],
) -> PageObject:
    """
    Combine multiple pages onto a single output page.

    Places input pages at specified positions on a new canvas.
    Useful for creating n-up layouts, booklets, or combining labels.

    Args:
        pages: List of source pages to combine
        page_size: (width, height) of the output page, with units (e.g., "8.5in", "11in")
        layout: List of placement specs, each with:
            - page: 0-indexed input page number
            - position: (x, y) lower-left corner position with units
            - scale: Optional scale factor (default 1.0)

    Returns:
        A new page with all input pages placed according to layout

    Example:
        # Create 2-up layout (two pages side by side)
        layout = [
            {"page": 0, "position": ("0in", "0in"), "scale": 0.5},
            {"page": 1, "position": ("4.25in", "0in"), "scale": 0.5},
        ]
        combined = combine_pages(pages, ("8.5in", "11in"), layout)
    """
    # Parse output page dimensions
    width = parse_dimension(page_size[0])
    height = parse_dimension(page_size[1])

    # Create a blank output page
    output_page = PageObject.create_blank_page(width=width, height=height)

    for item in layout:
        page_idx = item.get("page", 0)
        if page_idx >= len(pages):
            continue  # Skip if page doesn't exist

        source_page = pages[page_idx]
        position = item.get("position", (0, 0))
        scale = item.get("scale", 1.0)

        # Parse position coordinates
        x = _parse_coordinate(position[0])
        y = _parse_coordinate(position[1])

        # Build transformation: scale then translate
        # Note: transformations are applied in reverse order in the matrix
        transform = Transformation().scale(sx=scale, sy=scale).translate(tx=x, ty=y)

        # Merge the source page onto the output with the transformation
        output_page.merge_transformed_page(source_page, transform)

    return output_page


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
        raise TransformError(
            "pdf2image is required for render transform. "
            "Install with: pip install pdf2image"
        )

    try:
        from PIL import Image
    except ImportError:
        raise TransformError(
            "Pillow is required for render transform. "
            "Install with: pip install Pillow"
        )

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
