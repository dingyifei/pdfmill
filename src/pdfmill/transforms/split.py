"""Split each page into several pages, one per region.

- split:
    regions:
      - {lower_left: [0in, 3in], upper_right: [4in, 6in]}
      - {lower_left: [4in, 3in], upper_right: [8in, 6in]}
"""

from dataclasses import dataclass

from pypdf import PageObject

from pdfmill.schema import ConfigError, check_keys, require_dict
from pdfmill.transforms._page import clone
from pdfmill.transforms.crop import Box, crop_page, parse_box

NAME = "split"


@dataclass
class Options:
    regions: list[Box]


def parse(value, where: str) -> Options:
    value = require_dict(value, where)
    check_keys(value, ("regions",), where)
    regions = value.get("regions")
    if not isinstance(regions, list) or not regions:
        raise ConfigError(f"{where}.regions: expected a non-empty list of regions")
    return Options([parse_box(r, f"{where}.regions[{i}]") for i, r in enumerate(regions)])


def describe(opts: Options) -> str:
    return f"split{len(opts.regions)}"


def apply(pages: list[PageObject], opts: Options, fields: dict[str, str]) -> list[PageObject]:
    result = []
    for page in pages:
        result.extend(crop_page(clone(page), region) for region in opts.regions)
    return result
