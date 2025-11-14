"""Shared FIBA LiveStats HTML Scraping Infrastructure

Generic, reusable infrastructure for scraping basketball data from FIBA LiveStats HTML pages.
Used by multiple leagues: LKL, BAL, BCL, ABA, and NZ-NBL.

Key Features:
- Unified HTML parsing for box scores and play-by-play
- Game index management (CSV-based game ID catalog)
- Retry logic with exponential backoff
- Local caching to reduce server load
- Data validation against contracts
- Incremental updates (fetch only new games)

Architecture:
- FIBA LiveStats serves public HTML pages at:
  - Box scores: https://fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE_CODE}/{GAME_ID}/bs.html
  - Play-by-play: https://fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE_CODE}/{GAME_ID}/pbp.html
- Each league has a 3-letter code (e.g., "NZN" for NZ-NBL, "LKL" for Lithuania)
- Game IDs must be pre-collected in CSV files (FIBA doesn't provide searchable index API)

Usage:
    from cbb_data.fetchers.fiba_html_common import scrape_fiba_box_score, load_fiba_game_index

    # Load game index for a league/season
    game_index = load_fiba_game_index("LKL", "2023-24")

    # Scrape box score for a specific game
    player_stats = scrape_fiba_box_score("LKL", "123456")

Data Granularities:
- schedule: ✅ Via game index CSV
- player_game: ✅ Via HTML box score scraping
- team_game: ✅ Aggregated from player_game
- pbp: ✅ Via HTML play-by-play scraping
- shots: ❌ FIBA HTML doesn't provide (x,y) coordinates
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

from ..contracts import ensure_standard_columns, validate_player_game, validate_schedule
from ..utils.rate_limiter import get_source_limiter

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# FIBA LiveStats base URL
FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"

# Game index directory (CSV files with game IDs per league/season)
GAME_INDEX_DIR = Path("data/game_indexes")

# Cache directory for scraped HTML (reduces server load)
CACHE_DIR = Path("data/.cache/fiba_html")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Try to import optional dependencies
try:
    import requests
    from bs4 import BeautifulSoup

    HTML_PARSING_AVAILABLE = True
except ImportError:
    HTML_PARSING_AVAILABLE = False
    logger.warning(
        "HTML parsing dependencies not available. "
        "Install with: uv pip install requests beautifulsoup4\n"
        "FIBA league data fetching requires these packages."
    )


# ==============================================================================
# Retry & Caching Decorators
# ==============================================================================

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3, base_delay: float = 1.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied by attempt number)

    Example:
        @with_retry(max_attempts=3, base_delay=2.0)
        def fetch_data():
            return requests.get(url)
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = base_delay * attempt
                        logger.warning(
                            f"Error in {fn.__name__} attempt {attempt}/{max_attempts}: {exc}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"Error in {fn.__name__} after {max_attempts} attempts: {exc}")
            raise last_exc  # type: ignore

        return wrapper  # type: ignore

    return decorator


def with_cache(
    cache_key_fn: Callable[..., str],
) -> Callable[[Callable[..., pd.DataFrame]], Callable[..., pd.DataFrame]]:
    """Decorator for caching function results to disk

    Args:
        cache_key_fn: Function that generates cache key from args/kwargs
            Example: lambda league, game_id: f"{league}_{game_id}_bs"

    Example:
        @with_cache(lambda league, game_id: f"{league}_{game_id}")
        def scrape_game(league, game_id):
            return expensive_scrape()
    """

    def decorator(fn: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> pd.DataFrame:
            # Generate cache key
            cache_key = cache_key_fn(*args, **kwargs)
            cache_file = CACHE_DIR / f"{cache_key}.parquet"

            # Check if cached (and force_refresh not set)
            force_refresh = kwargs.get("force_refresh", False)
            if not force_refresh and cache_file.exists():
                try:
                    logger.debug(f"Loading from cache: {cache_file.name}")
                    return pd.read_parquet(cache_file)
                except Exception as e:
                    logger.warning(f"Cache read failed for {cache_file.name}: {e}")

            # Execute function and cache result
            result = fn(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and not result.empty:
                try:
                    result.to_parquet(cache_file, index=False)
                    logger.debug(f"Saved to cache: {cache_file.name}")
                except Exception as e:
                    logger.warning(f"Cache write failed for {cache_file.name}: {e}")

            return result

        return wrapper  # type: ignore

    return decorator


# ==============================================================================
# Game Index Management
# ==============================================================================


def load_fiba_game_index(
    league_code: str, season: str, index_path: Path | None = None
) -> pd.DataFrame:
    """Load pre-built FIBA game index for a league/season

    The game index is a CSV file mapping games to FIBA game IDs.
    Required because FIBA LiveStats doesn't provide a searchable schedule API.

    Args:
        league_code: FIBA league code (e.g., "LKL", "BAL", "BCL", "ABA", "NZN")
        season: Season string (e.g., "2023-24")
        index_path: Optional custom path to game index file

    Returns:
        DataFrame with game index

    Columns:
        - LEAGUE: League identifier (standardized, e.g., "LKL" not "LKL_LITHUANIA")
        - SEASON: Season string
        - GAME_ID: FIBA game ID
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score (if known)
        - AWAY_SCORE: Away team final score (if known)
        - FIBA_COMPETITION: FIBA competition code (for reference)
        - FIBA_PHASE: Season phase (RS, PO, FF, etc.)

    Example:
        >>> index = load_fiba_game_index("LKL", "2023-24")
        >>> print(f"Loaded {len(index)} games")
    """
    # Auto-detect path if not specified
    if index_path is None:
        # Try standard naming patterns
        candidates = [
            GAME_INDEX_DIR / f"{league_code}_{season.replace('-', '_')}.csv",
            GAME_INDEX_DIR / f"{league_code.lower()}_{season.replace('-', '_')}.csv",
            GAME_INDEX_DIR / f"{league_code}_{season}.csv",
            GAME_INDEX_DIR / f"{league_code.lower()}_{season}.csv",
        ]

        for candidate in candidates:
            if candidate.exists():
                index_path = candidate
                break

        if index_path is None:
            logger.warning(
                f"{league_code} game index not found for season {season}. Checked:\n"
                + "\n".join(f"  - {c}" for c in candidates)
                + f"\n\nCreate game index at: {candidates[0]}\n"
                "Format: LEAGUE,SEASON,GAME_ID,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE"
            )
            return pd.DataFrame(
                columns=[
                    "LEAGUE",
                    "SEASON",
                    "GAME_ID",
                    "GAME_DATE",
                    "HOME_TEAM",
                    "AWAY_TEAM",
                    "HOME_SCORE",
                    "AWAY_SCORE",
                ]
            )

    if not index_path.exists():
        logger.warning(f"{league_code} game index not found: {index_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(index_path)

        # Standardize column names (case-insensitive)
        df.columns = pd.Index([col.upper() for col in df.columns])

        # Convert GAME_DATE to datetime
        if "GAME_DATE" in df.columns:
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

        # Ensure required columns exist
        required_cols = ["GAME_ID", "HOME_TEAM", "AWAY_TEAM"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            logger.error(f"Game index missing required columns: {missing}")
            return pd.DataFrame()

        # Add standard columns
        if "LEAGUE" not in df.columns:
            df["LEAGUE"] = league_code
        if "SEASON" not in df.columns:
            df["SEASON"] = season

        logger.info(f"Loaded {len(df)} games from {league_code} game index ({index_path.name})")

        # Validate
        is_valid, issues = validate_schedule(df, league_code, season, strict=False)
        if not is_valid:
            logger.warning(
                "Game index validation issues:\n" + "\n".join(f"  - {i}" for i in issues)
            )

        return df

    except Exception as e:
        logger.error(f"Failed to load {league_code} game index: {e}")
        return pd.DataFrame()


def get_new_games(
    league_code: str,
    season: str,
    existing_game_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Get games from index that aren't in existing dataset (for incremental updates)

    Args:
        league_code: FIBA league code
        season: Season string
        existing_game_ids: Set of game IDs already scraped

    Returns:
        DataFrame with only new games

    Example:
        >>> existing_ids = set(existing_df["GAME_ID"].unique())
        >>> new_games = get_new_games("LKL", "2023-24", existing_ids)
        >>> print(f"Need to scrape {len(new_games)} new games")
    """
    all_games = load_fiba_game_index(league_code, season)

    if existing_game_ids is None:
        return all_games

    if all_games.empty:
        return all_games

    new_games = all_games[~all_games["GAME_ID"].isin(existing_game_ids)]
    logger.info(f"Found {len(new_games)} new games (out of {len(all_games)} total)")

    return new_games


