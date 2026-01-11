"""PDF transformation operations for pdfmill.

This module re-exports from the transforms package for backward compatibility.
New code should import from pdfmill.transforms directly.
"""

# Re-export everything from the transforms package
from pdfmill.transforms import (
    # Registry pattern
    TransformHandler,
    TransformContext,
    TransformRegistry,
    RotateHandler,
    CropHandler,
    SizeHandler,
    # Core functions
    rotate_page,
    crop_page,
    resize_page,
    parse_dimension,
    get_page_dimensions,
    is_landscape,
    detect_page_orientation,
)

# Also re-export TransformError for backward compatibility
from pdfmill.exceptions import TransformError

__all__ = [
    # Registry pattern
    "TransformHandler",
    "TransformContext",
    "TransformRegistry",
    "RotateHandler",
    "CropHandler",
    "SizeHandler",
    # Core functions
    "rotate_page",
    "crop_page",
    "resize_page",
    "parse_dimension",
    "get_page_dimensions",
    "is_landscape",
    "detect_page_orientation",
    # Exception
    "TransformError",
]
