#!/usr/bin/env python3
"""Discover fixture UUIDs for historical LNB seasons

This script extracts Atrium Sports fixture UUIDs for past LNB seasons by:
1. Fetching schedule for each season
2. Attempting to match LNB game IDs to Atrium fixture UUIDs
3. Storing results in fixture_uuids_by_season.json

The challenge: Atrium Sports uses UUIDs, LNB official uses numeric IDs.
We need to map between them for historical data access.

Approach:
- Try to extract UUIDs from match center URLs (if available)
- Cross-reference dates/teams between LNB schedule and Atrium data
- Manual mapping as fallback for older seasons

Usage:
    # Discover UUIDs for specific seasons
    uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 2022-2023

    # Interactive mode (prompts for manual UUID entry if needed)
    uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 --interactive

Output:
    tools/lnb/fixture_uuids_by_season.json
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import re
import time
from urllib.parse import parse_qs, urlparse

from src.cbb_data.fetchers.browser_scraper import BrowserScraper, is_playwright_available
from src.cbb_data.fetchers.lnb import fetch_lnb_schedule

# ==============================================================================
# CONFIG
# ==============================================================================

TOOLS_DIR = Path("tools/lnb")
UUID_MAPPING_FILE = TOOLS_DIR / "fixture_uuids_by_season.json"

# Known fixture UUIDs from previous discoveries
# TODO: Replace with actual discovered UUIDs
KNOWN_UUIDS = {
    "2024-2025": [
        "0cac6e1b-6715-11f0-a9f3-27e6e78614e1",
        "0cd1323f-6715-11f0-86f4-27e6e78614e1",
        "0ce02919-6715-11f0-9d01-27e6e78614e1",
        "0d0504a0-6715-11f0-98ab-27e6e78614e1",
        # Add more as discovered
    ]
}

# ==============================================================================
# UUID EXTRACTION UTILITIES
# ==============================================================================

# UUID regex pattern (36 characters: 8-4-4-4-12)
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def extract_uuid_from_text(text: str) -> str | None:
    """Extract fixture UUID from URL or raw text

    Supports multiple URL formats:
    - https://lnb.fr/fr/match-center/{uuid}
    - https://lnb.fr/fr/pre-match-center?mid={uuid}
    - Raw UUID string

    Args:
        text: URL or raw UUID string

    Returns:
        Extracted UUID or None if not found
    """
    text = text.strip()

    # Try to parse as URL first
    if text.startswith("http"):
        try:
            parsed = urlparse(text)

            # Check query parameters (e.g., ?mid=uuid)
            query_params = parse_qs(parsed.query)
            for param_name in ["mid", "match_id", "id", "uuid"]:
                if param_name in query_params:
                    uuid_candidate = query_params[param_name][0]
                    if UUID_PATTERN.fullmatch(uuid_candidate):
                        return uuid_candidate.lower()

            # Check URL path (e.g., /match-center/uuid)
            path_parts = parsed.path.split("/")
            for part in reversed(path_parts):  # Check from end
                if UUID_PATTERN.fullmatch(part):
                    return part.lower()

        except Exception as e:
            print(f"  [WARN] Failed to parse URL: {text} ({e})")

    # Try direct UUID match
    match = UUID_PATTERN.search(text)
    if match:
        return match.group(0).lower()

    return None


def extract_uuids_from_text_list(texts: list[str]) -> list[str]:
    """Extract and deduplicate UUIDs from a list of URLs/text

    Args:
        texts: List of URLs or raw UUID strings

    Returns:
        Deduplicated list of valid UUIDs
    """
    uuids = []

    for text in texts:
        uuid = extract_uuid_from_text(text)
        if uuid:
            uuids.append(uuid)
        else:
            print(f"  [WARN] Could not extract UUID from: {text}")

    # Deduplicate while preserving order
    seen = set()
    unique_uuids = []
    for uuid in uuids:
        if uuid not in seen:
            seen.add(uuid)
            unique_uuids.append(uuid)

    return unique_uuids


# ==============================================================================
# UUID DISCOVERY FUNCTIONS
# ==============================================================================


def load_existing_mappings() -> dict[str, list[str]]:
    """Load existing UUID mappings from JSON file

    Returns:
        Dict mapping season -> list of fixture UUIDs
    """
    if UUID_MAPPING_FILE.exists():
        try:
            with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
                data = json.load(f)
                # Extract only the mappings section (not metadata)
                mappings = data.get("mappings", {})
                print(f"[INFO] Loaded existing mappings: {len(mappings)} seasons")
                return mappings
        except Exception as e:
            print(f"[WARN] Failed to load existing mappings: {e}")

    return {}


def save_uuid_mappings(mappings: dict[str, list[str]]) -> None:
    """Save UUID mappings to JSON file

    Args:
        mappings: Dict mapping season -> list of fixture UUIDs
    """
    try:
        # Ensure directory exists
        UUID_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Add metadata
        output = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_seasons": len(mappings),
                "total_games": sum(len(uuids) for uuids in mappings.values()),
            },
            "mappings": mappings,
        }

        with open(UUID_MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"[SAVED] UUID mappings: {UUID_MAPPING_FILE}")
        print(
            f"        Seasons: {len(mappings)}, Total games: {sum(len(v) for v in mappings.values())}"
        )

    except Exception as e:
        print(f"[ERROR] Failed to save UUID mappings: {e}")


def try_select_historical_season(scraper: BrowserScraper, season: str) -> bool:
    """Attempt to navigate to a historical season on the LNB schedule page

    Tries multiple strategies to find and interact with season filters/selectors:
    1. Season dropdown/select elements
    2. Date filters
    3. Season navigation buttons
    4. Archive links

    Args:
        scraper: BrowserScraper instance with page already loaded
        season: Target season (e.g., "2022-2023")

    Returns:
        True if successfully navigated to historical season, False otherwise
    """
    print(f"  [SEASON-NAV] Attempting to navigate to {season} season...")

    # Extract season years for matching
    start_year, end_year = season.split("-")

    # Strategy 1: Look for season dropdown/select
    season_selectors = [
        'select[name*="season"]',
        'select[name*="saison"]',
        "select#season",
        "select#saison",
        ".season-select select",
        ".saison-select select",
    ]

    for selector in season_selectors:
        elements = scraper.find_elements(selector)
        if elements:
            print(f"  [FOUND] Season selector: {selector}")
            try:
                # Try to select the option that matches our season
                element = elements[0]

                # Get all option values
                options = scraper.find_elements(f"{selector} option")

                for option in options:
                    option_text = scraper.get_element_attribute(option, "textContent") or ""
                    option_value = scraper.get_element_attribute(option, "value") or ""

                    # Check if this option matches our season
                    if (
                        start_year in option_text
                        or start_year in option_value
                        or season in option_text
                        or season in option_value
                    ):
                        print(f"  [SELECT] Found matching season option: {option_text}")

                        # Click the option
                        option.click()
                        time.sleep(2)  # Wait for page to update

                        print(f"  [SUCCESS] Selected historical season: {season}")
                        return True

            except Exception as e:
                logger.debug(f"Failed to interact with season selector {selector}: {e}")
                continue

    # Strategy 2: Look for date filter inputs
    date_selectors = [
        'input[type="date"]',
        'input[name*="date"]',
        'input[name*="from"]',
        'input[placeholder*="date"]',
    ]

    for selector in date_selectors:
        elements = scraper.find_elements(selector)
        if elements:
            print(f"  [FOUND] Date filter: {selector}")
            try:
                # Try to set date to start of target season
                element = elements[0]

                # Set date to September of start_year (typical season start)
                target_date = f"{start_year}-09-01"

                element.fill(target_date)
                time.sleep(2)

                print(f"  [SUCCESS] Set date filter to: {target_date}")
                return True

            except Exception as e:
                logger.debug(f"Failed to set date filter {selector}: {e}")
                continue

    # Strategy 3: Look for archive/historical links
    archive_selectors = [
        'a[href*="archive"]',
        'a[href*="historique"]',
        'a[href*="saison"]',
        'button:has-text("Archive")',
        'button:has-text("Historique")',
    ]

    for selector in archive_selectors:
        elements = scraper.find_elements(selector)
        if elements:
            print(f"  [FOUND] Archive link: {selector}")
            # This would require more complex navigation logic
            # For now, just report that we found it
            print("  [INFO] Found archive selector but not implemented yet")

    print("  [WARN] No season navigation controls found")
    print("  [INFO] Schedule page may only show current season")
    return False


def discover_uuids_automated(
    season: str,
    max_games: int = 20,
    click_through_games: bool = True,
    try_historical_nav: bool = True,
) -> list[str]:
    """Automated UUID discovery using browser automation and game navigation

    Navigates to LNB schedule page, attempts to select historical season (if applicable),
    clicks through each game to access match-center, and extracts fixture UUIDs.

    Args:
        season: Season string (e.g., "2023-2024")
        max_games: Maximum games to process (default: 20)
        click_through_games: If True, click into each game to extract UUIDs (default: True)
        try_historical_nav: If True, attempt to navigate to historical season (default: True)

    Returns:
        List of discovered fixture UUIDs
    """
    print("  [AUTOMATED] Discovering UUIDs via browser automation...")

    if not is_playwright_available():
        print("  [ERROR] Playwright not installed - cannot use automated discovery")
        print("  [INFO] Install with: uv pip install playwright && playwright install chromium")
        return []

    try:
        # Determine if this is a historical season (not current)
        current_year = datetime.now().year
        season_start_year = int(season.split("-")[0])
        is_historical = season_start_year < current_year

        # Fetch schedule to get game list
        year = season.split("-")[0]
        schedule_df = fetch_lnb_schedule(season=year)

        if schedule_df.empty:
            print(f"  [WARN] No schedule data for season {season}")
            return []

        print(f"  [INFO] Found {len(schedule_df)} games in schedule")

        # Limit to max_games for discovery
        games_to_process = min(len(schedule_df), max_games)
        if games_to_process < len(schedule_df):
            print(f"  [INFO] Limited to {games_to_process} games for discovery")

        discovered_uuids = []

        with BrowserScraper(headless=True, capture_network=True, timeout=60000) as scraper:
            # Navigate to schedule page
            schedule_url = "https://www.lnb.fr/pro-a/calendrier"
            print(f"  [NAVIGATE] LNB schedule: {schedule_url}")

            scraper.get_rendered_html(
                url=schedule_url,
                wait_for="body",
                wait_time=3.0,  # Wait for dynamic content
            )

            # Try to navigate to historical season if needed
            if is_historical and try_historical_nav:
                historical_nav_success = try_select_historical_season(scraper, season)

                if historical_nav_success:
                    print(f"  [INFO] Successfully navigated to historical season {season}")
                    # Wait for page to reload with historical data
                    time.sleep(2)
                else:
                    # CRITICAL: For historical seasons, inability to navigate is a FATAL error
                    print(f"  [FATAL] Could not navigate to historical season {season}")
                    print(
                        "          The LNB calendar page does not expose season navigation controls."
                    )
                    print("          Automated discovery ONLY works for the current season.\n")
                    print("  [SOLUTION] Use manual file-based discovery instead:")
                    print(f"             1. Manually browse {season} games on https://www.lnb.fr")
                    print("             2. Save match-center URLs to a text file")
                    print(
                        "             3. Run: python tools/lnb/discover_historical_fixture_uuids.py \\"
                    )
                    print(f"                       --seasons {season} --from-file <urls.txt>\n")
                    print(f"  [ABORT] Returning empty UUID list for {season}")
                    return []

            # Try basic network extraction first (fast path)
            uuids_from_requests = scraper.extract_uuid_from_requests(
                domain_pattern="atriumsports.com"
            )

            if uuids_from_requests:
                print(
                    f"  [SUCCESS] Extracted {len(uuids_from_requests)} UUIDs from network requests"
                )
                discovered_uuids.extend(uuids_from_requests)

            # Click through games if enabled and we don't have enough UUIDs
            if click_through_games and len(discovered_uuids) < games_to_process:
                print("  [CLICK-THROUGH] Navigating to individual game pages...")

                # Find all game rows/links
                # LNB schedule typically has clickable rows that navigate to match-center
                # Try multiple selectors to find game links
                game_selectors = [
                    'a[href*="match-center"]',  # Direct links to match-center
                    'a[href*="pre-match-center"]',  # Pre-match links
                    'tr[data-href*="match-center"]',  # Rows with data-href to match-center
                    "tr.game-row a",  # Links within game rows
                    "tbody tr a",  # Links within table body rows
                ]

                game_elements = []
                for selector in game_selectors:
                    elements = scraper.find_elements(selector)
                    if elements:
                        print(f"  [FOUND] {len(elements)} elements with selector: {selector}")
                        game_elements = elements[:games_to_process]  # Limit to max_games
                        break

                if not game_elements:
                    print("  [WARN] No game elements found on schedule page")
                    print(f"  [INFO] Tried selectors: {game_selectors}")
                else:
                    # CRITICAL: Collect all URLs BEFORE navigating (elements will become stale after navigation)
                    print(f"  [INFO] Collecting URLs from {len(game_elements)} game elements...")

                    game_urls = []
                    for element in game_elements:
                        try:
                            href = scraper.get_element_attribute(element, "href")
                            data_href = scraper.get_element_attribute(element, "data-href")

                            match_url = href or data_href

                            if match_url:
                                # If relative URL, make it absolute
                                if not match_url.startswith("http"):
                                    if match_url.startswith("/"):
                                        match_url = f"https://www.lnb.fr{match_url}"
                                    else:
                                        match_url = f"https://www.lnb.fr/{match_url}"

                                game_urls.append(match_url)
                        except Exception as e:
                            logger.warning(f"Failed to get URL from element: {e}")
                            continue

                    # Deduplicate URLs (in case multiple links point to same game)
                    unique_game_urls = list(dict.fromkeys(game_urls))  # Preserves order
                    print(f"  [INFO] Found {len(unique_game_urls)} unique game URLs")

                    # Now navigate to each game
                    for i, match_url in enumerate(unique_game_urls[:games_to_process], 1):
                        try:
                            print(
                                f"  [{i}/{min(len(unique_game_urls), games_to_process)}] Navigating to: {match_url[:60]}..."
                            )

                            scraper.get_rendered_html(url=match_url, wait_for="body", wait_time=1.0)

                            # Extract UUID from current URL (page may redirect)
                            current_url = scraper.get_current_url()

                            # Try extracting from both the original match_url and current_url
                            # (in case page doesn't redirect or query params are preserved)
                            uuid = extract_uuid_from_text(match_url)
                            if not uuid:
                                uuid = extract_uuid_from_text(current_url)

                            if uuid:
                                print(f"           ✅ Extracted UUID: {uuid}")
                                discovered_uuids.append(uuid)
                            else:
                                print("           ⚠️  No UUID found")
                                print(f"                Match URL: {match_url}")
                                print(f"                Current URL: {current_url}")

                        except Exception as e:
                            print(f"           ❌ Failed to process game {i}: {e}")
                            continue

        # Deduplicate and return unique UUIDs
        unique_uuids = list(set(discovered_uuids))
        print(f"  [RESULT] Total unique UUIDs: {len(unique_uuids)}")

        return unique_uuids

    except Exception as e:
        print(f"  [ERROR] Automated discovery failed: {e}")
        import traceback

        traceback.print_exc()
        return []


def discover_uuids_for_season(
    season: str, interactive: bool = False, automated: bool = True, from_file: str | None = None
) -> list[str]:
    """Discover fixture UUIDs for a specific season

    Args:
        season: Season string (e.g., "2023-2024")
        interactive: If True, prompt user for manual UUID entry
        automated: If True, try automated discovery first (default: True)
        from_file: Optional path to file containing URLs/UUIDs (one per line)

    Returns:
        List of fixture UUIDs
    """
    print(f"\n[DISCOVERING] Season {season}...")

    # Check if UUIDs provided via file
    if from_file:
        print(f"  [FILE] Loading UUIDs from {from_file}")
        try:
            with open(from_file, encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            uuids = extract_uuids_from_text_list(lines)

            print(f"  [SUCCESS] Loaded {len(lines)} lines, extracted {len(uuids)} unique UUIDs")

            if uuids:
                print("  [INFO] Extracted UUIDs:")
                for i, uuid in enumerate(uuids, 1):
                    print(f"    {i:2d}. {uuid}")

            return uuids

        except Exception as e:
            print(f"  [ERROR] Failed to load from file: {e}")
            return []

    # Check if already known
    if season in KNOWN_UUIDS:
        print(f"  [INFO] Using {len(KNOWN_UUIDS[season])} known UUIDs")
        return KNOWN_UUIDS[season]

    # Try automated discovery first (if enabled and Playwright available)
    if automated and is_playwright_available():
        print("  [STRATEGY] Attempting automated discovery...")
        uuids = discover_uuids_automated(season, max_games=20)

        if uuids:
            print(f"  [SUCCESS] Automated discovery found {len(uuids)} UUIDs")
            return uuids
        else:
            print("  [WARN] Automated discovery found no UUIDs")

    # Try to fetch schedule for manual mode
    try:
        # Convert to calendar year (e.g., "2023-2024" -> "2023")
        year = season.split("-")[0]
        schedule_df = fetch_lnb_schedule(season=year)

        if schedule_df.empty:
            print(f"  [WARN] No schedule data for season {season}")
            return []

        print(f"  [INFO] Found {len(schedule_df)} games in schedule")

        # Interactive mode: manual UUID entry
        if interactive:
            print(f"\n  [INTERACTIVE] Manual UUID entry for {season}")
            print("  Enter fixture UUIDs or match center URLs, one per line")
            print("  Supported formats:")
            print("    - Raw UUID: 0cac6e1b-6715-11f0-a9f3-27e6e78614e1")
            print(
                "    - Match center URL: https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1"
            )
            print(
                "    - Pre-match URL: https://lnb.fr/fr/pre-match-center?mid=0cac6e1b-6715-11f0-a9f3-27e6e78614e1"
            )
            print("  Press Enter on empty line to finish.")
            print()

            raw_inputs = []
            while True:
                user_input = input("  URL or UUID: ").strip()
                if not user_input:
                    break
                raw_inputs.append(user_input)

            # Extract UUIDs from all inputs
            uuids = extract_uuids_from_text_list(raw_inputs)

            print(
                f"\n  [INFO] Entered {len(raw_inputs)} items, extracted {len(uuids)} unique UUIDs"
            )

            if uuids:
                print("  [SUCCESS] Extracted UUIDs:")
                for i, uuid in enumerate(uuids, 1):
                    print(f"    {i:2d}. {uuid}")

            return uuids

        else:
            print("  [INFO] No UUIDs discovered")
            print(
                "  [HINT] Try --interactive mode for manual entry, or check Playwright installation"
            )
            return []

    except Exception as e:
        print(f"  [ERROR] Failed to discover UUIDs: {e}")
        return []


def discover_all_seasons(
    seasons: list[str], interactive: bool = False, from_file: str | None = None
) -> dict[str, list[str]]:
    """Discover fixture UUIDs for multiple seasons

    Args:
        seasons: List of season strings
        interactive: If True, prompt for manual UUID entry
        from_file: Optional path to file containing URLs/UUIDs

    Returns:
        Dict mapping season -> list of fixture UUIDs
    """
    print(f"\n{'='*80}")
    print("  FIXTURE UUID DISCOVERY")
    print(f"{'='*80}\n")

    print(f"Seasons to process: {seasons}")
    print(f"Interactive mode: {interactive}")
    if from_file:
        print(f"Loading from file: {from_file}")
    print()

    # Load existing mappings
    all_mappings = load_existing_mappings()

    # Track newly discovered mappings for validation
    newly_discovered = {}

    # Discover UUIDs for each season
    for season in seasons:
        uuids = discover_uuids_for_season(season, interactive, from_file=from_file)

        if uuids:
            newly_discovered[season] = uuids
        else:
            print(f"  [WARN] No UUIDs discovered for {season}")

    # VALIDATION: Detect duplicate UUID sets across seasons
    if len(newly_discovered) > 1:
        print(f"\n{'='*80}")
        print("  VALIDATING DISCOVERED UUIDS")
        print(f"{'='*80}\n")

        # Compare UUID sets across newly discovered seasons
        season_uuid_sets = {season: set(uuids) for season, uuids in newly_discovered.items()}

        duplicates = []
        for season1, uuids1 in season_uuid_sets.items():
            for season2, uuids2 in season_uuid_sets.items():
                if season1 < season2 and uuids1 == uuids2:
                    duplicates.append((season1, season2, len(uuids1)))

        if duplicates:
            print("[ERROR] Duplicate UUID sets detected across seasons!")
            print("        This likely means the scraper is fetching the current schedule")
            print("        for all requested seasons (unable to navigate to historical data).\n")

            for s1, s2, count in duplicates:
                print(f"  - {s1} and {s2} have identical {count} UUIDs")

            print(
                "\n[SOLUTION] The LNB calendar page does not expose historical season navigation."
            )
            print("           Use one of these approaches instead:\n")
            print("  1. MANUAL FILE-BASED:")
            print("     - Manually browse each season's games on the LNB website")
            print("     - Copy match-center URLs to a text file (one per line)")
            print("     - Run: python tools/lnb/discover_historical_fixture_uuids.py \\")
            print("              --seasons <SEASON> --from-file <urls.txt>\n")
            print("  2. API-BASED (if you find the JSON endpoint):")
            print("     - Use browser DevTools to find the schedule JSON API")
            print("     - Add a new fetcher function to src.cbb_data.fetchers.lnb")
            print("     - Modify this script to use the JSON endpoint\n")

            print("[ACTION] Refusing to write duplicate UUIDs as historical seasons.")
            print("         Saving as 'current_round' instead.\n")

            # Save only as current_round
            if newly_discovered:
                # Take any season's UUIDs (they're all the same)
                first_season = list(newly_discovered.keys())[0]
                all_mappings["current_round"] = newly_discovered[first_season]
                print(
                    f"[SAVED] {len(newly_discovered[first_season])} UUIDs saved under 'current_round'"
                )

            return all_mappings

        else:
            print("[OK] No duplicate UUID sets detected across seasons")
            print("     Each season has unique fixtures ✅\n")

    # If validation passed, merge newly discovered into all_mappings
    all_mappings.update(newly_discovered)

    return all_mappings


def print_summary(mappings: dict[str, list[str]]) -> None:
    """Print summary of discovered UUIDs

    Args:
        mappings: Dict mapping season -> list of fixture UUIDs (season names as keys)
    """
    print(f"\n{'='*80}")
    print("  DISCOVERY SUMMARY")
    print(f"{'='*80}\n")

    if not mappings:
        print("[WARN] No UUID mappings available")
        return

    # Filter out any non-season keys (like metadata, etc) - season format is "YYYY-YYYY"
    season_mappings = {
        k: v for k, v in mappings.items() if isinstance(v, list) and "-" in k and len(k) == 9
    }

    if not season_mappings:
        print("[WARN] No valid season mappings found")
        return

    total_games = sum(len(uuids) for uuids in season_mappings.values())

    print(f"Total seasons: {len(season_mappings)}")
    print(f"Total games with UUIDs: {total_games}")
    print()

    print("Per-season breakdown:")
    for season in sorted(season_mappings.keys(), reverse=True):
        uuids = season_mappings[season]
        print(f"  {season:12s} : {len(uuids):4d} games")

    print()

    # Show what's available for historical pull
    if total_games > 0:
        print("✅ Ready for historical data pull!")
        print()
        print("Next steps:")
        print("  1. Build game index with UUIDs:")
        print(
            f"     uv run python tools/lnb/build_game_index.py --seasons {' '.join(sorted(season_mappings.keys()))}"
        )
        print()
        print("  2. Bulk ingest PBP + shots:")
        print(
            f"     uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons {' '.join(sorted(season_mappings.keys()))}"
        )
    else:
        print("⚠️  No UUIDs available yet")
        print("Use --interactive mode to manually enter UUIDs, or")
        print("investigate Atrium Sports API/website for UUID extraction methods")

    print()


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Discover fixture UUIDs for historical LNB seasons",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Discover UUIDs for specific seasons (non-interactive)
    uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 2022-2023

    # Interactive mode (prompts for manual UUID entry)
    uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 --interactive

    # Show current mappings
    uv run python tools/lnb/discover_historical_fixture_uuids.py --show

Notes:
    - Atrium Sports uses fixture UUIDs (not LNB numeric IDs)
    - Automatic discovery is limited by available data sources
    - Interactive mode allows manual UUID entry from browser inspection
    - UUIDs can be found by inspecting network requests in match center

Output:
    tools/lnb/fixture_uuids_by_season.json
        """,
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        help='Seasons to discover UUIDs for (e.g., "2023-2024" "2022-2023")',
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode (prompts for manual UUID entry)",
    )

    parser.add_argument(
        "--from-file", type=str, default=None, help="Load UUIDs/URLs from file (one per line)"
    )

    parser.add_argument("--show", action="store_true", help="Show current UUID mappings and exit")

    args = parser.parse_args()

    # Show current mappings
    if args.show:
        mappings = load_existing_mappings()
        print_summary(mappings.get("mappings", {}))
        return

    # Validate input
    if not args.seasons:
        print("[ERROR] No seasons specified")
        print("Usage: --seasons 2023-2024 2022-2023")
        print("   or: --show to view current mappings")
        sys.exit(1)

    # Discover UUIDs
    mappings = discover_all_seasons(args.seasons, args.interactive, args.from_file)

    # Save results
    if mappings:
        save_uuid_mappings(mappings)

    # Print summary
    print_summary(mappings)


if __name__ == "__main__":
    main()
