#!/usr/bin/env python3
# ruff: noqa: E402
"""Apply name normalization to canonical dataframes.

This module provides the integration point between name normalization utilities
and canonical data ingestion. It:
1. Validates no gold columns are present (contamination check)
2. Applies league-aware name normalization
3. Adds standardized columns to every canonical dataframe

Usage in fetchers:
    from src.identity.apply_normalization import add_name_fields, assert_no_gold_contamination

    # ... after building df ...
    assert_no_gold_contamination(df, context=f"{league}:{season}")
    df = add_name_fields(df, league=league, name_col="PLAYER_NAME_RAW")
    # write parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.identity.name_normalization import normalize_player_name

# Gold columns that should NEVER appear in canonical data
GOLD_COLUMNS = {
    "PLAYER_UID",
    "CANONICAL_PLAYER_ID",
    "CAREER_GAME_NUMBER",
    "LEAGUE_GAME_NUMBER",
    "CONFIDENCE",
    "MATCH_RULE",
}


def assert_no_gold_contamination(df: pd.DataFrame, context: str) -> None:
    """Validate that canonical data doesn't contain gold-layer columns.

    This prevents contamination where pipeline outputs get written back to
    canonical directories, causing merge conflicts downstream.

    Args:
        df: DataFrame to check
        context: Context string for error message (e.g., "ACB:2017-18")

    Raises:
        RuntimeError: If any gold columns are found

    Example:
        >>> assert_no_gold_contamination(df, context="NCAA_MBB:2019")
    """
    contaminated = [c for c in df.columns if c in GOLD_COLUMNS]
    if contaminated:
        raise RuntimeError(
            f"[{context}] Canonical data contamination detected!\n"
            f"Found gold-layer columns: {contaminated}\n"
            f"These columns should never exist in canonical/box_player_game.\n"
            f"This usually means pipeline output was written to canonical directory.\n"
            f"Fix: Remove these columns from the canonical parquet file."
        )


def add_name_fields(
    df: pd.DataFrame, league: str, name_col: str = "PLAYER_NAME_RAW"
) -> pd.DataFrame:
    """Add normalized name fields to dataframe.

    This function:
    1. Parses names using league-specific format rules
    2. Adds canonical name columns
    3. Adds parsed component columns (first, last, initial)
    4. Adds name key columns for matching
    5. Keeps PLAYER_NAME_RAW unchanged

    Columns added:
        - PLAYER_NAME_CANONICAL: "First Last" format
        - FIRST_NAME: Parsed first name (None if only initial available)
        - LAST_NAME: Parsed last name
        - FIRST_INITIAL: First letter of first name
        - NAME_KEY_CANONICAL: Key from full name (e.g., "luka_doncic")
        - NAME_KEY_INITIAL: Key from abbreviated form (e.g., "l_doncic")

    Args:
        df: DataFrame with player names
        league: League code (e.g., "NCAA_MBB", "EUROLEAGUE")
        name_col: Column containing raw player names

    Returns:
        DataFrame with added name columns

    Example:
        >>> df = pd.DataFrame({
        ...     "PLAYER_NAME_RAW": ["Z. Williamson", "DONCIC, LUKA"],
        ...     "PTS": [22.6, 18.7]
        ... })
        >>> df_norm = add_name_fields(df, league="NCAA_MBB")
        >>> df_norm["NAME_KEY_CANONICAL"].tolist()
        ['williamson', 'luka_doncic']
    """
    assert name_col in df.columns, (
        f"Expected '{name_col}' column in dataframe. " f"Got columns: {list(df.columns)[:20]}"
    )

    # Work on copy to avoid modifying input
    out = df.copy()

    # Apply normalization to each row
    norm_results = out[name_col].apply(lambda name: normalize_player_name(league, name))  # type: ignore[arg-type,return-value]

    # Extract fields from NormalizedName objects
    out["PLAYER_NAME_CANONICAL"] = norm_results.apply(lambda n: n.canonical_full)
    out["FIRST_NAME"] = norm_results.apply(lambda n: n.first)
    out["LAST_NAME"] = norm_results.apply(lambda n: n.last)
    out["FIRST_INITIAL"] = norm_results.apply(lambda n: n.first_initial)
    out["NAME_KEY_CANONICAL"] = norm_results.apply(lambda n: n.name_key_canonical)
    out["NAME_KEY_INITIAL"] = norm_results.apply(lambda n: n.name_key_initial)

    return out


def test_add_name_fields() -> None:
    """Test that add_name_fields works correctly."""
    print("Testing add_name_fields...")

    # Test NCAA format
    df_ncaa = pd.DataFrame(
        {"PLAYER_NAME_RAW": ["Z. Williamson", "A. Caruso", "L. Ball"], "PTS": [22.6, 11.0, 8.5]}
    )

    df_ncaa_norm = add_name_fields(df_ncaa, league="NCAA_MBB")

    print("\nNCAA_MBB results:")
    print(
        df_ncaa_norm[
            ["PLAYER_NAME_RAW", "PLAYER_NAME_CANONICAL", "NAME_KEY_CANONICAL", "NAME_KEY_INITIAL"]
        ].to_string()
    )

    # Test EuroLeague format
    df_euro = pd.DataFrame(
        {"PLAYER_NAME_RAW": ["DONCIC, LUKA", "VEZENKOV, ALEKSANDAR"], "PTS": [18.7, 14.3]}
    )

    df_euro_norm = add_name_fields(df_euro, league="EUROLEAGUE")

    print("\nEUROLEAGUE results:")
    print(
        df_euro_norm[
            ["PLAYER_NAME_RAW", "PLAYER_NAME_CANONICAL", "NAME_KEY_CANONICAL", "NAME_KEY_INITIAL"]
        ].to_string()
    )

    # Test NBL format
    df_nbl = pd.DataFrame({"PLAYER_NAME_RAW": ["LaMelo Ball", "Josh Giddey"], "PTS": [17.0, 10.9]})

    df_nbl_norm = add_name_fields(df_nbl, league="NBL")

    print("\nNBL results:")
    print(
        df_nbl_norm[
            ["PLAYER_NAME_RAW", "PLAYER_NAME_CANONICAL", "NAME_KEY_CANONICAL", "NAME_KEY_INITIAL"]
        ].to_string()
    )

    # Verify no gold contamination check works
    print("\nTesting contamination check...")
    df_bad = pd.DataFrame(
        {
            "PLAYER_NAME_RAW": ["Test Player"],
            "PLAYER_UID": ["P_test_123"],  # Gold column!
            "PTS": [10.0],
        }
    )

    try:
        assert_no_gold_contamination(df_bad, context="TEST:2024")
        print("✗ Should have raised error for gold column!")
    except RuntimeError as e:
        print(f"✓ Correctly caught contamination: {str(e)[:100]}...")

    print("\n✓ All tests passed")


if __name__ == "__main__":
    test_add_name_fields()
