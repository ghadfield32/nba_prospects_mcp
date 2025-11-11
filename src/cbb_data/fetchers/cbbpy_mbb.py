"""CBBpy NCAA Men's Basketball Fetcher

CBBpy web scraper wrapper with built-in team total filtering.
Primary data source for NCAA basketball (replaces buggy PBP parser).

Key Features:
- Box scores with 100% accuracy (when filtered correctly)
- Play-by-play with shot location data (x, y coordinates)
- Team schedules
- Automatic team total row filtering (player_id != 'TOTAL')
- Schema transformation to unified 33-column format

Source: https://github.com/dcstats/cbbpy
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Try to import cbbpy
try:
    import cbbpy.mens_scraper as cbb

    CBBPY_AVAILABLE = True
except ImportError:
    CBBPY_AVAILABLE = False
    logger.warning("cbbpy not installed. Install with: uv pip install cbbpy")


def _check_cbbpy_available() -> None:
    """Check if CBBpy is available"""
    if not CBBPY_AVAILABLE:
        raise ImportError("cbbpy not installed. " "Install with: uv pip install cbbpy")


def _filter_team_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    CRITICAL: Remove team summary rows before any aggregation.

    CBBpy includes rows with player_id='TOTAL' that contain team-level
    summaries. These must be filtered to avoid double-counting.

    Example issue:
        Without filtering: 264 total points (132 players + 132 team totals)
        With filtering: 132 total points (correct)

    Args:
        df: CBBpy DataFrame with potential team total rows

    Returns:
        DataFrame with only individual player rows
    """
    if df.empty:
        return df

    if "player_id" not in df.columns:
        logger.warning("No player_id column found - cannot filter team totals")
        return df

    before_count = len(df)
    filtered = df[df["player_id"] != "TOTAL"].copy()
    after_count = len(filtered)

    removed = before_count - after_count
    if removed > 0:
        logger.debug(f"Filtered {removed} team total rows")

    return filtered


