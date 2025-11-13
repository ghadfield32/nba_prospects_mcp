"""NBL Australia Official Data via nblR Package

This module provides access to official NBL Australia statistics via the nblR R package.
The nblR package wraps NBL's official stats backend and provides clean, historical data.

Data Source: nblR R package (CRAN, GPL-3)
- Package URL: https://cran.r-project.org/web/packages/nblR/
- Wraps NBL's official stats API
- Maintained by league data analysts

Data Coverage:
- **Match results**: All NBL games since **1979** (45+ years!)
- **Player box scores**: Since **2015-16** season (PTS, REB, AST, FG%, 3P%, FT%, etc.)
- **Team box scores**: Since **2015-16** season
- **Play-by-play**: Event-level data since **2015-16**
- **Shot locations**: (x, y) coordinates since **2015-16** ✨

Architecture:
1. R export script (tools/nbl/export_nbl.R) calls nblR and exports Parquet files
2. This Python module loads Parquet files and normalizes to cbb_data schema
3. Data flows into DuckDB for caching and querying

License Compliance:
- nblR is GPL-3 (we CALL the package, don't copy code - this is legal)
- Output data is public NBL statistics (factual information)
- This integration code follows project license

Usage:
    # Option A: Load pre-exported data
    from cbb_data.fetchers.nbl_official import load_nbl_table
    shots_df = load_nbl_table("nbl_shots")

    # Option B: Refresh from R + load
    from cbb_data.fetchers.nbl_official import run_nblr_export, load_nbl_table
    run_nblr_export()  # Runs tools/nbl/export_nbl.R
    shots_df = load_nbl_table("nbl_shots")

    # Option C: High-level API (recommended)
    from cbb_data.api.datasets import get_dataset
    df = get_dataset("shots", filters={"league": "NBL", "season": "2024"})

Prerequisites:
    1. R installed (https://www.r-project.org/)
    2. Install R packages: install.packages(c("nblR", "dplyr", "arrow"))
    3. Run export: Rscript tools/nbl/export_nbl.R

See Also:
    - tools/nbl/README.md - Setup and usage guide
    - tools/nbl/export_nbl.R - R export script
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Literal

import pandas as pd

from ..storage.duckdb_storage import get_storage
from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# Default export directory (matches R script default)
DEFAULT_EXPORT_DIR = Path("data/nbl_raw")

# Available tables from nblR
NBL_TABLES = [
    "nbl_results",  # Match results (1979+)
    "nbl_box_player",  # Player box scores (2015-16+)
    "nbl_box_team",  # Team box scores (2015-16+)
    "nbl_pbp",  # Play-by-play (2015-16+)
    "nbl_shots",  # Shot locations with x,y (2015-16+)
]

NBLTableType = Literal["nbl_results", "nbl_box_player", "nbl_box_team", "nbl_pbp", "nbl_shots"]


# ==============================================================================
# R Export Bridge
# ==============================================================================


def run_nblr_export(export_dir: Path | None = None, verbose: bool = True) -> None:
    """Run R export script to fetch NBL data via nblR package

    This executes tools/nbl/export_nbl.R which:
    1. Calls nblR functions (nbl_results, nbl_box_player, etc.)
    2. Exports data to Parquet files in export_dir

    Args:
        export_dir: Output directory for Parquet files (default: data/nbl_raw)
        verbose: Print R script output to console

    Raises:
        FileNotFoundError: If export_nbl.R script not found
        subprocess.CalledProcessError: If R script fails
        RuntimeError: If R or required packages not installed

    Example:
        >>> run_nblr_export()
        NBL Export Tool
        ===============
        Output directory: data/nbl_raw
        [1/5] Fetching match results since 1979...
        [nbl_results] Exporting match results... OK (10234 rows, 12 cols)
        ...
    """
    if export_dir is None:
        export_dir = DEFAULT_EXPORT_DIR

    export_dir.mkdir(parents=True, exist_ok=True)

    # Find R script
    script_path = Path("tools/nbl/export_nbl.R")
    if not script_path.exists():
        raise FileNotFoundError(
            f"R export script not found: {script_path}\n"
            "Expected location: tools/nbl/export_nbl.R\n"
            "Run from project root directory."
        )

    logger.info(f"Running nblR export script: {script_path}")
    logger.info(f"Output directory: {export_dir}")

    # Set environment variable for R script
    env = os.environ.copy()
    env["NBL_EXPORT_DIR"] = str(export_dir.absolute())

    # Check R is installed
    try:
        subprocess.run(
            ["Rscript", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError(
            "R not found. Install R:\n"
            "  Ubuntu/Debian: sudo apt-get install r-base\n"
            "  macOS: brew install r\n"
            "  Windows: https://cran.r-project.org/bin/windows/base/"
        )

    # Run R export script
    try:
        result = subprocess.run(
            ["Rscript", str(script_path)],
            check=True,
            capture_output=not verbose,
            text=True,
            env=env,
        )

        if verbose and result.stdout:
            print(result.stdout)

        logger.info("nblR export completed successfully")

    except subprocess.CalledProcessError as e:
        error_msg = f"R export script failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\n\nError output:\n{e.stderr}"

        # Check for common issues
        if "there is no package called" in (e.stderr or ""):
            error_msg += (
                "\n\nMissing R package. Install with:\n"
                '  R -e \'install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")\''
            )

        logger.error(error_msg)
        raise RuntimeError(error_msg)


# ==============================================================================
# Load Parquet Data
# ==============================================================================


def load_nbl_table(table: NBLTableType, export_dir: Path | None = None) -> pd.DataFrame:
    """Load NBL data from Parquet file (exported by R script)

    Args:
        table: Table name ("nbl_results", "nbl_box_player", "nbl_box_team", "nbl_pbp", "nbl_shots")
        export_dir: Directory containing Parquet files (default: data/nbl_raw)

    Returns:
        DataFrame with NBL data

    Raises:
        FileNotFoundError: If Parquet file not found (run run_nblr_export() first)

    Example:
        >>> shots = load_nbl_table("nbl_shots")
        >>> print(f"Loaded {len(shots)} shots with x,y coordinates")
        Loaded 523,847 shots with x,y coordinates
    """
    if export_dir is None:
        export_dir = DEFAULT_EXPORT_DIR

    file_path = export_dir / f"{table}.parquet"

    if not file_path.exists():
        raise FileNotFoundError(
            f"NBL data file not found: {file_path}\n\n"
            "Run R export first:\n"
            "  Rscript tools/nbl/export_nbl.R\n"
            "Or from Python:\n"
            "  from cbb_data.fetchers.nbl_official import run_nblr_export\n"
            "  run_nblr_export()"
        )

    logger.info(f"Loading NBL table: {table} from {file_path}")

    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded {len(df)} rows from {table}")
        return df

    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        raise


# ==============================================================================
# Normalized Fetchers (cbb_data schema)
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_schedule(season: str = "2024", season_type: str = "Regular Season") -> pd.DataFrame:
    """Fetch NBL schedule from nblR results data

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
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
        - VENUE: Arena name (if available)
        - LEAGUE: "NBL"

    Note:
        This uses nbl_results() which covers ALL NBL games since 1979!
        For detailed stats (box scores, PBP, shots), use 2015-16+ data.
    """
    logger.info(f"Fetching NBL schedule via nblR: {season}, {season_type}")

    try:
        # Load results from nblR export
        df = load_nbl_table("nbl_results")

        if df.empty:
            logger.warning("No NBL results data found")
            return _empty_schedule_df()

        # Filter by season (nblR uses season_slug like "2024-25")
        # Convert input "2024" to "2024-25" format
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # TODO: Apply season_type filter if nblR provides this info
        # For now, we return all games

        # Normalize column names to cbb_data schema
        df = df.rename(
            columns={
                "match_id": "GAME_ID",
                "season_slug": "SEASON",
                "start_time_utc": "GAME_DATE",
                "home_team": "HOME_TEAM",
                "away_team": "AWAY_TEAM",
                "home_score": "HOME_SCORE",
                "away_score": "AWAY_SCORE",
                "venue": "VENUE",
            }
        )

        # Add league identifier
        df["LEAGUE"] = "NBL"

        # Select and order columns
        columns = [
            "GAME_ID",
            "SEASON",
            "GAME_DATE",
            "HOME_TEAM",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
            "VENUE",
            "LEAGUE",
        ]
        df = df[[col for col in columns if col in df.columns]]

        logger.info(f"Fetched {len(df)} NBL games for {season}")
        return df

    except FileNotFoundError:
        logger.warning(
            "NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R"
        )
        return _empty_schedule_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL schedule: {e}")
        return _empty_schedule_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_player_season(season: str = "2024", per_mode: str = "Totals") -> pd.DataFrame:
    """Fetch NBL player season statistics from nblR box score data

    This aggregates game-level player stats (from nbl_box_player) into season totals.

    Args:
        season: Season year as string (e.g., "2024")
        per_mode: "Totals", "PerGame", or "Per40"

    Returns:
        DataFrame with player season statistics

    Columns:
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - GP: Games played
        - MIN: Minutes
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - LEAGUE: "NBL"
        - SEASON: Season string

    Note:
        nbl_box_player has data since 2015-16 season.
        For historical results pre-2015, use fetch_nbl_schedule().
    """
    logger.info(f"Fetching NBL player season stats via nblR: {season}, {per_mode}")

    try:
        # Load player box scores from nblR export
        df = load_nbl_table("nbl_box_player")

        if df.empty:
            logger.warning("No NBL player box score data found")
            return _empty_player_season_df()

        # Filter by season
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # Aggregate to season totals (group by player)
        agg_dict = {
            "match_id": "count",  # GP (games played)
            "mins": "sum",
            "pts": "sum",
            "rebs": "sum",
            "asts": "sum",
            "stls": "sum",
            "blks": "sum",
            "tovs": "sum",
            "fouls": "sum",
            # Shooting stats (need weighted averages for percentages)
            "fgm": "sum",
            "fga": "sum",
            "three_m": "sum",
            "three_a": "sum",
            "ftm": "sum",
            "fta": "sum",
        }

        # Group by player and aggregate
        season_df = df.groupby(["player_id", "player_name", "team_name"], as_index=False).agg(agg_dict)

        # Calculate shooting percentages
        season_df["FG_PCT"] = (season_df["fgm"] / season_df["fga"] * 100).fillna(0)
        season_df["FG3_PCT"] = (season_df["three_m"] / season_df["three_a"] * 100).fillna(0)
        season_df["FT_PCT"] = (season_df["ftm"] / season_df["fta"] * 100).fillna(0)

        # Rename columns to standard schema
        season_df = season_df.rename(
            columns={
                "player_id": "PLAYER_ID",
                "player_name": "PLAYER_NAME",
                "team_name": "TEAM",
                "match_id": "GP",
                "mins": "MIN",
                "pts": "PTS",
                "rebs": "REB",
                "asts": "AST",
                "stls": "STL",
                "blks": "BLK",
                "tovs": "TOV",
                "fouls": "PF",
                "fgm": "FGM",
                "fga": "FGA",
                "three_m": "FG3M",
                "three_a": "FG3A",
                "ftm": "FTM",
                "fta": "FTA",
            }
        )

        # Apply per_mode calculations
        if per_mode == "PerGame":
            stat_cols = [
                "MIN",
                "PTS",
                "REB",
                "AST",
                "STL",
                "BLK",
                "TOV",
                "PF",
                "FGM",
                "FGA",
                "FG3M",
                "FG3A",
                "FTM",
                "FTA",
            ]
            for col in stat_cols:
                if col in season_df.columns:
                    season_df[col] = season_df[col] / season_df["GP"].replace(0, 1)

        elif per_mode == "Per40":
            stat_cols = [
                "PTS",
                "REB",
                "AST",
                "STL",
                "BLK",
                "TOV",
                "PF",
                "FGM",
                "FGA",
                "FG3M",
                "FG3A",
                "FTM",
                "FTA",
            ]
            for col in stat_cols:
                if col in season_df.columns:
                    season_df[col] = season_df[col] / (season_df["MIN"].replace(0, 1) / 40.0)

        # Add league metadata
        season_df["LEAGUE"] = "NBL"
        season_df["SEASON"] = season

        logger.info(f"Fetched {len(season_df)} NBL players for {season}")
        return season_df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_player_season_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL player season stats: {e}")
        return _empty_player_season_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_team_season(season: str = "2024", per_mode: str = "Totals") -> pd.DataFrame:
    """Fetch NBL team season statistics from nblR box score data

    This aggregates game-level team stats (from nbl_box_team) into season totals.

    Args:
        season: Season year as string (e.g., "2024")
        per_mode: "Totals", "PerGame", or "Per40" (note: teams typically use Totals or PerGame)

    Returns:
        DataFrame with team season statistics

    Columns:
        - TEAM: Team name
        - GP: Games played
        - MIN: Total minutes
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - OREB, DREB: Offensive/defensive rebounds (if available)
        - OFF_RATING, DEF_RATING: Average ratings (if available)
        - LEAGUE: "NBL"
        - SEASON: Season string

    Note:
        Data available since 2015-16 season.
    """
    logger.info(f"Fetching NBL team season stats via nblR: {season}, {per_mode}")

    try:
        # Load team box scores from nblR export
        df = load_nbl_table("nbl_box_team")

        if df.empty:
            logger.warning("No NBL team box score data found")
            return _empty_team_season_df()

        # Filter by season
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # Aggregate to season totals (group by team)
        agg_dict = {
            "match_id": "count",  # GP (games played)
            "mins": "sum",
            "pts": "sum",
            "rebs": "sum",
            "asts": "sum",
            "stls": "sum",
            "blks": "sum",
            "tovs": "sum",
            "fouls": "sum",
            # Shooting stats (need weighted averages for percentages)
            "fgm": "sum",
            "fga": "sum",
            "three_m": "sum",
            "three_a": "sum",
            "ftm": "sum",
            "fta": "sum",
        }

        # Add optional columns if they exist
        if "o_rebs" in df.columns:
            agg_dict["o_rebs"] = "sum"
        if "d_rebs" in df.columns:
            agg_dict["d_rebs"] = "sum"
        if "off_rating" in df.columns:
            agg_dict["off_rating"] = "mean"
        if "def_rating" in df.columns:
            agg_dict["def_rating"] = "mean"

        # Group by team and aggregate
        season_df = df.groupby("team_name", as_index=False).agg(agg_dict)

        # Calculate shooting percentages
        season_df["FG_PCT"] = (season_df["fgm"] / season_df["fga"] * 100).fillna(0)
        season_df["FG3_PCT"] = (season_df["three_m"] / season_df["three_a"] * 100).fillna(0)
        season_df["FT_PCT"] = (season_df["ftm"] / season_df["fta"] * 100).fillna(0)

        # Rename columns to standard schema
        rename_dict = {
            "team_name": "TEAM",
            "match_id": "GP",
            "mins": "MIN",
            "pts": "PTS",
            "rebs": "REB",
            "asts": "AST",
            "stls": "STL",
            "blks": "BLK",
            "tovs": "TOV",
            "fouls": "PF",
            "fgm": "FGM",
            "fga": "FGA",
            "three_m": "FG3M",
            "three_a": "FG3A",
            "ftm": "FTM",
            "fta": "FTA",
        }
        if "o_rebs" in season_df.columns:
            rename_dict["o_rebs"] = "OREB"
        if "d_rebs" in season_df.columns:
            rename_dict["d_rebs"] = "DREB"
        if "off_rating" in season_df.columns:
            rename_dict["off_rating"] = "OFF_RATING"
        if "def_rating" in season_df.columns:
            rename_dict["def_rating"] = "DEF_RATING"

        season_df = season_df.rename(columns=rename_dict)

        # Apply per_mode calculations
        if per_mode == "PerGame":
            stat_cols = [
                "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF",
                "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"
            ]
            if "OREB" in season_df.columns:
                stat_cols.extend(["OREB", "DREB"])
            for col in stat_cols:
                if col in season_df.columns:
                    season_df[col] = season_df[col] / season_df["GP"].replace(0, 1)

        elif per_mode == "Per40":
            stat_cols = [
                "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF",
                "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"
            ]
            if "OREB" in season_df.columns:
                stat_cols.extend(["OREB", "DREB"])
            for col in stat_cols:
                if col in season_df.columns:
                    season_df[col] = season_df[col] / (season_df["MIN"].replace(0, 1) / 40.0)

        # Add league metadata
        season_df["LEAGUE"] = "NBL"
        season_df["SEASON"] = season

        logger.info(f"Fetched {len(season_df)} NBL teams for {season}")
        return season_df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_team_season_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL team season stats: {e}")
        return _empty_team_season_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_player_game(season: str = "2024") -> pd.DataFrame:
    """Fetch NBL player-game box scores from nblR

    Returns one row per (GAME_ID, PLAYER_ID) with game-level statistics.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with player-game box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - MIN: Minutes played
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - PLUS_MINUS: Plus/minus rating (if available)
        - LEAGUE: "NBL"
        - SEASON: Season string

    Note:
        Data available since 2015-16 season.
    """
    logger.info(f"Fetching NBL player-game box scores via nblR: {season}")

    try:
        # Load player box scores from nblR export
        df = load_nbl_table("nbl_box_player")

        if df.empty:
            logger.warning("No NBL player box score data found")
            return _empty_player_game_df()

        # Filter by season
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # Calculate shooting percentages
        df["FG_PCT"] = (df["fgm"] / df["fga"] * 100).fillna(0)
        df["FG3_PCT"] = (df["three_m"] / df["three_a"] * 100).fillna(0)
        df["FT_PCT"] = (df["ftm"] / df["fta"] * 100).fillna(0)

        # Normalize columns to standard schema
        df = df.rename(
            columns={
                "match_id": "GAME_ID",
                "player_id": "PLAYER_ID",
                "player_name": "PLAYER_NAME",
                "team_name": "TEAM",
                "mins": "MIN",
                "pts": "PTS",
                "rebs": "REB",
                "asts": "AST",
                "stls": "STL",
                "blks": "BLK",
                "tovs": "TOV",
                "fouls": "PF",
                "fgm": "FGM",
                "fga": "FGA",
                "three_m": "FG3M",
                "three_a": "FG3A",
                "ftm": "FTM",
                "fta": "FTA",
                "plus_minus": "PLUS_MINUS",
            }
        )

        # Add league metadata
        df["LEAGUE"] = "NBL"
        df["SEASON"] = season

        # Select columns in standard order
        standard_cols = [
            "GAME_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM", "MIN",
            "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF",
            "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
            "FTM", "FTA", "FT_PCT", "PLUS_MINUS", "LEAGUE", "SEASON"
        ]
        df = df[[col for col in standard_cols if col in df.columns]]

        logger.info(f"Fetched {len(df)} NBL player-game records for {season}")
        return df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_player_game_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL player-game data: {e}")
        return _empty_player_game_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_team_game(season: str = "2024") -> pd.DataFrame:
    """Fetch NBL team-game box scores from nblR

    Returns one row per (GAME_ID, TEAM) with team-level statistics.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with team-game box scores

    Columns:
        - GAME_ID: Game identifier
        - TEAM: Team name
        - MIN: Total team minutes (usually 200 for 5 players × 40 min)
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - OREB, DREB: Offensive/defensive rebounds (if available)
        - OFF_RATING, DEF_RATING: Offensive/defensive ratings (if available)
        - LEAGUE: "NBL"
        - SEASON: Season string

    Note:
        Data available since 2015-16 season.
    """
    logger.info(f"Fetching NBL team-game box scores via nblR: {season}")

    try:
        # Load team box scores from nblR export
        df = load_nbl_table("nbl_box_team")

        if df.empty:
            logger.warning("No NBL team box score data found")
            return _empty_team_game_df()

        # Filter by season
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # Calculate shooting percentages
        df["FG_PCT"] = (df["fgm"] / df["fga"] * 100).fillna(0)
        df["FG3_PCT"] = (df["three_m"] / df["three_a"] * 100).fillna(0)
        df["FT_PCT"] = (df["ftm"] / df["fta"] * 100).fillna(0)

        # Normalize columns to standard schema
        df = df.rename(
            columns={
                "match_id": "GAME_ID",
                "team_name": "TEAM",
                "mins": "MIN",
                "pts": "PTS",
                "rebs": "REB",
                "asts": "AST",
                "stls": "STL",
                "blks": "BLK",
                "tovs": "TOV",
                "fouls": "PF",
                "fgm": "FGM",
                "fga": "FGA",
                "three_m": "FG3M",
                "three_a": "FG3A",
                "ftm": "FTM",
                "fta": "FTA",
                "o_rebs": "OREB",
                "d_rebs": "DREB",
                "off_rating": "OFF_RATING",
                "def_rating": "DEF_RATING",
            }
        )

        # Add league metadata
        df["LEAGUE"] = "NBL"
        df["SEASON"] = season

        # Select columns in standard order
        standard_cols = [
            "GAME_ID", "TEAM", "MIN",
            "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF",
            "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
            "FTM", "FTA", "FT_PCT", "OREB", "DREB",
            "OFF_RATING", "DEF_RATING", "LEAGUE", "SEASON"
        ]
        df = df[[col for col in standard_cols if col in df.columns]]

        logger.info(f"Fetched {len(df)} NBL team-game records for {season}")
        return df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_team_game_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL team-game data: {e}")
        return _empty_team_game_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_pbp(season: str = "2024", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NBL play-by-play data from nblR

    Returns event-level play-by-play data for games.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        game_id: Optional game ID to filter (None = all games in season)

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENT_NUM: Event sequence number
        - PERIOD: Quarter number
        - CLOCK: Game clock (MM:SS)
        - TEAM: Team name (if event has team)
        - PLAYER: Player name (if event has player)
        - EVENT_TYPE: Type of event (shot, foul, turnover, etc.)
        - DESCRIPTION: Event description
        - SCORE_HOME: Home team score after event
        - SCORE_AWAY: Away team score after event
        - LEAGUE: "NBL"
        - SEASON: Season string

    Note:
        Data available since 2015-16 season.
    """
    logger.info(f"Fetching NBL play-by-play via nblR: {season}, game_id={game_id}")

    try:
        # Load play-by-play from nblR export
        df = load_nbl_table("nbl_pbp")

        if df.empty:
            logger.warning("No NBL play-by-play data found")
            return _empty_pbp_df()

        # Filter by season
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # Filter by game if specified
        if game_id:
            df = df[df["match_id"] == game_id]

        # Normalize columns to standard schema
        df = df.rename(
            columns={
                "match_id": "GAME_ID",
                "event_num": "EVENT_NUM",
                "period": "PERIOD",
                "clock": "CLOCK",
                "team_name": "TEAM",
                "player_name": "PLAYER",
                "event_type": "EVENT_TYPE",
                "description": "DESCRIPTION",
                "score_home": "SCORE_HOME",
                "score_away": "SCORE_AWAY",
            }
        )

        # Add league metadata
        df["LEAGUE"] = "NBL"
        df["SEASON"] = season

        # Select columns in standard order
        standard_cols = [
            "GAME_ID", "EVENT_NUM", "PERIOD", "CLOCK",
            "TEAM", "PLAYER", "EVENT_TYPE", "DESCRIPTION",
            "SCORE_HOME", "SCORE_AWAY", "LEAGUE", "SEASON"
        ]
        df = df[[col for col in standard_cols if col in df.columns]]

        logger.info(f"Fetched {len(df)} NBL play-by-play events (season={season}, game={game_id or 'all'})")
        return df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_pbp_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL play-by-play: {e}")
        return _empty_pbp_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_shots(season: str = "2024", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NBL shot chart data with (x, y) coordinates via nblR

    This is the "Shot Machine" equivalent - spatial shot data that SpatialJam charges $20/mo for!

    Args:
        season: Season year (e.g., "2024")
        game_id: Optional game ID to filter (None = all games in season)

    Returns:
        DataFrame with shot locations

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - PERIOD: Quarter number
        - CLOCK: Game clock
        - LOC_X: X coordinate (court position)
        - LOC_Y: Y coordinate (court position)
        - SHOT_TYPE: Description of shot
        - SHOT_DISTANCE: Distance from basket
        - IS_MAKE: Boolean - shot made/missed
        - POINTS_VALUE: 2 or 3 points
        - LEAGUE: "NBL"

    Note:
        Shot location data available since 2015-16 season.
        This is the same data source SpatialJam uses!
    """
    logger.info(f"Fetching NBL shot data via nblR: {season}, game_id={game_id}")

    try:
        # Load shots from nblR export
        df = load_nbl_table("nbl_shots")

        if df.empty:
            logger.warning("No NBL shot data found")
            return _empty_shots_df()

        # Filter by season
        season_slug = f"{season}-{str(int(season) + 1)[-2:]}"
        df = df[df["season_slug"] == season_slug]

        # Filter by game if specified
        if game_id:
            df = df[df["match_id"] == game_id]

        # Normalize columns to standard schema
        df = df.rename(
            columns={
                "match_id": "GAME_ID",
                "player_id": "PLAYER_ID",
                "player_name": "PLAYER_NAME",
                "team_name": "TEAM",
                "period": "PERIOD",
                "clock": "CLOCK",
                "loc_x": "LOC_X",
                "loc_y": "LOC_Y",
                "shot_type": "SHOT_TYPE",
                "shot_distance": "SHOT_DISTANCE",
                "is_make": "IS_MAKE",
                "points_value": "POINTS_VALUE",
            }
        )

        # Add league identifier
        df["LEAGUE"] = "NBL"
        df["SEASON"] = season

        logger.info(f"Fetched {len(df)} NBL shots (season={season}, game={game_id or 'all'})")
        return df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_shots_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL shots: {e}")
        return _empty_shots_df()


# ==============================================================================
# DuckDB Integration
# ==============================================================================


def ingest_nbl_into_duckdb(export_dir: Path | None = None) -> None:
    """Ingest all NBL data from Parquet files into DuckDB

    This is the bridge between R exports and the cbb_data storage layer.

    Args:
        export_dir: Directory containing nblR Parquet exports (default: data/nbl_raw)

    Example:
        >>> from cbb_data.fetchers.nbl_official import run_nblr_export, ingest_nbl_into_duckdb
        >>> run_nblr_export()  # Step 1: Export from R
        >>> ingest_nbl_into_duckdb()  # Step 2: Load into DuckDB
        >>> # Step 3: Query via high-level API
        >>> from cbb_data.api.datasets import get_dataset
        >>> df = get_dataset("shots", filters={"league": "NBL"})
    """
    storage = get_storage()

    logger.info("Ingesting NBL data into DuckDB...")

    for table in NBL_TABLES:
        try:
            df = load_nbl_table(table, export_dir=export_dir)

            # Determine season from data (use most recent for table name)
            if "season_slug" in df.columns:
                latest_season = df["season_slug"].max()
            else:
                latest_season = "all"  # For historical results table

            # Save to DuckDB
            # Note: Table naming follows pattern: {dataset}_{league}_{season}
            storage.save(df, dataset=table, league="NBL", season=latest_season)

            logger.info(f"Ingested {table}: {len(df)} rows")

        except FileNotFoundError:
            logger.warning(f"Skipping {table}: Parquet file not found")
        except Exception as e:
            logger.error(f"Failed to ingest {table}: {e}")

    logger.info("NBL data ingestion complete")


# ==============================================================================
# Empty DataFrame Helpers
# ==============================================================================


def _empty_schedule_df() -> pd.DataFrame:
    """Return empty DataFrame with schedule schema"""
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
        ]
    )


def _empty_player_season_df() -> pd.DataFrame:
    """Return empty DataFrame with player season schema"""
    return pd.DataFrame(
        columns=[
            "PLAYER_ID",
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
            "PF",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_team_season_df() -> pd.DataFrame:
    """Return empty DataFrame with team season schema"""
    return pd.DataFrame(
        columns=[
            "TEAM",
            "GP",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "OREB",
            "DREB",
            "OFF_RATING",
            "DEF_RATING",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_player_game_df() -> pd.DataFrame:
    """Return empty DataFrame with player-game schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "PLUS_MINUS",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_team_game_df() -> pd.DataFrame:
    """Return empty DataFrame with team-game schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "TEAM",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "OREB",
            "DREB",
            "OFF_RATING",
            "DEF_RATING",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_pbp_df() -> pd.DataFrame:
    """Return empty DataFrame with play-by-play schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "EVENT_NUM",
            "PERIOD",
            "CLOCK",
            "TEAM",
            "PLAYER",
            "EVENT_TYPE",
            "DESCRIPTION",
            "SCORE_HOME",
            "SCORE_AWAY",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_shots_df() -> pd.DataFrame:
    """Return empty DataFrame with shots schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM",
            "PERIOD",
            "CLOCK",
            "LOC_X",
            "LOC_Y",
            "SHOT_TYPE",
            "SHOT_DISTANCE",
            "IS_MAKE",
            "POINTS_VALUE",
            "LEAGUE",
            "SEASON",
        ]
    )
