# Configuration Guide

pdfmill uses YAML configuration files to define processing pipelines. This guide covers the overall structure and common settings.

## Config File Structure

A config file has these top-level sections:

```yaml
version: 1

settings:
  # Global behavior settings

input:
  # Where to find PDFs and how to filter them

outputs:
  # One or more output profiles (required)

watch:
  # Watch mode settings (optional)
```

Relative paths in the config (`input.path`, `output_dir`) are relative to the current working directory, not to the config file.

## Settings

The `settings` section controls global behavior:

```yaml
settings:
  on_error: continue      # "continue" or "stop"
  cleanup_source: false   # Delete source files that fully succeeded
  cleanup_output_after_print: false  # Delete output files whose print succeeded
  print_backend: auto     # "auto", "cups" or "sumatra"
```

| Setting | Default | Description |
|---------|---------|-------------|
| `on_error` | `continue` | `continue` records the failure and moves on; `stop` aborts the run at the first error (nothing further is printed or cleaned up) |
| `cleanup_source` | `false` | Delete input files that succeeded (see below) |
| `cleanup_output_after_print` | `false` | Delete output files whose print job succeeded |
| `print_backend` | `auto` | `auto` = SumatraPDF on Windows, CUPS elsewhere. Overridden by `--backend` |

### What Counts as Success

Each source PDF is a unit of work. It succeeds only if **every enabled profile produced its output** and **every print job containing that output was accepted** by the printer system.

- `cleanup_source` deletes only sources that succeeded. A source with any failed profile or print job is kept, so you can fix the problem and run again.
- `cleanup_output_after_print` deletes only outputs whose print succeeded. Outputs of profiles without printing are never deleted.
- Nothing is deleted in a `--dry-run`.
- The exit code is `1` if anything failed.

## Output Profiles

The `outputs` section defines one or more processing profiles. Each profile can select different pages, apply different transforms, and send to different printers:

```yaml
outputs:
  packing_sheet:
    pages: "1"
    output_dir: ./output/sheets
    print:
      enabled: true
      printer: "Office_Printer"

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
      printer: "Label_Printer"
```

Profile names (like `packing_sheet` and `label`) are used in output filenames. `pages` is required in every profile.

## Enable/Disable

Profiles, transforms, and printing can be individually toggled without removing configuration:

```yaml
outputs:
  label:
    enabled: false          # Skip this entire profile
    pages: "last"
    transforms:
      - rotate: 90
        enabled: false      # Skip this transform (works on every transform type)
      - crop:
          lower_left: [0, 0]
          upper_right: [100, 100]
    print:
      enabled: true         # Would print if profile was enabled
      printer: "Label_Printer"
```

| Level | Field | Default | Description |
|-------|-------|---------|-------------|
| Profile | `enabled` | `true` | Skip entire profile when `false` |
| Transform | `enabled` | `true` | Skip this transform when `false` |
| Print | `print.enabled` | `false` | Printing is opt-in (must explicitly enable; requires a `printer` or `targets`) |

## Watch Settings

```yaml
watch:
  poll_interval: 2.0      # Seconds between polls
  debounce_delay: 1.0     # Seconds a file must be unchanged before processing
  process_existing: true  # Process files already present on startup
```

See [Watch Mode](watch-mode.md).

## Config Validation

Configs are validated strictly when loaded, before anything is processed:

- Unknown keys are errors, with a suggestion for the closest valid key
- Types, allowed values, and units are checked, and every message includes the YAML path of the problem

```
Configuration error: outputs.label.print: unknown key 'copise' (did you mean 'copies'?)
Configuration error: outputs.label.transforms[1].crop.lower_left: invalid length '10 inch' (use e.g. 100mm, 4in, 288pt, 10cm)
```

Validate your config before running:

```sh
# Check the config
pdfm -c config.yaml --validate

# Also check input path, printers (exist and ready) and optional dependencies
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
