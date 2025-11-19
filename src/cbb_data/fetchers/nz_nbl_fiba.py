"""NZ NBL (New Zealand National Basketball League) Fetcher

NZ NBL data via FIBA LiveStats HTML scraping (public pages).
New Zealand's top-tier professional basketball league.

Data Source: FIBA LiveStats public HTML pages
- Box scores: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/[GAME_ID]/bs.html
- Play-by-play: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/[GAME_ID]/pbp.html

League Code: "NZN" (NZ NBL in FIBA LiveStats system)

Data Coverage:
- Schedule: Via nznbl.basketball website scraping (dynamic discovery)
- Player-game box scores: Via FIBA LiveStats HTML scraping
- Team-game box scores: Aggregated from player stats
- Play-by-play: Via FIBA LiveStats HTML scraping (when available)
- Shot charts: Via FIBA LiveStats HTML/JavaScript extraction

Implementation Notes:
- Schedule discovery scrapes https://nznbl.basketball/stats/results/
- Extracts FIBA LiveStats game IDs from embedded URLs
- Uses BeautifulSoup for HTML parsing
- No authentication required (public pages)
- Gracefully handles missing/incomplete data

Dependencies:
- requests: HTTP client
- beautifulsoup4: HTML parsing
- pandas: Data manipulation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)


# Get rate limiter
rate_limiter = get_source_limiter()

# FIBA LiveStats configuration
FIBA_LEAGUE_CODE = "NZN"  # NZ NBL code in FIBA LiveStats
FIBA_BASE_URL = "https://fibalivestats.dcd.shared.geniussports.com"

# Game index paths (pre-built mapping of games)
DEFAULT_GAME_INDEX_PARQUET = Path("data/nz_nbl_game_index.parquet")
DEFAULT_GAME_INDEX_CSV = Path("data/nz_nbl_game_index.csv")

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
        "NZ-NBL data fetching requires these packages."
    )

# Try to import Playwright for JS-rendered schedule discovery
try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.debug(
        "Playwright not available. JS-rendered schedule discovery disabled. "
        "Install with: uv pip install 'cbb-data[nz_nbl]' && playwright install chromium"
    )

# User-Agent string for all requests
_UA_STRING = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


# ==============================================================================
# Game Index Management
# ==============================================================================


def load_game_index(index_path: Path | None = None) -> pd.DataFrame:
    """Load pre-built NZ-NBL game index

    The game index is a manually curated mapping of NZ-NBL games to FIBA game IDs.
    This is necessary because FIBA LiveStats doesn't provide a searchable schedule API.

    Args:
        index_path: Path to game index file (default: auto-detect .parquet or .csv)

    Returns:
        DataFrame with game index

    Columns:
        - SEASON: Season string (e.g., "2024")
        - GAME_ID: FIBA game ID
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score (if known)
        - AWAY_SCORE: Away team final score (if known)

    Example:
        >>> index = load_game_index()
        >>> print(f"Loaded {len(index)} NZ-NBL games")
    """
    # Auto-detect format if no path specified
    if index_path is None:
        if DEFAULT_GAME_INDEX_PARQUET.exists():
            index_path = DEFAULT_GAME_INDEX_PARQUET
        elif DEFAULT_GAME_INDEX_CSV.exists():
            index_path = DEFAULT_GAME_INDEX_CSV
        else:
            logger.warning(
                "NZ-NBL game index not found. Checked:\n"
                f"  - {DEFAULT_GAME_INDEX_PARQUET}\n"
                f"  - {DEFAULT_GAME_INDEX_CSV}\n"
                "Create game index first. See documentation for details."
            )
            return pd.DataFrame(
                columns=[
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
        logger.warning(f"NZ-NBL game index not found: {index_path}")
        return pd.DataFrame(
            columns=[
                "SEASON",
                "GAME_ID",
                "GAME_DATE",
                "HOME_TEAM",
                "AWAY_TEAM",
                "HOME_SCORE",
                "AWAY_SCORE",
            ]
        )

    try:
        # Load based on file extension
        if index_path.suffix == ".parquet":
            df = pd.read_parquet(index_path)
        elif index_path.suffix == ".csv":
            df = pd.read_csv(index_path)
            # Convert GAME_DATE to datetime
            if "GAME_DATE" in df.columns:
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        else:
            logger.error(f"Unsupported game index format: {index_path.suffix}")
            return pd.DataFrame()

        logger.info(f"Loaded {len(df)} games from NZ-NBL game index ({index_path.name})")
        return df

    except Exception as e:
        logger.error(f"Failed to load NZ-NBL game index: {e}")
        return pd.DataFrame()


# ==============================================================================
# Schedule Discovery from NZ-NBL Website
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
def _scrape_nz_nbl_schedule(season: str) -> pd.DataFrame:
    """Scrape NZ-NBL schedule from official website

    Args:
        season: Season string (e.g., "2024")

    Returns:
        DataFrame with schedule including FIBA game IDs

    Columns:
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score (if available)
        - AWAY_SCORE: Away team final score (if available)
        - FIBA_GAME_ID: FIBA LiveStats game ID
        - VENUE: Venue name (if available)
        - STATUS: Game status (FINAL, SCHEDULED, etc.)
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    import re

    url = f"https://nznbl.basketball/stats/results/?season={season}"
    logger.info(f"Scraping NZ-NBL schedule: {url}")

    try:
        rate_limiter.acquire("nz_nbl_web")
        # Add User-Agent to avoid 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find the games table
        # NZ-NBL website typically uses a table or div structure for game listings
        games = []

        # Look for game rows (adjust selector based on actual HTML structure)
        game_rows = soup.find_all("tr", class_=["game-row", "match-row"]) or soup.find_all(
            "div", class_=["game", "match"]
        )

        if not game_rows:
            # Fallback: try to find any links to FIBA LiveStats
            logger.debug("No game rows found with expected classes, searching for FIBA links")
            fiba_links = soup.find_all(
                "a", href=re.compile(r"fibalivestats\.dcd\.shared\.geniussports\.com")
            )

            for link in fiba_links:
                href = link.get("href", "")
                # Extract FIBA game ID from URL
                match = re.search(
                    r"fibalivestats\.dcd\.shared\.geniussports\.com/u/([A-Z]+)/(\d+)", href
                )
                if match:
                    comp_id = match.group(1)
                    game_id = match.group(2)

                    # Try to extract team names from surrounding context
                    parent = link.find_parent(["tr", "div", "li"])
                    text = parent.get_text(strip=True) if parent else link.get_text(strip=True)

                    games.append(
                        {
                            "FIBA_GAME_ID": game_id,
                            "FIBA_COMP_ID": comp_id,
                            "RAW_TEXT": text,
                        }
                    )
        else:
            # Parse structured game rows
            for row in game_rows:
                try:
                    # Extract FIBA LiveStats link
                    fiba_link = row.find(
                        "a", href=re.compile(r"fibalivestats\.dcd\.shared\.geniussports\.com")
                    )
                    if not fiba_link:
                        continue

                    href = fiba_link.get("href", "")
                    match = re.search(
                        r"fibalivestats\.dcd\.shared\.geniussports\.com/u/([A-Z]+)/(\d+)", href
                    )
                    if not match:
                        continue

                    comp_id = match.group(1)
                    game_id = match.group(2)

                    # Extract team names (adjust selectors based on actual HTML)
                    team_cells = row.find_all("td", class_=["team", "team-name"]) or row.find_all(
                        "span", class_=["team", "team-name"]
                    )
                    home_team = team_cells[0].get_text(strip=True) if len(team_cells) > 0 else ""
                    away_team = team_cells[1].get_text(strip=True) if len(team_cells) > 1 else ""

                    # Extract scores (adjust selectors based on actual HTML)
                    score_cells = row.find_all("td", class_=["score"]) or row.find_all(
                        "span", class_=["score"]
                    )
                    home_score = (
                        _safe_int(score_cells[0].get_text(strip=True))
                        if len(score_cells) > 0
                        else None
                    )
                    away_score = (
                        _safe_int(score_cells[1].get_text(strip=True))
                        if len(score_cells) > 1
                        else None
                    )

                    # Extract date (adjust selectors based on actual HTML)
                    date_cell = row.find("td", class_=["date", "game-date"]) or row.find(
                        "span", class_=["date", "game-date"]
                    )
                    game_date = date_cell.get_text(strip=True) if date_cell else ""

                    # Extract venue
                    venue_cell = row.find("td", class_=["venue"]) or row.find(
                        "span", class_=["venue"]
                    )
                    venue = venue_cell.get_text(strip=True) if venue_cell else ""

                    # Determine status
                    status = "FINAL" if home_score is not None else "SCHEDULED"

                    games.append(
                        {
                            "FIBA_GAME_ID": game_id,
                            "FIBA_COMP_ID": comp_id,
                            "HOME_TEAM": home_team,
                            "AWAY_TEAM": away_team,
                            "HOME_SCORE": home_score,
                            "AWAY_SCORE": away_score,
                            "GAME_DATE": game_date,
                            "VENUE": venue,
                            "STATUS": status,
                        }
                    )

                except Exception as e:
                    logger.debug(f"Error parsing game row: {e}")
                    continue

        if not games:
            logger.warning(f"No games found for NZ-NBL {season}")
            return pd.DataFrame()

        df = pd.DataFrame(games)

        # Add metadata
        df["LEAGUE"] = "NZ-NBL"
        df["SEASON"] = season

        # Ensure GAME_ID column (use FIBA_GAME_ID as primary identifier)
        if "FIBA_GAME_ID" in df.columns:
            df["GAME_ID"] = df["FIBA_GAME_ID"]

        # Try to parse game dates
        if "GAME_DATE" in df.columns:
            try:
                df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
            except Exception:
                pass

        logger.info(f"Scraped {len(df)} NZ-NBL games for {season}")
        return df

    except Exception as e:
        logger.error(f"Failed to scrape NZ-NBL schedule for {season}: {e}")
        return pd.DataFrame()


