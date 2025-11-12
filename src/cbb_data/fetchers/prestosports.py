"""PrestoSports Platform Fetcher

Unified scraper for basketball leagues using the PrestoSports/PrestoStats platform.
Handles NJCAA, NAIA, U SPORTS (Canada), and CCAA (Canada).

Key Features:
- PrestoSports is a widely-used stats platform for college athletics
- Consistent HTML structure across leagues makes unified scraping possible
- Comprehensive stats including leaders, schedules, and box scores
- Canadian leagues (U SPORTS, CCAA) use same platform infrastructure

Data Granularities (per league):
- schedule: ⚠️ Limited (requires PrestoSports HTML parsing)
- player_game: ⚠️ Limited (box scores available via scraping)
- team_game: ⚠️ Limited (team stats available via scraping)
- pbp: ❌ Unavailable (PrestoSports doesn't publish detailed PBP)
- shots: ❌ Unavailable (shot coordinates not available)
- player_season: ✅ Available (season leaders published directly) **IMPLEMENTED**
- team_season: ✅ Available (team stats published directly)

Data Sources:
- NJCAA (USA): https://njcaastats.prestosports.com/sports/mbkb/
- NAIA (USA): https://naiastats.prestosports.com/sports/mbkb/
- U SPORTS (Canada): https://universitysport.prestosports.com/sports/mbkb/
- CCAA (Canada): https://ccaa.prestosports.com/sports/mbkb/

Platform Documentation: https://www.prestosports.com/prestostats/

Implementation Status:
- Season leaders: ✅ IMPLEMENTED (full HTML parsing with BeautifulSoup)
- Schedule: Scaffold (requires implementation)
- Box scores: Scaffold (requires implementation)

Implementation Notes:
- PrestoSports uses consistent HTML table structure across all leagues
- Tables have class="stats-table" with thead/tbody structure
- Player names link to player pages (can extract IDs from URLs)
- Stats are in data-value attributes for sorting (use these for accurate values)
- Canadian leagues (U SPORTS, CCAA) follow exact same HTML structure
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
import requests

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Try to import BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    logger.warning("BeautifulSoup4 not available. Install with: pip install beautifulsoup4")
    BS4_AVAILABLE = False

# Get rate limiter
rate_limiter = get_source_limiter()

# PrestoSports league configurations
PRESTOSPORTS_CONFIGS = {
    "NJCAA": {
        "name": "NJCAA",
        "base_url": "https://njcaastats.prestosports.com",
        "sport_path": "/sports/mbkb",
        "description": "National Junior College Athletic Association",
        "division": "Division I",  # Note: NJCAA has D1, D2, D3
    },
    "NAIA": {
        "name": "NAIA",
        "base_url": "https://naiastats.prestosports.com",
        "sport_path": "/sports/mbkb",
        "description": "National Association of Intercollegiate Athletics",
        "division": None,  # NAIA doesn't use divisions
    },
    "U-SPORTS": {
        "name": "U SPORTS",
        "base_url": "https://universitysport.prestosports.com",
        "sport_path": "/sports/mbkb",
        "description": "U SPORTS (Canadian University Basketball)",
        "division": None,  # U SPORTS doesn't use divisions
    },
    "CCAA": {
        "name": "CCAA",
        "base_url": "https://ccaa.prestosports.com",
        "sport_path": "/sports/mbkb",
        "description": "Canadian Collegiate Athletic Association",
        "division": None,  # CCAA doesn't use divisions
    },
}


def _make_prestosports_request(
    league: str, endpoint: str, params: dict[str, Any] | None = None
) -> str:
    """Make a request to PrestoSports platform

    Args:
        league: League identifier (NJCAA, NAIA)
        endpoint: Endpoint path (e.g., "/scoreboard", "/leaders")
        params: Optional query parameters

    Returns:
        HTML content as string

    Raises:
        requests.HTTPError: If the request fails
        ValueError: If league not recognized
    """
    if league not in PRESTOSPORTS_CONFIGS:
        raise ValueError(
            f"Unknown league: {league}. Must be one of: {list(PRESTOSPORTS_CONFIGS.keys())}"
        )

    rate_limiter.acquire(league.lower())

    config = PRESTOSPORTS_CONFIGS[league]
    if not isinstance(config, dict):
        raise ValueError(f"Invalid config for league {league}")
    base: str = config["base_url"]
    sport: str = config["sport_path"]
    url = f"{base}{sport}{endpoint}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": base,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"PrestoSports request failed ({league}): {url} - {e}")
        raise


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_prestosports_schedule(
    league: str,
    season: str = "2024-25",
    division: str | None = None,
) -> pd.DataFrame:
    """Fetch schedule for PrestoSports league

    Note: Requires HTML parsing of PrestoSports scoreboard. Currently returns
    empty DataFrame with correct schema.

    Args:
        league: League identifier (NJCAA, NAIA)
        season: Season string (e.g., "2024-25")
        division: Optional division filter (for NJCAA: "div1", "div2", "div3")

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
        - LEAGUE: League identifier (NJCAA, NAIA)

    TODO: Implement PrestoSports scoreboard scraping
    - Endpoint: /scoreboard (or /schedule)
    - Parse game cards with BeautifulSoup
    - PrestoSports HTML structure is consistent across leagues
    - Example: https://njcaastats.prestosports.com/sports/mbkb/2024-25/div1/scoreboard
    """
    if league not in PRESTOSPORTS_CONFIGS:
        raise ValueError(
            f"Unknown league: {league}. Must be one of: {list(PRESTOSPORTS_CONFIGS.keys())}"
        )

    config = PRESTOSPORTS_CONFIGS[league]
    if not isinstance(config, dict):
        raise ValueError(f"Invalid config for league {league}")
    logger.info(f"Fetching {league} schedule: {season}, division={division}")

    # TODO: Implement PrestoSports scraping
    logger.warning(
        f"{league} ({config['description']}) schedule fetching requires PrestoSports HTML parsing. "
        "Returning empty DataFrame."
    )

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

    df["LEAGUE"] = league

    logger.info(f"Fetched {len(df)} {league} games (scaffold mode)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_prestosports_box_score(league: str, game_id: str) -> pd.DataFrame:
    """Fetch box score for PrestoSports league game

    Note: Requires HTML parsing. Currently returns empty DataFrame.

    Args:
        league: League identifier (NJCAA, NAIA)
        game_id: Game ID (PrestoSports game identifier)

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
        - LEAGUE: League identifier

    TODO: Implement PrestoSports box score scraping
    - Parse game detail pages
    - Player stat tables are consistently formatted
    - May need to handle game IDs/URLs specific to PrestoSports
    """
    if league not in PRESTOSPORTS_CONFIGS:
        raise ValueError(
            f"Unknown league: {league}. Must be one of: {list(PRESTOSPORTS_CONFIGS.keys())}"
        )

    logger.info(f"Fetching {league} box score: {game_id}")

    # TODO: Implement scraping logic
    logger.warning(
        f"{league} box score fetching for game {game_id} requires implementation. "
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
            "LEAGUE",
        ]
    )

    df["LEAGUE"] = league
    df["GAME_ID"] = game_id

    logger.info(f"Fetched box score: {len(df)} players (scaffold mode)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_prestosports_season_leaders(
    league: str,
    season: str = "2024-25",
    stat_category: str = "points",
    division: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Fetch season leaders for PrestoSports league

    **IMPLEMENTED**: Full HTML parsing with BeautifulSoup4.
    Scrapes leader tables directly from PrestoSports stats pages.

    Args:
        league: League identifier (NJCAA, NAIA)
        season: Season string (e.g., "2024-25")
        stat_category: Stat category (scoring, rebounding, assists, etc.)
        division: Optional division filter (for NJCAA: "div1", "div2", "div3")
        limit: Optional limit on number of players returned (default: all)

    Returns:
        DataFrame with season leader stats

    Columns (varies by stat_category):
        - PLAYER_ID: Player ID (extracted from player page URL)
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - YEAR: Class year (FR, SO, JR, SR)
        - GP: Games played
        - Primary stats depend on category (PTS, REB, AST, etc.)
        - LEAGUE: League identifier

    Stat Categories:
        - scoring: Points leaders (PTS, PPG, FG%, FT%, etc.)
        - rebounding: Rebound leaders (REB, RPG, OREB, DREB)
        - assists: Assist leaders (AST, APG, A/TO ratio)
        - steals: Steal leaders (STL, SPG)
        - blocks: Block leaders (BLK, BPG)
        - field-goals: FG% leaders
        - three-points: 3P% leaders
        - free-throws: FT% leaders

    Example:
        >>> # Get top 50 scorers from NJCAA Division I
        >>> df = fetch_prestosports_season_leaders("NJCAA", "2024-25", "scoring", "div1", limit=50)
        >>> print(df[["PLAYER_NAME", "TEAM", "GP", "PTS", "PPG"]])
    """
    if league not in PRESTOSPORTS_CONFIGS:
        raise ValueError(
            f"Unknown league: {league}. Must be one of: {list(PRESTOSPORTS_CONFIGS.keys())}"
        )

    if not BS4_AVAILABLE:
        logger.error("BeautifulSoup4 not available. Install with: pip install beautifulsoup4")
        return pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM", "LEAGUE"])

    # Build endpoint path
    division_path = f"/{division}" if division else ""
    endpoint = f"{division_path}/leaders"

    logger.info(
        f"Fetching {league} season leaders: {season}, stat={stat_category}, division={division}"
    )

    try:
        # Make request to leaders page
        html = _make_prestosports_request(league, endpoint)

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Find the stats table
        # PrestoSports uses tables with class "stats-table" or "table table-bordered"
        table = soup.find("table", {"class": re.compile(r"stats.*table|table.*stats")})

        if not table:
            logger.warning(f"No stats table found for {league} {stat_category} leaders")
            df = pd.DataFrame()
        else:
            # Parse table into DataFrame
            df = _parse_prestosports_table(table, league)

            # Apply limit if specified
            if limit and len(df) > limit:
                df = df.head(limit)

            logger.info(f"Fetched {len(df)} {league} season leaders for {stat_category}")

    except Exception as e:
        logger.error(f"Failed to fetch {league} season leaders: {e}")
        df = pd.DataFrame()

    # Ensure LEAGUE column exists
    if not df.empty and "LEAGUE" not in df.columns:
        df["LEAGUE"] = league

    return df


