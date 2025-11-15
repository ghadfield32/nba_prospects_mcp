"""NZ NBL (New Zealand National Basketball League) Fetcher

NZ NBL data via FIBA LiveStats HTML scraping (public pages).
New Zealand's top-tier professional basketball league.

Data Source: FIBA LiveStats public HTML pages
- Box scores: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/[GAME_ID]/bs.html
- Play-by-play: https://fibalivestats.dcd.shared.geniussports.com/u/NZN/[GAME_ID]/pbp.html

League Code: "NZN" (NZ NBL in FIBA LiveStats system)

Data Coverage:
- Schedule: Via pre-built game index (data/nz_nbl_game_index.parquet)
- Player-game box scores: Via FIBA LiveStats HTML scraping
- Team-game box scores: Aggregated from player stats
- Play-by-play: Via FIBA LiveStats HTML scraping (when available)
- Shots: ❌ Not available (FIBA HTML doesn't provide x,y coordinates)

Implementation Notes:
- Game IDs must be pre-collected (FIBA doesn't provide searchable game index)
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
        response = requests.get(url, timeout=30)
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
        response = requests.get(url, timeout=30)
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

    # Filter by season
    df = index[index["SEASON"] == season].copy()

    # Add league identifier
    df["LEAGUE"] = "NZ-NBL"

    logger.info(f"Fetched {len(df)} NZ-NBL games for {season}")
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
