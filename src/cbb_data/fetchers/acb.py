"""ACB (Liga Endesa - Spain) Fetcher

Official ACB (Spanish professional basketball) stats portal scraper.

ACB (Asociación de Clubes de Baloncesto) is Spain's top-tier professional basketball league,
featuring 18 teams. Known as "Liga Endesa" due to sponsorship, it's one of Europe's strongest
leagues. NBA talent pipeline includes Pau Gasol, Marc Gasol, Ricky Rubio, and many others.

⚠️ **DATA AVAILABILITY**:
- **Player/Team season stats**: ❌ Unavailable (JavaScript-rendered site)
- **Schedule/Box scores**: ⚠️ Limited (requires implementation)

Key Features:
- Web scraping from official acb.com pages
- Graceful degradation for JavaScript-rendered content
- Rate-limited requests with retry logic
- UTF-8 support for Spanish names (accents: á, é, í, ó, ú, ñ)

Data Granularities:
- schedule: ⚠️ Limited (requires HTML/API parsing)
- player_game: ⚠️ Limited (box scores require scraping)
- team_game: ⚠️ Limited (team stats require scraping)
- pbp: ❌ Unavailable (not published publicly)
- shots: ❌ Unavailable (not published publicly)
- player_season: ❌ Unavailable (JavaScript-rendered)
- team_season: ❌ Unavailable (JavaScript-rendered)

Competition Structure:
- Regular Season: 18 teams
- Playoffs: Top 8 teams advance to playoffs
- Finals: Best-of-5 series
- Typical season: October-June

Historical Context:
- Founded: 1957 (one of Europe's oldest leagues)
- Prominent teams: Real Madrid, Barcelona, Valencia, Baskonia
- NBA pipeline: Pau Gasol, Marc Gasol, Ricky Rubio, Sergio Llull
- Multiple EuroLeague titles by ACB teams

Documentation: https://www.acb.com/
Data Source: https://www.acb.com/estadisticas

Implementation Status:
✅ IMPLEMENTED - Season aggregate functions with graceful degradation
⚠️ JavaScript-rendered site requires Selenium/Playwright for actual data

Technical Notes:
- Website uses JavaScript frameworks (React/Angular)
- Static HTML scraping returns no tables
- Requires Selenium/Playwright or API discovery for implementation
- Rate limiting: 1 req/sec to respect website resources
- Encoding: UTF-8 for Spanish names (á, é, í, ó, ú, ñ)
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

# ACB URLs
ACB_BASE_URL = "https://www.acb.com"
ACB_STATS_URL = f"{ACB_BASE_URL}/estadisticas"
ACB_PLAYERS_URL = f"{ACB_BASE_URL}/estadisticas/jugadores"
ACB_TEAMS_URL = f"{ACB_BASE_URL}/clasificacion"


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch ACB (Liga Endesa) player season statistics

    ⚠️ LIMITATION: ACB website uses JavaScript-rendered statistics.
    Returns empty DataFrame with correct schema for graceful degradation.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        per_mode: Aggregation mode ("Totals", "PerGame", "Per40")

    Returns:
        DataFrame with player season statistics (empty for JS-rendered site)

    Columns (schema only):
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - GP: Games played
        - MIN: Minutes played
        - PTS: Points
        - REB: Rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - LEAGUE: "ACB"
        - SEASON: Season string
        - COMPETITION: "Liga Endesa"

    Note:
        Requires Selenium/Playwright or API discovery for actual implementation.
        See LEAGUE_WEB_SCRAPING_FINDINGS.md for details.
    """
    rate_limiter.acquire("acb")

    logger.info(f"Fetching ACB player season stats: {season}, {per_mode}")

    try:
        # Attempt to fetch HTML table (will fail for JS-rendered site)
        df = read_first_table(
            url=ACB_PLAYERS_URL,
            min_columns=5,
            min_rows=10,
        )

        # Spanish column names mapping
        column_map = {
            "Jugador": "PLAYER_NAME",
            "Equipo": "TEAM",
            "Partidos": "GP",
            "Minutos": "MIN",
            "Puntos": "PTS",
            "Rebotes": "REB",
            "Asistencias": "AST",
            "Robos": "STL",
            "Tapones": "BLK",
            "Pérdidas": "TOV",
            "Faltas": "PF",
        }

        df = normalize_league_columns(
            df=df,
            league="ACB",
            season=season,
            competition="Liga Endesa",
            column_map=column_map,
        )

        # Optional per_mode calculations
        if per_mode == "PerGame" and "GP" in df.columns:
            stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN"]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = df[col] / df["GP"]

        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB player season stats: {e}")
        # Return empty DataFrame with correct schema (graceful degradation)
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
def fetch_acb_team_season(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch ACB (Liga Endesa) team season statistics/standings

    ⚠️ LIMITATION: ACB website uses JavaScript-rendered statistics.
    Returns empty DataFrame with correct schema for graceful degradation.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with team season statistics (empty for JS-rendered site)

    Columns (schema only):
        - TEAM: Team name
        - GP: Games played
        - W: Wins
        - L: Losses
        - WIN_PCT: Win percentage
        - PTS: Points scored
        - OPP_PTS: Opponent points
        - LEAGUE: "ACB"
        - SEASON: Season string
        - COMPETITION: "Liga Endesa"

    Note:
        Requires Selenium/Playwright or API discovery for actual implementation.
    """
    rate_limiter.acquire("acb")

    logger.info(f"Fetching ACB team season stats: {season}")

    try:
        df = read_first_table(
            url=ACB_TEAMS_URL,
            min_columns=5,
            min_rows=5,
        )

        # Spanish column names mapping
        column_map = {
            "Equipo": "TEAM",
            "Partidos": "GP",
            "Victorias": "W",
            "Derrotas": "L",
            "Puntos": "PTS",
        }

        df = normalize_league_columns(
            df=df,
            league="ACB",
            season=season,
            competition="Liga Endesa",
            column_map=column_map,
        )

        # Calculate win percentage if not present
        if "WIN_PCT" not in df.columns and "W" in df.columns and "GP" in df.columns:
            df["WIN_PCT"] = df["W"] / df["GP"]

        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB team season stats: {e}")
        return pd.DataFrame(
            columns=["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "LEAGUE", "SEASON", "COMPETITION"]
        )


# Legacy scaffold functions (kept for backwards compatibility)


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_schedule(
    season: str = "2024-25",
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Fetch ACB schedule (placeholder)

    Note: Requires HTML/API parsing implementation. Currently returns empty
    DataFrame with correct schema.

    Args:
        season: Season string (e.g., "2024-25")
        season_type: Season type ("Regular Season", "Playoffs")

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: Unique game identifier
        - SEASON: Season string
        - GAME_DATE: Game date/time
        - HOME_TEAM_ID: Home team ID
        - HOME_TEAM: Home team name
        - AWAY_TEAM_ID: Away team ID
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score
        - AWAY_SCORE: Away team score
        - VENUE: Arena name
        - LEAGUE: "ACB"

    TODO: Implement ACB schedule scraping
    - Check ACB website for JSON endpoints
    - Check network tab in browser for API calls
    """
    logger.info(f"Fetching ACB schedule: {season}, {season_type}")

    # TODO: Implement scraping/API logic
    logger.warning("ACB schedule fetching requires implementation. " "Returning empty DataFrame.")

    df = pd.DataFrame(
        columns=[
            "GAME_ID",
            "SEASON",
            "GAME_DATE",
            "HOME_TEAM_ID",
            "HOME_TEAM",
            "AWAY_TEAM_ID",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
            "VENUE",
            "LEAGUE",
        ]
    )

    df["LEAGUE"] = "ACB"

    logger.info(f"Fetched {len(df)} ACB games (scaffold mode)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch ACB box score for a game

    Note: Requires implementation. Currently returns empty DataFrame.

    Args:
        game_id: Game ID (ACB game identifier)

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_ID: Team ID
        - TEAM: Team name
        - MIN: Minutes played
        - PTS: Points
        - FGM, FGA, FG_PCT: Field goals
        - FG3M, FG3A, FG3_PCT: 3-point field goals
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB: Rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - PLUS_MINUS: Plus/minus
        - LEAGUE: "ACB"

    TODO: Implement ACB box score scraping
    """
    logger.info(f"Fetching ACB box score: {game_id}")

    # TODO: Implement scraping logic
    logger.warning(
        f"ACB box score fetching for game {game_id} requires implementation. "
        "Returning empty DataFrame."
    )

    df = pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            "TEAM",
            "MIN",
            "PTS",
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
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
            "PLUS_MINUS",
            "LEAGUE",
        ]
    )

    df["LEAGUE"] = "ACB"
    df["GAME_ID"] = game_id

    logger.info(f"Fetched box score: {len(df)} players (scaffold mode)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch ACB play-by-play data

    Note: Limited availability. ACB does not publish detailed play-by-play
    publicly. This function returns empty DataFrame.

    Args:
        game_id: Game ID

    Returns:
        Empty DataFrame (PBP limited availability)

    Implementation Notes:
        - ACB website may have basic play logs (requires scraping)
        - No known public API for play-by-play data
    """
    logger.warning(
        f"ACB play-by-play for game {game_id} has limited availability. " "Not published publicly."
    )

    df = pd.DataFrame(
        columns=[
            "GAME_ID",
            "EVENT_NUM",
            "EVENT_TYPE",
            "PERIOD",
            "CLOCK",
            "DESCRIPTION",
            "LEAGUE",
        ]
    )

    df["LEAGUE"] = "ACB"
    df["GAME_ID"] = game_id

    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_shot_chart(game_id: str) -> pd.DataFrame:
    """Fetch ACB shot chart data

    Note: Shot chart data has limited availability. Not published publicly.
    This function returns empty DataFrame.

    Args:
        game_id: Game ID

    Returns:
        Empty DataFrame (shot data limited availability)

    Implementation Notes:
        - ACB website may have basic shot location data (requires research)
        - No known public API for shot chart data
    """
    logger.warning(
        f"ACB shot chart for game {game_id} has limited availability. " "Not published publicly."
    )

    df = pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            "TEAM",
            "SHOT_TYPE",
            "SHOT_DISTANCE",
            "LOC_X",
            "LOC_Y",
            "SHOT_MADE",
            "PERIOD",
            "LEAGUE",
        ]
    )

    df["LEAGUE"] = "ACB"
    df["GAME_ID"] = game_id

    return df
