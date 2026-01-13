"""Tests for pdfmill.printer module."""

import logging
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

from pdfmill.logging_config import setup_logging
from pdfmill.printer import (
    get_architecture,
    get_cache_dir,
    get_sumatra_cache_path,
    get_sumatra_download_url,
    download_sumatra,
    remove_sumatra,
    get_sumatra_status,
    list_printers,
    find_sumatra_pdf,
    print_pdf,
    PrinterError,
    SUMATRA_VERSION,
    SUMATRA_URLS,
)


class TestGetArchitecture:
    """Test architecture detection."""

    def test_amd64(self):
        with patch("platform.machine", return_value="AMD64"):
            assert get_architecture() == "x64"

    def test_x86_64(self):
        with patch("platform.machine", return_value="x86_64"):
            assert get_architecture() == "x64"

    def test_arm64(self):
        with patch("platform.machine", return_value="arm64"):
            assert get_architecture() == "arm64"

    def test_aarch64(self):
        with patch("platform.machine", return_value="aarch64"):
            assert get_architecture() == "arm64"

    def test_i386(self):
        with patch("platform.machine", return_value="i386"):
            assert get_architecture() == "x86"

    def test_i686(self):
        with patch("platform.machine", return_value="i686"):
            assert get_architecture() == "x86"

    def test_unknown_defaults_to_x86(self):
        with patch("platform.machine", return_value="unknown_arch"):
            assert get_architecture() == "x86"


class TestGetCacheDir:
    """Test cache directory resolution."""

    def test_windows_localappdata(self, temp_dir):
        with patch("sys.platform", "win32"):
            with patch.dict("os.environ", {"LOCALAPPDATA": str(temp_dir)}):
                cache_dir = get_cache_dir()
                assert "pdfmill" in str(cache_dir)

    def test_linux_xdg_cache(self, temp_dir):
        with patch("sys.platform", "linux"):
            with patch.dict("os.environ", {"XDG_CACHE_HOME": str(temp_dir)}):
                cache_dir = get_cache_dir()
                assert "pdfmill" in str(cache_dir)


class TestGetSumatraCachePath:
    """Test SumatraPDF cache path."""

    def test_returns_path_with_exe(self):
        with patch("pdfmill.printer.get_cache_dir") as mock_cache:
            mock_cache.return_value = Path("/cache/pdfmill")
            path = get_sumatra_cache_path()
            assert path == Path("/cache/pdfmill/SumatraPDF.exe")


class TestGetSumatraDownloadUrl:
    """Test download URL generation."""

    def test_x64_url(self):
        with patch("pdfmill.printer.get_architecture", return_value="x64"):
            url = get_sumatra_download_url()
            assert SUMATRA_VERSION in url
            assert "64" in url

    def test_arm64_url(self):
        with patch("pdfmill.printer.get_architecture", return_value="arm64"):
            url = get_sumatra_download_url()
            assert "arm64" in url

    def test_x86_url(self):
        with patch("pdfmill.printer.get_architecture", return_value="x86"):
            url = get_sumatra_download_url()
            assert url == SUMATRA_URLS["x86"]


class TestDownloadSumatra:
    """Test SumatraPDF download."""

    def test_not_windows_raises(self):
        with patch("sys.platform", "linux"):
            with pytest.raises(PrinterError, match="Windows"):
                download_sumatra()

    def test_already_exists_no_force(self, temp_dir):
        existing = temp_dir / "SumatraPDF.exe"
        existing.touch()

        with patch("sys.platform", "win32"):
            with patch("pdfmill.printer.get_sumatra_cache_path", return_value=existing):
                result = download_sumatra(force=False)
                assert result == existing

    def test_force_redownloads(self, temp_dir):
        existing = temp_dir / "SumatraPDF.exe"
        existing.touch()

        with patch("sys.platform", "win32"):
            with patch("pdfmill.printer.get_sumatra_cache_path", return_value=existing):
                with patch("urllib.request.urlretrieve") as mock_download:
                    result = download_sumatra(force=True)
                    mock_download.assert_called_once()


