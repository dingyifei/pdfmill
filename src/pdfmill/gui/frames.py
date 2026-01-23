"""Frame components for the GUI."""

import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, ttk

from pdfmill.config import (
    ErrorHandling,
    FilterConfig,
    FilterMatch,
    InputConfig,
    OutputProfile,
    PrintConfig,
    PrintTarget,
    Settings,
    SortOrder,
    Transform,
    WatchSettings,
)
from pdfmill.gui.constants import ON_ERROR_OPTIONS, SORT_OPTIONS
from pdfmill.gui.dialogs import PrintTargetDialog, TransformDialog
from pdfmill.gui.i18n import _


class SettingsFrame(ttk.LabelFrame):
    """Frame for editing global settings."""

    def __init__(self, parent):
        super().__init__(parent, text=_("Global Settings"), padding=10)

        self.on_error_var = tk.StringVar(value="continue")
        self.cleanup_source_var = tk.BooleanVar(value=False)
        self.cleanup_output_var = tk.BooleanVar(value=False)

        # On error
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("On Error:")).pack(side="left")
        ttk.Combobox(row, textvariable=self.on_error_var, values=ON_ERROR_OPTIONS, state="readonly", width=15).pack(
            side="left", padx=5
        )

        # Cleanup checkboxes
        ttk.Checkbutton(self, text=_("Cleanup source files after processing"), variable=self.cleanup_source_var).pack(
            anchor="w", pady=2
        )
        ttk.Checkbutton(self, text=_("Cleanup output files after printing"), variable=self.cleanup_output_var).pack(
            anchor="w", pady=2
        )

    def load(self, settings: Settings):
        self.on_error_var.set(settings.on_error)
        self.cleanup_source_var.set(settings.cleanup_source)
        self.cleanup_output_var.set(settings.cleanup_output_after_print)

    def to_settings(self) -> Settings:
        return Settings(
            on_error=ErrorHandling(self.on_error_var.get()),
            cleanup_source=self.cleanup_source_var.get(),
            cleanup_output_after_print=self.cleanup_output_var.get(),
        )