def transform_cbbpy_to_unified(
    df: pd.DataFrame, season: int, league: str = "NCAA-MBB"
) -> pd.DataFrame:
    """
    Transform CBBpy box score (27 columns) to unified schema (33 columns).

    Maps CBBpy column names to match EuroLeague schema for consistency.
    Adds missing columns as NaN, calculates derived stats.

    Args:
        df: CBBpy box score DataFrame (already filtered of team totals)
        season: Season year (e.g., 2025)
        league: League identifier (default 'NCAA-MBB')

    Returns:
        DataFrame with unified 33-column schema matching EuroLeague

    Schema:
        ['SEASON', 'GAME_CODE', 'Home', 'PLAYER_ID', 'STARTER', 'IsPlaying',
         'TEAM', 'Dorsal', 'PLAYER_NAME', 'MIN', 'PTS', 'FG2M', 'FG2A',
         'FG3M', 'FG3A', 'FTM', 'FTA', 'OREB', 'DREB', 'REB', 'AST', 'STL',
         'TOV', 'BLK', 'BLK_AGAINST', 'PF', 'PF_DRAWN', 'VALUATION',
         'PLUS_MINUS', 'LEAGUE', 'FGM', 'FGA', 'FG_PCT']
    """
    if df.empty:
        return pd.DataFrame()

    # Column mapping: CBBpy → Unified
    column_map = {
        "game_id": "GAME_CODE",
        "team": "TEAM",
        "player": "PLAYER_NAME",
        "player_id": "PLAYER_ID",
        "starter": "STARTER",
        "min": "MIN",
        "pts": "PTS",
        "fgm": "FGM",
        "fga": "FGA",
        "2pm": "FG2M",
        "2pa": "FG2A",
        "3pm": "FG3M",
        "3pa": "FG3A",
        "ftm": "FTM",
        "fta": "FTA",
        "oreb": "OREB",
        "dreb": "DREB",
        "reb": "REB",
        "ast": "AST",
        "stl": "STL",
        "blk": "BLK",
        "to": "TOV",
        "pf": "PF",
        "fg%": "FG_PCT",
    }

    # Rename columns
    out = df.rename(columns=column_map)

    # Add metadata columns
    out["SEASON"] = season
    out["LEAGUE"] = league
    out["SOURCE"] = "cbbpy"

    # Add GAME_ID as alias for GAME_CODE (for compatibility with aggregation functions)
    if "GAME_CODE" in out.columns:
        out["GAME_ID"] = out["GAME_CODE"]

    # Add missing columns (not available in CBBpy)
    missing_columns = {
        "Home": 0,  # Not available
        "IsPlaying": 1,  # Assume all are playing
        "Dorsal": pd.NA,  # Jersey number not available
        "BLK_AGAINST": 0,  # Blocks against not available
        "PF_DRAWN": 0,  # Fouls drawn not available
        "VALUATION": 0,  # EuroLeague-specific stat
        "PLUS_MINUS": 0,  # +/- not available
    }

    for col, default_value in missing_columns.items():
        if col not in out.columns:
            out[col] = default_value

    # Calculate derived percentages if missing
    if "FG3_PCT" not in out.columns:
        out["FG3_PCT"] = np.where(out["FG3A"] > 0, out["FG3M"] / out["FG3A"], 0.0)

    if "FT_PCT" not in out.columns:
        out["FT_PCT"] = np.where(out["FTA"] > 0, out["FTM"] / out["FTA"], 0.0)

    # Ensure STARTER is boolean
    if "STARTER" in out.columns:
        out["STARTER"] = out["STARTER"].astype(bool)

    # Define canonical column order (matching EuroLeague)
    canonical_columns = [
        "SEASON",
        "GAME_CODE",
        "Home",
        "PLAYER_ID",
        "STARTER",
        "IsPlaying",
        "TEAM",
        "Dorsal",
        "PLAYER_NAME",
        "MIN",
        "PTS",
        "FG2M",
        "FG2A",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "STL",
        "TOV",
        "BLK",
        "BLK_AGAINST",
        "PF",
        "PF_DRAWN",
        "VALUATION",
        "PLUS_MINUS",
        "LEAGUE",
        "FGM",
        "FGA",
        "FG_PCT",
    ]

    # Add SOURCE and GAME_ID columns to canonical order
    canonical_columns.append("SOURCE")
    canonical_columns.append("GAME_ID")  # Add for compatibility with aggregation functions

    # Ensure all columns exist
    for col in canonical_columns:
        if col not in out.columns:
            out[col] = 0 if col not in ["PLAYER_NAME", "TEAM", "LEAGUE", "SOURCE"] else ""

    # Return in canonical order
    return out[canonical_columns]


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_cbbpy_box_score(game_id: str, season: int) -> pd.DataFrame:
    """
    Fetch box score for a single NCAA game.

    Automatically filters team total rows and transforms to unified schema.

    Args:
        game_id: ESPN game ID (e.g., '401824809')
        season: Season year (e.g., 2025)

    Returns:
        DataFrame with player box scores (33 columns, unified schema)

    Example:
        >>> df = fetch_cbbpy_box_score('401824809', 2025)
        >>> print(len(df))  # 22 players (not 24 - team totals filtered)
        >>> print(df['PTS'].sum())  # 132 (not 264 - no double counting)
    """
    _check_cbbpy_available()

    logger.info(f"Fetching CBBpy box score: game_id={game_id}, season={season}")

    # Fetch from CBBpy
    try:
        raw_box = cbb.get_game_boxscore(game_id)
    except Exception as e:
        logger.error(f"CBBpy fetch failed for game {game_id}: {e}")
        raise

    if raw_box.empty:
        logger.warning(f"Empty box score for game {game_id}")
        return pd.DataFrame()

    # CRITICAL: Filter team totals BEFORE any processing
    filtered_box = _filter_team_totals(raw_box)

    if filtered_box.empty:
        logger.warning(f"No individual players found for game {game_id} after filtering")
        return pd.DataFrame()

    # Transform to unified schema
    unified_box = transform_cbbpy_to_unified(filtered_box, season)

    logger.info(f"Fetched {len(unified_box)} player box scores for game {game_id}")

    return unified_box


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_cbbpy_pbp(game_id: str) -> pd.DataFrame:
    """
    Fetch play-by-play data with shot locations.

    CBBpy PBP includes shot coordinates (x, y) that ESPN API doesn't have.

    Args:
        game_id: ESPN game ID

    Returns:
        DataFrame with 19 columns including shot_x, shot_y

    Columns:
        ['game_id', 'home_team', 'away_team', 'play_desc', 'home_score',
         'away_score', 'half', 'secs_left_half', 'secs_left_reg', 'play_team',
         'play_type', 'shooting_play', 'scoring_play', 'is_three', 'shooter',
         'is_assisted', 'assist_player', 'shot_x', 'shot_y']
    """
    _check_cbbpy_available()

    logger.info(f"Fetching CBBpy PBP: game_id={game_id}")

    try:
        pbp = cbb.get_game_pbp(game_id)
    except Exception as e:
        logger.error(f"CBBpy PBP fetch failed for game {game_id}: {e}")
        raise

    if pbp.empty:
        logger.warning(f"Empty PBP for game {game_id}")
        return pd.DataFrame()

    logger.info(f"Fetched {len(pbp)} PBP events for game {game_id}")

    return pbp


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_cbbpy_schedule(team: str, season: int) -> pd.DataFrame:
    """
    Fetch team schedule for a season.

    Args:
        team: Team name (e.g., 'Houston', 'UConn')
        season: Season year as integer (e.g., 2025 for 2024-25 season)

    Returns:
        DataFrame with team schedule

    Columns:
        ['team', 'team_id', 'season', 'game_id', 'game_day', 'game_time',
         'opponent', 'opponent_id', 'season_type', 'game_status', ...]
    """
    _check_cbbpy_available()

    logger.info(f"Fetching CBBpy schedule: team={team}, season={season}")

    try:
        schedule = cbb.get_team_schedule(team=team, season=season)
    except Exception as e:
        logger.error(f"CBBpy schedule fetch failed for {team} ({season}): {e}")
        raise

    if schedule.empty:
        logger.warning(f"Empty schedule for {team} in {season}")
        return pd.DataFrame()

    logger.info(f"Fetched {len(schedule)} games for {team} in {season}")

    return schedule


# Convenience function for getting shots from PBP
def extract_shots_from_pbp(pbp_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract shot chart data from PBP DataFrame.

    Filters to shooting plays with valid coordinates.

    Args:
        pbp_df: PBP DataFrame from fetch_cbbpy_pbp()

    Returns:
        DataFrame with shot data (subset of PBP with coordinates)
    """
    if pbp_df.empty:
        return pd.DataFrame()

    # Filter to shooting plays with coordinates
    shots = pbp_df[
        (pbp_df["shooting_play"] == True)  # noqa: E712
        & (pbp_df["shot_x"].notna())
        & (pbp_df["shot_y"].notna())
    ].copy()

    logger.debug(f"Extracted {len(shots)} shots with coordinates from {len(pbp_df)} PBP events")

    return shots
