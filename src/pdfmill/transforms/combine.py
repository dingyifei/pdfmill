"""Combine transform for pdfmill."""

from pypdf import PageObject, Transformation

from pdfmill.config import CombineTransform as CombineConfig
from pdfmill.config import Transform
from pdfmill.transforms._utils import parse_coordinate, parse_dimension
from pdfmill.transforms.base import BaseTransform, TransformContext, TransformResult
from pdfmill.transforms.registry import register_transform


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
        x = parse_coordinate(position[0])
        y = parse_coordinate(position[1])

        # Build transformation: scale then translate
        # Note: transformations are applied in reverse order in the matrix
        transform = Transformation().scale(sx=scale, sy=scale).translate(tx=x, ty=y)

        # Merge the source page onto the output with the transformation
        output_page.merge_transformed_page(source_page, transform)

    return output_page


@register_transform("combine")
class CombineTransformHandler(BaseTransform):
    """Handler for combine transforms (N pages -> 1 page, batched)."""

    def __init__(self, config: CombineConfig):
        self.config = config

    @classmethod
    def from_config(cls, transform: Transform) -> "CombineTransformHandler":
        if not transform.combine:
            raise ValueError("Combine transform missing combine config")
        return cls(transform.combine)

    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        batch_size = self.config.pages_per_output

        # Convert config layout to dict format
        layout = [
            {
                "page": item.page,
                "position": item.position,
                "scale": item.scale,
            }
            for item in self.config.layout
        ]

        new_pages = []
        for i in range(0, len(pages), batch_size):
            batch = pages[i : i + batch_size]
            combined = combine_pages(batch, self.config.page_size, layout)
            new_pages.append(combined)

        return TransformResult(
            pages=new_pages,
            mode="reduce",
            batch_size=batch_size,
        )

    def describe(self) -> str:
        n = self.config.pages_per_output
        return f"combine{n}"
