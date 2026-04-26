#!/usr/bin/env python
"""Fill OTE gap for missing seasons (2022-23, 2023-24, 2024-25).

This script uses Playwright to fetch OTE player box score data for missing seasons
from the overtimeelite.com website (a Next.js SPA that requires browser automation).

Validation players:
- Alex Sarr (OTE 2022-23 -> Perth NBL -> WAS #2 pick)
- Amen Thompson (OTE 2022-23 -> HOU #4 pick)
- Ausar Thompson (OTE 2022-23 -> DET #5 pick)

Usage:
    python scripts/fill_ote_gap.py
    python scripts/fill_ote_gap.py --seasons 2023-24 2024-25
    python scripts/fill_ote_gap.py --max-games 10
    python scripts/fill_ote_gap.py --dry-run
"""

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_PATH = DATA_DIR / "gold" / "player_career_game.parquet"
OUTPUT_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=OTE"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
LOG_DIR = DATA_DIR / "_logs" / "ote_playwright"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# OTE website
OTE_BASE_URL = "https://overtimeelite.com"
RATE_LIMIT_DELAY = 1.5  # Be nice to their servers

# Seasons to fill (gold table only has 2025 data currently)
MISSING_SEASONS = ["2022-23", "2023-24", "2024-25"]

# OTE teams for validation
OTE_TEAMS = {
    "BLU": "Blue Checks",
    "CTY": "City Reapers",
    "CHS": "Cold Hearts",
    "DOV": "Diamond Doves",
    "FGA": "Fear of God Athletics",
    "FZE": "FaZe",
    "JLY": "Jelly Fam",
    "RWE": "RWE",
    "YNG": "YNG Dreamerz",
}

