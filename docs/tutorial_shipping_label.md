# Tutorial: Shipping Label and Packing Slip Workflow

This tutorial walks through setting up pdfpipe to split PDFs containing a label and some packing slips into separate outputs, then printing on two different printers.

## The Problem

Your platform only supports limited options to download labels and packing slips.

You want to:
1. Print the packing slip on a regular printer (e.g., Canon inkjet)
2. Print the shipping label on a thermal label printer (e.g., 4x6" label printer)

## Prerequisites

1. Install pdfpipe:
   ```sh
   pip install -e .
   ```

2. Have a sample PDF ready. Place `example.pdf` in your working directory. This PDF should have:
   - One or more packing slip pages
   - A shipping label as the last page

3. Know your printer names:
   ```sh
   pdfp --list-printers
   ```

## Step 1: Create a Debug Config

First, create a config to extract and examine the shipping label. We'll use `debug: true` to see intermediate outputs after each transform.

Create `configs/debug_label.yaml`:

```yaml
version: 1

outputs:
  label:
    pages: "last"
    debug: true  # Save intermediate PDFs
    transforms:
      - rotate: 90
    output_dir: ./output
```

Run it:

```sh
pdfp -c configs/debug_label.yaml -i example.pdf
```

This creates:
```
./output/
├── example_label_step0_selected.pdf   # The raw last page
├── example_label_step1_rotate90.pdf   # After 90° rotation
└── example_label.pdf                  # Final output
```

## Step 2: Measure Crop Coordinates

Open `example_label_step1_rotate90.pdf` (the rotated page) and print it on regular paper.

Now measure where the actual label content is located. pdfpipe uses a coordinate system where:
- **Origin (0, 0) is the bottom-left corner**
- **X increases to the right**
- **Y increases upward**
- **72 points = 1 inch = 25.4mm**

pdfpipe supports any of these units (pt, in, mm, cm)

Using a ruler, measure from the bottom-left corner of the page:

```
         upper_right (190mm, 183mm)
              ┌─────────────┐
              │             │
              │   LABEL     │
              │   CONTENT   │
              │             │
              └─────────────┘
    lower_left (90mm, 33mm)

. lower_left_corner (0mm, 0mm)
```

Record:
- **lower_left**: Distance from left edge (X) and bottom edge (Y) to the label's bottom-left corner
- **upper_right**: Distance from left edge (X) and bottom edge (Y) to the label's top-right corner

## Step 3: Test the Crop

Update your debug config with the measured coordinates:

```yaml
version: 1

outputs:
  label:
    pages: "last"
    debug: true
    transforms:
      - rotate: 90
      - crop:
          lower_left: ["90mm", "33mm"]    # Your measurements
          upper_right: ["190mm", "183mm"]
    output_dir: ./output
```

Run again and check `example_label_step2_crop.pdf` to verify the crop is correct. Adjust measurements as needed.

## Step 4: Create the Final Config

Once cropping is correct, create the full config with both outputs:

Create `configs/label_packing.yaml`:

```yaml
version: 1

settings:
  on_error: continue

outputs:
  packing_sheet:
    pages: "1--1"           # All pages except last
    output_dir: ./output
    filename_suffix: "_1"
    print:
      merge: true           # Combine all packing slips into one print job
      enabled: true
      printer: "Canon G3060"  # Your regular printer

  label:
    pages: "last"
    debug: false            # Disable debug for production
    transforms:
      - rotate: 90
      - crop:
          lower_left: ["90mm", "33mm"]
          upper_right: ["190mm", "183mm"]
    output_dir: ./output
    filename_suffix: "_2"
    print:
      merge: true           # Combine all labels into one print job
      enabled: true
      printer: "PL80E"      # Your label printer
```

## Step 5: Run the Workflow

Process a single PDF:

```sh
pdfp -c configs/label_packing.yaml -i example.pdf
```

Process a folder of PDFs:

```sh
pdfp -c configs/label_packing.yaml -i ./input -o ./output
```

Dry run to preview without processing:

```sh
pdfp -c configs/label_packing.yaml -i ./input --dry-run
```

Note: you can also define an input folder for every config and define individual output folder for each output.

## Tips

### Different Label Sizes

For different label sizes, adjust the crop coordinates:
- 4x6" label: approximately 100mm x 150mm content area
- 4x4" label: approximately 100mm x 100mm content area

### Auto-Rotation

If your labels come in mixed orientations, use `landscape` or `portrait` instead of a fixed angle:

```yaml
transforms:
  - rotate: landscape  # Auto-rotate to landscape orientation
```

### Filtering by Content

If your input folder has mixed PDFs, filter by keywords:

```yaml
input:
  path: ./input
  filter:
    keywords: ["shipping", "tracking"]
    match: "any"
```