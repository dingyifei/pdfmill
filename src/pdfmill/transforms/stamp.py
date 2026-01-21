"""Stamp transform for pdfmill."""

import io
from datetime import datetime

from pypdf import PageObject, PdfReader

from pdfmill.config import StampPosition, Transform
from pdfmill.config import StampTransform as StampConfig
from pdfmill.transforms._utils import (
    TransformError,
    get_page_dimensions,
    parse_coordinate,
)
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.registry import register_transform


def _parse_color(color_str: str):
    """Parse a color string into a reportlab color object.

    Supports color names (e.g., "black", "red") and hex codes (e.g., "#FF0000").
    """
    try:
        from reportlab.lib import colors
    except ImportError:
        raise TransformError("reportlab is required for stamp transform. Install with: pip install reportlab")

    # Try hex color
    if color_str.startswith("#"):
        hex_str = color_str[1:]
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16) / 255
            g = int(hex_str[2:4], 16) / 255
            b = int(hex_str[4:6], 16) / 255
            return colors.Color(r, g, b)
        raise TransformError(f"Invalid hex color: {color_str}")

    # Try named color
    color = getattr(colors, color_str, None)
    if color is not None:
        return color

    raise TransformError(
        f"Unknown color: {color_str}. Use a color name (e.g., 'black', 'red') or hex code (e.g., '#FF0000')"
    )


def _create_text_overlay(
    text: str,
    width: float,
    height: float,
    x: float,
    y: float,
    font_name: str,
    font_size: int,
    font_color: str = "black",
    opacity: float = 1.0,
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
        font_color: Font color (name or hex code)
        opacity: Opacity 0.0-1.0

    Returns:
        PDF bytes containing the text overlay
    """
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        raise TransformError("reportlab is required for stamp transform. Install with: pip install reportlab")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont(font_name, font_size)

    # Set color
    color = _parse_color(font_color)
    c.setFillColor(color)

    # Set opacity
    if opacity < 1.0:
        c.setFillAlpha(opacity)

    c.drawString(x, y, text)
    c.save()
    buffer.seek(0)
    return buffer.read()


def _calculate_stamp_position(
    position: StampPosition,
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
        position: StampPosition enum value
        page_width: Page width in points
        page_height: Page height in points
        text: Text to stamp (for width estimation)
        font_size: Font size in points
        margin: Margin from edge in points
        custom_x: Custom X coordinate (used when position=CUSTOM)
        custom_y: Custom Y coordinate (used when position=CUSTOM)

    Returns:
        (x, y) coordinates in points
    """
    # Estimate text width (approximately 0.5 * font_size per character for Helvetica)
    text_width = len(text) * font_size * 0.5
    text_height = font_size

    if position == StampPosition.CUSTOM:
        return custom_x, custom_y
    elif position == StampPosition.TOP_LEFT:
        return margin, page_height - margin - text_height
    elif position == StampPosition.TOP_RIGHT:
        return page_width - margin - text_width, page_height - margin - text_height
    elif position == StampPosition.BOTTOM_LEFT:
        return margin, margin
    elif position == StampPosition.BOTTOM_RIGHT:
        return page_width - margin - text_width, margin
    elif position == StampPosition.CENTER:
        return (page_width - text_width) / 2, (page_height - text_height) / 2
    else:
        # This should never happen with proper enum usage
        valid = ", ".join(p.value for p in StampPosition)
        raise TransformError(f"Unknown stamp position: {position}. Valid options: {valid}")


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
    position: StampPosition = StampPosition.BOTTOM_RIGHT,
    x: float | str = 0,
    y: float | str = 0,
    font_size: int = 10,
    font_name: str = "Helvetica",
    font_color: str = "black",
    opacity: float = 1.0,
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
        position: StampPosition enum value
        x: X coordinate (used when position=CUSTOM)
        y: Y coordinate (used when position=CUSTOM)
        font_size: Font size in points
        font_name: Font name (PDF standard font)
        font_color: Font color (name or hex code)
        opacity: Opacity 0.0-1.0 (1.0 = fully opaque)
        margin: Margin from edge for preset positions
        page_num: Current page number (1-indexed)
        total_pages: Total number of pages
        datetime_format: strftime format for {datetime} placeholder

    Returns:
        The stamped page (mutates in place and returns)
    """
    # Parse coordinates and margin
    margin_pts = parse_coordinate(margin)
    x_pts = parse_coordinate(x) if position == StampPosition.CUSTOM else 0
    y_pts = parse_coordinate(y) if position == StampPosition.CUSTOM else 0

    # Get page dimensions
    page_width, page_height = get_page_dimensions(page)

    # Format text with placeholders
    formatted_text = _format_stamp_text(text, page_num, total_pages, datetime_format)

    # Calculate position
    stamp_x, stamp_y = _calculate_stamp_position(
        position,
        page_width,
        page_height,
        formatted_text,
        font_size,
        margin_pts,
        x_pts,
        y_pts,
    )

    # Create overlay PDF
    overlay_bytes = _create_text_overlay(
        formatted_text, page_width, page_height, stamp_x, stamp_y, font_name, font_size, font_color, opacity
    )

    # Merge overlay onto page
    overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]
    page.merge_page(overlay_page)

    return page


@register_transform("stamp")
class StampTransformHandler(BaseTransform):
    """Handler for stamp transforms."""

    def __init__(self, config: StampConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "StampTransformHandler":
        if not transform.stamp:
            raise ValueError("Stamp transform missing stamp config")
        return cls(transform.stamp)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        total_pages = len(pages)
        for i, page in enumerate(pages):
            stamp_page(
                page,
                self.config.text,
                position=self.config.position,
                x=self.config.x,
                y=self.config.y,
                font_size=self.config.font_size,
                font_name=self.config.font_name,
                font_color=self.config.font_color,
                opacity=self.config.opacity,
                margin=self.config.margin,
                page_num=i + 1,  # 1-indexed
                total_pages=total_pages,
                datetime_format=self.config.datetime_format,
            )
        return TransformResult(pages=pages, mode="replace")

    def describe(self) -> str:
        return "stamp"
