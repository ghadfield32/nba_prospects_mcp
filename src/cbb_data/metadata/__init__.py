"""Metadata Module

Coverage and metadata tracking for datasets.
"""

from .coverage import (
    CoverageMap,
    DatasetCoverage,
    format_date_range,
    get_coverage_summary,
    load_coverage,
    save_coverage,
)

__all__ = [
    "CoverageMap",
    "DatasetCoverage",
    "format_date_range",
    "get_coverage_summary",
    "load_coverage",
    "save_coverage",
]
