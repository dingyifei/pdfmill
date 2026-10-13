"""CUPS backend (macOS and Linux) using the ``lp`` and ``lpstat`` commands.

Target ``options`` become ``-o key=value`` arguments. Useful ones:
``media=w284h426`` (4x6in label), ``sides=one-sided``, ``fit-to-page=true``,
plus any PPD option listed by ``lpoptions -p <printer> -l``.
"""

import difflib
import re
import shutil
import subprocess
from pathlib import Path

from pdfmill.config import PrintTarget
from pdfmill.logging_config import get_logger
from pdfmill.printing.backend import PrinterError

logger = get_logger(__name__)

_JOB_ID_RE = re.compile(r"request id is (\S+)")


class CupsBackend:
    name = "cups"

    def list_printers(self) -> list[str]:
        out = self._run(["lpstat", "-e"]).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]

    def check_printer(self, printer: str) -> None:
        available = self.list_printers()
        if printer not in available:
            close = difflib.get_close_matches(printer, available, n=1, cutoff=0.4)
            hint = f" Did you mean '{close[0]}'?" if close else ""
            listing = ", ".join(available) or "none"
            raise PrinterError(f"Printer '{printer}' not found.{hint} Available printers: {listing}")
        accepting = self._run(["lpstat", "-a", printer], check=False).stdout
        if "not accepting" in accepting:
            raise PrinterError(f"Printer '{printer}' is not accepting jobs. Enable it with: cupsaccept {printer}")
        status = self._run(["lpstat", "-p", printer], check=False).stdout
        if "disabled" in status:
            # CUPS pauses a queue after a backend error (e.g. Bluetooth printer was off).
            # Jobs would sit in the queue silently, so refuse instead.
            raise PrinterError(
                f"Printer '{printer}' is paused: {status.strip()}\n"
                f"Check the printer is on and connected, then resume it with: cupsenable {printer}"
            )

    def command(self, path: Path, target: PrintTarget, title: str) -> list[str]:
        cmd = ["lp", "-d", target.printer, "-n", str(target.copies), "-t", title]
        for key, value in target.options.items():
            cmd += ["-o", f"{key}={value}"]
        return [*cmd, *target.args, "--", str(path)]

    def print_file(self, path: Path, target: PrintTarget, title: str) -> str:
        result = self._run(self.command(path, target, title))
        match = _JOB_ID_RE.search(result.stdout)
        if not match:
            raise PrinterError(f"lp did not report a job id: {result.stdout.strip() or result.stderr.strip()}")
        return match.group(1)

    @staticmethod
    def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        if shutil.which(cmd[0]) is None:
            raise PrinterError(f"'{cmd[0]}' not found. CUPS printing needs the CUPS command-line tools.")
        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if check and result.returncode != 0:
            raise PrinterError(f"{cmd[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
        return result
