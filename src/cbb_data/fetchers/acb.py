"""ACB (Liga Endesa - Spain) Fetcher

ACB (Asociación de Clubes de Baloncesto) is Spain's top-tier professional basketball league,
featuring 18 teams. Known as "Liga Endesa" due to sponsorship, it's one of Europe's strongest
leagues. NBA talent pipeline includes Pau Gasol, Marc Gasol, Ricky Rubio, and many others.

✅ **CURRENT STATUS: FULLY IMPLEMENTED** ✅
ACB website restructured in 2024. New URLs discovered and implemented (2025-11-13).
BAwiR integration added for PBP and shot charts (2025-11-18).

**DATA AVAILABILITY**:
- **player_season**: ✅ Available via HTML tables
- **team_season**: ✅ Available via HTML tables
- **schedule**: ✅ Available via HTML calendar scraping
- **box scores**: ✅ Available via HTML tables
- **play-by-play**: ✅ Available via BAwiR R package (requires rpy2)
- **shot charts**: ✅ Available via BAwiR R package (requires rpy2)

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
✅ EXPANDED (2025-11-18) - BAwiR integration for PBP and shot charts
✅ player_season: Scrapes HTML tables from /estadisticas-individuales
✅ team_season: Scrapes HTML tables from /estadisticas-equipos
✅ schedule: Scrapes /calendario page with temporada parameter
✅ box_score: Parses /partido/estadisticas/id/{game_id} tables
✅ play-by-play: Via BAwiR R package (do_scrape_acb_pbp)
✅ shot_chart: Via BAwiR R package (do_scrape_shots_acb)

Technical Notes:
- ACB uses "temporada_id" (ending year) in URLs: 2024-25 season = temporada_id/2025
- 22 HTML tables on player stats page, 20 tables on team stats page, 3 tables on standings
- Encoding: UTF-8 for Spanish names (á, é, í, ó, ú, ñ)
- Tables are server-rendered HTML (not JavaScript), parseable with BeautifulSoup/pandas
- BAwiR requires: uv pip install 'cbb-data[acb]' && R -e "install.packages('BAwiR')"
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error
from .html_tables import normalize_league_columns, read_first_table

logger = logging.getLogger(__name__)

# Path to R scripts for Rscript subprocess fallback
_R_SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "tools" / "r"

# =============================================================================
# Lazy rpy2/BAwiR initialization
# =============================================================================
# rpy2 is NOT imported at module load time to avoid breaking imports on Windows.
# Instead, we use lazy initialization when BAwiR functions are actually called.

RPY2_AVAILABLE = False
_rpy2_init_attempted = False
_ro = None  # type: ignore
_pandas2ri = None  # type: ignore
_importr = None  # type: ignore

# Track BAwiR package availability (checked lazily)
_BAWIR_LOADED = False
_BAWIR = None


def _try_init_rpy2() -> bool:
    """Lazily initialize rpy2 connection to R

    Only attempts initialization once. Returns True if rpy2 is available.
    This pattern prevents import-time failures on Windows where R isn't
    built as a shared library.

    Returns:
        True if rpy2 is available and connected to R, False otherwise
    """
    global RPY2_AVAILABLE, _rpy2_init_attempted, _ro, _pandas2ri, _importr

    # Only try once
    if _rpy2_init_attempted:
        return RPY2_AVAILABLE

    _rpy2_init_attempted = True

    try:
        import rpy2.robjects as ro
        from rpy2.robjects import pandas2ri
        from rpy2.robjects.packages import importr

        # Activate pandas conversion
        pandas2ri.activate()

        # Store references
        _ro = ro
        _pandas2ri = pandas2ri
        _importr = importr
        RPY2_AVAILABLE = True

        logger.info("rpy2 initialized successfully")
        return True

    except ImportError as e:
        RPY2_AVAILABLE = False
        logger.debug(
            f"rpy2 not installed: {e}. ACB BAwiR-based fetchers disabled. "
            "Install with: uv sync --extra acb"
        )
        return False

    except (TypeError, OSError, Exception) as e:
        # Windows-specific: R may not be built as a shared library
        RPY2_AVAILABLE = False
        logger.debug(
            f"rpy2 initialization failed: {e}. ACB BAwiR-based fetchers disabled. "
            "On Windows, R must be built with --enable-R-shlib for rpy2 to work. "
            "See PROJECT_LOG.md for workarounds (WSL, devcontainer)."
        )
        return False


def _ensure_bawir() -> bool:
    """Ensure BAwiR R package is loaded

    Uses lazy initialization - only attempts rpy2 connection when actually needed.

    Returns:
        True if BAwiR is available, False otherwise
    """
    global _BAWIR_LOADED, _BAWIR

    # First, ensure rpy2 is initialized (lazy init)
    if not _try_init_rpy2():
        return False

    if _BAWIR_LOADED:
        return _BAWIR is not None

    try:
        # Import BAwiR package using stored importr reference
        if _importr is None:
            logger.warning("rpy2 importr not available - cannot load BAwiR")
            _BAWIR_LOADED = True  # Mark as attempted
            _BAWIR = None
            return False
        _BAWIR = _importr("BAwiR")
        _BAWIR_LOADED = True
        logger.info("BAwiR R package loaded successfully")
        return True
    except Exception as e:
        logger.warning(
            f"Failed to load BAwiR R package: {e}. " "Install in R with: install.packages('BAwiR')"
        )
        _BAWIR_LOADED = True  # Mark as attempted
        _BAWIR = None
        return False


# =============================================================================
# Rscript subprocess fallback for Windows
# =============================================================================
# When rpy2 can't connect to R (common on Windows), we can still use BAwiR
# by running Rscript as a subprocess and exchanging data via CSV files.


def _check_rscript_available() -> bool:
    """Check if Rscript is available in PATH"""
    try:
        result = subprocess.run(
            ["Rscript", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_bawir_rscript(data_type: str, season: str, output_file: Path) -> bool:
    """Run BAwiR extraction via Rscript subprocess

    This is the fallback when rpy2 is unavailable (e.g., Windows).

    Args:
        data_type: Type of data to extract ("games", "shots", "days")
        season: Season string (e.g., "2024")
        output_file: Path to write CSV output

    Returns:
        True if successful, False otherwise
    """
    r_script = _R_SCRIPTS_DIR / "acb_bawir_extract.R"

    if not r_script.exists():
        logger.error(f"R script not found: {r_script}")
        return False

    if not _check_rscript_available():
        logger.error("Rscript not found in PATH")
        return False

    try:
        cmd = [
            "Rscript",
            "--vanilla",
            str(r_script),
            "--type",
            data_type,
            "--season",
            season,
            "--output",
            str(output_file),
        ]

        logger.info(f"Running BAwiR via Rscript: {data_type} for {season}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for large datasets
        )

        if result.returncode != 0:
            logger.error(f"Rscript failed: {result.stderr}")
            return False

        logger.info("Rscript completed successfully")
        return True

    except subprocess.TimeoutExpired:
        logger.error("Rscript timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Rscript execution failed: {e}")
        return False


# Get rate limiter
rate_limiter = get_source_limiter()

# ACB URLs (updated 2025-11-13 after website restructure)
ACB_BASE_URL = "https://www.acb.com"

# NEW URL structure (working as of 2025-11-13):
# Player stats: /estadisticas-individuales/index/temporada_id/{ending_year}
# Team stats: /estadisticas-equipos/index/temporada_id/{ending_year}
# Standings: /resultados-clasificacion/ver

# Note: ACB uses ending year in URLs (2024-25 season = temporada_id/2025)


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
    """Fetch ACB schedule from Next.js calendar page

    ✅ FIXED (2025-11-18): Parses embedded Next.js data from /es/calendario.

    The ACB website migrated to a React SPA in late 2024. This function now
    extracts game data from the embedded Next.js streaming format instead of
    HTML scraping.

    Args:
        season: Season string (e.g., "2024-25", "2024", "2023-24")
        season_type: Season type ("Regular Season", "Playoffs")

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: Unique game identifier
        - SEASON: Season string
        - GAME_DATE: Game date/time (ISO format)
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (if game completed)
        - AWAY_SCORE: Away team score (if game completed)
        - JORNADA: Matchday/round number
        - LEAGUE: "ACB"

    Implementation:
        Fetches https://www.acb.com/es/calendario?temporada={id}
        Parses embedded Next.js streaming data containing:
        - teams array: [{id, fullName, shortName, abbreviatedName}, ...]
        - rounds[].matches array: [{id, homeTeam, awayTeam, scores, date}, ...]

        Teams are referenced by array index in match data.

        Historical Access:
        ACB provides 42 years of historical data (1983-84 to 2025-26) via
        the temporada URL parameter. Formula: temporada = season_end_year - 1936
        Example: 2024-25 season → temporada=89 (2025-1936=89)

    Note:
        All historical seasons accessible via temporada parameter.
        Season format "YYYY-YY" (e.g., "2024-25") or "YYYY" (uses as end year).
    """
    rate_limiter.acquire("acb")

    logger.info(f"Fetching ACB schedule: {season}, {season_type}")

    try:
        # Calculate temporada parameter for historical season access
        # ACB formula: temporada = season_end_year - 1936
        # Examples: 2024-25 → 89, 1983-84 → 48
        if "-" in season:
            # Format: "2024-25" or "1983-84"
            parts = season.split("-")
            season_start = int(parts[0])
            season_end = int(parts[1])

            # Determine century based on start year for 2-digit end years
            if season_end < 100:
                if season_start >= 2000:
                    season_end_year = season_end + 2000
                else:
                    season_end_year = season_end + 1900
            else:
                season_end_year = season_end
        else:
            # Format: "2025" → use directly
            season_end_year = int(season)

        temporada = season_end_year - 1936
        logger.info(f"ACB season {season} → temporada parameter = {temporada}")

        # Fetch calendar page - new React SPA at /es/calendario
        import requests
        from bs4 import BeautifulSoup

        url = f"{ACB_BASE_URL}/es/calendario?temporada={temporada}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # Find the large data script with embedded Next.js streaming data
        scripts = soup.find_all("script")
        data_content = None

        for script in scripts:
            content = script.string or ""
            if len(content) > 100000 and "teams" in content and "matches" in content:
                # Unescape the Next.js streaming format
                data_content = content.replace('\\"', '"')
                break

        if not data_content:
            logger.warning("No Next.js data found on ACB calendar page")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "SEASON",
                    "GAME_DATE",
                    "HOME_TEAM",
                    "AWAY_TEAM",
                    "HOME_SCORE",
                    "AWAY_SCORE",
                    "JORNADA",
                    "LEAGUE",
                ]
            )

        # Extract teams from embedded data
        # Pattern: "id":4238,"clubId":2,"fullName":"Barça","shortName":"Barça","abbreviatedName":"BAR"
        team_pattern = r'"id":(\d+),"clubId":\d+,"fullName":"([^"]+)","shortName":"([^"]+)","abbreviatedName":"([^"]+)"'

        teams = []
        for m in re.finditer(team_pattern, data_content):
            teams.append(
                {
                    "id": int(m.group(1)),
                    "full_name": m.group(2),
                    "short_name": m.group(3),
                    "abbrev": m.group(4),
                }
            )

        if not teams:
            logger.warning("No teams found in ACB calendar data")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "SEASON",
                    "GAME_DATE",
                    "HOME_TEAM",
                    "AWAY_TEAM",
                    "HOME_SCORE",
                    "AWAY_SCORE",
                    "JORNADA",
                    "LEAGUE",
                ]
            )

        logger.info(f"Found {len(teams)} ACB teams")

        # Extract matches from embedded data
        # Pattern: "id":103773,"homeTeam":"$28:props:data:teams:16",...
        match_pattern = r'"id":(\d+),"homeTeam":"[^"]+:(\d+)","awayTeam":"[^"]+:(\d+)","homeTeamScore":(\d+|null),"awayTeamScore":(\d+|null),"startDateTime":"([^"]+)"'

        games = []
        for m in re.finditer(match_pattern, data_content):
            game_id = int(m.group(1))
            home_idx = int(m.group(2))
            away_idx = int(m.group(3))
            home_score = None if m.group(4) == "null" else int(m.group(4))
            away_score = None if m.group(5) == "null" else int(m.group(5))
            game_date = m.group(6)

            # Resolve team names from array indices
            if home_idx < len(teams) and away_idx < len(teams):
                home_team = teams[home_idx]["short_name"]
                away_team = teams[away_idx]["short_name"]
            else:
                home_team = f"Team{home_idx}"
                away_team = f"Team{away_idx}"

            games.append(
                {
                    "GAME_ID": str(game_id),
                    "SEASON": season,
                    "GAME_DATE": game_date,
                    "HOME_TEAM": home_team,
                    "AWAY_TEAM": away_team,
                    "HOME_SCORE": home_score,
                    "AWAY_SCORE": away_score,
                    "JORNADA": None,  # Round info would require additional parsing
                    "LEAGUE": "ACB",
                }
            )

        if not games:
            logger.warning("No games found in ACB calendar data")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "SEASON",
                    "GAME_DATE",
                    "HOME_TEAM",
                    "AWAY_TEAM",
                    "HOME_SCORE",
                    "AWAY_SCORE",
                    "JORNADA",
                    "LEAGUE",
                ]
            )

        df = pd.DataFrame(games)

        # Convert game date to datetime for sorting
        try:
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
            df = df.sort_values("GAME_DATE").reset_index(drop=True)
        except Exception:
            pass  # Keep as string if conversion fails

        logger.info(f"Fetched {len(df)} ACB games from calendar")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB schedule: {e}")
        # Return empty DataFrame with schema
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "SEASON",
                "GAME_DATE",
                "HOME_TEAM",
                "AWAY_TEAM",
                "HOME_SCORE",
                "AWAY_SCORE",
                "JORNADA",
                "LEAGUE",
            ]
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch ACB box score for a game

    ✅ IMPLEMENTED (2025-11-18): Scrapes box scores from game statistics page.

    Args:
        game_id: Game ID (ACB game identifier)

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - MIN: Minutes played
        - PTS: Points (P)
        - FGM, FGA, FG_PCT: 2-point field goals (T2)
        - FG3M, FG3A, FG3_PCT: 3-point field goals (T3)
        - FTM, FTA, FT_PCT: Free throws (T1)
        - OREB: Offensive rebounds (O)
        - DREB: Defensive rebounds (D)
        - REB: Total rebounds (T)
        - AST: Assists (A)
        - STL: Steals (BR)
        - BLK: Blocks (C)
        - TOV: Turnovers (BP)
        - PF: Personal fouls (F)
        - PLUS_MINUS: Plus/minus (+/-)
        - VAL: Valuation (V)
        - LEAGUE: "ACB"

    Implementation:
        Scrapes https://www.acb.com/partido/estadisticas/id/{game_id}
        Parses HTML tables with player statistics for both teams.

    Note:
        ACB uses Spanish abbreviations: T2 (2PT), T3 (3PT), T1 (FT),
        A (AST), BR (STL), BP (TOV), C (BLK), F (PF), V (Valuation)
    """
    rate_limiter.acquire("acb")

    logger.info(f"Fetching ACB box score: {game_id}")

    try:
        # Build URL for game statistics page
        url = f"{ACB_BASE_URL}/partido/estadisticas/id/{game_id}"

        # Fetch all tables from the page
        tables = pd.read_html(url, encoding="utf-8")

        if not tables or len(tables) < 2:
            logger.warning(f"No sufficient tables found for game {game_id}")
            return _empty_acb_box_score(game_id)

        all_players = []

        # ACB typically has 2 main tables (one for each team)
        # Tables usually have columns: Player, Min, P (points), T2, T3, T1, T/D+O (rebounds), A, BR, BP, C, F, +/-, V
        for table_idx, table in enumerate(tables[:2]):  # Process first 2 tables (teams)
            # Skip tables with too few columns or rows
            if table.shape[1] < 10 or len(table) < 2:
                continue

            # Try to get team name from table header or previous elements
            team_name = f"Team{table_idx + 1}"  # Fallback

            for _row_idx, row in table.iterrows():
                try:
                    # Skip header rows
                    if str(row.iloc[0]).lower() in ["jugador", "player", "totales", "totals"]:
                        continue

                    player_name = str(row.iloc[0]) if len(row) > 0 else "Unknown"

                    # Skip empty or total rows
                    if not player_name or player_name.lower() in [
                        "totales",
                        "totals",
                        "equipo",
                        "team",
                    ]:
                        continue

                    # Parse statistics (column positions may vary, handle gracefully)
                    minutes = _safe_acb_int(row.iloc[1]) if len(row) > 1 else 0
                    points = _safe_acb_int(row.iloc[2]) if len(row) > 2 else 0

                    # Parse shooting stats (format: "Made-Attempted" or "Made/Attempted")
                    t2_text = str(row.iloc[3]) if len(row) > 3 else "0-0"
                    t2m, t2a = _parse_acb_shooting(t2_text)

                    t3_text = str(row.iloc[4]) if len(row) > 4 else "0-0"
                    t3m, t3a = _parse_acb_shooting(t3_text)

                    ft_text = str(row.iloc[5]) if len(row) > 5 else "0-0"
                    ftm, fta = _parse_acb_shooting(ft_text)

                    # Rebounds (format: "T/D+O" or separate columns)
                    reb_text = str(row.iloc[6]) if len(row) > 6 else "0/0+0"
                    total_reb, def_reb, off_reb = _parse_acb_rebounds(reb_text)

                    # Other stats
                    assists = _safe_acb_int(row.iloc[7]) if len(row) > 7 else 0
                    steals = _safe_acb_int(row.iloc[8]) if len(row) > 8 else 0
                    turnovers = _safe_acb_int(row.iloc[9]) if len(row) > 9 else 0
                    blocks = _safe_acb_int(row.iloc[10]) if len(row) > 10 else 0
                    fouls = _safe_acb_int(row.iloc[11]) if len(row) > 11 else 0
                    plus_minus = _safe_acb_int(row.iloc[12]) if len(row) > 12 else 0
                    valuation = _safe_acb_int(row.iloc[13]) if len(row) > 13 else 0

                    player_stat = {
                        "GAME_ID": game_id,
                        "PLAYER_NAME": player_name,
                        "TEAM": team_name,
                        "MIN": minutes,
                        "PTS": points,
                        "FGM": t2m,  # 2-point made
                        "FGA": t2a,  # 2-point attempted
                        "FG_PCT": (t2m / t2a * 100) if t2a > 0 else 0,
                        "FG3M": t3m,
                        "FG3A": t3a,
                        "FG3_PCT": (t3m / t3a * 100) if t3a > 0 else 0,
                        "FTM": ftm,
                        "FTA": fta,
                        "FT_PCT": (ftm / fta * 100) if fta > 0 else 0,
                        "OREB": off_reb,
                        "DREB": def_reb,
                        "REB": total_reb,
                        "AST": assists,
                        "STL": steals,
                        "BLK": blocks,
                        "TOV": turnovers,
                        "PF": fouls,
                        "PLUS_MINUS": plus_minus,
                        "VAL": valuation,
                        "LEAGUE": "ACB",
                    }

                    all_players.append(player_stat)

                except Exception as e:
                    logger.debug(f"Error parsing player row in table {table_idx}: {e}")
                    continue

        if not all_players:
            logger.warning(f"No player stats extracted for game {game_id}")
            return _empty_acb_box_score(game_id)

        df = pd.DataFrame(all_players)
        logger.info(f"Fetched box score: {len(df)} players from {len(set(df['TEAM']))} teams")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB box score for game {game_id}: {e}")
        return _empty_acb_box_score(game_id)


