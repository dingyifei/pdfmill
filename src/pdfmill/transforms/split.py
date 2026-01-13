"""Split transform for pdfmill."""

import io
import logging

from pypdf import PageObject, PdfReader, PdfWriter

from pdfmill.config import SplitTransform as SplitConfig
from pdfmill.config import Transform
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.crop import crop_page
from pdfmill.transforms.registry import register_transform


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
    if not regions:
        return []

    # Serialize the source page to bytes once.
    # This is necessary because pypdf's deepcopy doesn't properly isolate
    # the content stream - multiple copies share the same /Contents object,
    # causing add_transformation() to affect all copies.
    temp_writer = PdfWriter()
    temp_writer.add_page(page)
    buffer = io.BytesIO()
    temp_writer.write(buffer)
    source_bytes = buffer.getvalue()

    result_pages = []

    # Temporarily suppress pypdf warnings about xref entries
    # These occur when re-reading serialized single-page PDFs but are harmless
    pypdf_logger = logging.getLogger("pypdf")
    original_level = pypdf_logger.level
    pypdf_logger.setLevel(logging.ERROR)

    try:
        for lower_left, upper_right in regions:
            # Create a fresh reader for each region to get independent page objects
            reader = PdfReader(io.BytesIO(source_bytes))
            page_copy = reader.pages[0]
            # Apply crop to extract the region
            crop_page(page_copy, lower_left, upper_right)
            result_pages.append(page_copy)
    finally:
        pypdf_logger.setLevel(original_level)

    return result_pages


@register_transform("split")
class SplitTransformHandler(BaseTransform):
    """Handler for split transforms (1 page -> N pages)."""

    def __init__(self, config: SplitConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "SplitTransformHandler":
        if not transform.split:
            raise ValueError("Split transform missing split config")
        return cls(transform.split)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        # Convert config regions to coordinate tuples
        regions = [(r.lower_left, r.upper_right) for r in self.config.regions]

        new_pages = []
        for page in pages:
            new_pages.extend(split_page(page, regions))

        return TransformResult(pages=new_pages, mode="expand")

    def describe(self) -> str:
        n = len(self.config.regions)
        return f"split{n}"
