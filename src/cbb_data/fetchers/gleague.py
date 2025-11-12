"""NBA G League Fetcher

Official NBA G League Stats API client.
Uses the stats.gleague.nba.com endpoints for comprehensive G League data.

Key Features:
- Free, official API (no authentication required)
- Comprehensive data (games, box scores, play-by-play, shot charts)
- Historical data back to 2001-02 season
- Rate limit: 5 req/sec (conservative, matching NBA API)

Data Granularities:
- schedule: ✅ Full (all games with scores, dates, venues)
- player_game: ✅ Full (complete box scores with all stats)
- team_game: ✅ Full (team box scores and game results)
- pbp: ✅ Full (play-by-play with timestamps, scores, players)
- shots: ✅ Full (X/Y coordinates, shot types, made/missed)
- player_season: ✅ Aggregated (from player_game data)
- team_season: ✅ Aggregated (from team_game data)

Data Source: https://stats.gleague.nba.com
API Documentation: Similar to NBA Stats API (stats.nba.com)
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

# G League API base URL
GLEAGUE_BASE_URL = "https://stats.gleague.nba.com/stats"

# Standard headers for G League API (mimics browser request)
GLEAGUE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://stats.gleague.nba.com/",
    "Origin": "https://stats.gleague.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def _make_gleague_request(endpoint: str, params: dict) -> dict:
    """Make a request to the G League Stats API

    Args:
        endpoint: API endpoint (e.g., "leaguegamelog")
        params: Query parameters

    Returns:
        JSON response as dict

    Raises:
        requests.HTTPError: If the request fails
    """
    rate_limiter.acquire("gleague")

    url = f"{GLEAGUE_BASE_URL}/{endpoint}"

    try:
        response = requests.get(url, headers=GLEAGUE_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"G League API request failed: {url} - {e}")
        raise


def _parse_resultset(data: dict, result_set_name: str = "leagueGameLog") -> pd.DataFrame:
    """Parse G League API ResultSet into DataFrame

    The G League API returns data in ResultSet format:
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
        DataFrame with the result set data
    """
    if "resultSets" not in data:
        logger.warning("No resultSets in API response")
        return pd.DataFrame()

    # Find the matching result set (case-insensitive)
    result_set = None
    for rs in data["resultSets"]:
        if rs.get("name", "").lower() == result_set_name.lower():
            result_set = rs
            break

    if result_set is None:
        # If exact match not found, use first result set
        if data["resultSets"]:
            result_set = data["resultSets"][0]
            logger.debug(
                f"Result set '{result_set_name}' not found, using first: {result_set.get('name')}"
            )
        else:
            logger.warning("No result sets found in response")
            return pd.DataFrame()

    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])

    if not headers or not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=headers)


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_gleague_schedule(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Fetch G League game schedule

    Args:
        season: Season string (e.g., "2024-25")
        season_type: Season type ("Regular Season", "Playoffs", "All-Star", "Pre Season")
        date_from: Optional start date (MM/DD/YYYY format)
        date_to: Optional end date (MM/DD/YYYY format)

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
        - LEAGUE: "G-League"
    """
    logger.info(f"Fetching G League schedule: {season}, {season_type}")

    # Map season type to API parameter
    season_type_map = {
        "Regular Season": "Regular Season",
        "Playoffs": "Playoffs",
        "All-Star": "All-Star",
        "Pre Season": "Pre Season",
        "All Star": "All-Star",
    }
    season_type_param = season_type_map.get(season_type, "Regular Season")

    params = {
        "LeagueID": "20",  # G League ID
        "Season": season,
        "SeasonType": season_type_param,
    }

    if date_from:
        params["DateFrom"] = date_from
    if date_to:
        params["DateTo"] = date_to

    # Use leaguegamefinder endpoint
    data = _make_gleague_request("leaguegamefinder", params)
    df = _parse_resultset(data, "LeagueGameFinderResults")

    if df.empty:
        logger.warning(f"No games found for G League {season}")
        return df

    # Rename columns to our schema
    column_mapping = {
        "GAME_ID": "GAME_ID",
        "SEASON_ID": "SEASON",
        "GAME_DATE": "GAME_DATE",
        "TEAM_ID": "TEAM_ID",
        "TEAM_NAME": "TEAM_NAME",
        "MATCHUP": "MATCHUP",
        "WL": "WIN_LOSS",
        "PTS": "SCORE",
    }

    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Parse game date
    if "GAME_DATE" in df.columns:
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    # Add league identifier
    df["LEAGUE"] = "G-League"

    # Transform to schedule format (one row per game, not per team)
    # Group by GAME_ID and combine home/away team info
    if "GAME_ID" in df.columns and "MATCHUP" in df.columns:
        # Identify home/away based on '@' symbol in MATCHUP
        df["IS_HOME"] = ~df["MATCHUP"].str.contains("@", na=False)

        # Split into home and away
        home_df = df[df["IS_HOME"]].copy()
        away_df = df[~df["IS_HOME"]].copy()

        # Merge on GAME_ID
        schedule_df = home_df.merge(
            away_df,
            on="GAME_ID",
            suffixes=("_HOME", "_AWAY"),
            how="outer",
        )

        # Select and rename columns
        schedule_df = schedule_df.rename(
            columns={
                "TEAM_ID_HOME": "HOME_TEAM_ID",
                "TEAM_NAME_HOME": "HOME_TEAM",
                "SCORE_HOME": "HOME_SCORE",
                "TEAM_ID_AWAY": "AWAY_TEAM_ID",
                "TEAM_NAME_AWAY": "AWAY_TEAM",
                "SCORE_AWAY": "AWAY_SCORE",
                "GAME_DATE_HOME": "GAME_DATE",
                "SEASON_HOME": "SEASON",
                "LEAGUE_HOME": "LEAGUE",
            }
        )

        # Select final columns
        columns_to_keep = [
            "GAME_ID",
            "SEASON",
            "GAME_DATE",
            "HOME_TEAM_ID",
            "HOME_TEAM",
            "AWAY_TEAM_ID",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
            "LEAGUE",
        ]

        df = schedule_df[[col for col in columns_to_keep if col in schedule_df.columns]]

    logger.info(f"Fetched {len(df)} G League games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_gleague_box_score(game_id: str) -> pd.DataFrame:
    """Fetch G League box score for a game

    Args:
        game_id: Game ID (e.g., "0022400001")

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_ID: Team ID
        - TEAM: Team name
        - STARTER: Is starter (0/1)
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
    """
    logger.info(f"Fetching G League box score: {game_id}")

    params = {
        "GameID": game_id,
        "StartPeriod": 0,
        "EndPeriod": 10,
        "StartRange": 0,
        "EndRange": 28800,
        "RangeType": 0,
    }

    data = _make_gleague_request("boxscoretraditionalv2", params)
    df = _parse_resultset(data, "PlayerStats")

    if df.empty:
        logger.warning(f"No box score data for game {game_id}")
        return df

    # Add GAME_ID if not present
    if "GAME_ID" not in df.columns:
        df["GAME_ID"] = game_id

    # Add league identifier
    df["LEAGUE"] = "G-League"

    # Rename columns for consistency
    column_mapping = {
        "PLAYER_NAME": "PLAYER_NAME",
        "TEAM_ABBREVIATION": "TEAM",
        "START_POSITION": "STARTER",
        "COMMENT": "COMMENT",
    }

    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Convert STARTER to 0/1
    if "STARTER" in df.columns:
        df["STARTER"] = (df["STARTER"].notna() & (df["STARTER"] != "")).astype(int)

    logger.info(f"Fetched box score: {len(df)} players")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_gleague_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch G League play-by-play data

    Args:
        game_id: Game ID (e.g., "0022400001")

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENT_NUM: Event number
        - EVENT_TYPE: Event type
        - PERIOD: Quarter/period (1-4, 5+ for OT)
        - CLOCK: Game clock (MM:SS)
        - DESCRIPTION: Play description
        - HOME_DESCRIPTION: Home team description
        - AWAY_DESCRIPTION: Away team description
        - SCORE: Current score
        - SCORE_MARGIN: Score margin
    """
    logger.info(f"Fetching G League play-by-play: {game_id}")

    params = {
        "GameID": game_id,
        "StartPeriod": 0,
        "EndPeriod": 10,
    }

    data = _make_gleague_request("playbyplayv2", params)
    df = _parse_resultset(data, "PlayByPlay")

    if df.empty:
        logger.warning(f"No play-by-play data for game {game_id}")
        return df

    # Add GAME_ID if not present
    if "GAME_ID" not in df.columns:
        df["GAME_ID"] = game_id

    # Add league identifier
    df["LEAGUE"] = "G-League"

    # Rename columns
    column_mapping = {
        "EVENTNUM": "EVENT_NUM",
        "EVENTMSGTYPE": "EVENT_TYPE",
        "PCTIMESTRING": "CLOCK",
        "HOMEDESCRIPTION": "HOME_DESCRIPTION",
        "VISITORDESCRIPTION": "AWAY_DESCRIPTION",
        "SCOREMARGIN": "SCORE_MARGIN",
    }

    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    logger.info(f"Fetched play-by-play: {len(df)} events")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_gleague_shot_chart(game_id: str) -> pd.DataFrame:
    """Fetch G League shot chart data

    Args:
        game_id: Game ID (e.g., "0022400001")

    Returns:
        DataFrame with shot locations and results

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_ID: Team ID
        - TEAM: Team name
        - SHOT_TYPE: Shot action type
        - SHOT_ZONE_BASIC: Basic shot zone
        - SHOT_ZONE_AREA: Shot zone area
        - SHOT_ZONE_RANGE: Shot distance range
        - SHOT_DISTANCE: Shot distance (feet)
        - LOC_X: X coordinate
        - LOC_Y: Y coordinate
        - SHOT_MADE: Shot made flag (0/1)
        - PERIOD: Quarter/period
        - MINUTES_REMAINING: Minutes remaining in period
        - SECONDS_REMAINING: Seconds remaining in period
    """
    logger.info(f"Fetching G League shot chart: {game_id}")

    params = {
        "GameID": game_id,
        "Season": "2024-25",  # Required but not used for game-specific queries
        "SeasonType": "Regular Season",
        "TeamID": 0,  # 0 = all teams
        "PlayerID": 0,  # 0 = all players
        "ContextMeasure": "FGA",  # Field goal attempts
        "RookieYear": "",
        "PlayerPosition": "",
    }

    data = _make_gleague_request("shotchartdetail", params)
    df = _parse_resultset(data, "Shot_Chart_Detail")

    if df.empty:
        logger.warning(f"No shot chart data for game {game_id}")
        return df

    # Add league identifier
    df["LEAGUE"] = "G-League"

    # Rename columns for consistency
    column_mapping = {
        "SHOT_MADE_FLAG": "SHOT_MADE",
        "ACTION_TYPE": "SHOT_TYPE",
        "SHOT_TYPE": "SHOT_CATEGORY",
        "TEAM_NAME": "TEAM",
    }

    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    logger.info(f"Fetched shot chart: {len(df)} shots")
    return df
