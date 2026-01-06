# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pdfmill` - A pip-installable Python package for configurable PDF processing. Splits multi-page PDFs, applies transformations (rotate, crop, resize), and prints to different printers via SumatraPDF. Configured via YAML files.

## Setup

```sh
# Install package in development mode
pip install -e .

# Place SumatraPDF.exe in the repository root for printing
```

**Dependencies**: pypdf, PyYAML, pywin32 (Windows only), SumatraPDF (portable exe)

## Commands

```sh
# List available printers
pdfp --list-printers

# Process PDFs with a config
pdfp -c configs/label_packing.yaml -i ./input -o ./output

# Validate config only
pdfp -c config.yaml --validate

# Dry run (preview without processing)
pdfp -c config.yaml -i ./input --dry-run
```

## Architecture

```
src/pdfpipe/
├── cli.py          # Entry point, argparse CLI
├── config.py       # YAML config loading, dataclass models
├── selector.py     # Page selection (patterns, ranges, indices)
├── transforms.py   # Rotate, crop, resize operations
├── printer.py      # SumatraPDF wrapper, printer enumeration
└── processor.py    # Main pipeline orchestration
```

### Module Responsibilities

- **cli.py** - Parses args, dispatches to processor or utility commands
- **config.py** - Loads YAML, validates structure, returns typed `Config` dataclass
- **selector.py** - Converts page specs (`"last"`, `"1-3"`, `[-1]`) to 0-indexed page list
- **transforms.py** - Applies rotate/crop/resize to pypdf page objects
- **printer.py** - Finds SumatraPDF, sends print jobs with pass-through args
- **processor.py** - Orchestrates: load config → get files → select pages → transform → write → print

## Config Structure

```yaml
version: 1
settings:
  on_error: continue|stop
  cleanup_source: false
  cleanup_output_after_print: false

input:
  path: ./input
  pattern: "*.pdf"            # Glob pattern for filenames
  filter:
    keywords: ["shipping"]    # Filter by text content (case-sensitive)
    match: "any"              # "any" (OR) or "all" (AND)

outputs:
  profile_name:
    pages: "last"           # Page selection spec
    transforms: []          # List of transforms
    output_dir: ./output
    filename_prefix: ""
    filename_suffix: ""
    debug: false            # Save intermediate PDFs after each transform
    print:
      enabled: true
      printer: "Printer Name"
      copies: 1
      merge: false          # Merge all PDFs before printing as single job
      args: []              # Pass-through SumatraPDF args
```

## Units

Crop and resize support unit strings: `mm`, `in`, `pt`, `cm` (72 pt = 1 inch)

```yaml
# Crop with units
- crop:
    lower_left: ["10mm", "20mm"]
    upper_right: ["100mm", "150mm"]

# Or raw points (backwards compatible)
- crop:
    lower_left: [72, 144]
    upper_right: [288, 432]
```

## Key Constants

Default label cropping coordinates (4x6" at 72 DPI):
- `lower_left: [82, 260]`
- `upper_right: [514, 548]`
