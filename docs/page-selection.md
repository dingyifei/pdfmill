# Page Selection

The `pages` field in output profiles determines which pages to extract from each input PDF. pdfmill supports multiple selection syntaxes.

## Quick Reference

| Syntax | Meaning | Example Result (10-page PDF) |
|--------|---------|------------------------------|
| `"all"` | All pages | Pages 1-10 |
| `"first"` | First page only | Page 1 |
| `"last"` | Last page only | Page 10 |
| `"odd"` | Odd-numbered pages | Pages 1, 3, 5, 7, 9 |
| `"even"` | Even-numbered pages | Pages 2, 4, 6, 8, 10 |
| `[1, 2, 3]` | Specific pages | Pages 1, 2, 3 |
| `"1-3"` | Range (inclusive) | Pages 1, 2, 3 |
| `"3-"` | Page 3 to end | Pages 3-10 |
| `"-2"` | Last 2 pages | Pages 9, 10 |
| `"1--1"` | First to second-to-last | Pages 1-9 |

## Keywords

Simple keywords for common selections:

```yaml
outputs:
  profile:
    pages: "all"     # Every page
    pages: "first"   # Just page 1
    pages: "last"    # Just the last page
    pages: "odd"     # Pages 1, 3, 5, ...
    pages: "even"    # Pages 2, 4, 6, ...
```

## List Syntax

Select specific pages by number (1-indexed):

```yaml
outputs:
  profile:
    pages: [1, 2, 3]      # Pages 1, 2, and 3
    pages: [1, 3, 5]      # Pages 1, 3, and 5
    pages: [3, 4, 5, 6]   # Pages 3 through 6
```

Negative indices count from the end:

```yaml
outputs:
  profile:
    pages: [-1]           # Last page
    pages: [-2]           # Second-to-last page
    pages: [-1, -2]       # Last two pages (reversed order)
```

## Range Syntax

Select page ranges with string notation:

```yaml
outputs:
  profile:
    pages: "1-3"    # Pages 1, 2, 3
    pages: "2-5"    # Pages 2, 3, 4, 5
    pages: "1-1"    # Just page 1
```

### Open-ended Ranges

Leave one end open to select from/to the start/end:

```yaml
outputs:
  profile:
    pages: "3-"     # Page 3 to end
    pages: "-3"     # Last 3 pages
```

### Negative Indices in Ranges

Use double-negative for second-to-last, third-to-last, etc:

```yaml
outputs:
  profile:
    pages: "1--1"   # First page to second-to-last (excludes last)
    pages: "1--2"   # First page to third-to-last
    pages: "--2-"   # Third-to-last to end
```

## Examples

### Split packing sheet from shipping label

A common pattern for shipping PDFs where the label is the last page:

```yaml
outputs:
  packing_sheet:
    pages: "1--1"       # All pages except the last

  label:
    pages: "last"       # Just the shipping label
```

### Extract middle pages

For a 6-page document, keep only pages 3-6:

```yaml
outputs:
  extracted:
    pages: [3, 4, 5, 6]
    # or equivalently:
    pages: "3-"
```

### Print odd and even pages separately

For manual duplex printing:

```yaml
outputs:
  odd_pages:
    pages: "odd"
    print:
      enabled: true
      printer: "Printer"

  even_pages:
    pages: "even"
    print:
      enabled: true
      printer: "Printer"
```

## Transform-Level Page Selection

Transforms can also target specific pages within the already-selected pages:

```yaml
outputs:
  document:
    pages: [3, 4, 5, 6]   # Select pages 3-6 from source
    transforms:
      - rotate: 270
        pages: [1, 2]     # Rotate only pages 1-2 of the selection
                          # (which are pages 3-4 of the source)
```

The `pages` parameter in transforms uses 0-indexed positions within the selected pages.

## Related Documentation

- [Configuration Guide](configuration.md) - Overall config structure
- [Output Profiles](output-profiles.md) - Full profile options
- [Transforms](transforms.md) - Apply transformations to selected pages
