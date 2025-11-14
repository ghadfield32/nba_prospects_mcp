"""Generic HTML Scraping Utilities

Shared HTML parsing functions used across multiple basketball leagues.
Provides reusable components for scraping schedule pages, box scores,
stats tables, and shot charts from various league websites.

Key Features:
- Generic HTML table → DataFrame parser
- Schedule page scrapers
- Box score page scrapers
- Stats table parsers with column normalization
- Robust error handling and logging

Used By: FIBA leagues (BCL/BAL/ABA/LKL), ACB, LNB Pro A

Dependencies:
- requests: HTTP client
- beautifulsoup4: HTML parsing
- pandas: Data manipulation
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from ..utils.rate_limiter import get_source_limiter

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# Standard headers to avoid bot detection
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


# ==============================================================================
# Generic HTML Table Parser
# ==============================================================================


def parse_html_table(
    html_or_soup: str | BeautifulSoup | Tag,
    table_selector: str = "table",
    header_row: int = 0,
    skip_rows: Optional[List[int]] = None,
    column_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Parse an HTML table into a pandas DataFrame.

    Generic table parser that handles various HTML table structures.
    Supports CSS selectors, header normalization, and column mapping.

    Args:
        html_or_soup: HTML string, BeautifulSoup object, or Tag
        table_selector: CSS selector for table element (default: "table")
        header_row: Which row contains headers (default: 0)
        skip_rows: List of row indices to skip (default: None)
        column_map: Dict mapping original column names to new names

    Returns:
        DataFrame with parsed table data

    Example:
        >>> html = '<table><tr><th>Name</th><th>Points</th></tr>
        ...         <tr><td>Player A</td><td>25</td></tr></table>'
        >>> df = parse_html_table(html)
        >>> print(df)
             Name  Points
        0  Player A      25
    """
    # Convert to BeautifulSoup if needed
    if isinstance(html_or_soup, str):
        soup = BeautifulSoup(html_or_soup, "html.parser")
    elif isinstance(html_or_soup, Tag):
        soup = html_or_soup
    else:
        soup = html_or_soup

    # Find table
    table = soup.select_one(table_selector) if isinstance(soup, BeautifulSoup) else soup

    if not table:
        logger.warning(f"No table found with selector: {table_selector}")
        return pd.DataFrame()

    # Extract all rows
    rows = table.find_all("tr")

    if not rows:
        logger.warning("Table has no rows")
        return pd.DataFrame()

    # Get headers from specified header row
    if header_row < len(rows):
        header_cells = rows[header_row].find_all(["th", "td"])
        headers = [cell.get_text(strip=True) for cell in header_cells]
    else:
        logger.warning(f"Header row {header_row} out of range, using column indices")
        first_data_row = rows[header_row + 1] if header_row + 1 < len(rows) else rows[0]
        num_cols = len(first_data_row.find_all(["th", "td"]))
        headers = [f"Column_{i}" for i in range(num_cols)]

    # Extract data rows (skip header row)
    data = []
    for i, row in enumerate(rows[header_row + 1:], start=header_row + 1):
        if skip_rows and i in skip_rows:
            continue

        cells = row.find_all(["td", "th"])
        row_data = [cell.get_text(strip=True) for cell in cells]

        # Pad or truncate to match header length
        if len(row_data) < len(headers):
            row_data.extend([""] * (len(headers) - len(row_data)))
        elif len(row_data) > len(headers):
            row_data = row_data[:len(headers)]

        data.append(row_data)

    # Create DataFrame
    df = pd.DataFrame(data, columns=headers)

    # Apply column mapping if provided
    if column_map:
        df = df.rename(columns=column_map)

    return df


# ==============================================================================
# FIBA Schedule Scraper
# ==============================================================================


