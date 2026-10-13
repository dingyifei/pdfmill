"""Draw text (page numbers, dates, ...) on every page. Needs the stamp extra (reportlab).

    - stamp: "{page}/{total}"
    - stamp:
        text: "Page {page} of {total} - {date}"
        position: bottom-right       # top-left top-right bottom-left bottom-right center custom
        x: 50mm                      # only for position: custom
        y: 20mm
        font_size: 10
        font_name: Helvetica
        font_color: black            # name or #RRGGBB
        opacity: 1.0
        margin: 10mm
        datetime_format: "%Y-%m-%d %H:%M:%S"

Placeholders: {page} {total} {datetime} {date} {time}
"""

import io
from dataclasses import dataclass
from datetime import datetime

from pypdf import PageObject, PdfReader

from pdfmill.schema import ConfigError, check_keys, choice, typed
from pdfmill.transforms._page import TransformError, size
from pdfmill.units import to_points

NAME = "stamp"
POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right", "center", "custom")


@dataclass
class Options:
    text: str = "{page}/{total}"
    position: str = "bottom-right"
    x: float = to_points("10mm")
    y: float = to_points("10mm")
    font_size: float = 10
    font_name: str = "Helvetica"
    font_color: str = "black"
    opacity: float = 1.0
    margin: float = to_points("10mm")
    datetime_format: str = "%Y-%m-%d %H:%M:%S"


def parse(value, where: str) -> Options:
    if isinstance(value, str):
        return Options(text=value)
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected text or a mapping of stamp options")
    check_keys(value, Options.__dataclass_fields__.keys(), where)
    defaults = Options()
    opts = Options(
        text=typed(value.get("text", defaults.text), str, f"{where}.text"),
        position=choice(value.get("position", defaults.position), POSITIONS, f"{where}.position"),
        x=to_points(value.get("x", defaults.x), f"{where}.x"),
        y=to_points(value.get("y", defaults.y), f"{where}.y"),
        font_size=typed(value.get("font_size", defaults.font_size), (int, float), f"{where}.font_size"),
        font_name=typed(value.get("font_name", defaults.font_name), str, f"{where}.font_name"),
        font_color=typed(value.get("font_color", defaults.font_color), str, f"{where}.font_color"),
        opacity=float(typed(value.get("opacity", defaults.opacity), (int, float), f"{where}.opacity")),
        margin=to_points(value.get("margin", defaults.margin), f"{where}.margin"),
        datetime_format=typed(value.get("datetime_format", defaults.datetime_format), str, f"{where}.datetime_format"),
    )
    if not 0 <= opts.opacity <= 1:
        raise ConfigError(f"{where}.opacity: must be between 0 and 1")
    return opts


def describe(opts: Options) -> str:
    return "stamp"


def apply(pages: list[PageObject], opts: Options) -> list[PageObject]:
    now = datetime.now()
    for i, page in enumerate(pages, start=1):
        stamp_page(page, format_text(opts.text, i, len(pages), opts.datetime_format, now), opts)
    return pages


def format_text(text: str, page: int, total: int, datetime_format: str, now: datetime) -> str:
    return (
        text.replace("{page}", str(page))
        .replace("{total}", str(total))
        .replace("{datetime}", now.strftime(datetime_format))
        .replace("{date}", now.strftime("%Y-%m-%d"))
        .replace("{time}", now.strftime("%H:%M:%S"))
    )


def text_position(opts: Options, text_width: float, page_w: float, page_h: float) -> tuple[float, float]:
    """Lower-left corner of the text for the configured position."""
    m, h = opts.margin, opts.font_size
    return {
        "custom": (opts.x, opts.y),
        "top-left": (m, page_h - m - h),
        "top-right": (page_w - m - text_width, page_h - m - h),
        "bottom-left": (m, m),
        "bottom-right": (page_w - m - text_width, m),
        "center": ((page_w - text_width) / 2, (page_h - h) / 2),
    }[opts.position]


def stamp_page(page: PageObject, text: str, opts: Options) -> PageObject:
    """Draw ``text`` onto ``page`` in place."""
    try:
        from reportlab.lib import colors
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.pdfgen import canvas
    except ImportError:
        raise TransformError("stamp needs the stamp extra: pip install 'pdfmill[stamp]'")

    if opts.font_color.startswith("#"):
        try:
            color = colors.HexColor(opts.font_color)
        except ValueError:
            raise TransformError(f"Invalid hex color: {opts.font_color}")
    else:
        color = getattr(colors, opts.font_color, None)
        if not isinstance(color, colors.Color):
            raise TransformError(f"Unknown color: {opts.font_color}")

    page_w, page_h = size(page)
    try:
        text_width = stringWidth(text, opts.font_name, opts.font_size)
    except KeyError:
        raise TransformError(f"Unknown font: {opts.font_name} (use a standard PDF font such as Helvetica)")
    x, y = text_position(opts, text_width, page_w, page_h)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setFont(opts.font_name, opts.font_size)
    c.setFillColor(color)
    c.setFillAlpha(opts.opacity)
    c.drawString(x, y, text)
    c.save()
    buffer.seek(0)
    page.merge_page(PdfReader(buffer).pages[0])
    return page