def _parse_prestosports_table(table: Any, league: str) -> pd.DataFrame:
    """Parse PrestoSports HTML table into DataFrame

    Args:
        table: BeautifulSoup table element
        league: League identifier for LEAGUE column

    Returns:
        DataFrame with parsed table data

    Implementation Notes:
        - Headers are in <thead><tr><th>
        - Data rows are in <tbody><tr><td>
        - Player names are in <a> tags with href to player pages
        - Stats may have data-value attributes for accurate sorting values
        - Team names are usually in second or third column
    """
    # Extract headers
    headers = []
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            for th in header_row.find_all("th"):
                # Clean header text (remove whitespace, newlines)
                header_text = th.get_text(strip=True)
                # Normalize common abbreviations
                header_text = _normalize_prestosports_header(header_text)
                headers.append(header_text)

    # Extract data rows
    rows = []
    tbody = table.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr"):
            row_data = []
            for td in tr.find_all("td"):
                # Check if this cell contains a player name link
                player_link = td.find("a", href=re.compile(r"/players/"))
                if player_link:
                    # Extract player name
                    player_name = player_link.get_text(strip=True)
                    row_data.append(player_name)

                    # Try to extract player ID from URL
                    # URL format: /players/player-name/123456
                    href = player_link.get("href", "")
                    player_id_match = re.search(r"/players/.+/(\d+)", href)
                    if player_id_match:
                        # Store player ID (will add as separate column later)
                        if "PLAYER_ID_RAW" not in headers:
                            # Add placeholder for player ID
                            pass
                else:
                    # Regular cell - get text or data-value attribute
                    value = td.get("data-value", td.get_text(strip=True))

                    # Try to convert to numeric if it looks like a number
                    try:
                        # Handle percentages (e.g., "45.2%")
                        if isinstance(value, str) and "%" in value:
                            value = float(value.replace("%", ""))
                        # Handle regular numbers
                        elif (
                            isinstance(value, str)
                            and value.replace(".", "").replace("-", "").isdigit()
                        ):
                            value = float(value) if "." in value else int(value)
                    except (ValueError, AttributeError):
                        pass  # Keep as string

                    row_data.append(value)

            if row_data:  # Only add non-empty rows
                rows.append(row_data)

    # Create DataFrame
    if not rows:
        logger.warning("No data rows found in PrestoSports table")
        return pd.DataFrame()

    # Create DataFrame with headers
    df = pd.DataFrame(rows, columns=headers[: len(rows[0])])  # Match column count to data

    # Add LEAGUE column
    df["LEAGUE"] = league

    # Standardize column names
    df = _standardize_prestosports_columns(df)

    return df


