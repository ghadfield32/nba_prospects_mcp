#!/usr/bin/env python3
"""Test Elite 2 Data Availability via Atrium API

This script tests if Elite 2 games have PBP and shot chart data available
through the Atrium Sports API. Since the bulk `/fixtures` endpoint only
returns Betclic ELITE data, we need to:

1. Get Elite 2 game UUIDs (via web scraping or manual extraction)
2. Query `/fixture_detail` endpoint with those UUIDs
3. Check if PBP and shot chart data exist

Status: BLOCKED - Need Elite 2 game UUIDs first
Next Step: Create Playwright scraper for https://www.lnb.fr/elite-2/calendrier

Created: 2025-11-18
"""

from __future__ import annotations

import io
import json
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

# ==============================================================================
# CONFIG
# ==============================================================================

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURE_DETAIL_ENDPOINT = "/v1/embed/12/fixture_detail"

TIMEOUT = 15

# ==============================================================================
# TEST FUNCTIONS
# ==============================================================================


def test_fixture_data_availability(fixture_uuid: str) -> dict:
    """Test if a fixture has PBP and shot chart data

    Args:
        fixture_uuid: Game UUID to test

    Returns:
        Dict with test results
    """
    print(f"\n[TESTING] Fixture {fixture_uuid[:8]}...")

    results = {
        "fixture_id": fixture_uuid,
        "has_metadata": False,
        "has_pbp": False,
        "has_shots": False,
        "competition": "Unknown",
        "season": "Unknown",
        "error": None,
    }

    try:
        # Test fixture_detail for metadata
        url = f"{ATRIUM_API_BASE}{FIXTURE_DETAIL_ENDPOINT}"
        params = {"fixtureId": fixture_uuid}

        response = requests.get(url, params=params, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            banner = data.get("data", {}).get("banner", {})

            # Extract metadata
            competition = banner.get("competition", {})
            season = banner.get("season", {})

            results["has_metadata"] = True
            results["competition"] = competition.get("name", "Unknown")
            results["season"] = season.get("name", "Unknown")

            print("  [OK] Metadata found")
            print(f"  Competition: {results['competition']}")
            print(f"  Season: {results['season']}")

            # Check PBP data (in fixture_detail response or separate call)
            play_by_play = data.get("data", {}).get("playByPlay", {})
            if play_by_play and len(play_by_play) > 0:
                results["has_pbp"] = True
                print(f"  [OK] PBP data found ({len(play_by_play)} events)")
            else:
                print("  [WARN] No PBP data in response")

            # Check shot chart data
            shot_chart = data.get("data", {}).get("shotChart", {})
            if shot_chart and len(shot_chart) > 0:
                results["has_shots"] = True
                print(f"  [OK] Shot chart data found ({len(shot_chart)} shots)")
            else:
                print("  [WARN] No shot chart data in response")

        else:
            print(f"  [ERROR] HTTP {response.status_code}")
            results["error"] = f"HTTP {response.status_code}"

    except Exception as e:
        print(f"  [ERROR] {e}")
        results["error"] = str(e)

    return results


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    print("=" * 80)
    print("  ELITE 2 DATA AVAILABILITY TEST")
    print("=" * 80)
    print()

    # UPDATED 2025-11-18: Load Elite 2 UUIDs from scraper output
    uuid_file = Path("tools/lnb/uuid_mappings/elite_2_2024_2025_uuids.json")

    if not uuid_file.exists():
        print("[BLOCKED] No Elite 2 game UUIDs available for testing")
        print()
        print("Next steps:")
        print("  1. Run scraper: python tools/lnb/scrape_lnb_schedule_uuids.py --league elite_2")
        print("  2. Re-run this test")
        print()
        return

    # Load UUIDs from file
    print(f"[LOADING] UUIDs from {uuid_file.name}...")
    with open(uuid_file, encoding="utf-8") as f:
        uuid_data = json.load(f)

    elite2_test_uuids = uuid_data.get("uuids", [])
    print(f"[OK] Loaded {len(elite2_test_uuids)} UUIDs")
    print(f"     League: {uuid_data.get('league')}")
    print(f"     Season: {uuid_data.get('season')}")
    print(f"     Extracted: {uuid_data.get('extracted_at')}")
    print()

    if not elite2_test_uuids:
        print("[ERROR] UUID file exists but contains no UUIDs")
        return

    # Test a sample of UUIDs (not all 41, to avoid spamming API)
    sample_size = min(5, len(elite2_test_uuids))
    print(f"[TESTING] Sample of {sample_size} games (out of {len(elite2_test_uuids)} total)")
    print()

    elite2_test_uuids = elite2_test_uuids[:sample_size]

    # Run tests
    all_results = []
    for uuid in elite2_test_uuids:
        result = test_fixture_data_availability(uuid)
        all_results.append(result)

    # Summary
    print("\n" + "=" * 80)
    print("  TEST SUMMARY")
    print("=" * 80)
    print()

    successful_tests = [r for r in all_results if r["has_metadata"]]
    with_pbp = [r for r in all_results if r["has_pbp"]]
    with_shots = [r for r in all_results if r["has_shots"]]

    print(f"Total fixtures tested: {len(all_results)}")
    print(f"Metadata retrieved: {len(successful_tests)}/{len(all_results)}")
    print(f"PBP data available: {len(with_pbp)}/{len(all_results)}")
    print(f"Shot chart available: {len(with_shots)}/{len(all_results)}")
    print()

    if with_pbp and with_shots:
        print("✓ RESULT: Elite 2 games have PBP and shot chart data!")
        print("  Can proceed with ingestion pipeline")
    elif successful_tests and not (with_pbp or with_shots):
        print("✗ RESULT: Elite 2 metadata found but no PBP/shot data")
        print("  Elite 2 may not be supported by Atrium API")
    else:
        print("? RESULT: Inconclusive - need more test data")

    print()


if __name__ == "__main__":
    main()