def _render_nz_nbl_match_centre(season: str) -> list[dict]:
    """Use Playwright to render NZ-NBL match centre and extract FIBA game IDs

    The NZ-NBL website uses a Genius Sports JavaScript widget to display
    game schedules. This function uses Playwright to render the page and
    extract real FIBA game IDs from the rendered content.

    Args:
        season: Season string (e.g., "2024")

    Returns:
        List of dictionaries with game data including FIBA IDs

    Requires:
        - Playwright installed: uv pip install 'cbb-data[nz_nbl]'
        - Chromium browser: playwright install chromium
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning(
            "Playwright not available for JS rendering. "
            "Install with: uv pip install 'cbb-data[nz_nbl]' && playwright install chromium"
        )
        return []

    import re

    url = f"https://nznbl.basketball/stats/results/?season={season}"
    logger.info(f"Rendering NZ-NBL match centre with Playwright: {url}")

    rows: list[dict] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_UA_STRING)
            page = context.new_page()

            # Navigate and wait for network to settle (widget loads async)
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Wait for the Genius Sports widget to render
            # The widget typically takes 2-5 seconds to populate
            page.wait_for_timeout(5000)

            # Strategy 1: Look for links to FIBA LiveStats in rendered HTML
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")

            fiba_links = soup.find_all(
                "a", href=re.compile(r"fibalivestats\.dcd\.shared\.geniussports\.com")
            )

            for link in fiba_links:
                href = link.get("href", "")
                match = re.search(
                    r"fibalivestats\.dcd\.shared\.geniussports\.com/u/([A-Z]+)/(\d+)", href
                )
                if match:
                    comp_id = match.group(1)
                    game_id = match.group(2)

                    # Try to extract game context from parent elements
                    parent = link.find_parent(["tr", "div", "li", "article"])

                    # Extract team names if available
                    home_team = ""
                    away_team = ""
                    game_date = ""

                    if parent:
                        # Look for team name elements
                        team_elements = parent.find_all(class_=re.compile(r"team|club|name", re.I))
                        if len(team_elements) >= 2:
                            home_team = team_elements[0].get_text(strip=True)
                            away_team = team_elements[1].get_text(strip=True)

                        # Look for date elements
                        date_element = parent.find(class_=re.compile(r"date|time", re.I))
                        if date_element:
                            game_date = date_element.get_text(strip=True)

                    rows.append(
                        {
                            "FIBA_GAME_ID": game_id,
                            "FIBA_COMP_ID": comp_id,
                            "HOME_TEAM": home_team,
                            "AWAY_TEAM": away_team,
                            "GAME_DATE_RAW": game_date,
                            "LIVE_STATS_URL": href,
                        }
                    )

            # Strategy 2: If no FIBA links found, try to intercept API calls
            if not rows:
                logger.debug("No FIBA links found in rendered HTML, checking for widget data")

                # Try to extract data from page scripts/variables
                scripts = soup.find_all("script")
                for script in scripts:
                    script_text = script.string or ""
                    # Look for game data patterns in JS variables
                    if "gameId" in script_text or "fixtureId" in script_text:
                        # Parse JSON from script if found
                        import json

                        json_match = re.search(r'\{[^}]*"gameId"[^}]*\}', script_text)
                        if json_match:
                            try:
                                data = json.loads(json_match.group())
                                if "gameId" in data:
                                    rows.append(
                                        {
                                            "FIBA_GAME_ID": str(data["gameId"]),
                                            "FIBA_COMP_ID": "NZN",
                                            "HOME_TEAM": data.get("homeTeam", ""),
                                            "AWAY_TEAM": data.get("awayTeam", ""),
                                            "GAME_DATE_RAW": data.get("date", ""),
                                            "LIVE_STATS_URL": "",
                                        }
                                    )
                            except json.JSONDecodeError:
                                continue

            browser.close()

        logger.info(f"Playwright extracted {len(rows)} games for NZ-NBL {season}")
        return rows

    except Exception as e:
        logger.error(f"Playwright rendering failed for NZ-NBL {season}: {e}")
        return []


# ==============================================================================
# FIBA LiveStats HTML Scraping
# ==============================================================================


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
    # Structure: <table class="teamBoxscore"> with rows for each player
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


def _safe_int(value: str, default: int = 0) -> int:
    """Safely convert string to int, returning default if invalid"""
    try:
        # Remove any non-digit characters except minus
        cleaned = "".join(c for c in value if c.isdigit() or c == "-")
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


def _scrape_fiba_box_score(game_id: str) -> pd.DataFrame:
    """Scrape box score from FIBA LiveStats HTML

    Args:
        game_id: FIBA game ID

    Returns:
        DataFrame with player box scores

    Note:
        This implementation parses FIBA LiveStats HTML tables.
        Structure may vary - adjust parsing logic if needed.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    url = f"{FIBA_BASE_URL}/u/{FIBA_LEAGUE_CODE}/{game_id}/bs.html"
    logger.info(f"Scraping NZ-NBL box score: {url}")

    try:
        rate_limiter.acquire("fiba_livestats")
        # Add User-Agent to avoid 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Extract team names from page
        team_headers = soup.find_all("h2", class_="teamName")
        if len(team_headers) < 2:
            logger.warning(f"Could not find team names for game {game_id}")
            return pd.DataFrame()

        team1_name = team_headers[0].get_text(strip=True)
        team2_name = team_headers[1].get_text(strip=True)

        # Parse both teams
        all_players = []
        all_players.extend(_parse_fiba_html_table(soup, team1_name))
        all_players.extend(_parse_fiba_html_table(soup, team2_name))

        if not all_players:
            logger.warning(f"No player stats found for game {game_id}")
            return pd.DataFrame()

        df = pd.DataFrame(all_players)

        # Calculate percentages
        if "FGM" in df.columns and "FGA" in df.columns:
            df["FG_PCT"] = (df["FGM"] / df["FGA"] * 100).fillna(0)
        if "FG3M" in df.columns and "FG3A" in df.columns:
            df["FG3_PCT"] = (df["FG3M"] / df["FG3A"] * 100).fillna(0)
        if "FTM" in df.columns and "FTA" in df.columns:
            df["FT_PCT"] = (df["FTM"] / df["FTA"] * 100).fillna(0)

        logger.info(f"Scraped {len(df)} player records for game {game_id}")
        return df

    except Exception as e:
        logger.error(f"Failed to scrape box score for game {game_id}: {e}")
        return pd.DataFrame()


