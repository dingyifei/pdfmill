"""Crop transform for pdfmill."""

from pypdf import PageObject, Transformation

from pdfmill.config import CropTransform as CropConfig, Transform
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.registry import register_transform
from pdfmill.transforms._utils import TransformError, parse_coordinate


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
    ll_x = parse_coordinate(lower_left[0])
    ll_y = parse_coordinate(lower_left[1])
    ur_x = parse_coordinate(upper_right[0])
    ur_y = parse_coordinate(upper_right[1])

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


@register_transform("crop")
class CropTransformHandler(BaseTransform):
    """Handler for crop transforms."""

    def __init__(self, config: CropConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "CropTransformHandler":
        if not transform.crop:
            raise ValueError("Crop transform missing crop config")
        return cls(transform.crop)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        for page in pages:
            crop_page(page, self.config.lower_left, self.config.upper_right)
        return TransformResult(pages=pages, mode="replace")

    def describe(self) -> str:
        return "crop"
