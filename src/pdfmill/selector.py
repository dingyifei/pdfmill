"""Page selection logic for pdfmill."""

import re
from typing import Sequence

from pdfmill.exceptions import PageSelectionError


def select_pages(spec: str | list[int], total_pages: int) -> list[int]:
    """
    Convert a page specification to a list of 0-indexed page numbers.

    Supports:
    - List of integers: [1, 2, 3] -> pages 1, 2, 3 (1-indexed input)
    - Range string: "1-3" -> pages 1 through 3
    - Open range: "3-" -> page 3 to end
    - Last N: "-2" -> last 2 pages
    - Negative offset: "1--1" -> page 1 to second-to-last
    - Keywords: "first", "last", "odd", "even", "all"

    Args:
        spec: Page selection specification
        total_pages: Total number of pages in the PDF

    Returns:
        List of 0-indexed page numbers

    Raises:
        PageSelectionError: If the specification is invalid or pages don't exist
    """
    if total_pages <= 0:
        raise PageSelectionError("PDF has no pages")

    if isinstance(spec, list):
        return _select_from_list(spec, total_pages)

    if isinstance(spec, int):
        return _select_from_list([spec], total_pages)

    spec = spec.strip().lower()

    # Handle keywords
    if spec == "first":
        return [0]
    elif spec == "last":
        return [total_pages - 1]
    elif spec == "all":
        return list(range(total_pages))
    elif spec == "odd":
        return [i for i in range(total_pages) if (i + 1) % 2 == 1]
    elif spec == "even":
        return [i for i in range(total_pages) if (i + 1) % 2 == 0]

    # Handle negative index (single page from end)
    if re.match(r"^-\d+$", spec) and "--" not in spec:
        # Check if it's "-N" meaning last N pages
        n = int(spec[1:])
        if n > total_pages:
            raise PageSelectionError(f"Cannot select last {n} pages from {total_pages} page PDF")
        return list(range(total_pages - n, total_pages))

    # Handle range with negative offset: "1--1" means page 1 to second-to-last
    if "--" in spec:
        parts = spec.split("--")
        if len(parts) != 2:
            raise PageSelectionError(f"Invalid range specification: {spec}")
        start_str, neg_offset_str = parts
        try:
            start = int(start_str) if start_str else 1
            neg_offset = int(neg_offset_str) if neg_offset_str else 0
            end = total_pages - neg_offset
            if start < 1 or end < 1 or start > end:
                raise PageSelectionError(f"Invalid range: {spec} for {total_pages} page PDF")
            return list(range(start - 1, end))
        except ValueError:
            raise PageSelectionError(f"Invalid range specification: {spec}")

    # Handle simple range: "1-3", "3-"
    if "-" in spec:
        parts = spec.split("-")
        if len(parts) != 2:
            raise PageSelectionError(f"Invalid range specification: {spec}")
        start_str, end_str = parts

        try:
            start = int(start_str) if start_str else 1
            end = int(end_str) if end_str else total_pages

            if start < 1 or end < 1 or start > total_pages:
                raise PageSelectionError(f"Invalid range: {spec} for {total_pages} page PDF")
            if end > total_pages:
                end = total_pages
            if start > end:
                raise PageSelectionError(f"Start page {start} is after end page {end}")

            return list(range(start - 1, end))
        except ValueError:
            raise PageSelectionError(f"Invalid range specification: {spec}")

    # Handle single page number
    if spec.isdigit():
        page = int(spec)
        return _select_from_list([page], total_pages)

    raise PageSelectionError(f"Unknown page specification: {spec}")


def _select_from_list(pages: Sequence[int], total_pages: int) -> list[int]:
    """Convert a list of 1-indexed page numbers to 0-indexed, with validation."""
    result = []
    for page in pages:
        if page < 0:
            # Negative index: -1 is last page, -2 is second to last, etc.
            idx = total_pages + page
        else:
            # 1-indexed to 0-indexed
            idx = page - 1

        if idx < 0 or idx >= total_pages:
            raise PageSelectionError(
                f"Page {page} is out of range for {total_pages} page PDF"
            )
        result.append(idx)
    return result
