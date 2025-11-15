"""LNB Pro A Official Data via Parquet Files

This module provides access to LNB Pro A (France) statistics via Parquet files.
Follows the same pattern as NBL official data integration.

Data Source: Parquet files exported from Calendar API and game data sources
- Export Script: tools/lnb/export_lnb.py
- Data Directory: data/lnb_raw/
- Maintained by: Custom export process

Data Coverage:
- **Fixtures**: All available games (current: 2025-26 season)
- **Play-by-play**: Event-level data (~3,336 events for 8 games)
- **Shot locations**: (x, y) coordinates (~973 shots for 8 games)
- **Box scores**: Player and team stats (derived from games)

Architecture:
1. Python export script (tools/lnb/export_lnb.py) exports Parquet files
2. This Python module loads Parquet files and normalizes to cbb_data schema
3. Data flows into DuckDB for caching and querying

Usage:
    # Option A: Load pre-exported data
    from cbb_data.fetchers.lnb_official import load_lnb_table
    fixtures_df = load_lnb_table("lnb_fixtures")

    # Option B: High-level API (recommended)
    from cbb_data.api.datasets import get_dataset
    df = get_dataset("schedule", filters={"league": "LNB_PROA", "season": "2025-26"}, pre_only=False)

Prerequisites:
    1. Python 3.8+ with pandas and pyarrow
    2. Run export: python tools/lnb/export_lnb.py --sample
    3. Verify data: ls data/lnb_raw/

See Also:
    - tools/lnb/README.md - Setup and usage guide
    - tools/lnb/export_lnb.py - Python export script
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import pandas as pd

from ..storage.duckdb_storage import get_storage
from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# Default export directory (matches export script default)
DEFAULT_EXPORT_DIR = Path("data/lnb_raw")

# Available tables from LNB export
LNB_TABLES = [
    "lnb_fixtures",  # Game schedule/results
    "lnb_box_player",  # Player box scores (future)
    "lnb_box_team",  # Team box scores (future)
    "lnb_pbp_events",  # Play-by-play events
    "lnb_shots",  # Shot locations with x,y
]

LNBTableType = Literal["lnb_fixtures", "lnb_box_player", "lnb_box_team", "lnb_pbp_events", "lnb_shots"]


# ==============================================================================
# Data Loading
# ==============================================================================


def load_lnb_table(
    table: LNBTableType,
    export_dir: Path | None = None,
) -> pd.DataFrame:
    """Load LNB table from Parquet file

    Args:
        table: Table name to load (lnb_fixtures, lnb_pbp_events, lnb_shots, etc.)
        export_dir: Directory containing Parquet files (default: data/lnb_raw)

    Returns:
        DataFrame with table data

    Raises:
        FileNotFoundError: If Parquet file not found (run export script first)

    Example:
        >>> fixtures = load_lnb_table("lnb_fixtures")
        >>> print(f"Loaded {len(fixtures)} games")
        Loaded 8 games
    """
    if export_dir is None:
        export_dir = DEFAULT_EXPORT_DIR

    file_path = export_dir / f"{table}.parquet"

    if not file_path.exists():
        raise FileNotFoundError(
            f"LNB data file not found: {file_path}\n\n"
            "Run export first:\n"
            "  python tools/lnb/export_lnb.py --sample\n"
            "Or from Python:\n"
            "  from cbb_data.fetchers.lnb_official import run_lnb_export\n"
            "  run_lnb_export()"
        )

    logger.info(f"Loading LNB table: {table} from {file_path}")

    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded {len(df)} rows from {table}")
        return df

    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        raise


# ==============================================================================
# Helper Functions for Empty DataFrames
# ==============================================================================


def _empty_schedule_df() -> pd.DataFrame:
    """Return empty schedule DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "SEASON",
            "GAME_DATE",
            "HOME_TEAM",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
            "VENUE",
            "LEAGUE",
            "COMPETITION",
        ]
    )


