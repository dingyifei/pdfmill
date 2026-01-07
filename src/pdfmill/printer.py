"""Printer interface for pdfmill using SumatraPDF."""

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# SumatraPDF version to download
SUMATRA_VERSION = "3.5.2"

# Download URLs by architecture
SUMATRA_URLS = {
    "x64": f"https://www.sumatrapdfreader.org/dl/rel/{SUMATRA_VERSION}/SumatraPDF-{SUMATRA_VERSION}-64.exe",
    "arm64": f"https://www.sumatrapdfreader.org/dl/rel/{SUMATRA_VERSION}/SumatraPDF-{SUMATRA_VERSION}-arm64.exe",
    "x86": f"https://www.sumatrapdfreader.org/dl/rel/{SUMATRA_VERSION}/SumatraPDF-{SUMATRA_VERSION}.exe",
}


class PrinterError(Exception):
    """Raised when printing fails."""


def get_architecture() -> str:
    """
    Detect system architecture.

    Returns:
        'x64', 'arm64', or 'x86'
    """
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    elif machine in ("arm64", "aarch64"):
        return "arm64"
    else:
        return "x86"


def get_cache_dir() -> Path:
    """
    Get the cache directory for pdfmill.

    Returns:
        Path to cache directory (created if doesn't exist)
    """
    if sys.platform == "win32":
        # Windows: %LOCALAPPDATA%\pdfmill
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        # Linux/Mac: ~/.cache/pdfmill
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

    cache_dir = base / "pdfmill"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_sumatra_cache_path() -> Path:
    """Get the path where SumatraPDF should be cached."""
    return get_cache_dir() / "SumatraPDF.exe"


def get_sumatra_download_url() -> str:
    """Get the appropriate SumatraPDF download URL for this system."""
    arch = get_architecture()
    return SUMATRA_URLS[arch]


def download_sumatra(force: bool = False) -> Path:
    """
    Download SumatraPDF to the cache directory.

    Args:
        force: If True, re-download even if already exists

    Returns:
        Path to downloaded SumatraPDF.exe

    Raises:
        PrinterError: If download fails
    """
    if sys.platform != "win32":
        raise PrinterError("SumatraPDF is only available on Windows.")

    cache_path = get_sumatra_cache_path()

    if cache_path.exists() and not force:
        print(f"SumatraPDF already installed at: {cache_path}")
        return cache_path

    url = get_sumatra_download_url()
    arch = get_architecture()

    print(f"Downloading SumatraPDF {SUMATRA_VERSION} ({arch})...")
    print(f"  From: {url}")
    print(f"  To: {cache_path}")

    try:
        # Download with progress indication
        def report_progress(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, block_num * block_size * 100 // total_size)
                print(f"\r  Progress: {percent}%", end="", flush=True)

        urllib.request.urlretrieve(url, cache_path, reporthook=report_progress)
        print()  # New line after progress
        print(f"Successfully installed SumatraPDF to: {cache_path}")
        return cache_path

    except Exception as e:
        # Clean up partial download
        if cache_path.exists():
            cache_path.unlink()
        raise PrinterError(f"Failed to download SumatraPDF: {e}")


def remove_sumatra() -> bool:
    """
    Remove SumatraPDF from the cache directory.

    Returns:
        True if removed, False if not found
    """
    cache_path = get_sumatra_cache_path()

    if cache_path.exists():
        cache_path.unlink()
        print(f"Removed SumatraPDF from: {cache_path}")

        # Also try to remove cache dir if empty
        cache_dir = get_cache_dir()
        try:
            cache_dir.rmdir()
            print(f"Removed empty cache directory: {cache_dir}")
        except OSError:
            pass  # Directory not empty, that's fine

        return True
    else:
        print("SumatraPDF is not installed in cache.")
        return False


def get_sumatra_status() -> dict:
    """
    Get the status of SumatraPDF installation.

    Returns:
        Dict with 'installed', 'path', and 'version' keys
    """
    path = find_sumatra_pdf(auto_download=False)
    return {
        "installed": path is not None,
        "path": str(path) if path else None,
        "version": SUMATRA_VERSION if path else None,
    }


def list_printers() -> list[str]:
    """
    List available printers on the system.

    Returns:
        List of printer names

    Raises:
        PrinterError: If printer enumeration fails
    """
    try:
        import win32print
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return [printer[2] for printer in printers]
    except ImportError:
        raise PrinterError("win32print not available. Printing only works on Windows.")


def find_sumatra_pdf(auto_download: bool = True) -> Path | None:
    """
    Find SumatraPDF executable.

    Search order:
    1. PDFPIPE_SUMATRA_PATH environment variable
    2. Current directory
    3. Cache directory
    4. PATH
    5. Auto-download to cache (if auto_download=True)

    Args:
        auto_download: If True, download SumatraPDF if not found

    Returns:
        Path to SumatraPDF.exe or None if not found
    """
    # 1. Check environment variable
    env_path = os.environ.get("PDFPIPE_SUMATRA_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # 2. Check current directory
    cwd_path = Path.cwd() / "SumatraPDF.exe"
    if cwd_path.exists():
        return cwd_path

    # 3. Check cache directory
    cache_path = get_sumatra_cache_path()
    if cache_path.exists():
        return cache_path

    # 4. Check PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for dir_path in path_dirs:
        exe_path = Path(dir_path) / "SumatraPDF.exe"
        if exe_path.exists():
            return exe_path

    # 5. Auto-download if enabled and on Windows
    if auto_download and sys.platform == "win32":
        try:
            return download_sumatra()
        except PrinterError as e:
            print(f"Warning: {e}", file=sys.stderr)
            return None

    return None


def print_pdf(
    pdf_path: Path,
    printer: str,
    copies: int = 1,
    extra_args: list[str] | None = None,
    sumatra_path: Path | None = None,
    dry_run: bool = False,
) -> bool:
    """
    Print a PDF file using SumatraPDF.

    Args:
        pdf_path: Path to the PDF file
        printer: Name of the printer to use
        copies: Number of copies to print
        extra_args: Additional SumatraPDF command-line arguments
        sumatra_path: Path to SumatraPDF.exe (auto-detected if None)
        dry_run: If True, only show what would be done

    Returns:
        True if printing succeeded, False otherwise

    Raises:
        PrinterError: If SumatraPDF is not found or printing fails
    """
    if not pdf_path.exists():
        raise PrinterError(f"PDF file not found: {pdf_path}")

    if sumatra_path is None:
        sumatra_path = find_sumatra_pdf(auto_download=True)

    if sumatra_path is None:
        raise PrinterError(
            "SumatraPDF.exe not found. Run 'pdfm install' to download it, "
            "or set PDFPIPE_SUMATRA_PATH environment variable."
        )

    # Build command
    cmd = [str(sumatra_path)]

    # Add print settings
    if copies > 1:
        cmd.extend(["-print-settings", f"{copies}x"])

    # Add extra args
    if extra_args:
        cmd.extend(extra_args)

    # Add printer and file
    cmd.extend(["-print-to", printer, str(pdf_path)])

    if dry_run:
        print(f"[dry-run] Would execute: {' '.join(cmd)}")
        return True

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Print failed: {e.stderr}", file=sys.stderr)
        return False
    except FileNotFoundError:
        raise PrinterError(f"SumatraPDF not found at: {sumatra_path}")
