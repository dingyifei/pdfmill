"""Transform registry for extensible transform dispatch."""

from typing import TYPE_CHECKING

from pdfmill.exceptions import ConfigError

if TYPE_CHECKING:
    from pdfmill.transforms.base import TransformHandler


class TransformRegistry:
    """Registry for transform handlers.

    Provides centralized dispatch for transform operations, replacing
    hardcoded if/elif chains with a pluggable registry pattern.

    Usage:
        # Register a handler (typically via decorator)
        @TransformRegistry.register
        class RotateHandler(TransformHandler):
            name = "rotate"
            ...

        # Get handler by name
        handler = TransformRegistry.get("rotate")

        # List available transforms
        names = TransformRegistry.all_names()
    """

    _handlers: dict[str, type["TransformHandler"]] = {}

    @classmethod
    def register(cls, handler_class: type["TransformHandler"]) -> type["TransformHandler"]:
        """Register a transform handler class.

        Can be used as a decorator:
            @TransformRegistry.register
            class MyHandler(TransformHandler):
                name = "my_transform"
                ...

        Args:
            handler_class: TransformHandler subclass to register

        Returns:
            The handler class (for decorator use)
        """
        # Get the name from an instance or class attribute
        name = handler_class.name if hasattr(handler_class, 'name') else handler_class().name
        cls._handlers[name] = handler_class
        return handler_class

    @classmethod
    def get(cls, name: str) -> type["TransformHandler"]:
        """Get a transform handler class by name.

        Args:
            name: Transform type name (e.g., 'rotate', 'crop')

        Returns:
            The handler class

        Raises:
            ConfigError: If no handler is registered for the name
        """
        if name not in cls._handlers:
            available = ", ".join(sorted(cls._handlers.keys()))
            raise ConfigError(
                f"Unknown transform type: '{name}'. Available: {available}",
                context={"transform_type": name},
            )
        return cls._handlers[name]

    @classmethod
    def get_instance(cls, name: str) -> "TransformHandler":
        """Get an instantiated transform handler by name.

        Args:
            name: Transform type name

        Returns:
            Handler instance
        """
        return cls.get(name)()

    @classmethod
    def all_names(cls) -> list[str]:
        """Get all registered transform type names.

        Returns:
            Sorted list of registered transform names
        """
        return sorted(cls._handlers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a transform type is registered.

        Args:
            name: Transform type name

        Returns:
            True if registered
        """
        return name in cls._handlers

    @classmethod
    def clear(cls) -> None:
        """Clear all registered handlers (for testing)."""
        cls._handlers.clear()
