#!/usr/bin/env python3
"""Check Elite 2 Season Status

Final hypothesis: Elite 2 season may not have started yet, which is why
the website shows Betclic ELITE games on the Elite 2 calendar page.

This script checks:
1. Are there any scheduled Elite 2 games in the API at all?
2. What's the start date of Elite 2 2024-2025 season?
3. How many games are in the Elite 2 season structure?

Created: 2025-11-18
"""

from __future__ import annotations

import io
import sys
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

TIMEOUT = 15


# ==============================================================================
# INVESTIGATION
# ==============================================================================


def check_season_via_api(league_name: str, season_dict: dict, season_year: str):
    """Check what fixtures are available for a season via API"""
    print(f"\n{'='*80}")
    print(f"  {league_name.upper()} {season_year}")
    print(f"{'='*80}\n")

    competition_id = season_dict["competition_id"]
    season_id = season_dict["season_id"]

    print(f"Competition ID: {competition_id}")
    print(f"Season ID: {season_id}")
    print()

    # Try the API with seasonId parameter (we learned this works in TEST 3)
    url = f"{ATRIUM_API_BASE}{FIXTURES_ENDPOINT}"
    params = {
        "competitionId": competition_id,
        "seasonId": season_id,
    }

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            data_obj = data.get("data", {})

            print("[API RESPONSE]")
            print("  HTTP Status: 200 OK")
            print(f"  Returned Season ID: {data_obj.get('seasonId', 'N/A')}")
            print(f"  Season ID Match: {data_obj.get('seasonId') == season_id}")

            # Extract fixtures array (CORRECT PATH based on working code)
            # Structure: {data: {fixtures: [{fixtureId: ..., ...}, ...]}}
            fixtures = data_obj.get("fixtures", [])

            total_fixtures = 0

            print("\n[FIXTURES ARRAY]")
            print(f"  Type: {type(fixtures)}")

            if isinstance(fixtures, list):
                total_fixtures = len(fixtures)
                print(f"  Total fixtures: {total_fixtures}")

                # Sample first 3 fixtures
                for i, fixture in enumerate(fixtures[:3], 1):
                    if isinstance(fixture, dict):
                        fixture_id = fixture.get("fixtureId")
                        status = fixture.get("status")
                        name = fixture.get("name")
                        date = fixture.get("startDate")

                        print(f"\n  [{i}] {name if name else 'N/A'}")
                        print(f"      ID: {fixture_id}")
                        print(f"      Status: {status}")
                        print(f"      Date: {date}")
            elif isinstance(fixtures, dict):
                # Sometimes fixtures is an object/dict instead of array
                total_fixtures = len(fixtures)
                print(f"  Total fixture entries: {total_fixtures}")

                # Sample a fixture
                for fixture_id, fixture_info in list(fixtures.items())[:3]:
                    if isinstance(fixture_info, dict):
                        status = fixture_info.get("status")
                        date = fixture_info.get("startDate")
                        print(f"    {fixture_id[:16]}...: status={status}, date={date}")

            print("\n[SUMMARY]")
            print(f"  Total fixtures found: {total_fixtures}")

            if total_fixtures == 0:
                print("\n  ⚠️  NO FIXTURES FOUND - Season may not have started yet")
            else:
                print(f"\n  ✓ {total_fixtures} fixtures found in this season")

        else:
            print("[API RESPONSE]")
            print(f"  HTTP Status: {response.status_code}")
            print("  ERROR: Failed to fetch season data")

    except Exception as e:
        print(f"[ERROR] {e}")


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    print("=" * 80)
    print("  ELITE 2 SEASON STATUS CHECK")
    print("=" * 80)
    print()
    print("Hypothesis: Elite 2 season may not have started yet,")
    print("            which is why the calendar shows Betclic ELITE games.")
    print()

    # Check Betclic ELITE (baseline - should have games)
    check_season_via_api(
        "Betclic ELITE",
        BETCLIC_ELITE_SEASONS["2024-2025"],
        "2024-2025",
    )

    # Check Elite 2 current season
    check_season_via_api(
        "Elite 2",
        ELITE_2_SEASONS["2024-2025"],
        "2024-2025",
    )

    # Check Elite 2 previous season (for comparison)
    check_season_via_api(
        "Elite 2",
        ELITE_2_SEASONS["2023-2024"],
        "2023-2024",
    )

    print("\n" + "=" * 80)
    print("  CONCLUSION")
    print("=" * 80)
    print()
    print("If Elite 2 shows 0 fixtures:")
    print("  → Season hasn't started yet or isn't scheduled in API")
    print("  → Website shows Betclic ELITE as placeholder")
    print("  → We should wait until Elite 2 season begins")
    print()
    print("If Elite 2 shows fixtures:")
    print("  → Fixtures exist but UUIDs aren't on website calendar")
    print("  → We can use those UUIDs for ingestion!")
    print()


if __name__ == "__main__":
    main()
