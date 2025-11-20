"""Unified Filter System for Dataset Queries

Provides centralized filter dataclasses for name-based, date-based, and game segment
filtering across all datasets. These filters are applied after data fetch to provide
consistent filtering behavior regardless of the underlying data source.

Usage:
    from cbb_data.api.filters import DatasetFilter, NameFilter, DateFilter, GameSegmentFilter

    # Filter by player name and last 7 days
    filters = DatasetFilter(
        names=NameFilter(leagues=["NCAA-MBB"], player_names=["Zach Edey"]),
        dates=DateFilter(relative_days=7),
    )

    # Filter PBP to 4th quarter crunch time
    filters = DatasetFilter(
        segments=GameSegmentFilter(periods=[4], start_seconds=2520)  # last 2 min of 4Q
    )

Design:
- Filters are applied post-fetch in get_dataset() for consistency
- Name resolution uses IdentityResolver from dimensions.py
- Date filters support both absolute (start/end) and relative (last N days)
- Game segments support periods, halves, and time-based filtering
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd


@dataclass
class NameFilter:
    """Filter datasets by team and/or player names

    Names are resolved to IDs via IdentityResolver before filtering.
    Supports aliases and fuzzy matching through the resolver.

    Attributes:
        leagues: List of leagues to resolve names within
        team_names: Team names/codes to filter by (e.g., ["Duke", "Kentucky"])
        player_names: Player names to filter by (e.g., ["LeBron James"])
    """

    leagues: list[str]
    team_names: list[str] | None = None
    player_names: list[str] | None = None


@dataclass
class DateFilter:
    """Filter datasets by date range

    Supports both absolute date ranges and relative time periods.
    If relative_days is set, it takes precedence over start/end dates.

    Attributes:
        start_date: Earliest date to include (inclusive)
        end_date: Latest date to include (inclusive)
        relative_days: Number of days back from today (e.g., 7 for "last week")

    Examples:
        # Last 7 days
        DateFilter(relative_days=7)

        # Specific range
        DateFilter(start_date=date(2024, 11, 1), end_date=date(2024, 11, 30))

        # Everything since a date
        DateFilter(start_date=date(2024, 1, 1))
    """

    start_date: date | None = None
    end_date: date | None = None
    relative_days: int | None = None

    def get_effective_range(self) -> tuple[date | None, date | None]:
        """Calculate effective start/end dates, accounting for relative_days"""
        if self.relative_days is not None:
            end = date.today()
            start = end - timedelta(days=self.relative_days)
            return start, end
        return self.start_date, self.end_date


@dataclass
class GameSegmentFilter:
    """Filter PBP/shots data by game segment (period, half, time)

    Useful for analyzing specific portions of games:
    - Quarters/periods (1-4, 5+ for OT)
    - Halves (1-2 for college basketball)
    - Time windows (e.g., crunch time, first 5 minutes)

    Attributes:
        periods: List of periods to include (e.g., [4] for 4th quarter)
        halves: List of halves to include (e.g., [1] for first half)
        start_seconds: Minimum game time in seconds from tip
        end_seconds: Maximum game time in seconds from tip

    Examples:
        # 4th quarter only
        GameSegmentFilter(periods=[4])

        # First half (NCAA)
        GameSegmentFilter(halves=[1])

        # Crunch time (last 2 minutes of 4Q in 48-min game)
        GameSegmentFilter(periods=[4], start_seconds=2760)  # 46*60 = 2760

        # Overtime only
        GameSegmentFilter(periods=[5, 6, 7])
    """

    periods: list[int] | None = None
    halves: list[int] | None = None
    start_seconds: int | None = None
    end_seconds: int | None = None


@dataclass
class DatasetFilter:
    """Combined filter for dataset queries

    Wraps all filter types into a single object for passing to get_dataset().

    Attributes:
        names: Name-based filtering (teams/players)
        dates: Date-based filtering (absolute/relative)
        segments: Game segment filtering (periods/halves/time)

    Example:
        # Complex filter: Duke players, last month, 2nd half only
        filters = DatasetFilter(
            names=NameFilter(
                leagues=["NCAA-MBB"],
                team_names=["Duke"],
            ),
            dates=DateFilter(relative_days=30),
            segments=GameSegmentFilter(halves=[2]),
        )
    """

    names: NameFilter | None = None
    dates: DateFilter | None = None
    segments: GameSegmentFilter | None = None


# =============================================================================
# Filter Application Functions
# =============================================================================


def apply_date_filter(
    df: pd.DataFrame,
    date_filter: DateFilter,
    date_column: str = "GAME_DATE",
) -> pd.DataFrame:
    """Apply date filter to a DataFrame

    Args:
        df: DataFrame to filter
        date_filter: Date filter specification
        date_column: Name of the date column to filter on

    Returns:
        Filtered DataFrame
    """
    if df.empty or date_column not in df.columns:
        return df

    start_date, end_date = date_filter.get_effective_range()

    # Ensure date column is datetime type
    if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")

    if start_date is not None:
        df = df[df[date_column] >= pd.Timestamp(start_date)]

    if end_date is not None:
        df = df[df[date_column] <= pd.Timestamp(end_date)]

    return df


def apply_segment_filter(
    df: pd.DataFrame,
    segment_filter: GameSegmentFilter,
) -> pd.DataFrame:
    """Apply game segment filter to PBP/shots DataFrame

    Args:
        df: DataFrame with game segment columns (PERIOD, HALF, GAME_SECONDS)
        segment_filter: Game segment filter specification

    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df

    # Period filter
    if segment_filter.periods is not None and "PERIOD" in df.columns:
        df = df[df["PERIOD"].isin(segment_filter.periods)]

    # Half filter (for NCAA-style games)
    if segment_filter.halves is not None and "HALF" in df.columns:
        df = df[df["HALF"].isin(segment_filter.halves)]

    # Time-based filters (require GAME_SECONDS column)
    if "GAME_SECONDS" in df.columns:
        if segment_filter.start_seconds is not None:
            df = df[df["GAME_SECONDS"] >= segment_filter.start_seconds]
        if segment_filter.end_seconds is not None:
            df = df[df["GAME_SECONDS"] <= segment_filter.end_seconds]

    return df


