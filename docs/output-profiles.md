# Output Profiles

Output profiles define how PDFs are processed and where they're saved. Each profile can have its own page selection, transforms, output directory, and print settings.

## Profile Structure

```yaml
outputs:
  profile_name:           # Name used in output filename
    enabled: true         # Toggle this profile
    pages: "all"          # Page selection
    transforms: []        # List of transforms
    output_dir: ./output  # Where to save
    filename_prefix: ""   # Add before filename
    filename_suffix: ""   # Add after filename
    sort: name_asc        # Override input sort
    debug: false          # Save intermediate files
    print:                # Print configuration
      enabled: false
```

## Output Filename

Output files are named using this pattern:

```
{prefix}{source_stem}{suffix}_{profile_name}.pdf
```

For example, with input `document.pdf`, prefix `"processed_"`, and profile `label`:
```
processed_document_label.pdf
```

### Filename Options

```yaml
outputs:
  label:
    filename_prefix: "processed_"    # Add before source filename
    filename_suffix: "_v2"           # Add after source filename
    output_dir: ./output/labels
```

## Multiple Profiles

Process the same input differently by defining multiple profiles:

```yaml
outputs:
  # Profile 1: Extract packing sheet
  packing_sheet:
    pages: "1--1"              # All pages except last
    output_dir: ./output/sheets
    print:
      enabled: true
      printer: "Office Printer"

  # Profile 2: Extract and transform label
  label:
    pages: "last"
    transforms:
      - rotate: 90
      - crop:
          lower_left: ["33mm", "91mm"]
          upper_right: ["180mm", "192mm"]
    output_dir: ./output/labels
    print:
      enabled: true
      printer: "Label Printer"
```

Each input file produces one output per enabled profile.

## Profile-Level Sort Override

Override the input sort order for a specific profile:

```yaml
input:
  path: ./input
  sort: name_asc          # Default sort

outputs:
  labels:
    pages: "last"
    sort: time_desc       # Override: newest first for this profile
```

**Note:** Setting both input-level and profile-level sort will raise an error to prevent confusion.

## Debug Mode

Enable `debug: true` to save intermediate PDFs after each transform step:

```yaml
outputs:
  label:
    debug: true
    pages: "last"
    transforms:
      - rotate: 90
      - crop:
          lower_left: ["33mm", "91mm"]
          upper_right: ["180mm", "192mm"]
    output_dir: ./output
```

This generates files showing each processing stage:

```
./output/
├── myfile_label_step0_selected.pdf   # After page selection
├── myfile_label_step1_rotate90.pdf   # After rotation
├── myfile_label_step2_crop.pdf       # After crop
└── myfile_label.pdf                  # Final output
```

Debug mode is useful for:
- Troubleshooting transform issues
- Verifying crop coordinates
- Understanding the transform pipeline

## Enable/Disable Profiles

Temporarily disable a profile without removing its configuration:

```yaml
outputs:
  packing_sheet:
    enabled: true         # Will be processed

  label:
    enabled: false        # Skipped entirely
    pages: "last"
    transforms:
      - rotate: 90
```

## Output Directory

Each profile can have its own output directory:

```yaml
outputs:
  invoices:
    pages: "1-2"
    output_dir: ./output/invoices

  receipts:
    pages: "last"
    output_dir: ./output/receipts
```

The directory is created if it doesn't exist.

CLI override applies to all profiles: `pdfm -c config.yaml -i ./input -o ./override`

## Complete Example

```yaml
version: 1

settings:
  cleanup_output_after_print: true

input:
  path: ./incoming
  pattern: "order_*.pdf"
  sort: time_asc

outputs:
  packing_slip:
    enabled: true
    pages: "1"
    filename_prefix: "pack_"
    output_dir: ./processed/packing
    print:
      enabled: true
      printer: "Office Printer"

  shipping_label:
    enabled: true
    pages: "last"
    filename_prefix: "label_"
    transforms:
      - rotate: 90
      - size:
          width: 100mm
          height: 150mm
          fit: stretch
    output_dir: ./processed/labels
    debug: false
    print:
      enabled: true
      printer: "Label Printer"

  archive:
    enabled: true
    pages: "all"
    output_dir: ./archive
    print:
      enabled: false
```

## Related Documentation

- [Page Selection](page-selection.md) - Page selection syntax
- [Transforms](transforms.md) - Available transforms
- [Printing](printing.md) - Print configuration
- [Configuration Guide](configuration.md) - Enable/disable options
