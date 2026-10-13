"""Length parsing. All geometry in pdfmill is in PDF points (72 pt = 1 inch)."""

import re

from pdfmill.schema import ConfigError

UNIT_TO_POINTS = {
    "pt": 1.0,
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
}

_LENGTH_RE = re.compile(r"^(-?\d+(?:\.\d*)?|-?\.\d+)\s*(mm|in|pt|cm)?$")


def to_points(value: float | int | str, where: str = "value") -> float:
    """Convert ``72``, ``"72pt"``, ``"1in"``, ``"25.4mm"`` or ``"2.54cm"`` to points.

    A bare number (or numeric string) is already in points.
    """
    if isinstance(value, bool):
        raise ConfigError(f"{where}: expected a length, got bool")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _LENGTH_RE.match(value.strip().lower())
        if match:
            return float(match.group(1)) * UNIT_TO_POINTS[match.group(2) or "pt"]
    raise ConfigError(f"{where}: invalid length {value!r} (use e.g. 100mm, 4in, 288pt, 10cm)")
