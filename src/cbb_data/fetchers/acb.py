"""ACB (Liga Endesa - Spain) Fetcher

ACB (Asociación de Clubes de Baloncesto) is Spain's top-tier professional basketball league,
featuring 18 teams. Known as "Liga Endesa" due to sponsorship, it's one of Europe's strongest
leagues. NBA talent pipeline includes Pau Gasol, Marc Gasol, Ricky Rubio, and many others.

✅ **CURRENT STATUS: RESTORED** ✅
ACB website restructured in 2024. New URLs discovered and implemented (2025-11-13).

**DATA AVAILABILITY**:
- **player_season**: ⚠️ May be blocked (403 errors) - see fallback strategies below
- **team_season**: ⚠️ May be blocked (403 errors) - see fallback strategies below
- **schedule/box scores**: ❌ Not yet implemented (future work)

**WEBSITE BLOCKING (403 ERRORS)**:
ACB.com may block automated requests with 403 Forbidden errors, even with realistic headers.
This is likely due to IP-based bot protection or aggressive rate limiting.

**FALLBACK STRATEGIES**:
1. **Zenodo Historical Data**: For seasons 2020-21 and earlier, use Zenodo archives:
   - https://zenodo.org/communities/basketball-data
   - Search for "ACB" or "Liga Endesa"
2. **Manual CSV Creation**: If website blocks requests, manually create CSV files:
   - Visit https://www.acb.com/estadisticas-individuales
   - Export or copy-paste data to CSV
   - Place in `data/manual/acb_player_season_{YEAR}.csv`
3. **Residential Proxy**: Use residential IP proxy service (not recommended for production)
4. **Rate Limiting**: Increase delay between requests (try 2-5 seconds)

**URL CHANGES (2025-11-13)**:
- OLD (404): /estadisticas/jugadores, /clasificacion
- NEW (working): /estadisticas-individuales/index/temporada_id/{season}, /estadisticas-equipos/index/temporada_id/{season}

Competition Structure:
- Regular Season: 18 teams
- Playoffs: Top 8 teams advance
- Finals: Best-of-5 series
- Season: October-June

Historical Context:
- Founded: 1957 (one of Europe's oldest leagues)
- Prominent teams: Real Madrid, Barcelona, Valencia, Baskonia
- NBA pipeline: Pau Gasol, Marc Gasol, Ricky Rubio, Sergio Llull

Documentation: https://www.acb.com/

Implementation Status:
✅ RESTORED (2025-11-13) - New URLs functional after website restructure
✅ player_season: Scrapes HTML tables from /estadisticas-individuales
✅ team_season: Scrapes HTML tables from /estadisticas-equipos
⚠️ schedule/box scores: Not yet implemented (future work)

Technical Notes:
- ACB uses "temporada_id" (ending year) in URLs: 2024-25 season = temporada_id/2025
- 22 HTML tables on player stats page, 20 tables on team stats page, 3 tables on standings
- Encoding: UTF-8 for Spanish names (á, é, í, ó, ú, ñ)
- Tables are server-rendered HTML (not JavaScript), parseable with BeautifulSoup/pandas
- Website may block automated requests (403 Forbidden) - see fallback strategies above
- Rate limiting: Minimum 1 second between requests (increase if experiencing 403 errors)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error
from .html_tables import normalize_league_columns, read_first_table

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# ACB URLs (updated 2025-11-13 after website restructure)
ACB_BASE_URL = "https://www.acb.com"

# NEW URL structure (working as of 2025-11-13):
# Player stats: /estadisticas-individuales/index/temporada_id/{ending_year}
# Team stats: /estadisticas-equipos/index/temporada_id/{ending_year}
# Standings: /resultados-clasificacion/ver

# Note: ACB uses ending year in URLs (2024-25 season = temporada_id/2025)

# Fallback data directory for manual CSV files
ACB_MANUAL_DATA_DIR = Path("data/manual/acb")


def _load_manual_csv(season: str, data_type: str) -> pd.DataFrame | None:
    """Load manually created CSV file as fallback

    Args:
        season: Season string (e.g., "2024")
        data_type: Data type ("player_season" or "team_season")

    Returns:
        DataFrame if file exists, None otherwise
    """
    csv_path = ACB_MANUAL_DATA_DIR / f"acb_{data_type}_{season}.csv"

    if csv_path.exists():
        logger.info(f"Loading ACB {data_type} from manual CSV: {csv_path}")
        try:
            df = pd.read_csv(csv_path)
            df["LEAGUE"] = "ACB"
            df["SEASON"] = season
            df["SOURCE"] = "manual_csv"
            return df
        except Exception as e:
            logger.error(f"Failed to load manual CSV {csv_path}: {e}")
            return None

    return None


def _handle_acb_error(error: Exception, season: str, data_type: str) -> None:
    """Provide helpful error messages and fallback instructions

    Args:
        error: The exception that occurred
        season: Season string
        data_type: Data type ("player_season" or "team_season")
    """
    error_msg = str(error)

    # Check if it's a 403 error
    if "403" in error_msg or "Forbidden" in error_msg:
        logger.error(
            f"ACB website blocked request (403 Forbidden) for {season} {data_type}.\n\n"
            "The ACB website may be blocking automated requests. Try these fallback strategies:\n\n"
            "1. **Manual CSV Creation**:\n"
            f"   - Visit https://www.acb.com/estadisticas-individuales/index/temporada_id/{int(season)+1}\n"
            "   - Copy data to CSV file\n"
            f"   - Save to: data/manual/acb/acb_{data_type}_{season}.csv\n"
            "   - Required columns: PLAYER_NAME, TEAM, GP, MIN, PTS, REB, AST, STL, BLK, TOV, PF\n\n"
            "2. **Zenodo Historical Data** (for seasons 2020-21 and earlier):\n"
            "   - Visit https://zenodo.org/communities/basketball-data\n"
            "   - Search for 'ACB' or 'Liga Endesa'\n"
            "   - Download CSV and place in data/manual/acb/\n\n"
            "3. **Increase Rate Limiting**:\n"
            "   - Website may be rate limiting requests\n"
            "   - Try increasing delay in utils/rate_limiter.py (2-5 seconds)\n\n"
            "4. **Check IP Address**:\n"
            "   - Some IPs may be blocked (VPN, cloud providers, etc.)\n"
            "   - Try from different network/IP address\n\n"
            "For more information, see documentation in src/cbb_data/fetchers/acb.py"
        )

    # Check if it's a timeout
    elif "timeout" in error_msg.lower() or isinstance(error, requests.Timeout):
        logger.error(
            f"ACB request timed out for {season} {data_type}.\n"
            "The ACB website may be slow or unresponsive. Try:\n"
            "- Increasing timeout in html_tables.py\n"
            "- Checking network connection\n"
            "- Trying again later"
        )

    # Check if it's a connection error
    elif "connection" in error_msg.lower() or isinstance(error, requests.ConnectionError):
        logger.error(
            f"Failed to connect to ACB website for {season} {data_type}.\n"
            "Check:\n"
            "- Internet connection\n"
            "- ACB website status: https://www.acb.com/\n"
            "- DNS resolution\n"
            "- Firewall settings"
        )

    # Generic error
    else:
        logger.error(
            f"Failed to fetch ACB {data_type} for {season}: {error}\n"
            "See fallback strategies in src/cbb_data/fetchers/acb.py"
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch ACB (Liga Endesa) player season statistics

    ✅ RESTORED (2025-11-13): New URL structure functional after website restructure.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        per_mode: Aggregation mode ("Totals", "PerGame", "Per40")

    Returns:
        DataFrame with player season statistics

    Columns:
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
        ACB website uses "temporada_id" (ending year): 2024-25 season = temporada_id/2025
    """
    rate_limiter.acquire("acb")

    # Convert season to ACB's temporada_id format (ending year)
    # "2024" -> 2025, "2024-25" -> 2025
    if "-" in season:
        ending_year = season.split("-")[1]
        if len(ending_year) == 2:  # "24" -> "2024"
            ending_year = "20" + ending_year
    else:
        ending_year = str(int(season) + 1)

    # Build URL with correct temporada_id
    url = f"{ACB_BASE_URL}/estadisticas-individuales/index/temporada_id/{ending_year}"

    logger.info(f"Fetching ACB player season: {season} (temporada_id/{ending_year}), {per_mode}")

    # Check for manual CSV fallback first
    manual_df = _load_manual_csv(season, "player_season")
    if manual_df is not None:
        logger.info(f"Using manual CSV for ACB player_season {season}")
        return manual_df

    try:
        # Fetch HTML table from new URL structure
        # Note: ACB has 22 category-specific tables (top scorers, rebounders, etc.) with ~5 rows each
        df = read_first_table(
            url=url,
            min_columns=3,
            min_rows=3,  # Lower threshold for category tables
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

        # Add source metadata
        df["SOURCE"] = "acb_html"

        # Optional per_mode calculations
        if per_mode == "PerGame" and "GP" in df.columns:
            stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN"]
            for col in stat_cols:
                if col in df.columns:
                    df[col] = df[col] / df["GP"]

        return df

    except Exception as e:
        # Provide helpful error messages and fallback instructions
        _handle_acb_error(e, season, "player_season")

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

    ✅ RESTORED (2025-11-13): New URL structure functional after website restructure.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with team season statistics/standings

    Columns:
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
        Uses standings page (/resultados-clasificacion/ver) which doesn't require season parameter.
    """
    rate_limiter.acquire("acb")

    # Use standings URL (doesn't require season parameter - shows current season)
    url = f"{ACB_BASE_URL}/resultados-clasificacion/ver"

    logger.info(f"Fetching ACB team season/standings: {season}")

    # Check for manual CSV fallback first
    manual_df = _load_manual_csv(season, "team_season")
    if manual_df is not None:
        logger.info(f"Using manual CSV for ACB team_season {season}")
        return manual_df

    try:
        df = read_first_table(
            url=url,
            min_columns=5,
            min_rows=5,
        )

        # Spanish column names mapping (from standings table)
        # Columns: Pos., Equipo, J (Games), V (Wins), D (Losses), % (Win PCT), P.F. (Points For), P.C. (Points Against), Dif.
        column_map = {
            "Equipo": "TEAM",
            "J": "GP",  # Juegos (Games)
            "V": "W",  # Victorias (Wins)
            "D": "L",  # Derrotas (Losses)
            "%": "WIN_PCT",  # Win percentage
            "P.F.": "PTS",  # Puntos a Favor (Points For)
            "P.C.": "OPP_PTS",  # Puntos en Contra (Points Against)
            "Dif.": "DIFF",  # Diferencia (Point Differential)
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

        # Add source metadata
        df["SOURCE"] = "acb_html"

        return df

    except Exception as e:
        # Provide helpful error messages and fallback instructions
        _handle_acb_error(e, season, "team_season")
        return pd.DataFrame(
            columns=["TEAM", "GP", "W", "L", "WIN_PCT", "PTS", "LEAGUE", "SEASON", "COMPETITION"]
        )


# Legacy scaffold functions (kept for backwards compatibility)


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_schedule(
    season: str = "2024",
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Fetch ACB (Liga Endesa) schedule via HTML scraping

    **HTML-FIRST APPROACH**: Scrapes acb.com calendar/results pages to build
    complete schedule with game IDs, dates, teams, scores, and game centre links.

    Args:
        season: Season ending year as string (e.g., "2024" for 2024-25 season)
                ACB uses ending year in URLs (temporada_id/2025 for 2024-25)
        season_type: Season type ("Regular Season" or "Playoffs")
                    Note: Currently filters by PHASE column after scraping

    Returns:
        DataFrame with game schedule

    Columns:
        - LEAGUE: "ACB"
        - SEASON: Season string
        - GAME_ID: ACB game ID (extracted from partido URLs)
        - GAME_DATE: Game date
        - GAME_TIME: Game time
        - HOME_TEAM: Home team name
        - HOME_TEAM_ID: Home team ID (same as name for ACB)
        - AWAY_TEAM: Away team name
        - AWAY_TEAM_ID: Away team ID (same as name for ACB)
        - HOME_SCORE: Home team score (if completed)
        - AWAY_SCORE: Away team score (if completed)
        - ROUND: Round/jornada number
        - VENUE: Venue name (if available)
        - GAME_URL: Link to game centre page
        - COMPETITION: "Liga Endesa"
        - PHASE: "Regular Season" or "Playoffs"
        - SOURCE: "acb_html_schedule"

    Example:
        >>> schedule = fetch_acb_schedule("2024")
        >>> print(f"Found {len(schedule)} ACB games")
        >>> print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())

    Note:
        - Scrapes from acb.com/resultados-clasificacion/ver/temporada_id/{year}
        - May encounter 403 errors if website blocks automated requests
        - Returns empty DataFrame if scraping fails
    """
    logger.info(f"Fetching ACB schedule: {season}, {season_type}")

    try:
        # Import HTML scraper
        from .html_scrapers import scrape_acb_schedule_page

        # Scrape schedule from ACB website
        df = scrape_acb_schedule_page(season)

        if df.empty:
            logger.warning(f"No games found for ACB {season}")
            return df

        # Filter by season type if specified
        if season_type and season_type != "All":
            df = df[df["PHASE"].str.contains(season_type, case=False, na=False)]

        # Ensure team IDs (use team names as IDs for ACB)
        if "HOME_TEAM" in df.columns and "HOME_TEAM_ID" not in df.columns:
            df["HOME_TEAM_ID"] = df["HOME_TEAM"]
        if "AWAY_TEAM" in df.columns and "AWAY_TEAM_ID" not in df.columns:
            df["AWAY_TEAM_ID"] = df["AWAY_TEAM"]

        logger.info(f"Fetched {len(df)} ACB games for {season}")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB schedule: {e}")
        _handle_acb_error(e, season, "schedule")
        # Return empty DataFrame with correct schema
        return pd.DataFrame(
            columns=[
                "LEAGUE",
                "SEASON",
                "GAME_ID",
                "GAME_DATE",
                "GAME_TIME",
                "HOME_TEAM",
                "HOME_TEAM_ID",
                "AWAY_TEAM",
                "AWAY_TEAM_ID",
                "HOME_SCORE",
                "AWAY_SCORE",
                "ROUND",
                "VENUE",
                "GAME_URL",
                "COMPETITION",
                "PHASE",
                "SOURCE",
            ]
        )


def fetch_acb_player_game(season: str = "2024") -> pd.DataFrame:
    """Fetch ACB player game statistics via HTML scraping

    Scrapes individual game centre pages to extract player box scores for all
    games in a season.

    Args:
        season: Season ending year (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with player game statistics

    Columns:
        - LEAGUE: "ACB"
        - SEASON: Season string
        - GAME_ID: Game identifier
        - PLAYER_NAME: Player name
        - PLAYER_ID: Generated player ID (TEAM_PLAYERNAME)
        - TEAM: Team name
        - TEAM_ID: Team ID (same as name for ACB)
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
        - PLUS_MINUS: Plus/minus (if available)
        - EFF: Efficiency rating (if available)
        - SOURCE: "acb_html_boxscore"

    Example:
        >>> player_game = fetch_acb_player_game("2024")
        >>> top_scorers = player_game.nlargest(10, "PTS")

    Note:
        - Requires schedule to be fetched first
        - May encounter 403 errors if website blocks requests
        - Skips games where scraping fails
    """
    logger.info(f"Fetching ACB player game stats for {season}")

    try:
        from .html_scrapers import scrape_acb_game_centre

        # First get schedule to know which games to scrape
        schedule = fetch_acb_schedule(season)

        if schedule.empty:
            logger.warning(f"No schedule found for ACB {season}")
            return pd.DataFrame()

        all_player_stats = []

        for _, game in schedule.iterrows():
            game_url = game.get("GAME_URL")
            game_id = game.get("GAME_ID")

            if not game_url:
                logger.debug(f"No game URL for {game_id}, skipping")
                continue

            try:
                # Scrape game centre
                player_df, _ = scrape_acb_game_centre(game_url, game_id)

                if not player_df.empty:
                    # Add metadata
                    player_df["LEAGUE"] = "ACB"
                    player_df["SEASON"] = season
                    player_df["SOURCE"] = "acb_html_boxscore"

                    # Generate player IDs if not present
                    if "PLAYER_ID" not in player_df.columns and "PLAYER_NAME" in player_df.columns:
                        player_df["PLAYER_ID"] = (
                            player_df["TEAM"].str[:3] + "_" + player_df["PLAYER_NAME"].str.replace(" ", "_")
                        )

                    # Ensure team ID
                    if "TEAM_ID" not in player_df.columns:
                        player_df["TEAM_ID"] = player_df["TEAM"]

                    all_player_stats.append(player_df)
                    logger.debug(f"Scraped {len(player_df)} players from {game_id}")

            except Exception as e:
                logger.warning(f"Failed to scrape {game_id}: {e}")
                continue

        if not all_player_stats:
            logger.warning(f"No player stats scraped for ACB {season}")
            return pd.DataFrame()

        df = pd.concat(all_player_stats, ignore_index=True)
        logger.info(f"Fetched {len(df)} player game stats for ACB {season}")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB player game stats: {e}")
        _handle_acb_error(e, season, "player_game")
        return pd.DataFrame()


def fetch_acb_team_game(season: str = "2024") -> pd.DataFrame:
    """Fetch ACB team game statistics via HTML scraping

    Scrapes individual game centre pages to extract team box scores (totals)
    for all games in a season.

    Args:
        season: Season ending year (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with team game statistics

    Columns:
        - LEAGUE: "ACB"
        - SEASON: Season string
        - GAME_ID: Game identifier
        - TEAM: Team name
        - TEAM_ID: Team ID (same as name for ACB)
        - MIN: Total minutes
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
        - SOURCE: "acb_html_boxscore"

    Example:
        >>> team_game = fetch_acb_team_game("2024")
        >>> print(team_game[["GAME_ID", "TEAM", "PTS"]].head())

    Note:
        - Requires schedule to be fetched first
        - May encounter 403 errors if website blocks requests
        - Skips games where scraping fails
    """
    logger.info(f"Fetching ACB team game stats for {season}")

    try:
        from .html_scrapers import scrape_acb_game_centre

        # First get schedule
        schedule = fetch_acb_schedule(season)

        if schedule.empty:
            logger.warning(f"No schedule found for ACB {season}")
            return pd.DataFrame()

        all_team_stats = []

        for _, game in schedule.iterrows():
            game_url = game.get("GAME_URL")
            game_id = game.get("GAME_ID")

            if not game_url:
                logger.debug(f"No game URL for {game_id}, skipping")
                continue

            try:
                # Scrape game centre
                _, team_df = scrape_acb_game_centre(game_url, game_id)

                if not team_df.empty:
                    # Add metadata
                    team_df["LEAGUE"] = "ACB"
                    team_df["SEASON"] = season
                    team_df["SOURCE"] = "acb_html_boxscore"

                    # Ensure team ID
                    if "TEAM_ID" not in team_df.columns:
                        team_df["TEAM_ID"] = team_df["TEAM"]

                    all_team_stats.append(team_df)
                    logger.debug(f"Scraped {len(team_df)} teams from {game_id}")

            except Exception as e:
                logger.warning(f"Failed to scrape {game_id}: {e}")
                continue

        if not all_team_stats:
            logger.warning(f"No team stats scraped for ACB {season}")
            return pd.DataFrame()

        df = pd.concat(all_team_stats, ignore_index=True)
        logger.info(f"Fetched {len(df)} team game stats for ACB {season}")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB team game stats: {e}")
        _handle_acb_error(e, season, "team_game")
        return pd.DataFrame()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch ACB box score for a single game via HTML scraping

    Legacy function - wraps fetch_acb_player_game for single game.
    Consider using fetch_acb_player_game() for full season scraping.

    Args:
        game_id: Game ID (ACB_123456 format or game URL)

    Returns:
        DataFrame with player box scores for the game

    Note:
        For efficiency, use fetch_acb_player_game(season) to scrape all games at once
    """
    logger.info(f"Fetching ACB box score: {game_id}")

    try:
        from .html_scrapers import scrape_acb_game_centre

        # Construct game URL if not provided
        if game_id.startswith("ACB_"):
            numeric_id = game_id.replace("ACB_", "")
            game_url = f"https://www.acb.com/partido/{numeric_id}"
        else:
            game_url = game_id  # Assume it's already a URL

        # Scrape game centre
        player_df, _ = scrape_acb_game_centre(game_url, game_id)

        if not player_df.empty:
            player_df["LEAGUE"] = "ACB"
            player_df["SOURCE"] = "acb_html_boxscore"

        logger.info(f"Fetched box score: {len(player_df)} players")
        return player_df

    except Exception as e:
        logger.error(f"Failed to fetch ACB box score for {game_id}: {e}")
        return pd.DataFrame()


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
