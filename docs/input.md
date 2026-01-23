# Input Configuration

The `input` section controls where pdfmill finds PDFs, how to filter them, and in what order to process them.

## Basic Usage

```yaml
input:
  path: ./input              # Directory or file path
  pattern: "*.pdf"           # Glob pattern for filenames
  sort: name_asc             # Sort order
  filter:
    keywords: ["shipping"]   # Text content filter
    match: "any"             # Match logic
```

All fields are optional. You can also override `path` via CLI with `-i`.

## Path

The `path` field specifies where to find input PDFs:

```yaml
input:
  path: ./input              # Directory
  path: ./documents/file.pdf # Single file
```

CLI override: `pdfm -c config.yaml -i ./other_folder`

## Pattern

Filter files by filename using glob patterns:

```yaml
input:
  pattern: "*.pdf"           # All PDFs (default)
  pattern: "shipping_*.pdf"  # Files starting with "shipping_"
  pattern: "*_label.pdf"     # Files ending with "_label"
  pattern: "2024-*.pdf"      # Files starting with "2024-"
```

## Sort Order

Control the processing order of files:

```yaml
input:
  sort: name_asc    # A-Z by filename
  sort: name_desc   # Z-A by filename
  sort: time_asc    # Oldest first (FIFO)
  sort: time_desc   # Newest first
```

| Value | Description |
|-------|-------------|
| `name_asc` | Alphabetical A-Z |
| `name_desc` | Alphabetical Z-A |
| `time_asc` | Oldest modified first |
| `time_desc` | Newest modified first |

Sorting can also be set per output profile. If both input-level and profile-level sort are set, an error is raised.

## Keyword Filtering

Filter PDFs by text content:

```yaml
input:
  filter:
    keywords: ["shipping", "label"]
    match: "any"    # Match if ANY keyword found (OR logic)

input:
  filter:
    keywords: ["invoice", "paid"]
    match: "all"    # Match only if ALL keywords found (AND logic)
```

| Field | Description |
|-------|-------------|
| `keywords` | List of text strings to search for |
| `match` | `"any"` = OR logic, `"all"` = AND logic |

**Notes:**
- Keyword matching is case-sensitive
- PDFs without searchable text (scanned images) won't match keyword filters
- Uses text extraction, not OCR

## Examples

### Process all PDFs alphabetically

```yaml
input:
  path: ./inbox
  sort: name_asc
```

### Process shipping labels only, oldest first

```yaml
input:
  path: ./downloads
  pattern: "shipping_*.pdf"
  sort: time_asc
  filter:
    keywords: ["tracking", "label"]
    match: "any"
```

### Process invoices that are marked paid

```yaml
input:
  path: ./invoices
  filter:
    keywords: ["invoice", "PAID"]
    match: "all"
```

## Related Documentation

- [Configuration Guide](configuration.md) - Overall config structure
- [Page Selection](page-selection.md) - Select pages within each PDF
- [Output Profiles](output-profiles.md) - Per-profile sort override
- [Watch Mode](watch-mode.md) - Automatically process new files in input directory
