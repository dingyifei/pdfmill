"""Dialog windows for the GUI."""

import shlex
import tkinter as tk
from tkinter import messagebox, ttk

from pdfmill.config import (
    CombineLayoutItem,
    CombineTransform,
    CropTransform,
    FitMode,
    PrintTarget,
    RenderTransform,
    RotateTransform,
    SizeTransform,
    SplitRegion,
    SplitTransform,
    StampPosition,
    StampTransform,
    Transform,
)
from pdfmill.gui.constants import (
    FIT_MODES,
    ROTATE_ANGLES,
    STAMP_POSITIONS,
    TRANSFORM_TYPES,
)
from pdfmill.gui.i18n import _


class TransformDialog(tk.Toplevel):
    """Dialog for editing a single transform."""

    def __init__(self, parent, transform: Transform | None = None):
        super().__init__(parent)
        self.title(_("Edit Transform"))
        self.geometry("500x500")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.result = None

        self.enabled_var = tk.BooleanVar(value=True)
        self.type_var = tk.StringVar(value="rotate")
        self.angle_var = tk.StringVar(value="90")
        self.crop_ll_x_var = tk.StringVar(value="0")
        self.crop_ll_y_var = tk.StringVar(value="0")
        self.crop_ur_x_var = tk.StringVar(value="612")
        self.crop_ur_y_var = tk.StringVar(value="792")
        self.size_w_var = tk.StringVar(value="100mm")
        self.size_h_var = tk.StringVar(value="150mm")
        self.fit_var = tk.StringVar(value="contain")
        # Stamp variables
        self.stamp_text_var = tk.StringVar(value="{page}/{total}")
        self.stamp_pos_var = tk.StringVar(value="bottom-right")
        self.stamp_x_var = tk.StringVar(value="10mm")
        self.stamp_y_var = tk.StringVar(value="10mm")
        self.stamp_fontsize_var = tk.IntVar(value=10)
        self.stamp_margin_var = tk.StringVar(value="10mm")
        self.render_dpi_var = tk.IntVar(value=150)

        # Split regions list
        self.split_regions: list[SplitRegion] = []
        # Combine layout list
        self.combine_layout: list[CombineLayoutItem] = []
        self.combine_page_w_var = tk.StringVar(value="8.5in")
        self.combine_page_h_var = tk.StringVar(value="11in")
        self.combine_pages_per_var = tk.IntVar(value=2)

        # Enabled checkbox
        row = ttk.Frame(self, padding=10)
        row.pack(fill="x")
        ttk.Checkbutton(row, text=_("Enabled"), variable=self.enabled_var).pack(side="left")

        # Type selector
        row = ttk.Frame(self, padding=10)
        row.pack(fill="x")
        ttk.Label(row, text=_("Type:")).pack(side="left")
        type_combo = ttk.Combobox(row, textvariable=self.type_var, values=TRANSFORM_TYPES, state="readonly", width=15)
        type_combo.pack(side="left", padx=5)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._update_fields())

        # Rotate frame
        self.rotate_frame = ttk.LabelFrame(self, text=_("Rotate Options"), padding=10)
        row = ttk.Frame(self.rotate_frame)
        row.pack(fill="x")
        ttk.Label(row, text=_("Angle:")).pack(side="left")
        ttk.Combobox(row, textvariable=self.angle_var, values=ROTATE_ANGLES, width=15).pack(side="left", padx=5)

        # Crop frame
        self.crop_frame = ttk.LabelFrame(self, text=_("Crop Options"), padding=10)
        row = ttk.Frame(self.crop_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Lower Left X:")).pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ll_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Y:")).pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ll_y_var, width=10).pack(side="left", padx=5)
        row = ttk.Frame(self.crop_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Upper Right X:")).pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ur_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Y:")).pack(side="left")
        ttk.Entry(row, textvariable=self.crop_ur_y_var, width=10).pack(side="left", padx=5)

        # Size frame
        self.size_frame = ttk.LabelFrame(self, text=_("Size Options"), padding=10)
        row = ttk.Frame(self.size_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Width:")).pack(side="left")
        ttk.Entry(row, textvariable=self.size_w_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Height:")).pack(side="left")
        ttk.Entry(row, textvariable=self.size_h_var, width=10).pack(side="left", padx=5)
        row = ttk.Frame(self.size_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Fit:")).pack(side="left")
        ttk.Combobox(row, textvariable=self.fit_var, values=FIT_MODES, state="readonly", width=10).pack(
            side="left", padx=5
        )

        # Stamp frame
        self.stamp_frame = ttk.LabelFrame(self, text=_("Stamp Options"), padding=10)
        row = ttk.Frame(self.stamp_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Text:")).pack(side="left")
        ttk.Entry(row, textvariable=self.stamp_text_var, width=25).pack(side="left", padx=5)
        row = ttk.Frame(self.stamp_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Position:")).pack(side="left")
        pos_combo = ttk.Combobox(row, textvariable=self.stamp_pos_var, values=STAMP_POSITIONS, width=12)
        pos_combo.pack(side="left", padx=5)
        pos_combo.bind("<<ComboboxSelected>>", lambda e: self._update_stamp_xy_state())
        row = ttk.Frame(self.stamp_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("X:")).pack(side="left")
        self.stamp_x_entry = ttk.Entry(row, textvariable=self.stamp_x_var, width=8)
        self.stamp_x_entry.pack(side="left", padx=5)
        ttk.Label(row, text=_("Y:")).pack(side="left")
        self.stamp_y_entry = ttk.Entry(row, textvariable=self.stamp_y_var, width=8)
        self.stamp_y_entry.pack(side="left", padx=5)
        ttk.Label(row, text=_("(for custom position)")).pack(side="left", padx=5)
        row = ttk.Frame(self.stamp_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Font Size:")).pack(side="left")
        ttk.Spinbox(row, textvariable=self.stamp_fontsize_var, from_=6, to=72, width=5).pack(side="left", padx=5)
        ttk.Label(row, text=_("Margin:")).pack(side="left")
        ttk.Entry(row, textvariable=self.stamp_margin_var, width=8).pack(side="left", padx=5)
        # Help text
        help_text = ttk.Label(
            self.stamp_frame,
            text=_("Placeholders: {page}, {total}, {datetime}, {date}, {time}"),
            font=("TkDefaultFont", 8),
        )
        help_text.pack(anchor="w", pady=(5, 0))

        # Split frame
        self.split_frame = ttk.LabelFrame(self, text=_("Split Options"), padding=10)
        ttk.Label(self.split_frame, text=_("Regions (each becomes a separate page):")).pack(anchor="w")
        self.split_list = tk.Listbox(self.split_frame, height=5)
        self.split_list.pack(fill="both", expand=True, pady=5)
        btn_row = ttk.Frame(self.split_frame)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text=_("Add Region"), command=self._add_split_region).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Edit Region"), command=self._edit_split_region).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Remove"), command=self._remove_split_region).pack(side="left", padx=2)

        # Combine frame
        self.combine_frame = ttk.LabelFrame(self, text=_("Combine Options"), padding=10)
        row = ttk.Frame(self.combine_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Output Page Size - Width:")).pack(side="left")
        ttk.Entry(row, textvariable=self.combine_page_w_var, width=8).pack(side="left", padx=5)
        ttk.Label(row, text=_("Height:")).pack(side="left")
        ttk.Entry(row, textvariable=self.combine_page_h_var, width=8).pack(side="left", padx=5)
        row = ttk.Frame(self.combine_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("Pages per output:")).pack(side="left")
        ttk.Spinbox(row, textvariable=self.combine_pages_per_var, from_=1, to=16, width=5).pack(side="left", padx=5)
        ttk.Label(self.combine_frame, text=_("Layout (where to place each input page):")).pack(anchor="w", pady=(5, 0))
        self.combine_list = tk.Listbox(self.combine_frame, height=5)
        self.combine_list.pack(fill="both", expand=True, pady=5)
        btn_row = ttk.Frame(self.combine_frame)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text=_("Add Placement"), command=self._add_combine_item).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Edit Placement"), command=self._edit_combine_item).pack(side="left", padx=2)
        ttk.Button(btn_row, text=_("Remove"), command=self._remove_combine_item).pack(side="left", padx=2)

        # Render frame
        self.render_frame = ttk.LabelFrame(self, text=_("Render Options"), padding=10)
        row = ttk.Frame(self.render_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=_("DPI:")).pack(side="left")
        ttk.Spinbox(row, textvariable=self.render_dpi_var, from_=72, to=600, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("(72-600, default 150)")).pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text=_("OK"), command=self._ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_("Cancel"), command=self.destroy).pack(side="right")

        # Load existing transform
        if transform:
            self._load_transform(transform)

        self._update_fields()

    def _update_fields(self):
        self.rotate_frame.pack_forget()
        self.crop_frame.pack_forget()
        self.size_frame.pack_forget()
        self.stamp_frame.pack_forget()
        self.split_frame.pack_forget()
        self.combine_frame.pack_forget()
        self.render_frame.pack_forget()

        t = self.type_var.get()
        if t == "rotate":
            self.rotate_frame.pack(fill="x", padx=10, pady=5)
        elif t == "crop":
            self.crop_frame.pack(fill="x", padx=10, pady=5)
        elif t == "size":
            self.size_frame.pack(fill="x", padx=10, pady=5)
        elif t == "stamp":
            self.stamp_frame.pack(fill="x", padx=10, pady=5)
            self._update_stamp_xy_state()
        elif t == "split":
            self.split_frame.pack(fill="both", expand=True, padx=10, pady=5)
        elif t == "combine":
            self.combine_frame.pack(fill="both", expand=True, padx=10, pady=5)
        elif t == "render":
            self.render_frame.pack(fill="x", padx=10, pady=5)

    def _update_stamp_xy_state(self):
        """Enable/disable X/Y entries based on position selection."""
        if self.stamp_pos_var.get() == "custom":
            self.stamp_x_entry.configure(state="normal")
            self.stamp_y_entry.configure(state="normal")
        else:
            self.stamp_x_entry.configure(state="disabled")
            self.stamp_y_entry.configure(state="disabled")

    def _refresh_split_list(self):
        self.split_list.delete(0, tk.END)
        for r in self.split_regions:
            self.split_list.insert(tk.END, f"{r.lower_left} -> {r.upper_right}")

    def _add_split_region(self):
        dlg = RegionDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.split_regions.append(dlg.result)
            self._refresh_split_list()

    def _edit_split_region(self):
        sel = self.split_list.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = RegionDialog(self, self.split_regions[idx])
        self.wait_window(dlg)
        if dlg.result:
            self.split_regions[idx] = dlg.result
            self._refresh_split_list()

    def _remove_split_region(self):
        sel = self.split_list.curselection()
        if sel:
            del self.split_regions[sel[0]]
            self._refresh_split_list()

    def _refresh_combine_list(self):
        self.combine_list.delete(0, tk.END)
        for item in self.combine_layout:
            self.combine_list.insert(tk.END, f"Page {item.page}: pos={item.position}, scale={item.scale}")

    def _add_combine_item(self):
        dlg = CombineItemDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.combine_layout.append(dlg.result)
            self._refresh_combine_list()

    def _edit_combine_item(self):
        sel = self.combine_list.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = CombineItemDialog(self, self.combine_layout[idx])
        self.wait_window(dlg)
        if dlg.result:
            self.combine_layout[idx] = dlg.result
            self._refresh_combine_list()

    def _remove_combine_item(self):
        sel = self.combine_list.curselection()
        if sel:
            del self.combine_layout[sel[0]]
            self._refresh_combine_list()

    def _load_transform(self, t: Transform):
        self.enabled_var.set(t.enabled)
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
        elif t.type == "stamp" and t.stamp:
            self.stamp_text_var.set(t.stamp.text)
            self.stamp_pos_var.set(t.stamp.position)
            self.stamp_x_var.set(str(t.stamp.x))
            self.stamp_y_var.set(str(t.stamp.y))
            self.stamp_fontsize_var.set(t.stamp.font_size)
            self.stamp_margin_var.set(str(t.stamp.margin))
        elif t.type == "split" and t.split:
            self.split_regions = list(t.split.regions)
            self._refresh_split_list()
        elif t.type == "combine" and t.combine:
            self.combine_page_w_var.set(t.combine.page_size[0])
            self.combine_page_h_var.set(t.combine.page_size[1])
            self.combine_pages_per_var.set(t.combine.pages_per_output)
            self.combine_layout = list(t.combine.layout)
            self._refresh_combine_list()
        elif t.type == "render" and t.render:
            self.render_dpi_var.set(t.render.dpi)

    def _ok(self):
        t = self.type_var.get()
        enabled = self.enabled_var.get()
        if t == "rotate":
            angle = self.angle_var.get()
            try:
                angle = int(angle)
            except ValueError:
                pass  # Keep as string (landscape/portrait/auto)
            self.result = Transform(type="rotate", rotate=RotateTransform(angle=angle), enabled=enabled)
        elif t == "crop":
            self.result = Transform(
                type="crop",
                crop=CropTransform(
                    lower_left=(self.crop_ll_x_var.get(), self.crop_ll_y_var.get()),
                    upper_right=(self.crop_ur_x_var.get(), self.crop_ur_y_var.get()),
                ),
                enabled=enabled,
            )
        elif t == "size":
            self.result = Transform(
                type="size",
                size=SizeTransform(
                    width=self.size_w_var.get(),
                    height=self.size_h_var.get(),
                    fit=FitMode(self.fit_var.get()),
                ),
                enabled=enabled,
            )
        elif t == "stamp":
            self.result = Transform(
                type="stamp",
                stamp=StampTransform(
                    text=self.stamp_text_var.get(),
                    position=StampPosition(self.stamp_pos_var.get()),
                    x=self.stamp_x_var.get(),
                    y=self.stamp_y_var.get(),
                    font_size=self.stamp_fontsize_var.get(),
                    margin=self.stamp_margin_var.get(),
                ),
            )
        elif t == "split":
            self.result = Transform(
                type="split",
                split=SplitTransform(regions=list(self.split_regions)),
            )
        elif t == "combine":
            self.result = Transform(
                type="combine",
                combine=CombineTransform(
                    page_size=(self.combine_page_w_var.get(), self.combine_page_h_var.get()),
                    layout=list(self.combine_layout),
                    pages_per_output=self.combine_pages_per_var.get(),
                ),
            )
        elif t == "render":
            self.result = Transform(
                type="render",
                render=RenderTransform(dpi=self.render_dpi_var.get()),
            )
        self.destroy()


class RegionDialog(tk.Toplevel):
    """Dialog for editing a split region."""

    def __init__(self, parent, region: SplitRegion | None = None):
        super().__init__(parent)
        self.title(_("Edit Region"))
        self.geometry("350x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None

        self.ll_x_var = tk.StringVar(value="0")
        self.ll_y_var = tk.StringVar(value="0")
        self.ur_x_var = tk.StringVar(value="4in")
        self.ur_y_var = tk.StringVar(value="6in")

        if region:
            self.ll_x_var.set(str(region.lower_left[0]))
            self.ll_y_var.set(str(region.lower_left[1]))
            self.ur_x_var.set(str(region.upper_right[0]))
            self.ur_y_var.set(str(region.upper_right[1]))

        ttk.Label(self, text=_("Define the crop region (supports units: mm, in, pt, cm)")).pack(pady=10, padx=10)

        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Lower Left X:")).pack(side="left")
        ttk.Entry(row, textvariable=self.ll_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Y:")).pack(side="left")
        ttk.Entry(row, textvariable=self.ll_y_var, width=10).pack(side="left", padx=5)

        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Upper Right X:")).pack(side="left")
        ttk.Entry(row, textvariable=self.ur_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Y:")).pack(side="left")
        ttk.Entry(row, textvariable=self.ur_y_var, width=10).pack(side="left", padx=5)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text=_("OK"), command=self._ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_("Cancel"), command=self.destroy).pack(side="right")

    def _ok(self):
        self.result = SplitRegion(
            lower_left=(self.ll_x_var.get(), self.ll_y_var.get()),
            upper_right=(self.ur_x_var.get(), self.ur_y_var.get()),
        )
        self.destroy()


class CombineItemDialog(tk.Toplevel):
    """Dialog for editing a combine layout item."""

    def __init__(self, parent, item: CombineLayoutItem | None = None):
        super().__init__(parent)
        self.title(_("Edit Placement"))
        self.geometry("400x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None

        self.page_var = tk.IntVar(value=0)
        self.pos_x_var = tk.StringVar(value="0")
        self.pos_y_var = tk.StringVar(value="0")
        self.scale_var = tk.DoubleVar(value=1.0)

        if item:
            self.page_var.set(item.page)
            self.pos_x_var.set(str(item.position[0]))
            self.pos_y_var.set(str(item.position[1]))
            self.scale_var.set(item.scale)

        ttk.Label(self, text=_("Define where to place an input page on the output")).pack(pady=10, padx=10)

        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Input Page (0-indexed):")).pack(side="left")
        ttk.Spinbox(row, textvariable=self.page_var, from_=0, to=15, width=5).pack(side="left", padx=5)

        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Position X:")).pack(side="left")
        ttk.Entry(row, textvariable=self.pos_x_var, width=10).pack(side="left", padx=5)
        ttk.Label(row, text=_("Y:")).pack(side="left")
        ttk.Entry(row, textvariable=self.pos_y_var, width=10).pack(side="left", padx=5)

        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Scale:")).pack(side="left")
        ttk.Entry(row, textvariable=self.scale_var, width=8).pack(side="left", padx=5)
        ttk.Label(row, text=_("(1.0 = 100%)")).pack(side="left")

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text=_("OK"), command=self._ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_("Cancel"), command=self.destroy).pack(side="right")

    def _ok(self):
        self.result = CombineLayoutItem(
            page=self.page_var.get(),
            position=(self.pos_x_var.get(), self.pos_y_var.get()),
            scale=self.scale_var.get(),
        )
        self.destroy()


class PrintTargetDialog(tk.Toplevel):
    """Dialog for editing a print target."""

    def __init__(self, parent, printers: list[str], name: str = "", target: PrintTarget | None = None):
        super().__init__(parent)
        self.title(_("Edit Print Target"))
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
        ttk.Label(row, text=_("Target Name:")).pack(side="left")
        ttk.Entry(row, textvariable=self.name_var, width=20).pack(side="left", padx=5)

        # Printer
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Printer:")).pack(side="left")
        combo = ttk.Combobox(row, textvariable=self.printer_var, values=printers, width=30)
        combo.pack(side="left", padx=5)
        if not printers:
            combo["state"] = "normal"

        # Weight
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Weight:")).pack(side="left")
        ttk.Spinbox(row, textvariable=self.weight_var, from_=1, to=1000, width=10).pack(side="left", padx=5)

        # Copies
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Copies:")).pack(side="left")
        ttk.Spinbox(row, textvariable=self.copies_var, from_=1, to=100, width=10).pack(side="left", padx=5)

        # Args
        row = ttk.Frame(self, padding=5)
        row.pack(fill="x", padx=10)
        ttk.Label(row, text=_("Extra Args:")).pack(side="left")
        ttk.Entry(row, textvariable=self.args_var, width=30).pack(side="left", padx=5)

        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text=_("OK"), command=self._ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_("Cancel"), command=self.destroy).pack(side="right")

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
            messagebox.showerror(_("Error"), _("Target name is required"))
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
