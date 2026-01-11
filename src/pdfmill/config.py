"""Configuration loading and validation for pdfmill."""

import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


# ============================================================================
# Enums for constrained string values
# ============================================================================


class StampPosition(str, Enum):
    """Valid positions for stamp transforms."""

    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    CENTER = "center"
    CUSTOM = "custom"


class SortOrder(str, Enum):
    """Valid sort orders for file processing."""

    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    TIME_ASC = "time_asc"
    TIME_DESC = "time_desc"


class FilterMatch(str, Enum):
    """Filter matching modes."""

    ANY = "any"  # OR: match if any keyword found
    ALL = "all"  # AND: match only if all keywords found


class ErrorHandling(str, Enum):
    """Error handling modes."""

    CONTINUE = "continue"  # Skip failed items, continue processing
    STOP = "stop"  # Stop on first error


class FitMode(str, Enum):
    """Resize fit modes."""

    CONTAIN = "contain"  # Fit within bounds, preserve aspect ratio
    COVER = "cover"  # Cover bounds, may crop
    STRETCH = "stretch"  # Stretch to exact dimensions


# ============================================================================
# Exceptions
# ============================================================================


class ConfigError(Exception):
    """Raised when configuration is invalid.

    Attributes:
        message: The error message.
        profile: Name of the profile where error occurred (if applicable).
        transform_idx: Index of the transform where error occurred (if applicable).
        field: Name of the field with the error (if applicable).
        suggestion: Suggested fix for the error (if applicable).
    """

    def __init__(
        self,
        message: str,
        profile: str | None = None,
        transform_idx: int | None = None,
        field: str | None = None,
        suggestion: str | None = None,
    ):
        self.message = message
        self.profile = profile
        self.transform_idx = transform_idx
        self.field = field
        self.suggestion = suggestion
        super().__init__(str(self))

    def __str__(self) -> str:
        parts = []

        # Build context path
        if self.profile:
            context = f"In profile '{self.profile}'"
            if self.transform_idx is not None:
                context += f", transform #{self.transform_idx + 1}"
            if self.field:
                context += f", field '{self.field}'"
            parts.append(context)

        parts.append(self.message)

        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")

        return "\n".join(parts)


def _parse_args(args: list) -> list[str]:
    """Parse args list, splitting any items that contain spaces."""
    result = []
    for arg in args:
        if isinstance(arg, str) and ' ' in arg:
            result.extend(shlex.split(arg))
        else:
            result.append(str(arg))
    return result


def _parse_enum(
    enum_class: type[Enum],
    value: str,
    profile: str | None = None,
    transform_idx: int | None = None,
    field: str | None = None,
) -> Enum:
    """Parse a string value into an enum with validation.

    Args:
        enum_class: The enum class to parse into.
        value: The string value to parse.
        profile: Profile name for error context.
        transform_idx: Transform index for error context.
        field: Field name for error context.

    Returns:
        The parsed enum value.

    Raises:
        ConfigError: If the value is not a valid enum member.
    """
    try:
        return enum_class(value)
    except ValueError:
        valid = ", ".join(e.value for e in enum_class)
        raise ConfigError(
            f"Invalid value '{value}'",
            profile=profile,
            transform_idx=transform_idx,
            field=field,
            suggestion=f"Valid values are: {valid}",
        )


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
    fit: FitMode = FitMode.CONTAIN


@dataclass
class RotateTransform:
    """Rotation configuration."""
    angle: int | str = 0  # 0, 90, 180, 270 or "landscape", "portrait"
    pages: list[int] | None = None  # If None, apply to all pages


@dataclass
class StampTransform:
    """Stamp transformation configuration for adding text overlays.

    Supports placeholders in text:
      - {page}: Current page number (1-indexed)
      - {total}: Total page count
      - {datetime}: Current datetime (format controlled by datetime_format)
      - {date}: Current date only
      - {time}: Current time only

    Position can be a preset string or custom coordinates:
      - Presets: "top-left", "top-right", "bottom-left", "bottom-right", "center"
      - Custom: Use x/y coordinates with units (e.g., "10mm", "0.5in")
    """
    text: str = "{page}/{total}"  # Text with placeholders
    position: StampPosition = StampPosition.BOTTOM_RIGHT
    x: str | float = "10mm"  # X coordinate (used when position=CUSTOM)
    y: str | float = "10mm"  # Y coordinate (used when position=CUSTOM)
    font_size: int = 10
    font_name: str = "Helvetica"  # PDF standard font
    margin: str | float = "10mm"  # Margin from edge for preset positions
    datetime_format: str = "%Y-%m-%d %H:%M:%S"  # strftime format


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
class RenderTransform:
    """Render (rasterize) configuration.

    Rasterizes pages to images and re-embeds them. This permanently removes
    any content outside the visible area and flattens all layers.
    """
    dpi: int = 150  # Resolution for rasterization


@dataclass
class Transform:
    """A single transformation step."""
    type: str  # "rotate", "crop", "size", "stamp", "split", "combine", "render"
    rotate: RotateTransform | None = None
    crop: CropTransform | None = None
    size: SizeTransform | None = None
    stamp: StampTransform | None = None
    split: SplitTransform | None = None
    combine: CombineTransform | None = None
    render: RenderTransform | None = None
    enabled: bool = True  # Set to False to skip this transform


@dataclass
class OutputProfile:
    """Configuration for a single output profile."""
    pages: str | list[int]  # Page selection spec
    enabled: bool = True  # Set to False to skip this profile
    output_dir: Path = Path("./output")
    filename_prefix: str = ""
    filename_suffix: str = ""
    transforms: list[Transform] = field(default_factory=list)
    print: PrintConfig = field(default_factory=PrintConfig)
    debug: bool = False  # Output intermediate files after each transform
    sort: SortOrder | None = None  # Override input.sort


