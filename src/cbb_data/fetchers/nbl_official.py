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
from typing import Any, Literal, cast

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
    except (subprocess.CalledProcessError, FileNotFoundError) as err:
        raise RuntimeError(
            "R not found. Install R:\n"
            "  Ubuntu/Debian: sudo apt-get install r-base\n"
            "  macOS: brew install r\n"
            "  Windows: https://cran.r-project.org/bin/windows/base/"
        ) from err

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
        raise RuntimeError(error_msg) from e


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

        # Filter by season (nblR uses format like "2015-2016", "1979", etc.)
        # Try both formats
        season_variants = [
            season,  # e.g., "2023"
            f"{season}-{str(int(season) + 1)[-2:]}",  # e.g., "2023-24"
            f"{season}-{str(int(season) + 1)}",  # e.g., "2023-2024"
        ]
        df = df[df["season"].isin(season_variants)]

        if df.empty:
            logger.warning(f"No games found for season {season}")
            return _empty_schedule_df()

        # Filter by match_type if season_type specified
        if season_type and season_type.lower() != "regular season":
            # Map season_type to match_type
            if "playoff" in season_type.lower():
                df = df[df["match_type"] != "REGULAR"]
        else:
            # Regular season only
            df = df[df["match_type"] == "REGULAR"]

        # NBL data has one row per team per game (each game appears twice)
        # We need to pivot this to one row per game with home/away split

        # Separate home and away rows
        home_df = df[df["is_home_competitor"] == "1"].copy()
        away_df = df[df["is_home_competitor"] != "1"].copy()

        # Merge on match_id to create one row per game
        schedule = pd.merge(
            home_df, away_df, on="match_id", how="outer", suffixes=("_home", "_away")
        )

        # Build standard schema
        result = pd.DataFrame()
        result["GAME_ID"] = schedule["match_id"]
        result["SEASON"] = schedule["season_home"].fillna(schedule["season_away"])
        result["GAME_DATE"] = pd.to_datetime(
            schedule["match_time_utc_home"].fillna(schedule["match_time_utc_away"])
        )
        result["HOME_TEAM"] = schedule["team_name_home"]
        result["AWAY_TEAM"] = schedule["team_name_away"]
        result["HOME_SCORE"] = pd.to_numeric(schedule["score_string_home"], errors="coerce")
        result["AWAY_SCORE"] = pd.to_numeric(schedule["score_string_away"], errors="coerce")
        result["VENUE"] = schedule["venue_name_home"].fillna(schedule["venue_name_away"])
        result["LEAGUE"] = "NBL"

        # Drop any rows where we couldn't match home/away properly
        result = result.dropna(subset=["HOME_TEAM", "AWAY_TEAM"])

        logger.info(f"Fetched {len(result)} NBL games for {season}")
        return result

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
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

        # Filter by season (nblR uses format like "2015-2016")
        season_variants = [
            season,  # e.g., "2023"
            f"{season}-{str(int(season) + 1)[-2:]}",  # e.g., "2023-24"
            f"{season}-{str(int(season) + 1)}",  # e.g., "2023-2024"
        ]
        df = df[df["season"].isin(season_variants)]

        if df.empty:
            logger.warning(f"No player data found for season {season}")
            return _empty_player_season_df()

        # Create player identifier (combine first_name + family_name)
        df["player_full_name"] = df["first_name"] + " " + df["family_name"]

        # Convert minutes from MM:SS string format to decimal minutes
        # Format is like "38:02" (38 minutes, 2 seconds)
        def parse_minutes(time_str: Any) -> float:
            """Convert MM:SS string to decimal minutes"""
            if pd.isna(time_str) or time_str == "":
                return 0.0
            try:
                if isinstance(time_str, str) and ":" in time_str:
                    parts = time_str.split(":")
                    mins = float(parts[0])
                    secs = float(parts[1]) if len(parts) > 1 else 0
                    return mins + (secs / 60.0)
                else:
                    # Already numeric or can be converted
                    return float(time_str)
            except (ValueError, AttributeError):
                return 0.0

        df["minutes_numeric"] = df["minutes"].apply(parse_minutes)

        # Aggregate to season totals (group by player)
        agg_dict = {
            "match_id": "count",  # GP (games played)
            "minutes_numeric": "sum",  # Use numeric minutes
            "points": "sum",
            "rebounds_total": "sum",
            "assists": "sum",
            "steals": "sum",
            "blocks": "sum",
            "turnovers": "sum",
            "fouls_personal": "sum",
            # Shooting stats (need weighted averages for percentages)
            "field_goals_made": "sum",
            "field_goals_attempted": "sum",
            "three_pointers_made": "sum",
            "three_pointers_attempted": "sum",
            "free_throws_made": "sum",
            "free_throws_attempted": "sum",
        }

        # Group by player and aggregate
        # Note: player_id may be null in some seasons, so we use player_full_name + team_name
        # to uniquely identify players
        season_df = df.groupby(["player_full_name", "team_name"], as_index=False).agg(agg_dict)

        # Add player_id column (will be empty if not available in source data)
        # Use first non-null player_id if available, otherwise empty string
        if "player_id" in df.columns and df["player_id"].notna().any():
            player_ids = df.groupby(["player_full_name", "team_name"])["player_id"].first()
            season_df = season_df.merge(
                player_ids.reset_index(), on=["player_full_name", "team_name"], how="left"
            )
        else:
            # No player IDs available, use player_full_name as ID
            season_df["player_id"] = season_df["player_full_name"]

        # Rename columns to standard schema BEFORE calculations
        season_df = season_df.rename(
            columns={
                "match_id": "GP",
                "minutes_numeric": "MIN",  # Use parsed numeric minutes
                "points": "PTS",
                "rebounds_total": "REB",
                "assists": "AST",
                "steals": "STL",
                "blocks": "BLK",
                "turnovers": "TOV",
                "fouls_personal": "PF",
                "field_goals_made": "FGM",
                "field_goals_attempted": "FGA",
                "three_pointers_made": "FG3M",
                "three_pointers_attempted": "FG3A",
                "free_throws_made": "FTM",
                "free_throws_attempted": "FTA",
                "player_full_name": "PLAYER_NAME",
                "team_name": "TEAM",
            }
        )

        # Rename player_id if it exists
        if "player_id" in season_df.columns:
            season_df = season_df.rename(columns={"player_id": "PLAYER_ID"})
        else:
            season_df["PLAYER_ID"] = season_df["PLAYER_NAME"]

        # Ensure all stat columns are numeric (in case merge caused type issues)
        numeric_cols = [
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
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
        ]
        for col in numeric_cols:
            if col in season_df.columns:
                season_df[col] = pd.to_numeric(season_df[col], errors="coerce").fillna(0)

        # Calculate shooting percentages (after rename, before per_mode)
        season_df["FG_PCT"] = (season_df["FGM"] / season_df["FGA"] * 100).fillna(0)
        season_df["FG3_PCT"] = (season_df["FG3M"] / season_df["FG3A"] * 100).fillna(0)
        season_df["FT_PCT"] = (season_df["FTM"] / season_df["FTA"] * 100).fillna(0)

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
            # Per40 formula: (stat / total_minutes) * 40
            # This normalizes stats to a 40-minute game

            # Save total minutes BEFORE modifying anything
            total_minutes = season_df["MIN"].copy()

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
                    # Use total minutes to normalize: (stat * 40) / total_minutes
                    season_df[col] = (season_df[col] * 40.0) / total_minutes.replace(0, 1)

            # Convert MIN to per-game average for display (using saved total)
            season_df["MIN"] = total_minutes / season_df["GP"].replace(0, 1)

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

        # Filter by season (nblR uses format like "2015-2016")
        season_variants = [
            season,  # e.g., "2023"
            f"{season}-{str(int(season) + 1)[-2:]}",  # e.g., "2023-24"
            f"{season}-{str(int(season) + 1)}",  # e.g., "2023-2024"
        ]
        df = df[df["season"].isin(season_variants)]

        if df.empty:
            logger.warning(f"No team data found for season {season}")
            return _empty_team_season_df()

        # Convert minutes from MM:SS string format to decimal minutes
        def parse_minutes(time_str: Any) -> float:
            """Convert MM:SS string to decimal minutes"""
            if pd.isna(time_str) or time_str == "":
                return 0.0
            try:
                if isinstance(time_str, str) and ":" in time_str:
                    parts = time_str.split(":")
                    mins = float(parts[0])
                    secs = float(parts[1]) if len(parts) > 1 else 0
                    return mins + (secs / 60.0)
                else:
                    return float(time_str)
            except (ValueError, AttributeError):
                return 0.0

        df["minutes_numeric"] = df["minutes"].apply(parse_minutes)

        # Aggregate to season totals (group by team)
        # Note: nbl_box_team uses 'name' for team name
        agg_dict = {
            "match_id": "count",  # GP (games played)
            "minutes_numeric": "sum",  # Use numeric minutes
            "points": "sum",
            "rebounds_total": "sum",
            "assists": "sum",
            "steals": "sum",
            "blocks": "sum",
            "turnovers": "sum",
            "fouls_personal": "sum",
            # Shooting stats
            "field_goals_made": "sum",
            "field_goals_attempted": "sum",
            "three_pointers_made": "sum",
            "three_pointers_attempted": "sum",
            "free_throws_made": "sum",
            "free_throws_attempted": "sum",
        }

        # Add optional columns if they exist
        if "rebounds_offensive" in df.columns:
            agg_dict["rebounds_offensive"] = "sum"
        if "rebounds_defensive" in df.columns:
            agg_dict["rebounds_defensive"] = "sum"

        # Group by team and aggregate
        season_df = df.groupby("name", as_index=False).agg(agg_dict)

        # Rename columns BEFORE calculations
        season_df = season_df.rename(
            columns={
                "name": "TEAM",
                "match_id": "GP",
                "minutes_numeric": "MIN",  # Use parsed numeric minutes
                "points": "PTS",
                "rebounds_total": "REB",
                "assists": "AST",
                "steals": "STL",
                "blocks": "BLK",
                "turnovers": "TOV",
                "fouls_personal": "PF",
                "field_goals_made": "FGM",
                "field_goals_attempted": "FGA",
                "three_pointers_made": "FG3M",
                "three_pointers_attempted": "FG3A",
                "free_throws_made": "FTM",
                "free_throws_attempted": "FTA",
            }
        )

        # Rename optional columns
        if "rebounds_offensive" in season_df.columns:
            season_df = season_df.rename(columns={"rebounds_offensive": "OREB"})
        if "rebounds_defensive" in season_df.columns:
            season_df = season_df.rename(columns={"rebounds_defensive": "DREB"})

        # Ensure all stat columns are numeric
        numeric_cols = [
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
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
        ]
        if "OREB" in season_df.columns:
            numeric_cols.extend(["OREB", "DREB"])
        for col in numeric_cols:
            if col in season_df.columns:
                season_df[col] = pd.to_numeric(season_df[col], errors="coerce").fillna(0)

        # Calculate shooting percentages
        season_df["FG_PCT"] = (season_df["FGM"] / season_df["FGA"] * 100).fillna(0)
        season_df["FG3_PCT"] = (season_df["FG3M"] / season_df["FG3A"] * 100).fillna(0)
        season_df["FT_PCT"] = (season_df["FTM"] / season_df["FTA"] * 100).fillna(0)

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
            if "OREB" in season_df.columns:
                stat_cols.extend(["OREB", "DREB"])
            for col in stat_cols:
                if col in season_df.columns:
                    season_df[col] = season_df[col] / season_df["GP"].replace(0, 1)

        elif per_mode == "Per40":
            # Per40 formula: (stat * 40) / total_minutes

            # Save total minutes BEFORE modifying anything
            total_minutes = season_df["MIN"].copy()

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
            if "OREB" in season_df.columns:
                stat_cols.extend(["OREB", "DREB"])
            for col in stat_cols:
                if col in season_df.columns:
                    season_df[col] = (season_df[col] * 40.0) / total_minutes.replace(0, 1)

            # Convert MIN to per-game average for display (using saved total)
            season_df["MIN"] = total_minutes / season_df["GP"].replace(0, 1)

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

        # Filter by season (handle multiple format variants)
        # Season may be stored as "2023", "2023-24", or "2023-2024"
        season_variants = [
            season,
            f"{season}-{str(int(season) + 1)[-2:]}",
            f"{season}-{str(int(season) + 1)}",
        ]
        df = df[df["season"].isin(season_variants)]

        # Parse minutes from "MM:SS" format to decimal
        def parse_minutes(time_str: Any) -> float:
            """Convert MM:SS string to decimal minutes"""
            if pd.isna(time_str) or time_str == "":
                return 0.0
            try:
                if isinstance(time_str, str) and ":" in time_str:
                    parts = time_str.split(":")
                    mins = float(parts[0])
                    secs = float(parts[1]) if len(parts) > 1 else 0
                    return mins + (secs / 60.0)
                else:
                    return float(time_str)
            except (ValueError, AttributeError):
                return 0.0

        if "minutes" in df.columns:
            df["minutes"] = df["minutes"].apply(parse_minutes)

        # Calculate shooting percentages (using actual nblR column names)
        df["FG_PCT"] = (df["field_goals_made"] / df["field_goals_attempted"] * 100).fillna(0)
        df["FG3_PCT"] = (df["three_pointers_made"] / df["three_pointers_attempted"] * 100).fillna(0)
        df["FT_PCT"] = (df["free_throws_made"] / df["free_throws_attempted"] * 100).fillna(0)

        # Normalize columns to standard schema
        df = df.rename(
            columns={
                "match_id": "GAME_ID",
                "player_id": "PLAYER_ID",
                "player_full_name": "PLAYER_NAME",
                "team_name": "TEAM",
                "minutes": "MIN",
                "points": "PTS",
                "rebounds_total": "REB",
                "assists": "AST",
                "steals": "STL",
                "blocks": "BLK",
                "turnovers": "TOV",
                "fouls_personal": "PF",
                "field_goals_made": "FGM",
                "field_goals_attempted": "FGA",
                "three_pointers_made": "FG3M",
                "three_pointers_attempted": "FG3A",
                "free_throws_made": "FTM",
                "free_throws_attempted": "FTA",
                "plus_minus": "PLUS_MINUS",
            }
        )

        # Add league metadata
        df["LEAGUE"] = "NBL"
        df["SEASON"] = season

        # Select columns in standard order
        standard_cols = [
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

        # Filter by season (handle multiple format variants)
        # Season may be stored as "2023", "2023-24", or "2023-2024"
        season_variants = [
            season,
            f"{season}-{str(int(season) + 1)[-2:]}",
            f"{season}-{str(int(season) + 1)}",
        ]
        df = df[df["season"].isin(season_variants)]

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

        # Filter by season (handle multiple format variants)
        # Season may be stored as "2023", "2023-24", or "2023-2024"
        season_variants = [
            season,
            f"{season}-{str(int(season) + 1)[-2:]}",
            f"{season}-{str(int(season) + 1)}",
        ]
        df = df[df["season"].isin(season_variants)]

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
        df = df[[col for col in standard_cols if col in df.columns]]

        logger.info(
            f"Fetched {len(df)} NBL play-by-play events (season={season}, game={game_id or 'all'})"
        )
        return df

    except FileNotFoundError:
        logger.warning("NBL data not yet exported. Run: Rscript tools/nbl/export_nbl.R")
        return _empty_pbp_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL play-by-play: {e}")
        return _empty_pbp_df()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_shots(
    season: str = "2024",
    game_id: str | None = None,
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Fetch NBL shot chart data with (x, y) coordinates via nblR

    This is the "Shot Machine" equivalent - spatial shot data that SpatialJam charges $20/mo for!

    Args:
        season: Season year (e.g., "2024")
        game_id: Optional game ID to filter (None = all games in season)
        season_type: Season type filter (currently ignored - NBL data doesn't separate regular/playoffs)

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

        # Filter by season (handle multiple format variants)
        # Season may be stored as "2023", "2023-24", or "2023-2024"
        # Input season may also be in any of these formats

        # Extract base year (handle "2023", "2023-24", or "2023-2024")
        base_year = season.split("-")[0] if "-" in season else season

        season_variants = [
            base_year,
            f"{base_year}-{str(int(base_year) + 1)[-2:]}",
            f"{base_year}-{str(int(base_year) + 1)}",
        ]
        df = df[df["season"].isin(season_variants)]

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

        # Derive GAME_MINUTE from PERIOD + CLOCK for game-minute filtering
        # NBL uses 10-minute quarters (FIBA standard)
        def _clock_to_seconds(clock: str) -> float:
            """Convert game clock string (MM:SS) to seconds remaining in period"""
            try:
                if not isinstance(clock, str):
                    return 0.0
                parts = str(clock).split(":")
                if len(parts) != 2:
                    return 0.0
                m, s = float(parts[0]), float(parts[1])
                return m * 60 + s
            except Exception:
                return 0.0

        if "PERIOD" in df.columns and "CLOCK" in df.columns:
            period_length = 10.0  # NBL uses 10-minute quarters
            clock_seconds = df["CLOCK"].apply(_clock_to_seconds)
            elapsed_in_period = period_length - (clock_seconds / 60.0)
            df["GAME_MINUTE"] = (
                df["PERIOD"].astype(float) - 1.0
            ) * period_length + elapsed_in_period
            df["GAME_MINUTE"] = df["GAME_MINUTE"].round(2)  # Round to 2 decimal places

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
            df = load_nbl_table(cast(NBLTableType, table), export_dir=export_dir)

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


# ==============================================================================
# CLI Entry Point
# ==============================================================================


def cli_export() -> None:
    """CLI entrypoint for nbl-export command

    This is the main entry point when running: uv run nbl-export

    It performs the full NBL data refresh:
    1. Runs the R export script (tools/nbl/export_nbl.R)
    2. Loads the Parquet files into memory
    3. Ingests them into DuckDB storage

    Example:
        $ uv run nbl-export
        NBL Export Tool
        ===============
        Output directory: data/nbl_raw
        [1/5] Fetching match results since 1979...
        [nbl_results] Exporting match results... OK (10234 rows, 12 cols)
        ...
        ✅ NBL official data exported and ingested.
    """
    import sys

    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger.info("🏀 NBL Data Export Starting...")
    logger.info("=" * 60)

    try:
        # Step 1: Run R export
        logger.info("Step 1/2: Running R export script (nblR package)")
        logger.info("-" * 60)
        run_nblr_export(verbose=True)

        logger.info("")
        logger.info("Step 2/2: Ingesting data into DuckDB")
        logger.info("-" * 60)

        # Step 2: Ingest into DuckDB
        ingest_nbl_into_duckdb()

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ NBL official data exported and ingested successfully!")
        logger.info("")
        logger.info("Data available via:")
        logger.info("  from cbb_data.api.datasets import get_dataset")
        logger.info('  df = get_dataset("shots", filters={"league": "NBL", "season": "2024"})')
        logger.info("")

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ NBL export failed: {e}")
        logger.error("=" * 60)
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("  1. Ensure R is installed: Rscript --version")
        logger.error(
            '  2. Install R packages: R -e \'install.packages(c("nblR", "dplyr", "arrow"))\''
        )
        logger.error("  3. See tools/nbl/SETUP_GUIDE.md for detailed setup instructions")
        logger.error("")
        sys.exit(1)
