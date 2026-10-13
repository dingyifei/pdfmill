# Printing

pdfmill sends output files to printers through one of two backends. This guide covers backend setup, single printer setup, multi-printer distribution, print safety, and common print settings.

## Backends

| Backend | Platforms | How it prints |
|---------|-----------|---------------|
| `cups` | macOS, Linux | `lp` / `lpstat` (CUPS is built into macOS) |
| `sumatra` | Windows | SumatraPDF |

The backend is chosen by `settings.print_backend` (or the `--backend` CLI flag):

```yaml
settings:
  print_backend: auto   # auto (default) | cups | sumatra
```

`auto` uses SumatraPDF on Windows and CUPS everywhere else.

### SumatraPDF on Windows

SumatraPDF is looked up in this order: the `PDFMILL_SUMATRA_PATH` environment variable, `SumatraPDF.exe` in the current directory, `%LOCALAPPDATA%\pdfmill\SumatraPDF.exe`, then `PATH`. If none is found, it is downloaded automatically on first print to `%LOCALAPPDATA%\pdfmill`.

## Prerequisites

```sh
# Verify available printers
pdfm --list-printers

# Check that every printer in the config exists and is ready
pdfm -c config.yaml --validate --strict
```

## Basic Print Setup

Enable printing in an output profile:

```yaml
outputs:
  label:
    pages: "last"
    print:
      enabled: true           # Must be true to print (default: false)
      printer: "PL80E-BT"     # Exact printer name from --list-printers
      copies: 1               # Number of copies
```

**Important:** Printing is opt-in. Set `enabled: true` to activate. `enabled: true` without a `printer` (or `targets`) is a config error.

## Printer Name

Use the exact printer name as shown by `pdfm --list-printers`. On macOS and Linux these are CUPS queue names, which usually use underscores instead of spaces:

```sh
$ pdfm --list-printers
Available printers (cups):
  Brother_HL_L2420DW
  PL80E-BT
```

```yaml
print:
  enabled: true
  printer: "Brother_HL_L2420DW"
```

On Windows, names are the ones shown in Windows printer settings (e.g. `Brother HL-L2420DW Printer`).

If a name is wrong, the error lists the available printers and suggests the closest match:

```
Printer 'Brother HL-L2420DW' not found. Did you mean 'Brother_HL_L2420DW'? Available printers: Brother_HL_L2420DW, PL80E-BT
```

## Merge Mode

The `merge` option controls how multiple output files are printed:

```yaml
print:
  enabled: true
  printer: "Brother_HL_L2420DW"
  merge: true    # Combine all outputs into one print job
  merge: false   # Print each file separately (default)
```

### When to Use Merge

- **`merge: true`**: All output files for the profile are combined into a single PDF before printing. Useful for batch processing where you want one continuous print job.

- **`merge: false`**: Each output file is sent as a separate print job. Default behavior.

Merged (and per-printer split) PDFs are written to a temporary directory and removed after the run; they never appear in the output directory.

## Print Options (CUPS)

On CUPS, `options` is a mapping that becomes `-o key=value` arguments to `lp`:

```yaml
print:
  enabled: true
  printer: "Brother_HL_L2420DW"
  options:
    sides: one-sided        # or two-sided-long-edge, two-sided-short-edge
    fit-to-page: true
```

### Common Options

| Option | Example | Description |
|--------|---------|-------------|
| `media` | `w284h426`, `Letter`, `A4` | Paper size (`w284h426` = 100x150mm / 4x6in label, size in points) |
| `sides` | `one-sided`, `two-sided-long-edge` | Simplex / duplex |
| `fit-to-page` | `true` | Scale to fit the paper |
| `print-color-mode` | `monochrome` | Force black and white |
| `orientation-requested` | `3` (portrait), `4` (landscape) | Orientation |

Printers also have their own (PPD) options. List them with:

```sh
lpoptions -p PL80E-BT -l
```

Values must be single values (YAML `true`/`false` become `true`/`false`). `options` are ignored with a warning on SumatraPDF.

## Backend Arguments

