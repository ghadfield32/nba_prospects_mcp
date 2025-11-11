"""
CBBpy Women's Basketball Fetcher Module
========================================

Fetches NCAA Women's Basketball data using the cbbpy.womens_scraper library.

This module provides WBB player box scores that ESPN API doesn't offer.
ESPN WBB API only provides schedule and play-by-play data, but CBBpy fills
the gap by scraping player box scores from the web.

Key Features:
- Player box scores (ESPN doesn't provide this for WBB)
- Play-by-play with shot coordinates
- Team schedules
- Automatic team totals filtering (prevents double-counting)
- Unified 33-column schema transformation

Usage:
    from cbb_data.fetchers.cbbpy_wbb import fetch_cbbpy_wbb_box_score

    df = fetch_cbbpy_wbb_box_score('401811123', 2025)
    # Returns 26 player records with unified schema

Dependencies:
    pip install cbbpy

Author: cbb-data
Date: 2025-11-05
"""

import logging

import numpy as np
import pandas as pd

from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Try importing CBBpy womens_scraper
try:
    import cbbpy.womens_scraper as wbb

    CBBPY_AVAILABLE = True
except ImportError:
    CBBPY_AVAILABLE = False
    logger.warning("cbbpy not installed. Install with: uv pip install cbbpy")


def _check_cbbpy_available() -> None:
    """Raise ImportError if cbbpy is not available."""
    if not CBBPY_AVAILABLE:
        raise ImportError("cbbpy library required for WBB data. Install with: uv pip install cbbpy")


def _filter_team_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove team summary rows (player_id='TOTAL') before aggregation.

    CBBpy includes team total rows that must be filtered before:
    - Aggregating stats (to avoid double-counting)
    - Calculating season totals (TOTAL rows would inflate numbers)

    Args:
        df: Raw CBBpy box score with possible TOTAL rows

    Returns:
        Filtered DataFrame with only individual player records

    Example:
        Raw:    22 players + 2 team TOTAL rows = 24 rows
        Filtered: 22 individual players only
    """
    if "player_id" not in df.columns:
        return df

    filtered = df[df["player_id"] != "TOTAL"].copy()

    if len(filtered) < len(df):
        logger.debug(f"Filtered {len(df) - len(filtered)} team TOTAL rows")

    return filtered


def transform_cbbpy_wbb_to_unified(
    df: pd.DataFrame, season: int, league: str = "NCAA-WBB"
) -> pd.DataFrame:
    """
    Transform CBBpy WBB box score (27 columns) to unified schema (33 columns).

    Handles column mapping, missing columns, and derived calculations.

    Args:
        df: Raw CBBpy box score (27 columns)
        season: Season year (e.g., 2025)
        league: League identifier (default: 'NCAA-WBB')

    Returns:
        Unified schema DataFrame (33 columns)

    Output Schema (33 columns):
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
def fetch_cbbpy_wbb_box_score(game_id: str, season: int) -> pd.DataFrame:
    """
    Fetch box score for a single NCAA Women's Basketball game.

    Automatically filters team total rows and transforms to unified schema.

    Args:
        game_id: ESPN game ID (e.g., '401811123')
        season: Season year (e.g., 2025)

    Returns:
        DataFrame with player box scores (33 columns, unified schema)

    Example:
        >>> df = fetch_cbbpy_wbb_box_score('401811123', 2025)
        >>> print(len(df))  # 26 players (not 28 - team totals filtered)
        >>> print(df['PTS'].sum())  # 128 (not 256 - no double counting)
    """
    _check_cbbpy_available()

    logger.info(f"Fetching CBBpy WBB box score: game_id={game_id}, season={season}")

    # Fetch from CBBpy
    try:
        raw_box = wbb.get_game_boxscore(game_id)
    except Exception as e:
        logger.error(f"CBBpy WBB fetch failed for game {game_id}: {e}")
        raise

    if raw_box.empty:
        logger.warning(f"Empty WBB box score for game {game_id}")
        return pd.DataFrame()

    # CRITICAL: Filter team totals BEFORE any processing
    filtered_box = _filter_team_totals(raw_box)

    if filtered_box.empty:
        logger.warning(f"No individual players found for WBB game {game_id} after filtering")
        return pd.DataFrame()

    # Transform to unified schema
    unified_box = transform_cbbpy_wbb_to_unified(filtered_box, season)

    logger.info(f"Fetched {len(unified_box)} WBB player box scores for game {game_id}")

    return unified_box


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_cbbpy_wbb_pbp(game_id: str) -> pd.DataFrame:
    """
    Fetch play-by-play data with shot locations for WBB.

    CBBpy WBB PBP includes shot coordinates (x, y) that ESPN API doesn't have.

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

    logger.info(f"Fetching CBBpy WBB PBP: game_id={game_id}")

    try:
        pbp = wbb.get_game_pbp(game_id)
    except Exception as e:
        logger.error(f"CBBpy WBB PBP fetch failed for game {game_id}: {e}")
        raise

    if pbp.empty:
        logger.warning(f"Empty WBB PBP for game {game_id}")
        return pd.DataFrame()

    logger.info(f"Fetched {len(pbp)} WBB PBP events for game {game_id}")

    return pbp


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_cbbpy_wbb_schedule(team: str, season: int) -> pd.DataFrame:
    """
    Fetch WBB team schedule for a season.

    Args:
        team: Team name (e.g., 'UConn', 'South Carolina')
        season: Season year as integer (e.g., 2025 for 2024-25 season)

    Returns:
        DataFrame with team schedule

    Columns:
        ['team', 'team_id', 'season', 'game_id', 'game_day', 'game_time',
         'opponent', 'opponent_id', 'season_type', 'game_status', ...]
    """
    _check_cbbpy_available()

    logger.info(f"Fetching CBBpy WBB schedule: team={team}, season={season}")

    try:
        schedule = wbb.get_team_schedule(team=team, season=season)
    except Exception as e:
        logger.error(f"CBBpy WBB schedule fetch failed for {team} ({season}): {e}")
        raise

    if schedule.empty:
        logger.warning(f"Empty WBB schedule for {team} in {season}")
        return pd.DataFrame()

    logger.info(f"Fetched {len(schedule)} WBB games for {team} in {season}")

    return schedule


# Convenience function for getting shots from PBP
def extract_shots_from_wbb_pbp(pbp_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract shot chart data from WBB PBP DataFrame.

    Filters to shooting plays with valid coordinates.

    Args:
        pbp_df: PBP DataFrame from fetch_cbbpy_wbb_pbp()

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

    logger.debug(f"Extracted {len(shots)} WBB shots with coordinates from {len(pbp_df)} PBP events")

    return shots
