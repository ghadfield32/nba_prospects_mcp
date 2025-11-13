"""Overtime Elite (OTE) Fetcher

Official OTE stats portal scraper.
Uses overtimeelite.com for schedule, box scores, and play-by-play data.

Key Features:
- Professional basketball league for elite high school prospects
- Alternative pathway to NBA (ages 16-20)
- Box Score + FULL Play-by-Play available on website (rare for non-NBA leagues!)

Data Granularities:
- schedule: ⚠️ Limited (requires web scraping)
- player_game: ⚠️ Limited (box scores available, requires scraping)
- team_game: ⚠️ Limited (team stats available, requires scraping)
- pbp: ✅ AVAILABLE (full play-by-play published on game pages!)
- shots: ❌ Unavailable (coordinates not published)
- player_season: ⚠️ Aggregated (from player_game data)
- team_season: ⚠️ Aggregated (from team_game data)

Data Source: https://overtimeelite.com/
Example Game with PBP: https://overtimeelite.com/games/607559e6-d366-4325-988a-4fffd3204845/box_score

Implementation Status:
Scaffold mode. Requires HTML parsing of OTE website.

Implementation Priority:
HIGH - OTE is a key NBA prospect pipeline and has rich data including PBP!

Future Enhancement Path:
1. Implement schedule scraper (OTE games page)
2. Implement box score scraper (game pages)
3. Implement play-by-play parser (UNIQUE: full PBP available!)
4. Check for JSON endpoints (OTE may have modern API)
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# OTE endpoints
OTE_BASE_URL = "https://overtimeelite.com"
OTE_GAMES_URL = f"{OTE_BASE_URL}/games"
OTE_SCHEDULE_URL = f"{OTE_BASE_URL}/schedule"

# Standard headers
OTE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": OTE_BASE_URL,
}


def _make_ote_request(url: str, params: dict[str, Any] | None = None) -> str:
    """Make a request to OTE website

    Args:
        url: Full URL to request
        params: Optional query parameters

    Returns:
        HTML content as string

    Raises:
        requests.HTTPError: If the request fails
    """
    rate_limiter.acquire("ote")

    try:
        response = requests.get(url, headers=OTE_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"OTE request failed: {url} - {e}")
        raise


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_ote_schedule(
    season: str = "2024-25",
) -> pd.DataFrame:
    """Fetch OTE schedule

    Scrapes the OTE schedule page for game information.

    Args:
        season: Season string (e.g., "2024-25") - Note: OTE website shows current season

    Returns:
        DataFrame with game schedule

    Columns:
        - GAME_ID: Unique game identifier (OTE uses UUID format)
        - SEASON: Season string
        - GAME_DATE: Game date/time
        - HOME_TEAM_ID: Home team ID
        - HOME_TEAM: Home team name
        - AWAY_TEAM_ID: Away team ID
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team score (null for upcoming games)
        - AWAY_SCORE: Away team score (null for upcoming games)
        - VENUE: Arena name
        - LEAGUE: "OTE"
    """
    logger.info(f"Fetching OTE schedule: {season}")

    # Fetch schedule page
    html = _make_ote_request(OTE_SCHEDULE_URL)
    soup = BeautifulSoup(html, "lxml")

    games = []
    processed_ids = set()

    # Find all game links (pattern: /games/{uuid}/box_score or /games/{uuid})
    game_links = soup.find_all("a", href=re.compile(r"/games/[a-f0-9\-]+"))

    for link in game_links:
        try:
            # Extract game ID from URL
            href_raw = link.get("href", "")
            href = str(href_raw) if href_raw else ""
            game_id_match = re.search(r"/games/([a-f0-9\-]+)", href)
            if not game_id_match:
                continue

            game_id = game_id_match.group(1)

            # Skip if already processed (same game appears multiple times)
            if game_id in processed_ids:
                continue

            # Find parent container with game info
            # Format: "Thu, Nov 13 | Fear of God Athletics | FGA | 3 | - | 2 | New York, NY | 6:00PM EST | Jelly Fam | JLY"
            game_container = link.find_parent()
            if not game_container:
                continue

            # Extract text content with pipe separator
            game_text = game_container.get_text(separator="|", strip=True)

            # Split by pipe and clean up
            parts = [p.strip() for p in game_text.split("|")]

            # Look for pattern: Date | Team1 | Abbr1 | Score1 | - | Score2 | Location | Time | Team2 | Abbr2
            if len(parts) < 5:
                continue

            # Try to find team names (longer text fields that aren't abbreviations)
            team_names = [p for p in parts if len(p) > 5 and not p.isdigit() and "-" not in p]

            if len(team_names) < 2:
                continue

            # First team is typically away, second is home
            away_team = team_names[0]
            home_team = team_names[1]

            # Try to extract venue (usually has city/state)
            venue = None
            for part in parts:
                if "," in part and len(part) < 30:
                    venue = part
                    break

            processed_ids.add(game_id)

            games.append(
                {
                    "GAME_ID": game_id,
                    "SEASON": season,
                    "GAME_DATE": None,  # Date parsing can be added if needed
                    "HOME_TEAM_ID": home_team,  # Using team name as ID
                    "HOME_TEAM": home_team,
                    "AWAY_TEAM_ID": away_team,
                    "AWAY_TEAM": away_team,
                    "HOME_SCORE": None,
                    "AWAY_SCORE": None,
                    "VENUE": venue,
                    "LEAGUE": "OTE",
                }
            )

        except Exception as e:
            logger.debug(f"Error parsing game: {e}")
            continue

    df = pd.DataFrame(games)

    logger.info(f"Fetched {len(df)} OTE games")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_ote_box_score(game_id: str) -> pd.DataFrame:
    """Fetch OTE box score for a game

    Scrapes player statistics from OTE game box score page.

    Args:
        game_id: Game ID (OTE UUID format, e.g., "607559e6-d366-4325-988a-4fffd3204845")

    Returns:
        DataFrame with player box scores

    Columns:
        - GAME_ID: Game identifier
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - TEAM_ID: Team ID
        - TEAM: Team name
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
        - PLUS_MINUS: Plus/minus
        - LEAGUE: "OTE"
    """
    logger.info(f"Fetching OTE box score: {game_id}")

    # Fetch box score page
    box_score_url = f"{OTE_BASE_URL}/games/{game_id}/box_score"
    html = _make_ote_request(box_score_url)
    soup = BeautifulSoup(html, "lxml")

    players = []

    # Find all tables with player stats
    # OTE uses unusual structure: player names are in headers, stats in data rows
    tables = soup.find_all("table")

    for table in tables:
        try:
            # Get headers
            headers = table.find_all("th")
            if len(headers) < 10:
                continue

            header_texts = [h.get_text(strip=True) for h in headers]

            # Check if this is a player stats table (has 'Player', 'minmin', 'ptspts', etc.)
            if not any("Player" in h for h in header_texts):
                continue

            # Extract player names from headers (they're at the end, after stats columns)
            # Format: "13Diamant Blazi" (jersey number + name)
            # Only look at headers after index 20 (to skip stat column headers)
            player_names = []
            team_name = ""

            for h_idx, header_text in enumerate(header_texts):
                if h_idx < 20:
                    # Skip stat column headers
                    continue

                # Check for player names (jersey number + name format)
                if len(header_text) > 3 and header_text[0].isdigit():
                    # Remove jersey number prefix (e.g., "13" from "13Diamant Blazi")
                    player_name = re.sub(r"^\d+", "", header_text).strip()
                    if player_name:  # Ensure name isn't empty
                        player_names.append(player_name)
                elif " " in header_text and len(header_text) > 5:
                    # Likely team name (e.g., "City Reapers")
                    if not any(
                        kw in header_text.lower() for kw in ["player", "min", "pts", "reb", "ast"]
                    ):
                        team_name = header_text

            if not player_names:
                continue

            # Get data rows (each row corresponds to a player)
            all_rows = table.find_all("tr")
            data_rows = all_rows[1:]  # Skip header row

            # IMPORTANT: Last row is team totals (skip it)
            # Only process rows for individual players
            if len(data_rows) > len(player_names):
                data_rows = data_rows[: len(player_names)]

            # Column indices (based on header order)
            # minmin, ptspts, astast, orborb, drbdrb, rebreb, stlstl, blkblk, dnkdnk,
            # 2pm2pm, 2pa2pa, 2p%2p%, 3pm3pm, 3pa3pa, 3p%3p%, fgmfgm, fgafga, fg%fg%,
            # ftmftm, ftafta, ft%ft%, +/-+/-, pfpf, toto

            for idx, row in enumerate(data_rows):
                if idx >= len(player_names):
                    break

                cells = row.find_all("td")
                if len(cells) < 15:
                    continue

                cell_values = [c.get_text(strip=True) for c in cells]

                # Skip team total rows (minutes field is often empty or special char)
                if not cell_values[0].isdigit():
                    continue

                # Parse stats (column indices based on OTE structure)
                try:
                    min_played = cell_values[0] if len(cell_values) > 0 else "0"
                    pts = int(cell_values[1]) if len(cell_values) > 1 else 0
                    ast = int(cell_values[2]) if len(cell_values) > 2 else 0
                    oreb = int(cell_values[3]) if len(cell_values) > 3 else 0
                    dreb = int(cell_values[4]) if len(cell_values) > 4 else 0
                    reb = int(cell_values[5]) if len(cell_values) > 5 else 0
                    stl = int(cell_values[6]) if len(cell_values) > 6 else 0
                    blk = int(cell_values[7]) if len(cell_values) > 7 else 0

                    # 2PM/2PA at indices 9-10, 3PM/3PA at 12-13, FGM/FGA at 15-16, FTM/FTA at 18-19
                    fg3m = int(cell_values[12]) if len(cell_values) > 12 else 0
                    fg3a = int(cell_values[13]) if len(cell_values) > 13 else 0
                    fgm = int(cell_values[15]) if len(cell_values) > 15 else 0
                    fga = int(cell_values[16]) if len(cell_values) > 16 else 0
                    ftm = int(cell_values[18]) if len(cell_values) > 18 else 0
                    fta = int(cell_values[19]) if len(cell_values) > 19 else 0

                    plus_minus = cell_values[21] if len(cell_values) > 21 else None
                    pf = int(cell_values[22]) if len(cell_values) > 22 else 0
                    tov = int(cell_values[23]) if len(cell_values) > 23 else 0

                    # Calculate percentages
                    fg_pct = (fgm / fga * 100) if fga > 0 else 0.0
                    fg3_pct = (fg3m / fg3a * 100) if fg3a > 0 else 0.0
                    ft_pct = (ftm / fta * 100) if fta > 0 else 0.0

                    player_name = player_names[idx]

                    players.append(
                        {
                            "GAME_ID": game_id,
                            "PLAYER_ID": player_name,  # Using name as ID
                            "PLAYER_NAME": player_name,
                            "TEAM_ID": team_name,
                            "TEAM": team_name,
                            "MIN": min_played,
                            "PTS": pts,
                            "FGM": fgm,
                            "FGA": fga,
                            "FG_PCT": round(fg_pct, 1),
                            "FG3M": fg3m,
                            "FG3A": fg3a,
                            "FG3_PCT": round(fg3_pct, 1),
                            "FTM": ftm,
                            "FTA": fta,
                            "FT_PCT": round(ft_pct, 1),
                            "OREB": oreb,
                            "DREB": dreb,
                            "REB": reb,
                            "AST": ast,
                            "STL": stl,
                            "BLK": blk,
                            "TOV": tov,
                            "PF": pf,
                            "PLUS_MINUS": plus_minus,
                            "LEAGUE": "OTE",
                        }
                    )

                except Exception as e:
                    logger.debug(f"Error parsing player {player_names[idx]}: {e}")
                    continue

        except Exception as e:
            logger.debug(f"Error parsing table: {e}")
            continue

    df = pd.DataFrame(players)

    logger.info(f"Fetched box score: {len(df)} players")
    return df


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_ote_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch OTE play-by-play data

    IMPORTANT: OTE publishes FULL play-by-play data on their website!
    This is rare for non-NBA leagues and provides high-value data.

    Args:
        game_id: Game ID (OTE UUID format)

    Returns:
        DataFrame with play-by-play events

    Columns:
        - GAME_ID: Game identifier
        - EVENT_NUM: Event number (sequential)
        - EVENT_TYPE: Event type (shot, foul, turnover, etc.)
        - PERIOD: Quarter/period (1-4, 5+ for OT)
        - CLOCK: Game clock (MM:SS)
        - DESCRIPTION: Play description
        - PLAYER_NAME: Player involved
        - TEAM: Team name
        - SCORE: Current score
        - LEAGUE: "OTE"
    """
    logger.info(f"Fetching OTE play-by-play: {game_id}")

    # Fetch box score page (PBP is on same page)
    box_score_url = f"{OTE_BASE_URL}/games/{game_id}/box_score"
    html = _make_ote_request(box_score_url)
    soup = BeautifulSoup(html, "lxml")

    events = []
    event_num = 0

    # Find play-by-play table
    # Look for table with headers: Time, Play, CTY, JLY (or similar team abbreviations)
    tables = soup.find_all("table")

    for table in tables:
        # Check if this is PBP table by looking for 'Time' and 'Play' headers
        headers = table.find_all("th")
        header_texts = [h.get_text(strip=True) for h in headers]

        if not ("Time" in header_texts and "Play" in header_texts):
            continue

        # This is the PBP table
        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            try:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                # Extract data from cells
                # [0]: Time, [1]: empty, [2]: Play, [3]: CTY score, [4]: JLY score
                time_cell = cells[0].get_text(strip=True)

                # Skip if not a valid time
                if not re.match(r"\d+:\d{2}", time_cell):
                    continue

                # Play description is in cell [2]
                play_text = cells[2].get_text(separator=" ", strip=True) if len(cells) > 2 else ""

                # Extract player name (if present)
                # Format: "PlayerNameActionType" (no spaces between name and action)
                # Need to find where player name ends and action begins
                player_name = ""

                # Try to find player link
                player_link = (
                    cells[2].find("a", href=re.compile(r"/players/")) if len(cells) > 2 else None
                )
                if player_link:
                    player_name = player_link.get_text(strip=True)

                # Extract scores from cells [3] and [4]
                score = ""
                if len(cells) >= 5:
                    home_score = cells[3].get_text(strip=True)
                    away_score = cells[4].get_text(strip=True)
                    if home_score.isdigit() and away_score.isdigit():
                        score = f"{home_score}-{away_score}"

                # Determine event type from description
                event_type = _classify_event_type(play_text)

                event_num += 1

                events.append(
                    {
                        "GAME_ID": game_id,
                        "EVENT_NUM": event_num,
                        "EVENT_TYPE": event_type,
                        "PERIOD": None,  # Period not clearly indicated in table
                        "CLOCK": time_cell,
                        "DESCRIPTION": play_text,
                        "PLAYER_NAME": player_name if player_name else None,
                        "TEAM": None,  # Team not explicitly stated
                        "SCORE": score if score else None,
                        "LEAGUE": "OTE",
                    }
                )

            except Exception as e:
                logger.debug(f"Error parsing PBP event: {e}")
                continue

        # Only process first PBP table found
        if events:
            break

    df = pd.DataFrame(events)

    logger.info(f"Fetched play-by-play: {len(df)} events")
    return df


