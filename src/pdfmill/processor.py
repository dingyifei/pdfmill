"""Main processing pipeline for pdfmill."""

import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfmill.config import Config, ConfigError, FilterConfig, OutputProfile, PrintTarget, Transform
from pdfmill.selector import select_pages, PageSelectionError
from pdfmill.transforms import rotate_page, crop_page, resize_page, split_page, combine_pages, render_page, TransformError
from pdfmill.printer import print_pdf, PrinterError


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

    if filter_config.match == "all":
        return all(kw in text for kw in filter_config.keywords)
    else:  # "any"
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


VALID_SORT_OPTIONS = {"name_asc", "name_desc", "time_asc", "time_desc"}


def sort_files(files: list[Path], sort_option: str) -> list[Path]:
    """Sort files by name or modification time.

    Args:
        files: List of file paths to sort
        sort_option: One of name_asc, name_desc, time_asc, time_desc

    Returns:
        Sorted list of file paths
    """
    if sort_option not in VALID_SORT_OPTIONS:
        raise ConfigError(f"Invalid sort option: {sort_option}. Valid options: {VALID_SORT_OPTIONS}")

    if sort_option == "name_asc":
        return sorted(files, key=lambda f: f.name.lower())
    elif sort_option == "name_desc":
        return sorted(files, key=lambda f: f.name.lower(), reverse=True)
    elif sort_option == "time_asc":
        return sorted(files, key=lambda f: f.stat().st_mtime)
    elif sort_option == "time_desc":
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