@dataclass
class Settings:
    """Global settings for the pipeline."""
    on_error: ErrorHandling = ErrorHandling.CONTINUE
    cleanup_source: bool = False
    cleanup_output_after_print: bool = False


@dataclass
class FilterConfig:
    """Keyword filter configuration for input files."""
    keywords: list[str] = field(default_factory=list)
    match: FilterMatch = FilterMatch.ANY


@dataclass
class InputConfig:
    """Input configuration."""
    path: Path = Path("./input")
    pattern: str = "*.pdf"
    filter: FilterConfig | None = None
    sort: SortOrder | None = None


@dataclass
class Config:
    """Root configuration object."""
    version: int = 1
    settings: Settings = field(default_factory=Settings)
    input: InputConfig = field(default_factory=InputConfig)
    outputs: dict[str, OutputProfile] = field(default_factory=dict)


def parse_transform(transform_data: dict[str, Any]) -> Transform:
    """Parse a single transform from config data."""
    enabled = transform_data.get("enabled", True)

    if "rotate" in transform_data:
        rotate_val = transform_data["rotate"]
        if isinstance(rotate_val, (int, str)):
            # Simple rotate: just angle
            return Transform(
                type="rotate",
                rotate=RotateTransform(angle=rotate_val),
                enabled=enabled,
            )
        elif isinstance(rotate_val, dict):
            # Complex rotate with pages
            return Transform(
                type="rotate",
                rotate=RotateTransform(
                    angle=rotate_val.get("angle", 0),
                    pages=rotate_val.get("pages"),
                ),
                enabled=enabled,
            )
    elif "crop" in transform_data:
        crop_val = transform_data["crop"]
        return Transform(
            type="crop",
            crop=CropTransform(
                lower_left=tuple(crop_val.get("lower_left", [0, 0])),
                upper_right=tuple(crop_val.get("upper_right", [612, 792])),
            ),
            enabled=enabled,
        )
    elif "size" in transform_data:
        size_val = transform_data["size"]
        fit_str = size_val.get("fit", "contain")
        fit = _parse_enum(FitMode, fit_str, field="fit")
        return Transform(
            type="size",
            size=SizeTransform(
                width=size_val.get("width", ""),
                height=size_val.get("height", ""),
                fit=fit,
            ),
            enabled=enabled,
        )
    elif "stamp" in transform_data:
        stamp_val = transform_data["stamp"]
        if isinstance(stamp_val, str):
            # Simple stamp: just text
            return Transform(
                type="stamp",
                stamp=StampTransform(text=stamp_val),
                enabled=enabled,
            )
        elif isinstance(stamp_val, dict):
            # Complex stamp with options
            position_str = stamp_val.get("position", "bottom-right")
            position = _parse_enum(StampPosition, position_str, field="position")
            return Transform(
                type="stamp",
                stamp=StampTransform(
                    text=stamp_val.get("text", "{page}/{total}"),
                    position=position,
                    x=stamp_val.get("x", "10mm"),
                    y=stamp_val.get("y", "10mm"),
                    font_size=stamp_val.get("font_size", 10),
                    font_name=stamp_val.get("font_name", "Helvetica"),
                    margin=stamp_val.get("margin", "10mm"),
                    datetime_format=stamp_val.get("datetime_format", "%Y-%m-%d %H:%M:%S"),
                ),
                enabled=enabled,
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
    elif "render" in transform_data:
        render_val = transform_data["render"]
        if isinstance(render_val, int) and not isinstance(render_val, bool):
            # Simple render: just dpi value (e.g., render: 300)
            return Transform(
                type="render",
                render=RenderTransform(dpi=render_val),
            )
        elif isinstance(render_val, dict):
            # Complex render with options (e.g., render: {dpi: 200})
            return Transform(
                type="render",
                render=RenderTransform(
                    dpi=render_val.get("dpi", 150),
                ),
            )
        else:
            # Default render (e.g., render: true or render: ~)
            return Transform(
                type="render",
                render=RenderTransform(),
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

    # Parse sort if provided
    sort = None
    sort_str = data.get("sort")
    if sort_str:
        sort = _parse_enum(SortOrder, sort_str, profile=name, field="sort")

    return OutputProfile(
        pages=data["pages"],
        enabled=data.get("enabled", True),
        output_dir=Path(data.get("output_dir", "./output")),
        filename_prefix=data.get("filename_prefix", ""),
        filename_suffix=data.get("filename_suffix", ""),
        transforms=transforms,
        print=print_config,
        debug=data.get("debug", False),
        sort=sort,
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
        on_error_str = s.get("on_error", "continue")
        on_error = _parse_enum(ErrorHandling, on_error_str, field="settings.on_error")
        settings = Settings(
            on_error=on_error,
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
            match_str = f.get("match", "any")
            match = _parse_enum(FilterMatch, match_str, field="input.filter.match")
            filter_config = FilterConfig(
                keywords=f.get("keywords", []),
                match=match,
            )
        # Parse input sort if provided
        input_sort = None
        input_sort_str = i.get("sort")
        if input_sort_str:
            input_sort = _parse_enum(SortOrder, input_sort_str, field="input.sort")
        input_config = InputConfig(
            path=Path(i.get("path", "./input")),
            pattern=i.get("pattern", "*.pdf"),
            filter=filter_config,
            sort=input_sort,
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