def _parse_fiba_pbp_table(soup: BeautifulSoup, period: int) -> list[dict[str, Any]]:
    """Parse FIBA LiveStats play-by-play HTML table for a period

    Args:
        soup: BeautifulSoup object of the period section
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


def _scrape_fiba_play_by_play(game_id: str) -> pd.DataFrame:
    """Scrape play-by-play from FIBA LiveStats HTML

    Args:
        game_id: FIBA game ID

    Returns:
        DataFrame with play-by-play events

    Note:
        This implementation parses FIBA LiveStats HTML tables.
        Structure may vary - adjust parsing logic if needed.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    url = f"{FIBA_BASE_URL}/u/{FIBA_LEAGUE_CODE}/{game_id}/pbp.html"
    logger.info(f"Scraping NZ-NBL play-by-play: {url}")

    try:
        rate_limiter.acquire("fiba_livestats")
        # Add User-Agent to avoid 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # FIBA typically organizes PBP by quarters
        # Look for quarter sections (Q1, Q2, Q3, Q4, OT)
        all_events = []

        # Try to find quarter headers and their associated tables
        quarter_headers = soup.find_all(["h3", "h4"], class_=["quarter", "period"])

        if not quarter_headers:
            # Fallback: try parsing all tables as one big list
            logger.debug("No quarter headers found, attempting single table parse")
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
            logger.warning(f"No play-by-play events found for game {game_id}")
            return pd.DataFrame()

        df = pd.DataFrame(all_events)
        logger.info(f"Scraped {len(df)} play-by-play events for game {game_id}")
        return df

    except Exception as e:
        logger.error(f"Failed to scrape play-by-play for game {game_id}: {e}")
        return pd.DataFrame()


