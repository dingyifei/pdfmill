# Transforms

Transforms modify PDF pages after selection. They are applied in order, with each transform operating on the output of the previous one.

## Overview

pdfmill supports 7 transforms:

| Transform | Description | Optional Dependencies |
|-----------|-------------|----------------------|
| `rotate` | Rotate pages by angle or to orientation | - |
| `crop` | Crop to a rectangular region | - |
| `size` | Resize pages with fit modes | - |
| `stamp` | Add text overlays (page numbers, dates) | `pip install pdfmill[stamp]` |
| `split` | Extract multiple regions per page | - |
| `combine` | Place multiple pages onto one canvas | - |
| `render` | Rasterize pages to images | Requires `poppler` |

## Common Parameters

All transforms support these optional parameters:

```yaml
transforms:
  - rotate: 90
    enabled: false    # Skip this transform (default: true)
    pages: [0, 1]     # Apply to specific pages only (0-indexed)
```

## Units

Crop and resize support unit strings:

| Unit | Description | Conversion |
|------|-------------|------------|
| `pt` | Points | 1 pt |
| `in` | Inches | 72 pt |
| `mm` | Millimeters | 2.835 pt |
| `cm` | Centimeters | 28.35 pt |

```yaml
# These are equivalent:
- crop:
    lower_left: [72, 144]           # Raw points
    upper_right: [288, 432]

- crop:
    lower_left: ["1in", "2in"]      # With units
    upper_right: ["4in", "6in"]

- crop:
    lower_left: ["25.4mm", "50.8mm"]
    upper_right: ["101.6mm", "152.4mm"]
```

---

## Rotate

Rotate pages by a fixed angle or to a target orientation.

### By Angle

```yaml
transforms:
  - rotate: 90      # Rotate 90° clockwise
  - rotate: 180     # Rotate 180°
  - rotate: 270     # Rotate 270° clockwise (90° counter-clockwise)
  - rotate: 0       # No rotation
```

### To Orientation

```yaml
transforms:
  - rotate: landscape   # Rotate to landscape if not already
  - rotate: portrait    # Rotate to portrait if not already
```

### Auto-Rotation (OCR)

With the OCR extra installed (`pip install pdfmill[ocr]`), pages can be auto-rotated based on text orientation:

```yaml
transforms:
  - rotate: auto    # Detect and correct orientation via OCR
```

---

## Crop

Extract a rectangular region from each page. Coordinates are from the lower-left corner.

```yaml
transforms:
  # Raw points (72 points = 1 inch)
  - crop:
      lower_left: [82, 260]
      upper_right: [514, 548]

  # With units
  - crop:
      lower_left: ["10mm", "20mm"]
      upper_right: ["100mm", "150mm"]

  # Mixed units
  - crop:
      lower_left: ["1in", "2in"]
      upper_right: ["4in", "6in"]
```

| Parameter | Description |
|-----------|-------------|
| `lower_left` | `[x, y]` coordinates of bottom-left corner |
| `upper_right` | `[x, y]` coordinates of top-right corner |

---

## Size (Resize)

Resize pages to specific dimensions with different fit modes.

```yaml
transforms:
  # Basic resize
  - size:
      width: 100mm
      height: 150mm

  # With fit mode
  - size:
      width: "4in"
      height: "6in"
      fit: contain    # Fit within bounds, preserve aspect ratio

  # Stretch to exact size
  - size:
      width: 100mm
      height: 150mm
      fit: stretch
```

### Fit Modes

| Mode | Description |
|------|-------------|
| `contain` | Scale to fit within dimensions, preserving aspect ratio (default) |
| `cover` | Scale to fill dimensions, preserving aspect ratio (may crop) |
| `stretch` | Stretch to exact dimensions (may distort) |

---

## Stamp

Add text overlays to pages. Requires `pip install pdfmill[stamp]`.

### Simple Format

```yaml
transforms:
  - stamp: "{page}/{total}"           # "1/5" on each page
  - stamp: "Page {page} of {total}"   # "Page 1 of 5"
```

### Full Configuration

```yaml
transforms:
  - stamp:
      text: "Page {page} of {total}"
      position: bottom-right
      font_size: 10
      font_name: Helvetica
      margin: "10mm"
      datetime_format: "%Y-%m-%d %H:%M:%S"
```

