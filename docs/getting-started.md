# Getting Started

This guide walks you through installing pdfmill and running your first PDF processing job.

## Prerequisites

- Python 3.10 or newer
- Windows 10 or newer

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
pip install pdfmill[stamp]

# For auto-rotation via OCR (adds pymupdf, pytesseract, Pillow)
pip install pdfmill[ocr]
```

## SumatraPDF Setup

pdfmill uses SumatraPDF for printing. It will be downloaded automatically on first use, or you can install it manually:

```sh
# Download SumatraPDF
pdfm install

# Remove SumatraPDF
pdfm uninstall
```

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

outputs:
  rotated:
    pages: "all"
    transforms:
      - rotate: 90
    output_dir: ./output
```

## Run Your First Job

```sh
# Process a single PDF
pdfm -c my_config.yaml -i document.pdf

# Process a directory of PDFs
pdfm -c my_config.yaml -i ./input -o ./output

# Preview without processing
pdfm -c my_config.yaml -i ./input --dry-run

# Validate config syntax
pdfm -c my_config.yaml --validate
```

## Next Steps

- [Configuration Guide](configuration.md) - Learn the full config structure
- [Page Selection](page-selection.md) - Select specific pages
- [Transforms](transforms.md) - Rotate, crop, resize, and more
- [Printing](printing.md) - Send output to printers