class TestRemoveSumatra:
    """Test SumatraPDF removal."""

    def test_removes_existing_file(self, temp_dir):
        existing = temp_dir / "SumatraPDF.exe"
        existing.touch()

        with patch("pdfmill.printer.get_sumatra_cache_path", return_value=existing):
            with patch("pdfmill.printer.get_cache_dir", return_value=temp_dir):
                result = remove_sumatra()
                assert result is True
                assert not existing.exists()

    def test_not_found_returns_false(self, temp_dir):
        nonexistent = temp_dir / "SumatraPDF.exe"

        with patch("pdfmill.printer.get_sumatra_cache_path", return_value=nonexistent):
            result = remove_sumatra()
            assert result is False


class TestGetSumatraStatus:
    """Test status reporting."""

    def test_installed(self, temp_dir):
        exe_path = temp_dir / "SumatraPDF.exe"
        exe_path.touch()

        with patch("pdfmill.printer.find_sumatra_pdf", return_value=exe_path):
            status = get_sumatra_status()
            assert status["installed"] is True
            assert status["path"] == str(exe_path)
            assert status["version"] == SUMATRA_VERSION

    def test_not_installed(self):
        with patch("pdfmill.printer.find_sumatra_pdf", return_value=None):
            status = get_sumatra_status()
            assert status["installed"] is False
            assert status["path"] is None
            assert status["version"] is None


class TestListPrinters:
    """Test printer enumeration."""

    def test_list_printers_success(self):
        mock_win32print = MagicMock()
        mock_win32print.PRINTER_ENUM_LOCAL = 2
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 4
        mock_win32print.EnumPrinters.return_value = [
            (0, "", "Printer 1", ""),
            (0, "", "Printer 2", ""),
            (0, "", "Label Printer", ""),
        ]
        with patch.dict("sys.modules", {"win32print": mock_win32print}):
            printers = list_printers()
            assert printers == ["Printer 1", "Printer 2", "Label Printer"]

    def test_list_printers_empty(self):
        mock_win32print = MagicMock()
        mock_win32print.PRINTER_ENUM_LOCAL = 2
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 4
        mock_win32print.EnumPrinters.return_value = []
        with patch.dict("sys.modules", {"win32print": mock_win32print}):
            printers = list_printers()
            assert printers == []


class TestFindSumatraPdf:
    """Test SumatraPDF discovery."""

    def test_env_var_path(self, temp_dir):
        sumatra_path = temp_dir / "SumatraPDF.exe"
        sumatra_path.touch()

        with patch.dict("os.environ", {"PDFPIPE_SUMATRA_PATH": str(sumatra_path)}):
            result = find_sumatra_pdf(auto_download=False)
            assert result == sumatra_path

    def test_env_var_path_not_exists(self, temp_dir):
        nonexistent = temp_dir / "nonexistent.exe"

        with patch.dict("os.environ", {"PDFPIPE_SUMATRA_PATH": str(nonexistent)}):
            with patch("pdfmill.printer.get_sumatra_cache_path") as mock_cache:
                mock_cache.return_value = temp_dir / "cached.exe"
                result = find_sumatra_pdf(auto_download=False)
                assert result is None

    def test_cwd_path(self, temp_dir, monkeypatch):
        sumatra_path = temp_dir / "SumatraPDF.exe"
        sumatra_path.touch()
        monkeypatch.chdir(temp_dir)

        with patch.dict("os.environ", {"PDFPIPE_SUMATRA_PATH": ""}):
            result = find_sumatra_pdf(auto_download=False)
            assert result == sumatra_path

    def test_cache_path(self, temp_dir):
        cache_path = temp_dir / "SumatraPDF.exe"
        cache_path.touch()

        with patch.dict("os.environ", {"PDFPIPE_SUMATRA_PATH": ""}):
            with patch("pdfmill.printer.get_sumatra_cache_path", return_value=cache_path):
                with patch("pathlib.Path.cwd", return_value=Path("/nonexistent")):
                    result = find_sumatra_pdf(auto_download=False)
                    assert result == cache_path

    def test_not_found_no_auto_download(self, temp_dir):
        with patch.dict("os.environ", {"PDFPIPE_SUMATRA_PATH": "", "PATH": ""}):
            with patch("pdfmill.printer.get_sumatra_cache_path") as mock_cache:
                mock_cache.return_value = temp_dir / "nonexistent.exe"
                with patch("pathlib.Path.cwd", return_value=temp_dir / "other"):
                    result = find_sumatra_pdf(auto_download=False)
                    assert result is None