class InputFrame(ttk.LabelFrame):
    """Frame for editing input configuration."""

    def __init__(self, parent):
        super().__init__(parent, text=_("Input Configuration"), padding=10)

        self.path_var = tk.StringVar(value="./input")
        self.pattern_var = tk.StringVar(value="*.pdf")
        self.sort_var = tk.StringVar(value="")
        self.keywords_var = tk.StringVar(value="")
        self.match_var = tk.StringVar(value="any")

        # Input path
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Input Path:")).pack(side="left")
        ttk.Entry(row, textvariable=self.path_var, width=40).pack(side="left", padx=5)
        ttk.Button(row, text=_("Browse..."), command=self._browse_path).pack(side="left")

        # Pattern
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("File Pattern:")).pack(side="left")
        ttk.Entry(row, textvariable=self.pattern_var, width=20).pack(side="left", padx=5)

        # Sort
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Sort Order:")).pack(side="left")
        ttk.Combobox(row, textvariable=self.sort_var, values=SORT_OPTIONS, width=15).pack(side="left", padx=5)

        # Filter section
        filter_frame = ttk.LabelFrame(self, text=_("Keyword Filter (optional)"), padding=5)
        filter_frame.pack(fill="x", pady=5)

        row = ttk.Frame(filter_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Keywords (comma-separated):")).pack(side="left")
        ttk.Entry(row, textvariable=self.keywords_var, width=30).pack(side="left", padx=5)

        row = ttk.Frame(filter_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Match:")).pack(side="left")
        ttk.Radiobutton(row, text=_("Any (OR)"), variable=self.match_var, value="any").pack(side="left", padx=5)
        ttk.Radiobutton(row, text=_("All (AND)"), variable=self.match_var, value="all").pack(side="left", padx=5)

    def _browse_path(self):
        path = filedialog.askdirectory(title=_("Select Input Directory"))
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
                filter_config = FilterConfig(keywords=keywords, match=FilterMatch(self.match_var.get()))

        sort_str = self.sort_var.get()
        return InputConfig(
            path=Path(self.path_var.get()),
            pattern=self.pattern_var.get(),
            filter=filter_config,
            sort=SortOrder(sort_str) if sort_str else None,
        )


class OutputProfileEditor(ttk.Frame):
    """Editor for a single output profile."""

    def __init__(self, parent, printers: list[str], on_refresh_printers=None):
        super().__init__(parent, padding=10)
        self.printers = printers
        self._on_refresh_printers = on_refresh_printers
        self.transforms: list[Transform] = []
        self.print_targets: dict[str, PrintTarget] = {}

        self.name_var = tk.StringVar()
        self.enabled_var = tk.BooleanVar(value=True)
        self.pages_var = tk.StringVar(value="all")
        self.output_dir_var = tk.StringVar(value="./output")
        self.prefix_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        self.sort_var = tk.StringVar(value="name_asc")
        self.debug_var = tk.BooleanVar(value=False)
        self.print_enabled_var = tk.BooleanVar(value=False)
        self.print_merge_var = tk.BooleanVar(value=True)

        # Profile name and enabled
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Profile Name:")).pack(side="left")
        ttk.Entry(row, textvariable=self.name_var, width=20).pack(side="left", padx=5)
        ttk.Checkbutton(row, text=_("Enabled"), variable=self.enabled_var).pack(side="left", padx=10)

        # Pages
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Pages:")).pack(side="left")
        ttk.Entry(row, textvariable=self.pages_var, width=15).pack(side="left", padx=5)
        ttk.Label(row, text=_("(e.g., all, last, 1-3, first)")).pack(side="left")

        # Output dir
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Output Dir:")).pack(side="left")
        ttk.Entry(row, textvariable=self.output_dir_var, width=30).pack(side="left", padx=5)
        ttk.Button(row, text=_("Browse..."), command=self._browse_output).pack(side="left")

        # Prefix/Suffix
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Prefix:")).pack(side="left")
        ttk.Entry(row, textvariable=self.prefix_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Suffix:")).pack(side="left")
        ttk.Entry(row, textvariable=self.suffix_var, width=10).pack(side="left", padx=5)

        # Sort
        row = ttk.Frame(self)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Sort Override:")).pack(side="left")
        ttk.Combobox(row, textvariable=self.sort_var, values=SORT_OPTIONS, width=15).pack(side="left", padx=5)

        # Debug
        ttk.Checkbutton(self, text=_("Debug mode (save intermediate files)"), variable=self.debug_var).pack(
            anchor="w", pady=2
        )

        # Transforms section
        tf = ttk.LabelFrame(self, text=_("Transforms"), padding=5)
        tf.pack(fill="both", expand=True, pady=5)

        self.transform_list = tk.Listbox(tf, height=4)
        self.transform_list.pack(side="left", fill="both", expand=True)

        btn_col = ttk.Frame(tf)
        btn_col.pack(side="left", padx=5)
        ttk.Button(btn_col, text=_("Add"), command=self._add_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text=_("Edit"), command=self._edit_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text=_("Copy"), command=self._copy_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text=_("Remove"), command=self._remove_transform).pack(fill="x", pady=1)
        ttk.Button(btn_col, text=_("Up"), command=self._move_up).pack(fill="x", pady=1)
        ttk.Button(btn_col, text=_("Down"), command=self._move_down).pack(fill="x", pady=1)

        # Print config section
        pf = ttk.LabelFrame(self, text=_("Print Configuration"), padding=5)
        pf.pack(fill="x", pady=5)

        row = ttk.Frame(pf)
        row.pack(fill="x")
        ttk.Checkbutton(row, text=_("Enabled"), variable=self.print_enabled_var).pack(side="left")
        ttk.Checkbutton(row, text=_("Merge PDFs before printing"), variable=self.print_merge_var).pack(
            side="left", padx=10
        )

        row = ttk.Frame(pf)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Print Targets:")).pack(side="left")

        self.target_list = tk.Listbox(pf, height=3)
        self.target_list.pack(fill="x", pady=2)

        btn_row = ttk.Frame(pf)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text=_("Add Target"), command=self._add_target).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Edit Target"), command=self._edit_target).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Copy Target"), command=self._copy_target).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Remove Target"), command=self._remove_target).pack(side="left", padx=2)

    def _browse_output(self):
        path = filedialog.askdirectory(title=_("Select Output Directory"))
        if path:
            self.output_dir_var.set(path)

    def _refresh_printers(self):
        if self._on_refresh_printers:
            self._on_refresh_printers()

    def _transform_str(self, t: Transform) -> str:
        disabled_prefix = "[DISABLED] " if not t.enabled else ""
        if t.type == "rotate" and t.rotate:
            return f"{disabled_prefix}rotate: {t.rotate.angle}"
        elif t.type == "crop" and t.crop:
            return f"{disabled_prefix}crop: {t.crop.lower_left} -> {t.crop.upper_right}"
        elif t.type == "size" and t.size:
            return f"{disabled_prefix}size: {t.size.width} x {t.size.height} ({t.size.fit})"
        elif t.type == "stamp" and t.stamp:
            return f"{disabled_prefix}stamp: '{t.stamp.text}' at {t.stamp.position}"
        elif t.type == "split" and t.split:
            n = len(t.split.regions)
            return f"{disabled_prefix}split: {n} region(s)"
        elif t.type == "combine" and t.combine:
            return f"{disabled_prefix}combine: {t.combine.pages_per_output} pages -> {t.combine.page_size}"
        elif t.type == "render" and t.render:
            return f"{disabled_prefix}render: {t.render.dpi} DPI"
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

    def _copy_transform(self):
        sel = self.transform_list.curselection()
        if sel:
            idx = sel[0]
            copy = deepcopy(self.transforms[idx])
            self.transforms.insert(idx + 1, copy)
            self._refresh_transforms()
            self.transform_list.selection_set(idx + 1)

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

    def _copy_target(self):
        sel = self.target_list.curselection()
        if sel:
            name = list(self.print_targets.keys())[sel[0]]
            target = self.print_targets[name]
            # Generate new name
            i = 2
            new_name = f"{name}_copy"
            while new_name in self.print_targets:
                new_name = f"{name}_copy{i}"
                i += 1
            self.print_targets[new_name] = deepcopy(target)
            self._refresh_targets()

    def load(self, name: str, profile: OutputProfile):
        self.name_var.set(name)
        self.enabled_var.set(profile.enabled)
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
            enabled=self.enabled_var.get(),
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
            sort=SortOrder(self.sort_var.get()) if self.sort_var.get() else None,
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

        ttk.Label(left, text=_("Profiles:")).pack(anchor="w")
        self.profile_list = tk.Listbox(left, width=20, height=15)
        self.profile_list.pack(fill="y", expand=True)
        self.profile_list.bind("<<ListboxSelect>>", self._on_select)

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text=_("Add"), command=self._add_profile).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=_("Copy"), command=self._copy_profile).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=_("Remove"), command=self._remove_profile).pack(side="left", padx=2)

        # Right panel - profile editor
        self.editor = OutputProfileEditor(self, printers, on_refresh_printers)
        self.editor.pack(side="left", fill="both", expand=True)

    def _refresh_list(self):
        self.profile_list.delete(0, tk.END)
        for name, profile in self.profiles.items():
            display_name = f"[DISABLED] {name}" if not profile.enabled else name
            self.profile_list.insert(tk.END, display_name)

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
        display_name = self.profile_list.get(sel[0])
        # Strip [DISABLED] prefix if present
        name = display_name.replace("[DISABLED] ", "")
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
            display_name = self.profile_list.get(sel[0])
            # Strip [DISABLED] prefix if present
            name = display_name.replace("[DISABLED] ", "")
            del self.profiles[name]
            self.current_profile = None
            self._refresh_list()

    def _copy_profile(self):
        sel = self.profile_list.curselection()
        if sel:
            self._save_current()
            display_name = self.profile_list.get(sel[0])
            name = display_name.replace("[DISABLED] ", "")
            profile = self.profiles[name]
            # Generate new name
            i = 2
            new_name = f"{name}_copy"
            while new_name in self.profiles:
                new_name = f"{name}_copy{i}"
                i += 1
            self.profiles[new_name] = deepcopy(profile)
            self._refresh_list()
            # Select the new profile
            idx = list(self.profiles.keys()).index(new_name)
            self.profile_list.selection_clear(0, tk.END)
            self.profile_list.selection_set(idx)
            self.current_profile = new_name
            self.editor.load(new_name, self.profiles[new_name])

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


