# pdfmill

[![Python package](https://github.com/dingyifei/PrintAThingPDF/actions/workflows/python-package.yml/badge.svg)](https://github.com/dingyifei/PrintAThingPDF/actions/workflows/python-package.yml)

A configurable PDF processing pipeline for splitting, transforming, and printing PDFs.

Runs on macOS and Linux (printing via CUPS) and Windows (printing via SumatraPDF).

## Features

- **YAML Configuration**: Define processing pipelines in simple config files, validated strictly at load time
- **Page Selection**: Select pages by index, range, or pattern (`first`, `last`, `odd`, `even`)
- **Transformations**: Rotate, crop, resize, stamp, split, and combine pages with precise control
- **Stamp Transform**: Add page numbers, timestamps, or custom text overlays
- **Split Transform**: Extract multiple regions from a page (e.g., split label sheets)
- **Combine Transform**: Place multiple pages onto a single canvas (e.g., n-up layouts)
- **Multi-Output**: Split one PDF into multiple outputs with different settings
- **Batch Processing**: Process single files or entire directories
- **Input Filtering**: Filter PDFs by filename pattern or text content keywords
- **Input Sorting**: Sort files by name or timestamp before processing
- **Printing**: Send outputs to different printers with custom settings (CUPS options or SumatraPDF arguments)
- **Multi-Printer Distribution**: Split pages across multiple printers by speed/weight
- **Print Safety**: Block jobs with too many pages or oversized pages
- **Watch Mode**: Poll a directory and automatically process new PDFs as they arrive
- **Dry Run**: Run every transform in a temp directory and show the exact print commands, without printing

## Installation

```sh
# Clone and install in development mode
git clone https://github.com/dingyifei/pdfmill.git
cd pdfmill
pip install -e .

# Optional extras
pip install -e ".[stamp]"   # stamp transform (reportlab)
pip install -e ".[ocr]"     # render and rotate: auto (pdf2image, pytesseract, Pillow)
```

## Quick Start

```sh
# List available printers (names to use for 'printer:')
pdfm --list-printers

# Process PDFs with a config file (input defaults to input.path from the config)
pdfm -c configs/label_packing.yaml

# Process a directory or a single file, overriding the output directory
pdfm -c configs/label_packing.yaml -i ./input -o ./output
pdfm -c configs/label_packing.yaml -i document.pdf

# Dry run (process in a temp dir, show print commands, print nothing)
pdfm -c configs/label_packing.yaml --dry-run

# Watch mode (process new files automatically)
pdfm -c configs/label_packing.yaml --watch

# Validate a config file (add --strict to also check printers, input path and dependencies)
pdfm -c configs/label_packing.yaml --validate --strict
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation and first run |
| [Configuration](docs/configuration.md) | Config file structure and settings |
| [Input](docs/input.md) | Input filtering and sorting |
| [Page Selection](docs/page-selection.md) | Page selection syntax |
| [Transforms](docs/transforms.md) | All transform types (rotate, crop, resize, stamp, split, combine, render) |
| [Output Profiles](docs/output-profiles.md) | Output profile options and debug mode |
| [Printing](docs/printing.md) | Printer backends, single and multi-printer setup |
| [Watch Mode](docs/watch-mode.md) | Automatic file monitoring and processing |
| [CLI Reference](docs/cli-reference.md) | Command-line options |

## Example Configs

See the `configs/` directory for ready-to-use examples:

- `label_packing.yaml` - Split PDFs into packing sheet + shipping label (Brother laser + PL80E-BT label printer on macOS)
- `six_page.yaml` - Process 6-page PDFs (remove pages 1-2, rotate pages 4-5)
- `multi_printer.yaml` - Multi-printer distribution with sorting

## Environment

- Python 3.10+
- macOS / Linux: CUPS (built into macOS; `lp` and `lpstat` must be available)
- Windows: SumatraPDF, downloaded automatically on first print to `%LOCALAPPDATA%\pdfmill` (or set `PDFMILL_SUMATRA_PATH`)
- Optional: `poppler` for `render` and `rotate: auto`, plus `tesseract` for `rotate: auto` (macOS: `brew install poppler tesseract`)

## License

MIT License
