"""Windows backend using SumatraPDF (https://www.sumatrapdfreader.org).

SumatraPDF is looked up via $PDFMILL_SUMATRA_PATH, the current directory, the
pdfmill cache and PATH, and downloaded to the cache on first use. Target
``args`` are passed through (e.g. ``["-print-settings", "simplex"]``);
CUPS-style ``options`` are not supported here.
"""

import os
import platform
import shutil
import subprocess
import urllib.request
from pathlib import Path

from pdfmill.config import PrintTarget
from pdfmill.logging_config import get_logger
from pdfmill.printing.backend import PrinterError

logger = get_logger(__name__)

SUMATRA_VERSION = "3.5.2"
_BASE_URL = f"https://www.sumatrapdfreader.org/dl/rel/{SUMATRA_VERSION}/SumatraPDF-{SUMATRA_VERSION}"
_URLS = {"x64": f"{_BASE_URL}-64.exe", "arm64": f"{_BASE_URL}-arm64.exe", "x86": f"{_BASE_URL}.exe"}


class SumatraBackend:
    name = "sumatra"

    def __init__(self, exe: Path | None = None):
        self._exe = exe

    def list_printers(self) -> list[str]:
        try:
            import win32print
        except ImportError:
            raise PrinterError("win32print is not available; the SumatraPDF backend only works on Windows")
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]

    def check_printer(self, printer: str) -> None:
        available = self.list_printers()
        if printer not in available:
            raise PrinterError(f"Printer '{printer}' not found. Available printers: {', '.join(available) or 'none'}")

    def command(self, path: Path, target: PrintTarget, title: str) -> list[str]:
        exe = str(self._exe or "SumatraPDF.exe")
        cmd = [exe]
        if target.copies > 1:
            cmd += ["-print-settings", f"{target.copies}x"]
        return [*cmd, *target.args, "-print-to", target.printer, str(path)]

    def print_file(self, path: Path, target: PrintTarget, title: str) -> str:
        if target.options:
            logger.warning("Ignoring CUPS 'options' for '%s' on SumatraPDF; use 'args' instead", target.printer)
        self._exe = self._exe or find_sumatra()
        result = subprocess.run(self.command(path, target, title), capture_output=True, text=True)
        if result.returncode != 0:
            raise PrinterError(f"SumatraPDF failed ({result.returncode}): {result.stderr.strip()}")
        return f"sumatra:{path.name}"


def _cache_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "pdfmill" / "SumatraPDF.exe"


def find_sumatra(download: bool = True) -> Path:
    for env in ("PDFMILL_SUMATRA_PATH", "PDFPIPE_SUMATRA_PATH"):
        if os.environ.get(env) and Path(os.environ[env]).exists():
            return Path(os.environ[env])
    for candidate in (Path.cwd() / "SumatraPDF.exe", _cache_path()):
        if candidate.exists():
            return candidate
    on_path = shutil.which("SumatraPDF")
    if on_path:
        return Path(on_path)
    if not download:
        raise PrinterError("SumatraPDF.exe not found; set PDFMILL_SUMATRA_PATH")
    return _download()


def _download() -> Path:
    machine = platform.machine().lower()
    arch = "x64" if machine in ("amd64", "x86_64") else "arm64" if machine in ("arm64", "aarch64") else "x86"
    dest = _cache_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".part")
    logger.info("Downloading SumatraPDF %s (%s) to %s", SUMATRA_VERSION, arch, dest)
    try:
        urllib.request.urlretrieve(_URLS[arch], partial)
        partial.replace(dest)
    except OSError as e:
        partial.unlink(missing_ok=True)
        raise PrinterError(f"Failed to download SumatraPDF: {e}")
    return dest
