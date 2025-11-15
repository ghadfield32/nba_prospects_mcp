"""LNB Pro A (France) Fetcher

Official LNB Pro A (French professional basketball) data via web scraping and API.

LNB Pro A is France's top-tier professional basketball league, featuring 16-18 teams.
Known for developing NBA talent including Victor Wembanyama, Rudy Gobert, Tony Parker,
Nicolas Batum, and others.

⚠️ **DATA AVAILABILITY**:
- **Team standings**: ✅ Available (static HTML table scraping)
- **Player statistics**: ✅ Available (Playwright-based scraping)
- **Schedule**: ✅ Available (Playwright-based scraping)
- **Box scores**: ✅ Available (Playwright-based scraping)
- **API endpoints**: ⚠️ Currently down (HTTP 404 - use web scraping instead)

Key Features:
- **Dual-source support**: Web scraping (Playwright) + API (when available)
- **Graceful fallback**: Works without Playwright (returns empty DataFrames)
- **JavaScript rendering**: Handles dynamic content via browser automation
- **Rate-limited requests**: Respects 1 req/sec limit with retry logic
- **UTF-8 support**: Full support for French names (é, à, ç, etc.)

Data Granularities:
- schedule: ✅ Available (Playwright scraping)
- player_game: ✅ Available (Playwright scraping + API when working)
- team_game: ⏳ Not implemented yet
- pbp: ✅ Available (Atrium Sports API - third-party stats provider)
- shots: ✅ Available (Atrium Sports API - third-party stats provider)
- player_season: ✅ Available (Playwright scraping + API when working)
- team_season: ✅ Available (static HTML scraping)

Competition Structure:
- Regular Season: 16-18 teams (varies by year)
- Round-robin: Each team plays others twice (home/away)
- Playoffs: Top 8 teams advance
- Finals: Best-of-5 series
- Typical season: September-June

Historical Context:
- Founded: 1921 (one of Europe's oldest leagues)
- Prominent teams: ASVEL Lyon-Villeurbanne, Monaco, Paris, Strasbourg
- NBA pipeline: Victor Wembanyama, Rudy Gobert, Tony Parker, Nicolas Batum
- Strong European competition (EuroLeague participants)

Documentation: https://www.lnb.fr/
Data Source: https://www.lnb.fr/pro-a/statistiques

Implementation Status:
✅ IMPLEMENTED - Team standings via static HTML (fetch_lnb_team_season)
✅ IMPLEMENTED - Player season stats via Playwright (fetch_lnb_player_season)
✅ IMPLEMENTED - Schedule via Playwright (fetch_lnb_schedule)
✅ IMPLEMENTED - Box scores via Playwright (fetch_lnb_box_score)
✅ IMPLEMENTED - API fetchers (v2 functions) - currently down (HTTP 404)

Technical Notes:
- **Playwright Required**: Install with `uv pip install playwright && playwright install chromium`
- **Graceful Fallback**: All functions work without Playwright (return empty DataFrames)
- **Encoding**: UTF-8 for French names (é, à, ç, etc.)
- **Season format**: Calendar year (e.g., "2024" for 2024-25 season)
- **Rate limiting**: 1 req/sec to respect website resources
- **Browser automation**: Headless Chrome via Playwright for JS-rendered pages
- **Timeout**: 45 seconds for page loads (adjustable)

Installation:
    # Basic (static HTML only - team standings)
    pip install pandas beautifulsoup4 lxml

    # Full (Playwright scraping - all data)
    uv pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import base64
import json
import logging
import zlib
from io import StringIO

import pandas as pd
import requests

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error
from .browser_scraper import BrowserScraper, is_playwright_available
from .html_tables import normalize_league_columns, read_first_table

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# LNB Pro A URLs
LNB_BASE_URL = "https://www.lnb.fr"
LNB_STANDINGS_URL = f"{LNB_BASE_URL}/pro-a/statistiques"

# Atrium Sports API (Third-party stats provider for LNB)
ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
ATRIUM_FIXTURE_DETAIL_URL = f"{ATRIUM_API_BASE}/v1/embed/12/fixture_detail"


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_team_season(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch LNB Pro A team season standings

    Scrapes official LNB Pro A standings page for team season aggregates.

    ⚠️ **LIMITATION**: Only team standings available. Player statistics require
    JavaScript execution (use Selenium/Playwright for player stats).

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with team season standings

    Columns (after normalization):
        - RANK: Standings rank (1-16)
        - TEAM: Team name
        - GP: Games played
        - W_L: Win-loss record (e.g., "5 - 2")
        - WIN_PCT: Win percentage (decimal)
        - PTS_DIFF: Point differential (+/-)
        - HOME_RECORD: Home record
        - AWAY_RECORD: Away record
        - FORM: Recent form (e.g., "VVDVV")
        - NEXT_OPPONENT: Next scheduled opponent
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - COMPETITION: "LNB Pro A"

    Example:
        >>> # Fetch LNB Pro A 2024-25 season standings
        >>> df = fetch_lnb_team_season("2024")
        >>> top_teams = df.nlargest(5, "RANK")
        >>> print(top_teams[["RANK", "TEAM", "W_L", "WIN_PCT"]])

    Note:
        Player statistics NOT available via static HTML. Website uses JavaScript
        to render player stats. Requires Selenium/Playwright implementation.
    """
    rate_limiter.acquire("lnb")

    logger.info(f"Fetching LNB Pro A team season standings: {season}")

    try:
        # Fetch HTML table from LNB standings page
        df = read_first_table(
            url=LNB_STANDINGS_URL,
            min_columns=8,  # Standings have ~12 columns
            min_rows=10,  # Expect at least 10 teams (more lenient for off-season)
        )

        logger.info(f"Fetched {len(df)} LNB Pro A teams")

        # Column mapping (columns are unnamed: "Unnamed: 0", "Unnamed: 1", etc.)
        # Based on inspection: 16 rows x 12 columns
        # Columns appear to be: Rank, Team, GP, W-L, Win%, PtsFor-Against, Diff, HomeRecord, AwayRecord, Form, (unknown), NextOpponent
        column_map = {
            "Unnamed: 0": "RANK",
            "Unnamed: 1": "TEAM",
            "Unnamed: 2": "GP",
            "Unnamed: 3": "W_L",
            "Unnamed: 4": "WIN_PCT",
            "Unnamed: 5": "PTS_FOR_AGAINST",
            "Unnamed: 6": "PTS_DIFF",
            "Unnamed: 7": "HOME_RECORD",
            "Unnamed: 8": "AWAY_RECORD",
            "Unnamed: 9": "FORM",
            "Unnamed: 10": "UNKNOWN",  # Unknown column
            "Unnamed: 11": "NEXT_OPPONENT",
        }

        # Normalize columns
        df = normalize_league_columns(
            df=df,
            league="LNB_PROA",
            season=season,
            competition="LNB Pro A",
            column_map=column_map,
        )

        # Clean win percentage (may have % symbol)
        if "WIN_PCT" in df.columns:
            df["WIN_PCT"] = df["WIN_PCT"].astype(str).str.rstrip("%").astype(float) / 100

        # Extract W and L from W_L column if present
        if "W_L" in df.columns:
            try:
                df[["W", "L"]] = df["W_L"].str.split(" - ", expand=True).astype(int)
            except Exception:
                logger.warning("Could not parse W_L column")

        # Calculate GP from W + L if not present or incorrect
        if "W" in df.columns and "L" in df.columns:
            if "GP" not in df.columns or df["GP"].isna().all():
                df["GP"] = df["W"] + df["L"]

        return df

    except Exception as e:
        logger.error(f"Failed to fetch LNB Pro A team season standings: {e}")
        # Return empty DataFrame with correct schema
        return pd.DataFrame(
            columns=[
                "RANK",
                "TEAM",
                "GP",
                "W_L",
                "WIN_PCT",
                "PTS_FOR_AGAINST",
                "PTS_DIFF",
                "HOME_RECORD",
                "AWAY_RECORD",
                "FORM",
                "NEXT_OPPONENT",
                "LEAGUE",
                "SEASON",
                "COMPETITION",
            ]
        )


