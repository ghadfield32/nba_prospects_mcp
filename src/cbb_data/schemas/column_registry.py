"""
Column Metadata Registry for Smart Auto-Pruning.

Defines which columns are "key" vs "supplementary" for each dataset, enabling
intelligent column pruning for token efficiency in compact mode.

Key Columns:
    - Essential for understanding the data (IDs, names, dates, primary stats)
    - Always included in compact mode
    - ~20-30% of total columns but contain ~80% of the value

Supplementary Columns:
    - Nice-to-have but not essential (advanced stats, percentages, rankings)
    - Excluded in compact mode
    - Can be fetched with full mode if needed

Usage:
    from cbb_data.schemas.column_registry import COLUMN_METADATA, get_key_columns

    # Get key columns for a dataset
    key_cols = get_key_columns("player_game")
    pruned_df = df[key_cols]

    # Check if a column is a key column
    is_key = is_key_column("player_game", "PTS")  # True
    is_key = is_key_column("player_game", "OFFENSIVE_RATING")  # False
"""

from __future__ import annotations

import pandas as pd

# ============================================================================
# Column Metadata by Dataset
# ============================================================================

COLUMN_METADATA: dict[str, dict[str, list[str]]] = {
    # ========================================================================
    # Schedule Dataset
    # ========================================================================
    "schedule": {
        "key_columns": [
            # Identifiers
            "GAME_ID",
            "SEASON",
            "SEASON_TYPE",
            "GAME_DATE",
            # Teams
            "HOME_TEAM",
            "HOME_TEAM_ID",
            "AWAY_TEAM",
            "AWAY_TEAM_ID",
            # Scores
            "HOME_SCORE",
            "AWAY_SCORE",
            "STATUS",
            # Location
            "VENUE",
            "CITY",
        ],
        "supplementary_columns": [
            # Advanced metadata
            "BROADCAST",
            "ATTENDANCE",
            "NEUTRAL_SITE",
            "CONFERENCE_GAME",
            "TOURNAMENT",
            # Detailed location
            "STATE",
            "COUNTRY",
            # Rankings (if present)
            "HOME_RANK",
            "AWAY_RANK",
        ],
    },
    # ========================================================================
    # Player Game Stats
    # ========================================================================
    "player_game": {
        "key_columns": [
            # Identifiers
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            "TEAM_ABBREVIATION",
            "GAME_ID",
            "GAME_DATE",
            # Core stats
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            # Context
            "HOME_AWAY",
            "WL",
        ],
        "supplementary_columns": [
            # Advanced stats
            "PLUS_MINUS",
            "OFFENSIVE_RATING",
            "DEFENSIVE_RATING",
            "NET_RATING",
            "TS_PCT",
            "EFG_PCT",
            "USG_PCT",
            # Detailed breakdowns
            "OREB",
            "DREB",
            "PF",
            "POSS",
            # Shooting zones
            "FG2M",
            "FG2A",
            "FG2_PCT",
        ],
    },
    # ========================================================================
    # Team Game Stats
    # ========================================================================
    "team_game": {
        "key_columns": [
            # Identifiers
            "TEAM_ID",
            "TEAM_NAME",
            "TEAM_ABBREVIATION",
            "GAME_ID",
            "GAME_DATE",
            # Scores
            "PTS",
            "OPP_PTS",
            "WL",
            # Core stats
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "REB",
            "AST",
            "TOV",
            # Context
            "HOME_AWAY",
        ],
        "supplementary_columns": [
            # Advanced stats
            "OFFENSIVE_RATING",
            "DEFENSIVE_RATING",
            "NET_RATING",
            "PACE",
            "EFG_PCT",
            "TS_PCT",
            # Detailed breakdowns
            "OREB",
            "DREB",
            "STL",
            "BLK",
            "PF",
            # Four factors
            "FOUR_FACTORS_EFG",
            "FOUR_FACTORS_TOV",
            "FOUR_FACTORS_OREB",
            "FOUR_FACTORS_FT_RATE",
        ],
    },
    # ========================================================================
    # Play-by-Play
    # ========================================================================
    "play_by_play": {
        "key_columns": [
            # Identifiers
            "GAME_ID",
            "EVENT_NUM",
            # Time
            "PERIOD",
            "CLOCK",
            "TIME_REMAINING",
            # Event details
            "EVENT_TYPE",
            "DESCRIPTION",
            # Score
            "HOME_SCORE",
            "AWAY_SCORE",
            "SCORE_MARGIN",
            # Players/Teams
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
        ],
        "supplementary_columns": [
            # Advanced event details
            "SHOT_DISTANCE",
            "SHOT_ZONE",
            "SHOT_MADE",
            "ASSIST_PLAYER_ID",
            "ASSIST_PLAYER_NAME",
            # Win probability (if present)
            "WIN_PROBABILITY",
            "WP_DELTA",
            # Coordinates (if present)
            "LOC_X",
            "LOC_Y",
        ],
    },
    # ========================================================================
    # Shot Chart
    # ========================================================================
    "shot_chart": {
        "key_columns": [
            # Identifiers
            "GAME_ID",
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            # Shot details
            "SHOT_MADE",
            "SHOT_TYPE",
            "SHOT_DISTANCE",
            "SHOT_VALUE",
            # Time
            "PERIOD",
            "MINUTES_REMAINING",
            "SECONDS_REMAINING",
        ],
        "supplementary_columns": [
            # Shot zones
            "SHOT_ZONE_BASIC",
            "SHOT_ZONE_AREA",
            "SHOT_ZONE_RANGE",
            # Coordinates
            "LOC_X",
            "LOC_Y",
            # Context
            "SHOT_ATTEMPTED_FLAG",
            "SHOT_DISTANCE_FEET",
        ],
    },
    # ========================================================================
    # Player Season Aggregates
    # ========================================================================
    "player_season": {
        "key_columns": [
            # Identifiers
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            "TEAM_ABBREVIATION",
            "SEASON",
            # Games played
            "GP",
            "GS",
            "MIN",
            # Per-game stats
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            # Shooting
            "FG_PCT",
            "FG3_PCT",
            "FT_PCT",
        ],
        "supplementary_columns": [
            # Totals
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            # Advanced stats
            "OFFENSIVE_RATING",
            "DEFENSIVE_RATING",
            "NET_RATING",
            "TS_PCT",
            "EFG_PCT",
            "USG_PCT",
            "PER",
            # Detailed
            "OREB",
            "DREB",
            "PF",
        ],
    },
    # ========================================================================
    # Team Season Aggregates
    # ========================================================================
    "team_season": {
        "key_columns": [
            # Identifiers
            "TEAM_ID",
            "TEAM_NAME",
            "TEAM_ABBREVIATION",
            "SEASON",
            # Record
            "WINS",
            "LOSSES",
            "WIN_PCT",
            # Per-game stats
            "PTS",
            "OPP_PTS",
            "POINT_DIFF",
            # Core stats
            "FG_PCT",
            "FG3_PCT",
            "FT_PCT",
            "REB",
            "AST",
            "TOV",
        ],
        "supplementary_columns": [
            # Advanced stats
            "OFFENSIVE_RATING",
            "DEFENSIVE_RATING",
            "NET_RATING",
            "PACE",
            "EFG_PCT",
            "TS_PCT",
            # Detailed
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            "OREB",
            "DREB",
            "STL",
            "BLK",
            "PF",
        ],
    },
    # ========================================================================
    # Box Score (Combined)
    # ========================================================================
    "box_score": {
        "key_columns": [
            # Identifiers
            "GAME_ID",
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            "TEAM_ABBREVIATION",
            # Core stats
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "FG_PCT",
            "FG3_PCT",
            "FT_PCT",
        ],
        "supplementary_columns": [
            # Shooting details
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            # Advanced
            "PLUS_MINUS",
            "OFFENSIVE_RATING",
            "DEFENSIVE_RATING",
            "OREB",
            "DREB",
            "TOV",
            "PF",
        ],
    },
}


