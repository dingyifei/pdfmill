# TODO

Features and improvements planned for pdfpipe.

## Core Processing
- [x] YAML configuration file support
- [x] Single PDF input mode
- [x] Batch folder input mode
- [x] Named output profiles (e.g., "label", "packing_sheet")
- [x] Output directory per profile

## Page Selection
- [x] Index-based selection (e.g., `[1, 2, 3]`)
- [x] Pattern-based selection (`first`, `last`, `odd`, `even`, `all`)
- [x] Negative indexing (`-1` for last page)
- [x] Range syntax (`1-3`, `3-`, `-2` for last 2 pages)
- [x] Negative offset range (`1--1` for all except last)
- [ ] Fallback behavior for missing pages (skip vs error) - currently errors

## Transformations
- [x] Rotate by degrees (0, 90, 180, 270)
- [x] Rotate by orientation (`portrait`, `landscape`)
- [x] Crop (specify crop box coordinates in points)
- [x] Target size enforcement with units (`100mm`, `4in`, `288pt`)
- [ ] Size fit modes need refinement:
  - [x] `contain` - scale uniformly to fit (basic)
  - [ ] `cover` - scale uniformly to fill (needs testing)
  - [ ] `stretch` - non-uniform scaling (needs proper implementation)
- [x] Transforms apply in config order

## Printing
- [x] Optional printing per output profile
- [x] Printer name configuration
- [x] Pass-through printer flags (SumatraPDF args)
- [x] Copies count
- [ ] Cross-platform printing backend:
  - [x] SumatraPDF on Windows (current)
  - [ ] `lpr` command on Linux/macOS
  - [ ] Auto-detect platform and route to appropriate backend
  - [ ] Expose platform-specific printer settings in config YAML
  - [ ] Common settings: printer name, copies, paper size
  - [ ] Platform-specific args passed through to backend

## Workflow Options
- [x] Cleanup source files after successful processing
- [x] Cleanup output files after successful printing
- [x] Configurable error handling (continue vs stop)
- [x] Dry-run mode

## CLI Interface
- [x] Flag-based interface: `-c/--config`, `-i/--input`, `-o/--output`
- [x] Override output directory via CLI
- [x] `--dry-run` flag
- [x] `--validate` flag
- [x] `--list-printers` command
- [x] `--version` flag

## Package & Distribution
- [x] Pip-installable package structure
- [x] `pyproject.toml` with modern Python packaging
- [x] Entry point for `pdfp` CLI command
- [x] Type hints throughout
- [ ] Unit tests
- [ ] Publish to PyPI

## Future Considerations
- [ ] GUI configuration editor
- [ ] Watch mode for automatic processing of new files
- [ ] Config inheritance/imports (extend from base configs)
- [ ] Logging with configurable verbosity levels