`args` is a raw list of extra arguments passed through to the backend command. On Windows, these are SumatraPDF arguments:

```yaml
print:
  enabled: true
  printer: "Brother HL-L2420DW Printer"
  args: ["-print-settings", "simplex"]
```

On CUPS, `args` are extra `lp` arguments (prefer `options` for `-o` settings). An item containing spaces is split shell-style, so `args: ["-print-settings simplex"]` also works.

### Common SumatraPDF Print Settings

| Setting | Description |
|---------|-------------|
| `simplex` | Single-sided printing |
| `duplex` | Double-sided, long edge binding |
| `duplexshort` | Double-sided, short edge binding |
| `color` | Force color printing |
| `monochrome` | Force black and white |
| `fit` | Fit to page |
| `shrink` | Shrink to fit (no enlarging) |
| `noscale` | Print at actual size |

```yaml
# Duplex printing
args: ["-print-settings", "duplex"]

# Fit to page, black and white
args: ["-print-settings", "fit,monochrome"]

# Multiple settings
args: ["-print-settings", "simplex,fit"]
```

## Multi-Printer Distribution

Distribute pages across multiple printers based on speed/capacity:

```yaml
print:
  enabled: true
  merge: true              # Required for page distribution
  targets:
    fast_printer:
      printer: "HP_LaserJet_Pro"
      weight: 100          # Higher = more pages
      copies: 1
    slow_printer:
      printer: "Brother_HL_L2420DW"
      weight: 50
      copies: 1
```

### How Distribution Works

When `merge: true` with multiple targets:

1. All output files are merged into one PDF
2. Pages are distributed based on weight ratio (targets with weight 0 get nothing)
3. Higher-weight printers get the first pages (for proper stacking order)

**Example:** 10 pages with weights 100:50
- Fast printer (weight 100): Pages 1-7
- Slow printer (weight 50): Pages 8-10

### Copy Mode

When `merge: false` with multiple targets, each file is sent to all printers:

```yaml
print:
  enabled: true
  merge: false             # Each file to each printer
  targets:
    office:
      printer: "HP_LaserJet_Pro"
      copies: 2            # 2 copies on this printer
    archive:
      printer: "Brother_HL_L2420DW"
      copies: 1            # 1 copy on this printer
```

### Target Options

| Option | Default | Description |
|--------|---------|-------------|
| `printer` | (required) | Printer name |
| `weight` | `1` | Page distribution weight |
| `copies` | `1` | Number of copies |
| `options` | `{}` | CUPS options (`-o key=value`) |
| `args` | `[]` | Raw backend arguments |

### Single Printer vs. Targets

`printer`, `copies`, `options` and `args` can be written directly under `print:` (single printer), or per target under `targets:`. The two forms cannot be mixed in one profile: with `targets:`, put every printer setting inside a target.

## Print Safety

Prevent accidentally printing too many pages or sending oversized documents to an incompatible printer:

```yaml
outputs:
  label:
    pages: "last"
    print:
      enabled: true
      printer: "PL80E-BT"
      max_pages: 50                    # Block if total pages exceed limit
      max_page_size: ["4.1in", "6.1in"] # Block if any page exceeds dimensions
      action: block                     # block | warn (default: block)
```

| Check | Description |
|-------|-------------|
| `max_pages` | Total page count of the profile's outputs in this run |
| `max_page_size` | Every page must fit, in either orientation |

- `block` (default): the profile is not printed and its sources count as failed
- `warn`: log a warning and print anyway

Safety checks fail closed: an output PDF that cannot be read counts as a violation.

## Reliability

- **Printers are checked first.** Before any job of a profile is sent, every printer of that profile is checked. A missing (or, on CUPS, paused or rejecting) printer fails the profile without sending anything to the others.
- **Success is per source PDF.** A source succeeds only if every enabled profile produced output and every print job containing it was accepted. If a profile's printing fails, all sources in that profile count as failed.
- **Cleanup only touches successes.** `cleanup_output_after_print` deletes only outputs whose print succeeded; `cleanup_source` deletes only sources that fully succeeded. Failed work is kept so you can re-run it.
- **Exit code** is `1` if anything failed.

