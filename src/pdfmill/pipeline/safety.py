"""Print safety checks for pdfmill."""

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from pdfmill.config import PrintConfig, SafetyAction
from pdfmill.logging_config import get_logger
from pdfmill.transforms._utils import parse_coordinate

logger = get_logger(__name__)


class PrintSafetyError(Exception):
    """Raised when a print safety check fails."""

    def __init__(self, message: str, violations: list[str]):
        self.message = message
        self.violations = violations
        super().__init__(message)


@dataclass
class SafetyCheckResult:
    """Result of safety checks."""

    passed: bool = True
    violations: list[str] = field(default_factory=list)

    def add_violation(self, message: str) -> None:
        self.passed = False
        self.violations.append(message)


def check_print_safety(
    pdf_paths: list[Path],
    print_config: PrintConfig,
    profile_name: str,
) -> SafetyCheckResult:
    """
    Check if PDF files pass print safety limits.

    Args:
        pdf_paths: List of PDF files to check
        print_config: Print configuration with safety limits
        profile_name: Name of the profile (for error messages)

    Returns:
        SafetyCheckResult with pass/fail and violations list
    """
    result = SafetyCheckResult()

    # Check max_pages limit
    if print_config.max_pages is not None:
        total_pages = 0
        for pdf_path in pdf_paths:
            try:
                reader = PdfReader(str(pdf_path))
                total_pages += len(reader.pages)
            except Exception as e:
                logger.warning("Could not read %s for page count: %s", pdf_path, e)

        if total_pages > print_config.max_pages:
            result.add_violation(f"Page count ({total_pages}) exceeds max_pages limit ({print_config.max_pages})")

    # Check max_page_size limit
    if print_config.max_page_size is not None:
        max_width = parse_coordinate(print_config.max_page_size[0])
        max_height = parse_coordinate(print_config.max_page_size[1])

        for pdf_path in pdf_paths:
            try:
                reader = PdfReader(str(pdf_path))
                for page_num, page in enumerate(reader.pages, start=1):
                    mediabox = page.mediabox
                    page_width = float(mediabox.width)
                    page_height = float(mediabox.height)

                    # Check both orientations (page could be rotated)
                    fits_normal = page_width <= max_width and page_height <= max_height
                    fits_rotated = page_height <= max_width and page_width <= max_height

                    if not fits_normal and not fits_rotated:
                        result.add_violation(
                            f"{pdf_path.name} page {page_num}: size ({page_width:.1f}x{page_height:.1f} pt) "
                            f"exceeds max_page_size ({max_width:.1f}x{max_height:.1f} pt)"
                        )
            except Exception as e:
                logger.warning("Could not read %s for size check: %s", pdf_path, e)

    return result


def enforce_print_safety(
    pdf_paths: list[Path],
    print_config: PrintConfig,
    profile_name: str,
) -> bool:
    """
    Enforce print safety checks and handle violations.

    Args:
        pdf_paths: List of PDF files to check
        print_config: Print configuration with safety limits
        profile_name: Name of the profile (for error messages)

    Returns:
        True if printing should proceed, False if skipped

    Raises:
        PrintSafetyError: If action is BLOCK and violations found
    """
    # No safety limits configured
    if print_config.max_pages is None and print_config.max_page_size is None:
        return True

    result = check_print_safety(pdf_paths, print_config, profile_name)

    if not result.passed:
        violation_msg = "; ".join(result.violations)

        if print_config.action == SafetyAction.BLOCK:
            logger.error(
                "Print safety check failed for profile '%s': %s",
                profile_name,
                violation_msg,
            )
            raise PrintSafetyError(
                f"Print blocked for profile '{profile_name}': {violation_msg}",
                result.violations,
            )
        else:  # SafetyAction.WARN
            logger.warning(
                "Print safety warning for profile '%s': %s (continuing anyway)",
                profile_name,
                violation_msg,
            )

    return True
