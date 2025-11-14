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
    """Fetch LNB Pro A schedule via Stats Center JSON API (REQUIRES DEVTOOLS DISCOVERY)

    ❌ **NOT YET IMPLEMENTED** - Awaiting Stats Center API discovery.

    **IMPLEMENTATION REQUIRED**: The LNB Stats Center is a JavaScript SPA that loads
    schedule data via JSON APIs. You must discover the endpoint using DevTools.

    **Discovery Steps**:
    1. Open https://lnb.fr/fr/stats-centre in your browser
    2. Open DevTools (F12) → Network tab → Filter: "XHR" or "Fetch"
    3. Navigate to the schedule/calendar view for Betclic ELITE
    4. Identify the API request that returns schedule data
    5. Note the endpoint URL and query parameters
    6. Save a sample response to tools/lnb/sample_responses/schedule_sample.json

    **To Implement** (after discovery):
    ```python
    import requests
    from .html_scrapers import (
        LNB_SCHEDULE_API_URL_TEMPLATE,
        _ensure_lnb_schedule_api_configured,
        scrape_lnb_schedule_json,
    )

    # 1. Validate API URL is configured
    _ensure_lnb_schedule_api_configured()

    # 2. Build URL with season parameter
    url = LNB_SCHEDULE_API_URL_TEMPLATE.format(season=season)

    # 3. Fetch JSON from API
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    json_data = response.json()

    # 4. Parse JSON using scrape_lnb_schedule_json
    # (after implementing the JSON parsing logic in html_scrapers.py)
    df = scrape_lnb_schedule_json(json_data, season)

    return df
    ```

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        Empty DataFrame (until API discovery complete)

    Expected Columns (after implementation):
        - LEAGUE: "LNB"
        - SEASON: Season string
        - COMPETITION: "Betclic ELITE"
        - GAME_ID: Unique game identifier
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home score (None if not yet played)
        - AWAY_SCORE: Away score (None if not yet played)
        - ROUND: Round/journée number (optional)
        - GAME_URL: Link to game detail page (optional)

    Raises:
        NotImplementedError: Always (until Stats Center API discovered)

    See Also:
        - docs/lnb_game_level_investigation.md: Complete investigation workflow
        - html_scrapers.py: LNB_SCHEDULE_API_URL_TEMPLATE constant
        - html_scrapers.py: scrape_lnb_schedule_json() skeleton function
        - tools/lnb/api_discovery_helper.py: Endpoint testing tool

    Note:
        - The old HTML scraper (scrape_lnb_schedule_page) is still available
          but likely returns empty due to JavaScript rendering
        - Stats Center API is the preferred approach for reliable data
    """
    logger.info(f"Fetching LNB Pro A schedule: {season}")

    raise NotImplementedError(
        "fetch_lnb_schedule: Stats Center API not yet discovered.\n"
        "Steps to implement:\n"
        "1. Use DevTools on https://lnb.fr/fr/stats-centre to find schedule API\n"
        "2. Set LNB_SCHEDULE_API_URL_TEMPLATE in html_scrapers.py\n"
        "3. Implement JSON parsing in scrape_lnb_schedule_json()\n"
        "4. Replace this NotImplementedError with API fetch code\n"
        "See: docs/lnb_game_level_investigation.md for detailed instructions"
    )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_game(
    season: str = "2024",
) -> pd.DataFrame:
    """Fetch LNB Pro A player game stats (REQUIRES DEVTOOLS DISCOVERY)

    ❌ **NOT YET IMPLEMENTED** - Awaiting Stats Center API discovery.

    **IMPLEMENTATION REQUIRED**: Fetch player boxscores for all games in a season
    by combining schedule API + boxscore API calls.

    **Discovery Steps**:
    1. Complete schedule API discovery first (see fetch_lnb_schedule)
    2. Open https://lnb.fr/fr/stats-centre and navigate to a specific game
    3. Open DevTools → Network → XHR/Fetch
    4. Identify the API request that returns player boxscore/stats
    5. Note the endpoint URL pattern (likely includes game_id)
    6. Save sample response to tools/lnb/sample_responses/boxscore_sample.json

    **To Implement** (after discovery):
    ```python
    import requests
    from .html_scrapers import (
        LNB_BOXSCORE_API_URL_TEMPLATE,
        _ensure_lnb_boxscore_api_configured,
        scrape_lnb_boxscore_json,
    )

    # 1. Get schedule to find all game IDs
    schedule_df = fetch_lnb_schedule(season)
    if schedule_df.empty:
        logger.warning("No schedule data, cannot fetch player_game")
        return pd.DataFrame()

    # 2. Validate boxscore API is configured
    _ensure_lnb_boxscore_api_configured()

    # 3. Loop through games and fetch boxscores
    all_player_games = []

    for _, row in schedule_df.iterrows():
        game_id = row["GAME_ID"]

        # Build boxscore URL
        url = LNB_BOXSCORE_API_URL_TEMPLATE.format(game_id=game_id)

        # Fetch JSON
        rate_limiter.acquire("lnb")  # Rate limiting
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        json_data = response.json()

        # Parse boxscore
        player_game_df, team_game_df = scrape_lnb_boxscore_json(
            json_data, "LNB", season, game_id
        )

        if not player_game_df.empty:
            all_player_games.append(player_game_df)

    # 4. Concatenate all games
    if all_player_games:
        return pd.concat(all_player_games, ignore_index=True)
    else:
        return pd.DataFrame()
    ```

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        Empty DataFrame (until API discovery complete)

    Expected Columns (after implementation):
        - LEAGUE: "LNB"
        - SEASON: Season string
        - GAME_ID: Game identifier
        - TEAM: Team name
        - TEAM_ID: Team identifier (if available)
        - PLAYER_NAME: Player name
        - PLAYER_ID: Player identifier (if available)
        - MIN: Minutes played
        - PTS: Points
        - FGM, FGA, FG_PCT: Field goals
        - FG2M, FG2A, FG2_PCT: 2-point field goals
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

    Raises:
        NotImplementedError: Always (until Stats Center API discovered)

    See Also:
        - docs/lnb_game_level_investigation.md: Investigation workflow
        - html_scrapers.py: LNB_BOXSCORE_API_URL_TEMPLATE constant
        - html_scrapers.py: scrape_lnb_boxscore_json() skeleton function
        - fetch_lnb_schedule(): Must be implemented first
        - fetch_lnb_team_game(): Aggregated version

    Note:
        - Requires one API call per game (schedule.count() requests total)
        - Use rate limiting (rate_limiter.acquire) between requests
        - boxscore API should return both player and team stats
    """
    logger.info(f"Fetching LNB Pro A player_game: {season}")

    raise NotImplementedError(
        "fetch_lnb_player_game: Stats Center API not yet discovered.\n"
        "Steps to implement:\n"
        "1. Complete fetch_lnb_schedule implementation first\n"
        "2. Use DevTools to find boxscore API endpoint for a single game\n"
        "3. Set LNB_BOXSCORE_API_URL_TEMPLATE in html_scrapers.py\n"
        "4. Implement JSON parsing in scrape_lnb_boxscore_json()\n"
        "5. Replace this NotImplementedError with loop-over-schedule code\n"
        "See: docs/lnb_game_level_investigation.md for detailed instructions"
    )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_team_game(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A team game stats (REQUIRES DEVTOOLS DISCOVERY)

    ❌ **NOT YET IMPLEMENTED** - Awaiting Stats Center API discovery.

    **IMPLEMENTATION NOTE**: Team-level stats are extracted from the same boxscore
    API as player stats. Once `fetch_lnb_player_game()` is implemented, this function
    can aggregate from player_game data or extract team_game_df directly.

    **Implementation Option A: Aggregate from player_game** (simpler):
    ```python
    # Get player game data
    player_game_df = fetch_lnb_player_game(season)

    if player_game_df.empty:
        return pd.DataFrame()

    # Aggregate by GAME_ID + TEAM
    numeric_cols = player_game_df.select_dtypes(include='number').columns.tolist()
    team_game_df = player_game_df.groupby(
        ["LEAGUE", "SEASON", "GAME_ID", "TEAM"],
        as_index=False
    )[numeric_cols].sum()

    return team_game_df
    ```

    **Implementation Option B: Extract from boxscore loop** (more direct):
    ```python
    # Same loop as fetch_lnb_player_game, but collect team_game_df instead
    import requests
    from .html_scrapers import scrape_lnb_boxscore_json

    schedule_df = fetch_lnb_schedule(season)
    all_team_games = []

    for _, row in schedule_df.iterrows():
        game_id = row["GAME_ID"]
        url = LNB_BOXSCORE_API_URL_TEMPLATE.format(game_id=game_id)

        rate_limiter.acquire("lnb")
        response = requests.get(url, timeout=30)
        json_data = response.json()

        player_game_df, team_game_df = scrape_lnb_boxscore_json(
            json_data, "LNB", season, game_id
        )

        if not team_game_df.empty:
            all_team_games.append(team_game_df)

    return pd.concat(all_team_games, ignore_index=True) if all_team_games else pd.DataFrame()
    ```

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        Empty DataFrame (until API discovery complete)

    Expected Columns (after implementation):
        - LEAGUE: "LNB"
        - SEASON: Season string
        - GAME_ID: Game identifier
        - TEAM: Team name
        - TEAM_ID: Team identifier (if available)
        - MIN: Total minutes (should be 200 for full game)
        - PTS: Points
        - FGM, FGA, FG_PCT: Field goals
        - FG2M, FG2A, FG2_PCT: 2-point field goals
        - FG3M, FG3A, FG3_PCT: 3-point field goals
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB: Rebounds
        - AST, STL, BLK, TOV, PF: Other stats
        - PLUS_MINUS: Point differential (if available)

    Raises:
        NotImplementedError: Always (until Stats Center API discovered)

    See Also:
        - fetch_lnb_player_game(): Player-level implementation (must be done first)
        - html_scrapers.py: scrape_lnb_boxscore_json() returns both player_game and team_game
        - docs/lnb_game_level_investigation.md: Investigation workflow

    Note:
        - scrape_lnb_boxscore_json() returns BOTH player_game and team_game DataFrames
        - team_game is automatically aggregated from player stats
        - Choose Option A (aggregate) for simplicity or Option B (direct) for efficiency
    """
    logger.info(f"Fetching LNB Pro A team_game: {season}")

    raise NotImplementedError(
        "fetch_lnb_team_game: Stats Center API not yet discovered.\n"
        "Steps to implement:\n"
        "1. Complete fetch_lnb_player_game implementation first\n"
        "2. Choose implementation option:\n"
        "   Option A: Aggregate from fetch_lnb_player_game() [simpler]\n"
        "   Option B: Extract team_game_df from boxscore loop [more efficient]\n"
        "3. Replace this NotImplementedError with chosen implementation\n"
        "See: docs/lnb_game_level_investigation.md for detailed instructions"
    )


def fetch_lnb_pbp(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A play-by-play data (CONDITIONAL - Scenario 2 only)

    ❌ **NOT YET IMPLEMENTED** - Only available if FIBA LiveStats route viable.

    **AVAILABILITY DEPENDS ON INVESTIGATION**:

    - **Scenario 1** (Stats Centre API): PBP NOT available
      - Stats centres typically don't expose play-by-play
      - Would need separate FIBA LiveStats access

    - **Scenario 2** (FIBA LiveStats): PBP AVAILABLE ✅
      - Same infrastructure as BCL/BAL/ABA/LKL
      - Full play-by-play with running score, substitutions
      - Shot clock, game clock timestamps
      - Action types: made/missed shots, fouls, timeouts, etc.

    **TO INVESTIGATE**:
    1. Check if LNB games listed on fiba.basketball
    2. Search for FFBB (French federation) competition codes
    3. Test FIBA LiveStats URLs:
       - https://fibalivestats.dcd.shared.geniussports.com/u/FFBB/{GAME_ID}/pbp.html
    4. If accessible → Scenario 2 confirmed, PBP available
    5. If 404/blocked → Scenario 1 likely, PBP not available

    **TO IMPLEMENT** (if Scenario 2):
    ```python
    from .fiba_html_common import fetch_fiba_pbp

    df = fetch_fiba_pbp(
        game_id=game_id,
        comp_code="FFBB_PROA"  # Or discovered code
    )
    df["LEAGUE"] = "LNB_PROA"
    df["SEASON"] = season
    return df
    ```

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        Empty DataFrame (until investigation determines availability)

    Expected Columns (if Scenario 2 viable):
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - GAME_ID: Game identifier
        - PERIOD: Quarter (1-4) or OT period
        - GAME_CLOCK: Time remaining in period (MM:SS)
        - SHOT_CLOCK: Shot clock (if available)
        - TEAM_ID: Team performing action
        - PLAYER_ID: Player performing action (if applicable)
        - ACTION_TYPE: "made_shot", "missed_shot", "rebound", etc.
        - SCORE_HOME: Home team running score
        - SCORE_AWAY: Away team running score
        - DESCRIPTION: Text description of play
        - SOURCE: "fiba_livestats_json" or "fiba_livestats_html"

    Raises:
        NotImplementedError: Always (until investigation complete)

    See Also:
        - docs/lnb_game_level_investigation.md: Investigation workflow
        - src/cbb_data/fetchers/fiba_html_common.py: FIBA PBP implementation
        - src/cbb_data/fetchers/bcl.py: Example FIBA PBP usage
    """
    raise NotImplementedError(
        "LNB PBP availability depends on investigation results. "
        "Only available if FIBA LiveStats route (Scenario 2) is viable. "
        "See docs/lnb_game_level_investigation.md Phase 1B for testing steps."
    )


def fetch_lnb_shots(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A shot chart data (CONDITIONAL - Scenario 2 only)

    ❌ **NOT YET IMPLEMENTED** - Only available if FIBA LiveStats route viable.

    **AVAILABILITY DEPENDS ON INVESTIGATION**:

    - **Scenario 1** (Stats Centre API): Shots NOT available
      - Stats centres rarely expose shot coordinates
      - Aggregated shooting stats only (FG%, 3P%, etc.)

    - **Scenario 2** (FIBA LiveStats): Shots AVAILABLE ✅
      - Same infrastructure as BCL/BAL/ABA/LKL
      - Shot chart with X/Y coordinates (0-100 normalized)
      - Made/missed flag, shot type (2PT/3PT), distance
      - Player, team, game clock for each shot

    **TO INVESTIGATE**:
    1. If Scenario 2 confirmed (see fetch_lnb_pbp docstring)
    2. Test FIBA LiveStats shot endpoints:
       - JSON: `/data/{GAME_ID}/data.json` → "tm.stat" array
       - HTML: `/u/FFBB/{GAME_ID}/bs.html` → Parse shot table
    3. Verify X/Y coordinates present and reasonable (0-100 range)

    **TO IMPLEMENT** (if Scenario 2):
    ```python
    from .fiba_html_common import fetch_fiba_shots

    df = fetch_fiba_shots(
        game_id=game_id,
        comp_code="FFBB_PROA"
    )
    df["LEAGUE"] = "LNB_PROA"
    df["SEASON"] = season
    return df
    ```

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        Empty DataFrame (until investigation determines availability)

    Expected Columns (if Scenario 2 viable):
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - GAME_ID: Game identifier
        - TEAM_ID: Shooting team
        - PLAYER_ID: Shooter
        - PLAYER_NAME: Shooter name
        - PERIOD: Quarter (1-4) or OT
        - GAME_CLOCK: Time of shot (MM:SS)
        - X: X coordinate (0-100, normalized court position)
        - Y: Y coordinate (0-100, normalized court position)
        - SHOT_MADE: 1 if made, 0 if missed
        - SHOT_VALUE: 2 or 3 (points if made)
        - SHOT_TYPE: "2PT" or "3PT"
        - DISTANCE: Distance from basket (meters or feet)
        - SOURCE: "fiba_livestats_json" or "fiba_livestats_html"

    Raises:
        NotImplementedError: Always (until investigation complete)

    See Also:
        - docs/lnb_game_level_investigation.md: Investigation workflow
        - src/cbb_data/fetchers/fiba_html_common.py: FIBA shots implementation
        - src/cbb_data/fetchers/bcl.py: Example FIBA shots usage
    """
    raise NotImplementedError(
        "LNB shots availability depends on investigation results. "
        "Only available if FIBA LiveStats route (Scenario 2) is viable. "
        "See docs/lnb_game_level_investigation.md for complete investigation guide."
    )


def fetch_lnb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch LNB Pro A box score for single game (LEGACY - use fetch_lnb_player_game)

    ❌ **DEPRECATED** - Use fetch_lnb_player_game(season) instead.

    This function signature (single game_id) is being phased out in favor of
    season-level fetchers that handle batching internally.

    Args:
        game_id: Game identifier

    Returns:
        Empty DataFrame

    See Also:
        - fetch_lnb_player_game(season): Preferred method for box scores
        - fetch_lnb_team_game(season): Team-level box scores
    """
    logger.warning(
        "fetch_lnb_box_score(game_id) is deprecated. "
        "Use fetch_lnb_player_game(season) for box scores. "
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