# ==============================================================================
# HTML Fetching with Retry & Rate Limiting
# ==============================================================================


@with_retry(max_attempts=3, base_delay=2.0)
def _fetch_fiba_html(league_code: str, game_id: str, page_type: str = "bs") -> str:
    """Fetch FIBA LiveStats HTML page with retry logic

    Args:
        league_code: FIBA league code (e.g., "LKL")
        game_id: FIBA game ID
        page_type: Page type ("bs" for box score, "pbp" for play-by-play)

    Returns:
        HTML content as string

    Raises:
        requests.HTTPError: If page not found or server error
    """
    if not HTML_PARSING_AVAILABLE:
        raise ImportError("requests and beautifulsoup4 required for HTML scraping")

    url = f"{FIBA_BASE_URL}/u/{league_code}/{game_id}/{page_type}.html"

    rate_limiter.acquire("fiba_livestats")

    logger.debug(f"Fetching FIBA {page_type}: {league_code} game {game_id}")

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.text


# ==============================================================================
# HTML Parsing Helpers (from NZ-NBL pattern)
# ==============================================================================


def _safe_int(value: str, default: int = 0) -> int:
    """Safely convert string to int, returning default if invalid"""
    try:
        # Remove any non-digit characters except minus
        cleaned = "".join(c for c in str(value) if c.isdigit() or c == "-")
        return int(cleaned) if cleaned else default
    except (ValueError, TypeError):
        return default


def _parse_made_attempted(text: str) -> tuple[int, int]:
    """Parse 'made-attempted' format (e.g., '5-10' or '5/10')

    Args:
        text: String in format "made-attempted" or "made/attempted"

    Returns:
        Tuple of (made, attempted)
    """
    try:
        # Handle both '-' and '/' separators
        if "-" in text:
            parts = text.split("-")
        elif "/" in text:
            parts = text.split("/")
        else:
            return 0, 0

        if len(parts) == 2:
            made = _safe_int(parts[0])
            attempted = _safe_int(parts[1])
            return made, attempted
    except Exception:
        pass

    return 0, 0


