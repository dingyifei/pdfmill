# Watch Mode

Monitor an input directory and automatically process new PDF files as they appear.

## Installation

Watch mode requires the `watchdog` library. Install it with:

```sh
pip install pdfmill[watch]
```

## Basic Usage

```sh
# Watch a directory and process new files
pdfm -c config.yaml -i ./input --watch

# Preview mode (see what would happen without processing)
pdfm -c config.yaml -i ./input --watch --dry-run

# Skip existing files when starting
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--watch` | - | Enable watch mode |
| `--watch-interval` | `2.0` | Polling interval in seconds (for network drives) |
| `--watch-debounce` | `1.0` | Debounce delay for file stability check |
| `--watch-state` | auto | Path to state file for tracking processed files |
| `--no-process-existing` | - | Skip files that exist when watch mode starts |

## How It Works

1. **Startup**: When watch mode starts, it processes all existing PDF files in the input directory (unless `--no-process-existing` is specified)

2. **Monitoring**: The watcher monitors the input directory for new files using:
   - Native OS file events (via `watchdog` library) for local drives
   - Polling-based detection for network drives (UNC paths like `\\server\share`)

3. **File Stability**: When a new file is detected, the watcher waits for it to stabilize (size and modification time stop changing) before processing. This handles files that are being copied or downloaded.

4. **Processing**: Each new PDF is processed using the same pipeline as batch mode (transforms, output profiles, printing)

5. **State Tracking**: Processed files are recorded to avoid reprocessing after restarts

## State Tracking

Watch mode tracks which files have been processed in a JSON state file:

- **Default location**: `.pdfmill_watch_state.json` in the input directory
- **Custom location**: Use `--watch-state /path/to/state.json`

The state file contains:
- Config hash (to detect config changes)
- List of processed files with their size and modification time

### State Reset

The state automatically resets when:
- The config file changes (detected via hash)
- The state file is deleted manually
- A file's size or modification time changes (it will be reprocessed)

## Examples

### Basic Watch Mode

Process PDFs as they appear in a directory:

```sh
pdfm -c configs/label_packing.yaml -i ./incoming --watch
```

### Automated Label Printing

Set up automatic label printing when new PDFs arrive:

```sh
pdfm -c configs/shipping_labels.yaml -i //server/labels --watch
```

### Development/Testing

Use dry-run to preview processing without making changes:

```sh
pdfm -c config.yaml -i ./test_input --watch --dry-run
```

### Fresh Start

Skip existing files and only process new arrivals:

```sh
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

### Network Drive with Custom Interval

For slow network drives, increase the polling interval:

```sh
pdfm -c config.yaml -i //nas/pdfs --watch --watch-interval 5.0
```

## Stopping Watch Mode

Press `Ctrl+C` to gracefully stop watching. The watcher will:
1. Stop monitoring for new files
2. Complete any in-progress file processing
3. Save the current state
4. Exit cleanly

## Troubleshooting

### Files Not Being Detected

1. **Check the file pattern**: Watch mode uses `input.pattern` from your config (default: `*.pdf`)
2. **Network drives**: Ensure polling is working by checking for "Using polling observer" in the log
3. **File stability**: Files being written may not be detected until they're complete

### Files Being Processed Multiple Times

1. **State file location**: Ensure the state file is writable and persists between runs
2. **File changes**: If a file is modified after processing, it will be reprocessed

### Permission Errors

1. **State file**: Ensure write permissions for the state file location
2. **Input directory**: Ensure read permissions for the input directory

## Related Documentation

- [CLI Reference](cli-reference.md) - Complete CLI options
- [Configuration](configuration.md) - Config file structure
- [Getting Started](getting-started.md) - Installation guide