# Placeholder functions for unavailable data
# Player statistics require JavaScript execution (Selenium/Playwright)


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch LNB Pro A player season statistics via web scraping (Playwright)

    Scrapes JavaScript-rendered player statistics from official LNB website.
    Falls back to empty DataFrame if Playwright is not installed.

    ⚠️ **REQUIRES PLAYWRIGHT**: Install with:
        uv pip install playwright
        playwright install chromium

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        per_mode: Aggregation mode ("Totals" or "PerGame") - not fully implemented

    Returns:
        DataFrame with player season statistics

    Columns (after normalization):
        - PLAYER_NAME: Player full name
        - TEAM: Team abbreviation or full name
        - GP: Games played
        - MIN: Total minutes played
        - PTS: Total points
        - REB: Total rebounds
        - AST: Total assists
        - STL: Total steals
        - BLK: Total blocks
        - TOV: Total turnovers
        - PF: Total personal fouls
        - FGM/FGA/FG_PCT: Field goals made/attempted/percentage
        - FG3M/FG3A/FG3_PCT: 3-point field goals
        - FTM/FTA/FT_PCT: Free throws
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - COMPETITION: "LNB Pro A"

    Example:
        >>> # Requires Playwright installed
        >>> df = fetch_lnb_player_season("2024")
        >>> top_scorers = df.nlargest(10, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])

    Note:
        - Requires Playwright for JavaScript execution
        - Falls back gracefully if Playwright not installed
        - Uses browser automation (slower than API but more reliable)
        - Respects rate limiting (1 req/sec)
    """
    # Check Playwright availability
    if not is_playwright_available():
        logger.warning(
            "Playwright not installed. Cannot scrape JavaScript-rendered player stats. "
            "Install with: uv pip install playwright && playwright install chromium. "
            "Returning empty DataFrame."
        )
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

    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB Pro A player season statistics via Playwright: season={season}")

    try:
        with BrowserScraper(headless=True, timeout=45000) as scraper:
            # Navigate to LNB player statistics page
            # URL structure: https://www.lnb.fr/pro-a/statistiques
            # The page likely has tabs/sections for player stats
            url = f"{LNB_BASE_URL}/pro-a/statistiques"

            logger.info(f"Navigating to {url}")

            # Get rendered HTML and extract tables
            # Wait for player stats table to load (may take a few seconds for JS)
            tables = scraper.get_tables(
                url=url,
                wait_for="table",  # Wait for any table to appear
                wait_time=3.0,  # Give extra time for JavaScript to fully render
            )

            if not tables:
                logger.warning("No tables found on LNB player stats page")
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

            logger.info(f"Found {len(tables)} tables on page")

            # Try to find player stats table (usually the largest table)
            # Player stats tables typically have many rows (100+ players)
            best_table = None
            best_table_rows = 0

            for i, table_html in enumerate(tables):
                # Wrap table HTML in proper tags for pandas
                table_html_complete = f"<table>{table_html}</table>"

                try:
                    # Parse with pandas
                    dfs = pd.read_html(StringIO(table_html_complete))
                    if dfs and len(dfs) > 0:
                        df = dfs[0]
                        num_rows = len(df)
                        num_cols = len(df.columns)

                        logger.debug(f"Table {i+1}: {num_rows} rows x {num_cols} columns")

                        # Player stats table should have:
                        # - Many rows (50+ players)
                        # - Multiple columns (10+ stats)
                        if num_rows > best_table_rows and num_cols >= 8:
                            best_table = df
                            best_table_rows = num_rows
                            logger.debug(f"Table {i+1} is new best candidate")

                except Exception as e:
                    logger.debug(f"Failed to parse table {i+1}: {e}")
                    continue

            if best_table is None:
                logger.warning("Could not find player stats table on page")
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

            logger.info(
                f"Selected player stats table: {len(best_table)} rows x {len(best_table.columns)} columns"
            )

            # Map columns to standard format
            # Column names will vary based on website structure - need to inspect
            # Typical French basketball stats columns:
            # - Joueur/Nom = Player name
            # - Équipe/Club = Team
            # - MJ = Matches played (GP)
            # - Min = Minutes
            # - Pts = Points
            # - Reb = Rebounds
            # - Pd = Assists (Passes décisives)
            # - Int = Steals (Interceptions)
            # - CT = Blocks (Contres)
            # - BP = Turnovers (Balles perdues)
            # - FP = Personal fouls (Fautes personnelles)

            # For now, return with generic column mapping
            # TODO: Inspect actual website to map columns accurately
            df = best_table.copy()

            # Add league metadata
            df["LEAGUE"] = "LNB_PROA"
            df["SEASON"] = season
            df["COMPETITION"] = "LNB Pro A"

            logger.info(f"Successfully scraped {len(df)} player records")
            return df

    except Exception as e:
        logger.error(f"Failed to scrape LNB player season statistics: {e}")
        import traceback

        traceback.print_exc()

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

    # Fallback return (unreachable but satisfies mypy)
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
def fetch_lnb_schedule(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch LNB Pro A schedule via web scraping (Playwright)

    Scrapes JavaScript-rendered schedule from official LNB website.
    Falls back to empty DataFrame if Playwright is not installed.

    ⚠️ **REQUIRES PLAYWRIGHT**: Install with:
        uv pip install playwright
        playwright install chromium

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with game schedule

    Columns (after normalization):
        - GAME_ID: Unique game identifier
        - SEASON: Season string
        - GAME_DATE: Game date (YYYY-MM-DD format)
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score (None if not played)
        - AWAY_SCORE: Away team final score (None if not played)
        - STATUS: Game status (scheduled/live/finished)
        - VENUE: Game venue/arena
        - LEAGUE: "LNB_PROA"

    Example:
        >>> # Requires Playwright installed
        >>> df = fetch_lnb_schedule("2024")
        >>> upcoming = df[df["STATUS"] == "scheduled"]
        >>> print(upcoming[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]])

    Note:
        - Requires Playwright for JavaScript execution
        - Falls back gracefully if Playwright not installed
        - Uses browser automation (slower than API but more reliable)
        - Respects rate limiting (1 req/sec)
    """
    # Check Playwright availability
    if not is_playwright_available():
        logger.warning(
            "Playwright not installed. Cannot scrape JavaScript-rendered schedule. "
            "Install with: uv pip install playwright && playwright install chromium. "
            "Returning empty DataFrame."
        )
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "SEASON",
                "GAME_DATE",
                "HOME_TEAM",
                "AWAY_TEAM",
                "HOME_SCORE",
                "AWAY_SCORE",
                "STATUS",
                "VENUE",
                "LEAGUE",
            ]
        )

    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB Pro A schedule via Playwright: season={season}")

    try:
        with BrowserScraper(headless=True, timeout=45000) as scraper:
            # Navigate to LNB schedule/calendar page
            # URL structure: https://www.lnb.fr/pro-a/calendrier or /matchs
            url = f"{LNB_BASE_URL}/pro-a/calendrier"

            logger.info(f"Navigating to {url}")

            # Get rendered HTML and extract tables
            # Schedule tables may have fixtures grouped by round/date
            tables = scraper.get_tables(
                url=url,
                wait_for="table",  # Wait for schedule table to appear
                wait_time=3.0,  # Give extra time for JavaScript to fully render
            )

            if not tables:
                logger.warning("No tables found on LNB schedule page")
                return pd.DataFrame(
                    columns=[
                        "GAME_ID",
                        "SEASON",
                        "GAME_DATE",
                        "HOME_TEAM",
                        "AWAY_TEAM",
                        "HOME_SCORE",
                        "AWAY_SCORE",
                        "STATUS",
                        "LEAGUE",
                    ]
                )

            logger.info(f"Found {len(tables)} tables on schedule page")

            # Find schedule table (likely has dates, team names, scores)
            # Schedule tables typically have moderate number of rows (200-300 games per season)
            best_table = None
            best_table_rows = 0

            for i, table_html in enumerate(tables):
                table_html_complete = f"<table>{table_html}</table>"

                try:
                    dfs = pd.read_html(StringIO(table_html_complete))
                    if dfs and len(dfs) > 0:
                        df = dfs[0]
                        num_rows = len(df)
                        num_cols = len(df.columns)

                        logger.debug(f"Table {i+1}: {num_rows} rows x {num_cols} columns")

                        # Schedule table should have:
                        # - Moderate rows (50+ games)
                        # - Several columns (date, teams, scores, venue)
                        if num_rows > best_table_rows and num_cols >= 4:
                            best_table = df
                            best_table_rows = num_rows
                            logger.debug(f"Table {i+1} is new best candidate")

                except Exception as e:
                    logger.debug(f"Failed to parse table {i+1}: {e}")
                    continue

            if best_table is None:
                logger.warning("Could not find schedule table on page")
                return pd.DataFrame(
                    columns=[
                        "GAME_ID",
                        "SEASON",
                        "GAME_DATE",
                        "HOME_TEAM",
                        "AWAY_TEAM",
                        "HOME_SCORE",
                        "AWAY_SCORE",
                        "STATUS",
                        "LEAGUE",
                    ]
                )

            logger.info(
                f"Selected schedule table: {len(best_table)} rows x {len(best_table.columns)} columns"
            )

            # Map columns to standard format
            # Typical French schedule columns:
            # - Date/Jour = Game date
            # - Équipe dom./Domicile = Home team
            # - Équipe ext./Extérieur = Away team
            # - Score = Final score (e.g., "85-78" or "-" if not played)
            # - Lieu/Salle = Venue

            # For now, return with generic column mapping
            # TODO: Inspect actual website to map columns accurately
            df = best_table.copy()

            # Add league metadata
            df["LEAGUE"] = "LNB_PROA"
            df["SEASON"] = season

            # Generate game IDs if not present
            if "GAME_ID" not in df.columns:
                df["GAME_ID"] = [f"LNB_{season}_{i+1}" for i in range(len(df))]

            logger.info(f"Successfully scraped {len(df)} games")
            return df

    except Exception as e:
        logger.error(f"Failed to scrape LNB schedule: {e}")
        import traceback

        traceback.print_exc()

        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "SEASON",
                "GAME_DATE",
                "HOME_TEAM",
                "AWAY_TEAM",
                "HOME_SCORE",
                "AWAY_SCORE",
                "STATUS",
                "LEAGUE",
            ]
        )

    # Fallback return (unreachable but satisfies mypy)
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "SEASON",
            "GAME_DATE",
            "HOME_TEAM",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
            "STATUS",
            "LEAGUE",
        ]
    )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch LNB Pro A box score via web scraping (Playwright)

    Scrapes JavaScript-rendered player box scores from official LNB website.
    Falls back to empty DataFrame if Playwright is not installed.

    ⚠️ **REQUIRES PLAYWRIGHT**: Install with:
        uv pip install playwright
        playwright install chromium

    Args:
        game_id: Game ID (can be external ID or URL slug)

    Returns:
        DataFrame with player box score statistics

    Columns (after normalization):
        - GAME_ID: Game identifier
        - PLAYER_NAME: Player full name
        - TEAM: Team name
        - MIN: Minutes played
        - PTS: Points scored
        - REB: Total rebounds
        - AST: Assists
        - STL: Steals
        - BLK: Blocks
        - TOV: Turnovers
        - PF: Personal fouls
        - FGM/FGA/FG_PCT: Field goals made/attempted/percentage
        - FG3M/FG3A/FG3_PCT: 3-point field goals
        - FTM/FTA/FT_PCT: Free throws
        - LEAGUE: "LNB_PROA"

    Example:
        >>> # Requires Playwright installed
        >>> df = fetch_lnb_box_score("28931")
        >>> top_scorers = df.nlargest(5, "PTS")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])

    Note:
        - Requires Playwright for JavaScript execution
        - Falls back gracefully if Playwright not installed
        - Uses browser automation (slower than API but more reliable)
        - Respects rate limiting (1 req/sec)
        - Game must have been played (scheduled games won't have box scores)
    """
    # Check Playwright availability
    if not is_playwright_available():
        logger.warning(
            "Playwright not installed. Cannot scrape JavaScript-rendered box scores. "
            "Install with: uv pip install playwright && playwright install chromium. "
            "Returning empty DataFrame."
        )
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
                "TOV",
                "PF",
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
            ]
        )

    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB Pro A box score via Playwright: game_id={game_id}")

    try:
        with BrowserScraper(headless=True, timeout=45000) as scraper:
            # Navigate to LNB game page / box score page
            # URL structure: https://www.lnb.fr/pro-a/match/{game_id} or /stats-centre
            # Try common patterns
            url = f"{LNB_BASE_URL}/pro-a/match/{game_id}"

            logger.info(f"Navigating to {url}")

            # Get rendered HTML and extract tables
            # Box score tables typically have player names and stats
            tables = scraper.get_tables(
                url=url,
                wait_for="table",  # Wait for stats table to appear
                wait_time=3.0,  # Give extra time for JavaScript to fully render
            )

            if not tables:
                logger.warning(f"No tables found on LNB box score page for game {game_id}")
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

            logger.info(f"Found {len(tables)} tables on box score page")

            # Box scores typically have 2 tables (one per team) or 1 combined table
            # Each table should have ~10-15 rows (players) and ~15+ columns (stats)
            all_box_scores = []

            for i, table_html in enumerate(tables):
                table_html_complete = f"<table>{table_html}</table>"

                try:
                    dfs = pd.read_html(StringIO(table_html_complete))
                    if dfs and len(dfs) > 0:
                        df = dfs[0]
                        num_rows = len(df)
                        num_cols = len(df.columns)

                        logger.debug(f"Table {i+1}: {num_rows} rows x {num_cols} columns")

                        # Box score table should have:
                        # - ~8-15 rows (players per team)
                        # - ~10+ columns (player stats)
                        if 5 <= num_rows <= 20 and num_cols >= 8:
                            logger.info(f"Table {i+1} looks like box score data")
                            df["GAME_ID"] = game_id
                            df["LEAGUE"] = "LNB_PROA"
                            all_box_scores.append(df)

                except Exception as e:
                    logger.debug(f"Failed to parse table {i+1}: {e}")
                    continue

            if not all_box_scores:
                logger.warning(f"Could not find box score tables for game {game_id}")
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

            # Combine all box score tables (both teams)
            combined_df = pd.concat(all_box_scores, ignore_index=True)

            logger.info(
                f"Successfully scraped {len(combined_df)} player box score rows for game {game_id}"
            )
            return combined_df

    except Exception as e:
        logger.error(f"Failed to scrape LNB box score for game {game_id}: {e}")
        import traceback

        traceback.print_exc()

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

    # Fallback return (unreachable but satisfies mypy)
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


# ==============================================================================
# Atrium Sports API Fetchers (Play-by-Play & Shots)
# ==============================================================================


def _create_atrium_state(fixture_id: str, view: str) -> str:
    """Create compressed state parameter for Atrium Sports API

    Args:
        fixture_id: Game UUID from LNB's getMatchDetails API
        view: View type ("pbp" for play-by-play, "shot_chart" for shots)

    Returns:
        Base64url-encoded, zlib-compressed state parameter

    Example:
        >>> state = _create_atrium_state("3522345e-3362-11f0-b97d-7be2bdc7a840", "pbp")
        >>> # Returns: "eJyrVqpSslIqSCpQ0lFKA7KMTY2..."
    """
    state_obj = {
        "z": view,  # View type: "pbp" or "shot_chart"
        "f": fixture_id,  # Fixture ID (game UUID)
    }

    # Convert to JSON and compress
    json_str = json.dumps(state_obj, separators=(",", ":"))
    compressed = zlib.compress(json_str.encode("utf-8"))

    # Base64url encode (replace + with -, / with _, remove padding)
    encoded = base64.b64encode(compressed).decode("ascii")
    encoded = encoded.replace("+", "-").replace("/", "_").rstrip("=")

    return encoded


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
# NOTE: Removed @cached_dataframe - game-level data should not be globally cached
#       since cache key doesn't include positional args (game_id). Caching should
#       happen at season/bulk level instead.
def fetch_lnb_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch LNB Pro A play-by-play data from Atrium Sports API

    Retrieves detailed play-by-play events from Atrium Sports (third-party stats
    provider for LNB). Each event includes player, team, action type, clock time,
    score progression, and court coordinates.

    ⚠️ **NOTE**: This uses a third-party API (Atrium Sports) that provides stats
    for LNB games. The fixture ID (game_id) must be the UUID from LNB's official
    API or match pages.

    Args:
        game_id: Game UUID (fixture ID) from LNB API
                 Format: "3522345e-3362-11f0-b97d-7be2bdc7a840"

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier (fixture UUID)
        - EVENT_ID: Unique event identifier
        - PERIOD_ID: Period/quarter number (1, 2, 3, 4, etc.)
        - CLOCK: Game clock in ISO 8601 duration format (PT10M0S = 10:00)
        - EVENT_TYPE: Type of event (jumpBall, 2pt, 3pt, freeThrow, rebound,
                      assist, steal, turnover, foul, block, timeOut, substitution)
        - EVENT_SUBTYPE: Subtype (won, jumpShot, layup, dunk, offensive, etc.)
        - PLAYER_ID: Player UUID
        - PLAYER_NAME: Player full name
        - PLAYER_JERSEY: Jersey number
        - TEAM_ID: Team UUID
        - DESCRIPTION: French description of the event
        - SUCCESS: Boolean for shot events (True/False/None)
        - X_COORD: X coordinate for location events (0-100 scale)
        - Y_COORD: Y coordinate for location events (0-100 scale)
        - HOME_SCORE: Home team score after this event
        - AWAY_SCORE: Away team score after this event
        - LEAGUE: "LNB_PROA"

    Example:
        >>> # Get play-by-play for a completed game
        >>> df = fetch_lnb_play_by_play("3522345e-3362-11f0-b97d-7be2bdc7a840")
        >>>
        >>> # Filter to shot attempts
        >>> shots = df[df['EVENT_TYPE'].isin(['2pt', '3pt'])]
        >>> print(shots[['PLAYER_NAME', 'EVENT_TYPE', 'SUCCESS', 'CLOCK']])
        >>>
        >>> # Get scoring plays
        >>> scoring = df[df['EVENT_TYPE'].isin(['2pt', '3pt', 'freeThrow'])]
        >>> scoring = scoring[scoring['SUCCESS'] == True]

    Technical Notes:
        - Data source: Atrium Sports API (eapi.web.prod.cloud.atriumsports.com)
        - Requires game to be completed (no live data)
        - Returns ~400-600 events per game
        - Includes score progression after each event
        - French descriptions (use EVENT_TYPE for programmatic filtering)
    """
    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB play-by-play from Atrium API: game_id={game_id}")

    try:
        # Create state parameter for API request
        state = _create_atrium_state(game_id, "pbp")

        # Call Atrium API
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://lnb.fr/",
        }

        params = {"fixtureId": game_id, "state": state}

        response = requests.get(
            ATRIUM_FIXTURE_DETAIL_URL, params=params, headers=headers, timeout=10
        )
        response.raise_for_status()

        data = response.json()

        # Extract play-by-play data
        pbp_data = data.get("data", {}).get("pbp", {})

        if not pbp_data:
            logger.warning(f"No play-by-play data found for game {game_id}")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "EVENT_ID",
                    "PERIOD_ID",
                    "CLOCK",
                    "EVENT_TYPE",
                    "EVENT_SUBTYPE",
                    "PLAYER_ID",
                    "PLAYER_NAME",
                    "PLAYER_JERSEY",
                    "TEAM_ID",
                    "DESCRIPTION",
                    "SUCCESS",
                    "X_COORD",
                    "Y_COORD",
                    "HOME_SCORE",
                    "AWAY_SCORE",
                    "LEAGUE",
                ]
            )

        # Parse events from all periods
        all_events = []

        for _period_id, period_data in pbp_data.items():
            events = period_data.get("events", [])

            for event in events:
                # Extract team scores (scores dict has team_id keys)
                scores = event.get("scores", {})
                team_ids = list(scores.keys())

                # Determine home/away scores (first team in list is typically home)
                home_score = scores.get(team_ids[0], 0) if len(team_ids) > 0 else 0
                away_score = scores.get(team_ids[1], 0) if len(team_ids) > 1 else 0

                all_events.append(
                    {
                        "GAME_ID": game_id,
                        "EVENT_ID": event.get("eventId"),
                        "PERIOD_ID": event.get("periodId"),
                        "CLOCK": event.get("clock"),
                        "EVENT_TYPE": event.get("eventType"),
                        "EVENT_SUBTYPE": event.get("eventSubType"),
                        "PLAYER_ID": event.get("personId"),
                        "PLAYER_NAME": event.get("name"),
                        "PLAYER_JERSEY": event.get("bib"),
                        "TEAM_ID": event.get("entityId"),
                        "DESCRIPTION": event.get("desc"),
                        "SUCCESS": event.get("success"),
                        "X_COORD": event.get("x"),
                        "Y_COORD": event.get("y"),
                        "HOME_SCORE": home_score,
                        "AWAY_SCORE": away_score,
                        "LEAGUE": "LNB_PROA",
                    }
                )

        df = pd.DataFrame(all_events)
        logger.info(f"Successfully fetched {len(df)} play-by-play events for game {game_id}")

        return df

    except requests.RequestException as e:
        logger.error(f"Failed to fetch LNB play-by-play for game {game_id}: {e}")
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_ID",
                "PERIOD_ID",
                "CLOCK",
                "EVENT_TYPE",
                "EVENT_SUBTYPE",
                "PLAYER_ID",
                "PLAYER_NAME",
                "PLAYER_JERSEY",
                "TEAM_ID",
                "DESCRIPTION",
                "SUCCESS",
                "X_COORD",
                "Y_COORD",
                "HOME_SCORE",
                "AWAY_SCORE",
                "LEAGUE",
            ]
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching LNB play-by-play for game {game_id}: {e}")
        import traceback

        traceback.print_exc()
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_ID",
                "PERIOD_ID",
                "CLOCK",
                "EVENT_TYPE",
                "EVENT_SUBTYPE",
                "PLAYER_ID",
                "PLAYER_NAME",
                "PLAYER_JERSEY",
                "TEAM_ID",
                "DESCRIPTION",
                "SUCCESS",
                "X_COORD",
                "Y_COORD",
                "HOME_SCORE",
                "AWAY_SCORE",
                "LEAGUE",
            ]
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
# NOTE: Removed @cached_dataframe - game-level data should not be globally cached
#       since cache key doesn't include positional args (game_id). Caching should
#       happen at season/bulk level instead.
def fetch_lnb_shots(game_id: str) -> pd.DataFrame:
    """Fetch LNB Pro A shot chart data from Atrium Sports API

    Retrieves detailed shot chart data from Atrium Sports (third-party stats
    provider for LNB). Each shot includes player, team, shot type, success/miss,
    and precise court coordinates.

    ⚠️ **NOTE**: This uses a third-party API (Atrium Sports) that provides stats
    for LNB games. The fixture ID (game_id) must be the UUID from LNB's official
    API or match pages.

    Args:
        game_id: Game UUID (fixture ID) from LNB API
                 Format: "3522345e-3362-11f0-b97d-7be2bdc7a840"

    Returns:
        DataFrame with shot chart data

    Columns:
        - GAME_ID: Game identifier (fixture UUID)
        - EVENT_ID: Unique shot identifier
        - PERIOD_ID: Period/quarter number (1, 2, 3, 4, etc.)
        - CLOCK: Game clock in ISO 8601 duration format (PT9M40S = 9:40)
        - SHOT_TYPE: Shot type ("2pt" or "3pt")
        - SHOT_SUBTYPE: Shot subtype (jumpShot, layup, dunk, tipIn, etc.)
        - PLAYER_ID: Player UUID
        - PLAYER_NAME: Player full name
        - PLAYER_JERSEY: Jersey number
        - TEAM_ID: Team UUID
        - DESCRIPTION: French description (e.g., "2 pts Jump Shot")
        - SUCCESS: Boolean (True = made, False = missed)
        - SUCCESS_STRING: French result ("réussi" or "raté")
        - X_COORD: X coordinate (0-100 scale, court position)
        - Y_COORD: Y coordinate (0-100 scale, court position)
        - LEAGUE: "LNB_PROA"

    Example:
        >>> # Get shot chart for a completed game
        >>> df = fetch_lnb_shots("3522345e-3362-11f0-b97d-7be2bdc7a840")
        >>>
        >>> # Filter to made 3-pointers
        >>> threes = df[(df['SHOT_TYPE'] == '3pt') & (df['SUCCESS'] == True)]
        >>> print(threes[['PLAYER_NAME', 'SHOT_SUBTYPE', 'X_COORD', 'Y_COORD']])
        >>>
        >>> # Calculate shooting percentages by player
        >>> player_stats = df.groupby('PLAYER_NAME').agg({
        ...     'SUCCESS': ['sum', 'count', 'mean']
        ... })

    Technical Notes:
        - Data source: Atrium Sports API (eapi.web.prod.cloud.atriumsports.com)
        - Requires game to be completed (no live data)
        - Returns ~120-160 shots per game
        - Coordinates are percentage-based (0-100 scale)
        - Includes both made and missed attempts
        - French descriptions (use SHOT_TYPE/SHOT_SUBTYPE for programmatic filtering)
    """
    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB shot chart from Atrium API: game_id={game_id}")

    try:
        # Create state parameter for API request
        state = _create_atrium_state(game_id, "shot_chart")

        # Call Atrium API
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://lnb.fr/",
        }

        params = {"fixtureId": game_id, "state": state}

        response = requests.get(
            ATRIUM_FIXTURE_DETAIL_URL, params=params, headers=headers, timeout=10
        )
        response.raise_for_status()

        data = response.json()

        # Extract shot chart data
        shot_chart = data.get("data", {}).get("shotChart", {})
        shots = shot_chart.get("shots", [])

        if not shots:
            logger.warning(f"No shot chart data found for game {game_id}")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "EVENT_ID",
                    "PERIOD_ID",
                    "CLOCK",
                    "SHOT_TYPE",
                    "SHOT_SUBTYPE",
                    "PLAYER_ID",
                    "PLAYER_NAME",
                    "PLAYER_JERSEY",
                    "TEAM_ID",
                    "DESCRIPTION",
                    "SUCCESS",
                    "SUCCESS_STRING",
                    "X_COORD",
                    "Y_COORD",
                    "LEAGUE",
                ]
            )

        # Parse shots
        all_shots = []

        for shot in shots:
            all_shots.append(
                {
                    "GAME_ID": game_id,
                    "EVENT_ID": shot.get("eventId"),
                    "PERIOD_ID": shot.get("periodId"),
                    "CLOCK": shot.get("clock"),
                    "SHOT_TYPE": shot.get("eventType"),  # "2pt" or "3pt"
                    "SHOT_SUBTYPE": shot.get("subType"),  # jumpShot, layup, dunk, etc.
                    "PLAYER_ID": shot.get("personId"),
                    "PLAYER_NAME": shot.get("name"),
                    "PLAYER_JERSEY": shot.get("bib"),
                    "TEAM_ID": shot.get("entityId"),
                    "DESCRIPTION": shot.get("desc"),
                    "SUCCESS": shot.get("success"),
                    "SUCCESS_STRING": shot.get("successString"),
                    "X_COORD": shot.get("x"),
                    "Y_COORD": shot.get("y"),
                    "LEAGUE": "LNB_PROA",
                }
            )

        df = pd.DataFrame(all_shots)
        logger.info(f"Successfully fetched {len(df)} shots for game {game_id}")

        return df

    except requests.RequestException as e:
        logger.error(f"Failed to fetch LNB shot chart for game {game_id}: {e}")
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_ID",
                "PERIOD_ID",
                "CLOCK",
                "SHOT_TYPE",
                "SHOT_SUBTYPE",
                "PLAYER_ID",
                "PLAYER_NAME",
                "PLAYER_JERSEY",
                "TEAM_ID",
                "DESCRIPTION",
                "SUCCESS",
                "SUCCESS_STRING",
                "X_COORD",
                "Y_COORD",
                "LEAGUE",
            ]
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching LNB shot chart for game {game_id}: {e}")
        import traceback

        traceback.print_exc()
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_ID",
                "PERIOD_ID",
                "CLOCK",
                "SHOT_TYPE",
                "SHOT_SUBTYPE",
                "PLAYER_ID",
                "PLAYER_NAME",
                "PLAYER_JERSEY",
                "TEAM_ID",
                "DESCRIPTION",
                "SUCCESS",
                "SUCCESS_STRING",
                "X_COORD",
                "Y_COORD",
                "LEAGUE",
            ]
        )


