# pdfmill

[![Python package](https://github.com/dingyifei/PrintAThingPDF/actions/workflows/python-package.yml/badge.svg)](https://github.com/dingyifei/PrintAThingPDF/actions/workflows/python-package.yml)

A configurable PDF processing pipeline for splitting, transforming, and printing PDFs.

Currently, supports only windows

<img src="docs/resources/outputs.png" width="400">

## Features

- **YAML Configuration**: Define processing pipelines in simple config files
- **Page Selection**: Select pages by index, range, or pattern (`first`, `last`, `odd`, `even`)
- **Transformations**: Rotate, crop, resize, stamp, split, and combine pages with precise control
- **Stamp Transform**: Add page numbers, timestamps, or custom text overlays
- **Split Transform**: Extract multiple regions from a page (e.g., split label sheets)
- **Combine Transform**: Place multiple pages onto a single canvas (e.g., n-up layouts)
- **Multi-Output**: Split one PDF into multiple outputs with different settings
- **Batch Processing**: Process single files or entire directories
- **Input Filtering**: Filter PDFs by filename pattern or text content keywords
- **Input Sorting**: Sort files by name or timestamp before processing
- **Printing**: Send outputs to different printers with custom settings
- **Multi-Printer Distribution**: Split pages across multiple printers by speed/weight
- **Dry Run**: Preview what will happen before processing

## Installation

```sh
# Clone and install in development mode
git clone https://github.com/dingyifei/pdfmill.git
cd pdfmill
pip install -e .
```

## Quick Start

```sh
# Start GUI
pdfm gui

# List available printers
pdfm --list-printers

# Process PDFs with a config file
pdfm -c configs/label_packing.yaml -i ./input -o ./output

# Process a single file
pdfm -c configs/label_packing.yaml -i document.pdf

# Dry run (see what would happen)
pdfm -c configs/label_packing.yaml -i ./input --dry-run

# Validate a config file
pdfm -c configs/label_packing.yaml --validate
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
| [Printing](docs/printing.md) | Single and multi-printer setup |
| [CLI Reference](docs/cli-reference.md) | Command-line options |

## Example Configs

See the `configs/` directory for ready-to-use examples:

- `label_packing.yaml` - Split PDFs into packing sheet + shipping label
- `six_page.yaml` - Process 6-page PDFs (remove pages 1-2, rotate pages 4-5)
- `multi_printer.yaml` - Multi-printer distribution with sorting

## Environment

- Python 3.10+
- Windows 10 or newer
- SumatraPDF (installed via `pdfm install`)

## License

MIT License
