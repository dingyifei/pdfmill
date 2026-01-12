"""Tkinter GUI for pdfmill configuration editor.

This package provides the PdfMillApp class and launch_gui() entry point
for the interactive configuration editor.

Usage:
    from pdfmill.gui import launch_gui
    launch_gui()
"""

from pdfmill.gui.app import PdfMillApp, launch_gui

__all__ = ["PdfMillApp", "launch_gui"]
