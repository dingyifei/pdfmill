"""Centralized constants for pdfmill.

This module consolidates constants that were previously duplicated across
processor.py, gui.py, and transforms.py.
"""

from typing import Literal

# Sort options for file ordering
SORT_OPTIONS = ("name_asc", "name_desc", "time_asc", "time_desc")
SortOption = Literal["name_asc", "name_desc", "time_asc", "time_desc"]

# Error handling behavior
ON_ERROR_OPTIONS = ("continue", "stop")
OnErrorOption = Literal["continue", "stop"]

# Transform types
TRANSFORM_TYPES = ("rotate", "crop", "size")
TransformType = Literal["rotate", "crop", "size"]

# Rotation angles (numeric and orientation-based)
ROTATE_ANGLES = (0, 90, 180, 270)
ROTATE_ORIENTATIONS = ("landscape", "portrait", "auto")

# Fit modes for resize transform
FIT_MODES = ("contain", "cover", "stretch")
FitMode = Literal["contain", "cover", "stretch"]

# Match modes for keyword filtering
MATCH_MODES = ("any", "all")
MatchMode = Literal["any", "all"]

# Unit conversion factors to PDF points (72 points per inch)
UNIT_TO_POINTS = {
    "pt": 1.0,
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
}