class WatchFrame(ttk.LabelFrame):
    """Frame for watch mode controls and logging."""

    def __init__(self, parent):
        super().__init__(parent, text=_("Watch Mode"), padding=10)

        self._on_start = None
        self._on_stop = None

        # Settings section
        settings_frame = ttk.LabelFrame(self, text=_("Watch Settings"), padding=5)
        settings_frame.pack(fill="x", pady=(0, 10))

        # Poll interval
        row = ttk.Frame(settings_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Poll Interval (seconds):")).pack(side="left")
        self.poll_interval_var = tk.StringVar(value="2.0")
        ttk.Spinbox(
            row,
            textvariable=self.poll_interval_var,
            from_=0.5,
            to=60.0,
            increment=0.5,
            width=8,
        ).pack(side="left", padx=5)
        ttk.Label(row, text=_("(for network drives)")).pack(side="left")

        # Debounce delay
        row = ttk.Frame(settings_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Debounce Delay (seconds):")).pack(side="left")
        self.debounce_delay_var = tk.StringVar(value="1.0")
        ttk.Spinbox(
            row,
            textvariable=self.debounce_delay_var,
            from_=0.1,
            to=10.0,
            increment=0.1,
            width=8,
        ).pack(side="left", padx=5)
        ttk.Label(row, text=_("(file write wait)")).pack(side="left")

        # Checkboxes
        self.process_existing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame,
            text=_("Process existing files on startup"),
            variable=self.process_existing_var,
        ).pack(anchor="w", pady=2)

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            settings_frame,
            text=_("Dry run (preview only)"),
            variable=self.dry_run_var,
        ).pack(anchor="w", pady=2)

        # Control buttons and status row
        control_row = ttk.Frame(self)
        control_row.pack(fill="x", pady=10)

        self.start_btn = ttk.Button(control_row, text=_("Start Watching"), command=self._on_start_click)
        self.start_btn.pack(side="left", padx=(0, 5))

        self.stop_btn = ttk.Button(control_row, text=_("Stop Watching"), command=self._on_stop_click, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 20))

        ttk.Label(control_row, text=_("Status:")).pack(side="left")
        self.status_var = tk.StringVar(value=_("Stopped"))
        self.status_label = ttk.Label(control_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=5)

        self.count_var = tk.StringVar(value="0 files")
        ttk.Label(control_row, textvariable=self.count_var).pack(side="right")

        # Log area
        log_frame = ttk.LabelFrame(self, text=_("Watch Log"), padding=5)
        log_frame.pack(fill="both", expand=True, pady=(0, 5))

        from tkinter import scrolledtext

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Clear log button
        ttk.Button(self, text=_("Clear Log"), command=self._clear_log).pack(anchor="w")

    def set_callbacks(self, on_start, on_stop):
        """Set callback functions for start/stop buttons."""
        self._on_start = on_start
        self._on_stop = on_stop

    def _on_start_click(self):
        if self._on_start:
            self._on_start()

    def _on_stop_click(self):
        if self._on_stop:
            self._on_stop()

    def set_watching(self, watching: bool):
        """Update UI state based on watching status."""
        if watching:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.status_var.set(_("Watching..."))
        else:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_var.set(_("Stopped"))

    def update_count(self, count: int):
        """Update the processed file count."""
        self.count_var.set(_("{} files").format(count))

    def log(self, msg: str):
        """Append a message to the log area."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        """Clear the log area."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def load(self, watch_settings: WatchSettings):
        """Load watch settings into UI."""
        self.poll_interval_var.set(str(watch_settings.poll_interval))
        self.debounce_delay_var.set(str(watch_settings.debounce_delay))
        self.process_existing_var.set(watch_settings.process_existing)

    def to_watch_settings(self) -> WatchSettings:
        """Build WatchSettings from UI values."""
        return WatchSettings(
            poll_interval=float(self.poll_interval_var.get()),
            debounce_delay=float(self.debounce_delay_var.get()),
            process_existing=self.process_existing_var.get(),
        )
