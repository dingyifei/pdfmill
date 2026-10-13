"""Run a config over input PDFs: select pages, transform, write, print, clean up.

Each source PDF is a unit of work. It counts as succeeded only if every
enabled profile produced its output and every print job containing that
output was accepted. Cleanup only ever touches work that succeeded.
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdfmill.config import Config, OutputProfile
from pdfmill.logging_config import get_logger
from pdfmill.printing import Backend, get_backend, print_profile
from pdfmill.selector import select_pages
from pdfmill.transforms import apply_all
from pdfmill.transforms._page import clone

logger = get_logger(__name__)


class ProcessingError(Exception):
    """Raised for input problems (e.g. missing input path) and when on_error is 'stop'."""


@dataclass
class RunResult:
    sources: list[Path] = field(default_factory=list)
    failed: dict[Path, str] = field(default_factory=dict)  # source -> first error
    outputs: list[Path] = field(default_factory=list)
    jobs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    @property
    def succeeded(self) -> list[Path]:
        return [s for s in self.sources if s not in self.failed]

    def fail(self, source: Path, message: str) -> None:
        logger.error("%s: %s", source.name, message)
        self.failed.setdefault(source, message)


def find_inputs(path: Path, pattern: str = "*.pdf") -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob(pattern) if p.is_file())
    raise ProcessingError(f"Input path does not exist: {path}")


def sort_files(files: list[Path], order: str | None) -> list[Path]:
    if order is None:
        return files
    by_time = order.startswith("time")
    key = (lambda f: f.stat().st_mtime) if by_time else (lambda f: f.name.lower())
    return sorted(files, key=key, reverse=order.endswith("desc"))


def matches_keywords(path: Path, keywords: list[str], match: str) -> bool:
    if not keywords:
        return True
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    found = (kw in text for kw in keywords)
    return all(found) if match == "all" else any(found)


def process_file(source: Path, profile: OutputProfile, output_dir: Path) -> Path:
    """Apply one profile to one PDF and return the written output path."""
    reader = PdfReader(source)
    indices = select_pages(profile.pages, len(reader.pages))
    seen: set[int] = set()
    pages = []
    for i in indices:
        # A page selected twice must be an independent copy, or transforms would apply twice.
        pages.append(clone(reader.pages[i]) if i in seen else reader.pages[i])
        seen.add(i)

    debug_prefix = output_dir / f"{source.stem}_{profile.name}" if profile.debug else None
    pages = apply_all(pages, profile.transforms, debug_prefix)

    output = output_dir / profile.output_name(source)
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)
    output_dir.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".pdf.part")
    with open(partial, "wb") as f:
        writer.write(f)
    partial.replace(output)  # never leave a half-written PDF behind
    logger.info("  Created: %s", output)
    return output


def process(
    config: Config,
    input_path: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
    backend: Backend | None = None,
) -> RunResult:
    """Process ``input_path`` (a file or directory; defaults to ``input.path``).

    ``output_dir`` overrides every profile's output_dir. A dry run does all
    the work in a temporary directory and logs the print commands instead of
    running them; nothing is printed or deleted.
    """
    input_path = input_path or config.input.path
    result = RunResult()
    stop = config.settings.on_error == "stop"

    sources = []
    for f in find_inputs(input_path, config.input.pattern):
        try:
            if matches_keywords(f, config.input.keywords, config.input.match):
                sources.append(f)
            else:
                logger.info("Skipping %s: keyword filter did not match", f.name)
        except Exception as e:
            result.sources.append(f)
            result.fail(f, f"cannot read PDF: {e}")
            if stop:
                raise ProcessingError(str(e))
    sources = sort_files(sources, config.input.sort)
    result.sources += sources
    if not result.sources:
        logger.info("No PDF files found in %s matching %s", input_path, config.input.pattern)
        return result
    logger.info("Found %d PDF file(s) to process", len(sources))

    profiles = [p for p in config.outputs.values() if p.enabled]
    with tempfile.TemporaryDirectory(prefix="pdfmill-") as tmp:
        workdir = Path(tmp)
        if dry_run:
            output_dir = workdir / "output"

        # 1. Transform: outputs[profile name] = [(source, output path)]
        outputs: dict[str, list[tuple[Path, Path]]] = {p.name: [] for p in profiles}
        for source in sources:
            logger.info("Processing: %s", source.name)
            for profile in profiles:
                try:
                    out = process_file(source, profile, output_dir or profile.output_dir)
                except Exception as e:
                    result.fail(source, f"profile '{profile.name}': {e}")
                    if stop:
                        raise ProcessingError(str(e))
                    continue
                outputs[profile.name].append((source, out))
                result.outputs.append(out)

        # 2. Print
        printed: list[Path] = []
        printing = [p for p in profiles if p.print.enabled and outputs[p.name]]
        if printing:
            backend = backend or get_backend(config.settings.print_backend)
        for profile in printing:
            items = outputs[profile.name]
            if profile.sort:
                order = sort_files([s for s, _ in items], profile.sort)
                items = sorted(items, key=lambda item: order.index(item[0]))
            try:
                result.jobs += print_profile(profile, [out for _, out in items], backend, workdir, dry_run)
                printed += [out for _, out in items]
            except Exception as e:
                for source, _ in items:
                    result.fail(source, f"printing profile '{profile.name}' failed: {e}")
                if stop:
                    raise ProcessingError(str(e))

    # 3. Clean up (only what succeeded)
    if not dry_run:
        if config.settings.cleanup_output_after_print:
            for out in printed:
                _remove(out)
        if config.settings.cleanup_source:
            for source in result.succeeded:
                _remove(source)
        if config.settings.cleanup_source and result.failed:
            logger.warning("Kept %d source file(s) that did not fully succeed", len(result.failed))

    logger.info("Done: %d succeeded, %d failed", len(result.succeeded), len(result.failed))
    return result


def _remove(path: Path) -> None:
    try:
        os.remove(path)
        logger.debug("Removed %s", path)
    except OSError as e:
        logger.warning("Could not remove %s: %s", path, e)
