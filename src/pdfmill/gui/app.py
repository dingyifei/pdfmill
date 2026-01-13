"""Main application window for the GUI."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

import yaml

from pdfmill.config import (
    Config,
    ConfigError,
    InputConfig,
    OutputProfile,
    Settings,
    load_config,
)
from pdfmill.gui.dpi import enable_high_dpi
from pdfmill.gui.frames import InputFrame, OutputsFrame, SettingsFrame
from pdfmill.gui.i18n import _

# Enable high DPI before creating any Tk windows
enable_high_dpi()


class PdfMillApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title(_("pdfmill Config Editor"))

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
            dpi = self.winfo_fpixels("1i")  # Pixels per inch
            scale_factor = dpi / 72.0  # 72 is the base DPI

            # Apply scaling to Tk
            self.tk.call("tk", "scaling", scale_factor)

            # Configure ttk style for better appearance
            style = ttk.Style()

            # Use a modern theme if available
            available_themes = style.theme_names()
            if "vista" in available_themes:
                style.theme_use("vista")
            elif "clam" in available_themes:
                style.theme_use("clam")

            # Calculate scaled font size (base 9pt, scaled for DPI)
            # Use a more conservative scaling to avoid oversized UI
            base_font_size = int(9 * (dpi / 96.0) * 0.85)  # 96 DPI is Windows default
            base_font_size = max(8, min(base_font_size, 11))  # Clamp between 8-11

            # Configure default fonts for better readability
            default_font = ("Segoe UI", base_font_size)
            heading_font = ("Segoe UI", base_font_size + 1, "bold")
            mono_font = ("Consolas", base_font_size)

            # Apply fonts to ttk widgets
            style.configure(".", font=default_font)
            style.configure("TLabel", font=default_font)
            style.configure("TButton", font=default_font, padding=(6, 2))
            style.configure("TCheckbutton", font=default_font)
            style.configure("TRadiobutton", font=default_font)
            style.configure("TEntry", font=default_font, padding=2)
            style.configure("TCombobox", font=default_font, padding=2)
            style.configure("TLabelframe.Label", font=heading_font)
            style.configure("TNotebook.Tab", font=default_font, padding=(8, 4))
            style.configure("TSpinbox", font=default_font, padding=2)

            # Configure Listbox and Text widgets (tk, not ttk)
            self.option_add("*Font", default_font)
            self.option_add("*Listbox.font", default_font)
            self.option_add("*Text.font", mono_font)

            # Store for later use
            self._mono_font = mono_font
            self._scale_factor = scale_factor

        except Exception:
            # Fallback if DPI detection fails
            self._mono_font = ("Consolas", 9)
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

        tab_labels = {"Settings": _("Settings"), "Input": _("Input"), "Outputs": _("Outputs")}
        for tab_name in ["Settings", "Input", "Outputs"]:
            btn = ttk.Button(tab_frame, text=tab_labels[tab_name], command=lambda t=tab_name: self._switch_tab(t))
            btn.pack(side="left", padx=(0, 2))
            self._tab_buttons[tab_name] = btn

        # Action buttons on the right
        ttk.Button(header, text=_("Run"), command=self._run).pack(side="right", padx=2)
        ttk.Button(header, text=_("Dry Run"), command=self._dry_run).pack(side="right", padx=2)
        ttk.Button(header, text=_("Validate"), command=self._validate).pack(side="right", padx=2)

        self.status_var = tk.StringVar(value=_("Ready"))
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
        log_frame = ttk.LabelFrame(self, text=_("Output Log"), padding=5)
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
            self._log(_("Warning: Could not enumerate printers: {}").format(e))
            return []

    def _refresh_printers(self):
        self.printers = self._get_printers()
        self.outputs_frame.printers = self.printers
        self.outputs_frame.editor.printers = self.printers
        self._log(_("Found {} printers").format(len(self.printers)))

    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("File"), menu=file_menu)
        file_menu.add_command(label=_("New"), command=self._new_config, accelerator="Ctrl+N")
        file_menu.add_command(label=_("Open..."), command=self._open_config, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label=_("Save"), command=self._save_config, accelerator="Ctrl+S")
        file_menu.add_command(label=_("Save As..."), command=self._save_config_as)
        file_menu.add_separator()
        file_menu.add_command(label=_("Exit"), command=self.quit)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("Help"), menu=help_menu)
        help_menu.add_command(label=_("About"), command=self._show_about)

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
        self.title(_("pdfmill Config Editor") + " - " + _("New Config"))

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
            title=_("Open Config"),
            filetypes=[(_("YAML files"), "*.yaml *.yml"), (_("All files"), "*.*")],
        )
        if not path:
            return

        try:
            config = load_config(Path(path))
            self._load_to_ui(config)
            self.current_file = Path(path)
            self.title(_("pdfmill Config Editor") + f" - {path}")
            self._log(_("Loaded: {}").format(path))
        except (ConfigError, FileNotFoundError) as e:
            messagebox.showerror(_("Error"), _("Failed to load config:") + f"\n{e}")

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
                "on_error": config.settings.on_error.value,
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
            data["input"]["sort"] = config.input.sort.value
        if config.input.filter:
            data["input"]["filter"] = {
                "keywords": config.input.filter.keywords,
                "match": config.input.filter.match.value,
            }

        for name, profile in config.outputs.items():
            p: dict[str, Any] = {
                "pages": profile.pages,
                "output_dir": str(profile.output_dir),
            }
            # Only export enabled if False (True is default)
            if not profile.enabled:
                p["enabled"] = profile.enabled
            if profile.filename_prefix:
                p["filename_prefix"] = profile.filename_prefix
            if profile.filename_suffix:
                p["filename_suffix"] = profile.filename_suffix
            if profile.sort:
                p["sort"] = profile.sort.value
            if profile.debug:
                p["debug"] = profile.debug

            if profile.transforms:
                p["transforms"] = []
                for t in profile.transforms:
                    transform_dict: dict[str, Any] = {}
                    if t.type == "rotate" and t.rotate:
                        transform_dict["rotate"] = t.rotate.angle
                    elif t.type == "crop" and t.crop:
                        transform_dict["crop"] = {
                            "lower_left": list(t.crop.lower_left),
                            "upper_right": list(t.crop.upper_right),
                        }
                    elif t.type == "size" and t.size:
                        transform_dict["size"] = {
                            "width": t.size.width,
                            "height": t.size.height,
                            "fit": t.size.fit.value,
                        }
                    elif t.type == "stamp" and t.stamp:
                        stamp_dict: dict[str, Any] = {
                            "text": t.stamp.text,
                            "position": t.stamp.position.value,
                            "font_size": t.stamp.font_size,
                            "margin": t.stamp.margin,
                        }
                        if t.stamp.position.value == "custom":
                            stamp_dict["x"] = t.stamp.x
                            stamp_dict["y"] = t.stamp.y
                        transform_dict["stamp"] = stamp_dict
                    elif t.type == "split" and t.split:
                        transform_dict["split"] = {
                            "regions": [
                                {
                                    "lower_left": list(r.lower_left),
                                    "upper_right": list(r.upper_right),
                                }
                                for r in t.split.regions
                            ]
                        }
                    elif t.type == "combine" and t.combine:
                        transform_dict["combine"] = {
                            "page_size": list(t.combine.page_size),
                            "pages_per_output": t.combine.pages_per_output,
                            "layout": [
                                {
                                    "page": item.page,
                                    "position": list(item.position),
                                    "scale": item.scale,
                                }
                                for item in t.combine.layout
                            ],
                        }
                    elif t.type == "render" and t.render:
                        transform_dict["render"] = {"dpi": t.render.dpi}
                    # Only export enabled if False (True is default)
                    if not t.enabled:
                        transform_dict["enabled"] = t.enabled
                    if transform_dict:
                        p["transforms"].append(transform_dict)

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
            title=_("Save Config As"),
            defaultextension=".yaml",
            filetypes=[(_("YAML files"), "*.yaml *.yml"), (_("All files"), "*.*")],
        )
        if path:
            self._save_to_file(Path(path))
            self.current_file = Path(path)
            self.title(_("pdfmill Config Editor") + f" - {path}")

    def _save_to_file(self, path: Path):
        try:
            config = self._ui_to_config()
            data = self._config_to_dict(config)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            self._log(_("Saved: {}").format(path))
        except Exception as e:
            messagebox.showerror(_("Error"), _("Failed to save config:") + f"\n{e}")

    def _validate(self):
        try:
            config = self._ui_to_config()
            if not config.outputs:
                raise ConfigError(_("At least one output profile is required"))
            self._log(_("Configuration is valid!"))
            self.status_var.set(_("Valid"))
        except Exception as e:
            self._log(_("Validation error: {}").format(e))
            self.status_var.set(_("Invalid"))
            messagebox.showerror(_("Validation Error"), str(e))

    def _run(self):
        self._execute_pipeline(dry_run=False)

    def _dry_run(self):
        self._execute_pipeline(dry_run=True)

    def _execute_pipeline(self, dry_run: bool):
        if self.running:
            self._log(_("Pipeline already running!"))
            return

        try:
            config = self._ui_to_config()
            if not config.outputs:
                raise ConfigError(_("At least one output profile is required"))
        except Exception as e:
            self._log(_("Configuration error: {}").format(e))
            return

        input_path = Path(self.input_frame.path_var.get())

        self.running = True
        self.status_var.set(_("Running...") if not dry_run else _("Dry Run..."))
        mode_str = _("DRY RUN") if dry_run else _("RUNNING")
        self._log(f"\n{'=' * 40}\n{mode_str} pipeline...\n{'=' * 40}")

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

        from pdfmill.logging_config import setup_logging

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr

        # Reconfigure logging to use captured streams
        setup_logging(stdout_stream=captured_stdout, stderr_stream=captured_stderr)

        try:
            from pdfmill.processor import process

            process(config=config, input_path=input_path, dry_run=dry_run)

            output = captured_stdout.getvalue() + captured_stderr.getvalue()
            self.output_queue.put(("output", output))
            self.output_queue.put(("complete", _("Pipeline completed successfully")))
        except Exception as e:
            output = captured_stdout.getvalue() + captured_stderr.getvalue()
            self.output_queue.put(("output", output))
            self.output_queue.put(("error", str(e)))
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            # Restore logging to use real stdout/stderr
            setup_logging()
            self.running = False

    def _poll_output(self):
        while not self.output_queue.empty():
            msg_type, msg = self.output_queue.get_nowait()
            if msg_type == "output" and msg:
                self._log(msg)
            elif msg_type == "complete":
                self.status_var.set(_("Complete"))
                self._log(f"\n=== {msg} ===\n")
            elif msg_type == "error":
                self.status_var.set(_("Error"))
                self._log("\n=== " + _("ERROR") + f": {msg} ===\n")

        if self.running:
            self.after(100, self._poll_output)

    def _show_about(self):
        from pdfmill import __version__

        messagebox.showinfo(_("About"), _("pdfmill Config Editor") + "\n" + _("Version {}").format(__version__))


def launch_gui() -> int:
    """Launch the GUI application."""
    app = PdfMillApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    launch_gui()
