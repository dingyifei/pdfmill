"""Configuration loading and validation for pdfmill."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclass
class PrintConfig:
    """Print configuration for an output profile."""
    enabled: bool = False
    printer: str = ""
    copies: int = 1
    args: list[str] = field(default_factory=list)
    merge: bool = False  # Merge all PDFs before printing as single job


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
class Transform:
    """A single transformation step."""
    type: str  # "rotate", "crop", "size"
    rotate: RotateTransform | None = None
    crop: CropTransform | None = None
    size: SizeTransform | None = None


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
        print_config = PrintConfig(
            enabled=p.get("enabled", False),
            printer=p.get("printer", ""),
            copies=p.get("copies", 1),
            args=p.get("args", []),
            merge=p.get("merge", False),
        )

    return OutputProfile(
        pages=data["pages"],
        output_dir=Path(data.get("output_dir", "./output")),
        filename_prefix=data.get("filename_prefix", ""),
        filename_suffix=data.get("filename_suffix", ""),
        transforms=transforms,
        print=print_config,
        debug=data.get("debug", False),
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