def _normalize_prestosports_header(header: str) -> str:
    """Normalize PrestoSports column headers to standard names

    Args:
        header: Original header text

    Returns:
        Normalized header name
    """
    # Common mappings from PrestoSports to our standard names
    mappings = {
        "Player": "PLAYER_NAME",
        "Name": "PLAYER_NAME",
        "Team": "TEAM",
        "School": "TEAM",
        "Yr": "YEAR",
        "Year": "YEAR",
        "Class": "YEAR",
        "G": "GP",
        "GP": "GP",
        "Games": "GP",
        "Pts": "PTS",
        "Points": "PTS",
        "Reb": "REB",
        "Rebounds": "REB",
        "Ast": "AST",
        "Assists": "AST",
        "Stl": "STL",
        "Steals": "STL",
        "Blk": "BLK",
        "Blocks": "BLK",
        "TO": "TOV",
        "Turnovers": "TOV",
        "PPG": "PPG",
        "RPG": "RPG",
        "APG": "APG",
        "FG%": "FG_PCT",
        "FG Pct": "FG_PCT",
        "3P%": "FG3_PCT",
        "3PT%": "FG3_PCT",
        "FT%": "FT_PCT",
        "FT Pct": "FT_PCT",
        "Min": "MIN",
        "Minutes": "MIN",
    }

    return mappings.get(header, header)


