# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pdfmill` (CLI: `pdfm`) is a pip-installable Python package for configurable PDF processing. It selects pages from PDFs, applies transforms (rotate, crop, size, stamp, split, combine, render), writes the outputs, and prints them. Printing goes through CUPS (`lp`/`lpstat`) on macOS/Linux or SumatraPDF on Windows. Everything is configured with YAML files in `configs/`. User docs are in `docs/`.

The main use case is shipping labels on macOS. The label printer is the CUPS queue `PL80E-BT` (Bluetooth, 203 dpi, media `w284h426` = 4x6in / 100x150mm). The packing slip printer is `Brother_HL_L2420DW`. See `configs/label_packing.yaml`.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,stamp,ocr]'
brew install poppler tesseract   # only for the render transform and rotate: auto
```

Dependencies: pypdf and PyYAML, plus pywin32 on Windows. Extras: `stamp` (reportlab) and `ocr` (pdf2image, pytesseract, Pillow).

## Commands

```sh
.venv/bin/pytest                         # tests + coverage (fail_under = 80)
.venv/bin/ruff check . && .venv/bin/ruff format --check .

pdfm --list-printers                     # CUPS queue names to use as `printer:`
pdfm -c configs/label_packing.yaml --validate --strict   # config + printers + deps
pdfm -c configs/label_packing.yaml --dry-run             # full run in a temp dir, logs lp commands
pdfm -c configs/label_packing.yaml                       # -i defaults to input.path
pdfm -c configs/label_packing.yaml --watch               # poll input dir, process new PDFs once
```

## Architecture

```
src/pdfmill/
├── cli.py              # argparse entry point; exit 1 if anything failed
├── config.py           # YAML -> dataclasses, strict validation (unknown keys are errors)
├── schema.py           # ConfigError + check_keys/choice/typed/pair helpers
├── units.py            # to_points("100mm" | "4in" | 72)
├── selector.py         # page specs ("last", "1-3", "1--1", [1, 3]) -> 0-indexed list
├── processor.py        # process() -> RunResult: select, transform, write, print, clean up
├── watcher.py          # polling watch mode with a JSON state file
├── logging_config.py
├── transforms/
│   ├── __init__.py     # TRANSFORMS registry, parse_transform(), apply_all() (+ debug steps)
│   ├── _page.py        # normalize(), set_box(), clone(), size(), TransformError
│   └── rotate.py crop.py resize.py stamp.py split.py combine.py render.py
└── printing/
    ├── __init__.py     # print_profile(): safety check, check printers, merge, split by weight, print
    ├── backend.py      # Backend protocol, PrinterError, get_backend()
    ├── cups.py         # lp / lpstat
    └── sumatra.py      # SumatraPDF (Windows)
```

To add a transform, write a module in `transforms/` that exposes `NAME`, `parse(value, where) -> options`, `apply(pages, options) -> pages` and `describe(options) -> str`, then add it to `_MODULES` in `transforms/__init__.py`. `parse` must validate everything and raise `ConfigError` with the `where` path. Values are converted to points at parse time.

## Invariants (don't break these)

- **Cleanup only touches success.** A source PDF succeeds only if every enabled profile produced output *and* every print job containing that output returned a job id. `cleanup_source` deletes only succeeded sources, and `cleanup_output_after_print` deletes only outputs that printed. Backends raise `PrinterError`; they never return a boolean.
- **Check every printer first.** `print_profile` checks all of a profile's printers before sending any job. The CUPS backend refuses queues that are missing, not accepting, or paused (`disabled`). A paused queue would hold jobs silently.
- **Safety checks fail closed.** An unreadable PDF counts as a `max_pages`/`max_page_size` violation.
- **Normalized geometry.** `apply_all` calls `normalize()` on every page first, which bakes `/Rotate` into the content and moves the CropBox to (0,0). Transforms change size only through `set_box()`, which keeps MediaBox, CropBox, TrimBox, BleedBox and ArtBox identical. CUPS on macOS rasterizes the CropBox.
- **Clone shared pages.** Use `clone()` whenever the same source page is used twice (split, combine, duplicate page selection). pypdf copies share content streams.
- **Temp files stay in the temp dir.** Merged and split print files are written to the run's temp dir. A dry run does all the work there, logs the backend commands, and never writes outputs, prints or deletes anything.
- **Watch processes each file once.** A file must be stable across two polls and at least `debounce_delay` old. State is keyed by name+size+mtime and survives config edits. Failed files are not retried until they change or watch restarts, because a retry could reprint profiles that already printed.
- **Rotation direction.** `rotate_page` turns counter-clockwise. Tesseract OSD reports the clockwise correction, so `detect_orientation` returns `360 - rotate`.

## Config cheat sheet

Full reference: `docs/configuration.md`, `docs/transforms.md`, `docs/printing.md`.

```yaml
version: 1
settings: {on_error: continue|stop, cleanup_source: false, cleanup_output_after_print: false, print_backend: auto|cups|sumatra}
watch: {poll_interval: 2.0, debounce_delay: 1.0, process_existing: true}
input: {path: input, pattern: "*.pdf", sort: name_asc, filter: {keywords: [], match: any}}
outputs:
  label:
    pages: last
    transforms:
      - rotate: 90                       # or {angle: 90, pages: [0]}, landscape, portrait, auto
      - crop: {lower_left: [90mm, 33mm], upper_right: [190mm, 183mm]}
      - size: {width: 100mm, height: 150mm, fit: stretch}   # contain | cover | stretch
    output_dir: output
    print:
      enabled: true
      merge: true
      printer: PL80E-BT                  # or targets: {name: {printer, weight, copies, args, options}}
      options: {media: w284h426}         # CUPS -o key=value
      max_page_size: [4.1in, 6.1in]      # also max_pages, action: block|warn
```
