"""NJCAA (National Junior College Athletic Association) Basketball Fetcher

NJCAA governs junior college basketball in the United States (two-year colleges).
Uses the PrestoSports platform for stats.

Key Features:
- US junior college basketball (two-year colleges)
- PrestoSports platform infrastructure
- Multiple divisions (DI, DII, DIII) and regional conferences
- Important pre-NBA prospect pipeline (many NBA players start at JUCO level)

Data Granularities:
- schedule: ⚠️ Limited (PrestoSports scaffold)
- player_game: ⚠️ Limited (PrestoSports scaffold)
- team_game: ⚠️ Limited (PrestoSports scaffold)
- pbp: ❌ Unavailable (PrestoSports doesn't provide PBP)
- shots: ❌ Unavailable (no shot coordinates)
- player_season: ✅ Available (PrestoSports season leaders)
- team_season: ✅ Available (via generic aggregation)

Data Source: https://njcaastats.prestosports.com/sports/mbkb/

Implementation Status:
- Season stats via PrestoSports platform (functional)
- Schedule/box scores: scaffold (requires PrestoSports HTML parsing)

Platform: PrestoSports
"""

from __future__ import annotations

import logging

import pandas as pd

from .base import cached_dataframe, retry_on_error
from .prestosports import (
    fetch_prestosports_box_score,
    fetch_prestosports_play_by_play,
    fetch_prestosports_schedule,
    fetch_prestosports_season_leaders,
    fetch_prestosports_shot_chart,
)

logger = logging.getLogger(__name__)

# League identifier in PrestoSports config
PRESTOSPORTS_LEAGUE_CODE = "NJCAA"
LEAGUE_CODE = "NJCAA"


# =============================================================================
# Core Data Functions (delegating to PrestoSports infrastructure)
# =============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_schedule(season: str = "2024-25", division: str | None = None) -> pd.DataFrame:
    """Fetch NJCAA schedule

    Args:
        season: Season string (e.g., "2024-25")
        division: Optional division filter (NJCAA has DI, DII, DIII)

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID, SEASON, GAME_DATE
        - HOME_TEAM_ID, HOME_TEAM, AWAY_TEAM_ID, AWAY_TEAM
        - HOME_SCORE, AWAY_SCORE, VENUE
        - LEAGUE: "NJCAA"
    """
    logger.info(f"Fetching {LEAGUE_CODE} schedule: {season}, division={division}")

    df = fetch_prestosports_schedule(PRESTOSPORTS_LEAGUE_CODE, season, division=division)

    # Standardize league code
    if not df.empty:
        df["LEAGUE"] = LEAGUE_CODE

    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_player_game(season: str = "2024-25", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NJCAA player game stats

    Note: Currently scaffold. Requires PrestoSports box score scraping.

    Args:
        season: Season string
        game_id: Optional specific game ID

    Returns:
        DataFrame with player game stats
    """
    logger.info(f"Fetching {LEAGUE_CODE} player game stats: {season}, game_id={game_id}")

    if game_id:
        df = fetch_prestosports_box_score(PRESTOSPORTS_LEAGUE_CODE, game_id)
        if not df.empty:
            df["LEAGUE"] = LEAGUE_CODE
            df["SEASON"] = season
        return df

    # No game_id: return empty (would need to iterate over schedule)
    logger.warning(f"{LEAGUE_CODE} player_game requires game_id parameter")
    df = pd.DataFrame()
    df["LEAGUE"] = LEAGUE_CODE
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_team_game(season: str = "2024-25", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NJCAA team game stats

    Note: Aggregated from player game stats (scaffold)

    Args:
        season: Season string
        game_id: Optional specific game ID

    Returns:
        DataFrame with team game stats
    """
    logger.info(f"Fetching {LEAGUE_CODE} team game stats: {season}, game_id={game_id}")

    # Would aggregate from player_game
    logger.warning(f"{LEAGUE_CODE} team_game uses generic aggregation")
    df = pd.DataFrame()
    df["LEAGUE"] = LEAGUE_CODE
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_pbp(season: str = "2024-25", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NJCAA play-by-play (UNAVAILABLE)

    PrestoSports does not provide detailed play-by-play data.

    Args:
        season: Season string
        game_id: Game ID

    Returns:
        Empty DataFrame with PBP schema
    """
    if game_id:
        df = fetch_prestosports_play_by_play(PRESTOSPORTS_LEAGUE_CODE, game_id)
        if not df.empty:
            df["LEAGUE"] = LEAGUE_CODE
            df["SEASON"] = season
        return df

    df = pd.DataFrame()
    df["LEAGUE"] = LEAGUE_CODE
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_player_season(
    season: str = "2024-25",
    stat_category: str = "points",
    division: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Fetch NJCAA player season stats

    **IMPLEMENTED**: Uses PrestoSports season leaders infrastructure.

    Args:
        season: Season string (e.g., "2024-25")
        stat_category: Stat category (scoring, rebounding, assists, etc.)
        division: Optional division filter (NJCAA has DI, DII, DIII)
        limit: Optional limit on results

    Returns:
        DataFrame with player season stats

    Columns:
        - PLAYER_ID, PLAYER_NAME, TEAM, YEAR, GP
        - Stats depend on category (PTS, REB, AST, etc.)
        - LEAGUE: "NJCAA"
    """
    logger.info(
        f"Fetching {LEAGUE_CODE} player season: {season}, stat={stat_category}, "
        f"division={division}, limit={limit}"
    )

    df = fetch_prestosports_season_leaders(
        PRESTOSPORTS_LEAGUE_CODE,
        season=season,
        stat_category=stat_category,
        division=division,
        limit=limit,
    )

    # Standardize league code
    if not df.empty:
        df["LEAGUE"] = LEAGUE_CODE
        df["SEASON"] = season

    logger.info(f"Fetched {len(df)} {LEAGUE_CODE} player season records")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_team_season(season: str = "2024-25", division: str | None = None) -> pd.DataFrame:
    """Fetch NJCAA team season stats

    Note: Uses generic aggregation from player_game

    Args:
        season: Season string
        division: Optional division filter

    Returns:
        DataFrame with team season stats
    """
    logger.info(f"Fetching {LEAGUE_CODE} team season: {season}, division={division}")

    # Would aggregate from player_game
    logger.warning(f"{LEAGUE_CODE} team_season uses generic aggregation")
    df = pd.DataFrame()
    df["LEAGUE"] = LEAGUE_CODE
    return df


# Unavailable endpoints
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_shots(season: str = "2024-25", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NJCAA shot chart (UNAVAILABLE)

    PrestoSports does not provide shot coordinate data.

    Args:
        season: Season string
        game_id: Game ID

    Returns:
        Empty DataFrame with shot schema
    """
    if game_id:
        df = fetch_prestosports_shot_chart(PRESTOSPORTS_LEAGUE_CODE, game_id)
        if not df.empty:
            df["LEAGUE"] = LEAGUE_CODE
            df["SEASON"] = season
        return df

    df = pd.DataFrame()
    df["LEAGUE"] = LEAGUE_CODE
    return df
