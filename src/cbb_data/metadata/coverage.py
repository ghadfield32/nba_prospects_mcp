"""Dataset Coverage Metadata

Tracks min/max date coverage for each (league, dataset) combination.
Used to generate the enhanced data availability matrix with date ranges.

Usage:
    from cbb_data.metadata.coverage import DatasetCoverage, CoverageMap, load_coverage

    # Load cached coverage
    coverage = load_coverage()

    # Get coverage for a specific league/dataset
    cov = coverage.get(("NCAA-MBB", "pbp"))
    if cov:
        print(f"Coverage: {cov.min_date} to {cov.max_date}")
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default paths
COVERAGE_CACHE_PATH = Path("data/metadata/coverage.json")


@dataclass(frozen=True)
class DatasetCoverage:
    """Coverage metadata for a single (league, dataset) combination

    Attributes:
        min_date: Earliest date in the dataset (YYYY-MM-DD or "present")
        max_date: Latest date in the dataset (YYYY-MM-DD or "present")
        record_count: Number of records (optional)
        last_updated: When this coverage was computed (ISO format)
        notes: Source info or other notes (optional)
    """

    min_date: str
    max_date: str
    record_count: int | None = None
    last_updated: str | None = None
    notes: str | None = None


# Type alias for coverage map
CoverageMap = dict[tuple[str, str], DatasetCoverage]


def save_coverage(coverage: CoverageMap, path: Path | None = None) -> None:
    """Save coverage metadata to JSON file

    Args:
        coverage: Coverage map to save
        path: Output path (default: data/metadata/coverage.json)
    """
    path = path or COVERAGE_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to JSON-serializable format
    data = {f"{league}|{dataset}": asdict(cov) for (league, dataset), cov in coverage.items()}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved coverage for {len(coverage)} league/dataset combinations to {path}")


def load_coverage(path: Path | None = None) -> CoverageMap:
    """Load coverage metadata from JSON file

    Args:
        path: Input path (default: data/metadata/coverage.json)

    Returns:
        Coverage map
    """
    path = path or COVERAGE_CACHE_PATH

    if not path.exists():
        logger.warning(f"Coverage file not found: {path}")
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        coverage: CoverageMap = {}
        for key, value in data.items():
            league, dataset = key.split("|")
            coverage[(league, dataset)] = DatasetCoverage(
                min_date=value["min_date"],
                max_date=value["max_date"],
                record_count=value.get("record_count"),
                last_updated=value.get("last_updated"),
                notes=value.get("notes"),
            )

        logger.info(f"Loaded coverage for {len(coverage)} league/dataset combinations")
        return coverage

    except Exception as e:
        logger.error(f"Error loading coverage from {path}: {e}")
        return {}


def format_date_range(cov: DatasetCoverage | None) -> str:
    """Format coverage as date range string

    Args:
        cov: Coverage metadata

    Returns:
        Formatted string like "2020-01-01 to 2024-12-31" or "-" if no coverage
    """
    if cov is None:
        return "-"

    # Shorten dates to just YYYY-MM for compactness
    min_short = cov.min_date[:7] if len(cov.min_date) >= 7 else cov.min_date
    max_short = cov.max_date[:7] if len(cov.max_date) >= 7 else cov.max_date

    return f"{min_short}–{max_short}"


def get_coverage_summary(coverage: CoverageMap) -> dict[str, Any]:
    """Get summary statistics about coverage

    Args:
        coverage: Coverage map

    Returns:
        Summary dict with stats
    """
    if not coverage:
        return {"total_combinations": 0}

    leagues = set()
    datasets = set()
    all_min_dates = []
    all_max_dates = []
    total_records = 0

    for (league, dataset), cov in coverage.items():
        leagues.add(league)
        datasets.add(dataset)
        all_min_dates.append(cov.min_date)
        all_max_dates.append(cov.max_date)
        if cov.record_count:
            total_records += cov.record_count

    return {
        "total_combinations": len(coverage),
        "leagues": len(leagues),
        "datasets": len(datasets),
        "overall_min_date": min(all_min_dates) if all_min_dates else None,
        "overall_max_date": max(all_max_dates) if all_max_dates else None,
        "total_records": total_records if total_records > 0 else None,
    }
