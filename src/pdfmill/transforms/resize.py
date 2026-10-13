"""Scale pages to an exact size.

- size: {width: 100mm, height: 150mm, fit: contain}   # contain | cover | stretch
"""

from dataclasses import dataclass

from pypdf import PageObject, Transformation

from pdfmill.schema import ConfigError, check_keys, choice, require_dict
from pdfmill.transforms._page import set_box, size
from pdfmill.units import to_points

NAME = "size"
FIT_MODES = ("contain", "cover", "stretch")


@dataclass
class Options:
    width: float
    height: float
    fit: str = "contain"


def parse(value, where: str) -> Options:
    value = require_dict(value, where)
    check_keys(value, ("width", "height", "fit"), where)
    for key in ("width", "height"):
        if key not in value:
            raise ConfigError(f"{where}: missing '{key}'")
    opts = Options(
        width=to_points(value["width"], f"{where}.width"),
        height=to_points(value["height"], f"{where}.height"),
        fit=choice(value.get("fit", "contain"), FIT_MODES, f"{where}.fit"),
    )
    if opts.width <= 0 or opts.height <= 0:
        raise ConfigError(f"{where}: width and height must be positive")
    return opts


def describe(opts: Options) -> str:
    return f"size_{opts.fit}"


def apply(pages: list[PageObject], opts: Options) -> list[PageObject]:
    for page in pages:
        resize_page(page, opts.width, opts.height, opts.fit)
    return pages


def resize_page(page: PageObject, width: float, height: float, fit: str = "contain") -> PageObject:
    """Scale ``page`` in place to ``width`` x ``height`` points.

    contain: uniform scale to fit inside, centered. cover: uniform scale to fill,
    centered (edges may be cut). stretch: non-uniform scale to the exact size.
    """
    current_w, current_h = size(page)
    sx, sy = width / current_w, height / current_h
    if fit == "stretch":
        transform = Transformation().scale(sx=sx, sy=sy)
    else:
        scale = min(sx, sy) if fit == "contain" else max(sx, sy)
        tx = (width - current_w * scale) / 2
        ty = (height - current_h * scale) / 2
        transform = Transformation().scale(sx=scale, sy=scale).translate(tx=tx, ty=ty)
    page.add_transformation(transform)
    set_box(page, width, height)
    return page
