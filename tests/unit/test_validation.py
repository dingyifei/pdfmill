"""Tests for pdfmill.validation module."""

import pytest
from pathlib import Path
from unittest.mock import patch

from pdfmill.validation import (
    validate_strict,
    ValidationResult,
    ValidationIssue,
)
from pdfmill.config import (
    Config,
    InputConfig,
    OutputProfile,
    PrintConfig,
    PrintTarget,
)


class TestValidationIssue:
    """Test ValidationIssue dataclass."""

    def test_str_with_profile(self):
        issue = ValidationIssue(
            level="error",
            profile="label",
            field="output_dir",
            message="Directory not writable",
        )
        s = str(issue)
        assert "[ERROR]" in s
        assert "label" in s
        assert "output_dir" in s
        assert "Directory not writable" in s

    def test_str_without_profile(self):
        issue = ValidationIssue(
            level="warning",
            profile=None,
            field="input.path",
            message="Path does not exist",
        )
        s = str(issue)
        assert "[WARNING]" in s
        assert "input.path" in s
        assert "Path does not exist" in s

    def test_str_with_suggestion(self):
        issue = ValidationIssue(
            level="error",
            profile=None,
            field="input.path",
            message="Path does not exist",
            suggestion="Create the directory",
        )
        s = str(issue)
        assert "Suggestion:" in s
        assert "Create the directory" in s


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_empty_result(self):
        result = ValidationResult()
        assert not result.has_errors
        assert not result.has_warnings
        assert len(result.issues) == 0

    def test_add_error(self):
        result = ValidationResult()
        result.add_error("field", "message")
        assert result.has_errors
        assert not result.has_warnings
        assert len(result.issues) == 1
        assert result.issues[0].level == "error"

    def test_add_warning(self):
        result = ValidationResult()
        result.add_warning("field", "message")
        assert not result.has_errors
        assert result.has_warnings
        assert len(result.issues) == 1
        assert result.issues[0].level == "warning"

    def test_mixed_issues(self):
        result = ValidationResult()
        result.add_error("field1", "error message")
        result.add_warning("field2", "warning message")
        assert result.has_errors
        assert result.has_warnings
        assert len(result.issues) == 2


class TestValidateStrictInputPath:
    """Test strict validation of input.path."""

    def test_valid_input_directory(self, tmp_path):
        """Test validation passes for existing input directory."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={"test": OutputProfile(pages="all", output_dir=tmp_path / "output")},
        )

        result = validate_strict(config)
        # Should have no errors for input path
        input_errors = [i for i in result.issues if "input.path" in i.field and i.level == "error"]
        assert len(input_errors) == 0

    def test_valid_input_file(self, tmp_path):
        """Test validation passes for existing input file."""
        input_file = tmp_path / "test.pdf"
        input_file.write_bytes(b"fake pdf")

        config = Config(
            input=InputConfig(path=input_file),
            outputs={"test": OutputProfile(pages="all", output_dir=tmp_path / "output")},
        )

        result = validate_strict(config)
        input_errors = [i for i in result.issues if "input.path" in i.field and i.level == "error"]
        assert len(input_errors) == 0

    def test_missing_input_path(self, tmp_path):
        """Test validation fails for non-existent input path."""
        config = Config(
            input=InputConfig(path=tmp_path / "nonexistent"),
            outputs={"test": OutputProfile(pages="all")},
        )

        result = validate_strict(config)
        assert result.has_errors
        assert any("input.path" in str(i) and "does not exist" in str(i) for i in result.issues)


class TestValidateStrictOutputDir:
    """Test strict validation of output_dir."""

    def test_existing_writable_output_dir(self, tmp_path):
        """Test validation passes for existing writable output directory."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={"test": OutputProfile(pages="all", output_dir=output_dir)},
        )

        result = validate_strict(config)
        output_errors = [i for i in result.issues if "output_dir" in i.field and i.level == "error"]
        assert len(output_errors) == 0

    def test_nonexistent_output_dir_with_writable_parent(self, tmp_path):
        """Test validation warns for non-existent output dir with writable parent."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={"test": OutputProfile(pages="all", output_dir=tmp_path / "new_output")},
        )

        result = validate_strict(config)
        # Should have warning, not error
        output_warnings = [i for i in result.issues if "output_dir" in i.field and i.level == "warning"]
        output_errors = [i for i in result.issues if "output_dir" in i.field and i.level == "error"]
        assert len(output_warnings) == 1
        assert len(output_errors) == 0
        assert "will be created" in str(output_warnings[0])

    def test_nonexistent_output_dir_parent(self, tmp_path):
        """Test validation fails when output dir parent doesn't exist."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={"test": OutputProfile(pages="all", output_dir=tmp_path / "no_parent" / "output")},
        )

        result = validate_strict(config)
        output_errors = [i for i in result.issues if "output_dir" in i.field and i.level == "error"]
        assert len(output_errors) == 1
        assert "parent does not exist" in str(output_errors[0])


