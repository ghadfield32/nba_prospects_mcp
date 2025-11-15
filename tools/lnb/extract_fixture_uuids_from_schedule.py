#!/usr/bin/env python3
"""Extract fixture UUIDs from LNB schedule page URLs

This script:
1. Loads the LNB Pro A schedule page with Playwright
2. Finds all links to match-center pages
3. Extracts fixture UUIDs from the URLs
4. Saves them to a file for stress testing

The fixture UUIDs are needed for the Atrium Sports API calls.

Usage:
    uv run python tools/lnb/extract_fixture_uuids_from_schedule.py

Output:
    tools/lnb/fixture_uuids_for_stress_test.json
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:
    print("[ERROR] Playwright not installed!")
    print("Install with: uv pip install playwright && playwright install chromium")
    sys.exit(1)

# ==============================================================================
# CONFIG
# ==============================================================================

SCHEDULE_URL = "https://www.lnb.fr/pro-a/calendrier"
OUTPUT_FILE = Path("tools/lnb/fixture_uuids_for_stress_test.json")

# Regex pattern to extract UUID from match-center URLs
# Example URL: https://lnb.fr/fr/match-center/3522345e-3362-11f0-b97d-7be2bdc7a840
UUID_PATTERN = re.compile(
    r"/match-center/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", re.IGNORECASE
)

# ==============================================================================
# EXTRACTION LOGIC
# ==============================================================================


def extract_fixture_uuids_from_page(page: Page) -> list[dict[str, Any]]:
    """Extract all fixture UUIDs from the schedule page

    Returns list of dicts with:
        - fixture_uuid: UUID for Atrium API
        - match_url: Full match-center URL
        - home_team: Home team name (if available)
        - away_team: Away team name (if available)
        - date: Game date (if available)
    """
    extracted_games = []

    print("[INFO] Looking for match-center links...")

    # Find all links that contain "match-center"
    links = page.locator('a[href*="match-center"]').all()

    print(f"[INFO] Found {len(links)} match-center links")

    for link in links:
        try:
            href = link.get_attribute("href")
            if not href:
                continue

            # Extract UUID from URL
            match = UUID_PATTERN.search(href)
            if not match:
                continue

            fixture_uuid = match.group(1)

            # Try to extract team names and date from the link or nearby elements
            link_text = link.inner_text().strip() if link.is_visible() else ""

            # Check if we've already added this UUID
            if any(g["fixture_uuid"] == fixture_uuid for g in extracted_games):
                continue

            game_info = {
                "fixture_uuid": fixture_uuid,
                "match_url": f"https://lnb.fr{href}" if href.startswith("/") else href,
                "link_text": link_text,
            }

            extracted_games.append(game_info)
            print(f"[OK] Found UUID: {fixture_uuid}")

        except Exception as e:
            print(f"[WARN] Error processing link: {e}")
            continue

    return extracted_games


def extract_uuids_with_playwright() -> list[dict[str, Any]]:
    """Use Playwright to load the schedule page and extract UUIDs"""

    print(f"\n{'='*80}")
    print("  EXTRACTING FIXTURE UUIDs FROM LNB SCHEDULE")
    print(f"{'='*80}\n")

    print(f"[INFO] Loading schedule page: {SCHEDULE_URL}")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        page = context.new_page()

        try:
            # Navigate to schedule page
            page.goto(SCHEDULE_URL, timeout=30000, wait_until="networkidle")
            print("[OK] Page loaded")

            # Wait for content to render
            time.sleep(3)

            # Extract UUIDs
            games = extract_fixture_uuids_from_page(page)

            print(f"\n[SUCCESS] Extracted {len(games)} unique fixture UUIDs")

            return games

        except Exception as e:
            print(f"[ERROR] Failed to extract UUIDs: {e}")
            import traceback

            traceback.print_exc()
            return []

        finally:
            browser.close()


def save_extracted_uuids(games: list[dict[str, Any]], output_path: Path) -> None:
    """Save extracted UUIDs to JSON file"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "extracted_at": datetime.now().isoformat(),
        "source_url": SCHEDULE_URL,
        "total_games": len(games),
        "fixture_uuids": [g["fixture_uuid"] for g in games],  # List of just UUIDs
        "games": games,  # Full game info
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Saved {len(games)} fixture UUIDs to {output_path}")


def print_summary(games: list[dict[str, Any]]) -> None:
    """Print summary of extracted UUIDs"""
    print(f"\n{'='*80}")
    print("  EXTRACTION SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total fixture UUIDs extracted: {len(games)}")

    print("\nSample UUIDs (first 10):")
    for i, game in enumerate(games[:10], 1):
        print(f"  {i}. {game['fixture_uuid']}")
        if game.get("link_text"):
            print(f"     Text: {game['link_text'][:60]}")

    print(f"\nAll UUIDs saved to: {OUTPUT_FILE}")


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    print("=" * 80)
    print("  LNB FIXTURE UUID EXTRACTION")
    print("=" * 80)

    # Extract UUIDs using Playwright
    games = extract_uuids_with_playwright()

    if not games:
        print("\n[ERROR] No fixture UUIDs extracted!")
        print("\nPossible reasons:")
        print("  1. Schedule page structure changed")
        print("  2. Network/timeout issues")
        print("  3. JavaScript failed to load")
        return

    # Save results
    save_extracted_uuids(games, OUTPUT_FILE)

    # Print summary
    print_summary(games)

    print(f"\n{'='*80}")
    print("  NEXT STEPS")
    print(f"{'='*80}")
    print("\n1. Review extracted UUIDs:")
    print(f"   {OUTPUT_FILE}")
    print("\n2. Update stress test script:")
    print("   Edit tools/lnb/run_lnb_stress_tests.py")
    print("   Add UUIDs to TEST_GAME_UUIDS list")
    print("\n3. Run comprehensive stress tests:")
    print("   uv run python tools/lnb/run_lnb_stress_tests.py")
    print()


if __name__ == "__main__":
    main()