# Validation players (should find these in 2022-23 data)
VALIDATION_PLAYERS = {
    "alex_sarr": {"search": "sarr", "season": "2022-23"},
    "amen_thompson": {"search": "amen", "season": "2022-23"},
    "ausar_thompson": {"search": "ausar", "season": "2022-23"},
}


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name."""
    if not name or pd.isna(name):
        return ""
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized


def generate_canonical_id(name_key: str, source_id: str, league: str = "OTE") -> str:
    """Generate deterministic canonical player ID."""
    base = f"{league}_{name_key}_{source_id}"
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:8]
    return f"P_{name_key[:20]}_{hash_suffix}"


def parse_minutes(value: str) -> float | None:
    """Parse minutes from MM:SS or numeric format."""
    if not value or pd.isna(value):
        return None
    value = str(value).strip()
    if ":" in value:
        parts = value.split(":")
        try:
            minutes = int(parts[0])
            seconds = int(parts[1]) if len(parts) > 1 else 0
            return minutes + seconds / 60.0
        except (ValueError, IndexError):
            return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_date_string(date_str: str) -> str | None:
    """Parse various date formats into YYYY-MM-DD format.

    Handles formats:
    - ISO 8601: 2024-01-20, 2024-01-20T19:00:00
    - US format: 01/20/2024, 1/20/24
    - Named months: January 20, 2024, Jan 20 2024
    - Timestamps: Unix timestamps (seconds or milliseconds)

    Args:
        date_str: Date string in various formats

    Returns:
        Date in 'YYYY-MM-DD' format, or None if unparseable
    """
    from datetime import datetime

    if not date_str or pd.isna(date_str):
        return None

    date_str = str(date_str).strip()

    # Try common date formats
    formats = [
        "%Y-%m-%d",  # 2024-01-20
        "%Y-%m-%dT%H:%M:%S",  # 2024-01-20T19:00:00
        "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-20T19:00:00Z
        "%Y-%m-%dT%H:%M:%S.%f",  # 2024-01-20T19:00:00.123
        "%Y-%m-%dT%H:%M:%S.%fZ",  # 2024-01-20T19:00:00.123Z
        "%m/%d/%Y",  # 01/20/2024
        "%m-%d-%Y",  # 01-20-2024
        "%B %d, %Y",  # January 20, 2024
        "%b %d, %Y",  # Jan 20, 2024
        "%B %d %Y",  # January 20 2024
        "%b %d %Y",  # Jan 20 2024
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try parsing as Unix timestamp
    try:
        timestamp = int(date_str)
        if timestamp > 1000000000:  # Unix timestamp in seconds (after 2001)
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d")
        elif timestamp > 1000000000000:  # Milliseconds
            dt = datetime.fromtimestamp(timestamp / 1000)
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        pass

    return None


def extract_game_date_from_page(page: Page, game_id: str) -> str | None:
    """Extract game date using multiple fallback strategies.

    Strategies (in order of reliability):
    1. Parse __NEXT_DATA__ JSON blob (most reliable - embedded Next.js data)
    2. Target specific HTML elements (time tags, date classes)
    3. Parse from page content with context (look near "Game Date:" keywords)
    4. Return None with debug logging

    Args:
        page: Playwright page object (already navigated to box score URL)
        game_id: Game ID for logging/debugging

    Returns:
        Game date in 'YYYY-MM-DD' format, or None if not found
    """

    # Strategy 1: Parse __NEXT_DATA__ JSON (Next.js embedded data)
    try:
        content = page.content()
        if "__NEXT_DATA__" in content:
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
            if match:
                next_data = json.loads(match.group(1))

                # Navigate JSON structure to find date
                # Common paths: props.pageProps.game.date, props.pageProps.gameDate
                if "props" in next_data and "pageProps" in next_data["props"]:
                    page_props = next_data["props"]["pageProps"]

                    # Try multiple keys where date might be stored
                    for key in ["game", "gameData", "data", "boxScore"]:
                        if key in page_props and isinstance(page_props[key], dict):
                            game_data = page_props[key]

                            # Look for date fields (try multiple naming conventions)
                            for date_key in [
                                "date",
                                "gameDate",
                                "scheduled",
                                "scheduledDate",
                                "game_date",
                                "event_date",
                                "played_at",
                            ]:
                                if date_key in game_data:
                                    date_value = game_data[date_key]
                                    parsed = parse_date_string(date_value)
                                    if parsed:
                                        print(
                                            f"      [Strategy 1] Found date in __NEXT_DATA__.{key}.{date_key}: {parsed}"
                                        )
                                        return parsed

                    # Also try top-level pageProps date fields
                    for date_key in ["date", "gameDate", "scheduled", "scheduledDate"]:
                        if date_key in page_props:
                            date_value = page_props[date_key]
                            parsed = parse_date_string(date_value)
                            if parsed:
                                print(
                                    f"      [Strategy 1] Found date in __NEXT_DATA__ pageProps.{date_key}: {parsed}"
                                )
                                return parsed

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"      [Strategy 1 failed] __NEXT_DATA__ parsing: {type(e).__name__}")
    except Exception as e:
        print(f"      [Strategy 1 failed] Unexpected error: {e}")

    # Strategy 2: Target specific HTML elements
    try:
        # Look for HTML5 time elements and date containers
        selectors = [
            "time[datetime]",  # HTML5 time element with datetime attribute
            ".game-date",  # Common class name
            ".date",  # Generic date class
            '[class*="date"]',  # Any class containing "date"
            '[data-testid*="date"]',  # Test IDs with date
            "h1 + div",  # Often date appears right after game title
            ".game-info .date",  # Date in game info section
        ]

        for selector in selectors:
            try:
                elements = page.locator(selector).all()
                for elem in elements[:5]:  # Check first 5 matches only
                    # Check datetime attribute (most reliable)
                    datetime_attr = elem.get_attribute("datetime")
                    if datetime_attr:
                        parsed = parse_date_string(datetime_attr)
                        if parsed:
                            print(f"      [Strategy 2] Found in {selector} datetime attr: {parsed}")
                            return parsed

                    # Check text content
                    text = elem.inner_text().strip()
                    if text and len(text) < 50:  # Avoid long text blocks
                        parsed = parse_date_string(text)
                        if parsed:
                            print(f"      [Strategy 2] Found in {selector} text: {parsed}")
                            return parsed
            except Exception:
                continue  # Try next selector

    except Exception as e:
        print(f"      [Strategy 2 failed] HTML element targeting: {type(e).__name__}")

    # Strategy 3: Parse from page content with context
    try:
        content = page.content()

        # Look for dates near keywords (more targeted than naive regex)
        patterns = [
            r"(?:Game Date|Date|Played on|Scheduled):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
            r"(?:Game Date|Date|Played on|Scheduled):\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            r'"date"\s*:\s*"([^"]+)"',  # JSON-like date in HTML
            r'"gameDate"\s*:\s*"([^"]+)"',
            r'"scheduled"\s*:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1)
                parsed = parse_date_string(date_str)
                if parsed:
                    print(f"      [Strategy 3] Found via pattern: {parsed}")
                    return parsed

    except Exception as e:
        print(f"      [Strategy 3 failed] Content parsing: {type(e).__name__}")

    # All strategies failed
    print(f"      [All strategies failed] Could not extract date for game {game_id[:8]}...")
    return None


def fetch_ote_scores_page(page: Page, season: str) -> list[dict]:
    """Fetch completed games from OTE scores page.

    The /scores page shows completed games with real scores.
    """
    games = []

    print("  Navigating to OTE scores page...")
    try:
        page.goto(f"{OTE_BASE_URL}/scores", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"    ERROR navigating to scores: {e}")
        return games

    # Find all game links with UUIDs
    game_links = page.locator('a[href*="/games/"]').all()
    print(f"    Found {len(game_links)} game link elements")

    seen_ids = set()
    for link in game_links:
        try:
            href = link.get_attribute("href")
            if not href:
                continue

            match = re.search(r"/games/([a-f0-9-]{36})", href)
            if not match:
                continue

            game_id = match.group(1)
            if game_id in seen_ids:
                continue
            seen_ids.add(game_id)

            # Try to extract game info from parent container
            parent = link.locator("..").first
            if parent:
                text = parent.inner_text()
                # Try to find date, teams, scores from text
                games.append(
                    {
                        "GAME_ID": game_id,
                        "LEAGUE": "OTE",
                        "SEASON": season,
                        "RAW_TEXT": text[:200] if text else "",
                    }
                )
        except Exception:
            continue

    print(f"    Found {len(games)} unique games")
    return games


def fetch_ote_schedule_page(page: Page, season: str) -> list[dict]:
    """Fetch games from OTE schedule page."""
    games = []

    print("  Navigating to OTE schedule page...")
    try:
        page.goto(f"{OTE_BASE_URL}/schedule", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"    ERROR navigating to schedule: {e}")
        return games

    # Find all game links
    game_links = page.locator('a[href*="/games/"]').all()
    print(f"    Found {len(game_links)} game link elements")

    seen_ids = set()
    for link in game_links:
        try:
            href = link.get_attribute("href")
            if not href:
                continue

            match = re.search(r"/games/([a-f0-9-]{36})", href)
            if not match:
                continue

            game_id = match.group(1)
            if game_id in seen_ids:
                continue
            seen_ids.add(game_id)

            games.append(
                {
                    "GAME_ID": game_id,
                    "LEAGUE": "OTE",
                    "SEASON": season,
                }
            )
        except Exception:
            continue

    print(f"    Found {len(games)} unique games")
    return games


def fetch_ote_boxscore(page: Page, game_id: str, season: str) -> pd.DataFrame:
    """Fetch box score for a single OTE game using Playwright.

    OTE box score table structure (discovered via browser exploration):
    Columns: Player, min, pts, ast, orb, drb, reb, stl, blk, dnk,
             2pm, 2pa, 2p%, 3pm, 3pa, 3p%, fgm, fga, fg%, ftm, fta, ft%, +/-, pf, to
    """
    all_players = []

    url = f"{OTE_BASE_URL}/games/{game_id}/box_score"
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"    ERROR navigating to box score: {e}")
        return pd.DataFrame()

    # Extract game date using multi-strategy approach
    # (replaces naive regex with structured parsing)
    game_date = extract_game_date_from_page(page, game_id)

    # Find team sections - OTE shows two tables, one per team
    tables = page.locator("table").all()

    current_team = None

    for _table_idx, table in enumerate(tables):
        try:
            # Try to find team name in a nearby header
            # Team names usually appear above/before their stats table
            parent = table.locator("..").first
            if parent:
                parent_text = parent.inner_text()
                # Look for OTE team names
                for abbr, full_name in OTE_TEAMS.items():
                    if full_name.lower() in parent_text.lower() or abbr in parent_text:
                        current_team = full_name
                        break

            # Get all rows from table
            rows = table.locator("tr").all()
            if len(rows) < 2:
                continue

            # First row should be headers
            header_row = rows[0]
            headers = header_row.locator("th, td").all()
            header_texts = [h.inner_text().strip().lower() for h in headers]

            # Check if this looks like a player stats table
            # Should have columns like 'player', 'min', 'pts', etc.
            if not any(h in ["player", "min", "pts"] for h in header_texts):
                continue

            # Build column index map
            col_map = {}
            for idx, h in enumerate(header_texts):
                # Normalize header names (OTE uses formats like "minmin", "ptspts")
                h_clean = re.sub(r"(.+)\1", r"\1", h)  # Remove duplicates
                col_map[h_clean] = idx

            # Process data rows (skip header, skip last row which is usually totals)
            data_rows = rows[1:-1] if len(rows) > 2 else rows[1:]

            for row in data_rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 5:
                        continue

                    cell_values = [c.inner_text().strip() for c in cells]

                    # First column is usually player name
                    player_name = cell_values[0] if cell_values else ""

                    # Clean whitespace (fix double-space issues reported in Session 332)
                    player_name = re.sub(r"\s+", " ", player_name).strip()

                    # Skip if not a valid player name (skip team totals, empty rows)
                    if not player_name or player_name.lower() in ["total", "totals", "team"]:
                        continue

                    # Extract player ID from link if available
                    player_link = row.locator('a[href*="/players/"]').first
                    source_player_id = None
                    if player_link:
                        href = player_link.get_attribute("href")
                        if href:
                            id_match = re.search(r"/players/([a-f0-9-]+)", href)
                            if id_match:
                                source_player_id = id_match.group(1)

                    if not source_player_id:
                        # Create composite ID from name
                        source_player_id = f"ote_{normalize_name(player_name)}"

                    # Extract stats - try to map columns
                    def get_stat(
                        col_names: list[str], default=None, col_map=col_map, cell_values=cell_values
                    ):
                        """Get stat value from cell values using column map."""
                        for col_name in col_names:
                            if col_name in col_map:
                                idx = col_map[col_name]
                                if idx < len(cell_values):
                                    val = cell_values[idx]
                                    try:
                                        return float(val) if val and val != "-" else default
                                    except ValueError:
                                        return default
                        return default

                    # Parse stats based on OTE column structure
                    player_data = {
                        "GAME_ID": game_id,
                        "LEAGUE": "OTE",
                        "SEASON": season,
                        "GAME_DATE": game_date,
                        "SOURCE_PLAYER_ID": source_player_id,
                        "PLAYER_NAME_RAW": player_name,
                        "NAME_KEY": normalize_name(player_name),
                        "TEAM_NAME_RAW": current_team,
                        "TEAM_KEY": normalize_name(current_team) if current_team else "",
                        # Stats - try multiple column name variations
                        "MIN": parse_minutes(
                            cell_values[col_map.get("min", 1)]
                            if "min" in col_map
                            else cell_values[1]
                            if len(cell_values) > 1
                            else None
                        ),
                        "PTS": get_stat(["pts", "points"], 0),
                        "AST": get_stat(["ast", "assists"], 0),
                        "OREB": get_stat(["orb", "oreb"], 0),
                        "DREB": get_stat(["drb", "dreb"], 0),
                        "REB": get_stat(["reb", "rebounds"], 0),
                        "STL": get_stat(["stl", "steals"], 0),
                        "BLK": get_stat(["blk", "blocks"], 0),
                        "FG3M": get_stat(["3pm", "fg3m"], 0),
                        "FG3A": get_stat(["3pa", "fg3a"], 0),
                        "FGM": get_stat(["fgm"], 0),
                        "FGA": get_stat(["fga"], 0),
                        "FTM": get_stat(["ftm"], 0),
                        "FTA": get_stat(["fta"], 0),
                        "PLUS_MINUS": get_stat(["+/-", "plusminus", "plus_minus"]),
                        "PF": get_stat(["pf", "fouls"], 0),
                        "TOV": get_stat(["to", "tov", "turnovers"], 0),
                    }

                    # Calculate REB if not available
                    if not player_data["REB"] and (player_data["OREB"] or player_data["DREB"]):
                        player_data["REB"] = (player_data["OREB"] or 0) + (player_data["DREB"] or 0)

                    # Calculate percentages
                    if player_data["FGA"] and player_data["FGA"] > 0:
                        player_data["FG_PCT"] = round(
                            player_data["FGM"] / player_data["FGA"] * 100, 1
                        )
                    else:
                        player_data["FG_PCT"] = None

                    if player_data["FG3A"] and player_data["FG3A"] > 0:
                        player_data["FG3_PCT"] = round(
                            player_data["FG3M"] / player_data["FG3A"] * 100, 1
                        )
                    else:
                        player_data["FG3_PCT"] = None

                    if player_data["FTA"] and player_data["FTA"] > 0:
                        player_data["FT_PCT"] = round(
                            player_data["FTM"] / player_data["FTA"] * 100, 1
                        )
                    else:
                        player_data["FT_PCT"] = None

                    # Generate canonical ID
                    player_data["CANONICAL_PLAYER_ID"] = generate_canonical_id(
                        player_data["NAME_KEY"], player_data["SOURCE_PLAYER_ID"]
                    )

                    all_players.append(player_data)

                except Exception:
                    continue

        except Exception:
            continue

    if not all_players:
        return pd.DataFrame()

    return pd.DataFrame(all_players)


def try_alternative_data_sources(page: Page, season: str) -> list[dict]:
    """Try alternative methods to get historical OTE data.

    OTE website may not expose historical seasons directly, so we try:
    1. Check if there's a __NEXT_DATA__ JSON blob with preloaded data
    2. Check network requests for API endpoints
    3. Try direct API URLs if discoverable
    """
    games = []

    print(f"  Trying alternative data sources for {season}...")

    # Navigate to scores page and check for __NEXT_DATA__
    try:
        page.goto(f"{OTE_BASE_URL}/scores", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # Check for Next.js data blob
        content = page.content()
        if "__NEXT_DATA__" in content:
            print("    Found __NEXT_DATA__ - checking for game data...")
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
            if match:
                try:
                    next_data = json.loads(match.group(1))
                    # Look for games in props
                    if "props" in next_data and "pageProps" in next_data["props"]:
                        page_props = next_data["props"]["pageProps"]
                        print(f"    pageProps keys: {list(page_props.keys())}")

                        # Try to find games array
                        for key in ["games", "schedule", "scores", "data"]:
                            if key in page_props:
                                items = page_props[key]
                                if isinstance(items, list):
                                    print(f"    Found {len(items)} items in '{key}'")
                                    for item in items:
                                        if isinstance(item, dict) and "id" in item:
                                            games.append(
                                                {
                                                    "GAME_ID": item.get("id"),
                                                    "LEAGUE": "OTE",
                                                    "SEASON": season,
                                                    "RAW_DATA": item,
                                                }
                                            )
                except json.JSONDecodeError:
                    print("    Failed to parse __NEXT_DATA__")
    except Exception as e:
        print(f"    Alternative source check failed: {e}")

    return games


def validate_data(df: pd.DataFrame, season: str) -> bool:
    """Validate the canonical data meets quality gates."""
    if df.empty:
        print(f"  WARN: No data for {season}")
        return False

    # Check PK uniqueness
    pk_cols = ["LEAGUE", "SEASON", "GAME_ID", "SOURCE_PLAYER_ID"]
    available_pks = [c for c in pk_cols if c in df.columns]
    if available_pks:
        pk_dupes = df.duplicated(subset=available_pks, keep=False).sum()
        if pk_dupes > 0:
            print(f"  WARN: {pk_dupes} PK duplicates in {season}")

    # Check stat sanity
    if "FGM" in df.columns and "FGA" in df.columns:
        invalid_fg = (df["FGM"].fillna(0) > df["FGA"].fillna(0)).sum()
        if invalid_fg > 0:
            print(f"  WARN: {invalid_fg} rows with FGM > FGA")

    if "FG3M" in df.columns and "FG3A" in df.columns:
        invalid_fg3 = (df["FG3M"].fillna(0) > df["FG3A"].fillna(0)).sum()
        if invalid_fg3 > 0:
            print(f"  WARN: {invalid_fg3} rows with FG3M > FG3A")

    # Check NAME_KEY coverage
    if "NAME_KEY" in df.columns:
        name_coverage = df["NAME_KEY"].notna().mean()
        if name_coverage < 0.9:
            print(f"  WARN: NAME_KEY coverage only {name_coverage:.1%}")

    # Check GAME_DATE coverage (new in Week 4)
    if "GAME_DATE" in df.columns:
        date_coverage = df["GAME_DATE"].notna().mean()
        if date_coverage < 0.95:
            print(f"  WARN: GAME_DATE coverage only {date_coverage:.1%} (target: >95%)")
        else:
            print(f"  PASS: GAME_DATE coverage {date_coverage:.1%}")
    else:
        print("  WARN: GAME_DATE column missing")

    print(f"  PASS: {len(df):,} rows, {df['NAME_KEY'].nunique()} unique players")
    return True


def search_validation_players(df: pd.DataFrame) -> dict:
    """Search for Thompson brothers and Alex Sarr in the data."""
    results = {}

    if "NAME_KEY" not in df.columns:
        return results

    for player_key, info in VALIDATION_PLAYERS.items():
        search_term = info["search"]
        target_season = info["season"]

        # Search in all data
        matches = df[df["NAME_KEY"].str.contains(search_term, case=False, na=False)]

        # Also check specific season
        season_matches = (
            matches[matches["SEASON"] == target_season] if "SEASON" in matches.columns else matches
        )

        if len(matches) > 0:
            results[player_key] = {
                "found": True,
                "total_games": len(matches),
                "season_games": len(season_matches),
                "names": matches["PLAYER_NAME_RAW"].unique().tolist()[:5],
                "seasons": matches["SEASON"].unique().tolist()
                if "SEASON" in matches.columns
                else [],
            }
        else:
            results[player_key] = {"found": False}

    return results


def merge_to_gold(new_data: pd.DataFrame, dry_run: bool = False) -> pd.DataFrame:
    """Merge new OTE data with existing gold table."""
    if not GOLD_PATH.exists():
        print(f"WARN: Gold table not found at {GOLD_PATH}")
        print("  Will only save to canonical directory")
        return new_data

    print("\nLoading existing gold table...")
    gold = pd.read_parquet(GOLD_PATH)
    print(f"  Existing rows: {len(gold):,}")

    # Check existing OTE data
    existing_ote = gold[gold["LEAGUE"] == "OTE"]
    print(f"  Existing OTE rows: {len(existing_ote):,}")
    if "SEASON" in existing_ote.columns:
        print(f"  Existing OTE seasons: {existing_ote['SEASON'].unique().tolist()}")

    # Remove existing OTE data for the seasons we're adding
    seasons_to_add = new_data["SEASON"].unique()
    mask = ~((gold["LEAGUE"] == "OTE") & (gold["SEASON"].isin(seasons_to_add)))
    gold_filtered = gold[mask].copy()
    print(f"  After removing seasons {list(seasons_to_add)}: {len(gold_filtered):,}")

    # Ensure columns match
    gold_cols = set(gold.columns)
    new_cols = set(new_data.columns)

    # Add missing columns to new_data
    for col in gold_cols - new_cols:
        new_data[col] = None

    # Select only columns that exist in gold
    new_data = new_data[[c for c in gold.columns if c in new_data.columns]]

    # Ensure GAME_DATE is consistent type (string, not Timestamp)
    # This prevents pyarrow type errors when saving parquet
    if "GAME_DATE" in gold_filtered.columns:
        gold_filtered["GAME_DATE"] = gold_filtered["GAME_DATE"].astype(str)
        gold_filtered.loc[gold_filtered["GAME_DATE"] == "NaT", "GAME_DATE"] = None
    if "GAME_DATE" in new_data.columns:
        new_data["GAME_DATE"] = new_data["GAME_DATE"].astype(str)
        new_data.loc[new_data["GAME_DATE"] == "NaN", "GAME_DATE"] = None

    # Concatenate
    merged = pd.concat([gold_filtered, new_data], ignore_index=True)

    # Recompute game numbers
    print("  Recomputing game numbers...")
    merged = merged.sort_values(["NAME_KEY", "GAME_DATE"])
    merged["CAREER_GAME_NUMBER"] = merged.groupby("NAME_KEY").cumcount() + 1
    merged["LEAGUE_GAME_NUMBER"] = merged.groupby(["NAME_KEY", "LEAGUE"]).cumcount() + 1

    print(f"  Final gold rows: {len(merged):,}")

    if not dry_run:
        print(f"\nSaving to {GOLD_PATH}...")
        merged.to_parquet(GOLD_PATH, index=False)
        print("  Done!")
    else:
        print("\n[DRY RUN] Would save to gold table")

    return merged


def main():
    parser = argparse.ArgumentParser(description="Fill OTE gap for missing seasons")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=MISSING_SEASONS,
        help="Seasons to fetch (default: 2022-23 2023-24 2024-25)",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Maximum games to fetch per season (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't save to gold table or canonical directory"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR),
        help="Output directory for canonical files",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--test-games",
        type=int,
        default=None,
        help="Only test with N games total (for development)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("OTE GAP FILLER (Playwright-based)")
    print("=" * 70)
    print(f"Seasons to fetch: {args.seasons}")
    print(f"Max games per season: {args.max_games or 'all'}")
    print(f"Test mode: {args.test_games or 'disabled'}")
    print()

    all_data = []
    all_games = []

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()

        for season in args.seasons:
            print(f"\n{'=' * 50}")
            print(f"Processing {season}")
            print("=" * 50)

            # Fetch game list
            # Try scores page first (has completed games), then schedule
            games = fetch_ote_scores_page(page, season)

            if not games:
                games = fetch_ote_schedule_page(page, season)

            if not games:
                # Try alternative data sources
                games = try_alternative_data_sources(page, season)

            if not games:
                print(f"  No games found for {season}")
                continue

            print(f"  Found {len(games)} games for {season}")
            all_games.extend(games)

            # Limit games if specified
            max_games = args.max_games
            if args.test_games and len(all_data) == 0:
                max_games = args.test_games
                print(f"  TEST MODE: Only fetching {max_games} games")

            games_to_fetch = games[:max_games] if max_games else games

            # Fetch box scores
            print(f"  Fetching box scores for {len(games_to_fetch)} games...")
            season_data = []

            for i, game in enumerate(games_to_fetch):
                if i > 0 and i % 10 == 0:
                    print(f"    Progress: {i}/{len(games_to_fetch)}")

                time.sleep(RATE_LIMIT_DELAY)

                box = fetch_ote_boxscore(page, game["GAME_ID"], season)
                if not box.empty:
                    season_data.append(box)
                    print(f"    Game {game['GAME_ID'][:8]}...: {len(box)} players")

                # Early exit for test mode
                if args.test_games and sum(len(d) for d in season_data) >= 20:
                    print(f"    TEST MODE: Stopping after {len(season_data)} games")
                    break

            if not season_data:
                print(f"  No box score data collected for {season}")
                continue

            # Combine season data
            season_df = pd.concat(season_data, ignore_index=True)
            print(f"  Season {season}: {len(season_df):,} player-game rows")

            # Validate
            print("  Validating...")
            validate_data(season_df, season)

            # Save canonical file
            output_dir = Path(args.output_dir) / f"season={season}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "data.parquet"

            if not args.dry_run:
                season_df.to_parquet(output_path, index=False)
                print(f"  Saved canonical: {output_path}")
            else:
                print(f"  [DRY RUN] Would save to {output_path}")

            all_data.append(season_df)

        browser.close()

    if not all_data:
        print("\nNo data fetched!")

        # Save game index for debugging
        if all_games:
            games_df = pd.DataFrame(all_games)
            games_path = (
                GAME_INDEX_DIR
                / f"OTE_playwright_games_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            games_df.to_csv(games_path, index=False)
            print(f"Saved game index to: {games_path}")
        return

    # Combine all seasons
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal new data: {len(combined):,} rows")

    # Validation player search
    print("\n" + "=" * 70)
    print("VALIDATION PLAYER SEARCH")
    print("=" * 70)
    validation = search_validation_players(combined)
    for player, info in validation.items():
        if info["found"]:
            print(f"[OK] {player}: {info['total_games']} games, names: {info['names']}")
            if info.get("seasons"):
                print(f"     Seasons: {info['seasons']}")
        else:
            print(f"[X] {player}: NOT FOUND")

    # Merge to gold
    if not args.dry_run:
        merge_to_gold(combined, dry_run=args.dry_run)
    else:
        print("\n[DRY RUN] Skipping gold table merge")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for season in args.seasons:
        season_data = combined[combined["SEASON"] == season]
        if not season_data.empty:
            print(
                f"  {season}: {len(season_data):,} rows, {season_data['NAME_KEY'].nunique()} players"
            )
        else:
            print(f"  {season}: No data")


if __name__ == "__main__":
    main()