### Custom Position

```yaml
transforms:
  - stamp:
      text: "{datetime}"
      position: custom
      x: "50mm"
      y: "20mm"
```

### Placeholders

| Placeholder | Description |
|-------------|-------------|
| `{page}` | Current page number (1-indexed) |
| `{total}` | Total page count |
| `{datetime}` | Current datetime (uses `datetime_format`) |
| `{date}` | Current date (YYYY-MM-DD) |
| `{time}` | Current time (HH:MM:SS) |

### Position Presets

| Position | Description |
|----------|-------------|
| `top-left` | Top-left corner with margin |
| `top-right` | Top-right corner with margin |
| `bottom-left` | Bottom-left corner with margin |
| `bottom-right` | Bottom-right corner with margin |
| `center` | Center of page |
| `custom` | Use `x` and `y` coordinates |

---

## Split

Extract multiple regions from each page, creating separate output pages. Useful for splitting label sheets or multi-up documents.

```yaml
transforms:
  - split:
      regions:
        - lower_left: ["0in", "3in"]
          upper_right: ["4in", "6in"]
        - lower_left: ["4in", "3in"]
          upper_right: ["8in", "6in"]
```

Each input page produces N output pages (one per region). For a 2-page PDF with 2 regions, the output has 4 pages.

### Example: Split 2-up Label Sheet

```yaml
# 8.5x11" sheet with two 4x6" labels stacked vertically
transforms:
  - split:
      regions:
        - lower_left: ["0.25in", "5.5in"]   # Top label
          upper_right: ["4.25in", "11in"]
        - lower_left: ["0.25in", "0in"]     # Bottom label
          upper_right: ["4.25in", "5.5in"]
```

---

## Combine

Place multiple input pages onto a single output page. Useful for creating n-up layouts, booklets, or composite documents.

```yaml
transforms:
  - combine:
      page_size: ["8.5in", "11in"]    # Output page dimensions
      pages_per_output: 2              # Input pages per output page
      layout:
        - page: 0                      # First input page (0-indexed)
          position: ["0in", "5.5in"]   # Lower-left corner position
          scale: 0.5                   # Scale factor
        - page: 1                      # Second input page
          position: ["0in", "0in"]
          scale: 0.5
```

Input pages are batched by `pages_per_output`, and each batch produces one combined page.

### Example: 2-Up Layout

Place two pages side-by-side on a landscape sheet:

```yaml
transforms:
  - combine:
      page_size: ["11in", "8.5in"]    # Landscape letter
      pages_per_output: 2
      layout:
        - page: 0
          position: ["0in", "0in"]
          scale: 0.5
        - page: 1
          position: ["5.5in", "0in"]
          scale: 0.5
```

---

## Render

Rasterize pages to images and re-embed them. This permanently removes content outside the visible area and flattens all layers, annotations, and transparency.

```yaml
transforms:
  - render: 300           # DPI value
  - render: {dpi: 200}    # Dict form
  - render: true          # Default 150 DPI
```

**Requirements:** Requires `poppler` to be installed on the system.

**Use cases:**
- Remove hidden content after cropping
- Flatten complex PDFs for printing
- Reduce file size for image-heavy documents

**Note:** This is a destructive operation. Text becomes non-searchable and the PDF cannot be further edited.

---

## Transform Pipeline Example

Transforms are applied in sequence:

```yaml
outputs:
  label:
    pages: "last"
    transforms:
      # 1. Rotate the page
      - rotate: 90

      # 2. Crop to label area
      - crop:
          lower_left: ["33mm", "91mm"]
          upper_right: ["180mm", "192mm"]

      # 3. Resize to standard label size
      - size:
          width: 100mm
          height: 150mm
          fit: stretch

      # 4. Add page number
      - stamp: "{page}"
        position: bottom-right
```

Enable `debug: true` on the profile to save intermediate PDFs after each transform step.

## Related Documentation

- [Page Selection](page-selection.md) - Select pages before transforming
- [Output Profiles](output-profiles.md) - Debug mode for intermediate files
- [Configuration Guide](configuration.md) - Enable/disable transforms
