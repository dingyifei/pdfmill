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

# SumatraPDF.exe will be automatically downloaded on first use
```

## Quick Start

```sh
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

## Configuration

Create a YAML config file to define your processing pipeline:

```yaml
version: 1

settings:
  on_error: continue  # or "stop"
  cleanup_source: false
  cleanup_output_after_print: false

outputs:
  packing_sheet:
    pages: "1--1"  # all pages except last
    output_dir: ./output
    filename_suffix: "_packing"
    print:
      enabled: true
      printer: "Canon G3060 series"

  label:
    pages: "last"
    transforms:
      - rotate: 270
      - crop:
          lower_left: [82, 260]
          upper_right: [514, 548]
    output_dir: ./output
    filename_suffix: "_label"
    print:
      enabled: true
      printer: "Label Printer"
```

### Input Filtering and Sorting

Filter which PDFs to process by filename pattern or text content, and control processing order:

```yaml
input:
  path: ./input
  pattern: "shipping_*.pdf"  # glob pattern for filenames
  sort: name_asc             # sort files before processing
  filter:
    keywords: ["shipping", "label"]  # text content keywords
    match: "any"  # "any" = OR logic, "all" = AND logic
```

| Option | Description |
|--------|-------------|
| `pattern` | Glob pattern for filename matching (default: `*.pdf`) |
| `sort` | Sort order: `name_asc`, `name_desc`, `time_asc`, `time_desc` |
| `filter.keywords` | List of keywords to search in PDF text content |
| `filter.match` | `"any"` matches if any keyword found, `"all"` requires all keywords |

Sorting can also be set per output profile using `sort:` at the profile level. If both input-level and profile-level sort are set, an error is raised.

Keyword matching is case-sensitive. PDFs without searchable text won't match keyword filters.

### Page Selection Syntax

| Syntax | Meaning |
|--------|---------|
| `[1, 2, 3]` | Exact pages 1, 2, 3 |
| `"1-3"` | Pages 1 through 3 |
| `"3-"` | Page 3 to end |
| `"-2"` | Last 2 pages |
| `"1--1"` | Page 1 to second-to-last |
| `"first"` | First page only |
| `"last"` | Last page only |
| `"odd"` | All odd-numbered pages |
| `"even"` | All even-numbered pages |
| `"all"` | All pages |

### Transforms

```yaml
transforms:
  # Rotate by degrees
  - rotate: 270  # 0, 90, 180, 270

  # Or rotate to orientation
  - rotate: landscape  # landscape, portrait

  # Crop to coordinates (supports units: mm, in, pt, cm)
  - crop:
      lower_left: [0, 0]           # raw points (72 per inch)
      upper_right: [288, 432]
  - crop:
      lower_left: ["10mm", "20mm"]  # with units
      upper_right: ["100mm", "150mm"]

  # Resize with units
  - size:
      width: 100mm   # supports: mm, in, pt, cm
      height: 150mm
      fit: contain   # contain, cover, stretch

  # Disable a transform without removing it
  - rotate: 90
    enabled: false  # skip this transform

  # Add page numbers or timestamps (requires: pip install pdfmill[stamp])
  - stamp: "{page}/{total}"   # simple format

  - stamp:                     # full configuration
      text: "Page {page} of {total}"
      position: bottom-right   # top-left, top-right, bottom-left, bottom-right, center, custom
      font_size: 10
      margin: "10mm"

  - stamp:                     # custom position
      text: "{datetime}"
      position: custom
      x: "50mm"
      y: "20mm"

  # Split: extract multiple regions from each page (1 page -> N pages)
  - split:
      regions:
        - lower_left: ["0in", "3in"]
          upper_right: ["4in", "6in"]
        - lower_left: ["4in", "3in"]
          upper_right: ["8in", "6in"]

  # Combine: place multiple pages onto one canvas (N pages -> 1 page)
  - combine:
      page_size: ["8.5in", "11in"]  # output page dimensions
      pages_per_output: 2            # input pages consumed per output
      layout:
        - page: 0                    # first input page (0-indexed)
          position: ["0in", "5.5in"] # lower-left corner position
          scale: 0.5                 # scale factor (0.5 = 50%)
        - page: 1
          position: ["0in", "0in"]
          scale: 0.5

  # Render (rasterize) - converts page to image
  - render: 300           # DPI value
  - render: {dpi: 200}    # Dict form
  - render: true          # Default 150 DPI
```

