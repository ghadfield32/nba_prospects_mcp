"""NZ NBL (New Zealand National Basketball League) Fetcher

NZ NBL data via FIBA LiveStats HTML scraping (public pages).
New Zealand's top-tier professional basketball league.

Data Source: FIBA LiveStats public HTML pages
- Box scores: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/[GAME_ID]/bs.html
- Play-by-play: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/[GAME_ID]/pbp.html

League Code: "NZN" (NZ NBL in FIBA LiveStats system)

Data Coverage:
- Schedule: Via pre-built game index (data/nz_nbl_game_index.parquet)
- Player-game box scores: Via FIBA LiveStats HTML scraping
- Team-game box scores: Aggregated from player stats
- Play-by-play: Via FIBA LiveStats HTML scraping (when available)
- Shots: ❌ Not available (FIBA HTML doesn't provide x,y coordinates)

Implementation Notes:
- Game IDs must be pre-collected (FIBA doesn't provide searchable game index)
- Uses BeautifulSoup for HTML parsing
- No authentication required (public pages)
- Gracefully handles missing/incomplete data

Dependencies:
- requests: HTTP client
- beautifulsoup4: HTML parsing
- pandas: Data manipulation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# FIBA LiveStats configuration
FIBA_LEAGUE_CODE = "NZN"  # NZ NBL code in FIBA LiveStats
FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"

# Game index paths (pre-built mapping of games)
DEFAULT_GAME_INDEX_PARQUET = Path("data/nz_nbl_game_index.parquet")
DEFAULT_GAME_INDEX_CSV = Path("data/nz_nbl_game_index.csv")

# Try to import optional dependencies
try:
    import requests
    from bs4 import BeautifulSoup

    HTML_PARSING_AVAILABLE = True
except ImportError:
    HTML_PARSING_AVAILABLE = False
    logger.warning(
        "HTML parsing dependencies not available. "
        "Install with: uv pip install requests beautifulsoup4\n"
        "NZ-NBL data fetching requires these packages."
    )


# ==============================================================================
# Game Index Management
# ==============================================================================


def load_game_index(index_path: Path | None = None) -> pd.DataFrame:
    """Load pre-built NZ-NBL game index

    The game index is a manually curated mapping of NZ-NBL games to FIBA game IDs.
    This is necessary because FIBA LiveStats doesn't provide a searchable schedule API.

    Args:
        index_path: Path to game index file (default: auto-detect .parquet or .csv)

    Returns:
        DataFrame with game index

    Columns:
        - SEASON: Season string (e.g., "2024")
        - GAME_ID: FIBA game ID
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score (if known)
        - AWAY_SCORE: Away team final score (if known)

    Example:
        >>> index = load_game_index()
        >>> print(f"Loaded {len(index)} NZ-NBL games")
    """
    # Auto-detect format if no path specified
    if index_path is None:
        if DEFAULT_GAME_INDEX_PARQUET.exists():
            index_path = DEFAULT_GAME_INDEX_PARQUET
        elif DEFAULT_GAME_INDEX_CSV.exists():
            index_path = DEFAULT_GAME_INDEX_CSV
        else:
            logger.warning(
                "NZ-NBL game index not found. Checked:\n"
                f"  - {DEFAULT_GAME_INDEX_PARQUET}\n"
                f"  - {DEFAULT_GAME_INDEX_CSV}\n"
                "Create game index first. See documentation for details."
            )
            return pd.DataFrame(
                columns=["SEASON", "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE"]
            )

    if not index_path.exists():
        logger.warning(f"NZ-NBL game index not found: {index_path}")
        return pd.DataFrame(
            columns=["SEASON", "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE"]
        )

    try:
        # Load based on file extension
        if index_path.suffix == ".parquet":
            df = pd.read_parquet(index_path)
        elif index_path.suffix == ".csv":
            df = pd.read_csv(index_path)
            # Convert GAME_DATE to datetime
            if "GAME_DATE" in df.columns:
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        else:
            logger.error(f"Unsupported game index format: {index_path.suffix}")
            return pd.DataFrame()

        logger.info(f"Loaded {len(df)} games from NZ-NBL game index ({index_path.name})")
        return df

    except Exception as e:
        logger.error(f"Failed to load NZ-NBL game index: {e}")
        return pd.DataFrame()


# ==============================================================================
# FIBA LiveStats HTML Scraping
# ==============================================================================


def _scrape_fiba_box_score(game_id: str) -> pd.DataFrame:
    """Scrape box score from FIBA LiveStats HTML

    Args:
        game_id: FIBA game ID

    Returns:
        DataFrame with player box scores

    Note:
        This is a scaffold implementation. Full HTML parsing to be implemented.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    url = f"{FIBA_BASE_URL}/u/{FIBA_LEAGUE_CODE}/{game_id}/bs.html"
    logger.info(f"Scraping NZ-NBL box score: {url}")

    try:
        rate_limiter.acquire("fiba_livestats")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # TODO: Implement HTML parsing to extract player stats
        # Expected structure:
        # - Find player stat tables (usually <table> with specific class)
        # - Extract rows with player names, minutes, points, rebounds, etc.
        # - Normalize to standard schema

        logger.warning(f"HTML parsing not yet implemented for game {game_id}")
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Failed to scrape box score for game {game_id}: {e}")
        return pd.DataFrame()


