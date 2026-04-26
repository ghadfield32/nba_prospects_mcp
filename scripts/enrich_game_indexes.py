#!/usr/bin/env python
"""Game Index Enrichment Orchestrator

Enriches game indexes with dates and scores from FIBA sources.
Runs validation after each season to ensure quality gates pass.

Phases:
- Phase 1A: BCL 2020-21 through 2024-25 (FIBA History)
- Phase 1C: BAL 2020-21 through 2024-25 (FIBA LiveStats)
- Phase 1D: OTE 2022-23 through 2024-25 (OTE website)

Usage:
    python scripts/enrich_game_indexes.py
    python scripts/enrich_game_indexes.py --league BCL
    python scripts/enrich_game_indexes.py --league BAL --season 2023-24
    python scripts/enrich_game_indexes.py --dry-run
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
GAME_INDEX_DIR = Path("data/game_indexes")
REPORTS_DIR = Path("data/_reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# FIBA URLs
FIBA_HISTORY_URL = "https://www.fiba.basketball/champions-league/history"
FIBA_LIVESTATS_BASE = "https://fibalivestats.dcd.shared.geniussports.com"
BAL_WEBSITE = "https://thebal.com"
OTE_WEBSITE = "https://overtimeelite.com"

# Rate limiting
REQUEST_DELAY = 1.0  # seconds between requests

# Season configurations
BCL_SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
BAL_SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
OTE_SEASONS = ["2022-23", "2023-24", "2024-25"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class EnrichmentProgress:
    """Track enrichment progress for monitoring."""

    def __init__(self):
        self.started_at = datetime.utcnow()
        self.phases = {}
        self.current_phase = None
        self.current_season = None
        self.games_processed = 0
        self.games_total = 0
        self.errors = []

    def start_phase(self, phase: str, seasons: list):
        """Start a new phase."""
        self.current_phase = phase
        self.phases[phase] = {
            "status": "in_progress",
            "started_at": datetime.utcnow().isoformat(),
            "seasons": seasons,
            "completed_seasons": [],
            "errors": [],
        }
        logger.info(f"Starting phase: {phase} ({len(seasons)} seasons)")

    def complete_season(self, season: str, games_enriched: int, status: str = "PASS"):
        """Mark a season as complete."""
        if self.current_phase:
            self.phases[self.current_phase]["completed_seasons"].append(
                {"season": season, "games": games_enriched, "status": status}
            )
        logger.info(f"Completed {season}: {games_enriched} games ({status})")

    def add_error(self, message: str):
        """Record an error."""
        self.errors.append(message)
        if self.current_phase:
            self.phases[self.current_phase]["errors"].append(message)
        logger.error(message)

    def complete_phase(self, status: str = "PASS"):
        """Mark current phase as complete."""
        if self.current_phase:
            self.phases[self.current_phase]["status"] = status
            self.phases[self.current_phase]["completed_at"] = datetime.utcnow().isoformat()

    def get_summary(self) -> dict:
        """Get progress summary."""
        return {
            "started_at": self.started_at.isoformat(),
            "elapsed_seconds": (datetime.utcnow() - self.started_at).total_seconds(),
            "phases": self.phases,
            "errors": self.errors,
        }


def fetch_url(url: str, timeout: int = 30) -> str | None:
    """Fetch URL with rate limiting and error handling."""
    time.sleep(REQUEST_DELAY)
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def discover_bcl_games_from_fiba(season: str) -> list[dict]:
    """Discover BCL games from FIBA Basketball Champions League pages.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        List of game dictionaries with GAME_ID, GAME_DATE, teams, scores
    """
    games = []
    logger.info(f"Discovering BCL games for {season} from FIBA...")

    # Parse season years
    parts = season.split("-")
    if len(parts) != 2:
        return games

    start_year = int("20" + parts[0][-2:]) if len(parts[0]) == 2 else int(parts[0])
    end_year = int("20" + parts[1]) if len(parts[1]) == 2 else int(parts[1])

    # BCL games URL pattern (FIBA structure)
    # Format: https://www.fiba.basketball/champions-league/{year}/games
    base_urls = [
        f"https://www.fiba.basketball/champions-league/{start_year}/games",
        f"https://www.fiba.basketball/champions-league/{end_year}/games",
    ]

    for base_url in base_urls:
        html = fetch_url(base_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        # Look for game links (pattern varies by FIBA site structure)
        game_links = soup.find_all("a", href=re.compile(r"/champions-league/\d+/game"))

        for link in game_links:
            try:
                href = str(link.get("href", ""))
                game_id_match = re.search(r"/game/(\d+)", href)
                if not game_id_match:
                    continue

                game_id = game_id_match.group(1)

                # Get game container text
                container = link.find_parent()
                if not container:
                    continue

                text = container.get_text(separator=" | ", strip=True)

                games.append(
                    {
                        "GAME_ID": game_id,
                        "raw_text": text,
                        "source_url": href,
                    }
                )

            except Exception as e:
                logger.debug(f"Error parsing game link: {e}")
                continue

    logger.info(f"Discovered {len(games)} BCL games for {season}")
    return games


def discover_bal_games(season: str) -> list[dict]:
    """Discover BAL games from Basketball Africa League sources.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        List of game dictionaries
    """
    games = []
    logger.info(f"Discovering BAL games for {season}...")

    # BAL typically runs March-May
    # Try FIBA LiveStats discovery
    parts = season.split("-")
    if len(parts) != 2:
        return games

    end_year = int("20" + parts[1]) if len(parts[1]) == 2 else int(parts[1])

    # FIBA BAL games endpoint
    bal_url = f"https://www.fiba.basketball/africa/bal/{end_year}/games"
    html = fetch_url(bal_url)

    if html:
        soup = BeautifulSoup(html, "lxml")
        game_links = soup.find_all("a", href=re.compile(r"/bal/\d+/game"))

        for link in game_links:
            try:
                href = str(link.get("href", ""))
                game_id_match = re.search(r"/game/(\d+)", href)
                if game_id_match:
                    games.append(
                        {
                            "GAME_ID": game_id_match.group(1),
                            "source_url": href,
                        }
                    )
            except Exception:
                continue

    # Also try thebal.com
    bal_schedule_url = f"{BAL_WEBSITE}/schedule"
    html = fetch_url(bal_schedule_url)

    if html:
        soup = BeautifulSoup(html, "lxml")
        game_links = soup.find_all("a", href=re.compile(r"/games/"))

        for link in game_links:
            try:
                href = str(link.get("href", ""))
                game_id_match = re.search(r"/games/(\d+)", href)
                if game_id_match:
                    games.append(
                        {
                            "GAME_ID": game_id_match.group(1),
                            "source": "thebal.com",
                        }
                    )
            except Exception:
                continue

    logger.info(f"Discovered {len(games)} BAL games for {season}")
    return games


def discover_ote_games(season: str) -> list[dict]:
    """Discover OTE games from Overtime Elite website schedule page.

    Extracts game details directly from the schedule page which has
    the correct matchup data including teams, dates, and scores.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        List of game dictionaries with teams and dates pre-populated
    """
    games = []
    logger.info(f"Discovering OTE games for {season}...")

    # Parse season year for date inference
    season_parts = season.split("-")
    season_year = int("20" + season_parts[1]) if len(season_parts) == 2 else 2024

    # OTE schedule page
    ote_url = f"{OTE_WEBSITE}/schedule"
    html = fetch_url(ote_url)

    if not html:
        return games

    soup = BeautifulSoup(html, "lxml")

    # Get full page text for parsing game sections
    page_text = soup.get_text(separator="\n")
    [line.strip() for line in page_text.split("\n") if line.strip()]

    # Find game links
    game_links = soup.find_all("a", href=re.compile(r"/games/[a-f0-9\-]+"))
    seen_ids = set()
    game_link_list = []

    for link in game_links:
        href = str(link.get("href", ""))
        game_id_match = re.search(r"/games/([a-f0-9\-]+)", href)
        if game_id_match:
            game_id = game_id_match.group(1)
            if game_id not in seen_ids:
                seen_ids.add(game_id)
                game_link_list.append((game_id, link))

    # OTE teams - known roster
    ote_teams = {
        "blue-checks": "Blue Checks",
        "city-reapers": "City Reapers",
        "cold-hearts": "Cold Hearts",
        "diamond-doves": "Diamond Doves",
        "fear-of-god": "Fear of God",
        "jelly-fam": "Jelly Fam",
        "yng-dreamerz": "YNG Dreamerz",
        "rwe": "RWE",
    }

    for game_id, link in game_link_list:
        try:
            # Find parent container that has game info
            # Go up several levels to find the game block
            parent = link
            for _ in range(10):
                parent = parent.find_parent() if parent else None
                if not parent:
                    break

            if not parent:
                games.append(
                    {
                        "GAME_ID": game_id,
                        "LEAGUE": "OTE",
                        "SEASON": season,
                    }
                )
                continue

            block_text = parent.get_text(separator="\n")
            [line.strip() for line in block_text.split("\n") if line.strip()]

            game_data = {
                "GAME_ID": game_id,
                "LEAGUE": "OTE",
                "SEASON": season,
            }

            # Extract date - look for "Mon, Jan 12" pattern
            date_match = re.search(r"\w{3},?\s+(\w{3})\s+(\d{1,2})", block_text)
            if date_match:
                month = date_match.group(1)
                day = date_match.group(2)
                date_str = f"{month} {day}, {season_year}"
                try:
                    date_obj = pd.to_datetime(date_str, errors="coerce")
                    if pd.notna(date_obj):
                        game_data["GAME_DATE"] = date_obj.strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Extract teams from links in this block
            team_links = parent.find_all("a", href=re.compile(r"/teams/"))
            team_names = []
            found_slugs = set()
            for tl in team_links:
                href = tl.get("href", "")
                for slug, name in ote_teams.items():
                    if slug in href and slug not in found_slugs:
                        found_slugs.add(slug)
                        team_names.append(name)
                        break

            if len(team_names) >= 2:
                game_data["AWAY_TEAM"] = team_names[0]
                game_data["HOME_TEAM"] = team_names[1]

            # Look for scores in format like "86" or "94"
            # Find numbers that look like basketball scores (40-150 range)
            score_matches = re.findall(r"\b(\d{2,3})\b", block_text)
            valid_scores = [int(s) for s in score_matches if 30 <= int(s) <= 150]
            if len(valid_scores) >= 2:
                game_data["AWAY_SCORE"] = valid_scores[0]
                game_data["HOME_SCORE"] = valid_scores[1]

            games.append(game_data)

        except Exception as e:
            logger.debug(f"Error parsing OTE game: {e}")
            games.append(
                {
                    "GAME_ID": game_id,
                    "LEAGUE": "OTE",
                    "SEASON": season,
                }
            )

    logger.info(f"Discovered {len(games)} OTE games for {season}")
    return games


def enrich_game_with_details(league: str, game_id: str, season: str) -> dict | None:
    """Fetch detailed game info (date, scores, teams) from FIBA LiveStats.

    Args:
        league: League code (BCL, BAL)
        game_id: FIBA game ID
        season: Season string

    Returns:
        Enriched game dictionary or None
    """
    # FIBA LiveStats box score page
    url = f"{FIBA_LIVESTATS_BASE}/u/{league}/{game_id}/bs.html"
    html = fetch_url(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    game_data = {
        "GAME_ID": game_id,
        "LEAGUE": league,
        "SEASON": season,
    }

    try:
        # Look for date in page
        date_elem = soup.find(string=re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}"))
        if date_elem:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", str(date_elem))
            if date_match:
                game_data["GAME_DATE"] = date_match.group(1)

        # Look for team names in headers
        team_headers = soup.find_all(["h1", "h2", "h3", "th"], string=re.compile(r"[A-Z][a-z]"))
        teams = []
        for header in team_headers:
            text = header.get_text(strip=True)
            if len(text) > 3 and not any(
                kw in text.lower() for kw in ["player", "min", "pts", "total"]
            ):
                teams.append(text)

        if len(teams) >= 2:
            game_data["HOME_TEAM"] = teams[0]
            game_data["AWAY_TEAM"] = teams[1]

        # Look for scores
        score_pattern = re.compile(r"(\d{2,3})\s*[-:]\s*(\d{2,3})")
        score_match = score_pattern.search(soup.get_text())
        if score_match:
            game_data["HOME_SCORE"] = int(score_match.group(1))
            game_data["AWAY_SCORE"] = int(score_match.group(2))

    except Exception as e:
        logger.debug(f"Error parsing game details: {e}")

    return game_data if "GAME_DATE" in game_data or "HOME_TEAM" in game_data else None


def write_game_index(league: str, season: str, games: list[dict]) -> Path:
    """Write game index to CSV file.

    Args:
        league: League code
        season: Season string
        games: List of game dictionaries

    Returns:
        Path to written file
    """
    GAME_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{league}_{season.replace('-', '_')}.csv"
    filepath = GAME_INDEX_DIR / filename

    df = pd.DataFrame(games)

    # Ensure required columns exist
    required_cols = [
        "LEAGUE",
        "SEASON",
        "GAME_ID",
        "GAME_DATE",
        "HOME_TEAM",
        "AWAY_TEAM",
        "HOME_SCORE",
        "AWAY_SCORE",
        "HOME_TEAM_ID",
        "AWAY_TEAM_ID",
        "FIBA_COMPETITION",
        "FIBA_PHASE",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    # Fill in defaults
    df["LEAGUE"] = df["LEAGUE"].fillna(league)
    df["SEASON"] = df["SEASON"].fillna(season)

    # Use team names as IDs if not set
    if df["HOME_TEAM_ID"].isna().all() and "HOME_TEAM" in df.columns:
        df["HOME_TEAM_ID"] = df["HOME_TEAM"]
    if df["AWAY_TEAM_ID"].isna().all() and "AWAY_TEAM" in df.columns:
        df["AWAY_TEAM_ID"] = df["AWAY_TEAM"]

    # Reorder columns
    df = df[required_cols]

    df.to_csv(filepath, index=False)
    logger.info(f"Wrote {len(df)} games to {filepath}")

    return filepath


def validate_enriched_index(filepath: Path) -> dict:
    """Run validation on enriched game index."""
    # Import validation from our validator script
    from validate_game_indexes import validate_game_index

    return validate_game_index(filepath)


def run_bcl_enrichment(
    seasons: list[str], progress: EnrichmentProgress, dry_run: bool = False
) -> None:
    """Run BCL date enrichment for specified seasons."""
    progress.start_phase("BCL", seasons)

    for season in seasons:
        logger.info(f"Enriching BCL {season}...")

        if dry_run:
            logger.info(f"[DRY RUN] Would enrich BCL {season}")
            progress.complete_season(season, 0, "DRY_RUN")
            continue

        # Discover games
        discovered = discover_bcl_games_from_fiba(season)

        if not discovered:
            logger.warning(f"No BCL games discovered for {season}")
            progress.add_error(f"BCL {season}: No games discovered")
            progress.complete_season(season, 0, "NO_DATA")
            continue

        # Enrich each game
        enriched_games = []
        for game in discovered:
            game_id = game["GAME_ID"]
            details = enrich_game_with_details("BCL", game_id, season)
            if details:
                enriched_games.append(details)

        if enriched_games:
            filepath = write_game_index("BCL", season, enriched_games)

            # Validate
            validation = validate_enriched_index(filepath)
            status = validation.get("status", "UNKNOWN")
            progress.complete_season(season, len(enriched_games), status)
        else:
            progress.add_error(f"BCL {season}: No games enriched")
            progress.complete_season(season, 0, "FAIL")

    progress.complete_phase()


def run_bal_enrichment(
    seasons: list[str], progress: EnrichmentProgress, dry_run: bool = False
) -> None:
    """Run BAL date/score enrichment for specified seasons."""
    progress.start_phase("BAL", seasons)

    for season in seasons:
        logger.info(f"Enriching BAL {season}...")

        if dry_run:
            logger.info(f"[DRY RUN] Would enrich BAL {season}")
            progress.complete_season(season, 0, "DRY_RUN")
            continue

        # Discover games
        discovered = discover_bal_games(season)

        if not discovered:
            logger.warning(f"No BAL games discovered for {season}")
            progress.add_error(f"BAL {season}: No games discovered")
            progress.complete_season(season, 0, "NO_DATA")
            continue

        # Enrich each game
        enriched_games = []
        for game in discovered:
            game_id = game["GAME_ID"]
            details = enrich_game_with_details("BAL", game_id, season)
            if details:
                enriched_games.append(details)

        if enriched_games:
            filepath = write_game_index("BAL", season, enriched_games)

            # Validate
            validation = validate_enriched_index(filepath)
            status = validation.get("status", "UNKNOWN")
            progress.complete_season(season, len(enriched_games), status)
        else:
            progress.add_error(f"BAL {season}: No games enriched")
            progress.complete_season(season, 0, "FAIL")

    progress.complete_phase()


def run_ote_enrichment(
    seasons: list[str], progress: EnrichmentProgress, dry_run: bool = False
) -> None:
    """Run OTE date/score enrichment for specified seasons.

    OTE data is now extracted directly from the schedule page in discover_ote_games,
    which provides teams, dates, and scores in one request per season.
    """
    progress.start_phase("OTE", seasons)

    for season in seasons:
        logger.info(f"Enriching OTE {season}...")

        if dry_run:
            logger.info(f"[DRY RUN] Would enrich OTE {season}")
            progress.complete_season(season, 0, "DRY_RUN")
            continue

        # Discover games - this now returns fully populated game data
        discovered = discover_ote_games(season)

        if not discovered:
            logger.warning(f"No OTE games discovered for {season}")
            progress.add_error(f"OTE {season}: No games discovered")
            progress.complete_season(season, 0, "NO_DATA")
            continue

        # Write to game index
        filepath = write_game_index("OTE", season, discovered)

        # Validate
        validation = validate_enriched_index(filepath)
        status = validation.get("status", "UNKNOWN")
        progress.complete_season(season, len(discovered), status)

    progress.complete_phase()


def main():
    parser = argparse.ArgumentParser(description="Game Index Enrichment Orchestrator")
    parser.add_argument(
        "--league", choices=["BCL", "BAL", "OTE", "ALL"], default="ALL", help="League to enrich"
    )
    parser.add_argument("--season", help="Specific season (e.g., 2023-24)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )
    parser.add_argument("--output", help="Output progress report path")
    args = parser.parse_args()

    print("=" * 70)
    print("GAME INDEX ENRICHMENT ORCHESTRATOR")
    print("=" * 70)
    print(f"League: {args.league}")
    print(f"Season: {args.season or 'ALL'}")
    print(f"Dry run: {args.dry_run}")
    print()

    progress = EnrichmentProgress()

    # Determine which seasons to process
    bcl_seasons = [args.season] if args.season else BCL_SEASONS
    bal_seasons = [args.season] if args.season else BAL_SEASONS
    ote_seasons = [args.season] if args.season else OTE_SEASONS

    if args.league in ["BCL", "ALL"]:
        run_bcl_enrichment(bcl_seasons, progress, args.dry_run)

    if args.league in ["BAL", "ALL"]:
        run_bal_enrichment(bal_seasons, progress, args.dry_run)

    if args.league in ["OTE", "ALL"]:
        run_ote_enrichment(ote_seasons, progress, args.dry_run)

    # Print summary
    summary = progress.get_summary()
    print()
    print("=" * 70)
    print("ENRICHMENT SUMMARY")
    print("=" * 70)
    print(f"Elapsed time: {summary['elapsed_seconds']:.1f} seconds")
    print()

    for phase, data in summary["phases"].items():
        print(f"{phase}:")
        print(f"  Status: {data['status']}")
        print(f"  Seasons completed: {len(data['completed_seasons'])}")
        for season_info in data["completed_seasons"]:
            print(
                f"    - {season_info['season']}: {season_info['games']} games ({season_info['status']})"
            )
        if data["errors"]:
            print(f"  Errors: {len(data['errors'])}")

    # Save progress report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSaved progress report to: {output_path}")
    else:
        # Default output location
        report_path = (
            REPORTS_DIR / f"enrichment_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSaved progress report to: {report_path}")


if __name__ == "__main__":
    main()