def _empty_player_season_df() -> pd.DataFrame:
    """Return empty player_season DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "PLAYER_NAME",
            "TEAM",
            "GP",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "FG_PCT",
            "FG3_PCT",
            "FT_PCT",
            "LEAGUE",
            "SEASON",
            "COMPETITION",
        ]
    )


def _empty_team_season_df() -> pd.DataFrame:
    """Return empty team_season DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "TEAM",
            "GP",
            "W",
            "L",
            "WIN_PCT",
            "PTS",
            "OPP_PTS",
            "PTS_DIFF",
            "LEAGUE",
            "SEASON",
            "COMPETITION",
        ]
    )


def _empty_player_game_df() -> pd.DataFrame:
    """Return empty player_game DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_NAME",
            "TEAM",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "FG_PCT",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_team_game_df() -> pd.DataFrame:
    """Return empty team_game DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "TEAM",
            "OPP_TEAM",
            "PTS",
            "OPP_PTS",
            "FG_PCT",
            "FG3_PCT",
            "FT_PCT",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_pbp_df() -> pd.DataFrame:
    """Return empty pbp DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "EVENT_NUM",
            "PERIOD",
            "CLOCK",
            "TEAM",
            "PLAYER_NAME",
            "EVENT_TYPE",
            "DESCRIPTION",
            "HOME_SCORE",
            "AWAY_SCORE",
            "LEAGUE",
            "COMPETITION",
        ]
    )


def _empty_shots_df() -> pd.DataFrame:
    """Return empty shots DataFrame with correct schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "SHOT_NUM",
            "PERIOD",
            "CLOCK",
            "TEAM",
            "PLAYER_NAME",
            "SHOT_TYPE",
            "SHOT_MADE",
            "SHOT_X",
            "SHOT_Y",
            "DISTANCE",
            "LEAGUE",
            "COMPETITION",
        ]
    )