class TestValidateStrictPrinters:
    """Test strict validation of printer configuration."""

    def test_disabled_print_skips_validation(self, tmp_path):
        """Test that disabled print config skips printer validation."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={
                "test": OutputProfile(
                    pages="all",
                    output_dir=tmp_path,
                    print=PrintConfig(
                        enabled=False,
                        targets={"default": PrintTarget(printer="NonExistent")},
                    ),
                )
            },
        )

        with patch("pdfmill.printer.list_printers", return_value=[]):
            result = validate_strict(config)

        # Should have no printer-related errors
        printer_errors = [i for i in result.issues if "printer" in i.field.lower()]
        assert len(printer_errors) == 0

    def test_valid_printer(self, tmp_path):
        """Test validation passes for existing printer."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={
                "test": OutputProfile(
                    pages="all",
                    output_dir=tmp_path,
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="HP LaserJet")},
                    ),
                )
            },
        )

        with patch("pdfmill.printer.list_printers", return_value=["HP LaserJet", "Brother"]):
            result = validate_strict(config)

        printer_errors = [i for i in result.issues if "printer" in i.field.lower() and i.level == "error"]
        assert len(printer_errors) == 0

    def test_printer_not_found(self, tmp_path):
        """Test validation fails for non-existent printer."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={
                "test": OutputProfile(
                    pages="all",
                    output_dir=tmp_path,
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="NonExistent")},
                    ),
                )
            },
        )

        with patch("pdfmill.printer.list_printers", return_value=["HP LaserJet", "Brother"]):
            result = validate_strict(config)

        assert result.has_errors
        printer_errors = [i for i in result.issues if "printer" in i.field.lower() and i.level == "error"]
        assert len(printer_errors) == 1
        assert "NonExistent" in str(printer_errors[0])

    def test_printer_case_mismatch(self, tmp_path):
        """Test validation warns for printer name case mismatch."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={
                "test": OutputProfile(
                    pages="all",
                    output_dir=tmp_path,
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="hp laserjet")},
                    ),
                )
            },
        )

        with patch("pdfmill.printer.list_printers", return_value=["HP LaserJet"]):
            result = validate_strict(config)

        # Should have warning for case mismatch, not error
        printer_warnings = [i for i in result.issues if "printer" in i.field.lower() and i.level == "warning"]
        assert len(printer_warnings) == 1
        assert "case mismatch" in str(printer_warnings[0]).lower()
        assert "HP LaserJet" in str(printer_warnings[0])

    def test_printer_enumeration_failure(self, tmp_path):
        """Test validation warns when printer enumeration fails."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={
                "test": OutputProfile(
                    pages="all",
                    output_dir=tmp_path,
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="SomePrinter")},
                    ),
                )
            },
        )

        with patch("pdfmill.printer.list_printers", side_effect=Exception("win32print not available")):
            result = validate_strict(config)

        # Should have warning about enumeration failure
        enum_warnings = [i for i in result.issues if "enumerate" in str(i).lower()]
        assert len(enum_warnings) == 1


class TestValidateStrictDisabledProfiles:
    """Test that disabled profiles are skipped."""

    def test_disabled_profile_skipped(self, tmp_path):
        """Test that disabled profiles skip validation."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config = Config(
            input=InputConfig(path=input_dir),
            outputs={
                "disabled": OutputProfile(
                    pages="all",
                    enabled=False,
                    output_dir=tmp_path / "nonexistent_parent" / "output",
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="NonExistent")},
                    ),
                )
            },
        )

        with patch("pdfmill.printer.list_printers", return_value=[]):
            result = validate_strict(config)

        # Should have no errors because profile is disabled
        assert not result.has_errors
