"""Integration tests for pdfmill CLI."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


@pytest.mark.integration
class TestCLIIntegration:
    """Test CLI as subprocess."""

    def test_help_flag(self):
        """Test --help displays usage."""
        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "pdfp" in result.stdout or "usage" in result.stdout.lower()

    def test_version_flag(self):
        """Test --version displays version info."""
        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "pdfmill" in result.stdout

    def test_validate_valid_config(self, temp_dir, minimal_config_dict):
        """Test --validate with valid config."""
        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(minimal_config_dict, f)

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path), "--validate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_validate_invalid_config(self, temp_dir):
        """Test --validate with invalid config."""
        config_path = temp_dir / "bad.yaml"
        config_path.write_text("version: 1\n# missing outputs")

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path), "--validate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_validate_missing_config(self, temp_dir):
        """Test --validate with non-existent config."""
        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(temp_dir / "nonexistent.yaml"), "--validate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_dry_run(self, temp_dir, minimal_config_dict, temp_pdf):
        """Test --dry-run processing."""
        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(minimal_config_dict, f)

        output_dir = temp_dir / "output"

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path),
             "--input", str(temp_pdf),
             "--output", str(output_dir),
             "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "dry-run" in result.stdout.lower()

        # No actual output should be created
        if output_dir.exists():
            assert len(list(output_dir.glob("*.pdf"))) == 0

    def test_full_processing(self, temp_dir, minimal_config_dict, temp_multi_page_pdf):
        """Test full PDF processing via CLI."""
        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(minimal_config_dict, f)

        output_dir = temp_dir / "output"

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path),
             "--input", str(temp_multi_page_pdf),
             "--output", str(output_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Output should be created
        assert output_dir.exists()
        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

    def test_no_input_error(self, temp_dir, minimal_config_dict):
        """Test error when --input is missing."""
        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(minimal_config_dict, f)

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "input" in result.stderr.lower()


@pytest.mark.integration
class TestCLIWithConfigProfiles:
    """Test CLI with different config profile setups."""

    def test_multiple_profiles(self, temp_dir, temp_multi_page_pdf):
        """Test processing with multiple output profiles."""
        config_dict = {
            "version": 1,
            "outputs": {
                "first": {"pages": "first"},
                "last": {"pages": "last"},
            }
        }
        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        output_dir = temp_dir / "output"

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path),
             "--input", str(temp_multi_page_pdf),
             "--output", str(output_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 2

    def test_profile_with_transforms(self, temp_dir, temp_pdf):
        """Test processing with transforms defined in config."""
        config_dict = {
            "version": 1,
            "outputs": {
                "rotated": {
                    "pages": "all",
                    "transforms": [
                        {"rotate": 90}
                    ]
                }
            }
        }
        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        output_dir = temp_dir / "output"

        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli",
             "--config", str(config_path),
             "--input", str(temp_pdf),
             "--output", str(output_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1


@pytest.mark.integration
@pytest.mark.windows
class TestCLIPrinterCommands:
    """Test printer-related CLI commands (Windows only)."""

    def test_list_printers(self):
        """Test --list-printers command."""
        result = subprocess.run(
            [sys.executable, "-m", "pdfmill.cli", "--list-printers"],
            capture_output=True,
            text=True,
        )
        # May succeed or fail depending on platform
        # Just verify it doesn't crash unexpectedly
        assert result.returncode in (0, 1)
