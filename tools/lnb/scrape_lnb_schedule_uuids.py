#!/usr/bin/env python3
"""Scrape LNB Schedule Pages for Game UUIDs

This script uses Playwright to scrape LNB schedule pages (Elite 2, Espoirs Elite, etc.)
and extract game UUIDs from match links. These UUIDs are then used for bulk discovery
via the Atrium API.

Purpose:
    - Extract game UUIDs from JavaScript-rendered schedule pages
    - Support all 4 LNB leagues: Betclic ELITE, ELITE 2, Espoirs ELITE, Espoirs PROB
    - Save UUIDs to JSON files for bulk discovery pipeline

Usage:
    # Scrape Elite 2 schedule
    uv run python tools/lnb/scrape_lnb_schedule_uuids.py --league elite_2

    # Scrape all leagues
    uv run python tools/lnb/scrape_lnb_schedule_uuids.py --all-leagues

    # Specify season
    uv run python tools/lnb/scrape_lnb_schedule_uuids.py --league elite_2 --season 2024-2025

Created: 2025-11-18
Part of: LNB Multi-League Integration Phase 2
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.cbb_data.fetchers.browser_scraper import BrowserScraper, is_playwright_available

# ==============================================================================
# CONFIG
# ==============================================================================

# LNB schedule URLs by league
# These pages contain all games for the season with UUIDs in match-center links
SCHEDULE_URLS = {
    "betclic_elite": "https://www.lnb.fr/pro-a/calendrier",
    "elite_2": "https://www.lnb.fr/elite-2/calendrier",
    "espoirs_elite": "https://www.lnb.fr/espoirs-elite/calendrier",
    "espoirs_prob": "https://www.lnb.fr/espoirs-prob/calendrier",
}

# Output directory for UUID mappings
OUTPUT_DIR = Path("tools/lnb/uuid_mappings")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Regex pattern to extract UUIDs from URLs
# Matches: /match-center/{uuid} or /fr/match-center/{uuid}
UUID_PATTERN = re.compile(
    r"/(?:fr/)?match-center/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)

# ==============================================================================
# SCRAPING FUNCTIONS
# ==============================================================================


def extract_uuids_from_html(html: str) -> list[str]:
    """Extract game UUIDs from schedule page HTML

    Searches for match-center URLs containing UUIDs and extracts them.

    Args:
        html: Raw HTML content from schedule page

    Returns:
        List of unique game UUIDs (deduplicated)

    Example:
        >>> html = '<a href="/fr/match-center/abc-123-def">Match</a>'
        >>> extract_uuids_from_html(html)
        ['abc-123-def']
    """
    matches = UUID_PATTERN.findall(html)

    # Deduplicate while preserving order
    seen = set()
    unique_uuids = []
    for uuid in matches:
        if uuid not in seen:
            seen.add(uuid)
            unique_uuids.append(uuid)

    return unique_uuids


def scrape_league_schedule(
    league: str,
    url: str,
    timeout: int = 30000,
    headless: bool = True,
) -> list[str]:
    """Scrape a league schedule page for game UUIDs

    Uses Playwright to load JavaScript-rendered page and extract UUIDs.

    Args:
        league: League identifier (e.g., "elite_2", "espoirs_elite")
        url: Schedule page URL
        timeout: Page load timeout in milliseconds
        headless: Run browser in headless mode

    Returns:
        List of game UUIDs extracted from page

    Raises:
        RuntimeError: If Playwright not available
        Exception: If scraping fails
    """
    if not is_playwright_available():
        raise RuntimeError(
            "Playwright not installed. Install with:\n"
            "  uv pip install playwright\n"
            "  playwright install chromium"
        )

    print(f"\n[SCRAPING] {league.upper()} schedule...")
    print(f"  URL: {url}")
    print(f"  Timeout: {timeout}ms")
    print()

    try:
        with BrowserScraper(headless=headless, timeout=timeout) as scraper:
            print("  [1/3] Launching browser...")

            # Load page and wait for content
            print("  [2/3] Loading schedule page...")
            print("        This may take 10-30 seconds (JavaScript rendering)...")

            html = scraper.get_rendered_html(url=url, wait_time=5.0)

            print(f"  [3/3] Extracting UUIDs from HTML ({len(html)} chars)...")

            # Extract UUIDs from HTML
            uuids = extract_uuids_from_html(html)

            print(f"  [SUCCESS] Extracted {len(uuids)} unique game UUIDs")

            return uuids

    except Exception as e:
        print(f"  [ERROR] Failed to scrape {league}: {e}")
        raise


# ==============================================================================
# FILE I/O
# ==============================================================================


def save_uuids_to_file(
    league: str,
    season: str,
    uuids: list[str],
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """Save extracted UUIDs to JSON file

    Creates a JSON file with metadata for bulk discovery pipeline.

    Args:
        league: League identifier
        season: Season string (e.g., "2024-2025")
        uuids: List of game UUIDs
        output_dir: Output directory path

    Returns:
        Path to saved JSON file

    Output Format:
        {
            "league": "elite_2",
            "season": "2024-2025",
            "extracted_at": "2025-11-18T14:30:00",
            "source_url": "https://www.lnb.fr/elite-2/calendrier",
            "uuid_count": 340,
            "uuids": ["uuid1", "uuid2", ...]
        }
    """
    output_file = output_dir / f"{league}_{season.replace('-', '_')}_uuids.json"

    data = {
        "league": league,
        "season": season,
        "extracted_at": datetime.now().isoformat(),
        "source_url": SCHEDULE_URLS.get(league, "Unknown"),
        "uuid_count": len(uuids),
        "uuids": uuids,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] {output_file}")
    print(f"        {len(uuids)} UUIDs for {league} {season}")

    return output_file


def load_uuids_from_file(file_path: Path) -> dict:
    """Load UUIDs from JSON file

    Args:
        file_path: Path to UUID mapping JSON file

    Returns:
        Dict with league, season, and UUIDs

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is invalid JSON
    """
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


def scrape_all_leagues(season: str, headless: bool = True) -> dict[str, list[str]]:
    """Scrape all LNB leagues for game UUIDs

    Args:
        season: Season string (e.g., "2024-2025")
        headless: Run browser in headless mode

    Returns:
        Dict mapping league -> list of UUIDs
    """
    print("=" * 80)
    print("  LNB MULTI-LEAGUE UUID SCRAPER")
    print("=" * 80)
    print()
    print(f"Season: {season}")
    print(f"Leagues: {len(SCHEDULE_URLS)}")
    print()

    results = {}

    for league, url in SCHEDULE_URLS.items():
        try:
            uuids = scrape_league_schedule(league, url, headless=headless)
            results[league] = uuids

            # Save to file
            save_uuids_to_file(league, season, uuids)

        except Exception as e:
            print(f"\n[ERROR] Failed to scrape {league}: {e}")
            results[league] = []

        print()

    # Summary
    print("=" * 80)
    print("  SCRAPING SUMMARY")
    print("=" * 80)
    print()

    total_uuids = 0
    for league, uuids in results.items():
        count = len(uuids)
        total_uuids += count
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {league:20s} {count:>4} UUIDs")

    print()
    print(f"Total UUIDs extracted: {total_uuids}")
    print()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scrape LNB schedule pages for game UUIDs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scrape Elite 2 schedule
    python tools/lnb/scrape_lnb_schedule_uuids.py --league elite_2

    # Scrape all leagues
    python tools/lnb/scrape_lnb_schedule_uuids.py --all-leagues

    # Scrape with visible browser (for debugging)
    python tools/lnb/scrape_lnb_schedule_uuids.py --league elite_2 --no-headless

Supported Leagues:
    - betclic_elite: Betclic ELITE (top-tier, 16 teams)
    - elite_2: ELITE 2 (second-tier, 20 teams)
    - espoirs_elite: Espoirs ELITE (U21 top-tier)
    - espoirs_prob: Espoirs PROB (U21 second-tier)
        """,
    )

    parser.add_argument(
        "--league",
        choices=list(SCHEDULE_URLS.keys()),
        help="League to scrape",
    )

    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="Scrape all leagues",
    )

    parser.add_argument(
        "--season",
        default="2024-2025",
        help="Season string (default: 2024-2025)",
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window (for debugging)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.league and not args.all_leagues:
        parser.error("Must specify either --league or --all-leagues")

    if args.league and args.all_leagues:
        parser.error("Cannot specify both --league and --all-leagues")

    # Check Playwright
    if not is_playwright_available():
        print("[ERROR] Playwright not installed!")
        print()
        print("Install with:")
        print("  uv pip install playwright")
        print("  playwright install chromium")
        print()
        sys.exit(1)

    headless = not args.no_headless

    # Execute scraping
    if args.all_leagues:
        scrape_all_leagues(season=args.season, headless=headless)
    else:
        league = args.league
        url = SCHEDULE_URLS[league]

        print("=" * 80)
        print(f"  LNB {league.upper()} UUID SCRAPER")
        print("=" * 80)
        print()

        uuids = scrape_league_schedule(league, url, headless=headless)
        save_uuids_to_file(league, args.season, uuids, args.output_dir)

        print("=" * 80)
        print("  SCRAPING COMPLETE")
        print("=" * 80)
        print()
        print(f"Extracted {len(uuids)} UUIDs for {league} {args.season}")
        print()

    print("Next Steps:")
    print("  1. Verify UUIDs in output files")
    print("  2. Test data availability: python tools/lnb/test_elite2_data_availability.py")
    print("  3. Run bulk discovery if data available")
    print()


if __name__ == "__main__":
    main()