def _parse_fiba_html_table(soup: BeautifulSoup, team_name: str) -> list[dict[str, Any]]:
    """Parse FIBA LiveStats HTML table to extract player stats

    Args:
        soup: BeautifulSoup object of the page
        team_name: Team name to filter by

    Returns:
        List of player stat dictionaries
    """
    players = []

    # FIBA LiveStats typically uses tables with class "teamBoxscore"
    tables = soup.find_all("table", class_="teamBoxscore")

    for table in tables:
        # Check if this is the right team's table
        team_header = table.find_previous("h2")
        if team_header and team_name.lower() not in team_header.text.lower():
            continue

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 10:  # Need at least basic stats
                continue

            try:
                # Extract player info and stats
                # Typical FIBA order: Player, MIN, PTS, 2PM-A, 3PM-A, FTM-A, OREB, DREB, REB, AST, STL, BLK, TO, PF
                player_cell = cells[0]
                player_name = player_cell.get_text(strip=True)

                # Skip totals/header rows
                if player_name.lower() in ["totals", "team", "player", ""]:
                    continue

                player_stat = {
                    "PLAYER_NAME": player_name,
                    "TEAM": team_name,
                    "MIN": _safe_int(cells[1].get_text(strip=True)),
                    "PTS": _safe_int(cells[2].get_text(strip=True)),
                }

                # Parse 2P field goals (format: "5-10" or "5/10")
                fg2_text = cells[3].get_text(strip=True) if len(cells) > 3 else "0-0"
                fg2m, fg2a = _parse_made_attempted(fg2_text)

                # Parse 3P field goals
                fg3_text = cells[4].get_text(strip=True) if len(cells) > 4 else "0-0"
                fg3m, fg3a = _parse_made_attempted(fg3_text)

                # Parse free throws
                ft_text = cells[5].get_text(strip=True) if len(cells) > 5 else "0-0"
                ftm, fta = _parse_made_attempted(ft_text)

                # Calculate total field goals
                player_stat.update(
                    {
                        "FGM": fg2m + fg3m,
                        "FGA": fg2a + fg3a,
                        "FG3M": fg3m,
                        "FG3A": fg3a,
                        "FTM": ftm,
                        "FTA": fta,
                    }
                )

                # Rebounds and other stats
                if len(cells) > 8:
                    player_stat["OREB"] = _safe_int(cells[6].get_text(strip=True))
                    player_stat["DREB"] = _safe_int(cells[7].get_text(strip=True))
                    player_stat["REB"] = _safe_int(cells[8].get_text(strip=True))
                if len(cells) > 9:
                    player_stat["AST"] = _safe_int(cells[9].get_text(strip=True))
                if len(cells) > 10:
                    player_stat["STL"] = _safe_int(cells[10].get_text(strip=True))
                if len(cells) > 11:
                    player_stat["BLK"] = _safe_int(cells[11].get_text(strip=True))
                if len(cells) > 12:
                    player_stat["TOV"] = _safe_int(cells[12].get_text(strip=True))
                if len(cells) > 13:
                    player_stat["PF"] = _safe_int(cells[13].get_text(strip=True))

                players.append(player_stat)

            except Exception as e:
                logger.debug(f"Error parsing player row: {e}")
                continue

    return players


# ==============================================================================
# Public Scraping Functions
# ==============================================================================


@with_cache(lambda league_code, game_id, **kwargs: f"{league_code}_{game_id}_bs")
def scrape_fiba_box_score(
    league_code: str,
    game_id: str,
    league: str | None = None,
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Scrape box score from FIBA LiveStats HTML (with caching)

    Args:
        league_code: FIBA league code (e.g., "LKL", "BAL", "NZN")
        game_id: FIBA game ID
        league: Optional standardized league name (for validation)
        season: Optional season string (for validation)
        force_refresh: If True, ignore cache and re-scrape

    Returns:
        DataFrame with player box scores

    Columns:
        - PLAYER_NAME, TEAM, MIN, PTS, FGM, FGA, FG3M, FG3A, FTM, FTA,
          REB, OREB, DREB, AST, STL, BLK, TOV, PF
        Plus calculated percentages: FG_PCT, FG3_PCT, FT_PCT

    Example:
        >>> df = scrape_fiba_box_score("LKL", "123456", league="LKL", season="2023-24")
        >>> print(f"Scraped {len(df)} player records")
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    try:
        html = _fetch_fiba_html(league_code, game_id, "bs")
        soup = BeautifulSoup(html, "html.parser")

        # Extract team names from page
        team_headers = soup.find_all("h2", class_="teamName")
        if len(team_headers) < 2:
            logger.warning(f"Could not find team names for {league_code} game {game_id}")
            return pd.DataFrame()

        team1_name = team_headers[0].get_text(strip=True)
        team2_name = team_headers[1].get_text(strip=True)

        # Parse both teams
        all_players = []
        all_players.extend(_parse_fiba_html_table(soup, team1_name))
        all_players.extend(_parse_fiba_html_table(soup, team2_name))

        if not all_players:
            logger.warning(f"No player stats found for {league_code} game {game_id}")
            return pd.DataFrame()

        df = pd.DataFrame(all_players)

        # Calculate percentages
        if "FGM" in df.columns and "FGA" in df.columns:
            df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)
        if "FG3M" in df.columns and "FG3A" in df.columns:
            df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)
        if "FTM" in df.columns and "FTA" in df.columns:
            df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

        # Add game context
        df["GAME_ID"] = game_id

        # Add league/season if provided
        if league:
            df["LEAGUE"] = league
        if season:
            df["SEASON"] = season

        # Ensure standard columns
        if league and season:
            df = ensure_standard_columns(df, "player_game", league, season)

        # Validate
        if league and season:
            is_valid, issues = validate_player_game(df, league, season, strict=False)
            if not is_valid:
                logger.warning(
                    "Scraped data validation issues:\n" + "\n".join(f"  - {i}" for i in issues)
                )

        logger.info(f"Scraped {len(df)} player records for {league_code} game {game_id}")
        return df

    except Exception as e:
        logger.error(f"Failed to scrape box score for {league_code} game {game_id}: {e}")
        return pd.DataFrame()


