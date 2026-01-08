"""Configuration loading and validation for pdfmill."""

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid."""


def _parse_args(args: list) -> list[str]:
    """Parse args list, splitting any items that contain spaces."""
    result = []
    for arg in args:
        if isinstance(arg, str) and ' ' in arg:
            result.extend(shlex.split(arg))
        else:
            result.append(str(arg))
    return result


@dataclass
class PrintTarget:
    """A single printer target with distribution settings."""
    printer: str
    weight: int = 1      # For page distribution (ppm/ipm)
    copies: int = 1
    args: list[str] = field(default_factory=list)


@dataclass
class PrintConfig:
    """Print configuration for an output profile."""
    enabled: bool = False
    merge: bool = False  # Merge all PDFs before printing as single job
    targets: dict[str, PrintTarget] = field(default_factory=dict)


@dataclass
class CropTransform:
    """Crop transformation configuration.

    Coordinates can be floats (points) or strings with units (e.g., "100mm", "4in", "288pt").
    """
    lower_left: tuple[float | str, float | str] = (0, 0)
    upper_right: tuple[float | str, float | str] = (612, 792)  # Default letter size


@dataclass
class SizeTransform:
    """Size enforcement configuration."""
    width: str = ""  # e.g., "100mm", "4in", "288pt"
    height: str = ""
    fit: str = "contain"  # contain, cover, stretch


@dataclass
class RotateTransform:
    """Rotation configuration."""
    angle: int | str = 0  # 0, 90, 180, 270 or "landscape", "portrait"
    pages: list[int] | None = None  # If None, apply to all pages


@dataclass
class SplitRegion:
    """A single region for split transform."""
    lower_left: tuple[float | str, float | str] = (0, 0)
    upper_right: tuple[float | str, float | str] = (612, 792)


@dataclass
class SplitTransform:
    """Split transform: extract multiple regions from each page."""
    regions: list[SplitRegion] = field(default_factory=list)


@dataclass
class CombineLayoutItem:
    """A single page placement in combine transform."""
    page: int = 0  # 0-indexed input page within the batch
    position: tuple[float | str, float | str] = (0, 0)  # Lower-left corner position
    scale: float = 1.0


@dataclass
class CombineTransform:
    """Combine transform: place multiple pages onto a single canvas."""
    page_size: tuple[str, str] = ("8.5in", "11in")  # Output page dimensions
    layout: list[CombineLayoutItem] = field(default_factory=list)
    pages_per_output: int = 2  # How many input pages consumed per output page


@dataclass
class Transform:
    """A single transformation step."""
    type: str  # "rotate", "crop", "size", "split", "combine"
    rotate: RotateTransform | None = None
    crop: CropTransform | None = None
    size: SizeTransform | None = None
    split: SplitTransform | None = None
    combine: CombineTransform | None = None


@dataclass
class OutputProfile:
    """Configuration for a single output profile."""
    pages: str | list[int]  # Page selection spec
    output_dir: Path = Path("./output")
    filename_prefix: str = ""
    filename_suffix: str = ""
    transforms: list[Transform] = field(default_factory=list)
    print: PrintConfig = field(default_factory=PrintConfig)
    debug: bool = False  # Output intermediate files after each transform
    sort: str | None = None  # Override input.sort: name_asc, name_desc, time_asc, time_desc


@dataclass
class Settings:
    """Global settings for the pipeline."""
    on_error: str = "continue"  # "continue" or "stop"
    cleanup_source: bool = False
    cleanup_output_after_print: bool = False


@dataclass
class FilterConfig:
    """Keyword filter configuration for input files."""
    keywords: list[str] = field(default_factory=list)
    match: str = "any"  # "any" (OR) or "all" (AND)


@dataclass
class InputConfig:
    """Input configuration."""
    path: Path = Path("./input")
    pattern: str = "*.pdf"
    filter: FilterConfig | None = None
    sort: str | None = None  # name_asc, name_desc, time_asc, time_desc


@dataclass
class Config:
    """Root configuration object."""
    version: int = 1
    settings: Settings = field(default_factory=Settings)
    input: InputConfig = field(default_factory=InputConfig)
    outputs: dict[str, OutputProfile] = field(default_factory=dict)


def parse_transform(transform_data: dict[str, Any]) -> Transform:
    """Parse a single transform from config data."""
    if "rotate" in transform_data:
        rotate_val = transform_data["rotate"]
        if isinstance(rotate_val, (int, str)):
            # Simple rotate: just angle
            return Transform(
                type="rotate",
                rotate=RotateTransform(angle=rotate_val),
            )
        elif isinstance(rotate_val, dict):
            # Complex rotate with pages
            return Transform(
                type="rotate",
                rotate=RotateTransform(
                    angle=rotate_val.get("angle", 0),
                    pages=rotate_val.get("pages"),
                ),
            )
    elif "crop" in transform_data:
        crop_val = transform_data["crop"]
        return Transform(
            type="crop",
            crop=CropTransform(
                lower_left=tuple(crop_val.get("lower_left", [0, 0])),
                upper_right=tuple(crop_val.get("upper_right", [612, 792])),
            ),
        )
    elif "size" in transform_data:
        size_val = transform_data["size"]
        return Transform(
            type="size",
            size=SizeTransform(
                width=size_val.get("width", ""),
                height=size_val.get("height", ""),
                fit=size_val.get("fit", "contain"),
            ),
        )
    elif "split" in transform_data:
        split_val = transform_data["split"]
        regions = []
        for r in split_val.get("regions", []):
            regions.append(SplitRegion(
                lower_left=tuple(r.get("lower_left", [0, 0])),
                upper_right=tuple(r.get("upper_right", [612, 792])),
            ))
        return Transform(
            type="split",
            split=SplitTransform(regions=regions),
        )
    elif "combine" in transform_data:
        combine_val = transform_data["combine"]
        layout = []
        for item in combine_val.get("layout", []):
            layout.append(CombineLayoutItem(
                page=item.get("page", 0),
                position=tuple(item.get("position", [0, 0])),
                scale=item.get("scale", 1.0),
            ))
        return Transform(
            type="combine",
            combine=CombineTransform(
                page_size=tuple(combine_val.get("page_size", ["8.5in", "11in"])),
                layout=layout,
                pages_per_output=combine_val.get("pages_per_output", 2),
            ),
        )

    raise ConfigError(f"Unknown transform type: {transform_data}")


def parse_output_profile(name: str, data: dict[str, Any]) -> OutputProfile:
    """Parse an output profile from config data."""
    if "pages" not in data:
        raise ConfigError(f"Output profile '{name}' missing required 'pages' field")

    transforms = []
    if "transforms" in data:
        for t in data["transforms"]:
            transforms.append(parse_transform(t))

    print_config = PrintConfig()
    if "print" in data:
        p = data["print"]
        targets = {}

        if "targets" in p:
            # New multi-target format
            for target_name, t in p["targets"].items():
                targets[target_name] = PrintTarget(
                    printer=t.get("printer", ""),
                    weight=t.get("weight", 1),
                    copies=t.get("copies", 1),
                    args=_parse_args(t.get("args", [])),
                )
        elif p.get("printer"):
            # Legacy single-printer format -> convert to target
            targets["default"] = PrintTarget(
                printer=p.get("printer", ""),
                weight=1,
                copies=p.get("copies", 1),
                args=_parse_args(p.get("args", [])),
            )

        print_config = PrintConfig(
            enabled=p.get("enabled", False),
            merge=p.get("merge", False),
            targets=targets,
        )

    return OutputProfile(
        pages=data["pages"],
        output_dir=Path(data.get("output_dir", "./output")),
        filename_prefix=data.get("filename_prefix", ""),
        filename_suffix=data.get("filename_suffix", ""),
        transforms=transforms,
        print=print_config,
        debug=data.get("debug", False),
        sort=data.get("sort"),
    )


def load_config(config_path: Path) -> Config:
    """Load and validate a configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ConfigError("Configuration must be a YAML dictionary")

    # Parse settings
    settings = Settings()
    if "settings" in data:
        s = data["settings"]
        settings = Settings(
            on_error=s.get("on_error", "continue"),
            cleanup_source=s.get("cleanup_source", False),
            cleanup_output_after_print=s.get("cleanup_output_after_print", False),
        )

    # Parse input
    input_config = InputConfig()
    if "input" in data:
        i = data["input"]
        filter_config = None
        if "filter" in i:
            f = i["filter"]
            filter_config = FilterConfig(
                keywords=f.get("keywords", []),
                match=f.get("match", "any"),
            )
        input_config = InputConfig(
            path=Path(i.get("path", "./input")),
            pattern=i.get("pattern", "*.pdf"),
            filter=filter_config,
            sort=i.get("sort"),
        )

    # Parse outputs
    outputs = {}
    if "outputs" not in data:
        raise ConfigError("Configuration must contain 'outputs' section")

    for name, output_data in data["outputs"].items():
        outputs[name] = parse_output_profile(name, output_data)

    return Config(
        version=data.get("version", 1),
        settings=settings,
        input=input_config,
        outputs=outputs,
    )
