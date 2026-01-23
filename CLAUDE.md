# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pdfmill` - A pip-installable Python package for configurable PDF processing. Splits multi-page PDFs, applies transformations (rotate, crop, resize, stamp, split, combine), and prints to different printers via SumatraPDF. Configured via YAML files.

## Setup

```sh
# Install package in development mode
pip install -e .

# Place SumatraPDF.exe in the repository root for printing
```

**Dependencies**: pypdf, PyYAML, pywin32 (Windows only), SumatraPDF (portable exe)

**Optional dependencies**:
- `pip install pdfmill[stamp]` - For stamp transform (adds reportlab)
- `pip install pdfmill[ocr]` - For auto-rotation via OCR (adds pymupdf, pytesseract, Pillow)
- `pip install pdfmill[watch]` - For watch mode (adds watchdog)

## Commands

```sh
# List available printers
pdfm --list-printers

# Process PDFs with a config
pdfm -c configs/label_packing.yaml -i ./input -o ./output

# Validate config only
pdfm -c config.yaml --validate

# Dry run (preview without processing)
pdfm -c config.yaml -i ./input --dry-run

# Verbose output (-v for verbose, -vv for debug)
pdfm -c config.yaml -i ./input -vv

# Quiet mode (errors only)
pdfm -c config.yaml -i ./input -q

# Log to file
pdfm -c config.yaml -i ./input --log-file output.log

# Watch mode - process new files as they appear
pdfm -c config.yaml -i ./input --watch

# Watch mode with dry-run preview
pdfm -c config.yaml -i ./input --watch --dry-run

# Watch mode - skip existing files on startup
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

## Architecture

```
src/pdfmill/
├── cli.py              # Entry point, argparse CLI
├── config.py           # YAML config loading, dataclass models
├── logging_config.py   # Logging setup, formatters, verbosity control
├── selector.py         # Page selection (patterns, ranges, indices)
├── transforms.py       # Rotate, crop, resize operations
├── printer.py          # SumatraPDF wrapper, printer enumeration
├── processor.py        # Main pipeline orchestration
└── watcher.py          # Watch mode for monitoring input directory
```

### Module Responsibilities

- **cli.py** - Parses args, dispatches to processor or utility commands
- **config.py** - Loads YAML, validates structure, returns typed `Config` dataclass
- **logging_config.py** - Configures Python logging with verbosity levels, console/file handlers
- **selector.py** - Converts page specs (`"last"`, `"1-3"`, `[-1]`) to 0-indexed page list
- **transforms.py** - Applies rotate/crop/resize/stamp/render/split/combine to pypdf page objects
- **printer.py** - Finds SumatraPDF, sends print jobs with pass-through args
- **processor.py** - Orchestrates: load config → get files → select pages → transform → write → print
- **watcher.py** - Monitors input directory for new PDFs, tracks processed files via JSON state

## Config Structure

```yaml
version: 1
settings:
  on_error: continue|stop
  cleanup_source: false
  cleanup_output_after_print: false

watch:
  poll_interval: 2.0      # Polling interval in seconds (default: 2.0)
  debounce_delay: 1.0     # File stability wait time in seconds (default: 1.0)
  process_existing: true  # Process existing files on startup (default: true)

input:
  path: ./input
  pattern: "*.pdf"            # Glob pattern for filenames
  sort: name_asc              # Sort order: name_asc, name_desc, time_asc, time_desc
  filter:
    keywords: ["shipping"]    # Filter by text content (case-sensitive)
    match: "any"              # "any" (OR) or "all" (AND)

outputs:
  profile_name:
    enabled: true           # Set to false to skip this profile
    pages: "last"           # Page selection spec
    transforms:             # List of transforms
      - rotate: 90
        enabled: true       # Set to false to skip this transform
    output_dir: ./output
    filename_prefix: ""
    filename_suffix: ""
    sort: time_desc         # Override input.sort (error if both set)
    debug: false            # Save intermediate PDFs after each transform
    print:
      enabled: true         # Set to false to disable printing (default: false)
      merge: false          # Merge all PDFs before printing as single job
      # Single printer (legacy, still supported):
      printer: "Printer Name"
      copies: 1
      args: []
      # Or multi-printer targets:
      targets:
        fast:
          printer: "HP LaserJet"
          weight: 100       # Page distribution weight (ppm/ipm)
          copies: 1
          args: []
        slow:
          printer: "Brother"
          weight: 50
          copies: 1
