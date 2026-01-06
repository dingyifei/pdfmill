"""Main processing pipeline for pdfpipe."""

import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfpipe.config import Config, OutputProfile, Transform
from pdfpipe.selector import select_pages, PageSelectionError
from pdfpipe.transforms import rotate_page, crop_page, resize_page, TransformError
from pdfpipe.printer import print_pdf, PrinterError


class ProcessingError(Exception):
    """Raised when PDF processing fails."""


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


def generate_output_filename(
    source_name: str,
    profile_name: str,
    prefix: str = "",
    suffix: str = "",
) -> str:
    """Generate output filename based on source and profile settings."""
    stem = Path(source_name).stem
    return f"{prefix}{stem}{suffix}_{profile_name}.pdf"


def merge_pdfs(pdf_paths: list[Path], output_path: Path) -> Path:
    """
    Merge multiple PDFs into a single file.

    Args:
        pdf_paths: List of PDF files to merge (in order)
        output_path: Path for the merged output file

    Returns:
        Path to the merged PDF
    """
    writer = PdfWriter()

    for pdf_path in pdf_paths:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path


def _get_transform_description(transform: Transform) -> str:
    """Get a short description of a transform for debug filenames."""
    if transform.type == "rotate" and transform.rotate:
        angle = transform.rotate.angle
        return f"rotate{angle}"
    elif transform.type == "crop" and transform.crop:
        return "crop"
    elif transform.type == "size" and transform.size:
        size = transform.size
        return f"size_{size.fit}"
    return transform.type


