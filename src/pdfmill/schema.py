"""Small helpers for strict, path-aware config validation."""

import difflib
from collections.abc import Iterable
from typing import Any


class ConfigError(Exception):
    """Raised when configuration is invalid. Messages are prefixed with the YAML path."""


def require_dict(value: Any, where: str) -> dict:
    """Return ``value`` if it is a mapping (``None`` becomes ``{}``), else raise."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected a mapping, got {type(value).__name__}")
    return value


def check_keys(data: dict, allowed: Iterable[str], where: str) -> None:
    """Reject keys not in ``allowed``, suggesting the closest valid key."""
    allowed = list(allowed)
    for key in data:
        if key not in allowed:
            close = difflib.get_close_matches(str(key), allowed, n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else f" (valid keys: {', '.join(allowed)})"
            raise ConfigError(f"{where}: unknown key '{key}'{hint}")


def choice(value: Any, options: Iterable[str], where: str) -> str:
    """Validate that ``value`` is one of ``options``."""
    options = list(options)
    if value not in options:
        raise ConfigError(f"{where}: invalid value {value!r} (valid: {', '.join(options)})")
    return value


def typed(value: Any, kind: type | tuple[type, ...], where: str) -> Any:
    """Validate the Python type of a scalar value (bools are not accepted as numbers)."""
    kinds = kind if isinstance(kind, tuple) else (kind,)
    if isinstance(value, bool) and bool not in kinds:
        raise ConfigError(f"{where}: expected {_names(kinds)}, got bool")
    if not isinstance(value, kinds):
        raise ConfigError(f"{where}: expected {_names(kinds)}, got {type(value).__name__}")
    return value


def pair(value: Any, where: str) -> tuple[Any, Any]:
    """Validate a two-element list such as ``[x, y]`` or ``[width, height]``."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigError(f"{where}: expected a list of two values, got {value!r}")
    return value[0], value[1]


def _names(kinds: tuple[type, ...]) -> str:
    return " or ".join(k.__name__ for k in kinds)