def split_pages_by_weight(
    pdf_path: Path,
    targets: dict[str, PrintTarget],
    output_dir: Path,
    profile_name: str,
) -> dict[str, Path]:
    """Split PDF pages across targets by weight ratio.

    Pages assigned sequentially: highest weight gets first pages.
    This allows stacking printouts in order when collecting from multiple printers.

    Args:
        pdf_path: Path to PDF to split
        targets: Dict of target name to PrintTarget
        output_dir: Directory for split PDF outputs
        profile_name: Profile name for output filenames

    Returns:
        Dict mapping target name to split PDF path
    """
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    # Sort by weight descending (fastest/highest-weight first for stacking)
    sorted_targets = sorted(
        [(name, t) for name, t in targets.items() if t.weight > 0],
        key=lambda x: x[1].weight,
        reverse=True
    )

    if not sorted_targets:
        return {}

    total_weight = sum(t.weight for _, t in sorted_targets)

    result = {}
    current_page = 0

    for i, (target_name, target) in enumerate(sorted_targets):
        # Last target gets remaining pages (handles rounding)
        if i == len(sorted_targets) - 1:
            page_count = total_pages - current_page
        else:
            page_count = round(total_pages * target.weight / total_weight)

        if page_count <= 0:
            continue

        # Create split PDF
        writer = PdfWriter()
        end_page = min(current_page + page_count, total_pages)
        for j in range(current_page, end_page):
            writer.add_page(reader.pages[j])

        split_path = output_dir / f"split_{profile_name}_{target_name}.pdf"
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(split_path, "wb") as f:
            writer.write(f)

        result[target_name] = split_path
        current_page = end_page

        if current_page >= total_pages:
            break

    return result


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
    elif transform.type == "split" and transform.split:
        n = len(transform.split.regions)
        return f"split{n}"
    elif transform.type == "combine" and transform.combine:
        n = transform.combine.pages_per_output
        return f"combine{n}"
    elif transform.type == "render" and transform.render:
        return f"render_{transform.render.dpi}dpi"
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
        elif transform.type == "split" and transform.split:
            # Split: 1 page -> N pages (one per region)
            split_cfg = transform.split
            regions = [(r.lower_left, r.upper_right) for r in split_cfg.regions]
            if dry_run:
                print(f"    [dry-run] Split {len(pages)} page(s) into {len(regions)} regions each")
                print(f"              Result: {len(pages) * len(regions)} pages")
            else:
                new_pages = []
                for page in pages:
                    new_pages.extend(split_page(page, regions))
                pages = new_pages

        elif transform.type == "combine" and transform.combine:
            # Combine: N pages -> 1 page (batched)
            combine_cfg = transform.combine
            batch_size = combine_cfg.pages_per_output
            layout = [
                {
                    "page": item.page,
                    "position": item.position,
                    "scale": item.scale,
                }
                for item in combine_cfg.layout
            ]
            if dry_run:
                output_count = (len(pages) + batch_size - 1) // batch_size
                print(f"    [dry-run] Combine {len(pages)} page(s) into {output_count} page(s)")
                print(f"              ({batch_size} pages per output, size {combine_cfg.page_size})")
            else:
                new_pages = []
                for i in range(0, len(pages), batch_size):
                    batch = pages[i:i + batch_size]
                    combined = combine_pages(batch, combine_cfg.page_size, layout)
                    new_pages.append(combined)
                pages = new_pages
        elif transform.type == "render" and transform.render:
            render = transform.render
            for i, page in enumerate(pages):
                if dry_run:
                    print(f"    [dry-run] Render page {i + 1} at {render.dpi} DPI")
                else:
                    # render_page returns a new page, so we need to replace it
                    pages[i] = render_page(page, render.dpi)

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

    # Apply keyword filter if configured
    if config.input.filter and config.input.filter.keywords:
        total_before = len(input_files)
        input_files = [f for f in input_files if matches_filter(f, config.input.filter)]
        filtered_count = total_before - len(input_files)
        if filtered_count > 0:
            print(f"Filtered out {filtered_count} file(s) by keyword filter")
        if not input_files:
            print("No PDF files matched the keyword filter")
            return

    print(f"Found {len(input_files)} PDF file(s) to process")

    # Validate sort settings - error if both input.sort and any profile.sort are set
    for profile_name, profile in config.outputs.items():
        if config.input.sort and profile.sort:
            raise ConfigError(
                f"Sort specified in both input ({config.input.sort}) "
                f"and profile '{profile_name}' ({profile.sort}). Use only one."
            )

    # Apply global input sorting if configured
    if config.input.sort:
        input_files = sort_files(input_files, config.input.sort)
        print(f"Sorted files by: {config.input.sort}")

    success_count = 0
    fail_count = 0
    # Track output files by profile name for merge support
    # Includes source_path for per-profile sorting
    output_files: list[tuple[Path, str, OutputProfile, Path]] = []

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
                    output_files.append((output_path, profile_name, profile, pdf_path))
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
        # Each entry: (output_path, profile, source_path)
        files_by_profile: dict[str, list[tuple[Path, OutputProfile, Path]]] = {}
        for output_path, profile_name, profile, source_path in output_files:
            if profile_name not in files_by_profile:
                files_by_profile[profile_name] = []
            files_by_profile[profile_name].append((output_path, profile, source_path))

        for profile_name, profile_files in files_by_profile.items():
            if not profile_files:
                continue

            profile = profile_files[0][1]  # All files have same profile
            if not profile.print.enabled or not profile.print.targets:
                continue

            # Apply per-profile sorting if configured (and no global sort)
            if profile.sort:
                # Sort by source file
                if profile.sort == "name_asc":
                    profile_files = sorted(profile_files, key=lambda x: x[2].name.lower())
                elif profile.sort == "name_desc":
                    profile_files = sorted(profile_files, key=lambda x: x[2].name.lower(), reverse=True)
                elif profile.sort == "time_asc":
                    profile_files = sorted(profile_files, key=lambda x: x[2].stat().st_mtime)
                elif profile.sort == "time_desc":
                    profile_files = sorted(profile_files, key=lambda x: x[2].stat().st_mtime, reverse=True)
                print(f"Sorted profile '{profile_name}' files by: {profile.sort}")

            targets = profile.print.targets
            merge_output_dir = output_dir if output_dir else profile.output_dir

            try:
                if profile.print.merge and len(profile_files) > 1:
                    # Merge all PDFs for this profile before printing
                    pdf_paths = [pf[0] for pf in profile_files]
                    merged_path = merge_output_dir / f"merged_{profile_name}.pdf"

                    print(f"Merging {len(pdf_paths)} files for profile '{profile_name}'...")
                    merge_pdfs(pdf_paths, merged_path)
                    merged_files.append(merged_path)
                    files_to_print = [merged_path]
                else:
                    files_to_print = [pf[0] for pf in profile_files]

                if len(targets) > 1 and profile.print.merge:
                    # Multi-printer page distribution
                    for file_path in files_to_print:
                        print(f"Splitting {file_path.name} across {len(targets)} printers...")
                        split_pdfs = split_pages_by_weight(
                            file_path, targets, merge_output_dir, profile_name
                        )
                        for target_name, split_path in split_pdfs.items():
                            target = targets[target_name]
                            print(f"  Printing {split_path.name} to {target.printer}...")
                            print_pdf(
                                split_path,
                                target.printer,
                                target.copies,
                                target.args,
                                dry_run=dry_run,
                            )
                            merged_files.append(split_path)  # Track for cleanup
                else:
                    # Single target or copy distribution (each file to all targets)
                    for file_path in files_to_print:
                        for target_name, target in targets.items():
                            print(f"Printing {file_path.name} to {target.printer}...")
                            print_pdf(
                                file_path,
                                target.printer,
                                target.copies,
                                target.args,
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
            for output_path, _, profile, _ in output_files:
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
