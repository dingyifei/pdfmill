"""Load and validate pdfmill YAML configs.

Validation is strict: unknown keys, wrong types and bad values raise
``ConfigError`` at load time with the YAML path of the problem, so nothing
is silently ignored at run time. Relative paths are relative to the
current working directory.
"""

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pdfmill.schema import ConfigError, check_keys, choice, pair, require_dict, typed
from pdfmill.selector import PageSelectionError, validate_page_spec_syntax
from pdfmill.transforms import Transform, parse_transform
from pdfmill.transforms.stamp import BUILTIN_PLACEHOLDERS
from pdfmill.units import to_points

__all__ = ["Config", "ConfigError", "load_config", "parse_config"]

SORT_ORDERS = ("name_asc", "name_desc", "time_asc", "time_desc")
BACKENDS = ("auto", "cups", "sumatra")


@dataclass
class PrintTarget:
    printer: str
    weight: int = 1  # relative share of pages when splitting a merged job
    copies: int = 1
    args: list[str] = field(default_factory=list)  # passed verbatim to the backend
    options: dict[str, str] = field(default_factory=dict)  # CUPS "-o key=value"


@dataclass
class PrintConfig:
    enabled: bool = False
    merge: bool = False
    targets: dict[str, PrintTarget] = field(default_factory=dict)
    max_pages: int | None = None
    max_page_size: tuple[float, float] | None = None  # points
    action: str = "block"  # block | warn


@dataclass
class OutputProfile:
    name: str
    pages: str | int | list[int]
    enabled: bool = True
    output_dir: Path = Path("output")
    filename_prefix: str = ""
    filename_suffix: str = ""
    transforms: list[Transform] = field(default_factory=list)
    print: PrintConfig = field(default_factory=PrintConfig)
    debug: bool = False
    sort: str | None = None  # print order for this profile; overrides input.sort

    def output_name(self, source: Path) -> str:
        return f"{self.filename_prefix}{source.stem}{self.filename_suffix}_{self.name}.pdf"


@dataclass
class Settings:
    on_error: str = "continue"  # continue | stop
    cleanup_source: bool = False
    cleanup_output_after_print: bool = False
    print_backend: str = "auto"


@dataclass
class WatchSettings:
    poll_interval: float = 2.0
    debounce_delay: float = 1.0  # a file must be unchanged this long before processing
    process_existing: bool = True


@dataclass
class TextField:
    """A value pulled out of each source PDF's text, usable as ``{name}`` in stamp text."""

    pattern: re.Pattern
    format: str | None = None  # re.Match.expand() template like "Box \\1/\\2"; default: group 1 or whole match
    default: str | None = None  # used when the pattern doesn't match; None means the field is required

    def extract(self, text: str) -> str | None:
        match = self.pattern.search(text)
        if not match:
            return self.default
        if self.format is not None:
            return match.expand(self.format)
        return match.group(1) if match.re.groups else match.group(0)


@dataclass
class InputConfig:
    path: Path = Path("input")
    pattern: str = "*.pdf"
    sort: str | None = None
    keywords: list[str] = field(default_factory=list)
    match: str = "any"  # any | all
    fields: dict[str, TextField] = field(default_factory=dict)


@dataclass
class Config:
    settings: Settings = field(default_factory=Settings)
    input: InputConfig = field(default_factory=InputConfig)
    outputs: dict[str, OutputProfile] = field(default_factory=dict)
    watch: WatchSettings = field(default_factory=WatchSettings)


