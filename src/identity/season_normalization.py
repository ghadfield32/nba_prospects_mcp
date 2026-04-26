"""Season Normalization - Add 5 season columns to canonical data.

Columns Added:
1. SEASON_RAW - Original season string from source (unchanged)
2. SEASON - Normalized YYYY-YY format (canonical)
3. SEASON_START_YEAR - Integer start year
4. SEASON_END_YEAR - Integer end year
5. SEASON_TYPE - 'regular' or 'postseason'

This module leverages existing utilities from api/src/airflow_project/eda/nba_prospects/cbb_data/utils/season.py
but adds proper handling for canonical format compliance.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# Lazy import helpers for season utilities (imported on first use)
def _ensure_season_utils_imported() -> None:
    """Ensure season utility functions are imported (lazy import to avoid path issues)"""
    global season_start_year, season_end_year

    if "season_start_year" not in globals():
        # Add path to access existing utilities
        CBB_DATA_PATH = Path("/workspace/api/src/airflow_project/eda/nba_prospects/cbb_data")
        if str(CBB_DATA_PATH) not in sys.path:
            sys.path.insert(0, str(CBB_DATA_PATH))

        try:
            from utils.season import season_end_year as _season_end_year
            from utils.season import season_start_year as _season_start_year

            # Make them module-level for subsequent calls
            globals()["season_start_year"] = _season_start_year
            globals()["season_end_year"] = _season_end_year
        except ImportError:
            # If import fails, it might be because we're in a different context
            # Try importing directly from the full path
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "season", str(CBB_DATA_PATH / "utils" / "season.py")
            )
            assert spec is not None and spec.loader is not None
            season_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(season_module)

            globals()["season_start_year"] = season_module.season_start_year
            globals()["season_end_year"] = season_module.season_end_year


@dataclass(frozen=True)
class NormalizedSeason:
    """Container for normalized season fields."""

    raw: str
    season: str  # YYYY-YY format
    start_year: int
    end_year: int
    season_type: str


def normalize_season(season_raw: str, league: str) -> NormalizedSeason:
    """
    Normalize season string to canonical YYYY-YY format.

    Handles all formats:
    - YYYY (single year) → YYYY-YY (e.g., "2019" → "2018-19")
    - YYYY-YY (already compliant) → unchanged
    - YYYY-YYYY (full dual year) → YYYY-YY (e.g., "2018-2019" → "2018-19")

    Args:
        season_raw: Original season string from source
        league: League code (for context)

    Returns:
        NormalizedSeason with 5 fields

    Examples:
        >>> normalize_season("2019", "NCAA_MBB")
        NormalizedSeason(raw="2019", season="2018-19", start_year=2018, end_year=2019, season_type="regular")

        >>> normalize_season("2021-22", "G_LEAGUE")
        NormalizedSeason(raw="2021-22", season="2021-22", start_year=2021, end_year=2022, season_type="regular")
    """
    # Ensure season utilities are imported (lazy import)
    _ensure_season_utils_imported()

    if not season_raw or pd.isna(season_raw):
        raise ValueError(f"Cannot parse NULL/empty season (league: {league})")

    season_str = str(season_raw).strip()

    # Extract start and end years using existing utilities
    start_year = season_start_year(season_str)  # type: ignore[name-defined]
    end_year = season_end_year(season_str)  # type: ignore[name-defined]

    if start_year is None:
        raise ValueError(f"Cannot parse season: {season_raw} (league: {league})")

    # Determine season type
    season_type = "postseason" if "playoff" in season_str.lower() else "regular"

    # Handle different formats and convert to canonical YYYY-YY
    # Check if already in YYYY-YY format
    if re.match(r"^\d{4}-\d{2}$", season_str):
        # Already compliant: "2021-22"
        season_canonical = season_str
        if end_year is None:
            # If end_year wasn't parsed, derive from season string
            end_suffix = int(season_str.split("-")[1])
            if end_suffix < 50:
                end_year = 2000 + end_suffix
            else:
                end_year = 1900 + end_suffix

    elif re.match(r"^\d{4}-\d{4}$", season_str):
        # Full format: "2018-2019" → "2018-19"
        start, end = season_str.split("-")
        season_canonical = f"{start}-{end[-2:]}"
        if end_year is None:
            end_year = int(end)

    elif re.match(r"^\d{4}$", season_str):
        # Single year: "2019" → interpret as 2018-19 season
        # Basketball seasons span two calendar years, with the single year
        # representing the second half (spring semester, playoffs)
        # So "2019" = "2018-19" season
        year = int(season_str)
        start_year = year - 1
        end_year = year
        season_canonical = f"{start_year}-{str(end_year)[-2:]}"

    elif re.match(r"^[EU]\d{4}$", season_str):
        # EuroLeague format: "E2019" or "U2019"
        # Extract year and convert to canonical format
        year = int(season_str[1:])
        start_year = year
        end_year = year + 1
        season_canonical = f"{start_year}-{str(end_year)[-2:]}"

    else:
        # Fallback: try to construct from start_year
        if end_year is None:
            end_year = start_year + 1
        season_canonical = f"{start_year}-{str(end_year)[-2:]}"

    return NormalizedSeason(
        raw=season_raw,
        season=season_canonical,
        start_year=start_year,
        end_year=end_year,
        season_type=season_type,
    )


def add_season_fields(df: pd.DataFrame, league: str, season_col: str = "SEASON") -> pd.DataFrame:
    """
    Add 5 normalized season columns to dataframe.

    Args:
        df: Input dataframe with raw season column
        league: League code
        season_col: Name of existing season column (default: "SEASON")

    Returns:
        DataFrame with 5 new columns added

    Raises:
        KeyError: If season_col not in dataframe
        ValueError: If normalization fails
    """

    if season_col not in df.columns:
        raise KeyError(
            f"Column '{season_col}' not found in dataframe. Available: {list(df.columns)}"
        )

    # Preserve original season in SEASON_RAW
    if "SEASON_RAW" not in df.columns:
        df = df.assign(SEASON_RAW=df[season_col].astype(str))

    # Normalize all seasons
    def safe_normalize(season_val: str) -> NormalizedSeason:
        """Wrapper to handle errors gracefully."""
        try:
            return normalize_season(season_val, league)
        except Exception as e:
            # Re-raise with context
            raise ValueError(
                f"Failed to normalize season '{season_val}' for league {league}: {e}"
            ) from e

    normalized = df["SEASON_RAW"].apply(safe_normalize)  # type: ignore[arg-type,return-value]

    # Unpack into separate columns
    df = df.assign(
        SEASON=normalized.apply(lambda n: n.season),
        SEASON_START_YEAR=normalized.apply(lambda n: n.start_year),
        SEASON_END_YEAR=normalized.apply(lambda n: n.end_year),
        SEASON_TYPE=normalized.apply(lambda n: n.season_type),
    )

    return df


def validate_season_normalization(df: pd.DataFrame) -> dict:
    r"""
    Validate season normalization was successful.

    Checks:
    1. All 5 season columns present
    2. SEASON matches pattern ^\d{4}-\d{2}$
    3. SEASON_START_YEAR < SEASON_END_YEAR
    4. No NULL values in SEASON

    Returns:
        dict with validation results
    """

    required_cols = ["SEASON_RAW", "SEASON", "SEASON_START_YEAR", "SEASON_END_YEAR", "SEASON_TYPE"]

    results = {
        "columns_present": all(col in df.columns for col in required_cols),
        "missing_columns": [col for col in required_cols if col not in df.columns],
    }

    if not results["columns_present"]:
        results["passed"] = False
        return results

    # Check SEASON format
    results["season_format_valid"] = df["SEASON"].str.match(r"^\d{4}-\d{2}$").all()

    # Check year ordering
    results["year_order_valid"] = (df["SEASON_START_YEAR"] < df["SEASON_END_YEAR"]).all()

    # Check for NULLs
    results["no_nulls"] = df["SEASON"].notna().all()

    # Summary stats
    results["total_rows"] = len(df)
    results["unique_seasons"] = df["SEASON"].nunique()

    # Overall pass/fail
    results["passed"] = all(
        [
            results["columns_present"],
            results["season_format_valid"],
            results["year_order_valid"],
            results["no_nulls"],
        ]
    )

    return results