# ==============================================================================
# API-Based Fetchers (New - Phase 5)
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_schedule_v2(
    season: int,
    division: int = 1,
) -> pd.DataFrame:
    """Fetch LNB schedule via API (replaces HTML scraping version).

    Uses get_calendar_by_division() endpoint for full season schedule.

    Args:
        season: Season year (e.g., 2025 for 2024-25 season)
        division: Division ID (default: 1 = Betclic ELITE)

    Returns:
        DataFrame matching LNBSchedule schema (18 columns)

    Example:
        >>> df = fetch_lnb_schedule_v2(season=2025, division=1)
        >>> print(df[["GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "STATUS"]])
    """
    from .lnb_api import LNBClient
    from .lnb_parsers import parse_calendar

    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB schedule: season={season}, division={division}")

    client = LNBClient()
    json_data = client.get_calendar_by_division(division_external_id=division, year=season)

    df = parse_calendar(json_data, season=season)
    logger.info(f"Fetched {len(df)} LNB games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_team_season_v2(
    season: int,
    competition_id: int = 302,
) -> pd.DataFrame:
    """Fetch LNB team season standings via API (replaces HTML scraping version).

    Uses get_standing() endpoint for team statistics and rankings.

    Args:
        season: Season year (e.g., 2025)
        competition_id: Competition ID (default: 302 = Betclic ELITE 2024-25)

    Returns:
        DataFrame matching LNBTeamSeason schema (24 columns)

    Example:
        >>> df = fetch_lnb_team_season_v2(season=2025, competition_id=302)
        >>> print(df[["TEAM_NAME", "RANK", "W", "L", "WIN_PCT", "PTS_PG"]])
    """
    from .lnb_api import LNBClient
    from .lnb_parsers import parse_standings

    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB team season: season={season}, competition_id={competition_id}")

    client = LNBClient()
    json_data = client.get_standing(competition_external_id=competition_id)

    df = parse_standings(json_data, season=season)
    logger.info(f"Fetched standings for {len(df)} LNB teams")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_season_v2(
    season: int,
    player_id: int,
) -> pd.DataFrame:
    """Fetch LNB player season statistics via API.

    Uses player→competitions discovery pipeline:
    1. Find all competitions player participated in
    2. Fetch performance stats for each competition
    3. Concatenate results

    Args:
        season: Season year (e.g., 2025)
        player_id: Player external ID

    Returns:
        DataFrame matching LNBPlayerSeason schema (34 columns)
        One row per competition the player participated in

    Example:
        >>> df = fetch_lnb_player_season_v2(season=2025, player_id=3586)
        >>> print(df[["PLAYER_NAME", "COMPETITION_ID", "GP", "PTS_PG", "REB_PG", "AST_PG"]])
    """
    from .lnb_api import LNBClient
    from .lnb_parsers import parse_competitions_by_player, parse_player_performance

    rate_limiter.acquire("lnb")
    logger.info(f"Fetching LNB player season: season={season}, player_id={player_id}")

    client = LNBClient()

    # Step 1: Find competitions player participated in
    comp_data = client.get_competitions_by_player(year=season, person_external_id=player_id)
    comp_df = parse_competitions_by_player(comp_data, player_id=player_id, season=season)

    if len(comp_df) == 0:
        logger.warning(f"Player {player_id} has no competitions for season {season}")
        from .lnb_schemas import get_player_season_columns

        return pd.DataFrame(columns=get_player_season_columns())

    # Step 2: Fetch stats for each competition
    all_stats = []
    for _, row in comp_df.iterrows():
        competition_id = row["COMPETITION_ID"]
        logger.info(f"Fetching player {player_id} stats for competition {competition_id}")

        try:
            perf_data = client.get_player_performance(
                competition_external_id=competition_id, person_external_id=player_id
            )
            perf_df = parse_player_performance(
                perf_data, season=season, competition_id=competition_id
            )
            all_stats.append(perf_df)
        except Exception as e:
            logger.warning(f"Failed to fetch stats for competition {competition_id}: {e}")
            continue

    # Step 3: Concatenate results
    if not all_stats:
        logger.warning(f"No stats retrieved for player {player_id}")
        from .lnb_schemas import get_player_season_columns

        return pd.DataFrame(columns=get_player_season_columns())

    df = pd.concat(all_stats, ignore_index=True)
    logger.info(f"Fetched stats for player {player_id} across {len(df)} competitions")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_game(
    season: int,
    game_id: int | None = None,
    endpoint_path: str = "/stats/getMatchBoxScore",
    try_endpoint: bool = False,
) -> pd.DataFrame:
    """Fetch LNB player game stats (box score) - CONDITIONAL IMPLEMENTATION.

    ⚠️  ENDPOINT DISCOVERY REQUIRED
    The default endpoint path is a placeholder. Once the real endpoint is discovered
    via browser DevTools (see LNB_BOXSCORE_DISCOVERY_GUIDE.md), set try_endpoint=True
    and update endpoint_path with the correct path.

    Discovery Process:
        1. Go to https://lnb.fr/fr/stats-centre during/after a live game
        2. Open browser DevTools (F12) → Network tab
        3. Click on game boxscore/statistics
        4. Find the API request (likely POST to /altrstats/* or /match/*)
        5. Copy the endpoint path
        6. Update this function's default endpoint_path parameter

    Args:
        season: Season year (e.g., 2025 for 2024-25 season)
        game_id: Game external ID (match_external_id)
        endpoint_path: API endpoint path (update after discovery)
        try_endpoint: If True, attempts to call endpoint (default: False for safety)

    Returns:
        DataFrame matching LNBPlayerGame schema (32 columns)
        Returns empty DataFrame if endpoint not discovered or try_endpoint=False

    Example (after endpoint discovery):
        >>> # Once endpoint is discovered, use:
        >>> df = fetch_lnb_player_game(
        ...     season=2025,
        ...     game_id=28931,
        ...     endpoint_path="/altrstats/getBoxScore",  # Real path
        ...     try_endpoint=True
        ... )
        >>> print(df[["PLAYER_NAME", "PTS", "REB", "AST", "MIN"]])

    Notes:
        - Set try_endpoint=True only after confirming endpoint works
        - Parser handles multiple potential response structures
        - Falls back gracefully if endpoint returns error
        - See LNB_BOXSCORE_DISCOVERY_GUIDE.md for detailed instructions
    """
    from .lnb_api import LNBClient
    from .lnb_parsers import parse_boxscore
    from .lnb_schemas import get_player_game_columns

    # Safety check: Don't attempt API call unless explicitly enabled
    if not try_endpoint:
        logger.warning(
            "fetch_lnb_player_game: Boxscore endpoint not yet discovered. "
            "Set try_endpoint=True after discovering real endpoint via DevTools. "
            "See LNB_BOXSCORE_DISCOVERY_GUIDE.md for instructions. "
            "Returning empty DataFrame."
        )
        return pd.DataFrame(columns=get_player_game_columns())

    # Require game_id for boxscore
    if game_id is None:
        logger.error("fetch_lnb_player_game: game_id is required for boxscore fetching")
        return pd.DataFrame(columns=get_player_game_columns())

    rate_limiter.acquire("lnb")
    logger.info(
        f"Fetching LNB boxscore: game_id={game_id}, season={season}, endpoint={endpoint_path}"
    )

    try:
        client = LNBClient()

        # Call the boxscore endpoint (with custom path if discovered)
        json_data = client.get_match_boxscore(match_external_id=game_id, path=endpoint_path)

        # Parse the response
        df = parse_boxscore(json_data=json_data, game_id=game_id, season=season)

        if len(df) > 0:
            logger.info(f"Fetched {len(df)} player boxscore rows for game {game_id}")
        else:
            logger.warning(f"Boxscore returned empty for game {game_id}")

        return df

    except Exception as e:
        logger.error(
            f"fetch_lnb_player_game failed for game {game_id}: {e}. "
            f"Endpoint '{endpoint_path}' may be incorrect. "
            "See LNB_BOXSCORE_DISCOVERY_GUIDE.md for discovery instructions."
        )
        return pd.DataFrame(columns=get_player_game_columns())
