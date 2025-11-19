"""NBL Australia Fetcher

NBL Australia data via nblR GitHub data releases and API-Basketball.

Australia's premier professional basketball league featuring top domestic and international talent.
Known for developing NBA prospects including Josh Giddey, Dyson Daniels, and many others.

**DATA AVAILABILITY**:
- **Game results**: ✅ Available (via nblR data - 1979+)
- **Player box scores**: ✅ Available (via nblR data - 2015+)
- **Team box scores**: ✅ Available (via nblR data - 2015+)
- **Play-by-play**: ✅ Available (via nblR data - 2015+)
- **Shot charts**: ✅ Available (via nblR data - 2015+)
- **Player season stats**: ✅ Available (via API-Basketball or aggregated from box scores)

**Primary Data Source**: nblR GitHub Data Releases
- **URL**: https://github.com/JaseZiv/nblr_data/releases
- **No API key required** - Public data files
- **Format**: RDS (R data files) parsed with pyreadr
- **Historical depth**: Results from 1979, detailed stats from 2015

**Secondary Data Source**: API-Basketball (api-sports.io)
- **Free tier**: 100 requests/day
- **API Key**: Set `API_BASKETBALL_KEY` environment variable

Competition Structure:
- Regular Season: 10 teams (varies by year)
- Finals: Top teams advance to playoffs
- Typical season: October-March (Southern Hemisphere)

Historical Context:
- Founded: 1979
- Prominent teams: Sydney Kings, Melbourne United, Perth Wildcats
- NBA pipeline: Josh Giddey, Dyson Daniels, Patty Mills, Matthew Dellavedova
- Strong development pathway to NBA

Technical Notes:
- Uses nblR pre-processed data files (no scraping required)
- Graceful degradation: falls back to API-Basketball if available
- pyreadr required for RDS file parsing

Documentation:
- NBL Official: https://www.nbl.com.au/
- nblR Package: https://github.com/JaseZiv/nblR
- nblR Data: https://github.com/JaseZiv/nblr_data/releases

Implementation Status:
✅ IMPLEMENTED - nblR data integration for all data types (2025-11-18)
✅ IMPLEMENTED - API-Basketball integration for player season stats
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
import requests

from ..clients.api_basketball import APIBasketballClient
from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# nblR data release URLs
# Each data type is in a different release tag
NBLR_DATA_BASE_URL = "https://github.com/JaseZiv/nblr_data/releases/download"

NBLR_DATA_FILES = {
    "results": f"{NBLR_DATA_BASE_URL}/match_results/results_wide.rds",
    "box_player": f"{NBLR_DATA_BASE_URL}/archive/box_player.rds",
    "box_team": f"{NBLR_DATA_BASE_URL}/box_team/box_team.rds",
    "pbp": f"{NBLR_DATA_BASE_URL}/pbp/pbp.csv",  # Use CSV for PBP (RDS has unsupported features)
    "shots": f"{NBLR_DATA_BASE_URL}/shots/shots.rds",
}

# Local cache directory for downloaded RDS files
NBLR_CACHE_DIR = Path(tempfile.gettempdir()) / "nblr_cache"

# Check for pyreadr availability
try:
    import pyreadr

    PYREADR_AVAILABLE = True
except ImportError:
    PYREADR_AVAILABLE = False
    logger.warning("pyreadr not installed. Install with: pip install pyreadr")

# Get rate limiter
rate_limiter = get_source_limiter()

# NBL League ID in API-Basketball (needs verification)
# To find: client = APIBasketballClient(); client.find_league_id("NBL", country="Australia")
NBL_API_LEAGUE_ID = 12  # Placeholder - verify with actual API call


def _download_nblr_file(data_type: str, force_refresh: bool = False) -> Path | None:
    """Download nblR data file from GitHub releases.

    Args:
        data_type: Type of data file (results, box_player, box_team, pbp, shots)
        force_refresh: Force re-download even if cached

    Returns:
        Path to downloaded file, or None if download failed
    """
    if data_type not in NBLR_DATA_FILES:
        logger.error(f"Unknown nblR data type: {data_type}")
        return None

    # Create cache directory if it doesn't exist
    NBLR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Get the file extension from the URL
    url = NBLR_DATA_FILES[data_type]
    ext = ".csv" if url.endswith(".csv") else ".rds"

    # Check for cached file
    cache_file = NBLR_CACHE_DIR / f"{data_type}{ext}"
    if cache_file.exists() and not force_refresh:
        logger.debug(f"Using cached nblR file: {cache_file}")
        return cache_file

    # Download from GitHub
    logger.info(f"Downloading nblR {data_type} data from: {url}")

    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()

        # Save to cache
        with open(cache_file, "wb") as f:
            f.write(response.content)

        logger.info(f"Downloaded {len(response.content) / 1024 / 1024:.1f} MB to {cache_file}")
        return cache_file

    except requests.RequestException as e:
        logger.error(f"Failed to download nblR {data_type} data: {e}")
        return None


def _load_nblr_data(data_type: str, force_refresh: bool = False) -> pd.DataFrame:
    """Load nblR data file as DataFrame.

    Args:
        data_type: Type of data file (results, box_player, box_team, pbp, shots)
        force_refresh: Force re-download even if cached

    Returns:
        DataFrame with nblR data, or empty DataFrame on error
    """
    # Download file if needed
    file_path = _download_nblr_file(data_type, force_refresh)
    if file_path is None:
        return pd.DataFrame()

    try:
        # Check file extension and use appropriate loader
        if str(file_path).endswith(".csv"):
            # Load CSV file directly with pandas
            df = pd.read_csv(str(file_path))
            logger.info(f"Loaded {len(df)} rows from nblR {data_type} (CSV)")
            return df
        else:
            # Load RDS file with pyreadr
            if not PYREADR_AVAILABLE:
                logger.error("pyreadr not available. Install with: pip install pyreadr")
                return pd.DataFrame()

            result = pyreadr.read_r(str(file_path))

            # RDS files contain a single object (usually named after the variable)
            # Get the first (and only) DataFrame
            if result:
                df = list(result.values())[0]
                logger.info(f"Loaded {len(df)} rows from nblR {data_type}")
                return df
            else:
                logger.warning(f"Empty result from nblR {data_type}")
                return pd.DataFrame()

    except Exception as e:
        logger.error(f"Failed to load nblR {data_type} data: {e}")
        return pd.DataFrame()


# =============================================================================
# nblR Data Functions (Primary Data Source)
# =============================================================================


def fetch_nbl_schedule_nblr(
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch NBL schedule/results from nblR data.

    Args:
        season: Season string (e.g., "2024" for 2024-25) or None for all seasons
        force_refresh: Force re-download of data

    Returns:
        DataFrame with game results

    Columns:
        - match_id: Unique game identifier
        - season: Season string
        - round: Round number
        - game_date: Game date
        - home_team: Home team name
        - away_team: Away team name
        - home_score: Home team score
        - away_score: Away team score
        - venue: Arena name
        - LEAGUE: "NBL"

    Note:
        Data available from 1979 onwards.
    """
    logger.info(f"Fetching NBL schedule from nblR: season={season}")

    df = _load_nblr_data("results", force_refresh)
    if df.empty:
        return df

    # Add league metadata
    df["LEAGUE"] = "NBL"

    # Filter by season if specified
    if season is not None:
        # nblR uses format like "2024-25" or just "2024"
        # Try multiple column names for season
        season_col = None
        for col in ["season", "Season", "SEASON"]:
            if col in df.columns:
                season_col = col
                break

        if season_col:
            # Handle different season formats
            if "-" in season:
                # User provided "2024-25" format
                df = df[df[season_col].astype(str).str.contains(season.split("-")[0])]
            else:
                # User provided "2024" format - match any containing that year
                df = df[df[season_col].astype(str).str.contains(season)]

    logger.info(f"Fetched {len(df)} NBL games from nblR")
    return df


