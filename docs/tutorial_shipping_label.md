# Tutorial: Shipping Label and Packing Slip Workflow

This tutorial walks through setting up pdfmill to split PDFs containing a label and some packing slips into separate outputs, then printing on two different printers.

## The Problem

Your platform only supports limited options to download labels and packing slips.

You want to:
1. Print the packing slip on a regular printer (e.g., Canon inkjet)
2. Print the shipping label on a thermal label printer (e.g., 4x6" label printer)

## Prerequisites

1. Install pdfmill:
   ```sh
   pip install pdfmill
   # Or for development:
   # pip install -e .
   ```

2. Have a sample PDF ready. Place `example.pdf` in your working directory. This PDF should have:
   - One or more packing slip pages
   - A shipping label as the last page

3. Know your printer names (on macOS/Linux these are CUPS queue names, e.g. `PL80E-BT`):
   ```sh
   pdfm --list-printers
   ```

## Step 1: Define input and output directory

