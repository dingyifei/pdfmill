"""Resize transform for pdfmill."""

from pypdf import PageObject, Transformation

from pdfmill.config import FitMode, SizeTransform as SizeConfig, Transform
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.registry import register_transform
from pdfmill.transforms._utils import (
    TransformError,
    get_page_dimensions,
    parse_dimension,
)


def resize_page(
    page: PageObject,
    width: str,
    height: str,
    fit: FitMode = FitMode.CONTAIN,
) -> PageObject:
    """
    Resize a page to the target dimensions.

    Args:
        page: The page to resize
        width: Target width (e.g., "100mm", "4in")
        height: Target height (e.g., "150mm", "6in")
        fit: FitMode enum value:
            - CONTAIN: Scale uniformly to fit within target, centered (may have whitespace)
            - COVER: Scale uniformly to fill target, centered (may crop edges)
            - STRETCH: Stretch non-uniformly to exactly match target

    Returns:
        The resized page (mutates in place and returns)
    """
    target_width = parse_dimension(width)
    target_height = parse_dimension(height)

    current_width, current_height = get_page_dimensions(page)

    if fit == FitMode.STRETCH:
        # Non-uniform scaling using transformation matrix
        scale_x = target_width / current_width
        scale_y = target_height / current_height

        # Apply non-uniform scale transformation
        transform = Transformation().scale(sx=scale_x, sy=scale_y)
        page.add_transformation(transform)

        # Update mediabox to target dimensions
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (target_width, target_height)
    elif fit in (FitMode.CONTAIN, FitMode.COVER):
        # Uniform scaling
        scale_x = target_width / current_width
        scale_y = target_height / current_height

        if fit == FitMode.CONTAIN:
            scale = min(scale_x, scale_y)
        else:  # COVER
            scale = max(scale_x, scale_y)

        # Calculate scaled dimensions
        scaled_width = current_width * scale
        scaled_height = current_height * scale

        # Calculate centering offsets
        offset_x = (target_width - scaled_width) / 2
        offset_y = (target_height - scaled_height) / 2

        # Apply scale and translation to center the content
        transform = (
            Transformation().scale(sx=scale, sy=scale).translate(tx=offset_x, ty=offset_y)
        )
        page.add_transformation(transform)

        # Set final mediabox to target size
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (target_width, target_height)
    else:
        # This should never happen with proper enum usage
        valid = ", ".join(f.value for f in FitMode)
        raise TransformError(f"Unknown fit mode: {fit}. Valid options: {valid}")

    return page


@register_transform("size")
class ResizeTransformHandler(BaseTransform):
    """Handler for resize transforms."""

    def __init__(self, config: SizeConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "ResizeTransformHandler":
        if not transform.size:
            raise ValueError("Size transform missing size config")
        return cls(transform.size)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        for page in pages:
            resize_page(page, self.config.width, self.config.height, self.config.fit)
        return TransformResult(pages=pages, mode="replace")

    def describe(self) -> str:
        return f"size_{self.config.fit.value}"