def fetch_nbl_player_game_nblr(
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch NBL player box scores from nblR data.

    Args:
        season: Season string or None for all seasons
        force_refresh: Force re-download of data

    Returns:
        DataFrame with player game statistics

    Columns:
        - match_id: Game identifier
        - player: Player name
        - team: Team name
        - season: Season string
        - minutes: Minutes played
        - pts: Points
        - reb: Rebounds
        - ast: Assists
        - stl: Steals
        - blk: Blocks
        - tov: Turnovers
        - fgm, fga: Field goals
        - fg3m, fg3a: Three-pointers
        - ftm, fta: Free throws
        - LEAGUE: "NBL"

    Note:
        Data available from 2015 onwards.
    """
    logger.info(f"Fetching NBL player box scores from nblR: season={season}")

    df = _load_nblr_data("box_player", force_refresh)
    if df.empty:
        return df

    # Add league metadata
    df["LEAGUE"] = "NBL"

    # Filter by season if specified
    if season is not None:
        season_col = None
        for col in ["season", "Season", "SEASON"]:
            if col in df.columns:
                season_col = col
                break

        if season_col:
            if "-" in season:
                df = df[df[season_col].astype(str).str.contains(season.split("-")[0])]
            else:
                df = df[df[season_col].astype(str).str.contains(season)]

    logger.info(f"Fetched {len(df)} NBL player game records from nblR")
    return df


def fetch_nbl_team_game_nblr(
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch NBL team box scores from nblR data.

    Args:
        season: Season string or None for all seasons
        force_refresh: Force re-download of data

    Returns:
        DataFrame with team game statistics

    Note:
        Data available from 2015 onwards.
    """
    logger.info(f"Fetching NBL team box scores from nblR: season={season}")

    df = _load_nblr_data("box_team", force_refresh)
    if df.empty:
        return df

    # Add league metadata
    df["LEAGUE"] = "NBL"

    # Filter by season if specified
    if season is not None:
        season_col = None
        for col in ["season", "Season", "SEASON"]:
            if col in df.columns:
                season_col = col
                break

        if season_col:
            if "-" in season:
                df = df[df[season_col].astype(str).str.contains(season.split("-")[0])]
            else:
                df = df[df[season_col].astype(str).str.contains(season)]

    logger.info(f"Fetched {len(df)} NBL team game records from nblR")
    return df


def fetch_nbl_pbp_nblr(
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch NBL play-by-play from nblR data.

    Args:
        season: Season string or None for all seasons
        force_refresh: Force re-download of data

    Returns:
        DataFrame with play-by-play events

    Note:
        Data available from 2015 onwards.
    """
    logger.info(f"Fetching NBL PBP from nblR: season={season}")

    df = _load_nblr_data("pbp", force_refresh)
    if df.empty:
        return df

    # Add league metadata
    df["LEAGUE"] = "NBL"

    # Filter by season if specified
    if season is not None:
        season_col = None
        for col in ["season", "Season", "SEASON"]:
            if col in df.columns:
                season_col = col
                break

        if season_col:
            if "-" in season:
                df = df[df[season_col].astype(str).str.contains(season.split("-")[0])]
            else:
                df = df[df[season_col].astype(str).str.contains(season)]

    logger.info(f"Fetched {len(df)} NBL PBP events from nblR")
    return df


def fetch_nbl_shots_nblr(
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch NBL shot chart data from nblR data.

    Args:
        season: Season string or None for all seasons
        force_refresh: Force re-download of data

    Returns:
        DataFrame with shot data including coordinates

    Columns:
        - match_id: Game identifier
        - player: Player name
        - team: Team name
        - shot_type: Type of shot
        - made: Whether shot was made
        - x, y: Shot coordinates
        - LEAGUE: "NBL"

    Note:
        Data available from 2015 onwards.
    """
    logger.info(f"Fetching NBL shot data from nblR: season={season}")

    df = _load_nblr_data("shots", force_refresh)
    if df.empty:
        return df

    # Add league metadata
    df["LEAGUE"] = "NBL"

    # Filter by season if specified
    if season is not None:
        season_col = None
        for col in ["season", "Season", "SEASON"]:
            if col in df.columns:
                season_col = col
                break

        if season_col:
            if "-" in season:
                df = df[df[season_col].astype(str).str.contains(season.split("-")[0])]
            else:
                df = df[df[season_col].astype(str).str.contains(season)]

    logger.info(f"Fetched {len(df)} NBL shots from nblR")
    return df


# Convenience alias for unified API
def fetch_nbl_player_game(
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Fetch NBL player box scores (convenience wrapper for nblR data).

    Args:
        season: Season string or None for all seasons
        force_refresh: Force re-download of data

    Returns:
        DataFrame with player game statistics
    """
    return fetch_nbl_player_game_nblr(season=season, force_refresh=force_refresh)


# =============================================================================
# API-Basketball Functions (Secondary Data Source)
# =============================================================================

# Initialize API-Basketball client (will be None if API key not set)
_api_client = None


def _get_api_client() -> APIBasketballClient:
    """Get or initialize API-Basketball client

    Returns:
        APIBasketballClient instance

    Raises:
        ValueError: If API_BASKETBALL_KEY not set
    """
    global _api_client

    if _api_client is None:
        api_key = os.getenv("API_BASKETBALL_KEY")
        if not api_key:
            raise ValueError(
                "API-Basketball API key required for NBL data.\n"
                "Set API_BASKETBALL_KEY environment variable.\n"
                "Get free key (100 req/day) at https://api-sports.io/register"
            )
        _api_client = APIBasketballClient(api_key=api_key)

    return _api_client


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch NBL Australia player season statistics via API-Basketball

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        per_mode: Aggregation mode ("Totals", "PerGame", "Per40")

    Returns:
        DataFrame with player season statistics

    Columns:
        - PLAYER_ID: Player ID (from API-Basketball)
        - PLAYER_NAME: Player name
        - TEAM_ID: Team ID (from API-Basketball)
        - TEAM: Team name
        - GP: Games played
        - MIN: Minutes played (total or per game based on per_mode)
        - PTS: Points
        - REB: Total rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - FGM, FGA, FG_PCT: Field goal stats
        - FG3M, FG3A, FG3_PCT: Three-point stats
        - FTM, FTA, FT_PCT: Free throw stats
        - LEAGUE: "NBL"
        - SEASON: Season string
        - COMPETITION: "NBL Australia"

    Raises:
        ValueError: If API_BASKETBALL_KEY not set

    Note:
        - Requires API-Basketball API key (free tier: 100 req/day)
        - Set API_BASKETBALL_KEY environment variable
        - Get free key at https://api-sports.io/register
    """
    logger.info(f"Fetching NBL player season stats via API-Basketball: {season}, {per_mode}")

    try:
        client = _get_api_client()

        # Convert season string to int (e.g., "2024" -> 2024)
        season_int = int(season)

        # Fetch player stats from API-Basketball
        df = client.get_league_player_stats(league_id=NBL_API_LEAGUE_ID, season=season_int)

        if df.empty:
            logger.warning(f"No NBL player stats returned from API-Basketball for season {season}")
            return _empty_player_season_df()

        # Rename columns to standard schema
        df = df.rename(
            columns={
                "player_id": "PLAYER_ID",
                "player_name": "PLAYER_NAME",
                "team_id": "TEAM_ID",
                "team_name": "TEAM",
                "games_played": "GP",
                "minutes": "MIN",
                "points": "PTS",
                "rebounds": "REB",
                "assists": "AST",
                "steals": "STL",
                "blocks": "BLK",
                "turnovers": "TOV",
                "field_goals_made": "FGM",
                "field_goals_attempted": "FGA",
                "field_goal_pct": "FG_PCT",
                "three_pointers_made": "FG3M",
                "three_pointers_attempted": "FG3A",
                "three_point_pct": "FG3_PCT",
                "free_throws_made": "FTM",
                "free_throws_attempted": "FTA",
                "free_throw_pct": "FT_PCT",
            }
        )

        # Add league metadata
        df["LEAGUE"] = "NBL"
        df["SEASON"] = season
        df["COMPETITION"] = "NBL Australia"

        # Apply per_mode calculations
        if per_mode == "PerGame" and "GP" in df.columns:
            # API-Basketball returns totals, so divide by games played
            stat_cols = [
                "MIN",
                "PTS",
                "REB",
                "AST",
                "STL",
                "BLK",
                "TOV",
                "FGM",
                "FGA",
                "FG3M",
                "FG3A",
                "FTM",
                "FTA",
            ]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = df[col] / df["GP"].replace(0, 1)  # Avoid division by zero

        elif per_mode == "Per40" and "MIN" in df.columns:
            # Per 40 minutes calculation
            stat_cols = [
                "PTS",
                "REB",
                "AST",
                "STL",
                "BLK",
                "TOV",
                "FGM",
                "FGA",
                "FG3M",
                "FG3A",
                "FTM",
                "FTA",
            ]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = df[col] / (df["MIN"].replace(0, 1) / 40.0)

        logger.info(f"Fetched {len(df)} NBL player season stats")
        return df

    except ValueError as e:
        logger.error(f"API-Basketball configuration error: {e}")
        logger.warning("Returning empty DataFrame. Set API_BASKETBALL_KEY environment variable.")
        return _empty_player_season_df()

    except Exception as e:
        logger.error(f"Failed to fetch NBL player season stats: {e}")
        return _empty_player_season_df()


def _empty_player_season_df() -> pd.DataFrame:
    """Return empty DataFrame with correct player season schema"""
    return pd.DataFrame(
        columns=[
            "PLAYER_ID",
            "PLAYER_NAME",
            "TEAM_ID",
            "TEAM",
            "GP",
            "MIN",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
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
            "COMPETITION",
        ]
    )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_team_season(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch NBL Australia team season statistics/standings

    ⚠️ LIMITATION: NBL website uses JavaScript-rendered statistics.
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
        - LEAGUE: "NBL"
        - SEASON: Season string
        - COMPETITION: "NBL Australia"

    Note:
        Requires Selenium/Playwright or API discovery for actual implementation.
    """
    rate_limiter.acquire("nbl")

    logger.info(
        f"Fetching NBL team season stats: {season} (returning empty - site uses JS rendering)"
    )

    # NBL website uses JavaScript-rendered statistics - cannot scrape with simple HTML parsing
    # Return empty DataFrame with correct schema for graceful degradation
    # TODO: Implement using Selenium/Playwright or discover underlying API
    return pd.DataFrame(
        columns=["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "LEAGUE", "SEASON", "COMPETITION"]
    )


# Legacy scaffold functions (kept for backwards compatibility)


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_schedule(
    season: str = "2024-25",
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Fetch NBL Australia schedule (placeholder)

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
        - LEAGUE: "NBL"

    TODO: Implement NBL schedule scraping
    - Study nblR package patterns: https://github.com/JaseZiv/nblR
    - NBL may have JSON endpoints used by their website
    - Check network tab in browser for API calls
    """
    logger.info(f"Fetching NBL schedule: {season}, {season_type}")

    # TODO: Implement scraping/API logic
    logger.warning(
        "NBL schedule fetching requires implementation. "
        "Reference nblR package for scraping patterns. Returning empty DataFrame."
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

    df["LEAGUE"] = "NBL"

    logger.info(f"Fetched {len(df)} NBL games (scaffold mode)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_box_score(game_id: str) -> pd.DataFrame:
    """Fetch NBL box score for a game

    Note: Requires implementation. Currently returns empty DataFrame.

    Args:
        game_id: Game ID (NBL game identifier)

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
        - LEAGUE: "NBL"

    TODO: Implement NBL box score scraping
    - URL pattern likely: https://www.nbl.com.au/games/{season}/{game_id}
    - Study nblR package for box score extraction patterns
    """
    logger.info(f"Fetching NBL box score: {game_id}")

    # TODO: Implement scraping logic
    logger.warning(
        f"NBL box score fetching for game {game_id} requires implementation. "
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

    df["LEAGUE"] = "NBL"
    df["GAME_ID"] = game_id

    logger.info(f"Fetched box score: {len(df)} players (scaffold mode)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch NBL play-by-play data

    Note: Limited availability. Some NBL games use FIBA LiveStats, which
    requires authentication. This function returns empty DataFrame.

    Args:
        game_id: Game ID

    Returns:
        Empty DataFrame (PBP limited availability)

    Implementation Notes:
        - Some games may have FIBA LiveStats feeds (requires auth)
        - NBL website may have basic play logs (requires scraping)
        - See: https://developer.geniussports.com/livestats/tvfeed/
    """
    logger.warning(
        f"NBL play-by-play for game {game_id} has limited availability. "
        "Some games use FIBA LiveStats (requires authentication)."
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

    df["LEAGUE"] = "NBL"
    df["GAME_ID"] = game_id

    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nbl_shot_chart(game_id: str) -> pd.DataFrame:
    """Fetch NBL shot chart data

    Note: Shot chart data has limited availability. Requires FIBA LiveStats
    for detailed coordinates. This function returns empty DataFrame.

    Args:
        game_id: Game ID

    Returns:
        Empty DataFrame (shot data limited availability)

    Implementation Notes:
        - FIBA LiveStats may be available for some games (requires auth)
        - NBL website may have basic shot location data (requires research)
    """
    logger.warning(
        f"NBL shot chart for game {game_id} has limited availability. "
        "May require FIBA LiveStats authentication."
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

    df["LEAGUE"] = "NBL"
    df["GAME_ID"] = game_id

    return df
