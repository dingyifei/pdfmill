# Getting Started

This guide walks you through installing pdfmill and running your first PDF processing job.

## Prerequisites

- Python 3.10 or newer
- For printing:
  - macOS / Linux: CUPS (built into macOS; most Linux desktops have it)
  - Windows: SumatraPDF (downloaded automatically on first print)

## Installation

### From PyPI (Recommended)

```sh
pip install pdfmill
```

### Development Mode

```sh
git clone https://github.com/dingyifei/pdfmill.git
cd pdfmill
pip install -e .
```

### Optional Dependencies

Install extras for additional features:

```sh
# For stamp transform (adds reportlab)
pip install "pdfmill[stamp]"

# For render and auto-rotation via OCR (adds pdf2image, pytesseract, Pillow)
pip install "pdfmill[ocr]"

# For development (pytest, ruff)
pip install "pdfmill[dev]"
```

`render` and `rotate: auto` also need the `poppler` tools, and `rotate: auto` needs `tesseract`:

```sh
# macOS
brew install poppler tesseract
```

## Printer Setup

pdfmill picks a print backend automatically (`settings.print_backend: auto`):

- **macOS / Linux**: CUPS via `lp` / `lpstat`. Add printers in System Settings (macOS) or your CUPS admin tool; nothing else to install.
- **Windows**: SumatraPDF. It is downloaded automatically on first print to `%LOCALAPPDATA%\pdfmill\SumatraPDF.exe`. To use your own copy, put `SumatraPDF.exe` in the current directory or on `PATH`, or set the `PDFMILL_SUMATRA_PATH` environment variable.

See [Printing](printing.md) for details.

## Verify Installation

Check that everything is working:

```sh
# Show version
pdfm --version

# List available printers
pdfm --list-printers
```

## Your First Config

Create a file called `my_config.yaml`:

```yaml
version: 1

input:
  path: ./input

outputs:
  rotated:
    pages: "all"
    transforms:
      - rotate: 90
    output_dir: ./output
```

Relative paths are resolved against the current working directory, not the config file's location.

## Run Your First Job

```sh
# Process input.path from the config (./input)
pdfm -c my_config.yaml

# Process a single PDF
pdfm -c my_config.yaml -i document.pdf

# Process a directory of PDFs into another output directory
pdfm -c my_config.yaml -i ./input -o ./output

# Preview: runs all transforms in a temp dir, prints and writes nothing
pdfm -c my_config.yaml --dry-run

# Validate config
pdfm -c my_config.yaml --validate
```

## Next Steps

- [Configuration Guide](configuration.md) - Learn the full config structure
- [Page Selection](page-selection.md) - Select specific pages
- [Transforms](transforms.md) - Rotate, crop, resize, and more
- [Printing](printing.md) - Send output to printers
- [Watch Mode](watch-mode.md) - Automatically process new files
