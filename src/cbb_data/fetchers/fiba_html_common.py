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
- shots: ✅ Via HTML/JSON shot chart scraping (may require browser rendering)
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
# Shot Chart Debug Infrastructure
# ==============================================================================


def save_fiba_html_debug(
    league_code: str,
    season: str,
    game_id: str,
    html_sc: str,
    html_shotchart: str,
    html_shots: str,
    root_dir: Path | None = None,
) -> Path:
    """Save raw HTML from FIBA LiveStats pages for debugging

    This is debug-only infrastructure to inspect what FIBA actually returns
    for sc.html / shotchart.html / shots.html when parsing fails.

    The directory structure is:
        data/raw/fiba/debug/<LEAGUE>/<season>/<GAME_ID>/{sc,shotchart,shots}.html

    Args:
        league_code: FIBA league code (e.g., "LKL", "ABA")
        season: Season string (e.g., "2023-24")
        game_id: FIBA game ID
        html_sc: HTML content from sc.html endpoint
        html_shotchart: HTML content from shotchart.html endpoint
        html_shots: HTML content from shots.html endpoint
        root_dir: Optional custom root directory (default: data/raw/fiba/debug)

    Returns:
        Path to directory where files were written

    Example:
        >>> save_fiba_html_debug("LKL", "2023-24", "301234", html1, html2, html3)
        PosixPath('data/raw/fiba/debug/LKL/2023-24/301234')
    """
    if root_dir is None:
        root_dir = Path("data") / "raw" / "fiba" / "debug"

    out_dir = root_dir / league_code / season / str(game_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        (out_dir / "sc.html").write_text(html_sc, encoding="utf-8")
        (out_dir / "shotchart.html").write_text(html_shotchart, encoding="utf-8")
        (out_dir / "shots.html").write_text(html_shots, encoding="utf-8")
        logger.warning(
            "Saved FIBA HTML debug files for %s %s game %s at %s",
            league_code,
            season,
            game_id,
            out_dir,
        )
    except Exception as exc:
        logger.error(
            "Failed to write FIBA HTML debug files for %s %s game %s: %s",
            league_code,
            season,
            game_id,
            exc,
        )

    # Also log a short snippet for quick inspection in logs
    logger.debug(
        "FIBA HTML snippets for %s %s game %s:\n"
        "  sc.html      (len=%d) %r\n"
        "  shotchart.html (len=%d) %r\n"
        "  shots.html   (len=%d) %r",
        league_code,
        season,
        game_id,
        len(html_sc),
        html_sc[:200],
        len(html_shotchart),
        html_shotchart[:200],
        len(html_shots),
        html_shots[:200],
    )

    return out_dir


# ==============================================================================
# Shot Chart Scraping
# ==============================================================================


def scrape_fiba_shot_chart(
    league_code: str,
    game_id: str,
    league: str | None = None,
    season: str | None = None,
    use_browser: bool = False,
    debug_html: bool = False,
) -> pd.DataFrame:
    """Scrape shot chart data from FIBA LiveStats

    Attempts multiple methods to retrieve shot chart data:
    1. Try HTML endpoint via HTTP (sc.html, shotchart.html, shots.html)
    2. Try JSON API endpoint
    3. If use_browser=True, use Playwright to render JavaScript

    Args:
        league_code: FIBA league code (e.g., "LKL", "ABA", "BAL", "BCL")
        game_id: FIBA game ID
        league: League name for standardization (e.g., "LKL")
        season: Season string for standardization (e.g., "2023-24")
        use_browser: If True, use Playwright browser rendering (slower but works for JS pages)
        debug_html: If True, dump raw HTML to data/raw/fiba/debug for inspection when no shots found

    Returns:
        DataFrame with shot chart data

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID (if available)
        - PLAYER_NAME: Player name
        - TEAM_CODE: Team code
        - TEAM_NAME: Team name
        - PERIOD: Quarter/period number
        - CLOCK: Game clock (MM:SS)
        - SHOT_X: X coordinate on court
        - SHOT_Y: Y coordinate on court
        - SHOT_TYPE: Shot type (2PT/3PT)
        - SHOT_MADE: Boolean - whether shot was made
        - SHOT_VALUE: Points value (2 or 3)
        - SHOT_DISTANCE: Distance from basket (if available)
        - SHOT_ZONE: Court zone (if available)
        - LEAGUE: League name (if provided)
        - SEASON: Season string (if provided)

    Example:
        >>> # Try simple HTTP first
        >>> shots = scrape_fiba_shot_chart("LKL", "301234", "LKL", "2023-24")
        >>>
        >>> # If blocked, use browser rendering with debug
        >>> shots = scrape_fiba_shot_chart("LKL", "301234", "LKL", "2023-24",
        ...                                 use_browser=True, debug_html=True)

    Note:
        FIBA LiveStats may block simple HTTP requests (403 Forbidden) due to bot protection.
        In such cases, use use_browser=True to render pages with Playwright.
        This requires: uv pip install playwright && playwright install chromium

        Use debug_html=True to save HTML files when parsing fails - helpful for debugging.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing dependencies not available")
        return pd.DataFrame()

    logger.info(f"Fetching {league_code} shot chart: game {game_id}")

    shots = []

    # Storage for debug HTML (captured when use_browser=True)
    html_sc = ""
    html_shotchart = ""
    html_shots = ""

    # Method 1: Try HTML endpoints via HTTP (simple requests)
    if not use_browser:
        for suffix in ["sc", "shotchart", "shots"]:
            try:
                html = _fetch_fiba_html(league_code, game_id, suffix)
                if html:
                    shots_from_html = _parse_fiba_shot_chart_html(html, league_code, game_id)
                    if not shots_from_html.empty:
                        logger.info(f"Found shots in {suffix}.html: {len(shots_from_html)} shots")
                        shots.extend(shots_from_html.to_dict("records"))
                        break
            except Exception as e:
                logger.debug(f"Failed to fetch {suffix}.html via HTTP: {e}")
                continue

    # Method 2: Try JSON API endpoint
    if not shots and not use_browser:
        try:
            json_data = _fetch_fiba_json_api(league_code, game_id, "shots")
            if json_data:
                shots_from_json = _parse_fiba_shot_chart_json(json_data, league_code, game_id)
                if not shots_from_json.empty:
                    logger.info(f"Found shots in JSON API: {len(shots_from_json)} shots")
                    shots.extend(shots_from_json.to_dict("records"))
        except Exception as e:
            logger.debug(f"Failed to fetch JSON API: {e}")

    # Method 3: Use browser rendering (for JS-required pages)
    if use_browser:
        try:
            from .browser_scraper import BrowserScraper

            with BrowserScraper(headless=True, timeout=30000) as scraper:
                # Fetch all three pages to maximize debug info
                for suffix, storage_var in [
                    ("sc", "html_sc"),
                    ("shotchart", "html_shotchart"),
                    ("shots", "html_shots"),
                ]:
                    try:
                        url = f"{FIBA_BASE_URL}/u/{league_code}/{game_id}/{suffix}.html"
                        logger.debug(f"Fetching {url} via browser...")
                        html = scraper.get_rendered_html(url, wait_time=3.0)

                        # Store for debug
                        if suffix == "sc":
                            html_sc = html
                        elif suffix == "shotchart":
                            html_shotchart = html
                        elif suffix == "shots":
                            html_shots = html

                        logger.debug(f"  Retrieved {len(html)} chars from {suffix}.html")

                        if html:
                            shots_from_browser = _parse_fiba_shot_chart_html(html, league_code, game_id)
                            if not shots_from_browser.empty:
                                logger.info(f"Found shots via browser ({suffix}.html): {len(shots_from_browser)} shots")
                                shots.extend(shots_from_browser.to_dict("records"))
                                # Don't break - keep fetching others for debug
                    except Exception as e:
                        logger.debug(f"Browser scraping failed for {suffix}.html: {e}")
                        continue

        except ImportError:
            logger.warning(
                "Browser scraping requested but Playwright not installed. "
                "Install with: uv pip install playwright && playwright install chromium"
            )
        except Exception as e:
            logger.error(f"Browser scraping failed: {e}")

    # Convert to DataFrame
    if not shots:
        logger.warning(f"No shot chart data found for {league_code} game {game_id}")

        # Save debug HTML if requested and we have HTML from browser
        if debug_html and season and use_browser and (html_sc or html_shotchart or html_shots):
            save_fiba_html_debug(
                league_code=league_code,
                season=season,
                game_id=game_id,
                html_sc=html_sc or "(not fetched)",
                html_shotchart=html_shotchart or "(not fetched)",
                html_shots=html_shots or "(not fetched)",
            )
        return pd.DataFrame(
            columns=[
                "GAME_ID",
                "PLAYER_ID",
                "PLAYER_NAME",
                "TEAM_CODE",
                "TEAM_NAME",
                "PERIOD",
                "CLOCK",
                "SHOT_X",
                "SHOT_Y",
                "SHOT_TYPE",
                "SHOT_MADE",
                "SHOT_VALUE",
                "SHOT_DISTANCE",
                "SHOT_ZONE",
                "LEAGUE",
                "SEASON",
            ]
        )

    df = pd.DataFrame(shots)

    # Add game context
    df["GAME_ID"] = game_id

    # Add league/season if provided
    if league:
        df["LEAGUE"] = league
    if season:
        df["SEASON"] = season

    logger.info(f"Scraped {len(df)} shots for {league_code} game {game_id}")
    return df


def _parse_fiba_shot_chart_html(html: str, league_code: str, game_id: str) -> pd.DataFrame:
    """Parse FIBA shot chart HTML to extract shot data

    Looks for:
    - JavaScript variables with shot data (e.g., var shotData = [...])
    - Tables with shot coordinates
    - SVG/Canvas elements with shot markers
    """
    soup = BeautifulSoup(html, "html.parser")
    shots = []

    # Look for JavaScript shot data
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and ("shot" in script.string.lower() or "LOC_X" in script.string or "loc_x" in script.string):
            # Try to extract JSON data from JavaScript
            import re
            import json as json_lib

            # Pattern: var shotData = [{...}, {...}]
            patterns = [
                r'shotData\s*=\s*(\[.*?\])',
                r'shots\s*=\s*(\[.*?\])',
                r'shotChart\s*=\s*(\{.*?\})',
            ]

            for pattern in patterns:
                match = re.search(pattern, script.string, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        shot_data = json_lib.loads(json_str)
                        if isinstance(shot_data, list):
                            shots.extend(shot_data)
                        elif isinstance(shot_data, dict) and "shots" in shot_data:
                            shots.extend(shot_data["shots"])
                    except Exception as e:
                        logger.debug(f"Failed to parse JS shot data: {e}")
                        continue

    # Look for shot tables
    if not shots:
        tables = soup.find_all("table")
        for table in tables:
            # Check if table has shot-related headers
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if any(h.lower() in ["x", "y", "loc_x", "loc_y", "shot", "coordinate"] for h in headers):
                rows = table.find_all("tr")[1:]  # Skip header
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 4:  # Need at least player, x, y, result
                        try:
                            shot = {
                                "PLAYER_NAME": cells[0].get_text(strip=True),
                                "SHOT_X": float(cells[1].get_text(strip=True)),
                                "SHOT_Y": float(cells[2].get_text(strip=True)),
                                "SHOT_MADE": "made" in cells[3].get_text(strip=True).lower(),
                            }
                            shots.append(shot)
                        except Exception:
                            continue

    if not shots:
        return pd.DataFrame()

    # Standardize shot data structure
    standardized_shots = []
    for shot in shots:
        try:
            standardized_shots.append({
                "PLAYER_ID": shot.get("playerId", shot.get("player_id")),
                "PLAYER_NAME": shot.get("playerName", shot.get("player_name", shot.get("PLAYER_NAME"))),
                "TEAM_CODE": shot.get("teamCode", shot.get("team_code", shot.get("TEAM_CODE"))),
                "TEAM_NAME": shot.get("teamName", shot.get("team_name", shot.get("TEAM_NAME"))),
                "PERIOD": shot.get("period", shot.get("quarter", shot.get("PERIOD"))),
                "CLOCK": shot.get("clock", shot.get("time", shot.get("CLOCK"))),
                "SHOT_X": shot.get("x", shot.get("locX", shot.get("LOC_X", shot.get("SHOT_X")))),
                "SHOT_Y": shot.get("y", shot.get("locY", shot.get("LOC_Y", shot.get("SHOT_Y")))),
                "SHOT_TYPE": shot.get("shotType", shot.get("shot_type", shot.get("SHOT_TYPE", "2PT"))),
                "SHOT_MADE": shot.get("made", shot.get("shotMade", shot.get("SHOT_MADE", False))),
                "SHOT_VALUE": shot.get("pointsValue", shot.get("SHOT_VALUE", 2)),
                "SHOT_DISTANCE": shot.get("distance", shot.get("SHOT_DISTANCE")),
                "SHOT_ZONE": shot.get("zone", shot.get("SHOT_ZONE")),
            })
        except Exception as e:
            logger.debug(f"Failed to standardize shot: {e}")
            continue

    return pd.DataFrame(standardized_shots)


def _parse_fiba_shot_chart_json(json_data: dict[str, Any], league_code: str, game_id: str) -> pd.DataFrame:
    """Parse FIBA shot chart JSON API response"""
    shots = []

    # Try to find shots in JSON structure
    if isinstance(json_data, list):
        shots = json_data
    elif "shots" in json_data:
        shots = json_data["shots"]
    elif "data" in json_data and "shots" in json_data["data"]:
        shots = json_data["data"]["shots"]

    if not shots:
        return pd.DataFrame()

    # Use same standardization as HTML parser
    standardized_shots = []
    for shot in shots:
        try:
            standardized_shots.append({
                "PLAYER_ID": shot.get("playerId", shot.get("player_id")),
                "PLAYER_NAME": shot.get("playerName", shot.get("player_name")),
                "TEAM_CODE": shot.get("teamCode", shot.get("team_code")),
                "TEAM_NAME": shot.get("teamName", shot.get("team_name")),
                "PERIOD": shot.get("period", shot.get("quarter")),
                "CLOCK": shot.get("clock", shot.get("time")),
                "SHOT_X": shot.get("x", shot.get("locX", shot.get("LOC_X"))),
                "SHOT_Y": shot.get("y", shot.get("locY", shot.get("LOC_Y"))),
                "SHOT_TYPE": shot.get("shotType", shot.get("shot_type", "2PT")),
                "SHOT_MADE": shot.get("made", shot.get("shotMade", False)),
                "SHOT_VALUE": shot.get("pointsValue", shot.get("points_value", 2)),
                "SHOT_DISTANCE": shot.get("distance"),
                "SHOT_ZONE": shot.get("zone"),
            })
        except Exception as e:
            logger.debug(f"Failed to parse shot from JSON: {e}")
            continue

    return pd.DataFrame(standardized_shots)


def _extract_shots_from_pbp_html(html: str, league_code: str, game_id: str) -> pd.DataFrame:
    """Extract shot data embedded in PBP HTML page"""
    # Similar logic to _parse_fiba_shot_chart_html but looks in PBP context
    return _parse_fiba_shot_chart_html(html, league_code, game_id)


def _fetch_fiba_json_api(league_code: str, game_id: str, endpoint: str) -> dict[str, Any] | None:
    """Fetch data from FIBA LiveStats JSON API

    Note: May return 403 Forbidden if authentication required
    """
    try:
        # Try FIBA API endpoint structure (similar to fiba_livestats_direct.py)
        # Endpoint pattern: /data/{competition}/{season}/data/{game_code}/{endpoint}.json
        # But we don't have season info here, so try simplified endpoint
        url = f"{FIBA_BASE_URL}/data/{league_code}/data/{game_id}/{endpoint}.json"

        rate_limiter.acquire("fiba_livestats")
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            logger.debug(f"JSON API returned {response.status_code} for {url}")
            return None
    except Exception as e:
        logger.debug(f"Failed to fetch JSON API: {e}")
        return None