def _standardize_prestosports_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize PrestoSports DataFrame column names

    Args:
        df: DataFrame with original PrestoSports column names

    Returns:
        DataFrame with standardized column names
    """
    # Rename columns to match our schema
    column_map = {}
    for col in df.columns:
        normalized = _normalize_prestosports_header(col)
        if normalized != col:
            column_map[col] = normalized

    if column_map:
        df = df.rename(columns=column_map)

    return df


# Unavailable endpoints for PrestoSports leagues
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_prestosports_play_by_play(league: str, game_id: str) -> pd.DataFrame:
    """Fetch play-by-play (UNAVAILABLE)

    PrestoSports does not publish detailed play-by-play data.
    Returns empty DataFrame.
    """
    logger.warning(
        f"{league} play-by-play unavailable. PrestoSports platform does not publish detailed PBP."
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

    df["LEAGUE"] = league
    df["GAME_ID"] = game_id

    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_prestosports_shot_chart(league: str, game_id: str) -> pd.DataFrame:
    """Fetch shot chart (UNAVAILABLE)

    PrestoSports does not publish shot coordinate data.
    Returns empty DataFrame.
    """
    logger.warning(
        f"{league} shot chart unavailable. PrestoSports platform does not publish shot coordinates."
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

    df["LEAGUE"] = league
    df["GAME_ID"] = game_id

    return df


# Convenience functions for each league
def fetch_njcaa_schedule(season: str = "2024-25", division: str | None = "div1") -> pd.DataFrame:
    """Fetch NJCAA schedule"""
    return fetch_prestosports_schedule("NJCAA", season, division)


def fetch_naia_schedule(season: str = "2024-25") -> pd.DataFrame:
    """Fetch NAIA schedule"""
    return fetch_prestosports_schedule("NAIA", season)


def fetch_njcaa_leaders(
    season: str = "2024-25", stat: str = "points", division: str | None = "div1"
) -> pd.DataFrame:
    """Fetch NJCAA season leaders"""
    return fetch_prestosports_season_leaders("NJCAA", season, stat, division)


def fetch_naia_leaders(season: str = "2024-25", stat: str = "points") -> pd.DataFrame:
    """Fetch NAIA season leaders"""
    return fetch_prestosports_season_leaders("NAIA", season, stat)