def _classify_event_type(description: str) -> str:
    """Classify play-by-play event type from description

    Args:
        description: Play description text

    Returns:
        Event type category
    """
    description_lower = description.lower()

    if "made" in description_lower or "makes" in description_lower:
        if "free throw" in description_lower or "ft" in description_lower:
            return "free_throw"
        elif "three" in description_lower or "3pt" in description_lower:
            return "three_pointer"
        else:
            return "field_goal"
    elif "miss" in description_lower:
        if "free throw" in description_lower or "ft" in description_lower:
            return "free_throw"
        elif "three" in description_lower or "3pt" in description_lower:
            return "three_pointer"
        else:
            return "field_goal"
    elif "rebound" in description_lower:
        return "rebound"
    elif "foul" in description_lower:
        return "foul"
    elif "turnover" in description_lower:
        return "turnover"
    elif "assist" in description_lower:
        return "assist"
    elif "steal" in description_lower:
        return "steal"
    elif "block" in description_lower:
        return "block"
    elif "substitution" in description_lower or "enters" in description_lower:
        return "substitution"
    else:
        return "other"


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_ote_shot_chart(game_id: str) -> pd.DataFrame:
    """Fetch OTE shot chart data

    Note: Shot coordinates not published on OTE website.
    Returns empty DataFrame.

    Args:
        game_id: Game ID

    Returns:
        Empty DataFrame (shot coordinates unavailable)

    Implementation Notes:
        - OTE website does not publish X/Y shot coordinates
        - Shot made/missed info available in play-by-play
        - Could derive basic shot data from PBP but not coordinates
    """
    logger.warning(
        f"OTE shot chart for game {game_id} unavailable. "
        "Shot coordinates not published (shot made/missed available in PBP)."
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

    df["LEAGUE"] = "OTE"
    df["GAME_ID"] = game_id

    return df
