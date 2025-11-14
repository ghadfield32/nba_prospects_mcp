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
# Shared Parsing Utilities
# ==============================================================================


def parse_makes_attempts(text: str) -> Tuple[int, int]:
    """
    Parse makes/attempts format into separate values.

    Handles various formats: "5/10", "5-10", "5 / 10", "5 - 10"
    Used by ACB, LNB, and other leagues for FGM/FGA, FTM/FTA, etc.

    Args:
        text: String in format "made/attempted" or "made-attempted"

    Returns:
        Tuple of (made, attempted) as integers

    Example:
        >>> parse_makes_attempts("5/10")
        (5, 10)
        >>> parse_makes_attempts("3-7")
        (3, 7)
        >>> parse_makes_attempts("invalid")
        (0, 0)
    """
    try:
        # Handle both "/" and "-" separators, with optional spaces
        text = str(text).strip()
        if "/" in text:
            parts = text.split("/")
        elif "-" in text:
            parts = text.split("-")
        else:
            return 0, 0

        if len(parts) == 2:
            made = int(parts[0].strip())
            attempted = int(parts[1].strip())
            return made, attempted
    except (ValueError, AttributeError):
        pass

    return 0, 0


def parse_french_time(time_str: str) -> str:
    """
    Parse French time format to standard HH:MM format.

    Converts "12h30" → "12:30", "9h00" → "09:00"
    Used by LNB Pro A and other French leagues.

    Args:
        time_str: French format time string (e.g., "12h30")

    Returns:
        Standard format time string (e.g., "12:30")

    Example:
        >>> parse_french_time("12h30")
        '12:30'
        >>> parse_french_time("9h00")
        '09:00'
    """
    try:
        time_str = str(time_str).strip()
        if "h" in time_str.lower():
            return time_str.replace("h", ":").replace("H", ":")
        return time_str
    except Exception:
        return time_str


def split_makes_attempts_columns(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    separator: str = "/",
) -> pd.DataFrame:
    """
    Split makes/attempts columns into separate made and attempted columns.

    Handles columns like "FGM-FGA" containing "5/10" format.
    Creates two new columns: "FGM" and "FGA" with numeric values.
    Used by ACB, LNB, and FIBA leagues.

    Args:
        df: DataFrame with makes/attempts columns
        columns: List of column names to split (e.g., ["FGM-FGA", "FTM-FTA"])
                If None, auto-detects columns with "-" in name
        separator: Character separating makes from attempts in cell values

    Returns:
        DataFrame with split columns

    Example:
        >>> df = pd.DataFrame({"FGM-FGA": ["5/10", "3/8"]})
        >>> df = split_makes_attempts_columns(df, ["FGM-FGA"])
        >>> print(df[["FGM", "FGA"]])
           FGM  FGA
        0    5   10
        1    3    8
    """
    # Auto-detect columns if not specified
    if columns is None:
        columns = [col for col in df.columns if "-" in col and col.count("-") == 1]

    for col in columns:
        if col not in df.columns:
            continue

        # Extract column names (e.g., "FGM-FGA" → "FGM", "FGA")
        parts = col.split("-")
        if len(parts) != 2:
            continue

        made_col, attempt_col = parts

        # Parse each cell
        split_data = df[col].apply(lambda x: parse_makes_attempts(str(x)))
        df[made_col] = split_data.apply(lambda x: x[0])
        df[attempt_col] = split_data.apply(lambda x: x[1])

        # Drop original column
        df = df.drop(columns=[col])

    return df


# Column mapping constants for multilingual support
ACB_COLUMN_MAP = {
    "Jugador": "PLAYER_NAME",
    "Player": "PLAYER_NAME",
    "Nombre": "PLAYER_NAME",
    "Min": "MIN",
    "Minutos": "MIN",
    "Puntos": "PTS",
    "Pts": "PTS",
    "T2": "FG2M-FG2A",  # 2-point field goals
    "T3": "FG3M-FG3A",  # 3-point field goals
    "TC": "FGM-FGA",    # Total field goals
    "TL": "FTM-FTA",    # Free throws (tiros libres)
    "RO": "OREB",       # Offensive rebounds (rebotes ofensivos)
    "RD": "DREB",       # Defensive rebounds (rebotes defensivos)
    "RT": "REB",        # Total rebounds (rebotes totales)
    "Rebotes": "REB",
    "AS": "AST",
    "Asistencias": "AST",
    "BR": "STL",        # Steals (balones recuperados)
    "Robos": "STL",
    "BP": "TOV",        # Turnovers (balones perdidos)
    "Pérdidas": "TOV",
    "TAP": "BLK",       # Blocks (tapones)
    "FC": "PF",         # Personal fouls (faltas cometidas)
    "Faltas": "PF",
    "+/-": "PLUS_MINUS",
    "Val": "EFF",       # Efficiency rating (valoración)
}

