#!/usr/bin/env python3
"""Merge Betclic ELITE and Elite 2 fixtures for 2024-2025 season

The bulk_discover script overwrites fixtures per season. We need both leagues
in the same 2024-2025 array so the game index builder can process all games.

This script:
1. Discovers Betclic ELITE 2024-2025 fixtures (174 games)
2. Discovers Elite 2 2024-2025 fixtures (272 games)
3. Merges both into single 2024-2025 array (446 total games)
4. Saves to fixture_uuids_by_season.json

Created: 2025-11-18
"""

from __future__ import annotations

import io
import json
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

import requests

from src.cbb_data.fetchers.lnb_league_config import (
    BETCLIC_ELITE_SEASONS,
    ELITE_2_SEASONS,
)

# ==============================================================================
# CONFIG
# ==============================================================================

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURES_ENDPOINT = "/v1/embed/12/fixtures"
UUID_MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")

TIMEOUT = 15


# ==============================================================================
# DISCOVERY
# ==============================================================================


def discover_fixtures(competition_id: str, season_id: str, league_name: str) -> list[str]:
    """Discover fixtures for a league/season"""
    print(f"\n[DISCOVERING] {league_name} 2024-2025...")

    url = f"{ATRIUM_API_BASE}{FIXTURES_ENDPOINT}"
    params = {
        "competitionId": competition_id,
        "seasonId": season_id,
    }

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        fixtures = data.get("data", {}).get("fixtures", [])

        if not isinstance(fixtures, list):
            raise ValueError(f"Expected fixtures array, got {type(fixtures)}")

        fixture_uuids = []
        for fixture in fixtures:
            fixture_id = fixture.get("fixtureId")
            if fixture_id:
                fixture_uuids.append(fixture_id)

        print(f"  [OK] Discovered {len(fixture_uuids)} fixtures")
        if fixture_uuids:
            print(f"  [SAMPLE] First: {fixture_uuids[0]}")
            print(f"  [SAMPLE] Last:  {fixture_uuids[-1]}")

        return fixture_uuids

    except Exception as e:
        print(f"  [ERROR] {e}")
        raise


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    print("=" * 80)
    print("  MERGE BETCLIC ELITE + ELITE 2 FOR 2024-2025")
    print("=" * 80)
    print()
    print("Goal: Combine both leagues into single 2024-2025 fixture array")
    print()

    # Get metadata
    betclic_meta = BETCLIC_ELITE_SEASONS["2024-2025"]
    elite2_meta = ELITE_2_SEASONS["2024-2025"]

    # Discover both leagues
    print("[1/3] Discovering Betclic ELITE 2024-2025...")
    betclic_fixtures = discover_fixtures(
        competition_id=betclic_meta["competition_id"],
        season_id=betclic_meta["season_id"],
        league_name="Betclic ELITE",
    )

    print("\n[2/3] Discovering Elite 2 2024-2025...")
    elite2_fixtures = discover_fixtures(
        competition_id=elite2_meta["competition_id"],
        season_id=elite2_meta["season_id"],
        league_name="Elite 2",
    )

    # Merge (remove duplicates if any)
    print("\n[3/3] Merging fixtures...")
    all_fixtures = betclic_fixtures + elite2_fixtures
    unique_fixtures = list(dict.fromkeys(all_fixtures))  # Preserve order, remove dupes

    print(f"  Betclic ELITE: {len(betclic_fixtures)} fixtures")
    print(f"  Elite 2: {len(elite2_fixtures)} fixtures")
    print(f"  Total: {len(all_fixtures)} fixtures")
    print(f"  Unique: {len(unique_fixtures)} fixtures")

    if len(unique_fixtures) < len(all_fixtures):
        dupes = len(all_fixtures) - len(unique_fixtures)
        print(f"  ⚠️  Removed {dupes} duplicate fixture(s)")

    # Load existing mappings
    print("\n[SAVING] Loading existing mappings...")
    if UUID_MAPPING_FILE.exists():
        with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
            all_mappings = json.load(f)
    else:
        all_mappings = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_seasons": 0,
                "total_games": 0,
                "discovery_method": "atrium_api",
            },
            "mappings": {},
        }

    # Update 2024-2025 with merged fixtures
    all_mappings["mappings"]["2024-2025"] = unique_fixtures

    # Update metadata
    all_mappings["metadata"]["generated_at"] = datetime.now().isoformat()
    all_mappings["metadata"]["total_seasons"] = len(
        [k for k in all_mappings["mappings"] if k != "current_round"]
    )
    all_mappings["metadata"]["total_games"] = sum(
        len(v) for k, v in all_mappings["mappings"].items() if k != "current_round"
    )

    # Save
    UUID_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UUID_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(all_mappings, f, indent=2, ensure_ascii=False)

    print(f"[OK] Saved to {UUID_MAPPING_FILE}")
    print(f"     Total seasons: {all_mappings['metadata']['total_seasons']}")
    print(f"     Total games: {all_mappings['metadata']['total_games']}")
    print()
    print("=" * 80)
    print("  MERGE COMPLETE - Ready for game index building!")
    print("=" * 80)


if __name__ == "__main__":
    main()