## Cleanup After Print

Automatically delete output files after successful printing:

```yaml
settings:
  cleanup_output_after_print: true

outputs:
  label:
    pages: "last"
    print:
      enabled: true
      printer: "PL80E-BT"
```

## Complete Examples

### Label Printer on macOS (PL80E-BT)

A 4x6in (100x150mm) thermal label printer over Bluetooth, as in `configs/label_packing.yaml`:

```yaml
outputs:
  label:
    pages: last
    transforms:
      - rotate: 90
      - crop:
          lower_left: [90mm, 33mm]
          upper_right: [190mm, 183mm]
      - size:
          width: 100mm
          height: 150mm
          fit: stretch
    print:
      enabled: true
      merge: true
      targets:
        default:
          printer: PL80E-BT
          copies: 1
          options:
            media: w284h426   # 4x6in label (see: lpoptions -p PL80E-BT -l)
      max_page_size: [4.1in, 6.1in]
```

### Duplex Document Printing

```yaml
outputs:
  document:
    pages: "all"
    print:
      enabled: true
      printer: "HP_LaserJet_Pro"
      options:
        sides: two-sided-long-edge
        fit-to-page: true
```

On Windows, the equivalent is `args: ["-print-settings", "duplex,fit"]`.

### High-Volume Distribution

```yaml
outputs:
  batch:
    pages: "all"
    print:
      enabled: true
      merge: true
      targets:
        fast:
          printer: "HP_LaserJet_Pro"
          weight: 100     # 100 ppm
          options:
            sides: one-sided
        medium:
          printer: "Brother_HL_L2420DW"
          weight: 50      # 50 ppm
          options:
            sides: one-sided
```

### Separate Printers for Different Profiles

```yaml
outputs:
  packing_sheet:
    pages: "1--1"
    print:
      enabled: true
      printer: "Brother_HL_L2420DW"
      options:
        sides: one-sided

  label:
    pages: "last"
    transforms:
      - rotate: 90
    print:
      enabled: true
      printer: "PL80E-BT"
```

## Troubleshooting

### Printer Not Found

```sh
# List available printers
pdfm --list-printers

# Validate config with strict mode
pdfm -c config.yaml --validate --strict
```

The error message suggests the closest printer name. On CUPS, use the queue name (e.g. `Brother_HL_L2420DW`), not the display name.

### Printer Paused or Not Accepting Jobs (CUPS)

CUPS pauses ("disables") a queue after a backend error, for example when a Bluetooth printer was switched off. Jobs sent to a paused queue would sit there silently, so pdfmill refuses to print to it:

```
Printer 'PL80E-BT' is paused: printer PL80E-BT disabled since ...
Check the printer is on and connected, then resume it with: cupsenable PL80E-BT
```

Turn the printer on, check it is connected, then:

```sh
cupsenable PL80E-BT     # resume a paused queue
cupsaccept PL80E-BT     # if the queue is "not accepting" jobs
lpstat -p PL80E-BT      # check the status
```

Sources from the failed run were kept (not cleaned up), so just run pdfmill again.

### SumatraPDF Not Found (Windows)

SumatraPDF is downloaded automatically on first print. If the download is blocked, download SumatraPDF yourself and set `PDFMILL_SUMATRA_PATH` to the `.exe`, or place `SumatraPDF.exe` in the current directory.

### Test Without Printing

Use `--dry-run` to run all transforms in a temporary directory and see the exact print commands without printing, writing outputs, or deleting anything. Printers are still checked, so a dry run also catches missing or paused printers:

```sh
pdfm -c config.yaml --dry-run
```

```
[dry-run] Would run: lp -d PL80E-BT -n 1 -t 'label: label_merged.pdf' -o media=w284h426 -- /tmp/pdfmill-.../label_merged.pdf
```

## Related Documentation

- [Getting Started](getting-started.md) - Installation and printer setup
- [Output Profiles](output-profiles.md) - Profile configuration
- [Configuration Guide](configuration.md) - Settings and cleanup options
- [CLI Reference](cli-reference.md) - Command-line options
