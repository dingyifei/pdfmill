# Printing

pdfmill uses SumatraPDF to send output files to printers. This guide covers single printer setup, multi-printer distribution, and common print settings.

## Prerequisites

SumatraPDF must be installed:

```sh
# Download SumatraPDF (automatic on first use)
pdfm install

# Verify available printers
pdfm --list-printers
```

## Basic Print Setup

Enable printing in an output profile:

```yaml
outputs:
  label:
    pages: "last"
    print:
      enabled: true           # Must be true to print (default: false)
      printer: "Printer Name" # Exact printer name from --list-printers
      copies: 1               # Number of copies
```

**Important:** Printing is opt-in. Set `enabled: true` to activate.

## Printer Name

Use the exact printer name as shown by `pdfm --list-printers`:

```sh
$ pdfm --list-printers
Available printers:
  - HP LaserJet Pro
  - Brother HL-L2420DW
  - PL80E
```

```yaml
print:
  enabled: true
  printer: "Brother HL-L2420DW"
```

## Merge Mode

The `merge` option controls how multiple output files are printed:

```yaml
print:
  enabled: true
  printer: "Printer Name"
  merge: true    # Combine all outputs into one print job
  merge: false   # Print each file separately (default)
```

### When to Use Merge

- **`merge: true`**: All output files for the profile are combined into a single PDF before printing. Useful for batch processing where you want one continuous print job.

- **`merge: false`**: Each output file is sent as a separate print job. Default behavior.

## SumatraPDF Arguments

Pass additional arguments to SumatraPDF for print settings:

```yaml
print:
  enabled: true
  printer: "Brother HL-L2420DW"
  args: ["-print-settings", "simplex"]
```

### Common Print Settings

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
      printer: "HP LaserJet Pro"
      weight: 100          # Higher = more pages
      copies: 1
    slow_printer:
      printer: "Brother HL-L2420DW"
      weight: 50
      copies: 1
```

### How Distribution Works

When `merge: true` with multiple targets:

1. All output files are merged into one PDF
2. Pages are distributed based on weight ratio
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
      printer: "HP LaserJet Pro"
      copies: 2            # 2 copies on this printer
    archive:
      printer: "Brother HL-L2420DW"
      copies: 1            # 1 copy on this printer
```

### Target Options

| Option | Default | Description |
|--------|---------|-------------|
| `printer` | (required) | Printer name |
| `weight` | `1` | Page distribution weight |
| `copies` | `1` | Number of copies |
| `args` | `[]` | SumatraPDF arguments |

## Cleanup After Print

Automatically delete output files after successful printing:

```yaml
settings:
  cleanup_output_after_print: true

outputs:
  label:
    print:
      enabled: true
      printer: "Label Printer"
```

## Complete Examples

### Simple Label Printing

```yaml
outputs:
  label:
    pages: "last"
    transforms:
      - rotate: 90
    print:
      enabled: true
      printer: "PL80E"
      copies: 1
```

### Duplex Document Printing

```yaml
outputs:
  document:
    pages: "all"
    print:
      enabled: true
      printer: "HP LaserJet Pro"
      args: ["-print-settings", "duplex,fit"]
```

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
          printer: "HP LaserJet Pro"
          weight: 100     # 100 ppm
          args: ["-print-settings", "simplex"]
        medium:
          printer: "Brother HL-L2420DW"
          weight: 50      # 50 ppm
          args: ["-print-settings", "simplex"]
```

### Separate Printers for Different Profiles

```yaml
outputs:
  packing_sheet:
    pages: "1--1"
    print:
      enabled: true
      printer: "Office Printer"
      args: ["-print-settings", "simplex"]

  label:
    pages: "last"
    transforms:
      - rotate: 90
    print:
      enabled: true
      printer: "Label Printer"
```

## Troubleshooting

### Printer Not Found

```sh
# List available printers
pdfm --list-printers

# Validate config with strict mode
pdfm -c config.yaml --validate --strict
```

### SumatraPDF Not Found

```sh
# Install SumatraPDF
pdfm install
```

### Test Without Printing

Use `--dry-run` to preview what would be printed:

```sh
pdfm -c config.yaml -i ./input --dry-run
```

## Related Documentation

- [Getting Started](getting-started.md) - SumatraPDF installation
- [Output Profiles](output-profiles.md) - Profile configuration
- [Configuration Guide](configuration.md) - Settings and cleanup options
- [CLI Reference](cli-reference.md) - Command-line options
