"""Tests for pdfmill.cli module."""

import logging
from pathlib import Path
from unittest.mock import patch

from pdfmill.cli import cmd_install, cmd_list_printers, cmd_uninstall, create_parser, main, show_version
from pdfmill.logging_config import setup_logging


class TestCreateParser:
    """Test argument parser creation."""

    def test_parser_creation(self):
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "pdfm"

    def test_version_flag(self):
        parser = create_parser()
        args = parser.parse_args(["-V"])
        assert args.version is True

    def test_version_long_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_config_flag(self):
        parser = create_parser()
        args = parser.parse_args(["-c", "test.yaml"])
        assert str(args.config) == "test.yaml"

    def test_config_long_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--config", "test.yaml"])
        assert args.config == Path("test.yaml")

    def test_input_flag(self):
        parser = create_parser()
        args = parser.parse_args(["-i", "./input"])
        assert args.input == Path("./input")

    def test_output_flag(self):
        parser = create_parser()
        args = parser.parse_args(["-o", "./output"])
        assert args.output == Path("./output")

    def test_validate_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--validate"])
        assert args.validate is True

    def test_dry_run_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_list_printers_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--list-printers"])
        assert args.list_printers is True

    def test_install_command(self):
        parser = create_parser()
        args = parser.parse_args(["install"])
        assert args.command == "install"

    def test_uninstall_command(self):
        parser = create_parser()
        args = parser.parse_args(["uninstall"])
        assert args.command == "uninstall"

    def test_install_force_flag(self):
        parser = create_parser()
        args = parser.parse_args(["install", "--force"])
        assert args.command == "install"
        assert args.force is True


