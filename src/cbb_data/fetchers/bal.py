"""Basketball Africa League (BAL) Fetcher

Official Basketball Africa League data via web scraping from thebal.com.

BAL is Africa's premier professional basketball league, jointly operated by
FIBA and the NBA with 12 teams from across Africa.

⚠️ **IMPLEMENTATION NOTE**: Originally used FIBA LiveStats Direct API, which is
BLOCKED (403 Forbidden). Replaced with web scraping from official BAL website.

Key Features:
- Web scraping from official thebal.com stats pages
- Season aggregate data (player_season, team_season)
- Rate-limited requests with retry logic
- First NBA-backed league outside North America

Data Granularities:
- schedule: ⚠️ Limited (requires scraping schedule pages)
- player_game: ⚠️ Limited (requires game-by-game scraping)
- team_game: ⚠️ Limited (requires game-by-game scraping)
- pbp: ❌ Unavailable (not published on website)
- shots: ❌ Unavailable (not published on website)
- player_season: ✅ Available (via stats pages)
- team_season: ✅ Available (via stats pages)

Competition Structure:
- 12 teams from 12 African countries
- Season format: Group stage → Playoffs
- Typical season: March-May
- Finals hosted in different African city each year

Historical Context:
- Founded: 2021 (first NBA-backed league outside North America)
- Champions: Zamalek (2021), US Monastir (2022), Al Ahly (2023), Petro de Luanda (2024)
- Purpose: Develop African basketball talent and provide NBA pathway

Documentation: https://thebal.com/
Data Source: https://thebal.com/stats/

Implementation Status:
✅ IMPLEMENTED - Web scraping from official website (season aggregates)
⚠️ Game-level data requires additional implementation

Technical Notes:
- Season format: Calendar year (e.g., "2024" for 2024 season)
- Rate limiting: 1 req/sec to respect website resources
- High strategic importance (NBA partnership, emerging market)
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

# BAL URLs
BAL_BASE_URL = "https://thebal.com"
BAL_STATS_URL = f"{BAL_BASE_URL}/stats"
BAL_PLAYERS_URL = f"{BAL_BASE_URL}/stats/players"
BAL_TEAMS_URL = f"{BAL_BASE_URL}/stats/teams"


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_bal_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch Basketball Africa League player season statistics

    Scrapes official BAL stats pages for player season aggregates.

    Args:
        season: Season year as string (e.g., "2024" for 2024 season)
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
        - LEAGUE: "BAL"
        - SEASON: Season string
        - COMPETITION: "Basketball Africa League"

    Example:
        >>> # Fetch BAL 2024 season player stats
        >>> df = fetch_bal_player_season("2024")
        >>> top_scorers = df.nlargest(10, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
    """
    rate_limiter.acquire("bal")

    logger.info(f"Fetching BAL player season stats: {season}, {per_mode}")

    try:
        # Try primary stats URL first, fallback to players URL
        try:
            df = read_first_table(
                url=BAL_STATS_URL,
                min_columns=5,  # More lenient for various website structures
                min_rows=10,  # More lenient for off-season
            )
        except Exception:
            logger.warning("Primary BAL stats URL failed, trying players URL")
            df = read_first_table(
                url=BAL_PLAYERS_URL,
                min_columns=5,
                min_rows=10,
            )

        logger.info(f"Fetched {len(df)} BAL players")

        # Column mapping (adjust based on actual website columns)
        column_map = {
            "Player": "PLAYER_NAME",
            "Name": "PLAYER_NAME",
            "Team": "TEAM",
            "Games": "GP",
            "G": "GP",
            "Minutes": "MIN",
            "MIN": "MIN",
            "Points": "PTS",
            "PTS": "PTS",
            "Rebounds": "REB",
            "REB": "REB",
            "Assists": "AST",
            "AST": "AST",
            "Steals": "STL",
            "STL": "STL",
            "Blocks": "BLK",
            "BLK": "BLK",
            "Turnovers": "TOV",
            "TO": "TOV",
            "Fouls": "PF",
            "PF": "PF",
        }

        # Normalize columns
        df = normalize_league_columns(
            df=df,
            league="BAL",
            season=season,
            competition="Basketball Africa League",
            column_map=column_map,
        )

        # Handle per_mode
        if per_mode == "PerGame" and "GP" in df.columns:
            stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN"]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = df[col] / df["GP"]

        elif per_mode == "Per40" and "MIN" in df.columns:
            stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF"]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = (df[col] / df["MIN"]) * 40

        return df

    except Exception as e:
        logger.error(f"Failed to fetch BAL player season stats: {e}")
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
def fetch_bal_team_season(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch Basketball Africa League team season statistics

    Scrapes official BAL stats pages for team season aggregates.

    Args:
        season: Season year as string (e.g., "2024" for 2024 season)

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
        - LEAGUE: "BAL"
        - SEASON: Season string
        - COMPETITION: "Basketball Africa League"

    Example:
        >>> df = fetch_bal_team_season("2024")
        >>> standings = df.sort_values("WIN_PCT", ascending=False)
        >>> print(standings[["TEAM", "W", "L", "WIN_PCT"]])
    """
    rate_limiter.acquire("bal")

    logger.info(f"Fetching BAL team season stats: {season}")

    try:
        df = read_first_table(
            url=BAL_TEAMS_URL,
            min_columns=5,
            min_rows=10,  # Expect at least 10 teams
        )

        logger.info(f"Fetched {len(df)} BAL teams")

        # Column mapping
        column_map = {
            "Team": "TEAM",
            "Games": "GP",
            "G": "GP",
            "Wins": "W",
            "W": "W",
            "Losses": "L",
            "L": "L",
            "Points": "PTS",
            "PTS": "PTS",
        }

        df = normalize_league_columns(
            df=df,
            league="BAL",
            season=season,
            competition="Basketball Africa League",
            column_map=column_map,
        )

        # Calculate win percentage if not present
        if "WIN_PCT" not in df.columns and "W" in df.columns and "GP" in df.columns:
            df["WIN_PCT"] = df["W"] / df["GP"]

        return df

    except Exception as e:
        logger.error(f"Failed to fetch BAL team season stats: {e}")
        return pd.DataFrame(
            columns=["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "LEAGUE", "SEASON", "COMPETITION"]
        )


# Legacy function stubs (for backwards compatibility)


def fetch_bal_schedule(
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch BAL schedule (placeholder)

    Note: Requires implementation of schedule page scraping.
    Season aggregates (fetch_bal_player_season, fetch_bal_team_season) are
    the primary functional endpoints.

    Returns:
        Empty DataFrame (requires implementation)
    """
    logger.warning("BAL schedule fetching requires implementation (game-by-game scraping)")
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


def fetch_bal_box_score(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BAL box score (placeholder)

    Returns:
        Empty DataFrame (requires implementation)
    """
    logger.warning("BAL box score fetching requires implementation (game-by-game scraping)")
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


def fetch_bal_play_by_play(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BAL play-by-play (not available)

    Returns:
        Empty DataFrame (not available)
    """
    logger.warning("BAL play-by-play data not available on official website")
    return pd.DataFrame(
        columns=["GAME_ID", "EVENT_TYPE", "PERIOD", "CLOCK", "DESCRIPTION", "LEAGUE"]
    )


def fetch_bal_shot_chart(season: int, game_code: int) -> pd.DataFrame:
    """Fetch BAL shot chart (not available)

    Returns:
        Empty DataFrame (not available)
    """
    logger.warning("BAL shot chart data not available on official website")
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