LNB_COLUMN_MAP = {
    "Joueur": "PLAYER_NAME",
    "Player": "PLAYER_NAME",
    "Nom": "PLAYER_NAME",
    "Équipe": "TEAM",
    "Team": "TEAM",
    "Equipe": "TEAM",
    "MJ": "GP",          # Matches jouées (games played)
    "Matches": "GP",
    "TC": "GS",          # Titularisations (games started)
    "Min": "MIN",
    "Minutes": "MIN",
    "Pts": "PTS",
    "Points": "PTS",
    "2PTS": "FG2M-FG2A",
    "3PTS": "FG3M-FG3A",
    "LF": "FTM-FTA",     # Lancers francs (free throws)
    "RO": "OREB",        # Rebonds offensifs
    "RD": "DREB",        # Rebonds défensifs
    "RT": "REB",         # Rebonds totaux
    "Rebonds": "REB",
    "PD": "AST",         # Passes décisives (assists)
    "Passes": "AST",
    "Int": "STL",        # Interceptions (steals)
    "CT": "BLK",         # Contres (blocks)
    "BP": "TOV",         # Balles perdues (turnovers)
    "Pertes": "TOV",
    "FP": "PF",          # Fautes personnelles (personal fouls)
    "Fautes": "PF",
    "Eval": "EFF",       # Évaluation (efficiency)
    "+/-": "PLUS_MINUS",
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
    Scrape ACB (Liga Endesa) schedule/results page to extract games.

    Scrapes the official ACB calendar/results pages to build a complete schedule
    with game IDs, dates, teams, scores, and links to game centres.

    Args:
        season: Season ending year as string (e.g., "2024" for 2024-25 season)
                ACB uses ending year in URLs (temporada_id/2025 for 2024-25)

    Returns:
        DataFrame with columns:
        - LEAGUE: "ACB"
        - SEASON: Season string
        - GAME_ID: Extracted from game centre URL or generated
        - GAME_DATE: Game date
        - GAME_TIME: Game time (if available)
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (if final)
        - AWAY_SCORE: Away team score (if final)
        - ROUND: Round/jornada number
        - VENUE: Venue name (if available)
        - GAME_URL: Link to game centre page
        - COMPETITION: "Liga Endesa"
        - PHASE: "Regular Season" or "Playoffs"
        - SOURCE: "acb_html_schedule"

    Example:
        >>> df = scrape_acb_schedule_page("2024")
        >>> print(df[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "GAME_ID"]].head())

    Note:
        - ACB website structure may change; scraper may need updates
        - Some games may not have game centres yet (future games)
        - Game IDs are extracted from partido/{id} URLs when available
    """
    logger.info(f"Scraping ACB schedule for season {season}")

    # ACB uses ending year in URLs
    # 2024-25 season = temporada_id/2025
    temporada_id = int(season) if season.isdigit() else int(season.split("-")[1])

    # ACB calendar/results URL
    calendar_url = f"https://www.acb.com/resultados-clasificacion/ver/temporada_id/{temporada_id}"

    try:
        rate_limiter.wait()
        response = requests.get(calendar_url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        games = []

        # ACB schedule is typically organized by rounds/jornadas
        # Look for game containers - structure varies, so we use multiple strategies

        # Strategy 1: Find all game links (partido pages)
        game_links = soup.find_all("a", href=re.compile(r"/partido/\d+"))

        logger.info(f"Found {len(game_links)} ACB game links")

        for link in game_links:
            href = link.get("href", "")

            # Extract game ID from URL (e.g., /partido/12345)
            game_id_match = re.search(r"/partido/(\d+)", href)
            game_id = f"ACB_{game_id_match.group(1)}" if game_id_match else None

            # Build full URL
            game_url = urljoin("https://www.acb.com", href)

            # Try to extract context from parent container
            parent = link.find_parent(["div", "tr", "li"])

            if not parent:
                # Minimal info - just save the game URL
                games.append({
                    "LEAGUE": "ACB",
                    "SEASON": season,
                    "GAME_ID": game_id,
                    "GAME_DATE": None,
                    "GAME_TIME": None,
                    "HOME_TEAM": None,
                    "AWAY_TEAM": None,
                    "HOME_SCORE": None,
                    "AWAY_SCORE": None,
                    "ROUND": None,
                    "VENUE": None,
                    "GAME_URL": game_url,
                    "COMPETITION": "Liga Endesa",
                    "PHASE": "Regular Season",
                    "SOURCE": "acb_html_schedule",
                })
                continue

            # Extract all text from parent
            parent_text = parent.get_text(separator=" ", strip=True)

            # Extract date (various Spanish formats)
            # e.g., "12/10/2024", "12-10-2024", "12.10.2024"
            date_match = re.search(r"(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})", parent_text)
            game_date = date_match.group(1) if date_match else None

            # Extract time (e.g., "20:30", "18:00")
            time_match = re.search(r"(\d{1,2}:\d{2})", parent_text)
            game_time = time_match.group(1) if time_match else None

            # Extract score (e.g., "85-72", "85 - 72", "85:72")
            score_match = re.search(r"(\d{1,3})\s*[-:]\s*(\d{1,3})", parent_text)
            home_score = int(score_match.group(1)) if score_match else None
            away_score = int(score_match.group(2)) if score_match else None

            # Extract round/jornada (e.g., "Jornada 5", "J.5")
            round_match = re.search(r"J(?:ornada)?[\s\.]?(\d+)", parent_text, re.IGNORECASE)
            round_num = round_match.group(1) if round_match else None

            # Extract team names - look for team name elements
            team_elements = parent.find_all(["span", "div"], class_=re.compile(r"team|equipo", re.IGNORECASE))

            if len(team_elements) >= 2:
                home_team = team_elements[0].get_text(strip=True)
                away_team = team_elements[1].get_text(strip=True)
            else:
                # Fallback: try to extract from link text
                link_text = link.get_text(strip=True)
                # Pattern: "Team A vs Team B" or "Team A - Team B"
                vs_match = re.search(r"(.+?)\s+(?:vs|v\.|-)?\s+(.+)", link_text)
                home_team = vs_match.group(1).strip() if vs_match else None
                away_team = vs_match.group(2).strip() if vs_match else None

            games.append({
                "LEAGUE": "ACB",
                "SEASON": season,
                "GAME_ID": game_id,
                "GAME_DATE": game_date,
                "GAME_TIME": game_time,
                "HOME_TEAM": home_team,
                "AWAY_TEAM": away_team,
                "HOME_SCORE": home_score,
                "AWAY_SCORE": away_score,
                "ROUND": round_num,
                "VENUE": None,  # Can be extracted if present
                "GAME_URL": game_url,
                "COMPETITION": "Liga Endesa",
                "PHASE": "Regular Season",  # Can be refined if playoffs indicated
                "SOURCE": "acb_html_schedule",
            })

        df = pd.DataFrame(games)

        # Remove duplicates (same game might be linked multiple times)
        if not df.empty:
            df = df.drop_duplicates(subset=["GAME_ID"], keep="first")

        logger.info(f"Extracted {len(df)} unique ACB games from schedule")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape ACB schedule: {e}")
        return pd.DataFrame()


def scrape_acb_game_centre(game_url: str, game_id: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Scrape ACB game centre page to extract boxscore data.

    Parses individual game pages to extract player and team statistics from
    boxscore tables. Returns both player-level and team-level data.

    Args:
        game_url: URL of ACB game centre page (e.g., https://www.acb.com/partido/12345)
        game_id: Optional game ID (extracted from URL if not provided)

    Returns:
        Tuple of (player_game_df, team_game_df):
        - player_game_df: DataFrame with player box scores
          Columns: GAME_ID, TEAM, PLAYER_NAME, MIN, PTS, FGM, FGA, FG3M, FG3A,
                   FTM, FTA, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PLUS_MINUS
        - team_game_df: DataFrame with team totals
          Columns: GAME_ID, TEAM, MIN, PTS, FGM, FGA, etc. (same structure)

    Example:
        >>> player_df, team_df = scrape_acb_game_centre("https://www.acb.com/partido/12345")
        >>> print(f"Players: {len(player_df)}, Teams: {len(team_df)}")

    Note:
        - Returns empty DataFrames if scraping fails
        - ACB boxscores have two tables (one per team)
        - Table structure may vary by season - adjust selectors as needed
    """
    if not game_id:
        # Extract game ID from URL
        match = re.search(r"/partido/(\d+)", game_url)
        game_id = f"ACB_{match.group(1)}" if match else None

    logger.info(f"Scraping ACB game centre: {game_id}")

    try:
        rate_limiter.wait()
        response = requests.get(game_url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find boxscore tables - typically 2 tables (home + away)
        # ACB uses various class names, so we search flexibly
        boxscore_tables = soup.find_all("table", class_=re.compile(r"stats|boxscore|estadisticas", re.IGNORECASE))

        if not boxscore_tables:
            # Fallback: find all tables and filter by size
            all_tables = soup.find_all("table")
            boxscore_tables = [t for t in all_tables if len(t.find_all("tr")) > 5]

        logger.info(f"Found {len(boxscore_tables)} potential boxscore tables")

        all_player_stats = []
        all_team_stats = []

        for table_idx, table in enumerate(boxscore_tables[:2]):  # Limit to first 2 tables
            # Extract team name from context
            team_header = table.find_previous(["h2", "h3", "div"], class_=re.compile(r"team|equipo", re.IGNORECASE))
            team_name = team_header.get_text(strip=True) if team_header else f"Team {table_idx + 1}"

            # Parse table to DataFrame
            df = parse_html_table(table)

            if df.empty:
                continue

            # Apply ACB Spanish column mapping (using shared constant)
            df = df.rename(columns={k: v for k, v in ACB_COLUMN_MAP.items() if k in df.columns})

            # Add metadata
            df["GAME_ID"] = game_id
            df["TEAM"] = team_name

            # Separate totals row (usually last row or marked as "TOTAL")
            totals_row = None
            if not df.empty:
                last_row = df.iloc[-1]
                if isinstance(last_row.get("PLAYER_NAME"), str):
                    if "total" in last_row["PLAYER_NAME"].lower():
                        totals_row = df.iloc[[-1]].copy()
                        df = df.iloc[:-1]  # Remove totals from player stats

            # Process makes/attempts columns using shared utility
            # Handles columns like "FGM-FGA" containing "5/10" format
            df = split_makes_attempts_columns(df, columns=["FGM-FGA", "FG2M-FG2A", "FG3M-FG3A", "FTM-FTA"])

            all_player_stats.append(df)

            if totals_row is not None:
                all_team_stats.append(totals_row)

        # Combine all player stats
        if all_player_stats:
            player_game_df = pd.concat(all_player_stats, ignore_index=True)
        else:
            player_game_df = pd.DataFrame()

        # Combine team stats
        if all_team_stats:
            team_game_df = pd.concat(all_team_stats, ignore_index=True)
        else:
            team_game_df = pd.DataFrame()

        logger.info(f"Extracted {len(player_game_df)} player stats, {len(team_game_df)} team stats")

        return player_game_df, team_game_df

    except Exception as e:
        logger.error(f"Failed to scrape ACB game centre {game_id}: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ==============================================================================
# LNB HTML Scrapers
# ==============================================================================


def scrape_lnb_player_season_html(season: str) -> pd.DataFrame:
    """
    Scrape LNB Pro A player season statistics from Stats Centre HTML tables.

    Parses the official LNB Pro A statistics page to extract comprehensive
    player season data including scoring, rebounding, assists, efficiency, etc.

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with columns:
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - PLAYER_NAME: Player name
        - TEAM: Team name
        - GP: Games played
        - GS: Games started (if available)
        - MIN: Total minutes
        - MIN_PG: Minutes per game
        - PTS: Total points
        - PTS_PG: Points per game
        - FGM, FGA, FG_PCT: Field goals
        - FG3M, FG3A, FG3_PCT: Three pointers
        - FTM, FTA, FT_PCT: Free throws
        - OREB, DREB, REB, REB_PG: Rebounds
        - AST, AST_PG: Assists
        - STL, STL_PG: Steals
        - BLK, BLK_PG: Blocks
        - TOV, TOV_PG: Turnovers
        - PF: Personal fouls
        - EFF: Efficiency rating
        - SOURCE: "lnb_html_playerstats"

    Example:
        >>> df = scrape_lnb_player_season_html("2024")
        >>> top_scorers = df.nlargest(10, "PTS_PG")
        >>> print(top_scorers[["PLAYER_NAME", "TEAM", "PTS_PG"]])

    Note:
        - LNB website may use JavaScript for some tables - check if Selenium needed
        - Column names are in French - mapping to English provided
        - Stats page URL structure may change per season
    """
    logger.info(f"Scraping LNB Pro A player season stats for {season}")

    # LNB Pro A stats URL - adjust for actual structure
    # The site has different views; we want the full per-game stats table
    stats_url = f"https://www.lnb.fr/pro-a/statistiques"

    try:
        rate_limiter.wait()
        response = requests.get(stats_url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # LNB player stats are typically in a large HTML table
        # Find the main stats table - try multiple selectors
        table = None

        # Try common class names
        for selector in ["table.stats-table", "table.statistiques", "table", "#player-stats-table"]:
            table = soup.select_one(selector)
            if table:
                logger.info(f"Found table with selector: {selector}")
                break

        if not table:
            logger.warning("No stats table found on page")
            return pd.DataFrame()

        # Parse table
        df = parse_html_table(table)

        if df.empty:
            logger.warning("Parsed table is empty")
            return pd.DataFrame()

        logger.info(f"Parsed table with {len(df)} rows and {len(df.columns)} columns")

        # Apply LNB French column mapping (using shared constant)
        df = df.rename(columns={k: v for k, v in LNB_COLUMN_MAP.items() if k in df.columns})

        # Process makes/attempts columns using shared utility
        # LNB uses both "/" and "-" separators
        df = split_makes_attempts_columns(df, columns=["FG2M-FG2A", "FG3M-FG3A", "FTM-FTA"])

        # Calculate FGM/FGA from 2PT + 3PT if needed
        if "FG2M" in df.columns and "FG3M" in df.columns and "FGM" not in df.columns:
            df["FGM"] = df["FG2M"] + df["FG3M"]
            df["FGA"] = df["FG2A"] + df["FG3A"]

        # Calculate per-game stats if not present
        if "GP" in df.columns:
            gp = df["GP"].replace(0, 1)  # Avoid division by zero

            for stat in ["MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF"]:
                if stat in df.columns and f"{stat}_PG" not in df.columns:
                    df[f"{stat}_PG"] = (df[stat] / gp).round(1)

        # Calculate shooting percentages if not present
        if "FGM" in df.columns and "FGA" in df.columns and "FG_PCT" not in df.columns:
            df["FG_PCT"] = (df["FGM"] / df["FGA"].replace(0, 1) * 100).round(1)

        if "FG3M" in df.columns and "FG3A" in df.columns and "FG3_PCT" not in df.columns:
            df["FG3_PCT"] = (df["FG3M"] / df["FG3A"].replace(0, 1) * 100).round(1)

        if "FTM" in df.columns and "FTA" in df.columns and "FT_PCT" not in df.columns:
            df["FT_PCT"] = (df["FTM"] / df["FTA"].replace(0, 1) * 100).round(1)

        # Add metadata
        df["LEAGUE"] = "LNB_PROA"
        df["SEASON"] = season
        df["COMPETITION"] = "LNB Pro A"
        df["SOURCE"] = "lnb_html_playerstats"

        # Filter out header/footer rows that may have been included
        if "PLAYER_NAME" in df.columns:
            df = df[df["PLAYER_NAME"].notna()]
            df = df[~df["PLAYER_NAME"].str.contains("Joueur|Player|Total", case=False, na=False)]

        logger.info(f"Extracted {len(df)} LNB player season stats")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape LNB player season stats: {e}")
        return pd.DataFrame()


def scrape_lnb_schedule_page(season: str) -> pd.DataFrame:
    """
    Scrape LNB Pro A schedule/results page.

    **OPTIONAL**: This function is a best-effort scraper for LNB schedule data.
    LNB schedule pages may be JavaScript-heavy; if this returns empty, consider:
    1. Using Selenium/Playwright for JavaScript rendering
    2. Reverse-engineering internal APIs (see tools/lnb/README.md)
    3. Manual CSV creation from website

    Args:
        season: Season year as string (e.g., "2024" for 2024-25 season)

    Returns:
        DataFrame with schedule or empty DataFrame if scraping fails

    Columns (if successful):
        - LEAGUE: "LNB_PROA"
        - SEASON: Season string
        - GAME_ID: Generated or extracted game ID
        - GAME_DATE: Game date
        - GAME_TIME: Game time
        - HOME_TEAM: Home team
        - AWAY_TEAM: Away team
        - HOME_SCORE: Home score (if final)
        - AWAY_SCORE: Away score (if final)
        - ROUND: Round number
        - VENUE: Venue name
        - GAME_URL: Link to game page
        - SOURCE: "lnb_html_schedule"

    Example:
        >>> df = scrape_lnb_schedule_page("2024")
        >>> if not df.empty:
        ...     print(df[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())

    Note:
        Returns empty DataFrame if:
        - Page requires JavaScript execution
        - HTML structure has changed
        - No games found for season
    """
    logger.info(f"Scraping LNB Pro A schedule for {season}")

    # LNB Pro A schedule URL (verify actual structure)
    schedule_url = f"https://www.lnb.fr/pro-a/calendrier-resultats"

    try:
        rate_limiter.wait()
        response = requests.get(schedule_url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        games = []

        # Look for game links or containers
        # LNB typically uses match cards or table rows
        game_containers = soup.find_all(["div", "tr"], class_=re.compile(r"match|game|rencontre", re.IGNORECASE))

        if not game_containers:
            # Try finding links to individual games
            game_links = soup.find_all("a", href=re.compile(r"/match/|/rencontre/"))
            game_containers = [link.find_parent(["div", "tr"]) for link in game_links if link.find_parent(["div", "tr"])]

        logger.info(f"Found {len(game_containers)} potential game containers")

        for idx, container in enumerate(game_containers):
            if not container:
                continue

            # Extract text from container
            container_text = container.get_text(separator=" ", strip=True)

            # Extract date (French format: "12/10/2024" or "12 octobre 2024")
            date_match = re.search(r"(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})", container_text)
            game_date = date_match.group(1) if date_match else None

            # Extract time (French format: "12h30" or standard "12:30")
            time_match = re.search(r"(\d{1,2}h\d{2}|\d{1,2}:\d{2})", container_text)
            game_time = parse_french_time(time_match.group(1)) if time_match else None

            # Extract score
            score_match = re.search(r"(\d{1,3})\s*[-:]\s*(\d{1,3})", container_text)
            home_score = int(score_match.group(1)) if score_match else None
            away_score = int(score_match.group(2)) if score_match else None

            # Extract round
            round_match = re.search(r"J\.?\s*(\d+)|Journée\s*(\d+)", container_text, re.IGNORECASE)
            round_num = (round_match.group(1) or round_match.group(2)) if round_match else None

            # Extract team names - challenging without knowing structure
            # Look for team name elements
            team_elements = container.find_all(["span", "div"], class_=re.compile(r"team|equipe", re.IGNORECASE))

            if len(team_elements) >= 2:
                home_team = team_elements[0].get_text(strip=True)
                away_team = team_elements[1].get_text(strip=True)
            else:
                home_team = None
                away_team = None

            # Extract game URL
            game_link = container.find("a", href=re.compile(r"/match/|/rencontre/"))
            game_url = urljoin("https://www.lnb.fr", game_link.get("href")) if game_link else None

            # Generate game ID
            game_id = f"LNB_{season}_{idx+1:03d}"
            if game_link:
                id_match = re.search(r"/(?:match|rencontre)/(\d+)", game_link.get("href", ""))
                if id_match:
                    game_id = f"LNB_{id_match.group(1)}"

            games.append({
                "LEAGUE": "LNB_PROA",
                "SEASON": season,
                "GAME_ID": game_id,
                "GAME_DATE": game_date,
                "GAME_TIME": game_time,
                "HOME_TEAM": home_team,
                "AWAY_TEAM": away_team,
                "HOME_SCORE": home_score,
                "AWAY_SCORE": away_score,
                "ROUND": round_num,
                "VENUE": None,
                "GAME_URL": game_url,
                "COMPETITION": "LNB Pro A",
                "PHASE": "Regular Season",
                "SOURCE": "lnb_html_schedule",
            })

        df = pd.DataFrame(games)

        # Remove duplicates
        if not df.empty:
            df = df.drop_duplicates(subset=["GAME_ID"], keep="first")

        logger.info(f"Extracted {len(df)} LNB games from schedule")

        return df

    except Exception as e:
        logger.error(f"Failed to scrape LNB schedule: {e}")
        return pd.DataFrame()


# ============================================================================
# OPTIONAL ENHANCEMENTS - Competition Tagging
# ============================================================================


def tag_acb_competition(schedule_df: pd.DataFrame) -> pd.DataFrame:
    """Tag ACB games with competition type (Liga Regular, Playoffs, Copa del Rey)

    **OPTIONAL ENHANCEMENT** - Adds COMPETITION and PHASE columns to ACB schedule.

    ACB has multiple competitions throughout the season:
    - **Liga Regular**: Regular season (18 teams, ~34 games each, Oct-May)
    - **Playoffs**: Top 8 teams, best-of-5 series (May-June)
    - **Copa del Rey**: Knockout tournament (mid-season, February)
    - **Supercopa**: Preseason tournament (September)

    This function attempts to infer competition type from:
    1. Game dates (Copa del Rey typically in February)
    2. Round numbers (Playoffs: "1/4 Final", "Semifinal", "Final")
    3. URL patterns (acb.com URLs may contain competition codes)
    4. Team counts (Copa/Supercopa have limited teams)

    Args:
        schedule_df: ACB schedule DataFrame with columns:
            - GAME_DATE: Game date (required)
            - ROUND: Round number or name (optional)
            - GAME_URL: Link to game page (optional)
            - HOME_TEAM, AWAY_TEAM: Team names

    Returns:
        DataFrame with added columns:
            - COMPETITION: "Liga Regular", "Playoffs", "Copa del Rey", or "Supercopa"
            - PHASE: More specific phase ("Regular Season", "Quarterfinals", etc.)

    Example:
        >>> from src.cbb_data.fetchers.acb import fetch_acb_schedule
        >>> from src.cbb_data.fetchers.html_scrapers import tag_acb_competition
        >>>
        >>> # Fetch ACB schedule
        >>> schedule = fetch_acb_schedule("2023-24")
        >>>
        >>> # Tag competitions
        >>> schedule_tagged = tag_acb_competition(schedule)
        >>>
        >>> # Analyze by competition
        >>> competition_counts = schedule_tagged["COMPETITION"].value_counts()
        >>> print(competition_counts)

    Note:
        - **NOT YET FULLY IMPLEMENTED** - Currently uses heuristics
        - Requires inspection of actual ACB schedule HTML structure
        - May need manual mapping for historical seasons
        - ACB website structure may change annually

    **TO IMPLEMENT** (requires website inspection):
    1. Visit https://www.acb.com/calendario for current season
    2. Identify how ACB marks different competitions in HTML
    3. Check for class names, data attributes, or URL patterns
    4. Update detection logic below with actual patterns
    5. Test against multiple seasons for robustness

    See Also:
        - scrape_acb_schedule_page(): Main ACB schedule scraper
        - tag_lnb_competition(): Similar function for LNB Pro A
    """
    logger.info("Tagging ACB games with competition type (OPTIONAL ENHANCEMENT)")

    if schedule_df.empty:
        logger.warning("Empty schedule, cannot tag competitions")
        return schedule_df

    if "GAME_DATE" not in schedule_df.columns:
        logger.warning("Schedule missing GAME_DATE column, cannot tag competitions")
        return schedule_df

    # Initialize competition columns
    schedule_df["COMPETITION"] = "Liga Regular"  # Default
    schedule_df["PHASE"] = "Regular Season"
    schedule_df["CONFIDENCE"] = 0.5  # Default confidence (50% - pure guess)

    try:
        # Convert GAME_DATE to datetime for date-based detection
        schedule_df["_GAME_DATE_DT"] = pd.to_datetime(schedule_df["GAME_DATE"], errors="coerce")

        # Extract month for seasonal patterns
        schedule_df["_MONTH"] = schedule_df["_GAME_DATE_DT"].dt.month

        # Confidence scores for each detection method
        confidence_scores = pd.Series(0.5, index=schedule_df.index)  # Start at 0.5

        # === HEURISTIC 1: Date-based Detection ===
        # Copa del Rey (typically February, confidence: +0.3)
        copa_mask = (schedule_df["_MONTH"] == 2)
        confidence_scores[copa_mask] = 0.8

        # Supercopa (typically September, confidence: +0.3)
        supercopa_mask = (schedule_df["_MONTH"] == 9)
        confidence_scores[supercopa_mask] = 0.8

        # Playoffs (May-June, confidence: +0.2)
        playoffs_mask = (schedule_df["_MONTH"].isin([5, 6]))
        confidence_scores[playoffs_mask] = 0.7

        # === HEURISTIC 2: Round-based Detection ===
        if "ROUND" in schedule_df.columns:
            # Playoff rounds (confidence: +0.3)
            playoff_rounds = schedule_df["ROUND"].astype(str).str.contains(
                r"Final|Semifinal|Cuartos|1/4|1/2",
                case=False,
                regex=True,
                na=False
            )
            playoffs_mask = playoffs_mask | playoff_rounds
            confidence_scores[playoff_rounds] = confidence_scores[playoff_rounds] + 0.3

        # === HEURISTIC 3: URL Pattern Detection (if available) ===
        # HTML inspection guide: Look for these patterns in actual ACB URLs
        # - Copa: /copa-del-rey/, /copa/
        # - Supercopa: /supercopa/, /spanish-supercup/
        # - Playoffs: /playoff/, /finals/
        if "GAME_URL" in schedule_df.columns:
            url_series = schedule_df["GAME_URL"].astype(str).str.lower()

            # Copa URL patterns (confidence: +0.4)
            copa_url_mask = url_series.str.contains(r"copa-del-rey|copa/", case=False, regex=True, na=False)
            copa_mask = copa_mask | copa_url_mask
            confidence_scores[copa_url_mask] = 0.9

            # Supercopa URL patterns (confidence: +0.4)
            supercopa_url_mask = url_series.str.contains(r"supercopa|spanish-supercup", case=False, regex=True, na=False)
            supercopa_mask = supercopa_mask | supercopa_url_mask
            confidence_scores[supercopa_url_mask] = 0.9

            # Playoff URL patterns (confidence: +0.3)
            playoff_url_mask = url_series.str.contains(r"playoff|finals", case=False, regex=True, na=False)
            playoffs_mask = playoffs_mask | playoff_url_mask
            confidence_scores[playoff_url_mask] = confidence_scores[playoff_url_mask] + 0.3

        # === HEURISTIC 4: Team Count Detection ===
        # Group by date to detect unique teams per game day
        # Copa del Rey: 8 teams (4 games max per day in later rounds)
        # Supercopa: 4 teams (2 games max per day)
        # This is more complex and requires careful grouping
        if "HOME_TEAM" in schedule_df.columns and "AWAY_TEAM" in schedule_df.columns:
            # For Copa/Supercopa, limited team sets in short time windows
            # Group games by week
            schedule_df["_WEEK"] = schedule_df["_GAME_DATE_DT"].dt.isocalendar().week

            for week in schedule_df["_WEEK"].unique():
                if pd.isna(week):
                    continue

                week_mask = schedule_df["_WEEK"] == week
                week_df = schedule_df[week_mask]

                # Get unique teams in this week
                teams_in_week = set(week_df["HOME_TEAM"]).union(set(week_df["AWAY_TEAM"]))
                team_count = len(teams_in_week)

                # Supercopa: 4 teams, 3 games total (2 semis + final)
                if team_count == 4 and len(week_df) <= 3 and schedule_df.loc[week_mask, "_MONTH"].iloc[0] == 9:
                    supercopa_mask[week_mask] = True
                    confidence_scores[week_mask] = 0.95

                # Copa del Rey: 8-16 teams in knockout rounds (harder to detect)
                elif team_count <= 16 and schedule_df.loc[week_mask, "_MONTH"].iloc[0] == 2:
                    copa_mask[week_mask] = True
                    confidence_scores[week_mask] = confidence_scores[week_mask] + 0.1

            # Clean up temporary week column
            schedule_df = schedule_df.drop(columns=["_WEEK"], errors="ignore")

        # === Apply Competition Tags ===
        schedule_df.loc[copa_mask, "COMPETITION"] = "Copa del Rey"
        schedule_df.loc[copa_mask, "PHASE"] = "Knockout Tournament"

        schedule_df.loc[supercopa_mask, "COMPETITION"] = "Supercopa"
        schedule_df.loc[supercopa_mask, "PHASE"] = "Preseason Tournament"

        schedule_df.loc[playoffs_mask, "COMPETITION"] = "Playoffs"

        # === Further Classify Playoff Phases ===
        if "ROUND" in schedule_df.columns:
            # Quarterfinals
            qf_mask = playoffs_mask & schedule_df["ROUND"].astype(str).str.contains(
                r"Cuartos|1/4|Quarterfinal",
                case=False,
                regex=True,
                na=False
            )
            schedule_df.loc[qf_mask, "PHASE"] = "Quarterfinals"
            confidence_scores[qf_mask] = 0.9

            # Semifinals
            sf_mask = playoffs_mask & schedule_df["ROUND"].astype(str).str.contains(
                r"Semifinal|1/2",
                case=False,
                regex=True,
                na=False
            )
            schedule_df.loc[sf_mask, "PHASE"] = "Semifinals"
            confidence_scores[sf_mask] = 0.9

            # Finals
            f_mask = playoffs_mask & schedule_df["ROUND"].astype(str).str.contains(
                r"^Final$|Finale",
                case=False,
                regex=True,
                na=False
            )
            schedule_df.loc[f_mask, "PHASE"] = "Finals"
            confidence_scores[f_mask] = 0.95

        # === Assign Confidence Scores ===
        # Cap confidence at 0.95 (never 100% certain with heuristics)
        schedule_df["CONFIDENCE"] = confidence_scores.clip(upper=0.95)

        # Clean up temporary columns
        schedule_df = schedule_df.drop(columns=["_GAME_DATE_DT", "_MONTH"], errors="ignore")

        # Log distribution
        competition_counts = schedule_df["COMPETITION"].value_counts()
        logger.info(f"Competition distribution: {competition_counts.to_dict()}")

        # Log confidence distribution
        avg_confidence = schedule_df["CONFIDENCE"].mean()
        logger.info(f"Average confidence score: {avg_confidence:.2f}")
        low_confidence = (schedule_df["CONFIDENCE"] < 0.7).sum()
        if low_confidence > 0:
            logger.warning(f"{low_confidence} games tagged with low confidence (<0.7)")

        logger.warning(
            "ACB competition tagging uses enhanced heuristics (confidence scores included). "
            "For 100% accuracy, inspect ACB HTML at https://www.acb.com/calendario and look for:\n"
            "  - HTML class names (e.g., 'copa-game', 'playoff-game')\n"
            "  - Data attributes (e.g., data-competition='copa')\n"
            "  - URL patterns (e.g., /copa-del-rey/, /playoff/)\n"
            "Update heuristic patterns in this function with discoveries."
        )

        return schedule_df

    except Exception as e:
        logger.error(f"Failed to tag ACB competitions: {e}")
        return schedule_df