```

## Enable/Disable

Profiles, transforms, and printing can be individually enabled/disabled:

| Level | Field | Default | Description |
|-------|-------|---------|-------------|
| Profile | `enabled` | `true` | Skip entire profile when `false` |
| Transform | `enabled` | `true` | Skip this transform when `false` |
| Print | `print.enabled` | `false` | Printing is opt-in (must set `true` to print) |

```yaml
outputs:
  label:
    enabled: false          # Temporarily disable this profile
    pages: last
    transforms:
      - rotate: 90
        enabled: false      # Skip rotation
      - crop:
          lower_left: [0, 0]
          upper_right: [100, 100]
    print:
      enabled: true         # Would print if profile was enabled
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

## Stamp Transform

Add page numbers, timestamps, or custom text to PDFs. Requires `pip install pdfmill[stamp]`.

```yaml
transforms:
  # Simple: page numbers in bottom-right
  - stamp: "{page}/{total}"

  # Full configuration
  - stamp:
      text: "Page {page} of {total}"    # Text with placeholders
      position: bottom-right             # top-left, top-right, bottom-left, bottom-right, center, custom
      font_size: 10
      font_name: Helvetica               # PDF standard fonts
      margin: "10mm"                     # Margin from edge (for preset positions)
      datetime_format: "%Y-%m-%d %H:%M:%S"

  # Custom position
  - stamp:
      text: "{datetime}"
      position: custom
      x: "50mm"
      y: "20mm"
```

**Placeholders**:
- `{page}` - Current page number (1-indexed)
- `{total}` - Total page count
- `{datetime}` - Current datetime (uses `datetime_format`)
- `{date}` - Current date (YYYY-MM-DD)
- `{time}` - Current time (HH:MM:SS)

**Position presets**: `top-left`, `top-right`, `bottom-left`, `bottom-right`, `center`, `custom`

## Split Transform

Extracts multiple regions from each page, creating separate output pages. Useful for splitting label sheets or multi-up documents.

```yaml
- split:
    regions:
      - lower_left: ["0in", "3in"]
        upper_right: ["4in", "6in"]
      - lower_left: ["4in", "3in"]
        upper_right: ["8in", "6in"]
```

Each input page produces N output pages (one per region).

## Combine Transform

Places multiple input pages onto a single output page. Useful for creating n-up layouts or booklets.

```yaml
- combine:
    page_size: ["8.5in", "11in"]    # Output page dimensions
    pages_per_output: 2              # Input pages consumed per output
    layout:
      - page: 0                      # First input page
        position: ["0in", "5.5in"]   # Lower-left corner position
        scale: 0.5                   # Scale factor (0.5 = 50%)
      - page: 1                      # Second input page
        position: ["0in", "0in"]
        scale: 0.5
```

Input pages are batched by `pages_per_output`, and each batch produces one combined page.

## Render Transform

The `render` transform rasterizes pages to images and re-embeds them. This permanently removes content outside the visible area and flattens all layers.

```yaml
# Render (rasterize) page
- render: 300           # Just DPI value
- render: {dpi: 200}    # Dict form with options
- render: true          # Default 150 DPI
```

Requires `poppler` installed on the system (used by pdf2image).

## Watch Mode

Monitor an input directory and automatically process new PDF files as they appear. Requires `pip install pdfmill[watch]`.

```sh
# Basic watch mode
pdfm -c config.yaml -i ./input --watch

# With dry-run to preview without processing
pdfm -c config.yaml -i ./input --watch --dry-run

# Skip existing files on startup
pdfm -c config.yaml -i ./input --watch --no-process-existing

# Custom polling interval and debounce
pdfm -c config.yaml -i ./input --watch --watch-interval 5.0 --watch-debounce 2.0
```

**Options**:
- `--watch` - Enable watch mode
- `--watch-interval` - Polling interval in seconds (default: 2.0, used for network drives)
- `--watch-debounce` - Wait time for file stability check (default: 1.0)
- `--watch-state` - Custom path for state file (default: `.pdfmill_watch_state.json` in input dir)
- `--no-process-existing` - Skip files that exist when watch mode starts

**State Tracking**:
- Processed files are tracked in `.pdfmill_watch_state.json` to avoid reprocessing after restarts
- State resets automatically when config changes (detected via hash)
- Files are only reprocessed if their size or modification time changes

**File Monitoring**:
- Uses native OS file events via `watchdog` library for immediate detection
- Falls back to polling for network drives (UNC paths)
- Debounces file events to wait for files being written to complete

**Config File Settings**:

Watch settings can also be configured in the YAML config file:

```yaml
watch:
  poll_interval: 2.0      # Polling interval in seconds (default: 2.0)
  debounce_delay: 1.0     # File stability wait time in seconds (default: 1.0)
  process_existing: true  # Process existing files on startup (default: true)
```

These settings are saved/loaded with the config and used by the GUI's Watch tab.

## Key Constants

Default label cropping coordinates (4x6" at 72 DPI):
- `lower_left: [82, 260]`
- `upper_right: [514, 548]`
