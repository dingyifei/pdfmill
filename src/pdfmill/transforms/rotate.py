"""Rotate transform for pdfmill."""

from pypdf import PageObject, Transformation

from pdfmill.config import RotateTransform as RotateConfig, Transform
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.registry import register_transform
from pdfmill.transforms._utils import (
    TransformError,
    detect_page_orientation,
    get_page_dimensions,
    is_landscape,
)


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
            raise TransformError(
                f"Rotation angle must be 0, 90, 180, or 270, got {angle}"
            )
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


@register_transform("rotate")
class RotateTransformHandler(BaseTransform):
    """Handler for rotation transforms."""

    def __init__(self, config: RotateConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "RotateTransformHandler":
        if not transform.rotate:
            raise ValueError("Rotate transform missing rotate config")
        return cls(transform.rotate)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        # Determine which pages to rotate
        pages_to_rotate = (
            self.config.pages if self.config.pages else list(range(len(pages)))
        )

        for idx in pages_to_rotate:
            if idx < len(pages):
                # Get original page number for OCR-based auto rotation
                orig_page_num = None
                if (
                    context.original_page_indices
                    and idx < len(context.original_page_indices)
                ):
                    orig_page_num = context.original_page_indices[idx]

                rotate_page(
                    pages[idx],
                    self.config.angle,
                    pdf_path=str(context.pdf_path) if context.pdf_path else None,
                    page_num=orig_page_num,
                )

        return TransformResult(pages=pages, mode="replace")

    def describe(self) -> str:
        return f"rotate{self.config.angle}"
