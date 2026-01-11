"""Tkinter GUI for pdfmill configuration editor."""

import ctypes
import platform
import queue
import shlex
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Any

import yaml


def enable_high_dpi():
    """Enable high DPI awareness on Windows for crisp rendering."""
    if platform.system() == "Windows":
        try:
            # Windows 10 1703+ (Per-Monitor V2 DPI awareness)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                # Windows 8.1+ (Per-Monitor DPI awareness)
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                try:
                    # Windows Vista+ (System DPI awareness)
                    ctypes.windll.user32.SetProcessDPIAware()
                except (AttributeError, OSError):
                    pass


# Enable high DPI before creating any Tk windows
enable_high_dpi()

from pdfmill.config import (
    Config, Settings, InputConfig, FilterConfig, OutputProfile,
    PrintConfig, PrintTarget, Transform, RotateTransform, CropTransform,
    SizeTransform, load_config, ConfigError,
)
from pdfmill.constants import (
    ON_ERROR_OPTIONS as _ON_ERROR_OPTIONS,
    SORT_OPTIONS as _SORT_OPTIONS,
    MATCH_MODES as _MATCH_MODES,
    TRANSFORM_TYPES as _TRANSFORM_TYPES,
    ROTATE_ANGLES as _ROTATE_ANGLES,
    ROTATE_ORIENTATIONS as _ROTATE_ORIENTATIONS,
    FIT_MODES as _FIT_MODES,
)

# Convert tuples to lists for tkinter dropdowns, with GUI-specific additions
ON_ERROR_OPTIONS = list(_ON_ERROR_OPTIONS)
SORT_OPTIONS = [""] + list(_SORT_OPTIONS)  # Empty option for "no sort"
MATCH_OPTIONS = list(_MATCH_MODES)
TRANSFORM_TYPES = list(_TRANSFORM_TYPES)
ROTATE_ANGLES = [str(a) for a in _ROTATE_ANGLES] + list(_ROTATE_ORIENTATIONS)
FIT_MODES = list(_FIT_MODES)


