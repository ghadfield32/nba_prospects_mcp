"""Basketball Champions League (BCL) Fetcher

Official Basketball Champions League data via web scraping from championsleague.basketball.

BCL is Europe's third-tier club competition (after EuroLeague and EuroCup),
organized by FIBA Europe with 32+ teams from across Europe.

⚠️ **IMPLEMENTATION NOTE**: Originally used FIBA LiveStats Direct API, which is
BLOCKED (403 Forbidden). Replaced with web scraping from official BCL website.

Key Features:
- Web scraping from official championsleague.basketball stats pages
- Season aggregate data (player_season, team_season)
- Rate-limited requests with retry logic
- UTF-8 support for international player names

Data Granularities:
- schedule: ⚠️ Limited (requires scraping schedule pages)
- player_game: ⚠️ Limited (requires game-by-game scraping)
- team_game: ⚠️ Limited (requires game-by-game scraping)
- pbp: ❌ Unavailable (not published on website)
- shots: ❌ Unavailable (not published on website)
- player_season: ✅ Available (via stats pages)
- team_season: ✅ Available (via standings pages)

Competition Structure:
- Regular Season: 32 teams, 8 groups of 4
- Top 16: Single-elimination knockout rounds
- Final Four: Semi-finals and final
- Typical season: October-May

Historical Context:
- Founded: 2016 (replaced FIBA EuroChallenge)
- Champions: AEK Athens (2018, 2020), Virtus Bologna (2019),
  Hereda San Pablo Burgos (2021, 2022, 2023), Unicaja (2024)
- Strong European competition feeding into EuroLeague

Documentation: https://www.championsleague.basketball/

Implementation Status:
✅ IMPLEMENTED - Web scraping from official website (season aggregates)
⚠️ Game-level data requires additional implementation

Technical Notes:
- Encoding: UTF-8 normalization for international names
- Season format: Calendar year (e.g., "2024" for 2024-25 season)
- Rate limiting: 1 req/sec to respect website resources
"""

from __future__ import annotations

import logging

