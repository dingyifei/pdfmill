"""Command-line interface for pdfmill."""

import argparse
import sys
from pathlib import Path

from pdfmill import __version__
from pdfmill.logging_config import get_logger

logger = get_logger(__name__)


def show_version() -> None:
    """Show version information including SumatraPDF status."""
    from pdfmill.printer import SUMATRA_VERSION, get_sumatra_status

    logger.info("pdfmill %s", __version__)

    status = get_sumatra_status()
    if status["installed"]:
        logger.info("SumatraPDF %s installed at: %s", SUMATRA_VERSION, status["path"])
    else:
        logger.info("SumatraPDF: not installed (run 'pdfm install' to download)")


def cmd_install(force: bool = False) -> int:
    """Install SumatraPDF."""
    from pdfmill.printer import PrinterError, download_sumatra

    try:
        download_sumatra(force=force)
        return 0
    except PrinterError as e:
        logger.error("%s", e)
        return 1


def cmd_uninstall() -> int:
    """Uninstall SumatraPDF."""
    from pdfmill.printer import remove_sumatra

    if remove_sumatra():
        return 0
    else:
        return 1


def cmd_list_printers() -> int:
    """List available printers."""
    from pdfmill.printer import PrinterError, list_printers

    try:
        printers = list_printers()
        if not printers:
            logger.info("No printers found.")
            return 1
        logger.info("Available printers:")
        for i, printer in enumerate(printers, 1):
            logger.info("  %d. %s", i, printer)
        return 0
    except PrinterError as e:
        logger.error("%s", e)
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdfm",
        description="Configurable PDF processing pipeline for splitting, transforming, and printing PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdfm install                                  Download SumatraPDF for printing
  pdfm uninstall                                Remove downloaded SumatraPDF
  pdfm -c config.yaml -i ./input -o ./output    Process PDFs with config
  pdfm -c config.yaml -i document.pdf           Process a single file
  pdfm -c config.yaml --validate                Validate config only
  pdfm -c config.yaml -i ./input --dry-run      Show what would happen
  pdfm --list-printers                          List available printers

Watch mode:
  pdfm -c config.yaml -i ./input --watch        Watch and process new files
  pdfm -c config.yaml -i ./input --watch --dry-run
                                                Watch with preview mode
  pdfm -c config.yaml -i ./input --watch --no-process-existing
                                                Skip existing files on startup
""",
    )

    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Show version information and exit",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to YAML configuration file",
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="Input PDF file or directory containing PDFs",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory (overrides config)",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration file and exit",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="With --validate, also check external resources (printers exist, paths valid)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )

    # Watch mode arguments
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch input directory and process new files as they appear",
    )

    parser.add_argument(
        "--watch-interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds for watch mode (default: 2.0)",
    )

    parser.add_argument(
        "--watch-debounce",
        type=float,
        default=1.0,
        help="Debounce delay in seconds for file stability check (default: 1.0)",
    )

    parser.add_argument(
        "--watch-state",
        type=Path,
        help="Path to state file for tracking processed files in watch mode",
    )

    parser.add_argument(
        "--no-process-existing",
        action="store_true",
        help="Skip processing existing files when starting watch mode",
    )

    parser.add_argument(
        "--list-printers",
        action="store_true",
        help="List available printers and exit",
    )

    # Subcommands as positional argument
    parser.add_argument(
        "command",
        nargs="?",
        choices=["install", "uninstall", "gui"],
        help="Subcommand: install (download SumatraPDF), uninstall (remove it), or gui (launch config editor)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if already installed (used with 'install')",
    )

    # Logging options
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for verbose, -vv for debug)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write logs to file (includes all levels)",
    )

    return parser


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Setup logging based on CLI flags
    from pdfmill.logging_config import setup_logging

    setup_logging(
        verbosity=parsed.verbose,
        quiet=parsed.quiet,
        log_file=parsed.log_file,
    )

    # Handle --version
    if parsed.version:
        show_version()
        return 0

    # Handle subcommands
    if parsed.command == "install":
        return cmd_install(force=parsed.force)
    elif parsed.command == "uninstall":
        return cmd_uninstall()
    elif parsed.command == "gui":
        from pdfmill.gui import launch_gui

        return launch_gui()

    # Handle --list-printers
    if parsed.list_printers:
        return cmd_list_printers()

    # Require config for other operations
    if not parsed.config:
        parser.print_help()
        return 1

    # Handle --validate
    if parsed.validate:
        from pdfmill.config import ConfigError, load_config

        try:
            config = load_config(parsed.config)
            logger.info("Configuration syntax is valid: %s", parsed.config)
            logger.info("  Outputs defined: %s", ", ".join(config.outputs.keys()))

            # If --strict, perform additional validation
            if parsed.strict:
                from pdfmill.validation import validate_strict

                logger.info("\nStrict validation:")
                result = validate_strict(config)

                if result.issues:
                    for issue in result.issues:
                        if issue.level == "error":
                            logger.error("  %s", issue)
                        else:
                            logger.warning("  %s", issue)
                    error_count = sum(1 for i in result.issues if i.level == "error")
                    warning_count = sum(1 for i in result.issues if i.level == "warning")
                    if result.has_errors:
                        logger.error("\nValidation failed with %d error(s)", error_count)
                        return 1
                    else:
                        logger.info("\nValidation passed with %d warning(s)", warning_count)
                else:
                    logger.info("  All external resources validated successfully")

            return 0
        except ConfigError as e:
            logger.error("Configuration error: %s", e)
            return 1
        except FileNotFoundError:
            logger.error("Configuration file not found: %s", parsed.config)
            return 1

    # Handle processing
    if not parsed.input:
        logger.error("--input is required for processing")
        return 1

    from pdfmill.config import ConfigError, load_config

    try:
        config = load_config(parsed.config)

        # Override output directory if specified
        output_dir = parsed.output

        # Handle watch mode
        if parsed.watch:
            # Watch mode requires a directory input
            if not parsed.input.is_dir():
                logger.error("--watch requires an input directory, not a file")
                return 1

            from pdfmill.watcher import PdfWatcher, WatchConfig

            watch_config = WatchConfig(
                poll_interval=parsed.watch_interval,
                debounce_delay=parsed.watch_debounce,
                state_file=parsed.watch_state,
                process_existing=not parsed.no_process_existing,
            )

            watcher = PdfWatcher(
                config=config,
                input_path=parsed.input,
                output_dir=output_dir,
                dry_run=parsed.dry_run,
                watch_config=watch_config,
            )
            watcher.run()
            return 0

        # Regular processing
        from pdfmill.processor import process

        process(
            config=config,
            input_path=parsed.input,
            output_dir=output_dir,
            dry_run=parsed.dry_run,
        )
        return 0
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        return 1
    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        return 1
    except Exception as e:
        logger.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
