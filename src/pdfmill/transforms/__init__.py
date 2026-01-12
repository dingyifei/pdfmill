"""Transform package for pdfmill.

This package provides a registry-based transform system with decorator registration.

Usage:
    from pdfmill.transforms import get_transform
    from pdfmill.config import Transform

    transform_config = Transform(rotate=RotateTransform(angle=90))
    handler = get_transform(transform_config)
    result = handler.apply(pages, context)

Backwards-compatible function exports are available:
    from pdfmill.transforms import rotate_page, crop_page, resize_page
"""

# Import all transform modules to trigger registration
from pdfmill.transforms import (
    combine,
    crop,
    render,
    resize,
    rotate,
    split,
    stamp,
)

# Core exports
from pdfmill.transforms.base import (
    BaseTransform,
    TransformContext,
    TransformResult,
)
from pdfmill.transforms.registry import (
    get_transform,
    list_transforms,
    register_transform,
)

# Backwards-compatible function exports
from pdfmill.transforms.combine import combine_pages
from pdfmill.transforms.crop import crop_page
from pdfmill.transforms.render import render_page
from pdfmill.transforms.resize import resize_page
from pdfmill.transforms.rotate import rotate_page
from pdfmill.transforms.split import split_page
from pdfmill.transforms.stamp import stamp_page

# Utility exports (for external use)
from pdfmill.transforms._utils import (
    UNIT_TO_POINTS,
    TransformError,
    detect_page_orientation,
    get_page_dimensions,
    is_landscape,
    parse_coordinate,
    parse_dimension,
)

# Internal functions exported for tests
from pdfmill.transforms.stamp import (
    _calculate_stamp_position,
    _format_stamp_text,
)

__all__ = [
    # Core classes
    "BaseTransform",
    "TransformContext",
    "TransformResult",
    # Registry functions
    "register_transform",
    "get_transform",
    "list_transforms",
    # Transform functions (backwards compat)
    "rotate_page",
    "crop_page",
    "resize_page",
    "stamp_page",
    "render_page",
    "split_page",
    "combine_pages",
    # Utilities
    "TransformError",
    "UNIT_TO_POINTS",
    "parse_dimension",
    "parse_coordinate",
    "get_page_dimensions",
    "is_landscape",
    "detect_page_orientation",
    # Internal (for tests)
    "_format_stamp_text",
    "_calculate_stamp_position",
]