class SettingsFrame(ttk.LabelFrame):
    """Frame for editing global settings."""

    def __init__(self, parent):
        super().__init__(parent, text="Global Settings", padding=10)

        self.on_error_var = tk.StringVar(value="continue")
        self.cleanup_source_var = tk.BooleanVar(value=False)
        self.cleanup_output_var = tk.BooleanVar(value=False)

        # On error
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="On Error:").pack(side="left")
        ttk.Combobox(row, textvariable=self.on_error_var, values=ON_ERROR_OPTIONS,
                     state="readonly", width=15).pack(side="left", padx=5)

        # Cleanup checkboxes
        ttk.Checkbutton(self, text="Cleanup source files after processing",
                        variable=self.cleanup_source_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(self, text="Cleanup output files after printing",
                        variable=self.cleanup_output_var).pack(anchor="w", pady=2)

    def load(self, settings: Settings):
        self.on_error_var.set(settings.on_error)
        self.cleanup_source_var.set(settings.cleanup_source)
        self.cleanup_output_var.set(settings.cleanup_output_after_print)

    def to_settings(self) -> Settings:
        return Settings(
            on_error=self.on_error_var.get(),
            cleanup_source=self.cleanup_source_var.get(),
            cleanup_output_after_print=self.cleanup_output_var.get(),
        )


class InputFrame(ttk.LabelFrame):
    """Frame for editing input configuration."""

    def __init__(self, parent):
        super().__init__(parent, text="Input Configuration", padding=10)

        self.path_var = tk.StringVar(value="./input")
        self.pattern_var = tk.StringVar(value="*.pdf")
        self.sort_var = tk.StringVar(value="")
        self.keywords_var = tk.StringVar(value="")
        self.match_var = tk.StringVar(value="any")

        # Input path
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Input Path:").pack(side="left")
        ttk.Entry(row, textvariable=self.path_var, width=40).pack(side="left", padx=5)
        ttk.Button(row, text="Browse...", command=self._browse_path).pack(side="left")

        # Pattern
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="File Pattern:").pack(side="left")
        ttk.Entry(row, textvariable=self.pattern_var, width=20).pack(side="left", padx=5)

        # Sort
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Sort Order:").pack(side="left")
        ttk.Combobox(row, textvariable=self.sort_var, values=SORT_OPTIONS,
                     width=15).pack(side="left", padx=5)

        # Filter section
        filter_frame = ttk.LabelFrame(self, text="Keyword Filter (optional)", padding=5)
        filter_frame.pack(fill="x", pady=5)

        row = ttk.Frame(filter_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Keywords (comma-separated):").pack(side="left")
        ttk.Entry(row, textvariable=self.keywords_var, width=30).pack(side="left", padx=5)

        row = ttk.Frame(filter_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Match:").pack(side="left")
        ttk.Radiobutton(row, text="Any (OR)", variable=self.match_var, value="any").pack(side="left", padx=5)
        ttk.Radiobutton(row, text="All (AND)", variable=self.match_var, value="all").pack(side="left", padx=5)

    def _browse_path(self):
        path = filedialog.askdirectory(title="Select Input Directory")
        if path:
            self.path_var.set(path)

    def load(self, input_config: InputConfig):
        self.path_var.set(str(input_config.path))
        self.pattern_var.set(input_config.pattern)
        self.sort_var.set(input_config.sort or "")
        if input_config.filter:
            self.keywords_var.set(", ".join(input_config.filter.keywords))
            self.match_var.set(input_config.filter.match)
        else:
            self.keywords_var.set("")
            self.match_var.set("any")

    def to_input_config(self) -> InputConfig:
        filter_config = None
        keywords_str = self.keywords_var.get().strip()
        if keywords_str:
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
            if keywords:
                filter_config = FilterConfig(keywords=keywords, match=self.match_var.get())

        return InputConfig(
            path=Path(self.path_var.get()),
            pattern=self.pattern_var.get(),
            filter=filter_config,
            sort=self.sort_var.get() or None,
        )


class TransformDialog(tk.Toplevel):
    """Dialog for editing a single transform."""

    def __init__(self, parent, transform: Transform | None = None):
        super().__init__(parent)
        self.title("Edit Transform")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None

        self.type_var = tk.StringVar(value="rotate")
        self.angle_var = tk.StringVar(value="90")
        self.crop_ll_x_var = tk.StringVar(value="0")
        self.crop_ll_y_var = tk.StringVar(value="0")
        self.crop_ur_x_var = tk.StringVar(value="612")
        self.crop_ur_y_var = tk.StringVar(value="792")
        self.size_w_var = tk.StringVar(value="100mm")
        self.size_h_var = tk.StringVar(value="150mm")
        self.fit_var = tk.StringVar(value="contain")

        # Type selector
        row = ttk.Frame(self, padding=10)
        row.pack(fill="x")
        ttk.Label(row, text="Type:").pack(side="left")
        type_combo = ttk.Combobox(row, textvariable=self.type_var, values=TRANSFORM_TYPES,
                                  state="readonly", width=15)
        type_combo.pack(side="left", padx=5)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._update_fields())

        # Rotate frame
        self.rotate_frame = ttk.LabelFrame(self, text="Rotate Options", padding=10)
        row = ttk.Frame(self.rotate_frame)
        row.pack(fill="x")
        ttk.Label(row, text="Angle:").pack(side="left")
        ttk.Combobox(row, textvariable=self.angle_var, values=ROTATE_ANGLES, width=15).pack(side="left", padx=5)

        # Crop frame
        self.crop_frame = ttk.LabelFrame(self, text="Crop Options", padding=10)
        row = ttk.Frame(self.crop_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Lower Left X:").pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ll_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text="Y:").pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ll_y_var, width=10).pack(side="left", padx=5)
        row = ttk.Frame(self.crop_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Upper Right X:").pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ur_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text="Y:").pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ur_y_var, width=10).pack(side="left", padx=5)

        # Size frame
        self.size_frame = ttk.LabelFrame(self, text="Size Options", padding=10)
        row = ttk.Frame(self.size_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Width:").pack(side="left")
        ttk.Entry(row, textvariable=self.size_w_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text="Height:").pack(side="left")
        ttk.Entry(row, textvariable=self.size_h_var, width=10).pack(side="left", padx=5)
        row = ttk.Frame(self.size_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Fit:").pack(side="left")
        ttk.Combobox(row, textvariable=self.fit_var, values=FIT_MODES, state="readonly", width=10).pack(side="left", padx=5)

        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right")

        # Load existing transform
        if transform:
            self._load_transform(transform)

        self._update_fields()

    def _update_fields(self):
        self.rotate_frame.pack_forget()
        self.crop_frame.pack_forget()
        self.size_frame.pack_forget()

        t = self.type_var.get()
        if t == "rotate":
            self.rotate_frame.pack(fill="x", padx=10, pady=5)
        elif t == "crop":
            self.crop_frame.pack(fill="x", padx=10, pady=5)
        elif t == "size":
            self.size_frame.pack(fill="x", padx=10, pady=5)

    def _load_transform(self, t: Transform):
        self.type_var.set(t.type)
        if t.type == "rotate" and t.rotate:
            self.angle_var.set(str(t.rotate.angle))
        elif t.type == "crop" and t.crop:
            self.crop_ll_x_var.set(str(t.crop.lower_left[0]))
            self.crop_ll_y_var.set(str(t.crop.lower_left[1]))
            self.crop_ur_x_var.set(str(t.crop.upper_right[0]))
            self.crop_ur_y_var.set(str(t.crop.upper_right[1]))
        elif t.type == "size" and t.size:
            self.size_w_var.set(t.size.width)
            self.size_h_var.set(t.size.height)
            self.fit_var.set(t.size.fit)

    def _ok(self):
        t = self.type_var.get()
        if t == "rotate":
            angle = self.angle_var.get()
            try:
                angle = int(angle)
            except ValueError:
                pass  # Keep as string (landscape/portrait/auto)
            self.result = Transform(type="rotate", rotate=RotateTransform(angle=angle))
        elif t == "crop":
            self.result = Transform(
                type="crop",
                crop=CropTransform(
                    lower_left=(self.crop_ll_x_var.get(), self.crop_ll_y_var.get()),
                    upper_right=(self.crop_ur_x_var.get(), self.crop_ur_y_var.get()),
                ),
            )
        elif t == "size":
            self.result = Transform(
                type="size",
                size=SizeTransform(
                    width=self.size_w_var.get(),
                    height=self.size_h_var.get(),
                    fit=self.fit_var.get(),
                ),
            )
        self.destroy()


class PrintTargetDialog(tk.Toplevel):
    """Dialog for editing a print target."""

    def __init__(self, parent, printers: list[str], name: str = "", target: PrintTarget | None = None):
        super().__init__(parent)
        self.title("Edit Print Target")
        self.geometry("400x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.result_name = None

        self.name_var = tk.StringVar(value=name)
        self.printer_var = tk.StringVar()
        self.weight_var = tk.IntVar(value=1)
        self.copies_var = tk.IntVar(value=1)
        self.args_var = tk.StringVar()

        # Name
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Target Name:").pack(side="left")
        ttk.Entry(row, textvariable=self.name_var, width=20).pack(side="left", padx=5)

        # Printer
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Printer:").pack(side="left")
        combo = ttk.Combobox(row, textvariable=self.printer_var, values=printers, width=30)
        combo.pack(side="left", padx=5)
        if not printers:
            combo["state"] = "normal"

        # Weight
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Weight:").pack(side="left")
        ttk.Spinbox(row, textvariable=self.weight_var, from_=1, to=1000, width=10).pack(side="left", padx=5)

        # Copies
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Copies:").pack(side="left")
        ttk.Spinbox(row, textvariable=self.copies_var, from_=1, to=100, width=10).pack(side="left", padx=5)

        # Args
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text="Extra Args:").pack(side="left")
        ttk.Entry(row, textvariable=self.args_var, width=30).pack(side="left", padx=5)

        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right")

        # Load existing or set defaults
        if target:
            self.printer_var.set(target.printer)
            self.weight_var.set(target.weight)
            self.copies_var.set(target.copies)
            self.args_var.set(shlex.join(target.args))
        elif len(printers) == 1:
            # New target with single printer: auto-select it
            self.printer_var.set(printers[0])

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Target name is required")
            return
        args = shlex.split(self.args_var.get())
        self.result_name = name
        self.result = PrintTarget(
            printer=self.printer_var.get(),
            weight=self.weight_var.get(),
            copies=self.copies_var.get(),
            args=args,
        )
        self.destroy()


class OutputProfileEditor(ttk.Frame):
    """Editor for a single output profile."""

    def __init__(self, parent, printers: list[str], on_refresh_printers=None):
        super().__init__(parent, padding=10)
        self.printers = printers
        self._on_refresh_printers = on_refresh_printers
        self.transforms: list[Transform] = []
        self.print_targets: dict[str, PrintTarget] = {}

        self.name_var = tk.StringVar()
        self.pages_var = tk.StringVar(value="all")
        self.output_dir_var = tk.StringVar(value="./output")
        self.prefix_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        self.sort_var = tk.StringVar()
        self.debug_var = tk.BooleanVar(value=False)
        self.print_enabled_var = tk.BooleanVar(value=False)
        self.print_merge_var = tk.BooleanVar(value=False)

        # Profile name
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Profile Name:").pack(side="left")
        ttk.Entry(row, textvariable=self.name_var, width=20).pack(side="left", padx=5)

        # Pages
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Pages:").pack(side="left")
        ttk.Entry(row, textvariable=self.pages_var, width=15).pack(side="left", padx=5)
        ttk.Label(row, text="(e.g., all, last, 1-3, first)").pack(side="left")

        # Output dir
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Output Dir:").pack(side="left")
        ttk.Entry(row, textvariable=self.output_dir_var, width=30).pack(side="left", padx=5)
        ttk.Button(row, text="Browse...", command=self._browse_output).pack(side="left")

        # Prefix/Suffix
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Prefix:").pack(side="left")
        ttk.Entry(row, textvariable=self.prefix_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text="Suffix:").pack(side="left")
        ttk.Entry(row, textvariable=self.suffix_var, width=10).pack(side="left", padx=5)

        # Sort
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Sort Override:").pack(side="left")
        ttk.Combobox(row, textvariable=self.sort_var, values=SORT_OPTIONS, width=15).pack(side="left", padx=5)

        # Debug
        ttk.Checkbutton(self, text="Debug mode (save intermediate files)", variable=self.debug_var).pack(anchor="w", pady=2)

        # Transforms section
        tf = ttk.LabelFrame(self, text="Transforms", padding=5)
        tf.pack(fill="both", expand=True, pady=5)

        self.transform_list = tk.Listbox(tf, height=4)
        self.transform_list.pack(side="left", fill="both", expand=True)

        btn_col = ttk.Frame(tf)
        btn_col.pack(side="left", padx=5)
        ttk.Button(btn_col, text="Add", command=self._add_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="Edit", command=self._edit_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="Remove", command=self._remove_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="Up", command=self._move_up).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="Down", command=self._move_down).pack(fill="x", pady=1)

        # Print config section
        pf = ttk.LabelFrame(self, text="Print Configuration", padding=5)
        pf.pack(fill="x", pady=5)

        row = ttk.Frame(pf)
        row.pack(fill="x")
        ttk.Checkbutton(row, text="Enabled", variable=self.print_enabled_var).pack(side="left")
        ttk.Checkbutton(row, text="Merge PDFs before printing", variable=self.print_merge_var).pack(side="left", padx=10)

        row = ttk.Frame(pf)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Print Targets:").pack(side="left")

        self.target_list = tk.Listbox(pf, height=3)
        self.target_list.pack(fill="x", pady=2)

        btn_row = ttk.Frame(pf)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Add Target", command=self._add_target).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Edit Target", command=self._edit_target).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Remove Target", command=self._remove_target).pack(side="left", padx=2)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir_var.set(path)

    def _refresh_printers(self):
        if self._on_refresh_printers:
            self._on_refresh_printers()

    def _transform_str(self, t: Transform) -> str:
        if t.type == "rotate" and t.rotate:
            return f"rotate: {t.rotate.angle}"
        elif t.type == "crop" and t.crop:
            return f"crop: {t.crop.lower_left} -> {t.crop.upper_right}"
        elif t.type == "size" and t.size:
            return f"size: {t.size.width} x {t.size.height} ({t.size.fit})"
        return str(t)

    def _refresh_transforms(self):
        self.transform_list.delete(0, tk.END)
        for t in self.transforms:
            self.transform_list.insert(tk.END, self._transform_str(t))

    def _add_transform(self):
        dlg = TransformDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.transforms.append(dlg.result)
            self._refresh_transforms()

    def _edit_transform(self):
        sel = self.transform_list.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = TransformDialog(self, self.transforms[idx])
        self.wait_window(dlg)
        if dlg.result:
            self.transforms[idx] = dlg.result
            self._refresh_transforms()

    def _remove_transform(self):
        sel = self.transform_list.curselection()
        if sel:
            del self.transforms[sel[0]]
            self._refresh_transforms()

    def _move_up(self):
        sel = self.transform_list.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            self.transforms[idx], self.transforms[idx - 1] = self.transforms[idx - 1], self.transforms[idx]
            self._refresh_transforms()
            self.transform_list.selection_set(idx - 1)

    def _move_down(self):
        sel = self.transform_list.curselection()
        if sel and sel[0] < len(self.transforms) - 1:
            idx = sel[0]
            self.transforms[idx], self.transforms[idx + 1] = self.transforms[idx + 1], self.transforms[idx]
            self._refresh_transforms()
            self.transform_list.selection_set(idx + 1)

    def _refresh_targets(self):
        self.target_list.delete(0, tk.END)
        for name, t in self.print_targets.items():
            self.target_list.insert(tk.END, f"{name}: {t.printer} (w={t.weight}, c={t.copies})")

    def _add_target(self):
        self._refresh_printers()
        # Generate default name based on existing targets
        if not self.print_targets:
            default_name = "default"
        else:
            i = 2
            while f"target_{i}" in self.print_targets:
                i += 1
            default_name = f"target_{i}"
        dlg = PrintTargetDialog(self, self.printers, name=default_name)
        self.wait_window(dlg)
        if dlg.result and dlg.result_name:
            self.print_targets[dlg.result_name] = dlg.result
            self._refresh_targets()

    def _edit_target(self):
        sel = self.target_list.curselection()
        if not sel:
            return
        self._refresh_printers()
        name = list(self.print_targets.keys())[sel[0]]
        target = self.print_targets[name]
        dlg = PrintTargetDialog(self, self.printers, name, target)
        self.wait_window(dlg)
        if dlg.result and dlg.result_name:
            if dlg.result_name != name:
                del self.print_targets[name]
            self.print_targets[dlg.result_name] = dlg.result
            self._refresh_targets()

    def _remove_target(self):
        sel = self.target_list.curselection()
        if sel:
            name = list(self.print_targets.keys())[sel[0]]
            del self.print_targets[name]
            # If only 1 target remains, rename it to "default"
            if len(self.print_targets) == 1:
                old_name = list(self.print_targets.keys())[0]
                if old_name != "default":
                    target = self.print_targets.pop(old_name)
                    self.print_targets["default"] = target
            self._refresh_targets()

    def load(self, name: str, profile: OutputProfile):
        self.name_var.set(name)
        self.pages_var.set(str(profile.pages) if isinstance(profile.pages, str) else ",".join(map(str, profile.pages)))
        self.output_dir_var.set(str(profile.output_dir))
        self.prefix_var.set(profile.filename_prefix)
        self.suffix_var.set(profile.filename_suffix)
        self.sort_var.set(profile.sort or "")
        self.debug_var.set(profile.debug)
        self.print_enabled_var.set(profile.print.enabled)
        self.print_merge_var.set(profile.print.merge)
        self.transforms = list(profile.transforms)
        self.print_targets = dict(profile.print.targets)
        self._refresh_transforms()
        self._refresh_targets()

    def to_profile(self) -> tuple[str, OutputProfile]:
        pages: str | list[int] = self.pages_var.get()
        # Try to parse as list of ints
        if pages and pages[0] == "[":
            try:
                pages = [int(x.strip()) for x in pages.strip("[]").split(",")]
            except ValueError:
                pass

        return self.name_var.get(), OutputProfile(
            pages=pages,
            output_dir=Path(self.output_dir_var.get()),
            filename_prefix=self.prefix_var.get(),
            filename_suffix=self.suffix_var.get(),
            transforms=list(self.transforms),
            print=PrintConfig(
                enabled=self.print_enabled_var.get(),
                merge=self.print_merge_var.get(),
                targets=dict(self.print_targets),
            ),
            debug=self.debug_var.get(),
            sort=self.sort_var.get() or None,
        )


class OutputsFrame(ttk.Frame):
    """Frame for managing output profiles."""

    def __init__(self, parent, printers: list[str], on_refresh_printers=None):
        super().__init__(parent, padding=10)
        self.printers = printers
        self._on_refresh_printers = on_refresh_printers
        self.profiles: dict[str, OutputProfile] = {}
        self.current_profile: str | None = None

        # Left panel - profile list
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left, text="Profiles:").pack(anchor="w")
        self.profile_list = tk.Listbox(left, width=20, height=15)
        self.profile_list.pack(fill="y", expand=True)
        self.profile_list.bind("<<ListboxSelect>>", self._on_select)

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_profile).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Remove", command=self._remove_profile).pack(side="left", padx=2)

        # Right panel - profile editor
        self.editor = OutputProfileEditor(self, printers, on_refresh_printers)
        self.editor.pack(side="left", fill="both", expand=True)

    def _refresh_list(self):
        self.profile_list.delete(0, tk.END)
        for name in self.profiles.keys():
            self.profile_list.insert(tk.END, name)

    def _save_current(self):
        if self.current_profile:
            name, profile = self.editor.to_profile()
            if name != self.current_profile:
                del self.profiles[self.current_profile]
            self.profiles[name] = profile
            self._refresh_list()

    def _on_select(self, event):
        sel = self.profile_list.curselection()
        if not sel:
            return
        name = self.profile_list.get(sel[0])
        if name == self.current_profile:
            return
        self._save_current()
        self.current_profile = name
        self.editor.load(name, self.profiles[name])

    def _add_profile(self):
        self._save_current()
        i = 1
        while f"profile_{i}" in self.profiles:
            i += 1
        name = f"profile_{i}"
        self.profiles[name] = OutputProfile(pages="all", output_dir=Path("./output"))
        self._refresh_list()
        # Select new profile
        idx = list(self.profiles.keys()).index(name)
        self.profile_list.selection_clear(0, tk.END)
        self.profile_list.selection_set(idx)
        self.current_profile = name
        self.editor.load(name, self.profiles[name])

    def _remove_profile(self):
        sel = self.profile_list.curselection()
        if sel:
            name = self.profile_list.get(sel[0])
            del self.profiles[name]
            self.current_profile = None
            self._refresh_list()

    def load(self, outputs: dict[str, OutputProfile]):
        self.profiles = dict(outputs)
        self.current_profile = None
        self._refresh_list()
        if self.profiles:
            first = list(self.profiles.keys())[0]
            self.profile_list.selection_set(0)
            self.current_profile = first
            self.editor.load(first, self.profiles[first])

    def to_outputs(self) -> dict[str, OutputProfile]:
        self._save_current()
        return dict(self.profiles)


class PdfMillApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("pdfmill Config Editor")

        # Configure high DPI scaling
        self._configure_dpi_scaling()

        self.geometry("900x900")

        self.current_file: Path | None = None
        self.running = False
        self.output_queue: queue.Queue = queue.Queue()

        # Get printers
        self.printers = self._get_printers()

        # Menu bar
        self._create_menu()

        # Create widgets
        self._create_widgets()

        # Load default config
        self._new_config()

    def _configure_dpi_scaling(self):
        """Configure DPI scaling for crisp rendering on high-DPI displays."""
        # Get the DPI scaling factor
        try:
            dpi = self.winfo_fpixels('1i')  # Pixels per inch
            scale_factor = dpi / 72.0  # 72 is the base DPI

            # Apply scaling to Tk
            self.tk.call('tk', 'scaling', scale_factor)

            # Configure ttk style for better appearance
            style = ttk.Style()

            # Use a modern theme if available
            available_themes = style.theme_names()
            if 'vista' in available_themes:
                style.theme_use('vista')
            elif 'clam' in available_themes:
                style.theme_use('clam')

            # Calculate scaled font size (base 9pt, scaled for DPI)
            # Use a more conservative scaling to avoid oversized UI
            base_font_size = int(9 * (dpi / 96.0) * 0.85)  # 96 DPI is Windows default
            base_font_size = max(8, min(base_font_size, 11))  # Clamp between 8-11

            # Configure default fonts for better readability
            default_font = ('Segoe UI', base_font_size)
            heading_font = ('Segoe UI', base_font_size + 1, 'bold')
            mono_font = ('Consolas', base_font_size)

            # Apply fonts to ttk widgets
            style.configure('.', font=default_font)
            style.configure('TLabel', font=default_font)
            style.configure('TButton', font=default_font, padding=(6, 2))
            style.configure('TCheckbutton', font=default_font)
            style.configure('TRadiobutton', font=default_font)
            style.configure('TEntry', font=default_font, padding=2)
            style.configure('TCombobox', font=default_font, padding=2)
            style.configure('TLabelframe.Label', font=heading_font)
            style.configure('TNotebook.Tab', font=default_font, padding=(8, 4))
            style.configure('TSpinbox', font=default_font, padding=2)

            # Configure Listbox and Text widgets (tk, not ttk)
            self.option_add('*Font', default_font)
            self.option_add('*Listbox.font', default_font)
            self.option_add('*Text.font', mono_font)

            # Store for later use
            self._mono_font = mono_font
            self._scale_factor = scale_factor

        except Exception:
            # Fallback if DPI detection fails
            self._mono_font = ('Consolas', 9)
            self._scale_factor = 1.0

    def _create_widgets(self):
        """Create all UI widgets."""
        # Header row with tab buttons on left, action buttons on right
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Tab buttons on the left
        tab_frame = ttk.Frame(header)
        tab_frame.pack(side="left")

        self._tab_buttons = {}
        self._tab_frames = {}
        self._current_tab = tk.StringVar(value="Settings")

        for tab_name in ["Settings", "Input", "Outputs"]:
            btn = ttk.Button(tab_frame, text=tab_name,
                           command=lambda t=tab_name: self._switch_tab(t))
            btn.pack(side="left", padx=(0, 2))
            self._tab_buttons[tab_name] = btn

        # Action buttons on the right
        ttk.Button(header, text="Run", command=self._run).pack(side="right", padx=2)
        ttk.Button(header, text="Dry Run", command=self._dry_run).pack(side="right", padx=2)
        ttk.Button(header, text="Validate", command=self._validate).pack(side="right", padx=2)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(header, textvariable=self.status_var).pack(side="right", padx=(0, 10))

        # Content area for tab panels
        content = ttk.Frame(self, relief="sunken", borderwidth=1)
        content.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Settings tab
        self.settings_frame = SettingsFrame(content)
        self._tab_frames["Settings"] = self.settings_frame

        # Input tab
        self.input_frame = InputFrame(content)
        self._tab_frames["Input"] = self.input_frame

        # Outputs tab
        self.outputs_frame = OutputsFrame(content, self.printers, self._refresh_printers)
        self._tab_frames["Outputs"] = self.outputs_frame

        # Show initial tab
        self._switch_tab("Settings")

        # Log output at bottom
        log_frame = ttk.LabelFrame(self, text="Output Log", padding=5)
        log_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def _switch_tab(self, tab_name: str):
        """Switch to a different tab."""
        # Hide all frames
        for frame in self._tab_frames.values():
            frame.pack_forget()

        # Show selected frame
        self._tab_frames[tab_name].pack(fill="both", expand=True, padx=5, pady=5)
        self._current_tab.set(tab_name)

        # Update button styles to show active tab
        for name, btn in self._tab_buttons.items():
            if name == tab_name:
                btn.state(["pressed"])
            else:
                btn.state(["!pressed"])

    def _get_printers(self) -> list[str]:
        try:
            from pdfmill.printer import list_printers
            return list_printers()
        except Exception as e:
            self._log(f"Warning: Could not enumerate printers: {e}")
            return []

    def _refresh_printers(self):
        self.printers = self._get_printers()
        self.outputs_frame.printers = self.printers
        self.outputs_frame.editor.printers = self.printers
        self._log(f"Found {len(self.printers)} printers")

    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self._new_config, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self._open_config, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self._save_config, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._save_config_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

        # Keyboard shortcuts
        self.bind("<Control-n>", lambda e: self._new_config())
        self.bind("<Control-o>", lambda e: self._open_config())
        self.bind("<Control-s>", lambda e: self._save_config())

    def _log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _new_config(self):
        self.current_file = None
        self.title("pdfmill Config Editor - New Config")

        # Default config
        config = Config(
            version=1,
            settings=Settings(),
            input=InputConfig(),
            outputs={"default": OutputProfile(pages="all", output_dir=Path("./output"))},
        )
        self._load_to_ui(config)

    def _open_config(self):
        path = filedialog.askopenfilename(
            title="Open Config",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            config = load_config(Path(path))
            self._load_to_ui(config)
            self.current_file = Path(path)
            self.title(f"pdfmill Config Editor - {path}")
            self._log(f"Loaded: {path}")
        except (ConfigError, FileNotFoundError) as e:
            messagebox.showerror("Error", f"Failed to load config:\n{e}")

    def _load_to_ui(self, config: Config):
        self.settings_frame.load(config.settings)
        self.input_frame.load(config.input)
        self.outputs_frame.load(config.outputs)

    def _ui_to_config(self) -> Config:
        return Config(
            version=1,
            settings=self.settings_frame.to_settings(),
            input=self.input_frame.to_input_config(),
            outputs=self.outputs_frame.to_outputs(),
        )

    def _config_to_dict(self, config: Config) -> dict[str, Any]:
        """Convert Config dataclass to YAML-compatible dict."""
        data: dict[str, Any] = {
            "version": config.version,
            "settings": {
                "on_error": config.settings.on_error,
                "cleanup_source": config.settings.cleanup_source,
                "cleanup_output_after_print": config.settings.cleanup_output_after_print,
            },
            "input": {
                "path": str(config.input.path),
                "pattern": config.input.pattern,
            },
            "outputs": {},
        }

        if config.input.sort:
            data["input"]["sort"] = config.input.sort
        if config.input.filter:
            data["input"]["filter"] = {
                "keywords": config.input.filter.keywords,
                "match": config.input.filter.match,
            }

        for name, profile in config.outputs.items():
            p: dict[str, Any] = {
                "pages": profile.pages,
                "output_dir": str(profile.output_dir),
            }
            if profile.filename_prefix:
                p["filename_prefix"] = profile.filename_prefix
            if profile.filename_suffix:
                p["filename_suffix"] = profile.filename_suffix
            if profile.sort:
                p["sort"] = profile.sort
            if profile.debug:
                p["debug"] = profile.debug

            if profile.transforms:
                p["transforms"] = []
                for t in profile.transforms:
                    if t.type == "rotate" and t.rotate:
                        p["transforms"].append({"rotate": t.rotate.angle})
                    elif t.type == "crop" and t.crop:
                        p["transforms"].append({
                            "crop": {
                                "lower_left": list(t.crop.lower_left),
                                "upper_right": list(t.crop.upper_right),
                            }
                        })
                    elif t.type == "size" and t.size:
                        p["transforms"].append({
                            "size": {
                                "width": t.size.width,
                                "height": t.size.height,
                                "fit": t.size.fit,
                            }
                        })

            if profile.print.enabled or profile.print.targets:
                p["print"] = {
                    "enabled": profile.print.enabled,
                    "merge": profile.print.merge,
                }
                if profile.print.targets:
                    p["print"]["targets"] = {}
                    for tname, target in profile.print.targets.items():
                        p["print"]["targets"][tname] = {
                            "printer": target.printer,
                            "weight": target.weight,
                            "copies": target.copies,
                        }
                        if target.args:
                            p["print"]["targets"][tname]["args"] = target.args

            data["outputs"][name] = p

        return data

    def _save_config(self):
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self._save_config_as()

    def _save_config_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Config As",
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if path:
            self._save_to_file(Path(path))
            self.current_file = Path(path)
            self.title(f"pdfmill Config Editor - {path}")

    def _save_to_file(self, path: Path):
        try:
            config = self._ui_to_config()
            data = self._config_to_dict(config)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            self._log(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config:\n{e}")

    def _validate(self):
        try:
            config = self._ui_to_config()
            if not config.outputs:
                raise ConfigError("At least one output profile is required")
            self._log("Configuration is valid!")
            self.status_var.set("Valid")
        except Exception as e:
            self._log(f"Validation error: {e}")
            self.status_var.set("Invalid")
            messagebox.showerror("Validation Error", str(e))

    def _run(self):
        self._execute_pipeline(dry_run=False)

    def _dry_run(self):
        self._execute_pipeline(dry_run=True)

    def _execute_pipeline(self, dry_run: bool):
        if self.running:
            self._log("Pipeline already running!")
            return

        try:
            config = self._ui_to_config()
            if not config.outputs:
                raise ConfigError("At least one output profile is required")
        except Exception as e:
            self._log(f"Configuration error: {e}")
            return

        input_path = Path(self.input_frame.path_var.get())

        self.running = True
        self.status_var.set("Running..." if not dry_run else "Dry Run...")
        self._log(f"\n{'='*40}\n{'DRY RUN' if dry_run else 'RUNNING'} pipeline...\n{'='*40}")

        thread = threading.Thread(
            target=self._pipeline_thread,
            args=(config, input_path, dry_run),
            daemon=True,
        )
        thread.start()
        self.after(100, self._poll_output)

    def _pipeline_thread(self, config: Config, input_path: Path, dry_run: bool):
        import io
        import sys

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            from pdfmill.processor import process
            process(config=config, input_path=input_path, dry_run=dry_run)

            output = sys.stdout.getvalue() + sys.stderr.getvalue()
            self.output_queue.put(("output", output))
            self.output_queue.put(("complete", "Pipeline completed successfully"))
        except Exception as e:
            output = sys.stdout.getvalue() + sys.stderr.getvalue()
            self.output_queue.put(("output", output))
            self.output_queue.put(("error", str(e)))
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.running = False

    def _poll_output(self):
        while not self.output_queue.empty():
            msg_type, msg = self.output_queue.get_nowait()
            if msg_type == "output" and msg:
                self._log(msg)
            elif msg_type == "complete":
                self.status_var.set("Complete")
                self._log(f"\n=== {msg} ===\n")
            elif msg_type == "error":
                self.status_var.set("Error")
                self._log(f"\n=== ERROR: {msg} ===\n")

        if self.running:
            self.after(100, self._poll_output)

    def _show_about(self):
        from pdfmill import __version__
        messagebox.showinfo("About", f"pdfmill Config Editor\nVersion {__version__}")


def launch_gui() -> int:
    """Launch the GUI application."""
    app = PdfMillApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    launch_gui()
