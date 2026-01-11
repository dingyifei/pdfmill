"""Transform package with registry pattern for extensible PDF transformations."""

from pdfmill.transforms.base import TransformHandler, TransformContext
from pdfmill.transforms.registry import TransformRegistry
from pdfmill.transforms.handlers import RotateHandler, CropHandler, SizeHandler

# Re-export legacy functions for backward compatibility
from pdfmill.transforms.core import (
    rotate_page,
    crop_page,
    resize_page,
    parse_dimension,
    get_page_dimensions,
    is_landscape,
    detect_page_orientation,
)

# Re-export exception and constants for backward compatibility
from pdfmill.exceptions import TransformError
from pdfmill.constants import UNIT_TO_POINTS

__all__ = [
    # Registry pattern
    "TransformHandler",
    "TransformContext",
    "TransformRegistry",
    "RotateHandler",
    "CropHandler",
    "SizeHandler",
    # Legacy functions
    "rotate_page",
    "crop_page",
    "resize_page",
    "parse_dimension",
    "get_page_dimensions",
    "is_landscape",
    "detect_page_orientation",
    # Exception and constants
    "TransformError",
    "UNIT_TO_POINTS",
]