def _save_debug_pdf(
    pages: list,
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

    print(f"    [debug] Saved: {debug_path}")


def apply_transforms(
    pages: list,
    transforms: list[Transform],
    dry_run: bool = False,
    pdf_path: Path | None = None,
    original_page_indices: list[int] | None = None,
    debug: bool = False,
    debug_output_dir: Path | None = None,
    debug_source_name: str = "",
    debug_profile_name: str = "",
) -> list:
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
        _save_debug_pdf(
            pages, debug_output_dir, debug_source_name,
            debug_profile_name, 0, "selected"
        )

    for step_num, transform in enumerate(transforms, start=1):
        step_desc = _get_transform_description(transform)

        if transform.type == "rotate" and transform.rotate:
            rot = transform.rotate
            pages_to_rotate = rot.pages if rot.pages else list(range(len(pages)))

            for idx in pages_to_rotate:
                if idx < len(pages):
                    if dry_run:
                        print(f"    [dry-run] Rotate page {idx + 1} by {rot.angle}")
                    else:
                        # For auto rotation, we need the original page number in the source PDF
                        orig_page_num = None
                        if original_page_indices and idx < len(original_page_indices):
                            orig_page_num = original_page_indices[idx]
                        rotate_page(
                            pages[idx],
                            rot.angle,
                            pdf_path=str(pdf_path) if pdf_path else None,
                            page_num=orig_page_num,
                        )

        elif transform.type == "crop" and transform.crop:
            crop = transform.crop
            for i, page in enumerate(pages):
                if dry_run:
                    print(f"    [dry-run] Crop page {i + 1}: {crop.lower_left} to {crop.upper_right}")
                else:
                    crop_page(page, crop.lower_left, crop.upper_right)

        elif transform.type == "size" and transform.size:
            size = transform.size
            for i, page in enumerate(pages):
                if dry_run:
                    print(f"    [dry-run] Resize page {i + 1} to {size.width} x {size.height} ({size.fit})")
                else:
                    resize_page(page, size.width, size.height, size.fit)

        # Save after each transform if debug enabled
        if debug and not dry_run and debug_output_dir:
            _save_debug_pdf(
                pages, debug_output_dir, debug_source_name,
                debug_profile_name, step_num, step_desc
            )

    return pages


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
        print(f"  Processing profile '{profile_name}' for {pdf_path.name}")

    # Read source PDF
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    # Select pages
    try:
        page_indices = select_pages(profile.pages, total_pages)
    except PageSelectionError as e:
        raise ProcessingError(f"Page selection failed: {e}")

    if dry_run:
        print(f"    [dry-run] Select pages: {[i + 1 for i in page_indices]} from {total_pages} pages")

    # Extract pages
    pages = [reader.pages[i] for i in page_indices]

    # Apply transforms (pass pdf_path and original indices for auto rotation)
    pages = apply_transforms(
        pages,
        profile.transforms,
        dry_run,
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
        print(f"    [dry-run] Write to: {output_path}")
        return None

    # Write output
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"  Created: {output_path}")
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
        print(f"No PDF files found in: {input_path}")
        return

    print(f"Found {len(input_files)} PDF file(s) to process")

    success_count = 0
    fail_count = 0
    # Track output files by profile name for merge support
    output_files: list[tuple[Path, str, OutputProfile]] = []

    for pdf_path in input_files:
        print(f"\nProcessing: {pdf_path.name}")

        for profile_name, profile in config.outputs.items():
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
                    output_files.append((output_path, profile_name, profile))
                success_count += 1

            except (ProcessingError, TransformError) as e:
                print(f"  Error in profile '{profile_name}': {e}")
                fail_count += 1
                if config.settings.on_error == "stop":
                    raise

    # Track merged files for cleanup (outside dry_run block for scope)
    merged_files: list[Path] = []

    # Print outputs
    if not dry_run:
        # Group files by profile name for merge support
        files_by_profile: dict[str, list[tuple[Path, OutputProfile]]] = {}
        for output_path, profile_name, profile in output_files:
            if profile_name not in files_by_profile:
                files_by_profile[profile_name] = []
            files_by_profile[profile_name].append((output_path, profile))

        for profile_name, profile_files in files_by_profile.items():
            if not profile_files:
                continue

            profile = profile_files[0][1]  # All files have same profile
            if not profile.print.enabled:
                continue

            try:
                if profile.print.merge and len(profile_files) > 1:
                    # Merge all PDFs for this profile before printing
                    pdf_paths = [pf[0] for pf in profile_files]
                    merge_output_dir = output_dir if output_dir else profile.output_dir
                    merged_path = merge_output_dir / f"merged_{profile_name}.pdf"

                    print(f"Merging {len(pdf_paths)} files for profile '{profile_name}'...")
                    merge_pdfs(pdf_paths, merged_path)
                    merged_files.append(merged_path)

                    print(f"Printing merged PDF to {profile.print.printer}...")
                    print_pdf(
                        merged_path,
                        profile.print.printer,
                        profile.print.copies,
                        profile.print.args,
                        dry_run=dry_run,
                    )
                else:
                    # Print each file individually
                    for output_path, _ in profile_files:
                        print(f"Printing {output_path.name} to {profile.print.printer}...")
                        print_pdf(
                            output_path,
                            profile.print.printer,
                            profile.print.copies,
                            profile.print.args,
                            dry_run=dry_run,
                        )
            except PrinterError as e:
                print(f"  Print error: {e}")
                fail_count += 1
                if config.settings.on_error == "stop":
                    raise

    # Cleanup
    if not dry_run:
        if config.settings.cleanup_source:
            for pdf_path in input_files:
                try:
                    os.remove(pdf_path)
                    print(f"Cleaned up source: {pdf_path}")
                except OSError as e:
                    print(f"Failed to cleanup {pdf_path}: {e}")

        if config.settings.cleanup_output_after_print:
            for output_path, _, profile in output_files:
                if profile.print.enabled:
                    try:
                        os.remove(output_path)
                        print(f"Cleaned up output: {output_path}")
                    except OSError as e:
                        print(f"Failed to cleanup {output_path}: {e}")

            # Also cleanup merged files
            for merged_path in merged_files:
                try:
                    os.remove(merged_path)
                    print(f"Cleaned up merged: {merged_path}")
                except OSError as e:
                    print(f"Failed to cleanup {merged_path}: {e}")

    # Summary
    print(f"\nProcessing complete: {success_count} succeeded, {fail_count} failed")
