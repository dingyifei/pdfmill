"""Configuration validation for pdfmill.

Provides comprehensive validation of configuration before processing,
catching errors early rather than during pipeline execution.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pdfmill.constants import SORT_OPTIONS, TRANSFORM_TYPES, FIT_MODES, MATCH_MODES
from pdfmill.exceptions import ConfigError

if TYPE_CHECKING:
    from pdfmill.config import Config


@dataclass
class ValidationResult:
    """Result of configuration validation.

    Attributes:
        valid: True if no errors were found
        errors: List of error messages (fatal issues)
        warnings: List of warning messages (non-fatal issues)
    """

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error and mark result as invalid."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning (does not affect validity)."""
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False


@dataclass
class ValidationContext:
    """Optional context for operational validation.

    Provides runtime information for validating that resources
    (files, printers) actually exist and are accessible.
    """

    input_path: Path | None = None
    """Path to validate input files exist."""

    available_printers: list[str] | None = None
    """List of available printers for validation."""

    check_paths: bool = True
    """Whether to validate file/directory paths exist."""

    check_printers: bool = False
    """Whether to validate printer names exist."""


class ConfigValidator:
    """Comprehensive configuration validator.

    Performs three phases of validation:
    1. Structural: Required fields, valid types
    2. Semantic: Logical consistency (sort conflicts, valid values)
    3. Operational: Resources exist (paths, printers) - optional

    Example:
        validator = ConfigValidator()
        result = validator.validate(config)
        if not result.valid:
            for error in result.errors:
                print(f"Error: {error}")
    """

    def validate(
        self,
        config: "Config",
        context: ValidationContext | None = None,
    ) -> ValidationResult:
        """Validate a configuration.

        Args:
            config: Configuration to validate
            context: Optional context for operational validation

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Phase 1: Structural validation
        result.merge(self._validate_structure(config))

        # Phase 2: Semantic validation
        result.merge(self._validate_semantics(config))

        # Phase 3: Operational validation (if context provided)
        if context:
            result.merge(self._validate_operational(config, context))

        return result

    def validate_or_raise(
        self,
        config: "Config",
        context: ValidationContext | None = None,
    ) -> None:
        """Validate configuration and raise ConfigError if invalid.

        Args:
            config: Configuration to validate
            context: Optional context for operational validation

        Raises:
            ConfigError: If validation fails
        """
        result = self.validate(config, context)
        if not result.valid:
            error_text = "; ".join(result.errors)
            raise ConfigError(f"Configuration validation failed: {error_text}")

    def _validate_structure(self, config: "Config") -> ValidationResult:
        """Validate structural requirements."""
        result = ValidationResult()

        # Must have at least one output profile
        if not config.outputs:
            result.add_error("At least one output profile is required")

        # Validate each output profile
        for name, profile in config.outputs.items():
            # Pages field is required (already enforced by parser, but double-check)
            if not profile.pages:
                result.add_error(f"Profile '{name}': 'pages' field is required")

            # Validate transforms have correct types
            for i, transform in enumerate(profile.transforms):
                if transform.type not in TRANSFORM_TYPES:
                    result.add_error(
                        f"Profile '{name}' transform {i + 1}: "
                        f"unknown type '{transform.type}'. "
                        f"Valid types: {', '.join(TRANSFORM_TYPES)}"
                    )

        return result

    def _validate_semantics(self, config: "Config") -> ValidationResult:
        """Validate semantic consistency."""
        result = ValidationResult()

        # Validate input sort option
        if config.input.sort and config.input.sort not in SORT_OPTIONS:
            result.add_error(
                f"Invalid input sort option: '{config.input.sort}'. "
                f"Valid options: {', '.join(SORT_OPTIONS)}"
            )

        # Validate filter match mode
        if config.input.filter and config.input.filter.match not in MATCH_MODES:
            result.add_error(
                f"Invalid filter match mode: '{config.input.filter.match}'. "
                f"Valid modes: {', '.join(MATCH_MODES)}"
            )

        # Check each profile
        for name, profile in config.outputs.items():
            # Sort conflict: can't have sort in both input and profile
            if config.input.sort and profile.sort:
                result.add_error(
                    f"Sort specified in both input ('{config.input.sort}') "
                    f"and profile '{name}' ('{profile.sort}'). "
                    f"Use only one location."
                )

            # Validate profile sort option
            if profile.sort and profile.sort not in SORT_OPTIONS:
                result.add_error(
                    f"Profile '{name}': invalid sort option '{profile.sort}'. "
                    f"Valid options: {', '.join(SORT_OPTIONS)}"
                )

            # Validate transforms
            for i, transform in enumerate(profile.transforms):
                result.merge(self._validate_transform(name, i, transform))

            # Validate print targets
            if profile.print.enabled:
                for target_name, target in profile.print.targets.items():
                    if target.weight < 0:
                        result.add_error(
                            f"Profile '{name}' target '{target_name}': "
                            f"weight must be non-negative"
                        )
                    if target.copies < 1:
                        result.add_error(
                            f"Profile '{name}' target '{target_name}': "
                            f"copies must be at least 1"
                        )

        return result

    def _validate_transform(
        self,
        profile_name: str,
        index: int,
        transform,
    ) -> ValidationResult:
        """Validate a single transform."""
        result = ValidationResult()
        prefix = f"Profile '{profile_name}' transform {index + 1}"

        if transform.type == "rotate" and transform.rotate:
            angle = transform.rotate.angle
            if isinstance(angle, int) and angle not in (0, 90, 180, 270):
                result.add_error(
                    f"{prefix}: rotation angle must be 0, 90, 180, or 270, "
                    f"got {angle}"
                )
            elif isinstance(angle, str):
                valid_orientations = ("landscape", "portrait", "auto")
                if angle.lower() not in valid_orientations:
                    result.add_error(
                        f"{prefix}: rotation must be a valid angle or "
                        f"one of {valid_orientations}, got '{angle}'"
                    )

        elif transform.type == "crop" and transform.crop:
            crop = transform.crop
            # Validate crop coordinates are sensible
            # Note: Actual numeric validation happens at runtime since
            # values can be strings like "100mm"

        elif transform.type == "size" and transform.size:
            size = transform.size
            if size.fit not in FIT_MODES:
                result.add_error(
                    f"{prefix}: invalid fit mode '{size.fit}'. "
                    f"Valid modes: {', '.join(FIT_MODES)}"
                )

        return result

    def _validate_operational(
        self,
        config: "Config",
        context: ValidationContext,
    ) -> ValidationResult:
        """Validate that resources exist and are accessible."""
        result = ValidationResult()

        # Check input path exists
        if context.check_paths and context.input_path:
            if not context.input_path.exists():
                result.add_warning(
                    f"Input path does not exist: {context.input_path}"
                )
            elif context.input_path.is_dir():
                # Check if there are any matching files
                files = list(context.input_path.glob(config.input.pattern))
                if not files:
                    result.add_warning(
                        f"No files matching '{config.input.pattern}' "
                        f"in {context.input_path}"
                    )

        # Check output directories are writable
        if context.check_paths:
            for name, profile in config.outputs.items():
                output_dir = profile.output_dir
                if output_dir.exists() and not output_dir.is_dir():
                    result.add_error(
                        f"Profile '{name}': output path exists but is not a directory: "
                        f"{output_dir}"
                    )

        # Check printer names exist
        if context.check_printers and context.available_printers is not None:
            for name, profile in config.outputs.items():
                if profile.print.enabled:
                    for target_name, target in profile.print.targets.items():
                        if target.printer and target.printer not in context.available_printers:
                            result.add_warning(
                                f"Profile '{name}' target '{target_name}': "
                                f"printer '{target.printer}' not found. "
                                f"Available: {', '.join(context.available_printers)}"
                            )

        return result


# Module-level convenience function
def validate_config(
    config: "Config",
    context: ValidationContext | None = None,
) -> ValidationResult:
    """Validate a configuration.

    Convenience function that creates a ConfigValidator and validates.

    Args:
        config: Configuration to validate
        context: Optional context for operational validation

    Returns:
        ValidationResult with errors and warnings
    """
    validator = ConfigValidator()
    return validator.validate(config, context)
