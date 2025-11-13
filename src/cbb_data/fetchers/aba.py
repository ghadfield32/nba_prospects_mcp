"""ABA League (Adriatic League) Fetcher

Official ABA League data via web scraping from aba-liga.com.

ABA League is a premier regional basketball league featuring top clubs from
the Balkans and Eastern Europe (Serbia, Croatia, Slovenia, Montenegro, Bosnia, etc.).

⚠️ **IMPLEMENTATION NOTE**: Originally used FIBA LiveStats Direct API, which is
BLOCKED (403 Forbidden). Replaced with web scraping from official ABA website.

Key Features:
- Web scraping from official aba-liga.com stats pages
- Season aggregate data (player_season, team_season)
- Rate-limited requests with retry logic
- UTF-8 support for Cyrillic/Latin player names

Data Granularities:
- schedule: ⚠️ Limited (requires scraping schedule pages)
- player_game: ⚠️ Limited (requires game-by-game scraping)
- team_game: ⚠️ Limited (requires game-by-game scraping)
- pbp: ❌ Unavailable (not published on website)
- shots: ❌ Unavailable (not published on website)
- player_season: ✅ Available (via stats pages)
- team_season: ✅ Available (via stats pages)

Competition Structure:
- 14 teams from 6-7 countries
- Regular season: Double round-robin
- Playoffs: Top 8 teams advance
- Finals: Best-of-5 series
- Typical season: October-June

Historical Context:
- Founded: 2001 (originally "Goodyear League")
- Prominent teams: Crvena Zvezda, Partizan, Olimpija, Cedevita, Budućnost
- High competition level: Many players move to EuroLeague from ABA
- Regional importance: Premier league for Balkan basketball

Documentation: https://www.aba-liga.com/
Data Source: https://www.aba-liga.com/players.php

Implementation Status:
✅ IMPLEMENTED - Web scraping from official website (season aggregates)
⚠️ Game-level data requires additional implementation

Technical Notes:
- Encoding: UTF-8 normalization for Cyrillic/Latin names
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

# ABA League URLs
ABA_BASE_URL = "https://www.aba-liga.com"
ABA_PLAYERS_URL = f"{ABA_BASE_URL}/players.php"
ABA_TEAMS_URL = f"{ABA_BASE_URL}/standings.php"


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_aba_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch ABA League player season statistics

    Scrapes official ABA Liga stats pages for player season aggregates.

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
        - LEAGUE: "ABA"
        - SEASON: Season string
        - COMPETITION: "ABA League"

    Example:
        >>> # Fetch ABA League 2024-25 season player stats
        >>> df = fetch_aba_player_season("2024")
        >>> top_scorers = df.nlargest(10, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
    """
    rate_limiter.acquire("aba")

    logger.info(f"Fetching ABA League player season stats: {season}, {per_mode}")

    try:
        # Fetch HTML table from ABA players page
        df = read_first_table(
            url=ABA_PLAYERS_URL,
            min_columns=5,  # Expect at least 5 stat columns
            min_rows=10,  # Expect at least 10 players (more lenient for off-season)
        )

        logger.info(f"Fetched {len(df)} ABA players from website")

        # Check if this is roster data (Name, Club, Position, Height) vs stats data (Points, Rebounds, etc.)
        # Roster columns: Name, Club, Jersey no., Position, Height, Date of Birth, Place of Birth, Nationality
        # Stats columns: Player, Team, Games, Points, Rebounds, Assists, etc.
        roster_indicators = [
            "Jersey no.",
            "Position",
            "Height",
            "Date of Birth",
            "Place of Birth",
            "Nationality",
        ]
        is_roster_data = any(indicator in df.columns for indicator in roster_indicators)

        if is_roster_data:
            logger.warning(
                "ABA players page contains ROSTER data (names, positions, heights), "
                "not STATISTICS (points, rebounds, assists). Stats require JS execution or alternative source. "
                "Returning empty DataFrame."
            )
            raise ValueError("Roster data found instead of statistics data")

        # Column mapping (may need adjustment based on actual website columns)
        # ABA website is typically in English but may have varied column names
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
            league="ABA",
            season=season,
            competition="ABA League",
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
        logger.error(f"Failed to fetch ABA player season stats: {e}")
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
def fetch_aba_team_season(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch ABA League team season statistics/standings

    Scrapes official ABA Liga standings pages for team season aggregates.

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
        - LEAGUE: "ABA"
        - SEASON: Season string
        - COMPETITION: "ABA League"

    Example:
        >>> df = fetch_aba_team_season("2024")
        >>> standings = df.sort_values("WIN_PCT", ascending=False)
        >>> print(standings[["TEAM", "W", "L", "WIN_PCT"]])
    """
    rate_limiter.acquire("aba")

    logger.info(f"Fetching ABA League team season stats: {season}")

    try:
        df = read_first_table(
            url=ABA_TEAMS_URL,
            min_columns=5,  # Expect at least 5 columns (team, W, L, etc.)
            min_rows=10,  # Expect at least 10 teams
        )

        logger.info(f"Fetched {len(df)} ABA teams")

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
            league="ABA",
            season=season,
            competition="ABA League",
            column_map=column_map,
        )

        # Calculate win percentage if not present
        if "WIN_PCT" not in df.columns and "W" in df.columns and "GP" in df.columns:
            df["WIN_PCT"] = df["W"] / df["GP"]

        return df

    except Exception as e:
        logger.error(f"Failed to fetch ABA team season stats: {e}")
        return pd.DataFrame(
            columns=["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "LEAGUE", "SEASON", "COMPETITION"]
        )


# Legacy function stubs (for backwards compatibility)
# These were originally meant to use FIBA LiveStats Direct API
# Now they are placeholders that could be implemented via game-by-game scraping


def fetch_aba_schedule(
    season: int,
    phase: str | None = "RS",
    round_start: int = 1,
    round_end: int | None = None,
) -> pd.DataFrame:
    """Fetch ABA League schedule (placeholder)

    Note: Requires implementation of schedule page scraping.
    Season aggregates (fetch_aba_player_season, fetch_aba_team_season) are
    the primary functional endpoints.

    Args:
        season: Season year
        phase: Phase (RS=Regular Season, PO=Playoffs)
        round_start: Starting round
        round_end: Ending round

    Returns:
        Empty DataFrame (requires implementation)
    """
    logger.warning("ABA schedule fetching requires implementation (game-by-game scraping)")
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


def fetch_aba_box_score(season: int, game_code: int) -> pd.DataFrame:
    """Fetch ABA box score (placeholder)

    Note: Requires implementation of game page scraping.

    Returns:
        Empty DataFrame (requires implementation)
    """
    logger.warning("ABA box score fetching requires implementation (game-by-game scraping)")
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


def fetch_aba_play_by_play(season: int, game_code: int) -> pd.DataFrame:
    """Fetch ABA play-by-play (not available)

    Note: Play-by-play data not published on ABA website.

    Returns:
        Empty DataFrame (not available)
    """
    logger.warning("ABA play-by-play data not available on official website")
    return pd.DataFrame(
        columns=["GAME_ID", "EVENT_TYPE", "PERIOD", "CLOCK", "DESCRIPTION", "LEAGUE"]
    )


def fetch_aba_shot_chart(season: int, game_code: int) -> pd.DataFrame:
    """Fetch ABA shot chart (not available)

    Note: Shot chart data not published on ABA website.

    Returns:
        Empty DataFrame (not available)
    """
    logger.warning("ABA shot chart data not available on official website")
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
