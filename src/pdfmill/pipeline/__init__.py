"""Pipeline package for pdfmill.

This package provides the TransformExecutor and PrintPipeline classes
for managing transform execution and print workflows.

Usage:
    from pdfmill.pipeline import TransformExecutor, PrintPipeline, PrintResult

    # Transform execution
    executor = TransformExecutor()
    pages = executor.apply(pages, transforms, dry_run=False, ...)

    # Print orchestration
    pipeline = PrintPipeline(dry_run=False)
    result = pipeline.print_outputs(files_by_profile, output_dir, on_error)
"""

from pdfmill.pipeline.printing import PrintPipeline, PrintResult
from pdfmill.pipeline.safety import PrintSafetyError, SafetyCheckResult, check_print_safety, enforce_print_safety
from pdfmill.pipeline.transforms import TransformExecutor

__all__ = [
    "TransformExecutor",
    "PrintPipeline",
    "PrintResult",
    "PrintSafetyError",
    "SafetyCheckResult",
    "check_print_safety",
    "enforce_print_safety",
]