# ==============================================================================
# Public Fetcher Functions
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_schedule(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL schedule from pre-built game index

    Args:
        season: Season string (e.g., "2024" for 2024 season)

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: FIBA game identifier
        - SEASON: Season string
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (if available)
        - AWAY_SCORE: Away team score (if available)
        - LEAGUE: "NZ-NBL"

    Example:
        >>> schedule = fetch_nz_nbl_schedule("2024")
        >>> print(f"Found {len(schedule)} NZ-NBL games")
    """
    logger.info(f"Fetching NZ-NBL schedule: {season}")

    # Load game index
    index = load_game_index()

    if index.empty:
        logger.warning("NZ-NBL game index is empty")
        return _empty_schedule_df()

    # Filter by season (handle both string and integer types)
    season_filter = index["SEASON"].astype(str) == str(season)
    df = index[season_filter].copy()

    # Add league identifier
    df["LEAGUE"] = "NZ-NBL"

    logger.info(f"Fetched {len(df)} NZ-NBL games for {season}")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_schedule_full(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL schedule via dynamic web scraping (includes FIBA game ID discovery)

    This function actively scrapes the NZ-NBL website to discover game schedules
    and extracts FIBA LiveStats game IDs from embedded URLs. Unlike fetch_nz_nbl_schedule()
    which loads from a pre-built index, this function discovers games dynamically.

    Args:
        season: Season string (e.g., "2024" for 2024 season)

    Returns:
        DataFrame with full game schedule including FIBA identifiers

    Columns:
        - GAME_ID: FIBA game identifier (same as FIBA_GAME_ID)
        - FIBA_GAME_ID: FIBA LiveStats game ID
        - FIBA_COMP_ID: FIBA competition code (typically "NZN")
        - SEASON: Season string
        - LEAGUE: "NZ-NBL"
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (if available)
        - AWAY_SCORE: Away team score (if available)
        - VENUE: Venue name (if available)
        - STATUS: Game status (FINAL, SCHEDULED, etc.)

    Example:
        >>> schedule = fetch_nz_nbl_schedule_full("2024")
        >>> print(f"Found {len(schedule)} NZ-NBL games")
        >>> print(f"FIBA game IDs: {schedule['FIBA_GAME_ID'].tolist()[:5]}")

    Note:
        This function requires active web scraping and may be slower than
        fetch_nz_nbl_schedule() which uses a pre-built index. Use this function
        when you need the most up-to-date schedule data or when the pre-built
        index hasn't been updated yet.
    """
    logger.info(f"Fetching NZ-NBL schedule (full discovery): {season}")

    # Try Playwright-based JS rendering first (if available)
    if PLAYWRIGHT_AVAILABLE:
        logger.info("Attempting Playwright-based schedule discovery")
        raw_rows = _render_nz_nbl_match_centre(season)

        if raw_rows:
            df = pd.DataFrame(raw_rows)

            # Add metadata columns
            df["LEAGUE"] = "NZ-NBL"
            df["SEASON"] = str(season)

            # Ensure GAME_ID column
            if "FIBA_GAME_ID" in df.columns:
                df["GAME_ID"] = df["FIBA_GAME_ID"]

            # Parse game dates
            if "GAME_DATE_RAW" in df.columns:
                try:
                    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE_RAW"], errors="coerce")
                except Exception:
                    df["GAME_DATE"] = None

            logger.info(f"Fetched {len(df)} NZ-NBL games via Playwright for {season}")
            return df
        else:
            logger.warning("Playwright found no games, falling back to HTML scraper")

    # Fall back to static HTML scraper (won't find games due to JS widget)
    df = _scrape_nz_nbl_schedule(season)

    if df.empty:
        logger.warning(f"No games found for NZ-NBL {season}")
        return _empty_schedule_df()

    logger.info(f"Fetched {len(df)} NZ-NBL games for {season} (full discovery)")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_player_game(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL player-game box scores via FIBA LiveStats HTML scraping

    Args:
        season: Season string (e.g., "2024")

    Returns:
        DataFrame with player-game box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID (if available)
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - MIN: Minutes played
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Note:
        Aggregates box scores from all games in the season.
        HTML parsing implementation pending.
    """
    logger.info(f"Fetching NZ-NBL player-game box scores: {season}")

    # Get schedule for season
    schedule = fetch_nz_nbl_schedule(season)

    if schedule.empty:
        logger.warning(f"No NZ-NBL games found for {season}")
        return _empty_player_game_df()

    # Scrape box scores for all games
    frames: list[pd.DataFrame] = []
    for game_id in schedule["GAME_ID"]:
        box_score = _scrape_fiba_box_score(game_id)
        if not box_score.empty:
            box_score["GAME_ID"] = game_id
            box_score["LEAGUE"] = "NZ-NBL"
            box_score["SEASON"] = season
            frames.append(box_score)

    if not frames:
        logger.warning(f"No box score data scraped for {season}")
        return _empty_player_game_df()

    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Fetched {len(df)} NZ-NBL player-game records for {season}")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_team_game(season: str = "2024") -> pd.DataFrame:
    """Fetch NZ-NBL team-game box scores

    Aggregates player stats per (GAME_ID, TEAM).

    Args:
        season: Season string (e.g., "2024")

    Returns:
        DataFrame with team-game box scores

    Columns:
        - GAME_ID: Game identifier
        - TEAM: Team name
        - PTS, REB, AST, STL, BLK, TOV, PF
        - FGM, FGA, FG_PCT
        - FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string
    """
    logger.info(f"Fetching NZ-NBL team-game box scores: {season}")

    # Get player-game data
    player_game = fetch_nz_nbl_player_game(season)

    if player_game.empty:
        logger.warning(f"No player-game data for {season}")
        return _empty_team_game_df()

    # Aggregate by game and team
    stat_cols = [
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
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
    ]
    available_cols = [col for col in stat_cols if col in player_game.columns]

    team_game = player_game.groupby(["GAME_ID", "TEAM"], as_index=False)[available_cols].sum()

    # Recalculate shooting percentages
    if "FGM" in team_game.columns and "FGA" in team_game.columns:
        team_game["FG_PCT"] = (team_game["FGM"] / team_game["FGA"] * 100).fillna(0)
    if "FG3M" in team_game.columns and "FG3A" in team_game.columns:
        team_game["FG3_PCT"] = (team_game["FG3M"] / team_game["FG3A"] * 100).fillna(0)
    if "FTM" in team_game.columns and "FTA" in team_game.columns:
        team_game["FT_PCT"] = (team_game["FTM"] / team_game["FTA"] * 100).fillna(0)

    # Add metadata
    team_game["LEAGUE"] = "NZ-NBL"
    team_game["SEASON"] = season

    logger.info(f"Fetched {len(team_game)} NZ-NBL team-game records for {season}")
    return team_game


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_pbp(season: str = "2024", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NZ-NBL play-by-play data via FIBA LiveStats HTML scraping

    Args:
        season: Season string (e.g., "2024")
        game_id: Optional game ID to filter (None = all games in season)

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENT_NUM: Event sequence number
        - PERIOD: Quarter number
        - CLOCK: Game clock (MM:SS)
        - TEAM: Team name (if event has team)
        - PLAYER: Player name (if event has player)
        - EVENT_TYPE: Type of event
        - DESCRIPTION: Event description
        - SCORE_HOME: Home team score after event
        - SCORE_AWAY: Away team score after event
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Note:
        HTML parsing implementation pending.
    """
    logger.info(f"Fetching NZ-NBL play-by-play: {season}, game_id={game_id}")

    if game_id:
        # Single game
        pbp = _scrape_fiba_play_by_play(game_id)
        if not pbp.empty:
            pbp["GAME_ID"] = game_id
            pbp["LEAGUE"] = "NZ-NBL"
            pbp["SEASON"] = season
        return pbp

    else:
        # All games in season
        schedule = fetch_nz_nbl_schedule(season)

        if schedule.empty:
            logger.warning(f"No NZ-NBL games found for {season}")
            return _empty_pbp_df()

        frames: list[pd.DataFrame] = []
        for gid in schedule["GAME_ID"]:
            pbp = _scrape_fiba_play_by_play(gid)
            if not pbp.empty:
                pbp["GAME_ID"] = gid
                pbp["LEAGUE"] = "NZ-NBL"
                pbp["SEASON"] = season
                frames.append(pbp)

        if not frames:
            logger.warning(f"No play-by-play data scraped for {season}")
            return _empty_pbp_df()

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"Fetched {len(df)} NZ-NBL play-by-play events for {season}")
        return df


def _scrape_fiba_shot_chart(game_id: str) -> pd.DataFrame:
    """Scrape shot chart from FIBA LiveStats HTML

    Args:
        game_id: FIBA game ID

    Returns:
        DataFrame with shot chart data

    Note:
        FIBA LiveStats embeds shot data in JavaScript/JSON within the HTML.
        This implementation attempts to extract and parse that data.
    """
    if not HTML_PARSING_AVAILABLE:
        logger.warning("HTML parsing not available. Install requests and beautifulsoup4.")
        return pd.DataFrame()

    import json
    import re

    url = f"{FIBA_BASE_URL}/u/{FIBA_LEAGUE_CODE}/{game_id}/sc.html"
    logger.info(f"Scraping NZ-NBL shot chart: {url}")

    try:
        rate_limiter.acquire("fiba_livestats")
        # Add User-Agent to avoid 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Strategy 1: Look for JavaScript variables containing shot data
        # FIBA typically embeds data in variables like: var shotData = [...];
        scripts = soup.find_all("script")
        shot_data = []

        for script in scripts:
            script_text = script.string if script.string else ""

            # Look for shot data patterns
            # Common patterns: var shotData = [...]; or shotChart = {...};
            patterns = [
                r"var\s+shotData\s*=\s*(\[.*?\]);",
                r"var\s+shots\s*=\s*(\[.*?\]);",
                r"shotChart\s*=\s*(\{.*?\});",
                r"chartData\s*=\s*(\[.*?\]);",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, script_text, re.DOTALL)
                for match in matches:
                    try:
                        # Try to parse as JSON
                        data = json.loads(match)
                        if isinstance(data, list):
                            shot_data.extend(data)
                        elif isinstance(data, dict):
                            # If dict, look for shots array within it
                            if "shots" in data:
                                shot_data.extend(data["shots"])
                            elif "data" in data:
                                shot_data.extend(data["data"])
                    except json.JSONDecodeError:
                        continue

        # Strategy 2: Look for data attributes on SVG/canvas elements
        if not shot_data:
            shot_elements = soup.find_all(["circle", "rect"], attrs={"data-shot": True})
            for elem in shot_elements:
                try:
                    data_str = elem.get("data-shot", "{}")
                    shot_info = json.loads(data_str)
                    shot_data.append(shot_info)
                except (json.JSONDecodeError, TypeError):
                    continue

        # Strategy 3: Parse shot table (if available)
        if not shot_data:
            shot_table = soup.find("table", class_=["shotChart", "shots"])
            if shot_table:
                rows = shot_table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 5:  # Expect: player, team, period, result, coords
                        try:
                            shot_data.append(
                                {
                                    "player": cells[0].get_text(strip=True),
                                    "team": cells[1].get_text(strip=True),
                                    "period": _safe_int(cells[2].get_text(strip=True)),
                                    "result": cells[3].get_text(strip=True),
                                    "x": _safe_int(cells[4].get("data-x", "0")),
                                    "y": _safe_int(cells[4].get("data-y", "0")),
                                }
                            )
                        except Exception:
                            continue

        if not shot_data:
            logger.warning(f"No shot chart data found for game {game_id}")
            return pd.DataFrame()

        # Convert to DataFrame and normalize
        df = pd.DataFrame(shot_data)

        # Normalize column names (handle various formats from FIBA)
        column_mapping = {
            "playerName": "PLAYER_NAME",
            "player": "PLAYER_NAME",
            "teamName": "TEAM",
            "team": "TEAM",
            "period": "PERIOD",
            "quarter": "PERIOD",
            "made": "MADE",
            "result": "SHOT_RESULT",
            "shotType": "SHOT_TYPE",
            "type": "SHOT_TYPE",
            "points": "POINTS",
            "x": "X",
            "y": "Y",
            "coordX": "X",
            "coordY": "Y",
            "clock": "CLOCK",
            "time": "CLOCK",
        }

        df.rename(columns=column_mapping, inplace=True)

        # Ensure required columns exist
        if "X" not in df.columns or "Y" not in df.columns:
            logger.warning(f"Shot coordinates not found for game {game_id}")
            return pd.DataFrame()

        # Determine shot type if not provided
        if "SHOT_TYPE" not in df.columns:
            # Infer from points or description
            if "POINTS" in df.columns:
                df["SHOT_TYPE"] = df["POINTS"].apply(
                    lambda p: "3PT" if p == 3 else ("2PT" if p == 2 else "FT")
                )
            else:
                df["SHOT_TYPE"] = "2PT"  # Default

        # Determine shot result if not provided
        if "SHOT_RESULT" not in df.columns:
            if "MADE" in df.columns:
                df["SHOT_RESULT"] = df["MADE"].apply(lambda m: "MADE" if m else "MISSED")
            elif "POINTS" in df.columns:
                df["SHOT_RESULT"] = df["POINTS"].apply(lambda p: "MADE" if p > 0 else "MISSED")
            else:
                df["SHOT_RESULT"] = "MADE"  # Assume made if unknown

        # Calculate points if not provided
        if "POINTS" not in df.columns:
            df["POINTS"] = df.apply(
                lambda row: (
                    3
                    if row.get("SHOT_TYPE") == "3PT" and row.get("SHOT_RESULT") == "MADE"
                    else 2
                    if row.get("SHOT_TYPE") == "2PT" and row.get("SHOT_RESULT") == "MADE"
                    else 1
                    if row.get("SHOT_TYPE") == "FT" and row.get("SHOT_RESULT") == "MADE"
                    else 0
                ),
                axis=1,
            )

        # Add shot ID
        df["SHOT_ID"] = range(1, len(df) + 1)

        logger.info(f"Scraped {len(df)} shots for game {game_id}")
        return df

    except Exception as e:
        logger.error(f"Failed to scrape shot chart for game {game_id}: {e}")
        return pd.DataFrame()


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_shot_chart(season: str = "2024", game_id: str | None = None) -> pd.DataFrame:
    """Fetch NZ-NBL shot chart data via FIBA LiveStats HTML scraping

    Args:
        season: Season string (e.g., "2024")
        game_id: Optional game ID to filter (None = all games in season)

    Returns:
        DataFrame with shot chart data

    Columns:
        - SHOT_ID: Sequential shot number
        - GAME_ID: Game identifier
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - PERIOD: Quarter number
        - CLOCK: Game clock when shot taken
        - X: Shot x-coordinate
        - Y: Shot y-coordinate
        - SHOT_TYPE: "2PT", "3PT", or "FT"
        - SHOT_RESULT: "MADE" or "MISSED"
        - POINTS: Points scored (0 if missed)
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Example:
        >>> shots = fetch_nz_nbl_shot_chart("2024")
        >>> print(f"Total shots: {len(shots)}")
        >>> made_pct = (shots['SHOT_RESULT'] == 'MADE').mean() * 100
        >>> print(f"FG%: {made_pct:.1f}%")

    Note:
        Shot coordinates extracted from FIBA LiveStats HTML/JavaScript.
        Coordinate system may vary - check FIBA documentation for details.
    """
    logger.info(f"Fetching NZ-NBL shot chart: {season}, game_id={game_id}")

    if game_id:
        # Single game
        shots = _scrape_fiba_shot_chart(game_id)
        if not shots.empty:
            shots["GAME_ID"] = game_id
            shots["LEAGUE"] = "NZ-NBL"
            shots["SEASON"] = season
        return shots

    else:
        # All games in season
        try:
            schedule = fetch_nz_nbl_schedule_full(season)
        except Exception:
            # Fallback to pre-built index if full discovery fails
            logger.debug("Full schedule discovery failed, trying pre-built index")
            schedule = fetch_nz_nbl_schedule(season)

        if schedule.empty:
            logger.warning(f"No NZ-NBL games found for {season}")
            return _empty_shot_chart_df()

        frames: list[pd.DataFrame] = []
        for gid in schedule["GAME_ID"]:
            shots = _scrape_fiba_shot_chart(gid)
            if not shots.empty:
                shots["GAME_ID"] = gid
                shots["LEAGUE"] = "NZ-NBL"
                shots["SEASON"] = season
                frames.append(shots)

        if not frames:
            logger.warning(f"No shot chart data scraped for {season}")
            return _empty_shot_chart_df()

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"Fetched {len(df)} NZ-NBL shots for {season}")
        return df