# ==============================================================================
# Normalized Fetchers (cbb_data schema)
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_schedule(season: str = "2025-26", season_type: str = "Regular Season") -> pd.DataFrame:
    """Fetch LNB Pro A schedule from fixtures data

    Args:
        season: Season year as string (e.g., "2025-26" or "2025")
        season_type: "Regular Season" or "Playoffs" (filters applied)

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: Unique game identifier
        - SEASON: Season string
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score
        - AWAY_SCORE: Away team final score
        - VENUE: Arena name
        - LEAGUE: "LNB_PROA"
        - COMPETITION: "LNB Pro A"

    Example:
        >>> df = fetch_lnb_schedule("2025-26")
        >>> print(f"{len(df)} games found")
        8 games found
    """
    logger.info(f"Fetching LNB schedule: {season}, {season_type}")

    try:
        # Load fixtures from export
        df = load_lnb_table("lnb_fixtures")

        if df.empty:
            logger.warning("No LNB fixtures data found")
            return _empty_schedule_df()

        # Filter by season (handle multiple formats)
        season_variants = [
            season,  # e.g., "2025-26"
            season.split("-")[0] if "-" in season else season,  # e.g., "2025"
            f"{season}-{str(int(season) + 1)[-2:]}" if "-" not in season else season,  # e.g., "2025" → "2025-26"
        ]
        df = df[df["season"].isin(season_variants)]

        if df.empty:
            logger.warning(f"No games found for season {season}")
            return _empty_schedule_df()

        # Normalize column names to cbb_data schema
        df = df.rename(
            columns={
                "game_id": "GAME_ID",
                "season": "SEASON",
                "game_date": "GAME_DATE",
                "home_team": "HOME_TEAM",
                "away_team": "AWAY_TEAM",
                "home_score": "HOME_SCORE",
                "away_score": "AWAY_SCORE",
                "venue": "VENUE",
                "league": "LEAGUE",
                "competition": "COMPETITION",
            }
        )

        # Convert GAME_ID to string for consistency with API expectations
        if "GAME_ID" in df.columns:
            df["GAME_ID"] = df["GAME_ID"].astype(str)

        # Ensure required columns exist
        if "LEAGUE" not in df.columns:
            df["LEAGUE"] = "LNB_PROA"
        if "COMPETITION" not in df.columns:
            df["COMPETITION"] = "LNB Pro A"

        logger.info(f"Fetched {len(df)} LNB games for {season}")
        # Return a copy to avoid mutating cached DataFrame
        return df.copy()

    except FileNotFoundError as e:
        logger.error(str(e))
        logger.info("Returning empty DataFrame. Run export script first.")
        return _empty_schedule_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB schedule: {e}")
        return _empty_schedule_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_season(season: str = "2025-26", per_mode: str = "Totals") -> pd.DataFrame:
    """Fetch LNB Pro A player season statistics

    Aggregates from player box scores (when available).
    Currently returns placeholder data until box_player data is exported.

    Args:
        season: Season year as string
        per_mode: "Totals" or "PerGame"

    Returns:
        DataFrame with player season statistics

    Columns:
        - PLAYER_NAME: Player full name
        - TEAM: Team name
        - GP: Games played
        - MIN: Minutes played
        - PTS: Points
        - REB: Total rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - FG_PCT: Field goal percentage
        - FG3_PCT: Three-point percentage
        - FT_PCT: Free throw percentage
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - COMPETITION: "LNB Pro A"
    """
    logger.info(f"Fetching LNB player season stats: {season}, {per_mode}")

    try:
        # Load box_player data (when available)
        df = load_lnb_table("lnb_box_player")

        if df.empty:
            logger.warning("No LNB box_player data found (will aggregate from PBP in future)")
            return _empty_player_season_df()

        # Filter by season
        df = df[df["season"] == season]

        if df.empty:
            logger.warning(f"No player data found for season {season}")
            return _empty_player_season_df()

        # Group by player and aggregate
        # TODO: Implement aggregation logic when box_player data available

        logger.info(f"Fetched {len(df)} LNB players for {season}")
        return df

    except FileNotFoundError:
        logger.warning("LNB box_player data not available yet")
        return _empty_player_season_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB player season stats: {e}")
        return _empty_player_season_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_team_season(season: str = "2025-26", per_mode: str = "Totals") -> pd.DataFrame:
    """Fetch LNB Pro A team season statistics

    Aggregates from team box scores or fixtures.

    Args:
        season: Season year as string
        per_mode: "Totals" or "PerGame"

    Returns:
        DataFrame with team season statistics

    Columns:
        - TEAM: Team name
        - GP: Games played
        - W: Wins
        - L: Losses
        - WIN_PCT: Win percentage
        - PTS: Points
        - OPP_PTS: Opponent points
        - PTS_DIFF: Point differential
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - COMPETITION: "LNB Pro A"
    """
    logger.info(f"Fetching LNB team season stats: {season}, {per_mode}")

    try:
        # Load fixtures and aggregate
        fixtures = load_lnb_table("lnb_fixtures")

        if fixtures.empty:
            logger.warning("No LNB fixtures data found")
            return _empty_team_season_df()

        # Filter by season
        season_variants = [
            season,
            season.split("-")[0] if "-" in season else season,
            f"{season}-{str(int(season) + 1)[-2:]}" if "-" not in season else season,
        ]
        fixtures = fixtures[fixtures["season"].isin(season_variants)]

        if fixtures.empty:
            logger.warning(f"No games found for season {season}")
            return _empty_team_season_df()

        # Aggregate team stats
        teams_home = fixtures.groupby("home_team").agg({
            "game_id": "count",
            "home_score": "sum",
            "away_score": "sum",
        }).rename(columns={"game_id": "GP_HOME", "home_score": "PTS_HOME", "away_score": "OPP_PTS_HOME"})

        teams_away = fixtures.groupby("away_team").agg({
            "game_id": "count",
            "home_score": "sum",
            "away_score": "sum",
        }).rename(columns={"game_id": "GP_AWAY", "home_score": "OPP_PTS_AWAY", "away_score": "PTS_AWAY"})

        # Combine home and away
        teams = pd.concat([teams_home, teams_away], axis=1).fillna(0)
        teams["GP"] = teams["GP_HOME"] + teams["GP_AWAY"]
        teams["PTS"] = teams["PTS_HOME"] + teams["PTS_AWAY"]
        teams["OPP_PTS"] = teams["OPP_PTS_HOME"] + teams["OPP_PTS_AWAY"]
        teams["PTS_DIFF"] = teams["PTS"] - teams["OPP_PTS"]

        # Calculate wins
        home_wins = fixtures[fixtures["home_score"] > fixtures["away_score"]].groupby("home_team").size()
        away_wins = fixtures[fixtures["away_score"] > fixtures["home_score"]].groupby("away_team").size()
        teams["W"] = home_wins.add(away_wins, fill_value=0).astype(int)
        teams["L"] = teams["GP"] - teams["W"]
        teams["WIN_PCT"] = teams["W"] / teams["GP"]

        # Reset index and rename
        teams = teams.reset_index()
        teams = teams.rename(columns={"index": "TEAM", "home_team": "TEAM", "away_team": "TEAM"})
        if "TEAM" not in teams.columns and teams.index.name in ["home_team", "away_team"]:
            teams["TEAM"] = teams.index

        # Select final columns
        teams = teams[["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "OPP_PTS", "PTS_DIFF"]]

        # Add metadata
        teams["LEAGUE"] = "LNB_PROA"
        teams["SEASON"] = season
        teams["COMPETITION"] = "LNB Pro A"

        logger.info(f"Fetched {len(teams)} LNB teams for {season}")
        return teams

    except FileNotFoundError as e:
        logger.error(str(e))
        return _empty_team_season_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB team season stats: {e}")
        return _empty_team_season_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_game(season: str = "2025-26") -> pd.DataFrame:
    """Fetch LNB Pro A player game statistics

    Returns player box scores for all games in season.

    Args:
        season: Season year as string

    Returns:
        DataFrame with player game statistics
    """
    logger.info(f"Fetching LNB player game stats: {season}")

    try:
        df = load_lnb_table("lnb_box_player")

        if df.empty:
            logger.warning("No LNB box_player data found")
            return _empty_player_game_df()

        # Filter by season
        df = df[df["season"] == season]

        logger.info(f"Fetched {len(df)} LNB player-games for {season}")
        return df

    except FileNotFoundError:
        logger.warning("LNB box_player data not available yet")
        return _empty_player_game_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB player game stats: {e}")
        return _empty_player_game_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_team_game(season: str = "2025-26") -> pd.DataFrame:
    """Fetch LNB Pro A team game statistics

    Returns team box scores for all games in season.

    Args:
        season: Season year as string

    Returns:
        DataFrame with team game statistics
    """
    logger.info(f"Fetching LNB team game stats: {season}")

    try:
        df = load_lnb_table("lnb_box_team")

        if df.empty:
            logger.warning("No LNB box_team data found")
            return _empty_team_game_df()

        # Filter by season
        df = df[df["season"] == season]

        logger.info(f"Fetched {len(df)} LNB team-games for {season}")
        return df

    except FileNotFoundError:
        logger.warning("LNB box_team data not available yet")
        return _empty_team_game_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB team game stats: {e}")
        return _empty_team_game_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
# Note: @cached_dataframe removed due to caching conflicts with GAME_ID type conversion
def fetch_lnb_pbp(season: str = "2025-26", game_id: str | None = None) -> pd.DataFrame:
    """Fetch LNB Pro A play-by-play data

    Args:
        season: Season year as string
        game_id: Optional game ID to filter (if None, returns all games in season)

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENT_NUM: Event sequence number
        - PERIOD: Quarter (1-4)
        - CLOCK: Game clock (MM:SS)
        - TEAM: Team name
        - PLAYER_NAME: Player name
        - EVENT_TYPE: Event type
        - DESCRIPTION: Event description
        - HOME_SCORE: Score after event
        - AWAY_SCORE: Score after event
        - LEAGUE: "LNB_PROA"
        - COMPETITION: "LNB Pro A"

    Example:
        >>> df = fetch_lnb_pbp("2025-26", game_id="1")
        >>> print(f"{len(df)} PBP events")
        417 PBP events
    """
    logger.info(f"Fetching LNB PBP: {season}, game_id={game_id}")

    try:
        # Load PBP events
        df = load_lnb_table("lnb_pbp_events")

        if df.empty:
            logger.warning("No LNB PBP data found")
            return _empty_pbp_df()

        # Filter by game_id if specified
        if game_id is not None:
            df = df[df["game_id"] == int(game_id)].copy()  # Copy to avoid view/cache issues

        if df.empty:
            logger.warning(f"No PBP events found for game_id={game_id}")
            return _empty_pbp_df()

        # Normalize column names and convert GAME_ID to string in one operation
        df = df.rename(
            columns={
                "game_id": "GAME_ID",
                "event_num": "EVENT_NUM",
                "period": "PERIOD",
                "clock": "CLOCK",
                "team": "TEAM",
                "player": "PLAYER_NAME",
                "event_type": "EVENT_TYPE",
                "description": "DESCRIPTION",
                "home_score": "HOME_SCORE",
                "away_score": "AWAY_SCORE",
                "league": "LEAGUE",
                "competition": "COMPETITION",
            }
        ).assign(GAME_ID=lambda x: x["GAME_ID"].astype(str))

        # Ensure required columns exist
        if "LEAGUE" not in df.columns:
            df["LEAGUE"] = "LNB_PROA"
        if "COMPETITION" not in df.columns:
            df["COMPETITION"] = "LNB Pro A"

        logger.info(f"Fetched {len(df)} LNB PBP events")
        # Return a copy to avoid mutating cached DataFrame
        return df.copy()

    except FileNotFoundError as e:
        logger.error(str(e))
        return _empty_pbp_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB PBP: {e}")
        return _empty_pbp_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_shots(
    season: str = "2025-26",
    game_id: str | None = None,
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Fetch LNB Pro A shot chart data

    Args:
        season: Season year as string
        game_id: Optional game ID to filter
        season_type: "Regular Season" or "Playoffs"

    Returns:
        DataFrame with shot data including x,y coordinates

    Columns:
        - GAME_ID: Game identifier
        - SHOT_NUM: Shot sequence number
        - PERIOD: Quarter (1-4)
        - CLOCK: Game clock (MM:SS)
        - TEAM: Team name
        - PLAYER_NAME: Player name
        - SHOT_TYPE: "2PT" or "3PT"
        - SHOT_MADE: 1=made, 0=missed
        - SHOT_X: X coordinate
        - SHOT_Y: Y coordinate
        - DISTANCE: Shot distance (feet)
        - LEAGUE: "LNB_PROA"
        - COMPETITION: "LNB Pro A"

    Example:
        >>> df = fetch_lnb_shots("2025-26")
        >>> print(f"{len(df)} shots with coordinates")
        973 shots with coordinates
    """
    logger.info(f"Fetching LNB shots: {season}, game_id={game_id}")

    try:
        # Load shots data
        df = load_lnb_table("lnb_shots")

        if df.empty:
            logger.warning("No LNB shots data found")
            return _empty_shots_df()

        # Filter by game_id if specified
        if game_id is not None:
            df = df[df["game_id"] == int(game_id)].copy()  # Copy to avoid view/cache issues

        if df.empty:
            logger.warning(f"No shots found for game_id={game_id}")
            return _empty_shots_df()

        # Normalize column names
        df = df.rename(
            columns={
                "game_id": "GAME_ID",
                "shot_num": "SHOT_NUM",
                "period": "PERIOD",
                "clock": "CLOCK",
                "team": "TEAM",
                "player": "PLAYER_NAME",
                "shot_type": "SHOT_TYPE",
                "made": "SHOT_MADE",
                "x": "SHOT_X",
                "y": "SHOT_Y",
                "distance": "DISTANCE",
                "league": "LEAGUE",
                "competition": "COMPETITION",
            }
        )

        # Convert GAME_ID to string for consistency with API expectations
        if "GAME_ID" in df.columns:
            df["GAME_ID"] = df["GAME_ID"].astype(str)

        # Ensure required columns exist
        if "LEAGUE" not in df.columns:
            df["LEAGUE"] = "LNB_PROA"
        if "COMPETITION" not in df.columns:
            df["COMPETITION"] = "LNB Pro A"

        logger.info(f"Fetched {len(df)} LNB shots")
        # Return a copy to avoid mutating cached DataFrame
        return df.copy()

    except FileNotFoundError as e:
        logger.error(str(e))
        return _empty_shots_df()

    except Exception as e:
        logger.error(f"Failed to fetch LNB shots: {e}")
        return _empty_shots_df()