class TestPrintPdf:
    """Test PDF printing."""

    def test_dry_run_no_subprocess(self, temp_pdf, mock_subprocess_run, caplog):
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.printer.find_sumatra_pdf") as mock_find:
                mock_find.return_value = Path("SumatraPDF.exe")
                result = print_pdf(temp_pdf, "Test Printer", dry_run=True)

        assert result is True
        mock_subprocess_run.assert_not_called()
        assert "[dry-run]" in caplog.text

    def test_pdf_not_found_raises(self, temp_dir):
        nonexistent = temp_dir / "nonexistent.pdf"

        with pytest.raises(PrinterError, match="PDF file not found"):
            print_pdf(nonexistent, "Printer")

    def test_sumatra_not_found_raises(self, temp_pdf):
        with patch("pdfmill.printer.find_sumatra_pdf", return_value=None):
            with pytest.raises(PrinterError, match="SumatraPDF.exe not found"):
                print_pdf(temp_pdf, "Printer")

    def test_success(self, temp_pdf, mock_subprocess_run):
        with patch("pdfmill.printer.find_sumatra_pdf") as mock_find:
            mock_find.return_value = Path("SumatraPDF.exe")
            result = print_pdf(temp_pdf, "Test Printer")

        assert result is True
        mock_subprocess_run.assert_called_once()

    def test_with_copies(self, temp_pdf, mock_subprocess_run):
        with patch("pdfmill.printer.find_sumatra_pdf") as mock_find:
            mock_find.return_value = Path("SumatraPDF.exe")
            print_pdf(temp_pdf, "Test Printer", copies=3)

        call_args = mock_subprocess_run.call_args[0][0]
        assert "-print-settings" in call_args
        assert "3x" in call_args

    def test_with_extra_args(self, temp_pdf, mock_subprocess_run):
        with patch("pdfmill.printer.find_sumatra_pdf") as mock_find:
            mock_find.return_value = Path("SumatraPDF.exe")
            print_pdf(temp_pdf, "Test Printer", extra_args=["-silent", "-exit-on-print"])

        call_args = mock_subprocess_run.call_args[0][0]
        assert "-silent" in call_args
        assert "-exit-on-print" in call_args

    def test_custom_sumatra_path(self, temp_pdf, temp_dir, mock_subprocess_run):
        custom_path = temp_dir / "custom" / "SumatraPDF.exe"
        custom_path.parent.mkdir()
        custom_path.touch()

        result = print_pdf(temp_pdf, "Test Printer", sumatra_path=custom_path)
        assert result is True
        call_args = mock_subprocess_run.call_args[0][0]
        assert str(custom_path) in call_args

    def test_subprocess_failure_returns_false(self, temp_pdf):
        import subprocess
        with patch("pdfmill.printer.find_sumatra_pdf") as mock_find:
            mock_find.return_value = Path("SumatraPDF.exe")
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")
                result = print_pdf(temp_pdf, "Test Printer")

        assert result is False


class TestConstants:
    """Test module constants."""

    def test_sumatra_version_defined(self):
        assert SUMATRA_VERSION is not None
        assert len(SUMATRA_VERSION) > 0

    def test_sumatra_urls_has_all_archs(self):
        assert "x64" in SUMATRA_URLS
        assert "arm64" in SUMATRA_URLS
        assert "x86" in SUMATRA_URLS

    def test_urls_contain_version(self):
        for url in SUMATRA_URLS.values():
            assert SUMATRA_VERSION in url