def _scrape_fiba_play_by_play(game_id: str) -> pd.DataFrame:
    """Scrape play-by-play from FIBA LiveStats HTML

    Args:
        game_id: FIBA game ID

    Returns:
        DataFrame with play-by-play events

    Note:
        This is a scaffold implementation. Full HTML parsing to be implemented.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    url = f"{FIBA_BASE_URL}/u/{FIBA_LEAGUE_CODE}/{game_id}/pbp.html"
    logger.info(f"Scraping NZ-NBL play-by-play: {url}")

    try:
        rate_limiter.acquire("fiba_livestats")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # TODO: Implement HTML parsing to extract play-by-play events
        # Expected structure:
        # - Find event tables grouped by quarter
        # - Extract time, team, player, action, score
        # - Normalize to standard schema

        logger.warning(f"HTML parsing not yet implemented for game {game_id}")
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Failed to scrape play-by-play for game {game_id}: {e}")
        return pd.DataFrame()


# ==============================================================================
# Public Fetcher Functions
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_schedule(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL schedule from pre-built game index

    Args:
        season: Season string (e.g., "2024" for 2024 season)

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: FIBA game identifier
        - SEASON: Season string
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (if available)
        - AWAY_SCORE: Away team score (if available)
        - LEAGUE: "NZ-NBL"

    Example:
        >>> schedule = fetch_nz_nbl_schedule("2024")
        >>> print(f"Found {len(schedule)} NZ-NBL games")
    """
    logger.info(f"Fetching NZ-NBL schedule: {season}")

    # Load game index
    index = load_game_index()

    if index.empty:
        logger.warning("NZ-NBL game index is empty")
        return _empty_schedule_df()

    # Filter by season
    df = index[index["SEASON"] == season].copy()

    # Add league identifier
    df["LEAGUE"] = "NZ-NBL"

    logger.info(f"Fetched {len(df)} NZ-NBL games for {season}")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_player_game(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL player-game box scores via FIBA LiveStats HTML scraping

    Args:
        season: Season string (e.g., "2024")

    Returns:
        DataFrame with player-game box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID (if available)
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - MIN: Minutes played
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Note:
        Aggregates box scores from all games in the season.
        HTML parsing implementation pending.
    """
    logger.info(f"Fetching NZ-NBL player-game box scores: {season}")

    # Get schedule for season
    schedule = fetch_nz_nbl_schedule(season)

    if schedule.empty:
        logger.warning(f"No NZ-NBL games found for {season}")
        return _empty_player_game_df()

    # Scrape box scores for all games
    frames: list[pd.DataFrame] = []
    for game_id in schedule["GAME_ID"]:
        box_score = _scrape_fiba_box_score(game_id)
        if not box_score.empty:
            box_score["GAME_ID"] = game_id
            box_score["LEAGUE"] = "NZ-NBL"
            box_score["SEASON"] = season
            frames.append(box_score)

    if not frames:
        logger.warning(f"No box score data scraped for {season}")
        return _empty_player_game_df()

    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Fetched {len(df)} NZ-NBL player-game records for {season}")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_team_game(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL team-game box scores

    Aggregates player stats per (GAME_ID, TEAM).

    Args:
        season: Season string (e.g., "2024")

    Returns:
        DataFrame with team-game box scores

    Columns:
        - GAME_ID: Game identifier
        - TEAM: Team name
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string
    """
    logger.info(f"Fetching NZ-NBL team-game box scores: {season}")

    # Get player-game data
    player_game = fetch_nz_nbl_player_game(season)

    if player_game.empty:
        logger.warning(f"No player-game data for {season}")
        return _empty_team_game_df()

    # Aggregate by game and team
    stat_cols = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    available_cols = [col for col in stat_cols if col in player_game.columns]

    team_game = player_game.groupby(["GAME_ID", "TEAM"], as_index=False)[available_cols].sum()

    # Recalculate shooting percentages
    if "FGM" in team_game.columns and "FGA" in team_game.columns:
        team_game["FG_PCT"] = (team_game["FGM"] / team_game["FGA"] * 100).fillna(0)
    if "FG3M" in team_game.columns and "FG3A" in team_game.columns:
        team_game["FG3_PCT"] = (team_game["FG3M"] / team_game["FG3A"] * 100).fillna(0)
    if "FTM" in team_game.columns and "FTA" in team_game.columns:
        team_game["FT_PCT"] = (team_game["FTM"] / team_game["FTA"] * 100).fillna(0)

    # Add metadata
    team_game["LEAGUE"] = "NZ-NBL"
    team_game["SEASON"] = season

    logger.info(f"Fetched {len(team_game)} NZ-NBL team-game records for {season}")
    return team_game


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_pbp(season: str = "2024", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NZ-NBL play-by-play data via FIBA LiveStats HTML scraping

    Args:
        season: Season string (e.g., "2024")
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
        - EVENT_TYPE: Type of event
        - DESCRIPTION: Event description
        - SCORE_HOME: Home team score after event
        - SCORE_AWAY: Away team score after event
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Note:
        HTML parsing implementation pending.
    """
    logger.info(f"Fetching NZ-NBL play-by-play: {season}, game_id={game_id}")

    if game_id:
        # Single game
        pbp = _scrape_fiba_play_by_play(game_id)
        if not pbp.empty:
            pbp["GAME_ID"] = game_id
            pbp["LEAGUE"] = "NZ-NBL"
            pbp["SEASON"] = season
        return pbp

    else:
        # All games in season
        schedule = fetch_nz_nbl_schedule(season)

        if schedule.empty:
            logger.warning(f"No NZ-NBL games found for {season}")
            return _empty_pbp_df()

        frames: list[pd.DataFrame] = []
        for gid in schedule["GAME_ID"]:
            pbp = _scrape_fiba_play_by_play(gid)
            if not pbp.empty:
                pbp["GAME_ID"] = gid
                pbp["LEAGUE"] = "NZ-NBL"
                pbp["SEASON"] = season
                frames.append(pbp)

        if not frames:
            logger.warning(f"No play-by-play data scraped for {season}")
            return _empty_pbp_df()

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"Fetched {len(df)} NZ-NBL play-by-play events for {season}")
        return df


# ==============================================================================
# Empty DataFrame Helpers
# ==============================================================================


def _empty_schedule_df() -> pd.DataFrame:
    """Return empty DataFrame with schedule schema"""
    return pd.DataFrame(
        columns=["GAME_ID", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE", "LEAGUE"]
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
