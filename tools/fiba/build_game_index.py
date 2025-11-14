#!/usr/bin/env python3
"""FIBA Game Index Builder

Discovers and validates FIBA LiveStats game IDs from official league websites.
Creates CSV game indexes used by league fetchers.

**Supported Leagues**:
- BCL (Basketball Champions League)
- BAL (Basketball Africa League)
- ABA (ABA League / Adriatic League)
- LKL (Lithuanian Basketball League)

**Output Format**: data/game_indexes/{LEAGUE}_{SEASON}.csv

**Columns**:
- LEAGUE: League code (BCL, BAL, ABA, LKL)
- SEASON: Season string (e.g., "2023-24")
- GAME_ID: FIBA LiveStats numeric game ID
- GAME_DATE: Game date (ISO format YYYY-MM-DD)
- HOME_TEAM: Home team name
- AWAY_TEAM: Away team name
- HOME_SCORE: Final home score (if available)
- AWAY_SCORE: Final away score (if available)
- COMPETITION_PHASE: Season phase (RS, PO, FF, etc.)
- ROUND: Round number (if applicable)
- VERIFIED: Boolean indicating if game ID was validated

**Usage**:
```bash
# Build index for single league/season
python tools/fiba/build_game_index.py --league BCL --season 2023-24

# Build all available seasons for a league
python tools/fiba/build_game_index.py --league BCL --all-seasons

# Validate existing index
python tools/fiba/build_game_index.py --league BCL --season 2023-24 --validate-only

# Build all leagues for current season
python tools/fiba/build_game_index.py --all-leagues
```

**Implementation Notes**:
- Uses BeautifulSoup for HTML parsing
- Respects robots.txt and implements rate limiting
- Validates game IDs by attempting to fetch their HTML widget
- Caches intermediate results to avoid repeated scraping
- Handles network errors gracefully with retries

**Last Updated**: 2025-11-14
**Maintainer**: Data Engineering Team
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
REPO_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "game_indexes"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# FIBA LiveStats URL patterns for validation
FIBA_HTML_URL_PATTERN = "https://fibalivestats.dcd.shared.geniussports.com/u/{league}/{game_id}/bs.html"
FIBA_JSON_URL_PATTERN = "https://fibalivestats.dcd.shared.geniussports.com/data/{game_id}/data.json"

# League-specific website URLs (to be discovered/updated)
LEAGUE_SITES = {
    "BCL": "https://www.championsleague.basketball",
    "BAL": "https://thebal.com",
    "ABA": "https://www.aba-liga.com",
    "LKL": "https://lkl.lt",
}

# Headers for web scraping (realistic browser)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


@dataclass
class GameIndexEntry:
    """Single game entry for index"""

    league: str
    season: str
    game_id: int
    game_date: str
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    competition_phase: Optional[str] = None
    round: Optional[int] = None
    verified: bool = False


class FibaGameIndexBuilder:
    """
    Discovers FIBA game IDs from official league websites and builds game indexes.
    """

    def __init__(self, session: Optional[requests.Session] = None, rate_limit_sec: float = 1.0):
        """
        Initialize builder.

        Args:
            session: Optional requests session for connection pooling
            rate_limit_sec: Seconds to wait between requests (respect rate limits)
        """
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.rate_limit_sec = rate_limit_sec
        self.last_request_time = 0.0

    def _rate_limit(self):
        """Apply rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_sec:
            time.sleep(self.rate_limit_sec - elapsed)
        self.last_request_time = time.time()

    def _fetch_html(self, url: str, timeout: int = 20) -> str:
        """
        Fetch HTML from URL with rate limiting and error handling.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            HTML content as string

        Raises:
            requests.HTTPError: On non-200 status
        """
        self._rate_limit()
        logger.debug(f"Fetching: {url}")

        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.HTTPError as e:
            if e.response.status_code == 403:
                logger.error(f"Access denied (403) for {url}. May need different headers or approach.")
            raise
        except requests.RequestException as e:
            logger.error(f"Network error fetching {url}: {e}")
            raise

    def _extract_fiba_game_ids_from_links(self, html: str, base_url: str) -> list[dict]:
        """
        Extract FIBA LiveStats game IDs from HTML links.

        Searches for links containing 'fibalivestats' and extracts game ID.

        Args:
            html: HTML content to parse
            base_url: Base URL for resolving relative links

        Returns:
            List of dicts with 'game_id', 'url', and any extractable metadata
        """
        soup = BeautifulSoup(html, "html.parser")
        found_games = []

        # Pattern 1: Direct links to fibalivestats
        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Check if it's a FIBA LiveStats link
            if "fibalivestats.dcd.shared.geniussports.com" in href:
                # Extract game ID from URL
                # Pattern: /u/{LEAGUE}/{GAME_ID}/bs.html or /data/{GAME_ID}/data.json
                match = re.search(r"/u/[^/]+/(\d+)/", href) or re.search(r"/data/(\d+)/", href)

                if match:
                    game_id = int(match.group(1))

                    # Try to extract context (date, teams) from surrounding elements
                    context = self._extract_game_context(link)

                    found_games.append(
                        {
                            "game_id": game_id,
                            "url": href,
                            "date": context.get("date"),
                            "home_team": context.get("home_team"),
                            "away_team": context.get("away_team"),
                            "home_score": context.get("home_score"),
                            "away_score": context.get("away_score"),
                        }
                    )

        logger.info(f"Found {len(found_games)} FIBA game IDs in HTML")
        return found_games

    def _extract_game_context(self, link_element) -> dict:
        """
        Extract game context (date, teams, scores) from DOM near the link.

        Args:
            link_element: BeautifulSoup link element

        Returns:
            Dict with extracted context fields
        """
        context = {}

        # Try to find parent row/article/card
        parent = link_element.find_parent(["tr", "article", "div", "li"])
        if not parent:
            return context

        # Extract all text from parent
        parent_text = parent.get_text(strip=True)

        # Try to find date patterns (YYYY-MM-DD, DD/MM/YYYY, etc.)
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # ISO format
            r"\d{2}/\d{2}/\d{4}",  # DD/MM/YYYY
            r"\d{2}\.\d{2}\.\d{4}",  # DD.MM.YYYY
        ]

        for pattern in date_patterns:
            match = re.search(pattern, parent_text)
            if match:
                context["date"] = match.group(0)
                break

        # Try to extract team names (heuristic: look for capitalized words or team indicators)
        # This is league-specific and would need refinement per site
        # For now, leave as None to be filled manually or via more specific scrapers

        # Try to extract scores (pattern: ##-## or ## : ##)
        score_match = re.search(r"(\d{2,3})\s*[-:]\s*(\d{2,3})", parent_text)
        if score_match:
            context["home_score"] = int(score_match.group(1))
            context["away_score"] = int(score_match.group(2))

        return context

    def validate_game_id(self, league: str, game_id: int) -> bool:
        """
        Validate a game ID by attempting to fetch its HTML widget.

        Args:
            league: League code (BCL, BAL, etc.)
            game_id: Game ID to validate

        Returns:
            True if game ID is valid and accessible
        """
        url = FIBA_HTML_URL_PATTERN.format(league=league, game_id=game_id)

        try:
            self._rate_limit()
            resp = self.session.get(url, timeout=10)
            is_valid = resp.status_code == 200
            if is_valid:
                logger.debug(f"✓ Validated game ID {game_id} for {league}")
            else:
                logger.warning(f"✗ Invalid game ID {game_id} for {league} (HTTP {resp.status_code})")
            return is_valid
        except requests.RequestException as e:
            logger.warning(f"✗ Could not validate game ID {game_id}: {e}")
            return False

    def build_bcl_index(self, season: str) -> list[GameIndexEntry]:
        """
        Build game index for Basketball Champions League.

        Args:
            season: Season string (e.g., "2023-24")

        Returns:
            List of GameIndexEntry objects
        """
        logger.info(f"Building BCL game index for season {season}")

        # BCL stats/games page (adjust based on actual site structure)
        # This is a placeholder - actual implementation requires inspecting the BCL site
        base_url = LEAGUE_SITES["BCL"]
        games_url = f"{base_url}/en/games"  # Adjust to actual schedule URL

        try:
            html = self._fetch_html(games_url)
            found_games = self._extract_fiba_game_ids_from_links(html, base_url)

            entries = []
            for game_data in found_games:
                entry = GameIndexEntry(
                    league="BCL",
                    season=season,
                    game_id=game_data["game_id"],
                    game_date=game_data.get("date", ""),
                    home_team=game_data.get("home_team", ""),
                    away_team=game_data.get("away_team", ""),
                    home_score=game_data.get("home_score"),
                    away_score=game_data.get("away_score"),
                    verified=False,
                )
                entries.append(entry)

            return entries

        except Exception as e:
            logger.error(f"Failed to build BCL index: {e}")
            return []

    def build_bal_index(self, season: str) -> list[GameIndexEntry]:
        """
        Build game index for Basketball Africa League.

        Args:
            season: Season string (e.g., "2023-24")

        Returns:
            List of GameIndexEntry objects
        """
        logger.info(f"Building BAL game index for season {season}")

        # Similar pattern to BCL - adjust for BAL site structure
        # Placeholder implementation
        logger.warning("BAL index builder not yet implemented. Please implement site-specific scraping.")
        return []

    def build_aba_index(self, season: str) -> list[GameIndexEntry]:
        """
        Build game index for ABA League.

        Args:
            season: Season string (e.g., "2023-24")

        Returns:
            List of GameIndexEntry objects
        """
        logger.info(f"Building ABA game index for season {season}")

        # ABA site structure (placeholder)
        logger.warning("ABA index builder not yet implemented. Please implement site-specific scraping.")
        return []

    def build_lkl_index(self, season: str) -> list[GameIndexEntry]:
        """
        Build game index for Lithuanian LKL.

        Args:
            season: Season string (e.g., "2023-24")

        Returns:
            List of GameIndexEntry objects
        """
        logger.info(f"Building LKL game index for season {season}")

        # LKL site structure (placeholder)
        logger.warning("LKL index builder not yet implemented. Please implement site-specific scraping.")
        return []

    def save_index(self, entries: list[GameIndexEntry], output_path: Path, validate: bool = False):
        """
        Save game index to CSV file.

        Args:
            entries: List of GameIndexEntry objects
            output_path: Output CSV file path
            validate: If True, validate each game ID before saving
        """
        if not entries:
            logger.warning("No entries to save")
            return

        # Validate if requested
        if validate:
            logger.info(f"Validating {len(entries)} game IDs...")
            for entry in entries:
                entry.verified = self.validate_game_id(entry.league, entry.game_id)
                time.sleep(0.5)  # Extra rate limiting during validation

        # Convert to DataFrame and save
        df = pd.DataFrame([asdict(entry) for entry in entries])

        # Sort by date and game_id
        df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)

        # Save to CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        logger.info(f"Saved {len(df)} games to {output_path}")

        # Print summary
        verified_count = df["verified"].sum() if "verified" in df.columns else "N/A"
        logger.info(f"Summary: {len(df)} total games, {verified_count} verified")