class TestShowVersion:
    """Test version display."""

    def test_shows_version(self, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.get_sumatra_status") as mock_status:
                mock_status.return_value = {"installed": False, "path": None, "version": None}
                show_version()

        assert "pdfmill" in caplog.text

    def test_shows_sumatra_installed(self, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.get_sumatra_status") as mock_status:
                mock_status.return_value = {"installed": True, "path": "/path/to/SumatraPDF.exe", "version": "3.5.2"}
                show_version()

        assert "SumatraPDF" in caplog.text
        assert "3.5.2" in caplog.text

    def test_shows_sumatra_not_installed(self, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.get_sumatra_status") as mock_status:
                mock_status.return_value = {"installed": False, "path": None, "version": None}
                show_version()

        assert "not installed" in caplog.text


class TestCmdInstall:
    """Test install command."""

    def test_install_success(self):
        with patch("pdfmill.printer.download_sumatra") as mock_download:
            mock_download.return_value = Path("SumatraPDF.exe")
            result = cmd_install()

        assert result == 0

    def test_install_with_force(self):
        with patch("pdfmill.printer.download_sumatra") as mock_download:
            mock_download.return_value = Path("SumatraPDF.exe")
            result = cmd_install(force=True)

        mock_download.assert_called_once_with(force=True)
        assert result == 0

    def test_install_error(self):
        from pdfmill.printer import PrinterError

        with patch("pdfmill.printer.download_sumatra") as mock_download:
            mock_download.side_effect = PrinterError("Download failed")
            result = cmd_install()

        assert result == 1


class TestCmdUninstall:
    """Test uninstall command."""

    def test_uninstall_success(self):
        with patch("pdfmill.printer.remove_sumatra") as mock_remove:
            mock_remove.return_value = True
            result = cmd_uninstall()

        assert result == 0

    def test_uninstall_not_found(self):
        with patch("pdfmill.printer.remove_sumatra") as mock_remove:
            mock_remove.return_value = False
            result = cmd_uninstall()

        assert result == 1


class TestCmdListPrinters:
    """Test list printers command."""

    def test_list_printers_success(self, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.list_printers") as mock_list:
                mock_list.return_value = ["Printer 1", "Printer 2"]
                result = cmd_list_printers()

        assert result == 0
        assert "Printer 1" in caplog.text
        assert "Printer 2" in caplog.text

    def test_list_printers_empty(self, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.list_printers") as mock_list:
                mock_list.return_value = []
                result = cmd_list_printers()

        assert result == 1
        assert "No printers found" in caplog.text

    def test_list_printers_error(self, caplog):
        from pdfmill.printer import PrinterError

        with caplog.at_level(logging.ERROR, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.list_printers") as mock_list:
                mock_list.side_effect = PrinterError("win32print not available")
                result = cmd_list_printers()

        assert result == 1


class TestMain:
    """Test main CLI entry point."""

    def test_version_returns_0(self):
        with patch("pdfmill.cli.show_version") as mock_show:
            result = main(["--version"])

        assert result == 0
        mock_show.assert_called_once()

    def test_list_printers_returns_result(self):
        with patch("pdfmill.cli.cmd_list_printers", return_value=0) as mock_cmd:
            result = main(["--list-printers"])

        assert result == 0
        mock_cmd.assert_called_once()

    def test_install_command(self):
        with patch("pdfmill.cli.cmd_install", return_value=0) as mock_cmd:
            result = main(["install"])

        assert result == 0
        mock_cmd.assert_called_once_with(force=False)

    def test_install_force(self):
        with patch("pdfmill.cli.cmd_install", return_value=0) as mock_cmd:
            main(["install", "--force"])

        mock_cmd.assert_called_once_with(force=True)

    def test_uninstall_command(self):
        with patch("pdfmill.cli.cmd_uninstall", return_value=0) as mock_cmd:
            main(["uninstall"])

        mock_cmd.assert_called_once()

    def test_no_args_prints_help(self, capsys):
        result = main([])

        assert result == 1
        captured = capsys.readouterr()
        # Should print help
        assert "pdfm" in captured.out or "usage" in captured.out.lower()

    def test_validate_valid_config(self, temp_config_file, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            result = main(["--config", str(temp_config_file), "--validate"])

        assert result == 0
        assert "valid" in caplog.text.lower()

    def test_validate_missing_config(self, temp_dir, capsys):
        result = main(["--config", str(temp_dir / "missing.yaml"), "--validate"])

        assert result == 1

    def test_validate_invalid_config(self, temp_dir, capsys):
        # Create invalid config
        bad_config = temp_dir / "bad.yaml"
        bad_config.write_text("version: 1\n# no outputs")

        result = main(["--config", str(bad_config), "--validate"])

        assert result == 1

    def test_config_without_input_errors(self, temp_config_file, capsys):
        result = main(["--config", str(temp_config_file)])

        assert result == 1
        captured = capsys.readouterr()
        assert "input" in captured.err.lower()

    def test_full_process(self, temp_config_file, temp_pdf, temp_dir):
        with patch("pdfmill.processor.process") as mock_process:
            result = main(
                [
                    "--config",
                    str(temp_config_file),
                    "--input",
                    str(temp_pdf),
                    "--output",
                    str(temp_dir),
                ]
            )

        assert result == 0
        mock_process.assert_called_once()

    def test_dry_run_passed(self, temp_config_file, temp_pdf, temp_dir):
        with patch("pdfmill.processor.process") as mock_process:
            main(
                [
                    "--config",
                    str(temp_config_file),
                    "--input",
                    str(temp_pdf),
                    "--output",
                    str(temp_dir),
                    "--dry-run",
                ]
            )

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["dry_run"] is True

    def test_output_dir_passed(self, temp_config_file, temp_pdf, temp_dir):
        output_dir = temp_dir / "custom_output"

        with patch("pdfmill.processor.process") as mock_process:
            main(
                [
                    "--config",
                    str(temp_config_file),
                    "--input",
                    str(temp_pdf),
                    "--output",
                    str(output_dir),
                ]
            )

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["output_dir"] == output_dir

    def test_process_error_returns_1(self, temp_config_file, temp_pdf, temp_dir):
        with patch("pdfmill.processor.process") as mock_process:
            mock_process.side_effect = Exception("Processing failed")
            result = main(
                [
                    "--config",
                    str(temp_config_file),
                    "--input",
                    str(temp_pdf),
                    "--output",
                    str(temp_dir),
                ]
            )

        assert result == 1

    def test_config_error_returns_1(self, temp_dir, capsys):
        bad_config = temp_dir / "bad.yaml"
        bad_config.write_text("{{invalid yaml")

        result = main(
            [
                "--config",
                str(bad_config),
                "--input",
                str(temp_dir),
            ]
        )

        assert result == 1


class TestStrictValidation:
    """Test --validate --strict mode."""

    def test_strict_flag_parsed(self):
        parser = create_parser()
        args = parser.parse_args(["--validate", "--strict"])
        assert args.validate is True
        assert args.strict is True

    def test_strict_validation_success(self, tmp_path, caplog):
        """Test --strict passes when all resources exist."""
        # Create input directory
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create valid config
        config_content = f"""
version: 1
input:
  path: {input_dir}
outputs:
  test:
    pages: all
    output_dir: {tmp_path / "output"}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with caplog.at_level(logging.INFO, logger="pdfmill"):
            result = main(
                [
                    "--config",
                    str(config_file),
                    "--validate",
                    "--strict",
                ]
            )

        assert result == 0
        assert "Strict validation" in caplog.text

    def test_strict_validation_missing_input_path(self, tmp_path, caplog):
        """Test --strict fails when input path doesn't exist."""
        config_content = f"""
version: 1
input:
  path: {tmp_path / "nonexistent"}
outputs:
  test:
    pages: all
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with caplog.at_level(logging.DEBUG, logger="pdfmill"):
            result = main(
                [
                    "--config",
                    str(config_file),
                    "--validate",
                    "--strict",
                ]
            )

        assert result == 1
        assert "input.path" in caplog.text
        assert "does not exist" in caplog.text

    def test_strict_validation_printer_not_found(self, tmp_path, caplog):
        """Test --strict fails when printer doesn't exist."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        config_content = f"""
version: 1
input:
  path: {input_dir}
outputs:
  test:
    pages: all
    output_dir: {tmp_path}
    print:
      enabled: true
      printer: NonExistentPrinter12345
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with caplog.at_level(logging.DEBUG, logger="pdfmill"):
            result = main(
                [
                    "--config",
                    str(config_file),
                    "--validate",
                    "--strict",
                ]
            )

        assert result == 1
        assert "NonExistentPrinter12345" in caplog.text

    def test_validate_without_strict(self, tmp_path, caplog):
        """Test --validate without --strict doesn't check external resources."""
        config_content = f"""
version: 1
input:
  path: {tmp_path / "nonexistent"}
outputs:
  test:
    pages: all
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with caplog.at_level(logging.INFO, logger="pdfmill"):
            result = main(
                [
                    "--config",
                    str(config_file),
                    "--validate",
                ]
            )

        # Should pass - we're only validating syntax, not strict checking
        assert result == 0
        assert "Strict validation" not in caplog.text

    def test_invalid_page_spec_fails_validate(self, tmp_path, capsys):
        """Test that invalid page spec syntax fails --validate."""
        config_content = """
version: 1
outputs:
  test:
    pages: "invalid-spec-abc"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        result = main(
            [
                "--config",
                str(config_file),
                "--validate",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "pages" in captured.err.lower() or "Unknown" in captured.err
