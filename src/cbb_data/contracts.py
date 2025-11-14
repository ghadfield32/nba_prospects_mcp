"""Data Contracts for Basketball League Fetchers

Defines the standard interface and column schemas that all league fetchers must implement.
This ensures consistency across different data sources (ESPN, FIBA HTML, PrestoSports, etc.)

Key Concepts:
- Endpoint: A specific dataset type (schedule, player_game, etc.)
- LeagueFetcher: Protocol defining required methods
- Column Standards: Standardized column names and types for each endpoint

Usage:
    from cbb_data.contracts import validate_schedule, validate_player_game

    df = fetch_some_schedule(...)
    validate_schedule(df, league="NCAA-MBB", season="2024")
"""

from __future__ import annotations

import logging
from typing import Literal, Protocol

import pandas as pd

logger = logging.getLogger(__name__)

# Endpoint type definitions
Endpoint = Literal[
    "schedule",
    "team_game",
    "player_game",
    "pbp",
    "team_season",
    "player_season",
    "shots",
]


# ==============================================================================
# League Fetcher Protocol
# ==============================================================================


class LeagueFetcher(Protocol):
    """Protocol defining the interface all league fetchers must implement

    Each fetcher should implement the methods for endpoints it supports.
    Check catalog/capabilities.py for which endpoints each league supports.
    """

    league_code: str

    def fetch_schedule(self, season: str) -> pd.DataFrame:
        """Fetch game schedule for a season"""
        ...

    def fetch_team_game(self, season: str) -> pd.DataFrame:
        """Fetch team-level box scores for all games in a season"""
        ...

    def fetch_player_game(self, season: str) -> pd.DataFrame:
        """Fetch player-level box scores for all games in a season"""
        ...

    def fetch_pbp(self, season: str) -> pd.DataFrame:
        """Fetch play-by-play events for all games in a season"""
        ...

    def fetch_team_season(self, season: str) -> pd.DataFrame:
        """Fetch team season aggregates"""
        ...

    def fetch_player_season(self, season: str) -> pd.DataFrame:
        """Fetch player season aggregates"""
        ...

    def fetch_shots(self, season: str) -> pd.DataFrame:
        """Fetch shot location data (optional - not all leagues provide)"""
        ...


# ==============================================================================
# Column Standards for Each Endpoint
# ==============================================================================

# Required columns for each endpoint type
REQUIRED_COLUMNS = {
    "schedule": {
        "LEAGUE": "League identifier (NCAA-MBB, EuroLeague, etc.)",
        "SEASON": "Season string",
        "GAME_ID": "Unique game identifier within league+season",
        "GAME_DATE": "Game date/time",
        "HOME_TEAM_ID": "Home team identifier",
        "AWAY_TEAM_ID": "Away team identifier",
    },
    "team_game": {
        "LEAGUE": "League identifier",
        "SEASON": "Season string",
        "GAME_ID": "Game identifier",
        "TEAM_ID": "Team identifier",
        "PTS": "Points scored",
    },
    "player_game": {
        "LEAGUE": "League identifier",
        "SEASON": "Season string",
        "GAME_ID": "Game identifier",
        "TEAM_ID": "Team identifier",
        "PLAYER_ID": "Player identifier",
        "PLAYER_NAME": "Player name",
        "MIN": "Minutes played",
        "PTS": "Points scored",
    },
    "pbp": {
        "LEAGUE": "League identifier",
        "SEASON": "Season string",
        "GAME_ID": "Game identifier",
        "EVENT_NUM": "Event sequence number",
        "PERIOD": "Quarter/period number",
        "EVENT_TYPE": "Type of event",
        "DESCRIPTION": "Event description",
    },
    "team_season": {
        "LEAGUE": "League identifier",
        "SEASON": "Season string",
        "TEAM_ID": "Team identifier",
        "TEAM": "Team name",
        "GP": "Games played",
        "PTS": "Total points",
    },
    "player_season": {
        "LEAGUE": "League identifier",
        "SEASON": "Season string",
        "PLAYER_ID": "Player identifier",
        "PLAYER_NAME": "Player name",
        "TEAM_ID": "Team identifier",
        "GP": "Games played",
        "PTS": "Total points",
    },
    "shots": {
        "LEAGUE": "League identifier",
        "SEASON": "Season string",
        "GAME_ID": "Game identifier",
        "TEAM_ID": "Team identifier",
        "PLAYER_ID": "Player identifier",
        "X": "Shot X coordinate",
        "Y": "Shot Y coordinate",
        "MADE": "Shot made (1) or missed (0)",
    },
}

# Optional but recommended columns
RECOMMENDED_COLUMNS = {
    "schedule": [
        "HOME_TEAM",
        "AWAY_TEAM",
        "HOME_SCORE",
        "AWAY_SCORE",
        "VENUE",
        "NEUTRAL_SITE",
        "STATUS",
    ],
    "team_game": [
        "TEAM",
        "IS_HOME",
        "MIN",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "REB",
        "AST",
        "TOV",
    ],
    "player_game": [
        "TEAM",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "PF",
    ],
    "pbp": ["CLOCK", "TEAM_ID", "PLAYER_ID", "SCORE_HOME", "SCORE_AWAY"],
    "team_season": ["MIN", "PTS_PG", "FG_PCT", "FG3_PCT", "FT_PCT", "REB_PG", "AST_PG"],
    "player_season": ["TEAM", "MIN", "PTS_PG", "FG_PCT", "FG3_PCT", "FT_PCT", "REB_PG", "AST_PG"],
    "shots": ["SHOT_TYPE", "SHOT_DISTANCE", "PERIOD", "CLOCK"],
}


# ==============================================================================
# Validation Functions
# ==============================================================================


