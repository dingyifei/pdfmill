"""Rotate pages by a fixed angle, to an orientation, or automatically via OCR.

- rotate: 90
- rotate: landscape            # or portrait, auto
- rotate: {angle: 90, pages: [0, 2]}   # 0-indexed within the selected pages
"""

from dataclasses import dataclass

from pypdf import PageObject, Transformation

from pdfmill.schema import ConfigError, check_keys, typed
from pdfmill.transforms._page import TransformError, set_box, size

NAME = "rotate"
ORIENTATIONS = ("landscape", "portrait", "auto")


@dataclass
class Options:
    angle: int | str = 0
    pages: list[int] | None = None


def parse(value, where: str) -> Options:
    if isinstance(value, dict):
        check_keys(value, ("angle", "pages"), where)
        pages = value.get("pages")
        valid = isinstance(pages, list) and all(isinstance(p, int) and not isinstance(p, bool) for p in pages)
        if pages is not None and not valid:
            raise ConfigError(f"{where}.pages: expected a list of 0-indexed page numbers")
        return Options(angle=_parse_angle(value.get("angle", 0), where), pages=pages)
    return Options(angle=_parse_angle(value, where))


def _parse_angle(value, where: str) -> int | str:
    typed(value, (int, str), where)
    if isinstance(value, str):
        if value.lower() not in ORIENTATIONS:
            raise ConfigError(f"{where}: invalid rotation {value!r} (use 0, 90, 180, 270, {', '.join(ORIENTATIONS)})")
        return value.lower()
    if value % 360 not in (0, 90, 180, 270):
        raise ConfigError(f"{where}: rotation must be a multiple of 90, got {value}")
    return value % 360


def describe(opts: Options) -> str:
    return f"rotate{opts.angle}"


def apply(pages: list[PageObject], opts: Options, fields: dict[str, str]) -> list[PageObject]:
    targets = opts.pages if opts.pages is not None else range(len(pages))
    for idx in targets:
        if idx < len(pages):
            angle = _resolve_angle(pages[idx], opts.angle)
            rotate_page(pages[idx], angle)
    return pages


def _resolve_angle(page: PageObject, angle: int | str) -> int:
    if isinstance(angle, int):
        return angle
    width, height = size(page)
    if angle == "landscape":
        return 90 if height > width else 0
    if angle == "portrait":
        return 90 if width > height else 0
    return detect_orientation(page)


def rotate_page(page: PageObject, angle: int) -> PageObject:
    """Rotate page content counter-clockwise by ``angle`` and resize the boxes to fit."""
    if angle == 0:
        return page
    width, height = size(page)
    # Rotation is about the origin; translate back into the positive quadrant.
    offsets = {90: (height, 0), 180: (width, height), 270: (0, width)}
    tx, ty = offsets[angle]
    page.add_transformation(Transformation().rotate(angle).translate(tx=tx, ty=ty))
    if angle == 180:
        set_box(page, width, height)
    else:
        set_box(page, height, width)
    return page


def detect_orientation(page: PageObject) -> int:
    """Return the counter-clockwise rotation that makes text upright, using Tesseract OSD."""
    try:
        import pytesseract
    except ImportError:
        raise TransformError("rotate: auto needs the OCR extra: pip install 'pdfmill[ocr]'")
    from pdfmill.transforms.render import rasterize

    image = rasterize(page, dpi=150)
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        raise TransformError("Tesseract is not installed (macOS: brew install tesseract)")
    except pytesseract.TesseractError as e:
        raise TransformError(f"OCR orientation detection failed: {e}")
    # Tesseract's "rotate" is the clockwise correction; rotate_page turns counter-clockwise.
    return (360 - int(osd.get("rotate", 0))) % 360