# ==============================================================================
# Season Aggregation Functions
# ==============================================================================


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_player_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch NZ-NBL player season statistics (aggregated from game-level data)

    Aggregates player_game data to create season totals/averages.
    Since FIBA LiveStats doesn't provide season aggregates directly,
    we build them from game-level box scores.

    Args:
        season: Season string (e.g., "2024")
        per_mode: Aggregation mode
            - "Totals": Season totals
            - "PerGame": Per-game averages
            - "Per40": Per-40-minute stats

    Returns:
        DataFrame with player season statistics

    Columns:
        - PLAYER_NAME: Player name
        - TEAM: Team name (last team if player was traded)
        - GP: Games played
        - MIN: Minutes (total or per-game)
        - PTS, REB, AST, STL, BLK, TOV, PF: Box score stats
        - FGM, FGA, FG_PCT: Field goal stats
        - FG3M, FG3A, FG3_PCT: 3-point stats
        - FTM, FTA, FT_PCT: Free throw stats
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Note:
        Built from game-level data aggregation, not a direct FIBA endpoint.
    """
    logger.info(f"Fetching NZ-NBL player season: {season}, {per_mode}")

    # Get all player-game data for the season
    player_game = fetch_nz_nbl_player_game(season=season)

    if player_game.empty:
        logger.warning(f"No player-game data available for {season}")
        return _empty_player_season_df()

    # Group by player and aggregate
    agg_dict = {
        "GAME_ID": "count",  # Will become GP
        "MIN": "sum",
        "PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "OREB": "sum",
        "DREB": "sum",
        "REB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
        "TEAM": "last",  # Use last team if player was traded
    }

    # Aggregate by player
    player_season = player_game.groupby("PLAYER_NAME", as_index=False).agg(agg_dict)

    # Rename GAME_ID count to GP
    player_season.rename(columns={"GAME_ID": "GP"}, inplace=True)

    # Calculate shooting percentages
    player_season["FG_PCT"] = (player_season["FGM"] / player_season["FGA"]).fillna(0)
    player_season["FG3_PCT"] = (player_season["FG3M"] / player_season["FG3A"]).fillna(0)
    player_season["FT_PCT"] = (player_season["FTM"] / player_season["FTA"]).fillna(0)

    # Apply per-mode calculations
    if per_mode == "PerGame":
        # Convert totals to per-game averages
        counting_stats = [
            "MIN",
            "PTS",
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            "OREB",
            "DREB",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
        ]
        for stat in counting_stats:
            if stat in player_season.columns:
                player_season[stat] = player_season[stat] / player_season["GP"]

    elif per_mode == "Per40":
        # Convert to per-40-minute stats
        counting_stats = [
            "PTS",
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            "OREB",
            "DREB",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
        ]
        for stat in counting_stats:
            if stat in player_season.columns:
                player_season[stat] = ((player_season[stat] / player_season["MIN"]) * 40).fillna(0)

    # Add metadata
    player_season["LEAGUE"] = "NZ-NBL"
    player_season["SEASON"] = season

    # Round numeric columns
    numeric_cols = player_season.select_dtypes(include=["float64"]).columns
    player_season[numeric_cols] = player_season[numeric_cols].round(1)

    logger.info(f"Aggregated {len(player_season)} NZ-NBL player season records for {season}")
    return player_season


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_team_season(
    season: str = "2024",
    per_mode: str = "Totals",
) -> pd.DataFrame:
    """Fetch NZ-NBL team season statistics (aggregated from game-level data)

    Aggregates team_game data to create season totals/averages.
    Since FIBA LiveStats doesn't provide season aggregates directly,
    we build them from game-level data.

    Args:
        season: Season string (e.g., "2024")
        per_mode: Aggregation mode
            - "Totals": Season totals
            - "PerGame": Per-game averages

    Returns:
        DataFrame with team season statistics

    Columns:
        - TEAM: Team name
        - GP: Games played
        - W: Wins
        - L: Losses
        - WIN_PCT: Win percentage
        - PTS: Points (total or per-game)
        - OPP_PTS: Opponent points
        - FGM, FGA, FG_PCT: Field goal stats
        - FG3M, FG3A, FG3_PCT: 3-point stats
        - FTM, FTA, FT_PCT: Free throw stats
        - REB, AST, STL, BLK, TOV, PF: Team stats
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string

    Note:
        Built from game-level data aggregation, not a direct FIBA endpoint.
    """
    logger.info(f"Fetching NZ-NBL team season: {season}, {per_mode}")

    # Get all team-game data for the season
    team_game = fetch_nz_nbl_team_game(season=season)

    if team_game.empty:
        logger.warning(f"No team-game data available for {season}")
        return _empty_team_season_df()

    # Group by team and aggregate
    agg_dict = {
        "GAME_ID": "count",  # Will become GP
        "W": "sum",  # Assuming team_game has W/L indicators
        "PTS": "sum",
        "OPP_PTS": "sum",
        "FGM": "sum",
        "FGA": "sum",
        "FG3M": "sum",
        "FG3A": "sum",
        "FTM": "sum",
        "FTA": "sum",
        "REB": "sum",
        "AST": "sum",
        "STL": "sum",
        "BLK": "sum",
        "TOV": "sum",
        "PF": "sum",
    }

    # Filter agg_dict to only include columns that exist in team_game
    agg_dict = {k: v for k, v in agg_dict.items() if k in team_game.columns}

    # Aggregate by team
    team_season = team_game.groupby("TEAM", as_index=False).agg(agg_dict)

    # Rename GAME_ID count to GP
    if "GAME_ID" in team_season.columns:
        team_season.rename(columns={"GAME_ID": "GP"}, inplace=True)

    # Calculate wins/losses if W column exists
    if "W" in team_season.columns and "GP" in team_season.columns:
        team_season["L"] = team_season["GP"] - team_season["W"]
        team_season["WIN_PCT"] = (team_season["W"] / team_season["GP"]).fillna(0)

    # Calculate shooting percentages
    if "FGM" in team_season.columns and "FGA" in team_season.columns:
        team_season["FG_PCT"] = (team_season["FGM"] / team_season["FGA"]).fillna(0)
    if "FG3M" in team_season.columns and "FG3A" in team_season.columns:
        team_season["FG3_PCT"] = (team_season["FG3M"] / team_season["FG3A"]).fillna(0)
    if "FTM" in team_season.columns and "FTA" in team_season.columns:
        team_season["FT_PCT"] = (team_season["FTM"] / team_season["FTA"]).fillna(0)

    # Apply per-mode calculations
    if per_mode == "PerGame" and "GP" in team_season.columns:
        # Convert totals to per-game averages
        counting_stats = [
            "PTS",
            "OPP_PTS",
            "FGM",
            "FGA",
            "FG3M",
            "FG3A",
            "FTM",
            "FTA",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
        ]
        for stat in counting_stats:
            if stat in team_season.columns:
                team_season[stat] = team_season[stat] / team_season["GP"]

    # Add metadata
    team_season["LEAGUE"] = "NZ-NBL"
    team_season["SEASON"] = season

    # Round numeric columns
    numeric_cols = team_season.select_dtypes(include=["float64"]).columns
    team_season[numeric_cols] = team_season[numeric_cols].round(1)

    logger.info(f"Aggregated {len(team_season)} NZ-NBL team season records for {season}")
    return team_season


# ==============================================================================
# Empty DataFrame Helpers
# ==============================================================================


def _empty_schedule_df() -> pd.DataFrame:
    """Return empty DataFrame with schedule schema"""
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


def _empty_player_game_df() -> pd.DataFrame:
    """Return empty DataFrame with player-game schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "PLAYER_ID",
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
            "SEASON",
        ]
    )


