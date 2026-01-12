"""Base classes for transform registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pypdf import PageObject

if TYPE_CHECKING:
    from pdfmill.config import Transform


@dataclass
class TransformResult:
    """Result of applying a transform.

    Attributes:
        pages: The resulting pages
        mode: How the result should be interpreted:
            - "replace": Replace input pages with result (most common)
            - "expand": Result may have more pages than input (split)
            - "reduce": Result has fewer pages (combine, batched)
        batch_size: For "reduce" mode, how many input pages consumed per output
    """

    pages: list[PageObject]
    mode: Literal["replace", "expand", "reduce"] = "replace"
    batch_size: int = 1


@dataclass
class TransformContext:
    """Context passed to all transforms.

    This provides all the information a transform might need without
    requiring each transform to declare every possible parameter.
    """

    # Source PDF path (for OCR-based auto rotation)
    pdf_path: Path | None = None

    # Original page indices in source PDF (0-indexed)
    original_page_indices: list[int] | None = None

    # Total pages being processed
    total_pages: int = 0

    # Dry run mode
    dry_run: bool = False


class BaseTransform(ABC):
    """Abstract base class for all transforms.

    Each transform class wraps an existing config dataclass and provides
    a unified interface for applying the transformation.
    """

    # The transform type name (e.g., "rotate", "crop")
    # Set by @register_transform decorator
    name: str = ""

    @abstractmethod
    def apply(
        self,
        pages: list[PageObject],
        context: TransformContext,
    ) -> TransformResult:
        """Apply this transform to the given pages.

        Args:
            pages: Input pages to transform
            context: Transform context with metadata

        Returns:
            TransformResult with output pages and mode
        """
        pass

    @abstractmethod
    def describe(self) -> str:
        """Return a short description for debug filenames.

        Returns:
            Short description string (e.g., "rotate90", "crop", "split2")
        """
        pass

    @classmethod
    @abstractmethod
    def from_config(cls, transform: "Transform") -> "BaseTransform":
        """Create a transform instance from a config Transform object.

        Args:
            transform: The parsed Transform config object

        Returns:
            An instance of this transform class
        """
        pass
