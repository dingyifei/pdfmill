"""Transform execution pipeline for pdfmill."""

from pathlib import Path

from pypdf import PageObject, PdfWriter

from pdfmill.config import Transform
from pdfmill.logging_config import get_logger
from pdfmill.transforms import TransformContext, get_transform

logger = get_logger(__name__)


class TransformExecutor:
    """Manages transform execution with debug support."""

    def apply(
        self,
        pages: list[PageObject],
        transforms: list[Transform],
        dry_run: bool = False,
        pdf_path: Path | None = None,
        original_page_indices: list[int] | None = None,
        debug: bool = False,
        debug_output_dir: Path | None = None,
        debug_source_name: str = "",
        debug_profile_name: str = "",
    ) -> list[PageObject]:
        """
        Apply transformations to a list of pages.

        Args:
            pages: List of pypdf PageObjects
            transforms: List of transforms to apply
            dry_run: If True, only describe what would be done
            pdf_path: Path to source PDF (needed for auto rotation)
            original_page_indices: 0-indexed page numbers from source PDF (for auto rotation)
            debug: If True, save intermediate PDFs after each transform
            debug_output_dir: Directory for debug output files
            debug_source_name: Source filename for debug output naming
            debug_profile_name: Profile name for debug output naming

        Returns:
            Transformed pages
        """
        # Save initial state (after page selection) if debug enabled
        if debug and not dry_run and debug_output_dir:
            self._save_debug_pdf(pages, debug_output_dir, debug_source_name, debug_profile_name, 0, "selected")

        for step_num, transform in enumerate(transforms, start=1):
            # Skip disabled transforms
            if not transform.enabled:
                continue

            # Get handler from registry
            handler = get_transform(transform)
            step_desc = handler.describe()

            # Build context
            context = TransformContext(
                pdf_path=pdf_path,
                original_page_indices=original_page_indices,
                total_pages=len(pages),
                dry_run=dry_run,
            )

            if dry_run:
                logger.info("    [dry-run] %s", step_desc)
            else:
                # Apply transform
                result = handler.apply(pages, context)
                pages = result.pages

            # Save after each transform if debug enabled
            if debug and not dry_run and debug_output_dir:
                self._save_debug_pdf(
                    pages, debug_output_dir, debug_source_name, debug_profile_name, step_num, step_desc
                )

        return pages

    def _save_debug_pdf(
        self,
        pages: list[PageObject],
        output_dir: Path,
        source_name: str,
        profile_name: str,
        step_num: int,
        step_desc: str,
    ) -> None:
        """Save intermediate PDF for debugging."""
        debug_filename = f"{Path(source_name).stem}_{profile_name}_step{step_num}_{step_desc}.pdf"
        debug_path = output_dir / debug_filename

        writer = PdfWriter()
        for page in pages:
            writer.add_page(page)

        output_dir.mkdir(parents=True, exist_ok=True)
        with open(debug_path, "wb") as f:
            writer.write(f)

        logger.debug("Saved: %s", debug_path)
