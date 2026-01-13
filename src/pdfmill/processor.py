"""Main processing pipeline for pdfmill."""

import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfmill.config import (
    Config,
    ConfigError,
    ErrorHandling,
    FilterConfig,
    FilterMatch,
    OutputProfile,
    SortOrder,
)
from pdfmill.logging_config import get_logger
from pdfmill.pipeline import PrintPipeline, TransformExecutor
from pdfmill.printer import PrinterError
from pdfmill.selector import PageSelectionError, select_pages
from pdfmill.transforms import TransformError

logger = get_logger(__name__)


class ProcessingError(Exception):
    """Raised when PDF processing fails."""


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text content from a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Concatenated text from all pages
    """
    reader = PdfReader(str(pdf_path))
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def matches_filter(pdf_path: Path, filter_config: FilterConfig) -> bool:
    """Check if a PDF matches the keyword filter.

    Args:
        pdf_path: Path to the PDF file
        filter_config: Filter configuration with keywords and match mode

    Returns:
        True if PDF matches the filter criteria
    """
    if not filter_config.keywords:
        return True  # No keywords = match all

    text = extract_pdf_text(pdf_path)

    if filter_config.match == FilterMatch.ALL:
        return all(kw in text for kw in filter_config.keywords)
    else:  # FilterMatch.ANY
        return any(kw in text for kw in filter_config.keywords)


def get_input_files(input_path: Path, pattern: str = "*.pdf") -> list[Path]:
    """
    Get list of PDF files to process.

    Args:
        input_path: File or directory path
        pattern: Glob pattern for finding files in directory

    Returns:
        List of PDF file paths
    """
    if input_path.is_file():
        return [input_path]
    elif input_path.is_dir():
        return sorted(input_path.glob(pattern))
    else:
        raise ProcessingError(f"Input path does not exist: {input_path}")


def sort_files(files: list[Path], sort_option: SortOrder) -> list[Path]:
    """Sort files by name or modification time.

    Args:
        files: List of file paths to sort
        sort_option: SortOrder enum value

    Returns:
        Sorted list of file paths
    """
    if sort_option == SortOrder.NAME_ASC:
        return sorted(files, key=lambda f: f.name.lower())
    elif sort_option == SortOrder.NAME_DESC:
        return sorted(files, key=lambda f: f.name.lower(), reverse=True)
    elif sort_option == SortOrder.TIME_ASC:
        return sorted(files, key=lambda f: f.stat().st_mtime)
    elif sort_option == SortOrder.TIME_DESC:
        return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def generate_output_filename(
    source_name: str,
    profile_name: str,
    prefix: str = "",
    suffix: str = "",
) -> str:
    """Generate output filename based on source and profile settings."""
    stem = Path(source_name).stem
    return f"{prefix}{stem}{suffix}_{profile_name}.pdf"


def process_single_pdf(
    pdf_path: Path,
    profile_name: str,
    profile: OutputProfile,
    output_dir: Path,
    dry_run: bool = False,
) -> Path | None:
    """
    Process a single PDF according to an output profile.

    Args:
        pdf_path: Path to source PDF
        profile_name: Name of the profile (for output filename)
        profile: Output profile configuration
        output_dir: Directory for output files
        dry_run: If True, only describe what would be done

    Returns:
        Path to output file, or None if dry run
    """
    if dry_run:
        logger.info("  Processing profile '%s' for %s", profile_name, pdf_path.name)

    # Read source PDF
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    # Select pages
    try:
        page_indices = select_pages(profile.pages, total_pages)
    except PageSelectionError as e:
        raise ProcessingError(f"Page selection failed: {e}")

    if dry_run:
        logger.info("    [dry-run] Select pages: %s from %d pages", [i + 1 for i in page_indices], total_pages)

    # Extract pages
    pages = [reader.pages[i] for i in page_indices]

    # Apply transforms (pass pdf_path and original indices for auto rotation)
    executor = TransformExecutor()
    pages = executor.apply(
        pages,
        profile.transforms,
        dry_run=dry_run,
        pdf_path=pdf_path,
        original_page_indices=page_indices,
        debug=profile.debug,
        debug_output_dir=output_dir,
        debug_source_name=pdf_path.name,
        debug_profile_name=profile_name,
    )

    # Generate output path
    output_filename = generate_output_filename(
        pdf_path.name,
        profile_name,
        profile.filename_prefix,
        profile.filename_suffix,
    )
    output_path = output_dir / output_filename

    if dry_run:
        logger.info("    [dry-run] Write to: %s", output_path)
        return None

    # Write output
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    logger.info("  Created: %s", output_path)
    return output_path


def process(
    config: Config,
    input_path: Path,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> None:
    """
    Process PDFs according to configuration.

    Args:
        config: Pipeline configuration
        input_path: Path to input file or directory
        output_dir: Override output directory (uses profile dirs if None)
        dry_run: If True, only describe what would be done
    """
    # Get input files
    input_files = get_input_files(input_path, config.input.pattern)
    if not input_files:
        logger.info("No PDF files found in: %s", input_path)
        return

    # Apply keyword filter if configured
    if config.input.filter and config.input.filter.keywords:
        total_before = len(input_files)
        input_files = [f for f in input_files if matches_filter(f, config.input.filter)]
        filtered_count = total_before - len(input_files)
        if filtered_count > 0:
            logger.info("Filtered out %d file(s) by keyword filter", filtered_count)
        if not input_files:
            logger.info("No PDF files matched the keyword filter")
            return

    logger.info("Found %d PDF file(s) to process", len(input_files))

    # Validate sort settings - error if both input.sort and any profile.sort are set
    for profile_name, profile in config.outputs.items():
        if config.input.sort and profile.sort:
            raise ConfigError(
                f"Sort specified in both input ({config.input.sort.value}) "
                f"and profile '{profile_name}' ({profile.sort.value}). Use only one."
            )

    # Apply global input sorting if configured
    if config.input.sort:
        input_files = sort_files(input_files, config.input.sort)
        logger.info("Sorted files by: %s", config.input.sort.value)

    success_count = 0
    fail_count = 0
    # Track output files by profile name for merge support
    # Includes source_path for per-profile sorting
    output_files: list[tuple[Path, str, OutputProfile, Path]] = []

    for pdf_path in input_files:
        logger.info("\nProcessing: %s", pdf_path.name)

        for profile_name, profile in config.outputs.items():
            # Skip disabled profiles
            if not profile.enabled:
                logger.debug("Skipping disabled profile: %s", profile_name)
                continue

            try:
                # Determine output directory
                profile_output_dir = output_dir if output_dir else profile.output_dir

                output_path = process_single_pdf(
                    pdf_path,
                    profile_name,
                    profile,
                    profile_output_dir,
                    dry_run,
                )

                if output_path:
                    output_files.append((output_path, profile_name, profile, pdf_path))
                success_count += 1

            except (ProcessingError, TransformError) as e:
                logger.error("Error in profile '%s': %s", profile_name, e)
                fail_count += 1
                if config.settings.on_error == ErrorHandling.STOP:
                    raise

    # Track temporary files for cleanup
    temporary_files: list[Path] = []

    # Print outputs
    if not dry_run:
        # Group files by profile name for merge support
        # Each entry: (output_path, profile, source_path)
        files_by_profile: dict[str, list[tuple[Path, OutputProfile, Path]]] = {}
        for output_path, profile_name, profile, source_path in output_files:
            if profile_name not in files_by_profile:
                files_by_profile[profile_name] = []
            files_by_profile[profile_name].append((output_path, profile, source_path))

        # Use PrintPipeline for print orchestration
        pipeline = PrintPipeline(dry_run=dry_run)
        try:
            print_result = pipeline.print_outputs(
                files_by_profile,
                output_dir,
                config.settings.on_error,
            )
            temporary_files = print_result.temporary_files
            fail_count += print_result.fail_count
        except PrinterError:
            # Error already logged by pipeline, re-raise if on_error is STOP
            if config.settings.on_error == ErrorHandling.STOP:
                raise

    # Cleanup
    if not dry_run:
        if config.settings.cleanup_source:
            for pdf_path in input_files:
                try:
                    os.remove(pdf_path)
                    logger.debug("Cleaned up source: %s", pdf_path)
                except OSError as e:
                    logger.warning("Failed to cleanup %s: %s", pdf_path, e)

        if config.settings.cleanup_output_after_print:
            for output_path, _, profile, _ in output_files:
                if profile.print.enabled:
                    try:
                        os.remove(output_path)
                        logger.debug("Cleaned up output: %s", output_path)
                    except OSError as e:
                        logger.warning("Failed to cleanup %s: %s", output_path, e)

            # Also cleanup temporary files (merged/split)
            for temp_path in temporary_files:
                try:
                    os.remove(temp_path)
                    logger.debug("Cleaned up temporary: %s", temp_path)
                except OSError as e:
                    logger.warning("Failed to cleanup %s: %s", temp_path, e)

    # Summary
    logger.info("\nProcessing complete: %d succeeded, %d failed", success_count, fail_count)
