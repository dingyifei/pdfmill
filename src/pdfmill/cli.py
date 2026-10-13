"""Command-line interface: ``pdfm``."""

import argparse
import importlib.util
import sys
from pathlib import Path

from pdfmill import __version__
from pdfmill.logging_config import get_logger, setup_logging

logger = get_logger(__name__)

EPILOG = """
Examples:
  pdfm --list-printers                          List printer names for 'printer:'
  pdfm -c config.yaml --validate --strict       Check config, printers and dependencies
  pdfm -c config.yaml --dry-run                 Process into a temp dir, show print commands
  pdfm -c config.yaml                           Process input.path from the config
  pdfm -c config.yaml -i label.pdf -o ./out     Process one file into ./out
  pdfm -c config.yaml --watch                   Process new PDFs as they appear
"""

# Optional modules each transform needs, with the extra that provides them.
_TRANSFORM_DEPS = {
    "stamp": [("reportlab", "stamp")],
    "render": [("pdf2image", "ocr")],
}


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdfm",
        description="Split, transform and print PDFs as described by a YAML config.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    p.add_argument("-V", "--version", action="version", version=f"pdfmill {__version__}")
    p.add_argument("-c", "--config", type=Path, help="YAML configuration file")
    p.add_argument("-i", "--input", type=Path, help="input PDF or directory (default: input.path from the config)")
    p.add_argument("-o", "--output", type=Path, help="output directory for every profile (overrides config)")
    p.add_argument("--validate", action="store_true", help="validate the config and exit")
    p.add_argument("--strict", action="store_true", help="with --validate: also check printers, input path, deps")
    p.add_argument("--dry-run", action="store_true", help="process in a temp dir; show print commands, print nothing")
    p.add_argument("--list-printers", action="store_true", help="list available printers and exit")
    p.add_argument("--backend", choices=("auto", "cups", "sumatra"), help="override settings.print_backend")

    w = p.add_argument_group("watch mode")
    w.add_argument("--watch", action="store_true", help="watch the input directory and process new PDFs")
    w.add_argument("--watch-interval", type=float, help="seconds between polls (default: watch.poll_interval)")
    w.add_argument(
        "--watch-debounce", type=float, help="seconds a file must be unchanged (default: watch.debounce_delay)"
    )
    w.add_argument("--watch-state", type=Path, help="state file (default: <input>/.pdfmill_watch_state.json)")
    w.add_argument("--no-process-existing", action="store_true", help="ignore files present when watch starts")

    log = p.add_argument_group("logging")
    log.add_argument("-v", "--verbose", action="count", default=0, help="-v verbose, -vv debug")
    log.add_argument("-q", "--quiet", action="store_true", help="errors only")
    log.add_argument("--log-file", type=Path, help="also write all log levels to this file")
    return p


def main(args: list[str] | None = None) -> int:
    parser = create_parser()
    opts = parser.parse_args(args)
    setup_logging(verbosity=opts.verbose, quiet=opts.quiet, log_file=opts.log_file)

    from pdfmill.config import ConfigError, load_config
    from pdfmill.printing import PrinterError, get_backend

    try:
        if opts.list_printers:
            return cmd_list_printers(get_backend(opts.backend or "auto"))
        if not opts.config:
            parser.print_help()
            return 1

        config = load_config(opts.config)
        if opts.backend:
            config.settings.print_backend = opts.backend
        if opts.validate:
            return cmd_validate(config, opts)

        input_path = opts.input or config.input.path
        if opts.watch:
            return cmd_watch(config, input_path, opts)

        from pdfmill.processor import process

        result = process(config, input_path, opts.output, dry_run=opts.dry_run)
        return 0 if result.ok else 1
    except FileNotFoundError as e:
        logger.error("File not found: %s", e.filename or e)
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
    except PrinterError as e:
        logger.error("%s", e)
    except Exception as e:  # last-resort: report instead of a traceback
        logger.error("%s: %s", type(e).__name__, e)
        logger.debug("Traceback:", exc_info=True)
    return 1


def cmd_list_printers(backend) -> int:
    printers = backend.list_printers()
    if not printers:
        logger.info("No printers found.")
        return 1
    logger.info("Available printers (%s):", backend.name)
    for name in printers:
        logger.info("  %s", name)
    return 0


def cmd_validate(config, opts) -> int:
    logger.info("Configuration is valid: %s", opts.config)
    logger.info("  Profiles: %s", ", ".join(config.outputs))
    if not opts.strict:
        return 0

    from pdfmill.printing import PrinterError, get_backend

    errors = []
    input_path = opts.input or config.input.path
    if not input_path.exists():
        errors.append(f"input path does not exist: {input_path}")

    profiles = [p for p in config.outputs.values() if p.enabled]
    for profile in profiles:
        for t in profile.transforms:
            if t.name == "rotate" and t.options.angle == "auto":
                deps = [("pytesseract", "ocr"), ("pdf2image", "ocr")]
            else:
                deps = _TRANSFORM_DEPS.get(t.name, [])
            for module, extra in deps:
                if importlib.util.find_spec(module) is None:
                    errors.append(f"profile '{profile.name}': {t.name} needs {module} (pip install 'pdfmill[{extra}]')")

    printers = {t.printer for p in profiles if p.print.enabled for t in p.print.targets.values()}
    if printers:
        backend = get_backend(config.settings.print_backend)
        for printer in sorted(printers):
            try:
                backend.check_printer(printer)
                logger.info("  Printer OK: %s", printer)
            except PrinterError as e:
                errors.append(str(e))

    for err in errors:
        logger.error("  %s", err)
    if errors:
        logger.error("Strict validation failed with %d error(s)", len(errors))
        return 1
    logger.info("Strict validation passed")
    return 0


def cmd_watch(config, input_path: Path, opts) -> int:
    if not input_path.is_dir():
        logger.error("--watch needs an input directory: %s", input_path)
        return 1
    from pdfmill.watcher import Watcher

    Watcher(
        config,
        input_path,
        output_dir=opts.output,
        dry_run=opts.dry_run,
        state_file=opts.watch_state,
        process_existing=False if opts.no_process_existing else None,
        poll_interval=opts.watch_interval,
        debounce_delay=opts.watch_debounce,
    ).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
