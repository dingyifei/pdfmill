# CLI Reference

Complete reference for the `pdfm` command-line interface.

## Synopsis

```sh
pdfm [OPTIONS]
```

There are no subcommands; everything is controlled by options. Run `pdfm --help` for a summary.

## Options

### Processing Options

| Option | Description |
|--------|-------------|
| `-c, --config FILE` | Path to YAML configuration file (required for processing) |
| `-i, --input PATH` | Input PDF file or directory (default: `input.path` from the config) |
| `-o, --output DIR` | Output directory for every profile (overrides each profile's `output_dir`) |
| `--backend {auto,cups,sumatra}` | Print backend (overrides `settings.print_backend`) |

Relative paths (on the command line and in the config) are relative to the current working directory.

```sh
# Process input.path from the config
pdfm -c config.yaml

# Process another directory
pdfm -c config.yaml -i ./input

# Override output directory
pdfm -c config.yaml -i ./input -o ./custom_output

# Process single file
pdfm -c config.yaml -i document.pdf
```

### Validation Options

| Option | Description |
|--------|-------------|
| `--validate` | Load and validate the config, then exit |
| `--strict` | With `--validate`: also check that the input path exists, every printer used by an enabled profile exists and is ready, and optional dependencies for the transforms in use are installed |

```sh
# Config check (unknown keys, types, values, units)
pdfm -c config.yaml --validate

# Also check input path, printers and dependencies
pdfm -c config.yaml --validate --strict
```

The dependency check covers Python packages (`reportlab` for `stamp`, `pdf2image` for `render`, `pytesseract` + `pdf2image` for `rotate: auto`); it does not check for the `poppler` or `tesseract` programs.

### Preview Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Run all transforms in a temporary directory and log the exact print commands, without printing, writing outputs, or deleting anything |

```sh
# Preview without making changes
pdfm -c config.yaml --dry-run
```

Example output line:

```
[dry-run] Would run: lp -d PL80E-BT -n 1 -t 'label: label_merged.pdf' -o media=w284h426 -- /tmp/pdfmill-.../label_merged.pdf
```

### Watch Mode Options

| Option | Default | Description |
|--------|---------|-------------|
| `--watch` | - | Enable watch mode (input must be a directory) |
| `--watch-interval` | `watch.poll_interval` (2.0) | Seconds between polls |
| `--watch-debounce` | `watch.debounce_delay` (1.0) | Seconds a file must be unchanged before processing |
| `--watch-state` | `<input>/.pdfmill_watch_state.json` | Path to state file for tracking processed files |
| `--no-process-existing` | `watch.process_existing` | Skip files that exist when watch mode starts |

CLI flags override the config's `watch:` section.

```sh
# Watch input.path for new files
pdfm -c config.yaml --watch

# Watch with dry-run preview
pdfm -c config.yaml -i ./input --watch --dry-run

# Skip existing files on startup
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

See [Watch Mode](watch-mode.md) for detailed documentation.

### Logging Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Verbose output; `-vv` for debug output (including the commands run) |
| `-q, --quiet` | Errors only |
| `--log-file FILE` | Also write all log levels to this file |

### Information Options

| Option | Description |
|--------|-------------|
| `-V, --version` | Print the version and exit |
| `--list-printers` | List available printers for the current backend (combine with `--backend` to pick one) |

```sh
# Show version
pdfm --version

# List printers
pdfm --list-printers
```

## Usage Examples

### Basic Processing

```sh
# Process directory with config
pdfm -c configs/label_packing.yaml -i ./input -o ./output

# Process single file
pdfm -c config.yaml -i document.pdf
```

### Validation Workflow

```sh
# 1. Validate config
pdfm -c config.yaml --validate

# 2. Validate with printer, path and dependency checks
pdfm -c config.yaml --validate --strict

# 3. Preview processing and print commands
pdfm -c config.yaml --dry-run

# 4. Process for real
pdfm -c config.yaml
```

### Setup Workflow

```sh
# 1. Check available printers (CUPS queue names on macOS/Linux)
pdfm --list-printers

# 2. Create and validate config
pdfm -c my_config.yaml --validate --strict

# 3. Process files
pdfm -c my_config.yaml -i ./input
```

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | Something failed: invalid config, a source PDF that did not fully succeed (any profile or print job failed), strict validation failure, or no printers found |
| `2` | Command-line argument error |

## Related Documentation

- [Getting Started](getting-started.md) - Installation guide
- [Configuration Guide](configuration.md) - Config file structure
- [Watch Mode](watch-mode.md) - Automatic file processing
- [Printing](printing.md) - Print setup and troubleshooting
