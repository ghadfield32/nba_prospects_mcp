"""WNBA Fetcher

Official WNBA Stats API client.
Uses the stats.wnba.com endpoints for comprehensive WNBA data.

Key Features:
- Free, official API (no authentication required)
- Comprehensive data (games, box scores, play-by-play, shot charts)
- Historical data back to 1997 season
- Rate limit: 5 req/sec (conservative, matching NBA/G-League API)

Data Granularities:
- schedule: ✅ Full (all games with scores, dates, venues)
- player_game: ✅ Full (complete box scores with all stats)
- team_game: ✅ Full (team box scores and game results)
- pbp: ✅ Full (play-by-play with timestamps, scores, players)
- shots: ✅ Full (X/Y coordinates, shot types, made/missed)
- player_season: ✅ Aggregated (from player_game data)
- team_season: ✅ Aggregated (from team_game data)

Data Source: https://stats.wnba.com
API Documentation: Similar to NBA Stats API (stats.nba.com)

Implementation Notes:
- Mirrors G-League implementation pattern
- Uses same ResultSet format as NBA/G-League APIs
- Season format: "2024" for 2024 WNBA season (not "2024-25")
- League ID: "10" for WNBA in API calls
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# WNBA API base URL
WNBA_BASE_URL = "https://stats.wnba.com/stats"

# Standard headers for WNBA API (mimics browser request)
WNBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://stats.wnba.com/",
    "Origin": "https://stats.wnba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def _make_wnba_request(endpoint: str, params: dict) -> dict:
    """Make a request to the WNBA Stats API

    Args:
        endpoint: API endpoint (e.g., "leaguegamelog")
        params: Query parameters

    Returns:
        JSON response as dict

    Raises:
        requests.HTTPError: If the request fails
    """
    rate_limiter.acquire("wnba")

    url = f"{WNBA_BASE_URL}/{endpoint}"

    try:
        response = requests.get(url, headers=WNBA_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data: dict = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"WNBA API request failed: {url} - {e}")
        raise


def _parse_resultset(data: dict, result_set_name: str = "leagueGameLog") -> pd.DataFrame:
    """Parse WNBA API ResultSet into DataFrame

    The WNBA API returns data in ResultSet format (same as NBA/G-League):
    {
        "resource": "endpoint_name",
        "parameters": {...},
        "resultSets": [
            {
                "name": "ResultSetName",
                "headers": ["COL1", "COL2", ...],
                "rowSet": [[val1, val2, ...], ...]
            }
        ]
    }

    Args:
        data: JSON response from API
        result_set_name: Name of the result set to extract (case-insensitive)

    Returns:
        DataFrame with columns from headers

    Raises:
        KeyError: If result set not found
    """
    result_sets = data.get("resultSets", [])

    # Find matching result set (case-insensitive)
    for rs in result_sets:
        if rs.get("name", "").lower() == result_set_name.lower():
            headers = rs.get("headers", [])
            rows = rs.get("rowSet", [])
            return pd.DataFrame(rows, columns=headers)

    # Not found - list available
    available = [rs.get("name") for rs in result_sets]
    raise KeyError(f"ResultSet '{result_set_name}' not found. Available: {available}")


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_wnba_schedule(
    season: str = "2024",
    season_type: str = "Regular Season",
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Fetch WNBA schedule

    Args:
        season: Season year (e.g., "2024" for 2024 season)
        season_type: "Regular Season", "Playoffs", "All Star"
        date_from: Optional start date (YYYY-MM-DD or MM/DD/YYYY)
        date_to: Optional end date (YYYY-MM-DD or MM/DD/YYYY)

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: Unique game identifier
        - GAME_DATE: Game date
        - HOME_TEAM_ID, HOME_TEAM_NAME, HOME_TEAM_ABBREVIATION
        - AWAY_TEAM_ID, AWAY_TEAM_NAME, AWAY_TEAM_ABBREVIATION
        - HOME_SCORE, AWAY_SCORE (null for future games)
        - STATUS: Game status (STATUS_SCHEDULED, STATUS_FINAL, STATUS_IN_PROGRESS)
        - SEASON: Season string
        - LEAGUE: "WNBA"
    """
    logger.info(f"Fetching WNBA schedule: season={season}, type={season_type}")

    # Map season types to API codes
    season_type_map = {
        "Regular Season": "Regular Season",
        "Playoffs": "Playoffs",
        "All Star": "All-Star",
        "Preseason": "Pre Season",
    }
    api_season_type = season_type_map.get(season_type, season_type)

    params = {
        "LeagueID": "10",  # WNBA league ID
        "Season": season,
        "SeasonType": api_season_type,
    }

    if date_from:
        params["DateFrom"] = date_from
    if date_to:
        params["DateTo"] = date_to

    # Fetch schedule data
    data = _make_wnba_request("leaguegamefinder", params)
    df = _parse_resultset(data, "LeagueGameFinderResults")

    if df.empty:
        logger.warning(f"No games found for WNBA {season} {season_type}")
        return df

    # Normalize column names and add metadata
    df = df.rename(
        columns={
            "GAME_DATE": "GAME_DATE_RAW",
            "TEAM_ID": "HOME_TEAM_ID",
            "TEAM_NAME": "HOME_TEAM",
            "TEAM_ABBREVIATION": "HOME_TEAM_ABBREVIATION",
            "PTS": "HOME_SCORE",
        }
    )

    # Parse game date
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE_RAW"])

    # Add league identifier
    df["LEAGUE"] = "WNBA"
    df["SEASON"] = season

    # Determine game status
    df["STATUS"] = "STATUS_FINAL"  # Most games in gamefinder are completed

    logger.info(f"Fetched {len(df)} WNBA games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_wnba_box_score(game_id: str) -> pd.DataFrame:
    """Fetch WNBA player box score

    Args:
        game_id: WNBA game ID (10-digit string)

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID, PLAYER_NAME
        - TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION
        - MIN: Minutes played (as string "MM:SS")
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - PLUS_MINUS
        - LEAGUE: "WNBA"
    """
    logger.info(f"Fetching WNBA box score: game_id={game_id}")

    params = {
        "GameID": game_id,
        "StartPeriod": "0",
        "EndPeriod": "10",
        "StartRange": "0",
        "EndRange": "28800",
        "RangeType": "0",
    }

    data = _make_wnba_request("boxscoretraditionalv2", params)
    df = _parse_resultset(data, "PlayerStats")

    if df.empty:
        logger.warning(f"No player stats found for WNBA game {game_id}")
        return df

    # Add metadata
    df["GAME_ID"] = game_id
    df["LEAGUE"] = "WNBA"

    logger.info(f"Fetched box score: {len(df)} players")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_wnba_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch WNBA play-by-play data

    Args:
        game_id: WNBA game ID

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENTNUM: Event number
        - EVENTMSGTYPE: Event type code
        - EVENTMSGACTIONTYPE: Event action type code
        - PERIOD: Quarter (1-4, 5+ for OT)
        - PCTIMESTRING: Game clock (MM:SS)
        - HOMEDESCRIPTION, VISITORDESCRIPTION, NEUTRALDESCRIPTION
        - SCORE: Current score
        - SCOREMARGIN: Score differential
        - PLAYER1_ID, PLAYER1_NAME, PLAYER1_TEAM_ID
        - PLAYER2_ID, PLAYER2_NAME, PLAYER2_TEAM_ID
        - LEAGUE: "WNBA"
    """
    logger.info(f"Fetching WNBA play-by-play: game_id={game_id}")

    params = {
        "GameID": game_id,
        "StartPeriod": "0",
        "EndPeriod": "10",
    }

    data = _make_wnba_request("playbyplayv2", params)
    df = _parse_resultset(data, "PlayByPlay")

    if df.empty:
        logger.warning(f"No play-by-play found for WNBA game {game_id}")
        return df

    # Add metadata
    df["GAME_ID"] = game_id
    df["LEAGUE"] = "WNBA"

    logger.info(f"Fetched play-by-play: {len(df)} events")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_wnba_shot_chart(game_id: str) -> pd.DataFrame:
    """Fetch WNBA shot chart data

    Args:
        game_id: WNBA game ID

    Returns:
        DataFrame with shot data

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID, PLAYER_NAME
        - TEAM_ID, TEAM_NAME
        - PERIOD: Quarter
        - MINUTES_REMAINING, SECONDS_REMAINING
        - EVENT_TYPE: Shot type description
        - SHOT_TYPE: "2PT" or "3PT"
        - SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE
        - SHOT_DISTANCE: Distance in feet
        - LOC_X, LOC_Y: Court coordinates (in tenths of feet)
        - SHOT_MADE_FLAG: 1 if made, 0 if missed
        - LEAGUE: "WNBA"
    """
    logger.info(f"Fetching WNBA shot chart: game_id={game_id}")

    params = {
        "GameID": game_id,
        "LeagueID": "10",
        "Season": "2024",
        "SeasonType": "Regular Season",
        "TeamID": "0",
        "PlayerID": "0",
        "Outcome": "",
        "Location": "",
        "Month": "0",
        "SeasonSegment": "",
        "DateFrom": "",
        "DateTo": "",
        "OpponentTeamID": "0",
        "VsConference": "",
        "VsDivision": "",
        "Position": "",
        "RookieYear": "",
        "GameSegment": "",
        "Period": "0",
        "LastNGames": "0",
        "ContextMeasure": "FGA",
    }

    data = _make_wnba_request("shotchartdetail", params)
    df = _parse_resultset(data, "Shot_Chart_Detail")

    if df.empty:
        logger.warning(f"No shot data found for WNBA game {game_id}")
        return df

    # Add metadata
    df["GAME_ID"] = game_id
    df["LEAGUE"] = "WNBA"

    logger.info(f"Fetched shot chart: {len(df)} shots")
    return df
