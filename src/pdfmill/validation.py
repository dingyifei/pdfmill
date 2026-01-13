"""Strict validation for pdfmill configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdfmill.config import Config, OutputProfile


@dataclass
class ValidationIssue:
    """A single validation issue."""

    level: str  # "error" or "warning"
    profile: str | None
    field: str
    message: str
    suggestion: str | None = None

    def __str__(self) -> str:
        parts = []
        if self.profile:
            parts.append(f"[{self.level.upper()}] Profile '{self.profile}', {self.field}")
        else:
            parts.append(f"[{self.level.upper()}] {self.field}")
        parts.append(f": {self.message}")
        if self.suggestion:
            parts.append(f"\n  Suggestion: {self.suggestion}")
        return "".join(parts)


@dataclass
class ValidationResult:
    """Result of strict validation."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.level == "warning" for i in self.issues)

    def add_error(
        self,
        field: str,
        message: str,
        profile: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.issues.append(ValidationIssue("error", profile, field, message, suggestion))

    def add_warning(
        self,
        field: str,
        message: str,
        profile: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.issues.append(ValidationIssue("warning", profile, field, message, suggestion))


def validate_strict(config: "Config") -> ValidationResult:
    """
    Perform strict validation on a configuration.

    Checks:
    - input.path exists and is readable
    - output_dir for each profile is writable (or parent exists)
    - Configured printers exist on the system

    Args:
        config: The parsed configuration

    Returns:
        ValidationResult with any issues found
    """
    result = ValidationResult()

    # Check input path
    _validate_input_path(config, result)

    # Check each output profile
    for name, profile in config.outputs.items():
        if not profile.enabled:
            continue  # Skip disabled profiles

        _validate_output_dir(name, profile, result)
        _validate_printers(name, profile, result)

    return result


def _validate_input_path(config: "Config", result: ValidationResult) -> None:
    """Validate input.path exists and is readable."""
    input_path = config.input.path

    if not input_path.exists():
        result.add_error(
            field="input.path",
            message=f"Input path does not exist: {input_path}",
            suggestion="Create the directory or update the path in the config",
        )
    elif not input_path.is_dir() and not input_path.is_file():
        result.add_error(
            field="input.path",
            message=f"Input path is neither a file nor directory: {input_path}",
        )


def _validate_output_dir(profile_name: str, profile: "OutputProfile", result: ValidationResult) -> None:
    """Validate output_dir is writable."""
    output_dir = profile.output_dir

    if output_dir.exists():
        # Check if writable
        if not _is_writable(output_dir):
            result.add_error(
                field="output_dir",
                profile=profile_name,
                message=f"Output directory is not writable: {output_dir}",
            )
    else:
        # Check if parent exists and is writable (so we can create the dir)
        parent = output_dir.parent
        if parent.exists():
            if not _is_writable(parent):
                result.add_error(
                    field="output_dir",
                    profile=profile_name,
                    message=f"Cannot create output directory, parent not writable: {parent}",
                )
            else:
                result.add_warning(
                    field="output_dir",
                    profile=profile_name,
                    message=f"Output directory does not exist and will be created: {output_dir}",
                )
        else:
            result.add_error(
                field="output_dir",
                profile=profile_name,
                message=f"Output directory parent does not exist: {parent}",
                suggestion="Create the parent directory first",
            )


def _validate_printers(profile_name: str, profile: "OutputProfile", result: ValidationResult) -> None:
    """Validate configured printers exist on the system."""
    if not profile.print.enabled:
        return

    if not profile.print.targets:
        return

    try:
        from pdfmill.printer import list_printers

        available_printers = list_printers()
    except Exception as e:
        result.add_warning(
            field="print",
            profile=profile_name,
            message=f"Could not enumerate printers: {e}",
            suggestion="Printer validation skipped. Verify printers manually.",
        )
        return

    for target_name, target in profile.print.targets.items():
        if target.printer and target.printer not in available_printers:
            # Try case-insensitive match
            matches = [p for p in available_printers if p.lower() == target.printer.lower()]
            if matches:
                result.add_warning(
                    field=f"print.targets.{target_name}.printer",
                    profile=profile_name,
                    message=f"Printer name case mismatch: '{target.printer}'",
                    suggestion=f"Did you mean '{matches[0]}'?",
                )
            else:
                # Build suggestion with available printers
                if available_printers:
                    printer_list = ", ".join(available_printers[:5])
                    if len(available_printers) > 5:
                        printer_list += "..."
                    suggestion = f"Available printers: {printer_list}"
                else:
                    suggestion = "No printers found on the system"

                result.add_error(
                    field=f"print.targets.{target_name}.printer",
                    profile=profile_name,
                    message=f"Printer not found: '{target.printer}'",
                    suggestion=suggestion,
                )


def _is_writable(path: Path) -> bool:
    """Check if a path is writable."""
    return os.access(path, os.W_OK)