def load_config(path: Path) -> Config:
    """Load a config file. Raises FileNotFoundError or ConfigError."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML: {e}")
    return parse_config(data)


def parse_config(data: Any) -> Config:
    data = require_dict(data, "config")
    check_keys(data, ("version", "settings", "input", "outputs", "watch"), "config")
    if data.get("version", 1) != 1:
        raise ConfigError(f"version: unsupported config version {data['version']!r} (expected 1)")
    outputs = require_dict(data.get("outputs"), "outputs")
    if not outputs:
        raise ConfigError("outputs: at least one output profile is required")
    config = Config(
        settings=_settings(require_dict(data.get("settings"), "settings")),
        input=_input(require_dict(data.get("input"), "input")),
        outputs={str(name): _profile(str(name), require_dict(p, f"outputs.{name}")) for name, p in outputs.items()},
        watch=_watch(require_dict(data.get("watch"), "watch")),
    )
    _check_placeholders(config)
    return config


def _settings(d: dict) -> Settings:
    check_keys(d, Settings.__dataclass_fields__, "settings")
    return Settings(
        on_error=choice(d.get("on_error", "continue"), ("continue", "stop"), "settings.on_error"),
        cleanup_source=typed(d.get("cleanup_source", False), bool, "settings.cleanup_source"),
        cleanup_output_after_print=typed(
            d.get("cleanup_output_after_print", False), bool, "settings.cleanup_output_after_print"
        ),
        print_backend=choice(d.get("print_backend", "auto"), BACKENDS, "settings.print_backend"),
    )


def _watch(d: dict) -> WatchSettings:
    check_keys(d, WatchSettings.__dataclass_fields__, "watch")
    ws = WatchSettings(
        poll_interval=float(typed(d.get("poll_interval", 2.0), (int, float), "watch.poll_interval")),
        debounce_delay=float(typed(d.get("debounce_delay", 1.0), (int, float), "watch.debounce_delay")),
        process_existing=typed(d.get("process_existing", True), bool, "watch.process_existing"),
    )
    if ws.poll_interval <= 0 or ws.debounce_delay < 0:
        raise ConfigError("watch: poll_interval must be > 0 and debounce_delay >= 0")
    return ws


def _input(d: dict) -> InputConfig:
    check_keys(d, ("path", "pattern", "sort", "filter", "fields"), "input")
    flt = require_dict(d.get("filter"), "input.filter")
    check_keys(flt, ("keywords", "match"), "input.filter")
    keywords = flt.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise ConfigError("input.filter.keywords: expected a list of strings")
    return InputConfig(
        path=Path(typed(d.get("path", "input"), str, "input.path")),
        pattern=typed(d.get("pattern", "*.pdf"), str, "input.pattern"),
        sort=_sort(d.get("sort"), "input.sort"),
        keywords=keywords,
        match=choice(flt.get("match", "any"), ("any", "all"), "input.filter.match"),
        fields=_fields(require_dict(d.get("fields"), "input.fields")),
    )


def _fields(d: dict) -> dict[str, TextField]:
    """``name: pattern`` or ``name: {pattern, format, default}``."""
    fields = {}
    for name, spec in d.items():
        where = f"input.fields.{name}"
        if not re.fullmatch(r"[A-Za-z_]\w*", str(name)) or name in BUILTIN_PLACEHOLDERS:
            raise ConfigError(f"{where}: field names must be identifiers other than {', '.join(BUILTIN_PLACEHOLDERS)}")
        spec = {"pattern": spec} if isinstance(spec, str) else require_dict(spec, where)
        check_keys(spec, ("pattern", "format", "default"), where)
        try:
            pattern = re.compile(typed(spec.get("pattern"), str, f"{where}.pattern"))
        except re.error as e:
            raise ConfigError(f"{where}.pattern: invalid regular expression: {e}")
        fmt = spec.get("format")
        if fmt is not None:
            typed(fmt, str, f"{where}.format")
            for num, name_ref in re.findall(r"\\(\d+)|\\g<(\w+)>", fmt):
                if (num and int(num) > pattern.groups) or (name_ref and name_ref not in pattern.groupindex):
                    raise ConfigError(f"{where}.format: refers to group {num or name_ref!r}, which the pattern lacks")
        default = spec.get("default")
        fields[str(name)] = TextField(pattern, fmt, None if default is None else str(default))
    return fields


def _check_placeholders(config: "Config") -> None:
    """Every ``{name}`` in stamp text must be a built-in placeholder or an input field."""
    known = set(BUILTIN_PLACEHOLDERS) | set(config.input.fields)
    for profile in config.outputs.values():
        for i, t in enumerate(profile.transforms):
            if t.name != "stamp":
                continue
            for name in re.findall(r"\{(\w+)\}", t.options.text):
                if name not in known:
                    raise ConfigError(
                        f"outputs.{profile.name}.transforms[{i}].stamp.text: unknown placeholder {{{name}}} "
                        f"(built-in: {', '.join(BUILTIN_PLACEHOLDERS)}; define others under input.fields)"
                    )


def _sort(value: Any, where: str) -> str | None:
    return None if value is None else choice(value, SORT_ORDERS, where)


def _profile(name: str, d: dict) -> OutputProfile:
    where = f"outputs.{name}"
    check_keys(
        d,
        (
            "enabled",
            "pages",
            "transforms",
            "output_dir",
            "filename_prefix",
            "filename_suffix",
            "sort",
            "debug",
            "print",
        ),
        where,
    )
    if "pages" not in d:
        raise ConfigError(f"{where}: missing required 'pages' (e.g. pages: all)")
    try:
        validate_page_spec_syntax(d["pages"])
    except PageSelectionError as e:
        raise ConfigError(f"{where}.pages: {e}")
    transforms = d.get("transforms") or []
    if not isinstance(transforms, list):
        raise ConfigError(f"{where}.transforms: expected a list")
    return OutputProfile(
        name=name,
        pages=d["pages"],
        enabled=typed(d.get("enabled", True), bool, f"{where}.enabled"),
        output_dir=Path(typed(d.get("output_dir", "output"), str, f"{where}.output_dir")),
        filename_prefix=typed(d.get("filename_prefix", ""), str, f"{where}.filename_prefix"),
        filename_suffix=typed(d.get("filename_suffix", ""), str, f"{where}.filename_suffix"),
        transforms=[parse_transform(t, f"{where}.transforms[{i}]") for i, t in enumerate(transforms)],
        print=_print(require_dict(d.get("print"), f"{where}.print"), f"{where}.print"),
        debug=typed(d.get("debug", False), bool, f"{where}.debug"),
        sort=_sort(d.get("sort"), f"{where}.sort"),
    )


_TARGET_KEYS = ("printer", "weight", "copies", "args", "options")
_SINGLE_KEYS = ("printer", "copies", "args", "options")


def _print(d: dict, where: str) -> PrintConfig:
    check_keys(d, ("enabled", "merge", "targets", "max_pages", "max_page_size", "action", *_SINGLE_KEYS), where)
    if "targets" in d:
        mixed = [k for k in _SINGLE_KEYS if k in d]
        if mixed:
            raise ConfigError(f"{where}: use either 'targets' or a single 'printer', not both (found {mixed})")
        targets_data = require_dict(d["targets"], f"{where}.targets")
        targets = {
            str(n): _target(require_dict(t, f"{where}.targets.{n}"), f"{where}.targets.{n}")
            for n, t in targets_data.items()
        }
    elif "printer" in d:
        targets = {"default": _target({k: d[k] for k in _SINGLE_KEYS if k in d}, where)}
    else:
        targets = {}

    enabled = typed(d.get("enabled", False), bool, f"{where}.enabled")
    if enabled and not targets:
        raise ConfigError(f"{where}: printing is enabled but no 'printer' or 'targets' is set")

    max_pages = d.get("max_pages")
    if max_pages is not None and typed(max_pages, int, f"{where}.max_pages") < 1:
        raise ConfigError(f"{where}.max_pages: must be at least 1")
    max_size = None
    if "max_page_size" in d:
        w, h = pair(d["max_page_size"], f"{where}.max_page_size")
        max_size = (to_points(w, f"{where}.max_page_size"), to_points(h, f"{where}.max_page_size"))

    return PrintConfig(
        enabled=enabled,
        merge=typed(d.get("merge", False), bool, f"{where}.merge"),
        targets=targets,
        max_pages=max_pages,
        max_page_size=max_size,
        action=choice(d.get("action", "block"), ("block", "warn"), f"{where}.action"),
    )


def _target(d: dict, where: str) -> PrintTarget:
    check_keys(d, _TARGET_KEYS, where)
    printer = typed(d.get("printer", ""), str, f"{where}.printer").strip()
    if not printer:
        raise ConfigError(f"{where}: 'printer' is required (run 'pdfm --list-printers' to see names)")
    weight = typed(d.get("weight", 1), int, f"{where}.weight")
    copies = typed(d.get("copies", 1), int, f"{where}.copies")
    if weight < 0 or copies < 1:
        raise ConfigError(f"{where}: weight must be >= 0 and copies >= 1")
    return PrintTarget(
        printer=printer,
        weight=weight,
        copies=copies,
        args=_args(d.get("args", []), f"{where}.args"),
        options=_options(d.get("options", {}), f"{where}.options"),
    )


def _args(value: Any, where: str) -> list[str]:
    """A list of strings; an item containing spaces is split shell-style."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ConfigError(f"{where}: expected a list of strings")
    result: list[str] = []
    for item in value:
        if isinstance(item, (dict, list)):
            raise ConfigError(f"{where}: expected a list of strings")
        result.extend(shlex.split(item) if isinstance(item, str) and " " in item else [str(item)])
    return result


def _options(value: Any, where: str) -> dict[str, str]:
    value = require_dict(value, where)
    result = {}
    for key, val in value.items():
        if isinstance(val, (dict, list)) or val is None:
            raise ConfigError(f"{where}.{key}: expected a single value")
        result[str(key)] = str(val).lower() if isinstance(val, bool) else str(val)
    return result