def _classify_event_type(description: str) -> str:
    """Classify event type from description text

    Args:
        description: Event description text

    Returns:
        Event type string
    """
    desc_lower = description.lower()

    if "3pt" in desc_lower or "three point" in desc_lower or "3-pt" in desc_lower:
        return "3PT_SHOT"
    elif "2pt" in desc_lower or "two point" in desc_lower or "2-pt" in desc_lower:
        return "2PT_SHOT"
    elif "free throw" in desc_lower or "foul shot" in desc_lower:
        return "FREE_THROW"
    elif "rebound" in desc_lower:
        return "REBOUND"
    elif "assist" in desc_lower:
        return "ASSIST"
    elif "steal" in desc_lower:
        return "STEAL"
    elif "block" in desc_lower:
        return "BLOCK"
    elif "turnover" in desc_lower:
        return "TURNOVER"
    elif "foul" in desc_lower:
        return "FOUL"
    elif "substitution" in desc_lower or "sub in" in desc_lower or "sub out" in desc_lower:
        return "SUBSTITUTION"
    elif "timeout" in desc_lower:
        return "TIMEOUT"
    elif "jump ball" in desc_lower:
        return "JUMP_BALL"
    else:
        return "OTHER"


def _parse_fiba_pbp_table(soup: Any, period: int) -> list[dict[str, Any]]:
    """Parse FIBA LiveStats play-by-play HTML table for a period

    Args:
        soup: BeautifulSoup object or Tag of the period section
        period: Quarter/period number

    Returns:
        List of event dictionaries
    """
    events = []

    # Find play-by-play rows (typically in table with class "pbp")
    rows = soup.find_all("tr", class_=["pbpRow", "row"])

    event_num = 1
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        try:
            # Typical structure: Time | Team/Player/Action | Score
            clock = cells[0].get_text(strip=True)

            # Middle cell contains team, player, and action
            middle_cell = cells[1]
            description = middle_cell.get_text(strip=True)

            # Try to extract team and player from description
            team = ""
            player = ""
            if " - " in description:
                parts = description.split(" - ", 1)
                team = parts[0].strip()
                player_action = parts[1] if len(parts) > 1 else ""
                # Try to extract player name (usually before the action verb)
                if ":" in player_action:
                    player = player_action.split(":")[0].strip()

            # Score (format: "XX-YY")
            score_text = cells[2].get_text(strip=True) if len(cells) > 2 else "0-0"
            score_parts = score_text.split("-") if "-" in score_text else ["0", "0"]
            score_home = _safe_int(score_parts[0]) if len(score_parts) > 0 else 0
            score_away = _safe_int(score_parts[1]) if len(score_parts) > 1 else 0

            # Determine event type from description keywords
            event_type = _classify_event_type(description)

            events.append(
                {
                    "EVENT_NUM": event_num,
                    "PERIOD": period,
                    "CLOCK": clock,
                    "TEAM": team,
                    "PLAYER": player,
                    "EVENT_TYPE": event_type,
                    "DESCRIPTION": description,
                    "SCORE_HOME": score_home,
                    "SCORE_AWAY": score_away,
                }
            )

            event_num += 1

        except Exception as e:
            logger.debug(f"Error parsing pbp row: {e}")
            continue

    return events