# ============================================================================
# Helper Functions
# ============================================================================


def get_key_columns(dataset_id: str) -> list[str]:
    """
    Get key columns for a dataset.

    Args:
        dataset_id: Dataset identifier

    Returns:
        List of key column names

    Examples:
        >>> get_key_columns("player_game")
        ['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', ...]

        >>> get_key_columns("unknown_dataset")
        []  # Returns empty if not found
    """
    if dataset_id not in COLUMN_METADATA:
        return []
    return COLUMN_METADATA[dataset_id].get("key_columns", [])


def get_supplementary_columns(dataset_id: str) -> list[str]:
    """
    Get supplementary (non-key) columns for a dataset.

    Args:
        dataset_id: Dataset identifier

    Returns:
        List of supplementary column names
    """
    if dataset_id not in COLUMN_METADATA:
        return []
    return COLUMN_METADATA[dataset_id].get("supplementary_columns", [])


def is_key_column(dataset_id: str, column_name: str) -> bool:
    """
    Check if a column is a key column for a dataset.

    Args:
        dataset_id: Dataset identifier
        column_name: Column name to check

    Returns:
        True if column is a key column, False otherwise

    Examples:
        >>> is_key_column("player_game", "PTS")
        True

        >>> is_key_column("player_game", "OFFENSIVE_RATING")
        False
    """
    key_cols = get_key_columns(dataset_id)
    return column_name in key_cols


