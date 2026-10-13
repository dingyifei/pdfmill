# Transforms

Transforms modify PDF pages after selection. They are applied in order, with each transform operating on the output of the previous one.

## Overview

pdfmill supports 7 transforms:

| Transform | Description | Optional Dependencies |
|-----------|-------------|----------------------|
| `rotate` | Rotate pages by angle or to orientation | - |
| `crop` | Crop to a rectangular region | - |
| `size` | Resize pages with fit modes | - |
| `stamp` | Add text overlays (page numbers, dates) | `pip install "pdfmill[stamp]"` |
| `split` | Extract multiple regions per page | - |
| `combine` | Place multiple pages onto one canvas | - |
| `render` | Rasterize pages to images | `pip install "pdfmill[ocr]"` + `poppler` |

`rotate: auto` additionally needs `pip install "pdfmill[ocr]"`, `poppler` and `tesseract` (macOS: `brew install poppler tesseract`). Run `pdfm -c config.yaml --validate --strict` to check the Python packages are installed.

Each entry in `transforms:` holds exactly one transform. Options are validated when the config is loaded; unknown keys, bad values and bad units are errors.

## Common Parameters

Every transform type supports `enabled`:

```yaml
transforms:
  - rotate: 90
    enabled: false    # Skip this transform (default: true)
```

To rotate only some pages, use the nested `rotate` form (see [Rotate](#rotate)). There is no `pages:` key next to a transform.

## Page Geometry

Before any transform runs, every selected page is normalized:

- An existing `/Rotate` setting is baked into the page content, so the page is oriented exactly as a PDF viewer shows it
- The visible area (CropBox) is moved so its lower-left corner is at (0, 0)

So coordinates (for `crop`, `split`, `stamp`, ...) are always measured on the page as it appears in a viewer, from the lower-left corner, after the previous transforms. After each transform the page's MediaBox, CropBox and TrimBox are identical, so printers (CUPS in particular) see the same page size you do.

## Units

All lengths (crop, split, size, combine, stamp positions and margins, `max_page_size`) support unit strings:

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

Angles are multiples of 90 and rotate counter-clockwise; the page size is swapped for 90/270 so nothing is cut off.

```yaml
transforms:
  - rotate: 90      # Rotate 90° counter-clockwise
  - rotate: 180     # Rotate 180°
  - rotate: 270     # Rotate 270° counter-clockwise (90° clockwise)
  - rotate: -90     # Same as 270
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

Detection runs on the current page (after any earlier transforms) and rotates it so the text is upright. Requires `poppler` and `tesseract` to be installed.

### Specific Pages Only

Use the nested form to rotate only some of the selected pages. `pages` are 0-indexed positions within the selected pages:

```yaml
transforms:
  - rotate:
      angle: 90       # Any angle, landscape, portrait or auto
      pages: [0, 1]   # Only the first two selected pages
```

---

## Crop

Extract a rectangular region from each page. Coordinates are from the lower-left corner of the page as it appears in a viewer (see [Page Geometry](#page-geometry)), after any earlier transforms such as `rotate`. The cropped region becomes the new page, with its lower-left corner at (0, 0).

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

`lower_left` must be below and to the left of `upper_right`. Content outside the crop is hidden, not removed; add a `render` step afterwards to remove it permanently.

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
| `contain` | Scale to fit within dimensions, preserving aspect ratio, centered (default) |
| `cover` | Scale to fill dimensions, preserving aspect ratio, centered (edges may be cut) |
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
      font_name: Helvetica            # A standard PDF font (Helvetica, Times-Roman, Courier, ...)
      font_color: black               # Color name or "#RRGGBB"
      opacity: 1.0                    # 0.0 (invisible) to 1.0 (opaque)
      margin: "10mm"                  # Distance from the edge for preset positions
      datetime_format: "%Y-%m-%d %H:%M:%S"
```

### Watermark

```yaml
transforms:
  - stamp:
      text: "COPY"
      position: center
      font_size: 72
      font_color: "#FF0000"
      opacity: 0.3
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

**Requirements:** `pip install "pdfmill[ocr]"` (pdf2image, Pillow) and the `poppler` tools (macOS: `brew install poppler`). DPI must be between 36 and 1200.

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
      - stamp:
          text: "{page}"
          position: bottom-right
```

Enable `debug: true` on the profile to save intermediate PDFs after each transform step.

## Related Documentation

- [Page Selection](page-selection.md) - Select pages before transforming
- [Output Profiles](output-profiles.md) - Debug mode for intermediate files
- [Configuration Guide](configuration.md) - Enable/disable transforms