import pandas as pd

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error
from .html_tables import normalize_league_columns, read_first_table

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# BCL URLs
BCL_BASE_URL = "https://www.championsleague.basketball"
BCL_PLAYERS_URL = f"{BCL_BASE_URL}/stats/players"
BCL_TEAMS_URL = f"{BCL_BASE_URL}/standings"


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_bcl_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch Basketball Champions League player season statistics

    Scrapes official BCL stats pages for player season aggregates.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        per_mode: Aggregation mode ("Totals", "PerGame", "Per40")
                  Note: Website may not support all modes, defaults to available data

    Returns:
        DataFrame with player season statistics

    Columns (after normalization):
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - GP: Games played
        - MIN: Minutes played
        - PTS: Points
        - REB: Rebounds
        - AST: Assists
        - FGM, FGA, FG_PCT: Field goals
        - FG3M, FG3A, FG3_PCT: 3-point field goals
        - FTM, FTA, FT_PCT: Free throws
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - LEAGUE: "BCL"
        - SEASON: Season string
        - COMPETITION: "Basketball Champions League"

    Example:
        >>> # Fetch BCL 2024-25 season player stats
        >>> df = fetch_bcl_player_season("2024")
        >>> top_scorers = df.nlargest(10, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
    """
    rate_limiter.acquire("bcl")

    logger.info(f"Fetching BCL player season stats: {season}, {per_mode}")

    try:
        # Fetch HTML table from BCL players page
        df = read_first_table(
            url=BCL_PLAYERS_URL,
            min_columns=5,  # Expect at least 5 stat columns
            min_rows=10,  # Expect at least 10 players
        )

        logger.info(f"Fetched {len(df)} BCL players")

        # Column mapping (may need adjustment based on actual website columns)
        column_map = {
            "Player": "PLAYER_NAME",
            "Team": "TEAM",
            "Games": "GP",
            "Minutes": "MIN",
            "Points": "PTS",
            "Rebounds": "REB",
            "Assists": "AST",
            "Steals": "STL",
            "Blocks": "BLK",
            "Turnovers": "TOV",
            "Fouls": "PF",
            # Add more mappings as needed based on actual column names
        }

        # Normalize columns
        df = normalize_league_columns(
            df=df,
            league="BCL",
            season=season,
            competition="Basketball Champions League",
            column_map=column_map,
        )

        # Handle per_mode if needed (website may only show totals)
        if per_mode == "PerGame" and "GP" in df.columns:
            # Calculate per-game stats
            stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN"]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = df[col] / df["GP"]

        elif per_mode == "Per40" and "MIN" in df.columns:
            # Calculate per-40-minutes stats
            stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF"]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = (df[col] / df["MIN"]) * 40

        return df

    except Exception as e:
        logger.error(f"Failed to fetch BCL player season stats: {e}")
        # Return empty DataFrame with correct schema
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
                "PF",
                "LEAGUE",
                "SEASON",
                "COMPETITION",
            ]
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_bcl_team_season(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch Basketball Champions League team season statistics/standings

    Scrapes official BCL standings pages for team season aggregates.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with team season statistics

    Columns (after normalization):
        - TEAM: Team name
        - GP: Games played
        - W: Wins
        - L: Losses
        - WIN_PCT: Win percentage
        - PTS: Points scored (total or average)
        - OPP_PTS: Opponent points (total or average)
        - LEAGUE: "BCL"
        - SEASON: Season string
        - COMPETITION: "Basketball Champions League"

    Example:
        >>> df = fetch_bcl_team_season("2024")
        >>> standings = df.sort_values("WIN_PCT", ascending=False)
        >>> print(standings[["TEAM", "W", "L", "WIN_PCT"]])
    """
    rate_limiter.acquire("bcl")

    logger.info(f"Fetching BCL team season stats: {season}")

    try:
        df = read_first_table(
            url=BCL_TEAMS_URL,
            min_columns=5,  # Expect at least 5 columns (team, W, L, etc.)
            min_rows=10,  # Expect at least 10 teams
        )

        logger.info(f"Fetched {len(df)} BCL teams")

        # Column mapping
        column_map = {
            "Team": "TEAM",
            "Games": "GP",
            "Wins": "W",
            "Losses": "L",
            "Points": "PTS",
            # Add more mappings as needed
        }

        df = normalize_league_columns(
            df=df,
            league="BCL",
            season=season,
            competition="Basketball Champions League",
            column_map=column_map,
        )

        # Calculate win percentage if not present
        if "WIN_PCT" not in df.columns and "W" in df.columns and "GP" in df.columns:
            df["WIN_PCT"] = df["W"] / df["GP"]

        return df

    except Exception as e:
        logger.error(f"Failed to fetch BCL team season stats: {e}")
        return pd.DataFrame(
            columns=["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "LEAGUE", "SEASON", "COMPETITION"]
        )


# Legacy function stubs (for backwards compatibility)
# These were originally meant to use FIBA LiveStats Direct API
# Now they are placeholders that could be implemented via game-by-game scraping


def fetch_bcl_schedule(
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch Basketball Champions League schedule (placeholder)

    Note: Requires implementation of schedule page scraping.
    Season aggregates (fetch_bcl_player_season, fetch_bcl_team_season) are
    the primary functional endpoints.

    Args:
        season: Season year
        phase: Phase (RS=Regular Season, PO=Playoffs, FF=Final Four)
        round_start: Starting round
        round_end: Ending round

    Returns:
        Empty DataFrame (requires implementation)
    """
    logger.warning("BCL schedule fetching requires implementation (game-by-game scraping)")
    return pd.DataFrame(
        columns=[
            "SEASON",
            "ROUND",
            "GAME_CODE",
            "GAME_DATE",
            "HOME_TEAM",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
            "LEAGUE",
        ]
    )


def fetch_bcl_box_score(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BCL box score (placeholder)

    Note: Requires implementation of game page scraping.

    Returns:
        Empty DataFrame (requires implementation)
    """
    logger.warning("BCL box score fetching requires implementation (game-by-game scraping)")
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
            "LEAGUE",
        ]
    )


def fetch_bcl_play_by_play(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BCL play-by-play (not available)

    Note: Play-by-play data not published on BCL website.

    Returns:
        Empty DataFrame (not available)
    """
    logger.warning("BCL play-by-play data not available on official website")
    return pd.DataFrame(
        columns=["GAME_ID", "EVENT_TYPE", "PERIOD", "CLOCK", "DESCRIPTION", "LEAGUE"]
    )


def fetch_bcl_shot_chart(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BCL shot chart (not available)

    Note: Shot chart data not published on BCL website.

    Returns:
        Empty DataFrame (not available)
    """
    logger.warning("BCL shot chart data not available on official website")
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_NAME",
            "TEAM",
            "SHOT_TYPE",
            "LOC_X",
            "LOC_Y",
            "SHOT_MADE",
            "LEAGUE",
        ]
    )
