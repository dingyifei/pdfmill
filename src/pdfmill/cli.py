"""Command-line interface for pdfmill."""

import argparse
import sys
from pathlib import Path

from pdfmill import __version__


def show_version() -> None:
    """Show version information including SumatraPDF status."""
    from pdfmill.printer import get_sumatra_status, SUMATRA_VERSION

    print(f"pdfmill {__version__}")

    status = get_sumatra_status()
    if status["installed"]:
        print(f"SumatraPDF {SUMATRA_VERSION} installed at: {status['path']}")
    else:
        print("SumatraPDF: not installed (run 'pdfp install' to download)")


def cmd_install(force: bool = False) -> int:
    """Install SumatraPDF."""
    from pdfmill.printer import download_sumatra, PrinterError

    try:
        download_sumatra(force=force)
        return 0
    except PrinterError as e:
        print(f"Error: {e}", file=sys.stderr)
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
    from pdfmill.printer import list_printers, PrinterError

    try:
        printers = list_printers()
        if not printers:
            print("No printers found.")
            return 1
        print("Available printers:")
        for i, printer in enumerate(printers, 1):
            print(f"  {i}. {printer}")
        return 0
    except PrinterError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdfp",
        description="Configurable PDF processing pipeline for splitting, transforming, and printing PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdfp install                                  Download SumatraPDF for printing
  pdfp uninstall                                Remove downloaded SumatraPDF
  pdfp -c config.yaml -i ./input -o ./output    Process PDFs with config
  pdfp -c config.yaml -i document.pdf           Process a single file
  pdfp -c config.yaml --validate                Validate config only
  pdfp -c config.yaml -i ./input --dry-run      Show what would happen
  pdfp --list-printers                          List available printers
""",
    )

    parser.add_argument(
        "-V", "--version",
        action="store_true",
        help="Show version information and exit",
    )

    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to YAML configuration file",
    )

    parser.add_argument(
        "-i", "--input",
        type=Path,
        help="Input PDF file or directory containing PDFs",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output directory (overrides config)",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration file and exit",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
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

    return parser


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    parsed = parser.parse_args(args)

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
        from pdfmill.config import load_config, ConfigError
        try:
            config = load_config(parsed.config)
            print(f"Configuration is valid: {parsed.config}")
            print(f"  Outputs defined: {', '.join(config.outputs.keys())}")
            return 0
        except ConfigError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            return 1
        except FileNotFoundError:
            print(f"Configuration file not found: {parsed.config}", file=sys.stderr)
            return 1

    # Handle processing
    if not parsed.input:
        print("Error: --input is required for processing", file=sys.stderr)
        return 1

    from pdfmill.config import load_config, ConfigError
    from pdfmill.processor import process

    try:
        config = load_config(parsed.config)

        # Override output directory if specified
        output_dir = parsed.output

        process(
            config=config,
            input_path=parsed.input,
            output_dir=output_dir,
            dry_run=parsed.dry_run,
        )
        return 0
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
