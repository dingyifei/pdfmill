# Configuration Guide

pdfmill uses YAML configuration files to define processing pipelines. This guide covers the overall structure and common settings.

## Config File Structure

A config file has four main sections:

```yaml
version: 1

settings:
  # Global behavior settings

input:
  # Where to find PDFs and how to filter them

outputs:
  # One or more output profiles
```

## Settings

The `settings` section controls global behavior:

```yaml
settings:
  on_error: continue      # "continue" or "stop"
  cleanup_source: false   # Delete source files after processing
  cleanup_output_after_print: false  # Delete output files after printing
```

| Setting | Default | Description |
|---------|---------|-------------|
| `on_error` | `continue` | `continue` skips failed files, `stop` halts on first error |
| `cleanup_source` | `false` | Delete input files after successful processing |
| `cleanup_output_after_print` | `false` | Delete output files after successful printing |

## Output Profiles

The `outputs` section defines one or more processing profiles. Each profile can select different pages, apply different transforms, and send to different printers:

```yaml
outputs:
  packing_sheet:
    pages: "1"
    output_dir: ./output/sheets
    print:
      enabled: true
      printer: "Office Printer"

  label:
    pages: "last"
    transforms:
      - rotate: 90
      - crop:
          lower_left: ["10mm", "20mm"]
          upper_right: ["100mm", "150mm"]
    output_dir: ./output/labels
    print:
      enabled: true
      printer: "Label Printer"
```

Profile names (like `packing_sheet` and `label`) are used in output filenames.

## Enable/Disable

Profiles, transforms, and printing can be individually toggled without removing configuration:

```yaml
outputs:
  label:
    enabled: false          # Skip this entire profile
    pages: "last"
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
| Print | `print.enabled` | `false` | Printing is opt-in (must explicitly enable) |

## Config Validation

Validate your config before running:

```sh
# Check syntax
pdfm -c config.yaml --validate

# Check syntax + verify printers exist and paths are valid
pdfm -c config.yaml --validate --strict
```

## Example Configs

See the `configs/` directory for ready-to-use examples:

- `label_packing.yaml` - Split PDFs into packing sheet + shipping label
- `six_page.yaml` - Process 6-page PDFs (remove pages, rotate others)
- `multi_printer.yaml` - Multi-printer distribution with sorting

## Related Documentation

- [Input Configuration](input.md) - Filter and sort input files
- [Page Selection](page-selection.md) - Select which pages to process
- [Transforms](transforms.md) - Apply transformations
- [Output Profiles](output-profiles.md) - Configure output settings
- [Printing](printing.md) - Send to printers