def _empty_acb_box_score(game_id: str) -> pd.DataFrame:
    """Return empty ACB box score DataFrame with correct schema"""
    df = pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_NAME",
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
            "VAL",
            "LEAGUE",
        ]
    )
    df["LEAGUE"] = "ACB"
    df["GAME_ID"] = game_id
    return df


def _safe_acb_int(value: Any, default: int = 0) -> int:
    """Safely convert ACB stat value to int"""
    try:
        # Handle pandas NA/NaN
        if pd.isna(value):
            return default
        # Convert to string and clean
        s = str(value).strip().replace(",", "")
        # Extract first number if multiple present
        import re

        match = re.search(r"-?\d+", s)
        return int(match.group(0)) if match else default
    except (ValueError, TypeError):
        return default


def _parse_acb_shooting(text: str) -> tuple[int, int]:
    """Parse ACB shooting stat (format: 'Made-Attempted' or 'Made/Attempted')

    Args:
        text: Shooting stat text (e.g., "5-10", "5/10", "50%")

    Returns:
        Tuple of (made, attempted)
    """
    try:
        text = str(text).strip()
        # Handle percentage format (just ignore)
        if "%" in text:
            return 0, 0
        # Split by '-' or '/'
        if "-" in text:
            parts = text.split("-")
        elif "/" in text:
            parts = text.split("/")
        else:
            return 0, 0

        if len(parts) == 2:
            made = _safe_acb_int(parts[0])
            attempted = _safe_acb_int(parts[1])
            return made, attempted
    except Exception:
        pass

    return 0, 0