def extract_fiba_game_id_from_link(link_href: str) -> Optional[int]:
    """
    Extract FIBA game ID from a FIBA LiveStats link.

    Args:
        link_href: URL or href attribute

    Returns:
        Game ID as integer, or None if not found

    Example:
        >>> url = "https://fibalivestats.dcd.shared.geniussports.com/u/BCL/123456/bs.html"
        >>> extract_fiba_game_id_from_link(url)
        123456
    """
    if not link_href:
        return None

    # Pattern: fibalivestats.../u/{LEAGUE}/{GAME_ID}/...
    match = re.search(r"/u/[A-Z]+/(\d+)/", link_href)

    if match:
        return int(match.group(1))

    return None


def scrape_fiba_schedule_page(
    schedule_url: str,
    league_code: str,
    season: str,
) -> pd.DataFrame:
    """
    Scrape a FIBA league schedule page to extract game information.

    Parses league schedule/results pages that link to FIBA LiveStats boxscores.
    Extracts game IDs, dates, teams, scores, and competition phases.

    Args:
        schedule_url: URL of league schedule page
        league_code: FIBA league code (e.g., "BCL", "BAL")
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with columns:
        - LEAGUE
        - SEASON
        - GAME_ID
        - GAME_DATE
        - HOME_TEAM
        - AWAY_TEAM
        - HOME_SCORE
        - AWAY_SCORE
        - COMPETITION_PHASE
        - FIBA_URL

    Example:
        >>> df = scrape_fiba_schedule_page(
        ...     "https://www.championsleague.basketball/schedule",
        ...     "BCL",
        ...     "2023-24"
        ... )
    """
    logger.info(f"Scraping {league_code} schedule from: {schedule_url}")

    try:
        # Fetch HTML
        rate_limiter.wait()  # Respect rate limits
        response = requests.get(schedule_url, headers=DEFAULT_HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        games = []

        # Find all FIBA LiveStats links
        # These typically look like: href="...fibalivestats.../u/BCL/123456/bs.html"
        fiba_links = soup.find_all("a", href=re.compile(r"fibalivestats\..*?/u/[A-Z]+/\d+/"))

        logger.info(f"Found {len(fiba_links)} FIBA LiveStats links")

        for link in fiba_links:
            href = link.get("href", "")

            # Extract game ID
            game_id = extract_fiba_game_id_from_link(href)

            if not game_id:
                continue

            # Try to extract context from parent rows/containers
            # This is league-specific, so we make best effort

            # Find parent row (usually a <tr> or <div> containing game info)
            parent_row = link.find_parent(["tr", "div", "li"])

            if not parent_row:
                # Just save the game ID with minimal info
                games.append({
                    "LEAGUE": league_code,
                    "SEASON": season,
                    "GAME_ID": game_id,
                    "GAME_DATE": None,
                    "HOME_TEAM": None,
                    "AWAY_TEAM": None,
                    "HOME_SCORE": None,
                    "AWAY_SCORE": None,
                    "COMPETITION_PHASE": "Regular Season",  # Default
                    "FIBA_URL": href,
                })
                continue

            # Extract all text from parent row
            row_text = parent_row.get_text(separator=" ", strip=True)

            # Try to extract date (various formats)
            date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", row_text)
            game_date = date_match.group(1) if date_match else None

            # Try to extract score (e.g., "85-72" or "85 - 72")
            score_match = re.search(r"(\d{1,3})\s*[-:]\s*(\d{1,3})", row_text)
            home_score = int(score_match.group(1)) if score_match else None
            away_score = int(score_match.group(2)) if score_match else None

            # Try to extract team names (challenging without knowing structure)
            # For now, leave as None - can be filled from boxscore later
            home_team = None
            away_team = None

            games.append({
                "LEAGUE": league_code,
                "SEASON": season,
                "GAME_ID": game_id,
                "GAME_DATE": game_date,
                "HOME_TEAM": home_team,
                "AWAY_TEAM": away_team,
                "HOME_SCORE": home_score,
                "AWAY_SCORE": away_score,
                "COMPETITION_PHASE": "Regular Season",  # Can be refined
                "FIBA_URL": href,
            })

        df = pd.DataFrame(games)

        # Remove duplicates (same game might be linked multiple times)
        if not df.empty:
            df = df.drop_duplicates(subset=["GAME_ID"], keep="first")

        logger.info(f"Extracted {len(df)} unique games from schedule")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape schedule from {schedule_url}: {e}")
        return pd.DataFrame()


# ==============================================================================
# FIBA Shot Chart Scraper
# ==============================================================================


def scrape_fiba_shot_chart_html(
    league_code: str,
    game_id: int,
) -> pd.DataFrame:
    """
    Scrape FIBA LiveStats shot chart data from HTML page.

    Extracts shot data from either:
    1. Shot chart HTML page (sh.html)
    2. Embedded JSON in <script> tags
    3. HTML elements with data attributes

    Args:
        league_code: FIBA league code (e.g., "BCL")
        game_id: FIBA game ID

    Returns:
        DataFrame with columns:
        - GAME_ID
        - LEAGUE
        - TEAM_ID
        - TEAM_NAME
        - PLAYER_ID
        - PLAYER_NAME
        - PERIOD
        - GAME_CLOCK
        - X
        - Y
        - SHOT_VALUE (2 or 3)
        - MADE (0 or 1)
        - SHOT_TYPE
        - SOURCE ("fiba_html_shotchart")

    Example:
        >>> df = scrape_fiba_shot_chart_html("BCL", 123456)
    """
    logger.info(f"Scraping shot chart for {league_code} game {game_id}")

    base_url = "https://fibalivestats.dcd.shared.geniussports.com"
    shot_chart_url = f"{base_url}/u/{league_code}/{game_id}/sh.html"

    try:
        rate_limiter.wait()
        response = requests.get(shot_chart_url, headers=DEFAULT_HEADERS, timeout=15)

        if response.status_code != 200:
            logger.warning(f"Shot chart page returned status {response.status_code}")

            # Try alternate approach: boxscore page might have shot data
            bs_url = f"{base_url}/u/{league_code}/{game_id}/bs.html"
            response = requests.get(bs_url, headers=DEFAULT_HEADERS, timeout=15)

        if response.status_code != 200:
            logger.warning(f"Could not access shot data for game {game_id}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.content, "html.parser")

        shots = []

        # Approach 1: Look for JSON in <script> tags
        scripts = soup.find_all("script")

        for script in scripts:
            script_text = script.string

            if not script_text:
                continue

            # Look for shot arrays or objects
            # Common patterns: shots:[{...}], shotsData:[{...}], etc.
            if "shot" in script_text.lower():
                # Try to extract JSON arrays
                # This is fragile and league-specific
                # For production, would need more robust JSON extraction

                import json

                # Look for array patterns: [{...}]
                array_matches = re.findall(r'\[{[^[]*?}\]', script_text)

                for arr_str in array_matches:
                    try:
                        shot_array = json.loads(arr_str)

                        for shot in shot_array:
                            if isinstance(shot, dict) and any(k in shot for k in ['x', 'X', 'coord_x']):
                                # Found shot data
                                shots.append({
                                    "GAME_ID": game_id,
                                    "LEAGUE": league_code,
                                    "TEAM_ID": shot.get("team_id") or shot.get("teamId"),
                                    "TEAM_NAME": shot.get("team") or shot.get("teamName"),
                                    "PLAYER_ID": shot.get("player_id") or shot.get("playerId"),
                                    "PLAYER_NAME": shot.get("player") or shot.get("playerName"),
                                    "PERIOD": shot.get("period") or shot.get("quarter"),
                                    "GAME_CLOCK": shot.get("time") or shot.get("clock"),
                                    "X": shot.get("x") or shot.get("X") or shot.get("coord_x"),
                                    "Y": shot.get("y") or shot.get("Y") or shot.get("coord_y"),
                                    "SHOT_VALUE": shot.get("points") or shot.get("value") or 2,
                                    "MADE": 1 if shot.get("made") or shot.get("result") == "made" else 0,
                                    "SHOT_TYPE": shot.get("type") or "Field Goal",
                                    "SOURCE": "fiba_html_shotchart",
                                })

                    except json.JSONDecodeError:
                        continue

        # Approach 2: Look for HTML elements with data attributes
        # e.g., <circle data-x="50" data-y="30" data-made="1" />
        shot_markers = soup.find_all(["circle", "div", "span"], attrs={"data-x": True})

        for marker in shot_markers:
            shots.append({
                "GAME_ID": game_id,
                "LEAGUE": league_code,
                "TEAM_ID": marker.get("data-team-id"),
                "TEAM_NAME": marker.get("data-team"),
                "PLAYER_ID": marker.get("data-player-id"),
                "PLAYER_NAME": marker.get("data-player"),
                "PERIOD": marker.get("data-period"),
                "GAME_CLOCK": marker.get("data-time"),
                "X": marker.get("data-x"),
                "Y": marker.get("data-y"),
                "SHOT_VALUE": int(marker.get("data-points", 2)),
                "MADE": int(marker.get("data-made", 0)),
                "SHOT_TYPE": marker.get("data-type", "Field Goal"),
                "SOURCE": "fiba_html_shotchart",
            })

        df = pd.DataFrame(shots)

        if df.empty:
            logger.warning(f"No shot data found for game {game_id}")
        else:
            logger.info(f"Extracted {len(df)} shots for game {game_id}")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape shot chart for game {game_id}: {e}")
        return pd.DataFrame()


# ==============================================================================
# ACB HTML Scrapers
# ==============================================================================


def scrape_acb_schedule_page(season: str) -> pd.DataFrame:
    """
    Scrape ACB schedule/results page.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with ACB schedule

    Note: Implementation depends on actual ACB website structure.
    This is a template that needs to be customized.
    """
    logger.info(f"Scraping ACB schedule for season {season}")

    # ACB URL pattern (example - verify actual structure)
    url = f"https://www.acb.com/resultados-clasificacion/calendario?season={season}"

    try:
        rate_limiter.wait()
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Parse schedule table
        # This is highly dependent on ACB's actual HTML structure
        df = parse_html_table(
            soup,
            table_selector="table.fixtures",  # Adjust based on actual structure
            column_map={
                "Fecha": "GAME_DATE",
                "Local": "HOME_TEAM",
                "Visitante": "AWAY_TEAM",
                "Resultado": "SCORE",
                # Add more mappings as needed
            }
        )

        # Add league and season
        df["LEAGUE"] = "ACB"
        df["SEASON"] = season

        # Generate game IDs (ACB-specific format)
        df["GAME_ID"] = [f"ACB_{season}_{i:03d}" for i in range(len(df))]

        logger.info(f"Scraped {len(df)} ACB games")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape ACB schedule: {e}")
        return pd.DataFrame()


# ==============================================================================
# LNB HTML Scrapers
# ==============================================================================


def scrape_lnb_stats_table(stats_url: str, league: str = "LNB", season: str = None) -> pd.DataFrame:
    """
    Scrape LNB Stats Centre table.

    Generic stats table scraper for LNB player/team season stats.

    Args:
        stats_url: URL of stats page
        league: League code (default: "LNB")
        season: Season string

    Returns:
        DataFrame with stats

    Example:
        >>> url = "https://lnb.fr/stats/joueurs?season=2023-24"
        >>> df = scrape_lnb_stats_table(url, "LNB", "2023-24")
    """
    logger.info(f"Scraping LNB stats from: {stats_url}")

    try:
        rate_limiter.wait()
        response = requests.get(stats_url, headers=DEFAULT_HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find stats table (adjust selector based on actual structure)
        df = parse_html_table(
            soup,
            table_selector="table.stats",  # Adjust based on actual structure
        )

        # Add league and season
        if not df.empty:
            df["LEAGUE"] = league
            if season:
                df["SEASON"] = season

        logger.info(f"Scraped {len(df)} rows from LNB stats table")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape LNB stats: {e}")
        return pd.DataFrame()
