# CLI Reference

Complete reference for the `pdfm` command-line interface.

## Synopsis

```sh
pdfm [OPTIONS] [COMMAND]
```

## Commands

### install

Download and install SumatraPDF for printing support.

```sh
pdfm install
```

### uninstall

Remove the SumatraPDF installation.

```sh
pdfm uninstall
```

### gui

Launch the graphical configuration editor.

```sh
pdfm gui
```

## Options

### Processing Options

| Option | Description |
|--------|-------------|
| `-c, --config FILE` | Path to YAML configuration file (required for processing) |
| `-i, --input PATH` | Input PDF file or directory (overrides config `input.path`) |
| `-o, --output DIR` | Output directory (overrides config `output_dir`) |

```sh
# Process with config
pdfm -c config.yaml -i ./input

# Override output directory
pdfm -c config.yaml -i ./input -o ./custom_output

# Process single file
pdfm -c config.yaml -i document.pdf
```

### Validation Options

| Option | Description |
|--------|-------------|
| `--validate` | Validate config syntax and exit |
| `--strict` | With `--validate`: also verify printers exist and paths are valid |

```sh
# Basic syntax check
pdfm -c config.yaml --validate

# Full validation including external resources
pdfm -c config.yaml --validate --strict
```

### Preview Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would happen without processing |

```sh
# Preview without making changes
pdfm -c config.yaml -i ./input --dry-run
```

### Watch Mode Options

| Option | Default | Description |
|--------|---------|-------------|
| `--watch` | - | Enable watch mode |
| `--watch-interval` | `2.0` | Polling interval in seconds (for network drives) |
| `--watch-debounce` | `1.0` | Debounce delay for file stability check |
| `--watch-state` | auto | Path to state file for tracking processed files |
| `--no-process-existing` | - | Skip files that exist when watch mode starts |

```sh
# Watch directory for new files
pdfm -c config.yaml -i ./input --watch

# Watch with dry-run preview
pdfm -c config.yaml -i ./input --watch --dry-run

# Skip existing files on startup
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

See [Watch Mode](watch-mode.md) for detailed documentation.

### Information Options

| Option | Description |
|--------|-------------|
| `-V, --version` | Show version information |
| `--list-printers` | List available system printers |

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
# 1. Validate syntax
pdfm -c config.yaml --validate

# 2. Validate with external checks
pdfm -c config.yaml --validate --strict

# 3. Preview processing
pdfm -c config.yaml -i ./input --dry-run

# 4. Process for real
pdfm -c config.yaml -i ./input
```

### Setup Workflow

```sh
# 1. Install SumatraPDF
pdfm install

# 2. Check available printers
pdfm --list-printers

# 3. Create and validate config
pdfm -c my_config.yaml --validate

# 4. Process files
pdfm -c my_config.yaml -i ./input
```

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success |
| `1` | General error (invalid config, processing failure) |
| `2` | Command-line argument error |

## Related Documentation

- [Getting Started](getting-started.md) - Installation guide
- [Configuration Guide](configuration.md) - Config file structure
- [Watch Mode](watch-mode.md) - Automatic file processing
- [Printing](printing.md) - Print setup and troubleshooting