def _parse_acb_rebounds(text: str) -> tuple[int, int, int]:
    """Parse ACB rebound stat (format: 'Total/Defensive+Offensive')

    Args:
        text: Rebound stat text (e.g., "10/7+3")

    Returns:
        Tuple of (total, defensive, offensive)
    """
    try:
        text = str(text).strip()

        # Handle format: "T/D+O" (e.g., "10/7+3")
        if "/" in text and "+" in text:
            parts = text.split("/")
            total = _safe_acb_int(parts[0])

            reb_parts = parts[1].split("+")
            defensive = _safe_acb_int(reb_parts[0])
            offensive = _safe_acb_int(reb_parts[1]) if len(reb_parts) > 1 else 0

            return total, defensive, offensive

        # Fallback: just total rebounds
        total = _safe_acb_int(text)
        return total, 0, 0

    except Exception:
        pass

    return 0, 0, 0


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


# =============================================================================
# BAwiR-based fetchers (rpy2 + R package)
# =============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_game_index_bawir(season: str) -> pd.DataFrame:
    """Discover all game codes for an ACB season using BAwiR R package

    Uses BAwiR::get_acb_pbp_games() to retrieve game codes that can be used
    for play-by-play and shot chart fetching.

    Args:
        season: Season string (e.g., "2024", "2024-25")
                Uses starting year format (2024 → "2024-2025")

    Returns:
        DataFrame with game codes and metadata

    Columns:
        - GAME_CODE: ACB game identifier for BAwiR functions
        - SEASON: Season string
        - GAME_DATE: Game date (if available)
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - LEAGUE: "ACB"

    Requires:
        - rpy2 Python package: uv pip install 'cbb-data[acb]'
        - BAwiR R package: install.packages('BAwiR')

    Example:
        >>> games = fetch_acb_game_index_bawir("2024")
        >>> print(f"Found {len(games)} ACB games for 2024-25")
    """
    empty_df = pd.DataFrame(
        columns=["GAME_CODE", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]
    )

    rate_limiter.acquire("acb")

    # Convert season format to BAwiR expected format
    # BAwiR typically uses "YYYY-YYYY" format (e.g., "2024-2025")
    if "-" in season:
        parts = season.split("-")
        start_year = int(parts[0])
        end_year = int(parts[1])
        # Handle 2-digit year
        if end_year < 100:
            end_year = start_year + 1
        bawir_season = f"{start_year}-{end_year}"
    else:
        start_year = int(season)
        bawir_season = f"{start_year}-{start_year + 1}"

    # Try rpy2 first, fall back to Rscript subprocess
    if _ensure_bawir():
        # These are guaranteed non-None after _ensure_bawir() returns True
        assert _BAWIR is not None
        assert _pandas2ri is not None
        logger.info(f"Fetching ACB game index via BAwiR (rpy2): {bawir_season}")
        try:
            # Call BAwiR::get_acb_pbp_games()
            # Returns R data.frame with game codes
            r_result = _BAWIR.get_acb_pbp_games(bawir_season)

            # Convert R data.frame to pandas DataFrame using stored reference
            df = _pandas2ri.rpy2py(r_result)
        except Exception as e:
            logger.error(f"rpy2 BAwiR call failed: {e}")
            df = empty_df
    else:
        # rpy2 not available - check if Rscript fallback is possible
        if _check_rscript_available():
            logger.warning(
                "rpy2 unavailable but Rscript found. BAwiR Rscript fallback "
                "requires additional configuration. See PROJECT_LOG.md for details."
            )
        else:
            logger.warning(
                "Neither rpy2 nor Rscript available. BAwiR-based ACB data unavailable. "
                "Use HTML-based fetchers (fetch_acb_schedule, fetch_acb_box_score) instead."
            )
        return empty_df

    # Common processing for both rpy2 and Rscript paths
    if df.empty:
        logger.warning(f"No games found for ACB {bawir_season}")
        return empty_df

    # Normalize column names (BAwiR uses various conventions)
    # Common columns: game_code, date, home_team, away_team
    column_map = {
        "game_code": "GAME_CODE",
        "gameCode": "GAME_CODE",
        "codigo": "GAME_CODE",
        "date": "GAME_DATE",
        "fecha": "GAME_DATE",
        "home": "HOME_TEAM",
        "local": "HOME_TEAM",
        "away": "AWAY_TEAM",
        "visitante": "AWAY_TEAM",
    }

    # Apply column mapping
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    # Ensure required columns exist
    if "GAME_CODE" not in df.columns:
        # Try to use first column as game code
        df["GAME_CODE"] = df.iloc[:, 0]

    # Add metadata
    df["SEASON"] = season
    df["LEAGUE"] = "ACB"

    logger.info(f"Fetched {len(df)} ACB game codes via BAwiR for {bawir_season}")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_pbp_bawir(season: str) -> pd.DataFrame:
    """Fetch full ACB play-by-play for a season via BAwiR R package

    Uses BAwiR::do_scrape_acb_pbp() to fetch detailed play-by-play data
    for all games in a season. This is the primary PBP source for ACB.

    Args:
        season: Season string (e.g., "2024", "2024-25")

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENT_NUM: Event sequence number
        - PERIOD: Game period (1-4, OT)
        - CLOCK: Game clock time
        - EVENT_TYPE: Type of play (shot, rebound, turnover, etc.)
        - PLAYER_NAME: Player involved
        - TEAM: Team name
        - DESCRIPTION: Event description (Spanish)
        - HOME_SCORE: Running home team score
        - AWAY_SCORE: Running away team score
        - LEAGUE: "ACB"
        - SEASON: Season string

    Requires:
        - rpy2 Python package: uv pip install 'cbb-data[acb]'
        - BAwiR R package: install.packages('BAwiR')

    Note:
        This function fetches all games in the season, which may take several minutes.
        Use fetch_acb_game_index_bawir() first to discover available games.
    """
    if not _ensure_bawir():
        logger.error(
            "BAwiR not available. Install requirements: "
            "uv pip install 'cbb-data[acb]' && R -e \"install.packages('BAwiR')\""
        )
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_NUM",
                "PERIOD",
                "CLOCK",
                "EVENT_TYPE",
                "PLAYER_NAME",
                "TEAM",
                "DESCRIPTION",
                "LEAGUE",
                "SEASON",
            ]
        )

    rate_limiter.acquire("acb")

    # Get game index first
    game_index = fetch_acb_game_index_bawir(season)
    if game_index.empty:
        logger.warning(f"No games found for ACB {season}, cannot fetch PBP")
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_NUM",
                "PERIOD",
                "CLOCK",
                "EVENT_TYPE",
                "PLAYER_NAME",
                "TEAM",
                "DESCRIPTION",
                "LEAGUE",
                "SEASON",
            ]
        )

    # Convert season format
    if "-" in season:
        parts = season.split("-")
        start_year = int(parts[0])
        end_year = int(parts[1])
        if end_year < 100:
            end_year = start_year + 1
        bawir_season = f"{start_year}-{end_year}"
    else:
        start_year = int(season)
        bawir_season = f"{start_year}-{start_year + 1}"

    logger.info(f"Fetching ACB PBP via BAwiR for {len(game_index)} games: {bawir_season}")

    # These are guaranteed non-None (caller should have ensured BAwiR is available)
    assert _BAWIR is not None
    assert _pandas2ri is not None

    all_pbp = []

    try:
        # Get game codes
        game_codes = game_index["GAME_CODE"].tolist()

        for i, game_code in enumerate(game_codes):
            try:
                # Call BAwiR::do_scrape_acb_pbp() for each game
                r_result = _BAWIR.do_scrape_acb_pbp(game_code)

                # Convert to pandas using stored reference
                game_pbp = _pandas2ri.rpy2py(r_result)

                if game_pbp.empty:
                    continue

                # Normalize columns
                column_map = {
                    "time": "CLOCK",
                    "tiempo": "CLOCK",
                    "period": "PERIOD",
                    "periodo": "PERIOD",
                    "action": "EVENT_TYPE",
                    "accion": "EVENT_TYPE",
                    "player": "PLAYER_NAME",
                    "jugador": "PLAYER_NAME",
                    "team": "TEAM",
                    "equipo": "TEAM",
                    "description": "DESCRIPTION",
                    "descripcion": "DESCRIPTION",
                    "home_score": "HOME_SCORE",
                    "away_score": "AWAY_SCORE",
                }

                game_pbp = game_pbp.rename(
                    columns={k: v for k, v in column_map.items() if k in game_pbp.columns}
                )

                # Add metadata
                game_pbp["GAME_ID"] = str(game_code)
                game_pbp["EVENT_NUM"] = range(1, len(game_pbp) + 1)
                game_pbp["LEAGUE"] = "ACB"
                game_pbp["SEASON"] = season

                all_pbp.append(game_pbp)

                if (i + 1) % 20 == 0:
                    logger.info(f"Processed {i + 1}/{len(game_codes)} ACB games")

            except Exception as e:
                logger.warning(f"Failed to fetch PBP for game {game_code}: {e}")
                continue

        if not all_pbp:
            logger.warning(f"No PBP data collected for ACB {season}")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "EVENT_NUM",
                    "PERIOD",
                    "CLOCK",
                    "EVENT_TYPE",
                    "PLAYER_NAME",
                    "TEAM",
                    "DESCRIPTION",
                    "LEAGUE",
                    "SEASON",
                ]
            )

        df = pd.concat(all_pbp, ignore_index=True)
        logger.info(f"Fetched {len(df)} PBP events from {len(all_pbp)} ACB games")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB PBP via BAwiR: {e}")
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "EVENT_NUM",
                "PERIOD",
                "CLOCK",
                "EVENT_TYPE",
                "PLAYER_NAME",
                "TEAM",
                "DESCRIPTION",
                "LEAGUE",
                "SEASON",
            ]
        )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_shot_chart_bawir(season: str) -> pd.DataFrame:
    """Fetch ACB shot-level data for a season via BAwiR's do_scrape_shots_acb

    Uses BAwiR::do_scrape_shots_acb() to fetch shot chart data with
    court coordinates for all games in a season.

    Args:
        season: Season string (e.g., "2024", "2024-25")

    Returns:
        DataFrame with shot chart data

    Columns:
        - GAME_ID: Game identifier
        - SHOT_ID: Unique shot identifier
        - PLAYER_NAME: Shooter name
        - TEAM: Team name
        - PERIOD: Game period
        - CLOCK: Game clock time
        - SHOT_TYPE: Shot type (2PT, 3PT)
        - LOC_X: Court X coordinate
        - LOC_Y: Court Y coordinate
        - SHOT_RESULT: Made/Missed
        - SHOT_DISTANCE: Distance from basket
        - LEAGUE: "ACB"
        - SEASON: Season string

    Requires:
        - rpy2 Python package: uv pip install 'cbb-data[acb]'
        - BAwiR R package: install.packages('BAwiR')

    Note:
        Shot coordinates use ACB's court dimensions.
        This function fetches all games in the season.
    """
    if not _ensure_bawir():
        logger.error(
            "BAwiR not available. Install requirements: "
            "uv pip install 'cbb-data[acb]' && R -e \"install.packages('BAwiR')\""
        )
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "SHOT_ID",
                "PLAYER_NAME",
                "TEAM",
                "PERIOD",
                "CLOCK",
                "SHOT_TYPE",
                "LOC_X",
                "LOC_Y",
                "SHOT_RESULT",
                "LEAGUE",
                "SEASON",
            ]
        )

    rate_limiter.acquire("acb")

    # Get game index first
    game_index = fetch_acb_game_index_bawir(season)
    if game_index.empty:
        logger.warning(f"No games found for ACB {season}, cannot fetch shots")
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "SHOT_ID",
                "PLAYER_NAME",
                "TEAM",
                "PERIOD",
                "CLOCK",
                "SHOT_TYPE",
                "LOC_X",
                "LOC_Y",
                "SHOT_RESULT",
                "LEAGUE",
                "SEASON",
            ]
        )

    # Convert season format
    if "-" in season:
        parts = season.split("-")
        start_year = int(parts[0])
        end_year = int(parts[1])
        if end_year < 100:
            end_year = start_year + 1
        bawir_season = f"{start_year}-{end_year}"
    else:
        start_year = int(season)
        bawir_season = f"{start_year}-{start_year + 1}"

    logger.info(f"Fetching ACB shot charts via BAwiR for {len(game_index)} games: {bawir_season}")

    # These are guaranteed non-None (caller should have ensured BAwiR is available)
    assert _BAWIR is not None
    assert _pandas2ri is not None

    all_shots = []

    try:
        # Get game codes
        game_codes = game_index["GAME_CODE"].tolist()

        for i, game_code in enumerate(game_codes):
            try:
                # Call BAwiR::do_scrape_shots_acb() for each game
                r_result = _BAWIR.do_scrape_shots_acb(game_code)

                # Convert to pandas using stored reference
                game_shots = _pandas2ri.rpy2py(r_result)

                if game_shots.empty:
                    continue

                # Normalize columns
                column_map = {
                    "player": "PLAYER_NAME",
                    "jugador": "PLAYER_NAME",
                    "team": "TEAM",
                    "equipo": "TEAM",
                    "period": "PERIOD",
                    "periodo": "PERIOD",
                    "time": "CLOCK",
                    "tiempo": "CLOCK",
                    "x": "LOC_X",
                    "y": "LOC_Y",
                    "made": "SHOT_RESULT",
                    "anotado": "SHOT_RESULT",
                    "type": "SHOT_TYPE",
                    "tipo": "SHOT_TYPE",
                    "distance": "SHOT_DISTANCE",
                    "distancia": "SHOT_DISTANCE",
                }

                game_shots = game_shots.rename(
                    columns={k: v for k, v in column_map.items() if k in game_shots.columns}
                )

                # Normalize shot result to MADE/MISSED
                if "SHOT_RESULT" in game_shots.columns:
                    game_shots["SHOT_RESULT"] = game_shots["SHOT_RESULT"].apply(
                        lambda x: "MADE"
                        if str(x).lower() in ["true", "1", "yes", "si", "anotado"]
                        else "MISSED"
                    )

                # Add metadata
                game_shots["GAME_ID"] = str(game_code)
                game_shots["SHOT_ID"] = [f"{game_code}_{i}" for i in range(len(game_shots))]
                game_shots["LEAGUE"] = "ACB"
                game_shots["SEASON"] = season

                all_shots.append(game_shots)

                if (i + 1) % 20 == 0:
                    logger.info(f"Processed {i + 1}/{len(game_codes)} ACB games for shots")

            except Exception as e:
                logger.warning(f"Failed to fetch shots for game {game_code}: {e}")
                continue

        if not all_shots:
            logger.warning(f"No shot data collected for ACB {season}")
            return pd.DataFrame(
                columns=[
                    "GAME_ID",
                    "SHOT_ID",
                    "PLAYER_NAME",
                    "TEAM",
                    "PERIOD",
                    "CLOCK",
                    "SHOT_TYPE",
                    "LOC_X",
                    "LOC_Y",
                    "SHOT_RESULT",
                    "LEAGUE",
                    "SEASON",
                ]
            )

        df = pd.concat(all_shots, ignore_index=True)
        logger.info(f"Fetched {len(df)} shots from {len(all_shots)} ACB games")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch ACB shots via BAwiR: {e}")
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "SHOT_ID",
                "PLAYER_NAME",
                "TEAM",
                "PERIOD",
                "CLOCK",
                "SHOT_TYPE",
                "LOC_X",
                "LOC_Y",
                "SHOT_RESULT",
                "LEAGUE",
                "SEASON",
            ]
        )
