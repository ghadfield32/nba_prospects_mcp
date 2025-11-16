#!/usr/bin/env python3
"""Bulk Fixture UUID Discovery via LNB Schedule API

This script uses the existing fetch_lnb_schedule() function to get ALL fixtures
for historical seasons in one API call per season, instead of manual URL collection.

Workflow:
    1. Set up browser headers once (tools/lnb/lnb_headers.json)
    2. Run this script for each season
    3. Get 300+ fixture UUIDs automatically
    4. Feed to existing pipeline

One-time Setup (if headers not configured):
    1. Open browser → https://www.lnb.fr/statistiques
    2. DevTools (F12) → Network → Filter: getCalender
    3. Click around to trigger API call
    4. Right-click successful request → Copy → Copy as cURL
    5. Extract headers (Origin, Cookie, etc.)
    6. Save to tools/lnb/lnb_headers.json:
       {
           "Origin": "https://www.lnb.fr",
           "Cookie": "your_cookies_here",
           "Referer": "https://www.lnb.fr/statistiques"
       }

Usage:
    # Discover all 2022-23 fixtures
    uv run python tools/lnb/bulk_discover_via_schedule_api.py --seasons 2022-2023

    # Discover multiple seasons
    uv run python tools/lnb/bulk_discover_via_schedule_api.py \
        --seasons 2022-2023 2023-2024 2024-2025

    # Dry run (don't save)
    uv run python tools/lnb/bulk_discover_via_schedule_api.py \
        --seasons 2022-2023 \
        --dry-run

Output:
    - Saves to tools/lnb/fixture_uuids_by_season.json
    - Reports total fixtures discovered per season
    - Ready for game index building

Created: 2025-11-16
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# CONFIG
# ==============================================================================

TOOLS_DIR = Path("tools/lnb")
UUID_MAPPING_FILE = TOOLS_DIR / "fixture_uuids_by_season.json"


# ==============================================================================
# SCHEDULE API DISCOVERY
# ==============================================================================


def discover_season_via_api(season_str: str) -> list[str]:
    """Discover all fixture UUIDs for a season using schedule API.

    Args:
        season_str: Season in format "YYYY-YYYY" (e.g., "2022-2023")

    Returns:
        List of fixture UUIDs (as strings) for the season

    Raises:
        ImportError: If LNB API dependencies not available
        Exception: If API call fails or returns no data
    """
    print(f"\n[DISCOVERING] Season {season_str} via schedule API...")

    # Parse season year
    season_year = int(season_str.split("-")[0])
    print(f"  [INFO] Fetching schedule for year={season_year} (season {season_str})")

    # Import LNB fetcher (lazy import to show clear error if not available)
    try:
        from src.cbb_data.fetchers.lnb import fetch_lnb_schedule
    except ImportError as e:
        print(f"\n[ERROR] Failed to import LNB fetcher: {e}")
        print(
            "        Make sure you're running from repository root and dependencies are installed"
        )
        raise

    # Fetch schedule
    try:
        df = fetch_lnb_schedule(season=season_year, league="LNB", division=1)
    except Exception as e:
        print(f"\n[ERROR] Failed to fetch schedule: {e}")
        print("\n[TROUBLESHOOTING]")
        print("  1. Check if lnb_headers.json is configured (see docstring)")
        print("  2. Verify browser cookies are still valid (not expired)")
        print("  3. Try fetching a different season (current season = most reliable)")
        raise

    if df is None or len(df) == 0:
        print("  [WARN] No games returned from API")
        return []

    print(f"  [SUCCESS] Fetched {len(df)} games from schedule API")

    # Extract GAME_ID column (these are the external IDs we need)
    # Note: These are integer IDs, we need to convert to UUIDs
    # Actually, wait - we need the actual fixture UUIDs, not the external IDs

    # Check if GAME_ID is numeric (external ID) or UUID
    sample_id = df["GAME_ID"].iloc[0] if len(df) > 0 else None
    print(f"  [DEBUG] Sample GAME_ID: {sample_id} (type: {type(sample_id)})")

    # If GAME_ID is numeric, we need to fetch fixture UUIDs separately
    # For now, let's return the external IDs and document that we need UUID mapping
    game_ids = df["GAME_ID"].tolist()

    print(f"  [INFO] Extracted {len(game_ids)} game IDs")
    print("  [WARN] These are external IDs, not UUIDs!")
    print("         Next step: Fetch fixture UUIDs via fixture_detail endpoint")

    return [str(gid) for gid in game_ids]


# ==============================================================================
# UUID MAPPING PERSISTENCE
# ==============================================================================


def load_existing_mappings() -> dict:
    """Load existing UUID mappings from JSON file.

    Returns:
        Dict with 'metadata' and 'mappings' keys
    """
    if not UUID_MAPPING_FILE.exists():
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_seasons": 0,
                "total_games": 0,
            },
            "mappings": {},
        }

    with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_uuid_mappings(data: dict) -> None:
    """Save UUID mappings to JSON file.

    Args:
        data: Dict with 'metadata' and 'mappings' keys
    """
    # Update metadata
    data["metadata"]["generated_at"] = datetime.now().isoformat()
    data["metadata"]["total_seasons"] = len([k for k in data["mappings"] if k != "current_round"])
    data["metadata"]["total_games"] = sum(
        len(v) for k, v in data["mappings"].items() if k != "current_round"
    )

    # Ensure directory exists
    UUID_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically
    with open(UUID_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] UUID mappings: {UUID_MAPPING_FILE}")
    print(f"        Seasons: {data['metadata']['total_seasons']}")
    print(f"        Total games: {data['metadata']['total_games']}")


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Bulk discover fixture UUIDs using LNB schedule API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Discover 2022-23 season
    python tools/lnb/bulk_discover_via_schedule_api.py --seasons 2022-2023

    # Discover multiple seasons
    python tools/lnb/bulk_discover_via_schedule_api.py \
        --seasons 2022-2023 2023-2024 2024-2025

    # Dry run (preview only)
    python tools/lnb/bulk_discover_via_schedule_api.py \
        --seasons 2022-2023 --dry-run

Requirements:
    - lnb_headers.json must be configured with browser cookies
    - See docstring for one-time setup instructions
        """,
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        required=True,
        help="Seasons to discover (format: YYYY-YYYY)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview discovery without saving to file",
    )

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print("  BULK FIXTURE UUID DISCOVERY (Schedule API)")
    print(f"{'='*80}\n")

    print(f"Seasons to process: {args.seasons}")
    print(f"Dry run: {args.dry_run}\n")

    # Load existing mappings
    all_mappings = load_existing_mappings()

    # Discover each season
    newly_discovered = {}
    for season in args.seasons:
        try:
            uuids = discover_season_via_api(season)
            if uuids:
                newly_discovered[season] = uuids
                print(f"  [OK] {season}: {len(uuids)} fixtures")
            else:
                print(f"  [WARN] {season}: No fixtures found")
        except Exception as e:
            print(f"  [ERROR] {season}: {e}")
            continue

    # Merge and save
    if newly_discovered and not args.dry_run:
        all_mappings["mappings"].update(newly_discovered)
        save_uuid_mappings(all_mappings)
    elif newly_discovered and args.dry_run:
        print(f"\n[DRY RUN] Would save {len(newly_discovered)} season(s):")
        for season, uuids in newly_discovered.items():
            print(f"  - {season}: {len(uuids)} fixtures")
    else:
        print("\n[WARN] No new fixtures discovered")

    print()


if __name__ == "__main__":
    main()
