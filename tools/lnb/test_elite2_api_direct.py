#!/usr/bin/env python3
"""Test Elite 2 Discovery via Direct API Query

This script attempts to discover Elite 2 fixtures by querying the Atrium API
directly with known Elite 2 competition and season IDs from lnb_league_config.py.

Goal: Determine if Elite 2 fixtures can be discovered via API (bypassing web scraping)

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
    ELITE_2_SEASONS,
)

# ==============================================================================
# CONFIG
# ==============================================================================

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURES_ENDPOINT = "/v1/embed/12/fixtures"
FIXTURE_DETAIL_ENDPOINT = "/v1/embed/12/fixture_detail"

TIMEOUT = 15

# ==============================================================================
# TEST FUNCTIONS
# ==============================================================================


def test_fixtures_discovery(competition_id: str, season_id: str, league: str, season: str) -> dict:
    """Test if fixtures endpoint returns Elite 2 games

    Args:
        competition_id: Competition UUID to query
        season_id: Season UUID to query
        league: League name for logging (e.g., "elite_2")
        season: Season name for logging (e.g., "2024-2025")

    Returns:
        Dict with test results
    """
    print(f"\n[TEST 1] Fixtures Discovery: {league} {season}")
    print(f"  Competition ID: {competition_id[:16]}...")
    print(f"  Season ID: {season_id[:16]}...")

    results = {
        "league": league,
        "season": season,
        "competition_id": competition_id,
        "season_id": season_id,
        "fixtures_found": 0,
        "returned_competition_id": None,
        "returned_season_id": None,
        "sample_fixture_ids": [],
        "error": None,
    }

    try:
        url = f"{ATRIUM_API_BASE}{FIXTURES_ENDPOINT}"

        # Test with competitionId parameter
        params = {"competitionId": competition_id}
        response = requests.get(url, params=params, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()

            # Debug: Check response structure
            data_obj = data.get("data")
            if not isinstance(data_obj, dict):
                print(f"  [DEBUG] Unexpected data type: {type(data_obj)}")
                print(f"  [DEBUG] Data value: {str(data_obj)[:100]}")
                results["error"] = "Invalid response structure"
                return results

            # Check what competition/season was actually returned
            returned_comp_id = data_obj.get("competitionId")
            returned_season_id = data_obj.get("seasonId")

            results["returned_competition_id"] = returned_comp_id
            results["returned_season_id"] = returned_season_id

            # Get fixtures
            fixtures = data_obj.get("rounds", {})
            fixture_ids = []

            if isinstance(fixtures, dict):
                for round_data in fixtures.values():
                    if isinstance(round_data, dict):
                        for fixture in round_data.get("fixtures", []):
                            fixture_id = fixture.get("id")
                            if fixture_id:
                                fixture_ids.append(fixture_id)

            results["fixtures_found"] = len(fixture_ids)
            results["sample_fixture_ids"] = fixture_ids[:3]  # First 3 for inspection

            # Check if returned IDs match requested IDs
            id_mismatch = returned_comp_id != competition_id or returned_season_id != season_id

            if id_mismatch:
                print("  [WARN] API returned different competition/season!")
                print(f"    Requested Competition: {competition_id[:16]}...")
                print(
                    f"    Returned Competition:  {returned_comp_id[:16] if returned_comp_id else 'None'}..."
                )
                print(f"    Requested Season: {season_id[:16]}...")
                print(
                    f"    Returned Season:  {returned_season_id[:16] if returned_season_id else 'None'}..."
                )
            else:
                print("  [OK] Competition/Season IDs match!")

            print(f"  [RESULT] Found {len(fixture_ids)} fixtures")

            if fixture_ids:
                print("  Sample fixture IDs:")
                for fid in fixture_ids[:3]:
                    print(f"    - {fid[:16]}...")
        else:
            print(f"  [ERROR] HTTP {response.status_code}")
            results["error"] = f"HTTP {response.status_code}"

    except Exception as e:
        print(f"  [ERROR] {e}")
        results["error"] = str(e)

    return results


def test_fixture_detail(fixture_id: str) -> dict:
    """Test fixture_detail endpoint to verify league metadata

    Args:
        fixture_id: Fixture UUID to query

    Returns:
        Dict with metadata results
    """
    print(f"\n[TEST 2] Fixture Detail: {fixture_id[:16]}...")

    results = {
        "fixture_id": fixture_id,
        "competition_name": None,
        "competition_id": None,
        "season_name": None,
        "has_pbp": False,
        "has_shots": False,
        "error": None,
    }

    try:
        url = f"{ATRIUM_API_BASE}{FIXTURE_DETAIL_ENDPOINT}"
        params = {"fixtureId": fixture_id}

        response = requests.get(url, params=params, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            banner = data.get("data", {}).get("banner", {})

            # Extract metadata
            competition = banner.get("competition", {})
            season = banner.get("season", {})

            results["competition_name"] = competition.get("name", "Unknown")
            results["competition_id"] = competition.get("id", "Unknown")
            results["season_name"] = season.get("name", "Unknown")

            print(f"  Competition: {results['competition_name']}")
            print(
                f"  Competition ID: {results['competition_id'][:16] if results['competition_id'] != 'Unknown' else 'Unknown'}..."
            )
            print(f"  Season: {results['season_name']}")

            # Check PBP and shot data
            play_by_play = data.get("data", {}).get("playByPlay", {})
            shot_chart = data.get("data", {}).get("shotChart", {})

            results["has_pbp"] = bool(play_by_play and len(play_by_play) > 0)
            results["has_shots"] = bool(shot_chart and len(shot_chart) > 0)

            print(f"  PBP: {'✓ Yes' if results['has_pbp'] else '✗ No'}")
            print(f"  Shots: {'✓ Yes' if results['has_shots'] else '✗ No'}")

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
    print("  ELITE 2 API DIRECT QUERY TEST")
    print("=" * 80)
    print()
    print("Goal: Determine if Elite 2 fixtures can be discovered via Atrium API")
    print("Method: Query /fixtures endpoint with Elite 2 competition IDs")
    print()

    # Test all Elite 2 seasons
    all_results = []

    for season, metadata in ELITE_2_SEASONS.items():
        competition_id = metadata["competition_id"]
        season_id = metadata["season_id"]

        result = test_fixtures_discovery(
            competition_id=competition_id,
            season_id=season_id,
            league="elite_2",
            season=season,
        )
        all_results.append(result)

        # If fixtures found, test one to verify metadata
        if result["sample_fixture_ids"]:
            sample_id = result["sample_fixture_ids"][0]
            detail_result = test_fixture_detail(sample_id)
            result["sample_detail"] = detail_result

    # Summary
    print("\n" + "=" * 80)
    print("  TEST SUMMARY")
    print("=" * 80)
    print()

    for result in all_results:
        print(f"{result['league'].upper()} {result['season']}:")
        print(f"  Fixtures discovered: {result['fixtures_found']}")

        if result["returned_competition_id"] != result["competition_id"]:
            print("  ⚠️  WARNING: API returned different competition ID!")
            print("     (This means API ignored our Elite 2 request)")

        if "sample_detail" in result:
            detail = result["sample_detail"]
            print("  Sample fixture metadata:")
            print(f"    - Competition: {detail['competition_name']}")
            print(f"    - Has PBP: {detail['has_pbp']}")
            print(f"    - Has Shots: {detail['has_shots']}")

        print()

    # Overall conclusion
    elite2_fixtures = sum(r["fixtures_found"] for r in all_results)
    id_mismatches = sum(
        1 for r in all_results if r["returned_competition_id"] != r["competition_id"]
    )

    print("=" * 80)
    print("  CONCLUSION")
    print("=" * 80)
    print()

    if elite2_fixtures > 0 and id_mismatches == 0:
        print("✓ SUCCESS: Elite 2 fixtures can be discovered via API!")
        print(f"  Found {elite2_fixtures} total fixtures across all seasons")
        print("  Proceed with API-based ingestion")
    elif elite2_fixtures > 0 and id_mismatches > 0:
        print("✗ PROBLEM: API returns fixtures but ignores Elite 2 competition ID")
        print(f"  {id_mismatches}/{len(all_results)} queries returned wrong competition")
        print("  API may only support Betclic ELITE queries")
    else:
        print("✗ PROBLEM: No Elite 2 fixtures discovered via API")
        print("  Elite 2 may require web scraping approach")

    print()


if __name__ == "__main__":
    main()
