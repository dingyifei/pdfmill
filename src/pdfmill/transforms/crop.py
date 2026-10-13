"""Crop pages to a rectangle; the cropped region becomes the new page at (0, 0).

- crop:
    lower_left: [90mm, 33mm]
    upper_right: [190mm, 183mm]
"""

from dataclasses import dataclass

from pypdf import PageObject, Transformation

from pdfmill.schema import ConfigError, check_keys, pair, require_dict
from pdfmill.transforms._page import set_box
from pdfmill.units import to_points

NAME = "crop"


@dataclass
class Box:
    """A rectangle in points."""

    x0: float
    y0: float
    x1: float
    y1: float


Options = Box


def parse_box(value, where: str) -> Box:
    value = require_dict(value, where)
    check_keys(value, ("lower_left", "upper_right"), where)
    for key in ("lower_left", "upper_right"):
        if key not in value:
            raise ConfigError(f"{where}: missing '{key}'")
    x0, y0 = (to_points(v, f"{where}.lower_left") for v in pair(value["lower_left"], f"{where}.lower_left"))
    x1, y1 = (to_points(v, f"{where}.upper_right") for v in pair(value["upper_right"], f"{where}.upper_right"))
    if x0 >= x1 or y0 >= y1:
        raise ConfigError(f"{where}: lower_left must be below and left of upper_right")
    return Box(x0, y0, x1, y1)


parse = parse_box


def describe(opts: Box) -> str:
    return "crop"


def apply(pages: list[PageObject], opts: Box, fields: dict[str, str]) -> list[PageObject]:
    for page in pages:
        crop_page(page, opts)
    return pages


def crop_page(page: PageObject, box: Box) -> PageObject:
    """Crop ``page`` in place to ``box`` and move the result to the origin."""
    page.add_transformation(Transformation().translate(tx=-box.x0, ty=-box.y0))
    set_box(page, box.x1 - box.x0, box.y1 - box.y0)
    return page
