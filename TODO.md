# TODO

Features and improvements planned for pdfmill.

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
- [x] Size fit modes:
  - [x] `contain` - scale uniformly to fit
  - [x] `cover` - scale uniformly to fill
  - [x] `stretch` - non-uniform scaling
- [x] Transforms apply in config order

## Printing
- [x] Optional printing per output profile
- [x] Printer name configuration
- [x] Pass-through printer flags (SumatraPDF args)
- [x] Copies count
- [x] Multi-printer distribution:
  - [x] Named printer targets with individual settings
  - [x] Weight-based page distribution (for load balancing by speed/ppm)
  - [x] Copy distribution (different copy counts per target)
  - [x] Backwards compatible with single `printer:` config
- [ ] Cross-platform printing backend:
  - [x] SumatraPDF on Windows (current)
  - [ ] `lpr` command on Linux/macOS
  - [ ] Auto-detect platform and route to appropriate backend
  - [ ] Expose platform-specific printer settings in config YAML
  - [ ] Common settings: printer name, copies, paper size
  - [ ] Platform-specific args passed through to backend

## Input Processing
- [x] Input file sorting:
  - [x] Sort by name (ascending/descending)
  - [x] Sort by modification time (ascending/descending)
  - [x] Global sort in `input:` section
  - [x] Per-profile sort override (error if both set)

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
- [x] Entry point for `pdfm` CLI command
- [x] Type hints throughout
- [x] Unit tests
- [ ] Publish to PyPI

## Future Considerations
- [x] GUI configuration editor
- [ ] Watch mode for automatic processing of new files
- [ ] Config inheritance/imports (extend from base configs)
- [ ] Logging with configurable verbosity levels

---

## System Design Improvements

Architecture improvements to enhance maintainability and extensibility.

### Completed

- [x] **Enums for constrained values** - Added `StampPosition`, `SortOrder`, `FilterMatch`, `ErrorHandling`, `FitMode` enums in `config.py`
- [x] **Improved ConfigError** - Added context fields (profile, transform_idx, field, suggestion) for better error messages

### Phase 2: Validation (Medium Risk)

- [ ] Validate page specs at config load time
- [ ] Add `--validate --strict` mode for external resources (printers, paths)

### Phase 3: Transform Registry (Higher Risk)

- [ ] Define BaseTransform protocol/ABC
- [ ] Implement TransformRegistry for plugin-style transforms
- [ ] Migrate existing transforms to class-based
- [ ] Eliminate 150-line elif dispatch chain in processor.py

### Phase 4: Separation of Concerns (Higher Risk)

- [ ] Extract PrintPipeline from processor.py
- [ ] Create TransformExecutor class
- [ ] Reduce processor.py to pure orchestration

### Quick Reference

| Improvement | Impact | Effort | Status |
|-------------|--------|--------|--------|
| Transform Registry | High | Medium | Pending |
| Extract PrintPipeline | High | Medium | Pending |
| Early Validation | Medium | Low | Pending |
| Transform Context | Low | Low | Pending |
