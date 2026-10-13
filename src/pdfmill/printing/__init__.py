"""Send a profile's output PDFs to its printers: safety check, merge, split by weight, print."""

import shlex
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfmill.config import OutputProfile, PrintConfig, PrintTarget
from pdfmill.logging_config import get_logger
from pdfmill.printing.backend import Backend, PrinterError, get_backend

__all__ = ["Backend", "PrinterError", "PrintSafetyError", "get_backend", "print_profile"]

logger = get_logger(__name__)


class PrintSafetyError(PrinterError):
    """Raised when output exceeds a profile's max_pages / max_page_size limits."""


def print_profile(
    profile: OutputProfile,
    files: list[Path],
    backend: Backend,
    workdir: Path,
    dry_run: bool = False,
) -> list[str]:
    """Print ``files`` (already in print order) to the profile's targets.

    Every printer is checked before anything is sent, so a missing printer
    never leaves a job half-printed. Merged and split PDFs are written to
    ``workdir``. Returns the job ids; raises PrinterError on any failure.
    """
    cfg = profile.print
    check_safety(files, cfg, profile.name)
    for target in cfg.targets.values():
        backend.check_printer(target.printer)

    if cfg.merge and len(files) > 1:
        merged = workdir / f"{profile.name}_merged.pdf"
        _write(merged, [page for f in files for page in PdfReader(f).pages])
        logger.info("Merged %d files for profile '%s'", len(files), profile.name)
        files = [merged]

    jobs: list[tuple[Path, PrintTarget]] = []
    if cfg.merge and len(cfg.targets) > 1:
        for f in files:
            jobs += split_by_weight(f, cfg.targets, workdir / profile.name)
    else:
        jobs = [(f, t) for f in files for t in cfg.targets.values()]

    job_ids = []
    for path, target in jobs:
        title = f"{profile.name}: {path.name}"
        if dry_run:
            logger.info("[dry-run] Would run: %s", _quote(backend.command(path, target, title)))
            continue
        job_id = backend.print_file(path, target, title)
        logger.info("Printed %s on %s (job %s)", path.name, target.printer, job_id)
        job_ids.append(job_id)
    return job_ids


def check_safety(files: list[Path], cfg: PrintConfig, profile_name: str) -> None:
    """Enforce max_pages / max_page_size. Unreadable files count as violations."""
    if cfg.max_pages is None and cfg.max_page_size is None:
        return
    violations = []
    total = 0
    for f in files:
        try:
            pages = PdfReader(f).pages
        except Exception as e:
            violations.append(f"{f.name}: cannot read PDF ({e})")
            continue
        total += len(pages)
        if cfg.max_page_size:
            max_w, max_h = cfg.max_page_size
            for n, page in enumerate(pages, start=1):
                w, h = float(page.mediabox.width), float(page.mediabox.height)
                if not ((w <= max_w and h <= max_h) or (h <= max_w and w <= max_h)):
                    violations.append(
                        f"{f.name} page {n}: {w:.0f}x{h:.0f} pt exceeds max_page_size {max_w:.0f}x{max_h:.0f} pt"
                    )
    if cfg.max_pages is not None and total > cfg.max_pages:
        violations.append(f"{total} pages exceeds max_pages ({cfg.max_pages})")
    if not violations:
        return
    message = f"Print safety check failed for profile '{profile_name}': " + "; ".join(violations)
    if cfg.action == "warn":
        logger.warning("%s (printing anyway)", message)
        return
    raise PrintSafetyError(message)


def split_by_weight(path: Path, targets: dict[str, PrintTarget], out_dir: Path) -> list[tuple[Path, PrintTarget]]:
    """Split ``path`` into consecutive page ranges, sized by target weight.

    The highest-weight target gets the first pages so the stacks can be
    collected in order. Targets with weight 0 get nothing.
    """
    pages = PdfReader(path).pages
    ranked = sorted(((n, t) for n, t in targets.items() if t.weight > 0), key=lambda nt: nt[1].weight, reverse=True)
    if not ranked:
        raise PrinterError("All print targets have weight 0")
    total_weight = sum(t.weight for _, t in ranked)
    result = []
    start = 0
    for i, (name, target) in enumerate(ranked):
        count = len(pages) - start if i == len(ranked) - 1 else round(len(pages) * target.weight / total_weight)
        end = min(start + count, len(pages))
        if end > start:
            part = out_dir / f"{path.stem}_{name}.pdf"
            _write(part, pages[start:end])
            result.append((part, target))
        start = end
    return result


def _write(path: Path, pages) -> None:
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        writer.write(f)


def _quote(cmd: list[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)
