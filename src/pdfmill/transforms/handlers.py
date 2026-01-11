"""Concrete transform handler implementations."""

from pypdf import PageObject

from pdfmill.config import Transform
from pdfmill.transforms.base import TransformHandler, TransformContext
from pdfmill.transforms.registry import TransformRegistry
from pdfmill.transforms.core import rotate_page, crop_page, resize_page


@TransformRegistry.register
class RotateHandler(TransformHandler):
    """Handler for rotate transforms."""

    name = "rotate"

    def apply(
        self,
        page: PageObject,
        transform: Transform,
        context: TransformContext,
    ) -> PageObject:
        """Apply rotation to a page.

        Supports numeric angles (0, 90, 180, 270) and orientation modes
        ('landscape', 'portrait', 'auto').
        """
        if not transform.rotate:
            return page

        rot = transform.rotate

        # Check if this page should be rotated (for page-specific rotation)
        if rot.pages is not None:
            if context.page_index not in rot.pages:
                return page

        return rotate_page(
            page,
            rot.angle,
            pdf_path=str(context.pdf_path) if context.pdf_path else None,
            page_num=context.original_page_index,
        )

    def describe(self, transform: Transform) -> str:
        """Return description for dry-run output."""
        if not transform.rotate:
            return "Rotate (no config)"

        angle = transform.rotate.angle
        if transform.rotate.pages:
            pages_str = ", ".join(str(p + 1) for p in transform.rotate.pages)
            return f"Rotate pages [{pages_str}] by {angle}"
        return f"Rotate by {angle}"


@TransformRegistry.register
class CropHandler(TransformHandler):
    """Handler for crop transforms."""

    name = "crop"

    def apply(
        self,
        page: PageObject,
        transform: Transform,
        context: TransformContext,
    ) -> PageObject:
        """Apply cropping to a page."""
        if not transform.crop:
            return page

        crop = transform.crop
        return crop_page(page, crop.lower_left, crop.upper_right)

    def describe(self, transform: Transform) -> str:
        """Return description for dry-run output."""
        if not transform.crop:
            return "Crop (no config)"

        crop = transform.crop
        return f"Crop: {crop.lower_left} to {crop.upper_right}"


@TransformRegistry.register
class SizeHandler(TransformHandler):
    """Handler for resize transforms."""

    name = "size"

    def apply(
        self,
        page: PageObject,
        transform: Transform,
        context: TransformContext,
    ) -> PageObject:
        """Apply resize to a page."""
        if not transform.size:
            return page

        size = transform.size
        return resize_page(page, size.width, size.height, size.fit)

    def describe(self, transform: Transform) -> str:
        """Return description for dry-run output."""
        if not transform.size:
            return "Resize (no config)"

        size = transform.size
        return f"Resize to {size.width} x {size.height} ({size.fit})"
