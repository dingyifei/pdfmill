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

All fields are optional. You can also override `path` via CLI with `-i`; without `-i`, pdfmill processes `input.path` (default: `input`). Relative paths are relative to the current working directory.

## Path

The `path` field specifies where to find input PDFs:

```yaml
input:
  path: ./input              # Directory
  path: ./documents/file.pdf # Single file
```

CLI override: `pdfm -c config.yaml -i ./other_folder`

When the path is a single file, it is processed regardless of `pattern`. Only the top level of a directory is searched (no subdirectories).

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

Control the processing order of files (and the order their outputs are printed in):

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

Without `sort`, files are processed in filename order.

Sorting can also be set per output profile. A profile's `sort` overrides the **print order** for that profile only; `input.sort` still sets the processing order. Setting both is allowed. See [Output Profiles](output-profiles.md#profile-level-sort-override).

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
- A PDF that cannot be read counts as a failed source (it is not silently skipped)

## Fields

`fields` pull values out of each source PDF's text (all pages) with a regular expression. Stamp text can then use them as `{name}` placeholders, for example to print the order number from the packing list onto the shipping label:

```yaml
input:
  fields:
    order: 'Order No\.\s*(\d+)'          # shorthand: value is group 1 (or the whole match)
    box:
      pattern: 'Box\s+(\d+)\.\s+Your order will ship in\s+(\d+)\s+boxes'
      format: ' · BOX \1/\2'             # re.Match.expand() template
      default: ''                         # used when the pattern doesn't match

outputs:
  label:
    pages: last
    transforms:
      - stamp: {text: '#{order}{box}', position: custom, align: right, x: 83.5mm, y: 7.9mm, font_name: Helvetica-Bold, font_size: 6}
```

| Key | Description |
|-----|-------------|
| `pattern` | Regular expression searched in the PDF text |
| `format` | Optional template using `\1`, `\2` or `\g<name>` group references |
| `default` | Value used when nothing matches. Without a default the field is required: a PDF where it is missing fails (nothing is printed for it and it is never cleaned up) |

Use single quotes in YAML so backslashes are kept as written.

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