def get_all_columns(dataset_id: str) -> list[str]:
    """
    Get all columns (key + supplementary) for a dataset.

    Args:
        dataset_id: Dataset identifier

    Returns:
        List of all column names
    """
    if dataset_id not in COLUMN_METADATA:
        return []
    return COLUMN_METADATA[dataset_id].get("key_columns", []) + COLUMN_METADATA[dataset_id].get(
        "supplementary_columns", []
    )


def filter_to_key_columns(df: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    """
    Filter DataFrame to key columns only.

    Args:
        df: pandas DataFrame
        dataset_id: Dataset identifier

    Returns:
        DataFrame with only key columns (that exist in df)

    Examples:
        >>> df = pd.DataFrame({"PTS": [20], "OFFENSIVE_RATING": [110]})
        >>> filtered = filter_to_key_columns(df, "player_game")
        >>> list(filtered.columns)
        ['PTS']  # OFFENSIVE_RATING excluded
    """

    if df.empty:
        return df

    key_cols = get_key_columns(dataset_id)

    # Filter to columns that exist in both df and key_cols
    cols_to_keep = [c for c in df.columns if c in key_cols]

    if not cols_to_keep:
        # No key columns found - return first N columns as fallback
        return df.iloc[:, :10]

    return df[cols_to_keep]


def get_column_importance(dataset_id: str) -> dict[str, int]:
    """
    Get column importance scores (key=1, supplementary=0).

    Useful for sorting or prioritization.

    Args:
        dataset_id: Dataset identifier

    Returns:
        Dict mapping column name to importance score

    Examples:
        >>> importance = get_column_importance("player_game")
        >>> importance["PTS"]
        1
        >>> importance["OFFENSIVE_RATING"]
        0
    """
    importance = {}

    # Key columns get score 1
    for col in get_key_columns(dataset_id):
        importance[col] = 1

    # Supplementary columns get score 0
    for col in get_supplementary_columns(dataset_id):
        importance[col] = 0

    return importance


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "COLUMN_METADATA",
    "get_key_columns",
    "get_supplementary_columns",
    "is_key_column",
    "get_all_columns",
    "filter_to_key_columns",
    "get_column_importance",
]
