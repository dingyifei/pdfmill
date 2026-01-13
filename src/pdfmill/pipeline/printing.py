"""Print pipeline for pdfmill."""

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfmill.config import (
    ErrorHandling,
    OutputProfile,
    PrintTarget,
    SortOrder,
)
from pdfmill.printer import PrinterError, print_pdf


@dataclass
class PrintResult:
    """Result from print pipeline for cleanup tracking."""

    temporary_files: list[Path] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0


class PrintPipeline:
    """Manages printing workflow including merge, split, and distribution."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def merge_pdfs(self, pdf_paths: list[Path], output_path: Path) -> Path:
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
        self,
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
            reverse=True,
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

    def print_outputs(
        self,
        files_by_profile: dict[str, list[tuple[Path, OutputProfile, Path]]],
        output_dir: Path | None,
        on_error: ErrorHandling,
    ) -> PrintResult:
        """
        Orchestrate printing for all profiles.

        Args:
            files_by_profile: Dict mapping profile name to list of (output_path, profile, source_path)
            output_dir: Override output directory (uses profile dirs if None)
            on_error: Error handling strategy

        Returns:
            PrintResult with temporary files list and counts
        """
        result = PrintResult()

        for profile_name, profile_files in files_by_profile.items():
            if not profile_files:
                continue

            profile = profile_files[0][1]  # All files have same profile
            if not profile.print.enabled or not profile.print.targets:
                continue

            # Apply per-profile sorting if configured
            if profile.sort:
                profile_files = self._sort_profile_files(profile_files, profile.sort)
                print(f"Sorted profile '{profile_name}' files by: {profile.sort.value}")

            targets = profile.print.targets
            merge_output_dir = output_dir if output_dir else profile.output_dir

            try:
                self._print_profile(
                    profile_name,
                    profile_files,
                    profile,
                    targets,
                    merge_output_dir,
                    result,
                )
                result.success_count += 1
            except PrinterError as e:
                print(f"  Print error: {e}")
                result.fail_count += 1
                if on_error == ErrorHandling.STOP:
                    raise

        return result

    def _sort_profile_files(
        self,
        profile_files: list[tuple[Path, OutputProfile, Path]],
        sort_order: SortOrder,
    ) -> list[tuple[Path, OutputProfile, Path]]:
        """Sort profile files by source file according to sort order."""
        if sort_order == SortOrder.NAME_ASC:
            return sorted(profile_files, key=lambda x: x[2].name.lower())
        elif sort_order == SortOrder.NAME_DESC:
            return sorted(profile_files, key=lambda x: x[2].name.lower(), reverse=True)
        elif sort_order == SortOrder.TIME_ASC:
            return sorted(profile_files, key=lambda x: x[2].stat().st_mtime)
        elif sort_order == SortOrder.TIME_DESC:
            return sorted(profile_files, key=lambda x: x[2].stat().st_mtime, reverse=True)
        return profile_files

    def _print_profile(
        self,
        profile_name: str,
        profile_files: list[tuple[Path, OutputProfile, Path]],
        profile: OutputProfile,
        targets: dict[str, PrintTarget],
        merge_output_dir: Path,
        result: PrintResult,
    ) -> None:
        """Handle printing for a single profile."""
        if profile.print.merge and len(profile_files) > 1:
            # Merge all PDFs for this profile before printing
            pdf_paths = [pf[0] for pf in profile_files]
            merged_path = merge_output_dir / f"merged_{profile_name}.pdf"

            print(f"Merging {len(pdf_paths)} files for profile '{profile_name}'...")
            self.merge_pdfs(pdf_paths, merged_path)
            result.temporary_files.append(merged_path)
            files_to_print = [merged_path]
        else:
            files_to_print = [pf[0] for pf in profile_files]

        if len(targets) > 1 and profile.print.merge:
            # Multi-printer page distribution
            for file_path in files_to_print:
                print(f"Splitting {file_path.name} across {len(targets)} printers...")
                split_pdfs = self.split_pages_by_weight(file_path, targets, merge_output_dir, profile_name)
                for target_name, split_path in split_pdfs.items():
                    target = targets[target_name]
                    print(f"  Printing {split_path.name} to {target.printer}...")
                    print_pdf(
                        split_path,
                        target.printer,
                        target.copies,
                        target.args,
                        dry_run=self.dry_run,
                    )
                    result.temporary_files.append(split_path)
        else:
            # Single target or copy distribution (each file to all targets)
            for file_path in files_to_print:
                for _target_name, target in targets.items():
                    print(f"Printing {file_path.name} to {target.printer}...")
                    print_pdf(
                        file_path,
                        target.printer,
                        target.copies,
                        target.args,
                        dry_run=self.dry_run,
                    )
