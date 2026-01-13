"""Transform registry for pdfmill."""

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdfmill.config import Transform
    from pdfmill.transforms.base import BaseTransform

# Global registry mapping transform names to handler classes
_registry: dict[str, type["BaseTransform"]] = {}


def register_transform(
    name: str,
) -> Callable[[type["BaseTransform"]], type["BaseTransform"]]:
    """Decorator to register a transform class.

    Usage:
        @register_transform("rotate")
        class RotateTransformHandler(BaseTransform):
            ...

    Args:
        name: The transform type name (must match config.Transform.type values)

    Returns:
        Decorator function
    """

    def decorator(cls: type["BaseTransform"]) -> type["BaseTransform"]:
        if name in _registry:
            raise ValueError(f"Transform '{name}' is already registered")
        cls.name = name
        _registry[name] = cls
        return cls

    return decorator


def get_transform(transform_config: "Transform") -> "BaseTransform":
    """Get a transform instance from a config Transform object.

    Args:
        transform_config: The parsed Transform config

    Returns:
        Configured transform instance

    Raises:
        ValueError: If transform type is not registered
    """
    if transform_config.type not in _registry:
        registered = ", ".join(sorted(_registry.keys()))
        raise ValueError(f"Unknown transform type: '{transform_config.type}'. Registered transforms: {registered}")

    transform_cls = _registry[transform_config.type]
    return transform_cls.from_config(transform_config)


def list_transforms() -> list[str]:
    """Return list of registered transform names."""
    return sorted(_registry.keys())


def clear_registry() -> None:
    """Clear the registry. Mainly for testing."""
    _registry.clear()
