"""Page transforms.

Each transform is a module exposing ``NAME``, ``parse(value, where) -> options``,
``apply(pages, options, fields) -> pages`` and ``describe(options) -> str``.
``fields`` holds the values extracted from the source PDF (see input.fields). To add a
transform, write such a module and list it in ``_MODULES``.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PageObject, PdfWriter

from pdfmill.logging_config import get_logger
from pdfmill.schema import ConfigError, typed
from pdfmill.transforms import combine, crop, render, resize, rotate, split, stamp
from pdfmill.transforms._page import TransformError, normalize

__all__ = ["Transform", "TransformError", "apply_all", "parse_transform", "TRANSFORMS"]

logger = get_logger(__name__)

_MODULES = (rotate, crop, resize, stamp, split, combine, render)
TRANSFORMS = {m.NAME: m for m in _MODULES}


@dataclass
class Transform:
    name: str
    options: Any
    enabled: bool = True

    def describe(self) -> str:
        return TRANSFORMS[self.name].describe(self.options)


def parse_transform(data: Any, where: str) -> Transform:
    """Parse one entry of a ``transforms:`` list, e.g. ``{rotate: 90, enabled: false}``."""
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: expected a mapping like '- rotate: 90'")
    names = [k for k in data if k != "enabled"]
    if len(names) != 1 or names[0] not in TRANSFORMS:
        raise ConfigError(f"{where}: expected exactly one transform ({', '.join(TRANSFORMS)}), got {names or 'none'}")
    name = names[0]
    enabled = typed(data.get("enabled", True), bool, f"{where}.enabled")
    return Transform(name, TRANSFORMS[name].parse(data[name], f"{where}.{name}"), enabled)


def apply_all(
    pages: list[PageObject],
    transforms: list[Transform],
    debug_prefix: Path | None = None,
    fields: dict[str, str] | None = None,
) -> list[PageObject]:
    """Normalize pages, then apply enabled transforms in order.

    If ``debug_prefix`` is given, a PDF is saved after each step as
    ``<prefix>_step<N>_<description>.pdf``.
    """
    pages = [normalize(p) for p in pages]
    if debug_prefix:
        _save(pages, debug_prefix, 0, "selected")
    for step, transform in enumerate(transforms, start=1):
        if not transform.enabled:
            continue
        pages = TRANSFORMS[transform.name].apply(pages, transform.options, fields or {})
        if debug_prefix:
            _save(pages, debug_prefix, step, transform.describe())
    return pages


def _save(pages: list[PageObject], prefix: Path, step: int, desc: str) -> None:
    path = prefix.with_name(f"{prefix.name}_step{step}_{desc}.pdf")
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        writer.write(f)
    logger.debug("Saved debug step: %s", path)
