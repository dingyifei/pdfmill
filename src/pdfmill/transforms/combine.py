"""Place batches of pages onto new pages (n-up).

- combine:
    page_size: [8.5in, 11in]
    pages_per_output: 2
    layout:
      - {page: 0, position: [0in, 5.5in], scale: 0.5}
      - {page: 1, position: [0in, 0in], scale: 0.5}
"""

from dataclasses import dataclass

from pypdf import PageObject, Transformation

from pdfmill.schema import ConfigError, check_keys, pair, require_dict, typed
from pdfmill.transforms._page import clone, set_box
from pdfmill.units import to_points

NAME = "combine"


@dataclass
class Placement:
    page: int
    x: float
    y: float
    scale: float = 1.0


@dataclass
class Options:
    width: float
    height: float
    layout: list[Placement]
    pages_per_output: int = 2


def parse(value, where: str) -> Options:
    value = require_dict(value, where)
    check_keys(value, ("page_size", "pages_per_output", "layout"), where)
    width, height = pair(value.get("page_size", ["8.5in", "11in"]), f"{where}.page_size")
    per_output = typed(value.get("pages_per_output", 2), int, f"{where}.pages_per_output")
    if per_output < 1:
        raise ConfigError(f"{where}.pages_per_output: must be at least 1")
    layout_data = value.get("layout")
    if not isinstance(layout_data, list) or not layout_data:
        raise ConfigError(f"{where}.layout: expected a non-empty list of placements")
    layout = []
    for i, item in enumerate(layout_data):
        item_where = f"{where}.layout[{i}]"
        item = require_dict(item, item_where)
        check_keys(item, ("page", "position", "scale"), item_where)
        page = typed(item.get("page", 0), int, f"{item_where}.page")
        if not 0 <= page < per_output:
            raise ConfigError(f"{item_where}.page: must be between 0 and pages_per_output - 1 ({per_output - 1})")
        x, y = pair(item.get("position", [0, 0]), f"{item_where}.position")
        layout.append(
            Placement(
                page=page,
                x=to_points(x, f"{item_where}.position"),
                y=to_points(y, f"{item_where}.position"),
                scale=float(typed(item.get("scale", 1.0), (int, float), f"{item_where}.scale")),
            )
        )
    return Options(
        width=to_points(width, f"{where}.page_size"),
        height=to_points(height, f"{where}.page_size"),
        layout=layout,
        pages_per_output=per_output,
    )


def describe(opts: Options) -> str:
    return f"combine{opts.pages_per_output}"


def apply(pages: list[PageObject], opts: Options, fields: dict[str, str]) -> list[PageObject]:
    n = opts.pages_per_output
    return [combine_pages(pages[i : i + n], opts) for i in range(0, len(pages), n)]


def combine_pages(batch: list[PageObject], opts: Options) -> PageObject:
    """Merge ``batch`` onto one blank page according to ``opts.layout``."""
    output = PageObject.create_blank_page(width=opts.width, height=opts.height)
    for item in opts.layout:
        if item.page >= len(batch):
            continue  # last batch may be short
        # merge_transformed_page can alter the source, so merge a fresh copy each time.
        source = clone(batch[item.page])
        transform = Transformation().scale(sx=item.scale, sy=item.scale).translate(tx=item.x, ty=item.y)
        output.merge_transformed_page(source, transform)
    set_box(output, opts.width, opts.height)
    return output
