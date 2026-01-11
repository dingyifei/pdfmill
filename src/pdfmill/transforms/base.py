"""Base classes for transform handlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PageObject

if TYPE_CHECKING:
    from pdfmill.config import Transform


@dataclass
class TransformContext:
    """Context passed to transform handlers during execution.

    Provides information about the current transformation context,
    including page indices and source file information needed for
    operations like auto-rotation.
    """

    page_index: int
    """0-indexed position in the current page list being transformed."""

    total_pages: int
    """Total number of pages being transformed."""

    pdf_path: Path | None = None
    """Path to the source PDF file (needed for auto-rotation)."""

    original_page_index: int | None = None
    """0-indexed page number in the original source PDF."""

    dry_run: bool = False
    """If True, describe the operation without executing it."""


class TransformHandler(ABC):
    """Abstract base class for transform implementations.

    Each transform type (rotate, crop, size) implements this interface.
    Handlers are registered with the TransformRegistry for dispatch.

    Example:
        class RotateHandler(TransformHandler):
            name = "rotate"

            def apply(self, page, transform, context):
                return rotate_page(page, transform.rotate.angle)

            def describe(self, transform):
                return f"Rotate by {transform.rotate.angle}"
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Transform type name (e.g., 'rotate', 'crop', 'size').

        This must match the `type` field in Transform dataclass.
        """

    @abstractmethod
    def apply(
        self,
        page: PageObject,
        transform: "Transform",
        context: TransformContext,
    ) -> PageObject:
        """Apply the transform to a page.

        Args:
            page: The pypdf PageObject to transform
            transform: The Transform configuration
            context: Execution context with page info

        Returns:
            The transformed page (may mutate in place)
        """

    @abstractmethod
    def describe(self, transform: "Transform") -> str:
        """Return human-readable description for dry-run/debug output.

        Args:
            transform: The Transform configuration

        Returns:
            Short description like "Rotate by 90°"
        """
