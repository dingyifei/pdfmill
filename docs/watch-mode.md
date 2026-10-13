# Watch Mode

Monitor an input directory and automatically process new PDF files as they appear.

## Installation

Watch mode needs no extra dependencies; it is included in the base install.

## Basic Usage

```sh
# Watch input.path from the config and process new files
pdfm -c config.yaml --watch

# Watch another directory
pdfm -c config.yaml -i ./input --watch

# Preview mode (see what would happen without printing or writing anything)
pdfm -c config.yaml -i ./input --watch --dry-run

# Skip existing files when starting
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

The input must be a directory.

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--watch` | - | Enable watch mode |
| `--watch-interval` | `watch.poll_interval` (2.0) | Seconds between polls |
| `--watch-debounce` | `watch.debounce_delay` (1.0) | Seconds a file must be unchanged before processing |
| `--watch-state` | `<input>/.pdfmill_watch_state.json` | Path to state file for tracking processed files |
| `--no-process-existing` | - | Skip files that exist when watch mode starts |

## Config File Settings

Watch settings can also be set in the config. CLI flags override them.

```yaml
watch:
  poll_interval: 2.0      # Seconds between polls (default: 2.0)
  debounce_delay: 1.0     # Seconds a file must be unchanged (default: 1.0)
  process_existing: true  # Process existing files on startup (default: true)
```

## How It Works

1. **Startup**: When watch mode starts, it processes the PDF files already in the input directory (unless `--no-process-existing` or `process_existing: false`), skipping files already recorded in the state file

2. **Polling**: Every `poll_interval` seconds, the watcher lists the input directory (top level only) for files matching `input.pattern`

3. **File Stability**: A file is processed once its size and modification time are unchanged between two polls **and** it is at least `debounce_delay` seconds old. This handles files that are still being copied or downloaded.

4. **Processing**: Each new PDF is processed once, using the same pipeline as batch mode (keyword filter, output profiles, transforms, printing, cleanup)

5. **State Tracking**: Successfully processed files are recorded so they are not processed again after a restart

## State Tracking

Watch mode tracks which files have been processed in a JSON state file:

- **Default location**: `.pdfmill_watch_state.json` in the input directory
- **Custom location**: Use `--watch-state /path/to/state.json`

The state file records each successfully processed file by name, size and modification time.

- The state is **not** reset when the config changes, so editing a config never reprints everything in the input directory
- A file whose size or modification time changes (e.g. re-copied with the same name) is processed again
- Deleting the state file makes all files in the directory count as new on the next start
- `--dry-run` never writes the state file

### Failed Files

A file that fails (any profile or print job) is **not retried** while watch mode is running, because a retry could reprint profiles that already printed. To retry it, fix the problem (e.g. resume a paused printer), then either modify or re-copy the file, or restart watch mode.

## Examples

### Basic Watch Mode

Process PDFs as they appear in a directory:

```sh
pdfm -c configs/label_packing.yaml -i ./incoming --watch
```

### Automated Label Printing

Set up automatic label printing when new PDFs arrive in the config's `input.path`:

```sh
pdfm -c configs/label_packing.yaml --watch
```

### Development/Testing

Use dry-run to preview processing and print commands without making changes:

```sh
pdfm -c config.yaml -i ./test_input --watch --dry-run
```

### Fresh Start

Skip existing files and only process new arrivals:

```sh
pdfm -c config.yaml -i ./input --watch --no-process-existing
```

### Slower Polling

Increase the interval to poll less often (e.g. on a slow shared folder):

```sh
pdfm -c config.yaml -i ./input --watch --watch-interval 5.0
```

## Stopping Watch Mode

Press `Ctrl+C` to stop watching. State is saved after each successfully processed file, so there is nothing to flush. A file interrupted mid-processing is not recorded and will be processed again on the next start.

## Troubleshooting

### Files Not Being Detected

1. **Check the file pattern**: Watch mode uses `input.pattern` from your config (default: `*.pdf`)
2. **Subdirectories**: Only files directly in the input directory are watched
3. **File stability**: A file is only processed after it has stopped changing for at least one poll and `debounce_delay` seconds
4. **Already processed**: Files recorded in the state file are skipped; check `.pdfmill_watch_state.json`
5. **Failed earlier**: A file that failed is not retried until it changes or watch mode restarts

### Files Being Processed Multiple Times

1. **State file location**: Ensure the state file is writable and persists between runs
2. **File changes**: If a file is modified after processing, it will be processed again

### Permission Errors

1. **State file**: Ensure write permissions for the state file location
2. **Input directory**: Ensure read permissions for the input directory

## Related Documentation

- [CLI Reference](cli-reference.md) - Complete CLI options
- [Configuration](configuration.md) - Config file structure
- [Getting Started](getting-started.md) - Installation guide