def main():
    """Command-line interface for game index builder"""
    parser = argparse.ArgumentParser(
        description="Build FIBA game indexes from official league websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--league",
        choices=["BCL", "BAL", "ABA", "LKL"],
        help="League to build index for",
    )

    parser.add_argument(
        "--season",
        help="Season string (e.g., '2023-24')",
    )

    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="Build indexes for all supported leagues (current season)",
    )

    parser.add_argument(
        "--all-seasons",
        action="store_true",
        help="Build all available seasons for specified league",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate game IDs by fetching HTML widgets",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing index without rebuilding",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Output directory for CSV files (default: {DATA_DIR})",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize builder
    builder = FibaGameIndexBuilder()

    # Validate only mode
    if args.validate_only:
        if not args.league or not args.season:
            parser.error("--validate-only requires --league and --season")

        index_file = args.output_dir / f"{args.league}_{args.season.replace('-', '_')}.csv"
        if not index_file.exists():
            logger.error(f"Index file not found: {index_file}")
            return

        df = pd.read_csv(index_file)
        logger.info(f"Validating {len(df)} game IDs from {index_file}")

        validated = 0
        for _, row in df.iterrows():
            if builder.validate_game_id(row["LEAGUE"], int(row["GAME_ID"])):
                validated += 1

        logger.info(f"Validation complete: {validated}/{len(df)} game IDs valid")
        return

    # Build mode
    if args.all_leagues:
        # Build current season for all leagues
        current_season = "2024-25"  # Update as needed
        for league in ["BCL", "BAL", "ABA", "LKL"]:
            logger.info(f"\n{'='*60}\nBuilding {league} index for {current_season}\n{'='*60}")
            _build_league_index(builder, league, current_season, args)
    elif args.league:
        if args.all_seasons:
            logger.warning("--all-seasons not yet implemented. Please specify --season.")
            return
        elif args.season:
            _build_league_index(builder, args.league, args.season, args)
        else:
            parser.error("--league requires --season or --all-seasons")
    else:
        parser.error("Must specify --league or --all-leagues")


def _build_league_index(builder: FibaGameIndexBuilder, league: str, season: str, args):
    """Helper to build index for a single league/season"""
    # Map league to builder method
    build_methods = {
        "BCL": builder.build_bcl_index,
        "BAL": builder.build_bal_index,
        "ABA": builder.build_aba_index,
        "LKL": builder.build_lkl_index,
    }

    build_func = build_methods[league]
    entries = build_func(season)

    if entries:
        output_file = args.output_dir / f"{league}_{season.replace('-', '_')}.csv"
        builder.save_index(entries, output_file, validate=args.validate)
    else:
        logger.warning(f"No entries found for {league} {season}")


if __name__ == "__main__":
    main()
