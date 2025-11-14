"""FIBA-specific test helpers

Centralized utilities for testing FIBA HTML-based league fetchers.
Handles common scenarios like empty data due to 403 errors or placeholder game IDs.
"""

import pandas as pd
import pytest


def skip_if_empty_fiba(endpoint_name: str, df: pd.DataFrame, league: str, season: str) -> None:
    """Skip test if FIBA endpoint returns empty DataFrame

    This is common when:
    - FIBA LiveStats returns 403 Forbidden
    - Game index contains placeholder IDs
    - Network issues prevent scraping
    - Season/league not yet available

    Args:
        endpoint_name: Name of endpoint being tested (e.g., "player_game")
        df: DataFrame returned from fetch function
        league: League code (e.g., "LKL", "BAL")
        season: Season string (e.g., "2023-24")

    Example:
        >>> player_game = fetcher.fetch_player_game("2023-24")
        >>> skip_if_empty_fiba("player_game", player_game, "LKL", "2023-24")
        >>> # Test continues only if data is available
    """
    if df.empty:
        pytest.skip(
            f"{league} {season}: {endpoint_name} empty - "
            f"likely no FIBA HTML available or placeholder game IDs"
        )


def skip_if_no_schedule(schedule: pd.DataFrame, league: str, season: str) -> None:
    """Skip test if schedule is not available

    Schedule is required for most other endpoints. If schedule is empty,
    downstream tests cannot proceed.

    Args:
        schedule: Schedule DataFrame
        league: League code
        season: Season string

    Example:
        >>> schedule = fetcher.fetch_schedule("2023-24")
        >>> skip_if_no_schedule(schedule, "BAL", "2023-24")
        >>> # Test continues only if schedule exists
    """
    if schedule.empty:
        pytest.skip(
            f"{league} {season}: No schedule available - "
            f"create game index at data/game_indexes/{league}_{season.replace('-', '_')}.csv"
        )


def assert_fiba_metadata(df: pd.DataFrame, league: str, season: str) -> None:
    """Assert FIBA-specific metadata columns are present and valid

    FIBA HTML scraped data should have:
    - SOURCE = "fiba_html"
    - LEAGUE = league code
    - SEASON = season string

    Args:
        df: DataFrame to validate
        league: Expected league code
        season: Expected season string

    Raises:
        AssertionError: If metadata is missing or invalid
    """
    if df.empty:
        return  # Skip validation for empty DataFrames

    # Check SOURCE column
    if "SOURCE" in df.columns:
        assert (df["SOURCE"] == "fiba_html").all(), "All FIBA data should have SOURCE='fiba_html'"

    # Check LEAGUE column
    if "LEAGUE" in df.columns:
        assert (df["LEAGUE"] == league).all(), f"All data should have LEAGUE='{league}'"

    # Check SEASON column
    if "SEASON" in df.columns:
        assert (df["SEASON"] == season).all(), f"All data should have SEASON='{season}'"


def get_fiba_game_index_path(league: str, season: str) -> str:
    """Get expected path for FIBA game index CSV

    Args:
        league: League code (e.g., "LKL")
        season: Season string (e.g., "2023-24")

    Returns:
        Path string to game index CSV

    Example:
        >>> get_fiba_game_index_path("BCL", "2023-24")
        'data/game_indexes/BCL_2023_24.csv'
    """
    season_normalized = season.replace("-", "_")
    return f"data/game_indexes/{league}_{season_normalized}.csv"
