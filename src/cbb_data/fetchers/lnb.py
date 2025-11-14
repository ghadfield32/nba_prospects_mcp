"""LNB Pro A (France) Fetcher

Official LNB Pro A (French professional basketball) data via web scraping.

LNB Pro A is France's top-tier professional basketball league, featuring 16-18 teams.
Known for developing NBA talent including Victor Wembanyama, Rudy Gobert, Tony Parker,
Nicolas Batum, and others.

⚠️ **DATA AVAILABILITY**:
- **Team standings**: ✅ Available (static HTML table)
- **Player statistics**: ❌ Requires API discovery (see tools/lnb/README.md)
- **Game-level data**: ❌ Requires API discovery (see tools/lnb/README.md)

**TO IMPLEMENT MISSING DATA**:
The LNB website uses a JavaScript-driven Stats Centre. To access player/game data:
1. Follow the API discovery guide at: `tools/lnb/README.md`
2. Use browser DevTools to reverse-engineer API endpoints
3. Implement discovered endpoints in: `src/cbb_data/fetchers/lnb_api.py`
4. Update placeholder functions below to use the API client

Key Features:
- Web scraping from official lnb.fr stats pages
- Team season standings (rankings, W-L, points, etc.)
- Rate-limited requests with retry logic
- UTF-8 support for French names (accents, special characters)

Data Granularities:
- schedule: ❌ Requires API discovery (tools/lnb/README.md)
- player_game: ❌ Requires API discovery (tools/lnb/README.md)
- team_game: ❌ Requires API discovery (tools/lnb/README.md)
- pbp: ❌ Requires API discovery (tools/lnb/README.md)
- shots: ❌ Requires API discovery (tools/lnb/README.md)
- player_season: ❌ Requires API discovery (tools/lnb/README.md)
- team_season: ✅ Available (via standings page)

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
✅ IMPLEMENTED - Team standings via static HTML (team_season only)
❌ Player/game data requires API discovery - see tools/lnb/README.md for instructions
📋 TEMPLATE - API client template created at src/cbb_data/fetchers/lnb_api.py

Technical Notes:
- Encoding: UTF-8 for French names (é, à, ç, etc.)
- Season format: Calendar year (e.g., "2024" for 2024-25 season)
- Rate limiting: 1 req/sec to respect website resources
- Unlabeled columns: Table has "Unnamed: 0", "Unnamed: 1", etc. → manual mapping required
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

# LNB Pro A URLs
LNB_BASE_URL = "https://www.lnb.fr"
LNB_STANDINGS_URL = f"{LNB_BASE_URL}/pro-a/statistiques"


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
    """Fetch LNB Pro A player season statistics via HTML scraping

    **HTML-FIRST APPROACH**: Scrapes lnb.fr/pro-a/statistiques to extract
    player season stats from HTML tables. Falls back to empty DataFrame if
    scraping fails or table requires JavaScript rendering.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)
        per_mode: Aggregation mode ("Totals", "PerGame", "Per40")
                 Note: Currently only "Totals" supported from HTML

    Returns:
        DataFrame with player season statistics

    Columns:
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - COMPETITION: "LNB Pro A"
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - GP: Games played
        - GS: Games started (if available)
        - MIN: Total minutes
        - MIN_PG: Minutes per game
        - PTS: Total points
        - PTS_PG: Points per game
        - FGM, FGA, FG_PCT: Field goals
        - FG2M, FG2A, FG2_PCT: 2-point field goals
        - FG3M, FG3A, FG3_PCT: 3-point field goals
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB, REB_PG: Rebounds
        - AST, AST_PG: Assists
        - STL, STL_PG: Steals
        - BLK, BLK_PG: Blocks
        - TOV, TOV_PG: Turnovers
        - PF: Personal fouls
        - EFF: Efficiency rating
        - PLUS_MINUS: Plus/minus (if available)
        - SOURCE: "lnb_html_playerstats"

    Example:
        >>> player_season = fetch_lnb_player_season("2024")
        >>> top_scorers = player_season.nlargest(10, "PTS_PG")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS_PG"]])

    Note:
        - Scrapes from lnb.fr/pro-a/statistiques
        - Table may require JavaScript - if empty, check browser
        - French column names mapped to English
        - Per-game stats calculated from totals
    """
    logger.info(f"Fetching LNB Pro A player season stats: {season}")

    try:
        # Import HTML scraper
        from .html_scrapers import scrape_lnb_player_season_html

        # Scrape player season stats from LNB website
        df = scrape_lnb_player_season_html(season)

        if df.empty:
            logger.warning(
                f"No player stats found for LNB Pro A {season}. "
                "This may indicate:\n"
                "1. Season not yet started or stats not published\n"
                "2. Website structure changed (update scraper)\n"
                "3. JavaScript rendering required (consider Selenium)\n"
                "4. Website blocking automated requests (403 error)"
            )
            return df

        # Handle per_mode parameter
        if per_mode == "PerGame":
            # Use _PG columns if available
            pg_cols = [c for c in df.columns if c.endswith("_PG")]
            if pg_cols:
                logger.info(f"Using per-game stats ({len(pg_cols)} columns)")
        elif per_mode == "Per40":
            logger.warning("Per40 mode not yet implemented for LNB, using Totals")

        logger.info(f"Fetched {len(df)} LNB Pro A player season stats")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch LNB Pro A player season stats: {e}")
        return pd.DataFrame(
            columns=[
                "LEAGUE",
                "SEASON",
                "COMPETITION",
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
            ]
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_schedule(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch LNB Pro A schedule via HTML scraping (OPTIONAL)

    **OPTIONAL HTML SCRAPER**: Attempts to scrape schedule from lnb.fr HTML.
    May return empty DataFrame if page requires JavaScript rendering.

    **Alternatives if HTML fails**:
    1. Use Selenium/Playwright for JavaScript rendering
    2. Reverse-engineer internal APIs (see tools/lnb/README.md)
    3. Manual CSV creation from website

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with schedule or empty DataFrame if scraping fails

    Columns (if successful):
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - COMPETITION: "LNB Pro A"
        - GAME_ID: Game identifier
        - GAME_DATE: Game date
        - GAME_TIME: Game time
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home score (if completed)
        - AWAY_SCORE: Away score (if completed)
        - ROUND: Round/journée number
        - VENUE: Venue name (if available)
        - GAME_URL: Link to game page
        - PHASE: "Regular Season" or "Playoffs"
        - SOURCE: "lnb_html_schedule"

    Example:
        >>> schedule = fetch_lnb_schedule("2024")
        >>> if not schedule.empty:
        ...     print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())
        ... else:
        ...     print("Schedule scraping failed - may need JavaScript rendering")

    Note:
        - Scrapes from lnb.fr/pro-a/calendrier-resultats
        - Returns empty DataFrame if JavaScript required
        - French date/time formats parsed (12h30 → 12:30)
    """
    logger.info(f"Fetching LNB Pro A schedule: {season}")

    try:
        # Import HTML scraper
        from .html_scrapers import scrape_lnb_schedule_page

        # Attempt HTML scraping
        df = scrape_lnb_schedule_page(season)

        if df.empty:
            logger.warning(
                f"No schedule found for LNB Pro A {season}. "
                "This may indicate:\n"
                "1. JavaScript rendering required (HTML scraping insufficient)\n"
                "2. Season not yet started or schedule not published\n"
                "3. Website structure changed (update scraper)\n"
                "4. Consider alternative methods:\n"
                "   - Selenium/Playwright for JavaScript\n"
                "   - API discovery (tools/lnb/README.md)\n"
                "   - Manual CSV creation"
            )

        logger.info(f"Fetched {len(df)} LNB Pro A games")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch LNB Pro A schedule: {e}")
        logger.warning(
            "LNB Pro A schedule scraping failed. Consider:\n"
            "1. Using Selenium/Playwright for JavaScript rendering\n"
            "2. API discovery (see tools/lnb/README.md)\n"
            "3. Manual CSV creation from website"
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
            "LEAGUE",
        ]
    )


def fetch_lnb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch LNB Pro A box score (REQUIRES API DISCOVERY)

    ❌ Box scores require API discovery via browser DevTools.

    **TO IMPLEMENT**: See tools/lnb/README.md for API discovery instructions.

    Args:
        game_id: Game identifier

    Returns:
        Empty DataFrame (until API is discovered and implemented)

    Expected Columns (after implementation):
        - GAME_ID, PLAYER_NAME, TEAM, MIN, PTS, REB, AST, STL, BLK
        - FGM, FGA, FG3M, FG3A, FTM, FTA, LEAGUE
    """
    logger.warning(
        "LNB Pro A box scores require API discovery. "
        "See tools/lnb/README.md for implementation instructions. "
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
            "LEAGUE",
        ]
    )