def validate_dataframe(
    df: pd.DataFrame,
    endpoint: Endpoint,
    league: str,
    season: str,
    strict: bool = False,
) -> tuple[bool, list[str]]:
    """Validate a DataFrame against endpoint contract

    Args:
        df: DataFrame to validate
        endpoint: Endpoint type (schedule, player_game, etc.)
        league: League identifier for context
        season: Season string for context
        strict: If True, require recommended columns too

    Returns:
        Tuple of (is_valid, list_of_issues)

    Example:
        >>> df = fetch_schedule("NCAA-MBB", "2024")
        >>> is_valid, issues = validate_dataframe(df, "schedule", "NCAA-MBB", "2024")
        >>> if not is_valid:
        ...     logger.warning(f"Validation issues: {issues}")
    """
    issues = []

    # Check if DataFrame is empty
    if df.empty:
        issues.append(f"{league} {season} {endpoint}: DataFrame is empty")
        return len(issues) == 0, issues

    # Check required columns
    required = REQUIRED_COLUMNS.get(endpoint, {})
    missing_required = set(required.keys()) - set(df.columns)
    if missing_required:
        issues.append(f"{league} {season} {endpoint}: Missing required columns: {missing_required}")

    # Check recommended columns (if strict mode)
    if strict:
        recommended = RECOMMENDED_COLUMNS.get(endpoint, [])
        missing_recommended = set(recommended) - set(df.columns)
        if missing_recommended:
            issues.append(
                f"{league} {season} {endpoint}: Missing recommended columns: {missing_recommended}"
            )

    # Endpoint-specific validations
    if endpoint == "schedule":
        # No duplicate game IDs
        if "GAME_ID" in df.columns:
            duplicates = df.duplicated(subset=["GAME_ID"], keep=False)
            if duplicates.any():
                dup_count = duplicates.sum()
                issues.append(f"{league} {season} schedule: {dup_count} duplicate GAME_IDs found")

        # GAME_DATE should not be null
        if "GAME_DATE" in df.columns:
            null_dates = df["GAME_DATE"].isnull().sum()
            if null_dates > 0:
                issues.append(f"{league} {season} schedule: {null_dates} rows with null GAME_DATE")

    elif endpoint == "team_game":
        # Should have exactly 2 rows per game (home + away) for most cases
        if "GAME_ID" in df.columns:
            game_counts = df.groupby("GAME_ID").size()
            non_two_count = (game_counts != 2).sum()
            if non_two_count > 0:
                # This is a warning, not an error (some games might have forfeit/special cases)
                issues.append(
                    f"{league} {season} team_game: {non_two_count} games with != 2 teams "
                    "(may be normal for forfeits/special cases)"
                )

    elif endpoint == "player_game":
        # Player minutes should be reasonable
        if "MIN" in df.columns:
            invalid_mins = ((df["MIN"] < 0) | (df["MIN"] > 60)).sum()
            if invalid_mins > 0:
                issues.append(
                    f"{league} {season} player_game: {invalid_mins} rows with invalid minutes (<0 or >60)"
                )

    elif endpoint == "pbp":
        # Event numbers should be unique and sequential within each game
        if "GAME_ID" in df.columns and "EVENT_NUM" in df.columns:
            for game_id, game_df in df.groupby("GAME_ID"):
                event_nums = game_df["EVENT_NUM"].values
                if not all(event_nums[i] < event_nums[i + 1] for i in range(len(event_nums) - 1)):
                    issues.append(
                        f"{league} {season} pbp: Game {game_id} has non-sequential EVENT_NUMs"
                    )
                    break  # Don't spam with all games

    # Check for NULL values in critical columns
    critical_cols = list(required.keys())
    for col in critical_cols:
        if col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                issues.append(
                    f"{league} {season} {endpoint}: {null_count} null values in critical column '{col}'"
                )

    return len(issues) == 0, issues


def validate_schedule(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate schedule DataFrame"""
    return validate_dataframe(df, "schedule", league, season, strict)


def validate_team_game(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate team_game DataFrame"""
    return validate_dataframe(df, "team_game", league, season, strict)


def validate_player_game(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate player_game DataFrame"""
    return validate_dataframe(df, "player_game", league, season, strict)


def validate_pbp(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate pbp DataFrame"""
    return validate_dataframe(df, "pbp", league, season, strict)


def validate_team_season(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate team_season DataFrame"""
    return validate_dataframe(df, "team_season", league, season, strict)


def validate_player_season(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate player_season DataFrame"""
    return validate_dataframe(df, "player_season", league, season, strict)


def validate_shots(
    df: pd.DataFrame, league: str, season: str, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validate shots DataFrame"""
    return validate_dataframe(df, "shots", league, season, strict)


# ==============================================================================
# Helper: Add Missing Standard Columns
# ==============================================================================


def ensure_standard_columns(
    df: pd.DataFrame, endpoint: Endpoint, league: str, season: str
) -> pd.DataFrame:
    """Add missing standard columns with default values

    Args:
        df: DataFrame to augment
        endpoint: Endpoint type
        league: League identifier
        season: Season string

    Returns:
        DataFrame with all required columns (fills with defaults if missing)

    Example:
        >>> df = fetch_some_data(...)
        >>> df = ensure_standard_columns(df, "schedule", "NCAA-MBB", "2024")
    """
    df = df.copy()

    # Add LEAGUE and SEASON if missing
    if "LEAGUE" not in df.columns:
        df["LEAGUE"] = league
    if "SEASON" not in df.columns:
        df["SEASON"] = season

    # Add SOURCE column for debugging
    if "SOURCE" not in df.columns:
        df["SOURCE"] = f"{league.lower()}_fetcher"

    return df
