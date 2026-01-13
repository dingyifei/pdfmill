"""pdfmill - Configurable PDF processing pipeline."""

import logging

__version__ = "0.1.3"
__all__ = ["__version__"]

# Prevent "No handler found" warnings when used as a library
logging.getLogger("pdfmill").addHandler(logging.NullHandler())