**Stamp Placeholders**:
| Placeholder | Description |
|-------------|-------------|
| `{page}` | Current page number (1-indexed) |
| `{total}` | Total page count |
| `{datetime}` | Current datetime (format: `YYYY-MM-DD HH:MM:SS`) |
| `{date}` | Current date (`YYYY-MM-DD`) |
| `{time}` | Current time (`HH:MM:SS`) |

**Note on render transform:** The render transform rasterizes pages to images and re-embeds them. This permanently removes any content outside the visible area (useful after cropping to truly remove hidden content) and flattens all layers, annotations, and transparency. Requires `poppler` to be installed on the system.

### Debug Mode

Enable `debug: true` on an output profile to save intermediate PDFs after each transform step:

```yaml
outputs:
  label:
    debug: true  # saves intermediate files
    pages: "last"
    transforms:
      - rotate: 90
      - crop:
          lower_left: ["33mm", "91mm"]
          upper_right: ["180mm", "192mm"]
    output_dir: ./output
```

This generates files showing each processing stage:
```
./output/
├── myfile_label_step0_selected.pdf   # after page selection
├── myfile_label_step1_rotate90.pdf   # after rotation
├── myfile_label_step2_crop.pdf       # after crop
└── myfile_label.pdf                  # final output
```

### Print Options

**Single printer (simple):**
```yaml
print:
  enabled: true
  printer: "Printer Name"
  copies: 1
  merge: true   # merge all PDFs before printing as single job
  args: []      # pass-through SumatraPDF arguments
```

When `merge: true` is set, all output files for that profile are combined into a single PDF before being sent to the printer. This is useful for batch printing where you want all pages in one print job.

**Multi-printer distribution:**
```yaml
print:
  enabled: true
  merge: true
  targets:
    fast_printer:
      printer: "HP LaserJet"
      weight: 100    # higher = more pages (e.g., printer's ppm)
      copies: 1
    slow_printer:
      printer: "Brother"
      weight: 50
      copies: 1
```

When multiple targets are configured with `merge: true`:
- Pages are distributed across printers based on weight ratio
- Higher-weight printers get the first pages (for proper stacking order)
- Example: 10 pages with weights 100:50 → fast gets pages 1-7, slow gets 8-10

When `merge: false` with multiple targets:
- Each file is sent to all targets (copy distribution)
- Each target uses its own `copies` count

| Target Option | Description |
|---------------|-------------|
| `printer` | Printer name (required) |
| `weight` | Page distribution weight (default: 1) |
| `copies` | Number of copies (default: 1) |
| `args` | Pass-through SumatraPDF arguments |

### Enable/Disable

Profiles, transforms, and printing can be individually enabled/disabled without removing configuration:

```yaml
outputs:
  label:
    enabled: false          # Skip this profile entirely
    pages: last
    transforms:
      - rotate: 90
        enabled: false      # Skip this transform
      - crop:
          lower_left: [0, 0]
          upper_right: [100, 100]
    print:
      enabled: true         # Would print if profile was enabled
```

| Level | Field | Default | Description |
|-------|-------|---------|-------------|
| Profile | `enabled` | `true` | Skip entire profile when `false` |
| Transform | `enabled` | `true` | Skip this transform when `false` |
| Print | `print.enabled` | `false` | Printing is opt-in |

## Example Configs

See the `configs/` directory for ready-to-use examples:

- `label_packing.yaml` - Split PDFs into packing sheet + shipping label
- `six_page.yaml` - Process 6-page PDFs (remove pages 1-2, rotate pages 4-5)
- `multi_printer.yaml` - Multi-printer distribution with sorting

## Requirements

- Python 3.10+
- Windows 10 or newer

## License

MIT License