def _empty_team_game_df() -> pd.DataFrame:
    """Return empty DataFrame with team-game schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
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
            "SEASON",
        ]
    )


def _empty_pbp_df() -> pd.DataFrame:
    """Return empty DataFrame with play-by-play schema"""
    return pd.DataFrame(
        columns=[
            "GAME_ID",
            "EVENT_NUM",
            "PERIOD",
            "CLOCK",
            "TEAM",
            "PLAYER",
            "EVENT_TYPE",
            "DESCRIPTION",
            "SCORE_HOME",
            "SCORE_AWAY",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_player_season_df() -> pd.DataFrame:
    """Return empty DataFrame with player-season schema"""
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
            "OREB",
            "DREB",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_team_season_df() -> pd.DataFrame:
    """Return empty DataFrame with team-season schema"""
    return pd.DataFrame(
        columns=[
            "TEAM",
            "GP",
            "W",
            "L",
            "WIN_PCT",
            "PTS",
            "OPP_PTS",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
            "LEAGUE",
            "SEASON",
        ]
    )


def _empty_shot_chart_df() -> pd.DataFrame:
    """Return empty DataFrame with shot chart schema"""
    return pd.DataFrame(
        columns=[
            "SHOT_ID",
            "GAME_ID",
            "PLAYER_NAME",
            "TEAM",
            "PERIOD",
            "CLOCK",
            "X",
            "Y",
            "SHOT_TYPE",
            "SHOT_RESULT",
            "POINTS",
            "LEAGUE",
            "SEASON",
        ]
    )