@with_cache(lambda league_code, game_id, **kwargs: f"{league_code}_{game_id}_pbp")
def scrape_fiba_play_by_play(
    league_code: str,
    game_id: str,
    league: str | None = None,
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Scrape play-by-play from FIBA LiveStats HTML (with caching)

    Args:
        league_code: FIBA league code (e.g., "LKL", "BAL", "NZN")
        game_id: FIBA game ID
        league: Optional standardized league name
        season: Optional season string
        force_refresh: If True, ignore cache and re-scrape

    Returns:
        DataFrame with play-by-play events

    Columns:
        - EVENT_NUM, PERIOD, CLOCK, TEAM, PLAYER, EVENT_TYPE,
          DESCRIPTION, SCORE_HOME, SCORE_AWAY

    Example:
        >>> df = scrape_fiba_play_by_play("LKL", "123456", league="LKL", season="2023-24")
        >>> print(f"Scraped {len(df)} events")
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    try:
        html = _fetch_fiba_html(league_code, game_id, "pbp")
        soup = BeautifulSoup(html, "html.parser")

        # FIBA typically organizes PBP by quarters
        # Look for quarter sections (Q1, Q2, Q3, Q4, OT)
        all_events = []

        # Try to find quarter headers and their associated tables
        quarter_headers = soup.find_all(["h3", "h4"], class_=["quarter", "period"])

        if not quarter_headers:
            # Fallback: try parsing all tables as one big list
            logger.debug(
                f"No quarter headers found for {league_code} game {game_id}, attempting single table parse"
            )
            events = _parse_fiba_pbp_table(soup, period=1)
            all_events.extend(events)
        else:
            # Parse each quarter separately
            for i, header in enumerate(quarter_headers, start=1):
                period = i
                # Find the table following this header
                table_section = header.find_next("table")
                if table_section:
                    events = _parse_fiba_pbp_table(table_section, period=period)
                    all_events.extend(events)

        if not all_events:
            logger.warning(f"No PBP events found for {league_code} game {game_id}")
            return pd.DataFrame()

        df = pd.DataFrame(all_events)

        # Add game context
        df["GAME_ID"] = game_id

        # Add league/season if provided
        if league:
            df["LEAGUE"] = league
        if season:
            df["SEASON"] = season

        # Ensure standard columns
        if league and season:
            df = ensure_standard_columns(df, "pbp", league, season)

        logger.info(f"Scraped {len(df)} PBP events for {league_code} game {game_id}")
        return df

    except Exception as e:
        logger.error(f"Failed to scrape PBP for {league_code} game {game_id}: {e}")
        return pd.DataFrame()


# ==============================================================================
# Schedule Building from HTML (NEW)
# ==============================================================================


def build_fiba_schedule_from_html(
    league_code: str,
    season: str,
    schedule_url: str,
) -> pd.DataFrame:
    """Build FIBA league schedule by scraping league website HTML.

    Extracts game IDs from fibalivestats.dcd.shared.geniussports.com links
    embedded in league schedule pages. This eliminates the need for manually
    created game index CSV files.

    Args:
        league_code: FIBA league code (e.g., "BCL", "BAL", "ABA", "LKL")
        season: Season string (e.g., "2023-24")
        schedule_url: URL of league schedule page (e.g., "https://www.championsleague.basketball/schedule")

    Returns:
        DataFrame with schedule information including GAME_ID, GAME_DATE,
        HOME_TEAM, AWAY_TEAM, and other metadata

    Example:
        >>> df = build_fiba_schedule_from_html("BCL", "2023-24", "https://www.championsleague.basketball/schedule")
        >>> print(f"Found {len(df)} games")
        >>> print(df[["GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())

    Note:
        This function is the HTML-only alternative to load_fiba_game_index().
        It automatically discovers game IDs by parsing league websites.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    try:
        from .html_scrapers import scrape_fiba_schedule_page

        logger.info(f"Building {league_code} {season} schedule from HTML: {schedule_url}")

        df = scrape_fiba_schedule_page(
            schedule_url=schedule_url,
            league_code=league_code,
            season=season,
        )

        if df.empty:
            logger.warning(f"No games found at {schedule_url}")
            logger.warning("This could mean:")
            logger.warning("  1. Schedule page structure changed")
            logger.warning("  2. Wrong URL for this season")
            logger.warning("  3. Season hasn't started yet")
            return df

        # Add standardized columns
        df["LEAGUE"] = league_code
        df["SEASON"] = season

        # Ensure required columns exist
        if "FIBA_COMPETITION" not in df.columns:
            df["FIBA_COMPETITION"] = league_code

        if "FIBA_PHASE" not in df.columns:
            df["FIBA_PHASE"] = "RS"  # Default to Regular Season

        # Ensure standard column format
        df = ensure_standard_columns(df, "schedule", league_code, season)

        logger.info(f"Built schedule with {len(df)} games for {league_code} {season}")
        logger.info(f"  Game ID range: {df['GAME_ID'].min()} to {df['GAME_ID'].max()}")

        return df

    except ImportError:
        logger.error("html_scrapers module not found. Ensure src/cbb_data/fetchers/html_scrapers.py exists.")
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Failed to build schedule from HTML for {league_code} {season}: {e}")
        return pd.DataFrame()


# ==============================================================================
# Shot Chart Scraping from HTML (NEW)
# ==============================================================================


@with_cache(lambda league_code, game_id, **kwargs: f"{league_code}_{game_id}_shots")
def scrape_fiba_shots(
    league_code: str,
    game_id: str | int,
    league: str | None = None,
    season: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Scrape shot chart data from FIBA LiveStats HTML pages.

    Extracts shot events with X/Y coordinates from FIBA LiveStats shot chart pages.
    Uses multiple extraction strategies:
    1. JSON embedded in <script> tags (most common)
    2. HTML elements with data-x, data-y attributes (fallback)

    Args:
        league_code: FIBA league code (e.g., "BCL", "BAL", "ABA", "LKL")
        game_id: FIBA game ID
        league: Optional standardized league name
        season: Optional season string
        force_refresh: If True, ignore cache and re-scrape

    Returns:
        DataFrame with shot events including X, Y coordinates, SHOT_TYPE,
        SHOT_RESULT (MADE/MISSED), PLAYER_NAME, TEAM, PERIOD, CLOCK

    Columns:
        - GAME_ID, PERIOD, CLOCK, TEAM, PLAYER_NAME
        - SHOT_TYPE: "2PT" or "3PT"
        - SHOT_RESULT: "MADE" or "MISSED"
        - X, Y: Coordinates (0-100 scale)
        - DESCRIPTION: Shot description

    Example:
        >>> df = scrape_fiba_shots("BCL", "123456", league="BCL", season="2023-24")
        >>> made_shots = df[df['SHOT_RESULT'] == 'MADE']
        >>> print(f"FG%: {len(made_shots) / len(df) * 100:.1f}%")

    Note:
        - Returns empty DataFrame if shot data not available
        - Coordinates are normalized to 0-100 scale
        - This is the HTML-only alternative to JSON API shot extraction
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    try:
        from .html_scrapers import scrape_fiba_shot_chart_html

        logger.debug(f"Scraping shots for {league_code} game {game_id}")

        df = scrape_fiba_shot_chart_html(
            league_code=league_code,
            game_id=int(game_id),
        )

        if df.empty:
            logger.debug(f"No shot data found for {league_code} game {game_id}")
            return df

        # Add game context
        df["GAME_ID"] = str(game_id)

        if league:
            df["LEAGUE"] = league
        if season:
            df["SEASON"] = season

        # Ensure standard columns
        if league and season:
            df = ensure_standard_columns(df, "shots", league, season)

        logger.debug(f"Scraped {len(df)} shots for {league_code} game {game_id}")
        return df

    except ImportError:
        logger.error("html_scrapers module not found. Ensure src/cbb_data/fetchers/html_scrapers.py exists.")
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Failed to scrape shots for {league_code} game {game_id}: {e}")
        return pd.DataFrame()


# ============================================================================
# OPTIONAL FIBA UPGRADES - Advanced Analytics Layers
# ============================================================================


def build_lineup_game_from_pbp(
    pbp_df: pd.DataFrame,
    league: str,
    season: str
) -> pd.DataFrame:
    """Build lineup-game stats from play-by-play substitution events

    **OPTIONAL UPGRADE** - Derive on-court lineup combinations from PBP data.

    This function reconstructs which 5 players were on the court for each team
    during each possession/segment, enabling advanced lineup analytics like:
    - Net rating by lineup combination
    - Plus/minus for specific 5-man units
    - Optimal lineup discovery
    - Rotation pattern analysis

    **Algorithm**:
    1. Parse substitution events from PBP (SUB_IN, SUB_OUT)
    2. Track current 5-man lineup for each team
    3. Calculate stats for each lineup "stint" (time between substitutions)
    4. Aggregate: Points scored/allowed, possessions, plus/minus, minutes

    Args:
        pbp_df: Play-by-play DataFrame with columns:
            - GAME_ID: Game identifier
            - PERIOD: Quarter/period (1-4, OT, etc.)
            - GAME_CLOCK: Time remaining in period
            - ACTION_TYPE: "substitution", "made_shot", etc.
            - PLAYER_ID: Player performing action
            - TEAM_ID: Team performing action
            - SCORE_HOME, SCORE_AWAY: Running scores
        league: League identifier (e.g., "BCL")
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with lineup-game stats:
            - GAME_ID: Game identifier
            - TEAM_ID: Team identifier
            - LINEUP_ID: Hash of 5 player IDs (sorted)
            - PLAYER_1_ID, PLAYER_2_ID, ..., PLAYER_5_ID: Player IDs
            - PLAYER_1_NAME, PLAYER_2_NAME, ..., PLAYER_5_NAME: Player names
            - MIN: Minutes played by this lineup
            - PTS_FOR: Points scored while lineup on court
            - PTS_AGAINST: Points allowed while lineup on court
            - PLUS_MINUS: PTS_FOR - PTS_AGAINST
            - POSS: Possessions (estimated)
            - LEAGUE: League string
            - SEASON: Season string

    Example:
        >>> from src.cbb_data.fetchers.bcl import fetch_bcl_pbp
        >>> from src.cbb_data.fetchers.fiba_html_common import build_lineup_game_from_pbp
        >>>
        >>> # Fetch PBP for BCL season
        >>> pbp = fetch_bcp_pbp("2023-24")
        >>>
        >>> # Build lineup stats
        >>> lineup_game = build_lineup_game_from_pbp(pbp, "BCL", "2023-24")
        >>>
        >>> # Find best 5-man units by plus/minus
        >>> top_lineups = lineup_game.nlargest(10, "PLUS_MINUS")
        >>> print(top_lineups[["LINEUP_ID", "MIN", "PLUS_MINUS"]])

    Note:
        - Requires clean PBP data with substitution events
        - Starting lineups inferred from first events (may be incomplete)
        - Minutes calculated from game clock timestamps
        - Possessions estimated from scoring plays (not exact)

    See Also:
        - extract_roster_from_boxscore(): Get full team rosters
        - validate_lineup_totals(): QA helper for lineup data
    """
    logger.info("Building lineup-game stats from PBP data (OPTIONAL UPGRADE)")

    if pbp_df.empty:
        logger.warning("Empty PBP DataFrame, cannot build lineups")
        return pd.DataFrame()

    # Validate required columns
    required_cols = ["GAME_ID", "PERIOD", "ACTION_TYPE", "TEAM_ID", "PLAYER_ID"]
    missing_cols = [col for col in required_cols if col not in pbp_df.columns]

    if missing_cols:
        logger.error(f"PBP missing required columns for lineup building: {missing_cols}")
        return pd.DataFrame()

    # ======================================================================
    # PARTIAL IMPLEMENTATION - Detailed skeleton with TODOs
    # ======================================================================
    # This is a complex feature. Below is a detailed implementation guide
    # with helper function stubs and algorithm steps marked with TODOs.
    #
    # Future implementer: Follow the steps below, test each section,
    # and gradually remove TODO markers as you complete each part.
    # ======================================================================

    logger.warning(
        "build_lineup_game_from_pbp() is partially implemented with detailed TODOs. "
        "This is a complex feature requiring careful testing. "
        "Returning empty DataFrame for now."
    )

    # ===== HELPER FUNCTIONS (Stubs - TODO: Implement) =====

    def parse_substitution_events(pbp_sub_df):
        """
        Parse substitution events into IN/OUT pairs.

        TODO: Implement logic to:
        1. Filter PBP for ACTION_TYPE containing 'substitution' or 'sub'
        2. Parse DESCRIPTION for player IN/OUT (varies by source)
        3. Return DataFrame with columns: GAME_ID, PERIOD, TIME, TEAM_ID, PLAYER_IN_ID, PLAYER_OUT_ID

        Test case:
        Input: DESCRIPTION = "Player A substitutes Player B"
        Output: PLAYER_IN_ID = "A", PLAYER_OUT_ID = "B"
        """
        # TODO: Implement substitution parsing
        logger.debug("Parsing substitution events (TODO)")
        return pd.DataFrame()

    def infer_starting_lineups(pbp_df, game_id, team_id):
        """
        Infer starting lineup from first few events.

        TODO: Implement logic to:
        1. Get first events for this game/team (before first substitution)
        2. Extract unique PLAYER_IDs from those events
        3. Validate we have exactly 5 players (warn if not)
        4. Return list of 5 PLAYER_IDs

        Fallback: If < 5 players detected, return empty list (incomplete data)
        """
        # TODO: Implement starting lineup inference
        logger.debug(f"Inferring starting lineup for game {game_id}, team {team_id} (TODO)")
        return []

    def track_lineup_changes(game_pbp, subs_df):
        """
        Track lineup state changes throughout game.

        TODO: Implement logic to:
        1. Start with inferred starting lineup
        2. Process substitutions chronologically
        3. Update lineup state at each sub (remove OUT, add IN)
        4. Validate 5 players at all times
        5. Return list of lineup "stints" with start/end times

        Data structure: List[Dict] with keys:
        - lineup_players: List[player_id] (5 players)
        - start_time: Timestamp
        - end_time: Timestamp
        - start_score_home: int
        - start_score_away: int
        """
        # TODO: Implement lineup state tracking
        logger.debug("Tracking lineup changes (TODO)")
        return []

    def aggregate_stint_stats(stint, pbp_df):
        """
        Aggregate stats for a single lineup stint.

        TODO: Implement logic to:
        1. Filter PBP events during stint time window
        2. Calculate:
           - Minutes played (end_time - start_time)
           - Points scored (score delta)
           - Points allowed (opponent score delta)
           - Plus/minus
           - Possessions (estimate from events)
        3. Return Dict with stint stats

        Possession estimation heuristics:
        - FGM/FGA = possession end
        - Turnover = possession end
        - Defensive rebound = possession change
        """
        # TODO: Implement stint aggregation
        logger.debug("Aggregating stint stats (TODO)")
        return {}

    def calculate_lineup_id(player_ids):
        """
        Generate unique lineup ID from player IDs.

        TODO: Implement logic to:
        1. Sort player IDs (consistent ordering)
        2. Hash sorted list (MD5 or simple concatenation)
        3. Return lineup_id string

        Example:
        Input: ["P123", "P456", "P789", "P012", "P345"]
        Output: "P012_P123_P345_P456_P789" (sorted concatenation)
        """
        # TODO: Implement lineup ID generation
        if not player_ids or len(player_ids) != 5:
            return None
        # Simple implementation: sorted concatenation
        return "_".join(sorted(player_ids))

    # ===== ALGORITHM IMPLEMENTATION (TODOs) =====

    # TODO STEP 1: Parse all substitution events
    # subs_df = parse_substitution_events(pbp_df)
    # if subs_df.empty:
    #     logger.warning("No substitution events found in PBP")
    #     # Could still build lineups from first 5 players per team
    #     pass

    # TODO STEP 2: Group PBP by game and team
    # lineup_stints = []
    # for (game_id, team_id), game_team_pbp in pbp_df.groupby(['GAME_ID', 'TEAM_ID']):
    #     logger.debug(f"Processing game {game_id}, team {team_id}")
    #
    #     # TODO STEP 3: Infer starting lineup
    #     starting_five = infer_starting_lineups(pbp_df, game_id, team_id)
    #     if len(starting_five) != 5:
    #         logger.warning(f"Could not infer 5 starters for {game_id}/{team_id}, skipping")
    #         continue
    #
    #     # TODO STEP 4: Track lineup changes
    #     game_subs = subs_df[(subs_df['GAME_ID'] == game_id) & (subs_df['TEAM_ID'] == team_id)]
    #     stints = track_lineup_changes(game_team_pbp, game_subs)
    #
    #     # TODO STEP 5: Aggregate stats for each stint
    #     for stint in stints:
    #         stint_stats = aggregate_stint_stats(stint, game_team_pbp)
    #         stint_stats['GAME_ID'] = game_id
    #         stint_stats['TEAM_ID'] = team_id
    #         stint_stats['LINEUP_ID'] = calculate_lineup_id(stint['lineup_players'])
    #         stint_stats['LEAGUE'] = league
    #         stint_stats['SEASON'] = season
    #         lineup_stints.append(stint_stats)

    # TODO STEP 6: Aggregate stints to lineup-game level
    # Multiple stints may have same lineup in different periods
    # Group by (GAME_ID, TEAM_ID, LINEUP_ID) and sum stats
    # lineup_df = pd.DataFrame(lineup_stints)
    # if not lineup_df.empty:
    #     agg_cols = ['GAME_ID', 'TEAM_ID', 'LINEUP_ID', 'LEAGUE', 'SEASON']
    #     stat_cols = ['MIN', 'PTS_FOR', 'PTS_AGAINST', 'PLUS_MINUS', 'POSS']
    #     lineup_game_df = lineup_df.groupby(agg_cols)[stat_cols].sum().reset_index()
    #
    #     # TODO STEP 7: Add player names (join from roster or PBP)
    #     # Expand LINEUP_ID back to PLAYER_1_ID...PLAYER_5_ID columns
    #     # Join with player names
    #
    #     logger.info(f"Built {len(lineup_game_df)} lineup-game records")
    #     return lineup_game_df

    # TODO STEP 8: Validation (uncomment when implemented)
    # if not lineup_df.empty:
    #     # Validate: Sum of lineup minutes should = game minutes (48 min regulation)
    #     game_totals = lineup_df.groupby('GAME_ID')['MIN'].sum()
    #     games_with_wrong_total = (game_totals < 45) | (game_totals > 60)  # Allow OT
    #     if games_with_wrong_total.any():
    #         logger.warning(f"{games_with_wrong_total.sum()} games have incorrect total minutes")
    #
    #     # Validate: Each lineup has exactly 5 unique players
    #     # (Check via LINEUP_ID split)

    # For now, return empty DataFrame with correct schema

    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "TEAM_ID",
            "LINEUP_ID",
            "PLAYER_1_ID", "PLAYER_2_ID", "PLAYER_3_ID", "PLAYER_4_ID", "PLAYER_5_ID",
            "PLAYER_1_NAME", "PLAYER_2_NAME", "PLAYER_3_NAME", "PLAYER_4_NAME", "PLAYER_5_NAME",
            "MIN",
            "PTS_FOR",
            "PTS_AGAINST",
            "PLUS_MINUS",
            "POSS",
            "LEAGUE",
            "SEASON",
        ]
    )


def extract_roster_from_boxscore(
    player_game_df: pd.DataFrame,
    league: str,
    season: str
) -> pd.DataFrame:
    """Extract team rosters and player bio from player_game data

    **OPTIONAL UPGRADE** - Build roster/player bio layer from box score data.

    This function extracts unique player-team combinations across all games,
    providing a "roster" or "player bio" layer useful for:
    - Player directory/lookup (name, team, position)
    - Roster composition analysis
    - Player movement tracking (trades/transfers)
    - Team size validation (12-15 players typical)

    **Algorithm**:
    1. Group player_game by (PLAYER_ID, TEAM_ID)
    2. Take first/most frequent values for bio fields
    3. Count games played (GP)
    4. Calculate first/last game dates
    5. Deduplicate to single row per player-team

    Args:
        player_game_df: Player game DataFrame with columns:
            - PLAYER_ID: Unique player identifier
            - PLAYER_NAME: Player name
            - TEAM_ID: Team identifier
            - TEAM_NAME: Team name
            - POSITION: Position (if available)
            - JERSEY_NUMBER: Jersey # (if available)
            - GAME_DATE: Game date (if available)
        league: League identifier (e.g., "BCL")
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with player-team roster:
            - PLAYER_ID: Unique player identifier
            - PLAYER_NAME: Player name (most common spelling)
            - TEAM_ID: Team identifier
            - TEAM_NAME: Team name (most common)
            - POSITION: Position (if available)
            - JERSEY_NUMBER: Jersey # (if available)
            - GP: Games played for this team
            - FIRST_GAME: Date of first game (if available)
            - LAST_GAME: Date of last game (if available)
            - LEAGUE: League string
            - SEASON: Season string

    Example:
        >>> from src.cbb_data.fetchers.bcl import fetch_bcl_player_game
        >>> from src.cbb_data.fetchers.fiba_html_common import extract_roster_from_boxscore
        >>>
        >>> # Fetch player game data
        >>> player_game = fetch_bcl_player_game("2023-24")
        >>>
        >>> # Extract rosters
        >>> rosters = extract_roster_from_boxscore(player_game, "BCL", "2023-24")
        >>>
        >>> # Show roster for specific team
        >>> team_roster = rosters[rosters["TEAM_NAME"] == "Unicaja Malaga"]
        >>> print(team_roster[["PLAYER_NAME", "POSITION", "GP"]])

    Note:
        - Bio fields (position, jersey) often missing in FIBA data
        - Player IDs should be consistent across games (validate with QA)
        - Handles mid-season team changes (multiple rows per player)

    See Also:
        - build_lineup_game_from_pbp(): Lineup-level analytics
        - validate_roster_consistency(): QA helper for roster data
    """
    logger.info("Extracting team rosters from player_game data (OPTIONAL UPGRADE)")

    if player_game_df.empty:
        logger.warning("Empty player_game DataFrame, cannot extract rosters")
        return pd.DataFrame()

    # Validate required columns
    required_cols = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID"]
    missing_cols = [col for col in required_cols if col not in player_game_df.columns]

    if missing_cols:
        logger.error(f"player_game missing required columns: {missing_cols}")
        return pd.DataFrame()

    try:
        # Group by player-team combination
        groupby_cols = ["PLAYER_ID", "TEAM_ID"]

        # Build aggregation dictionary
        # Use simple column names that exist in player_game_df
        agg_dict = {
            "PLAYER_NAME": "first",  # Take first occurrence
        }

        # Add optional fields if they exist
        if "TEAM_NAME" in player_game_df.columns:
            agg_dict["TEAM_NAME"] = "first"

        if "POSITION" in player_game_df.columns:
            # Take most common position (mode)
            agg_dict["POSITION"] = lambda x: x.mode()[0] if not x.mode().empty else None

        if "JERSEY_NUMBER" in player_game_df.columns:
            agg_dict["JERSEY_NUMBER"] = lambda x: x.mode()[0] if not x.mode().empty else None

        if "GAME_DATE" in player_game_df.columns:
            agg_dict["GAME_DATE"] = ["min", "max"]  # Will create GAME_DATE_min and GAME_DATE_max

        # Perform aggregation
        roster_df = player_game_df.groupby(groupby_cols).agg(agg_dict).reset_index()

        # Flatten multi-level columns if GAME_DATE was aggregated
        if "GAME_DATE" in player_game_df.columns:
            roster_df.columns = [
                f"{col[0]}_{col[1]}" if col[1] else col[0]
                for col in roster_df.columns
            ]
            # Rename GAME_DATE columns
            if "GAME_DATE_min" in roster_df.columns:
                roster_df.rename(columns={"GAME_DATE_min": "FIRST_GAME"}, inplace=True)
            if "GAME_DATE_max" in roster_df.columns:
                roster_df.rename(columns={"GAME_DATE_max": "LAST_GAME"}, inplace=True)

        # Count games played (number of rows per player-team combo)
        gp_counts = player_game_df.groupby(groupby_cols).size().reset_index(name="GP")
        roster_df = roster_df.merge(gp_counts, on=groupby_cols, how="left")

        # Add league and season
        roster_df["LEAGUE"] = league
        roster_df["SEASON"] = season

        logger.info(f"Extracted {len(roster_df)} player-team roster entries")
        return roster_df

    except Exception as e:
        logger.error(f"Failed to extract roster from player_game: {e}")
        return pd.DataFrame()