def apply_name_filter(
    df: pd.DataFrame,
    name_filter: NameFilter,
    team_id_column: str = "TEAM_ID",
    player_id_column: str = "PLAYER_ID",
    team_name_column: str = "TEAM",
    player_name_column: str = "PLAYER_NAME",
    resolver: Any | None = None,
) -> pd.DataFrame:
    """Apply name-based filter to a DataFrame

    Filters by team and/or player names. If an IdentityResolver is provided,
    names are resolved to IDs first. Otherwise, direct name matching is used.

    Args:
        df: DataFrame to filter
        name_filter: Name filter specification
        team_id_column: Column name for team IDs
        player_id_column: Column name for player IDs
        team_name_column: Column name for team names (fallback)
        player_name_column: Column name for player names (fallback)
        resolver: IdentityResolver instance for ID resolution

    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df

    # Team name filtering
    if name_filter.team_names:
        if resolver is not None and team_id_column in df.columns:
            # Resolve names to IDs
            team_ids = set()
            for league in name_filter.leagues:
                for name in name_filter.team_names:
                    team_ids.update(resolver.resolve_team(league, name))
            if team_ids:
                df = df[df[team_id_column].isin(team_ids)]
        elif team_name_column in df.columns:
            # Direct name matching (case-insensitive)
            names_lower = [n.lower() for n in name_filter.team_names]
            df = df[df[team_name_column].str.lower().isin(names_lower)]
        elif team_id_column in df.columns:
            # Try matching against ID column directly
            df = df[df[team_id_column].isin(name_filter.team_names)]

    # Player name filtering
    if name_filter.player_names:
        if resolver is not None and player_id_column in df.columns:
            # Resolve names to IDs
            player_ids = set()
            for league in name_filter.leagues:
                for name in name_filter.player_names:
                    player_ids.update(resolver.resolve_player(league, name))
            if player_ids:
                df = df[df[player_id_column].isin(player_ids)]
        elif player_name_column in df.columns:
            # Direct name matching (case-insensitive)
            names_lower = [n.lower() for n in name_filter.player_names]
            df = df[df[player_name_column].str.lower().isin(names_lower)]
        elif player_id_column in df.columns:
            # Try matching against ID column directly
            df = df[df[player_id_column].isin(name_filter.player_names)]

    return df


def apply_filters(
    df: pd.DataFrame,
    filters: DatasetFilter | None,
    date_column: str = "GAME_DATE",
    team_id_column: str = "TEAM_ID",
    player_id_column: str = "PLAYER_ID",
    team_name_column: str = "TEAM",
    player_name_column: str = "PLAYER_NAME",
    resolver: Any | None = None,
) -> pd.DataFrame:
    """Apply all filters to a DataFrame

    Convenience function that applies name, date, and segment filters in sequence.

    Args:
        df: DataFrame to filter
        filters: Combined filter specification
        date_column: Column name for dates
        team_id_column: Column name for team IDs
        player_id_column: Column name for player IDs
        team_name_column: Column name for team names
        player_name_column: Column name for player names
        resolver: IdentityResolver for name-to-ID resolution

    Returns:
        Filtered DataFrame
    """
    if filters is None or df.empty:
        return df

    # Apply name filter
    if filters.names is not None:
        df = apply_name_filter(
            df,
            filters.names,
            team_id_column=team_id_column,
            player_id_column=player_id_column,
            team_name_column=team_name_column,
            player_name_column=player_name_column,
            resolver=resolver,
        )

    # Apply date filter
    if filters.dates is not None:
        df = apply_date_filter(df, filters.dates, date_column=date_column)

    # Apply segment filter
    if filters.segments is not None:
        df = apply_segment_filter(df, filters.segments)

    return df


# =============================================================================
# Time Column Standardization
# =============================================================================

# Period lengths by league (in seconds)
PERIOD_LENGTHS: dict[str, int] = {
    # Professional leagues (12-minute quarters)
    "G-League": 12 * 60,
    "WNBA": 10 * 60,  # 10-minute quarters
    # European leagues (10-minute quarters)
    "EuroLeague": 10 * 60,
    "EuroCup": 10 * 60,
    "ACB": 10 * 60,
    "LNB_PROA": 10 * 60,
    "NBL": 10 * 60,
    "NZ-NBL": 10 * 60,
    "LKL": 10 * 60,
    "BAL": 10 * 60,
    "BCL": 10 * 60,
    "ABA": 10 * 60,
    # College (20-minute halves, but PBP often uses 4 periods)
    "NCAA-MBB": 20 * 60,  # Half length
    "NCAA-WBB": 10 * 60,  # Quarter length (changed from halves)
    "NJCAA": 20 * 60,
    "NAIA": 20 * 60,
    "USPORTS": 20 * 60,
    "CCAA": 20 * 60,
    # Default
    "default": 10 * 60,
}


def add_game_seconds(
    df: pd.DataFrame,
    league: str,
    clock_column: str = "CLOCK",
    period_column: str = "PERIOD",
) -> pd.DataFrame:
    """Add GAME_SECONDS and PERIOD_SECONDS columns to PBP/shots DataFrame

    Converts clock time (MM:SS remaining) to elapsed seconds for easier filtering.

    Args:
        df: DataFrame with CLOCK and PERIOD columns
        league: League identifier for period length lookup
        clock_column: Name of clock column (MM:SS format)
        period_column: Name of period column

    Returns:
        DataFrame with PERIOD_SECONDS and GAME_SECONDS columns added
    """
    if df.empty or clock_column not in df.columns or period_column not in df.columns:
        return df

    df = df.copy()

    # Get period length for this league
    period_length = PERIOD_LENGTHS.get(league, PERIOD_LENGTHS["default"])

    # Parse clock to seconds remaining
    def parse_clock(clock_str: str) -> int:
        """Convert MM:SS to seconds"""
        if pd.isna(clock_str) or not clock_str:
            return 0
        try:
            parts = str(clock_str).split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(float(parts[1]))
            return int(float(clock_str))
        except (ValueError, TypeError):
            return 0

    # Calculate seconds elapsed in period
    secs_remaining = df[clock_column].apply(parse_clock)
    df["PERIOD_SECONDS"] = period_length - secs_remaining

    # Calculate total game seconds
    df["GAME_SECONDS"] = (df[period_column].astype(int) - 1) * period_length + df["PERIOD_SECONDS"]

    return df


def add_half_column(
    df: pd.DataFrame,
    period_column: str = "PERIOD",
) -> pd.DataFrame:
    """Add HALF column based on period (for college basketball)

    Maps periods 1-2 to half 1, periods 3-4 to half 2.

    Args:
        df: DataFrame with PERIOD column
        period_column: Name of period column

    Returns:
        DataFrame with HALF column added
    """
    if df.empty or period_column not in df.columns:
        return df

    df = df.copy()

    # NCAA uses 2 halves; if data has 4 periods, map to halves
    df["HALF"] = ((df[period_column].astype(int) - 1) // 2) + 1

    return df
