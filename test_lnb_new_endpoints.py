#!/usr/bin/env python3
"""Comprehensive test script for 4 new LNB API endpoints.

This script tests the newly integrated endpoints:
1. get_calendar_by_division() - GET /match/getCalenderByDivision
2. get_competitions_by_player() - POST /competition/getCompetitionByPlayer
3. get_player_performance() - POST /altrstats/getPerformancePersonV2
4. get_standing() - POST /altrstats/getStanding

Prerequisites:
- lnb_headers.json must contain complete headers including:
  - accept-encoding: gzip, deflate, br, zstd
  - cache-control: no-cache
  - pragma: no-cache
  - content-type: application/json
  - All sec-* headers from DevTools
  - User-Agent matching Chrome

Usage:
    python test_lnb_new_endpoints.py

Expected Output (if headers work):
    ✅ Each endpoint returns JSON data (200 OK)

Expected Output (if still 403):
    ❌ Endpoints return Access denied
    → Need to test cURL on host machine first
    → Add cookies if needed
    → Check if running in container vs host
"""

import json
import sys
from typing import Any, Dict

# Test with direct requests first to isolate issues
try:
    import requests
    USE_CLIENT = False
    print("Testing with requests library (direct HTTP)")
except ImportError:
    print("requests not available, trying LNBClient...")
    USE_CLIENT = True

if USE_CLIENT:
    try:
        from src.cbb_data.fetchers.lnb_api import LNBClient
        print("✅ LNBClient imported successfully")
    except ImportError as e:
        print(f"❌ Cannot import LNBClient: {e}")
        print("Install dependencies: pip install requests")
        sys.exit(1)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(endpoint: str, success: bool, details: str = "") -> None:
    """Print test result with colored output."""
    status = "✅ SUCCESS" if success else "❌ FAILED"
    print(f"\n{status}: {endpoint}")
    if details:
        print(f"   {details}")


def test_with_requests() -> None:
    """Test endpoints using requests library directly."""
    print_section("Testing with requests library (direct)")

    # Load headers from config
    try:
        with open("tools/lnb/lnb_headers.json", "r") as f:
            headers = json.load(f)
        print(f"✅ Loaded {len(headers)} headers from lnb_headers.json")
    except FileNotFoundError:
        print("❌ lnb_headers.json not found in tools/lnb/")
        print("   Create it with headers from DevTools (see DEVTOOLS_CAPTURE_GUIDE.md)")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in lnb_headers.json: {e}")
        return

    base_url = "https://api-prod.lnb.fr"

    # Test 1: GET /match/getCalenderByDivision
    print_section("Test 1: get_calendar_by_division")
    try:
        resp = requests.get(
            f"{base_url}/match/getCalenderByDivision",
            params={"division_external_id": 0, "year": 2025},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print_result(
                "getCalenderByDivision",
                True,
                f"Got {len(data) if isinstance(data, list) else 'N/A'} games",
            )
            print(f"   Sample: {json.dumps(data[0] if isinstance(data, list) and data else data, indent=2)[:200]}...")
        else:
            print_result(
                "getCalenderByDivision",
                False,
                f"Status {resp.status_code}: {resp.text[:100]}",
            )
    except Exception as e:
        print_result("getCalenderByDivision", False, f"Exception: {e}")

    # Test 2: POST /competition/getCompetitionByPlayer
    print_section("Test 2: get_competitions_by_player")
    try:
        resp = requests.post(
            f"{base_url}/competition/getCompetitionByPlayer",
            json={"year": 2025, "person_external_id": 3586},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print_result(
                "getCompetitionByPlayer",
                True,
                f"Got {len(data) if isinstance(data, list) else 'N/A'} competitions",
            )
            print(f"   Sample: {json.dumps(data[0] if isinstance(data, list) and data else data, indent=2)[:200]}...")
        else:
            print_result(
                "getCompetitionByPlayer",
                False,
                f"Status {resp.status_code}: {resp.text[:100]}",
            )
    except Exception as e:
        print_result("getCompetitionByPlayer", False, f"Exception: {e}")

    # Test 3: POST /altrstats/getPerformancePersonV2
    print_section("Test 3: get_player_performance")
    try:
        resp = requests.post(
            f"{base_url}/altrstats/getPerformancePersonV2",
            json={"competitionExternalId": 302, "personExternalId": 3586},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print_result(
                "getPerformancePersonV2",
                True,
                f"Got player stats: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}",
            )
            print(f"   Sample: {json.dumps(data, indent=2)[:300]}...")
        else:
            print_result(
                "getPerformancePersonV2",
                False,
                f"Status {resp.status_code}: {resp.text[:100]}",
            )
    except Exception as e:
        print_result("getPerformancePersonV2", False, f"Exception: {e}")

    # Test 4: POST /altrstats/getStanding
    print_section("Test 4: get_standing")
    try:
        resp = requests.post(
            f"{base_url}/altrstats/getStanding",
            json={"competitionExternalId": 302},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print_result(
                "getStanding",
                True,
                f"Got standings: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}",
            )
            print(f"   Sample: {json.dumps(data, indent=2)[:300]}...")
        else:
            print_result(
                "getStanding",
                False,
                f"Status {resp.status_code}: {resp.text[:100]}",
            )
    except Exception as e:
        print_result("getStanding", False, f"Exception: {e}")


def test_with_client() -> None:
    """Test endpoints using LNBClient."""
    print_section("Testing with LNBClient")

    try:
        client = LNBClient()
        print("✅ LNBClient initialized")
    except Exception as e:
        print(f"❌ Failed to initialize LNBClient: {e}")
        return

    # Test 1: get_calendar_by_division
    print_section("Test 1: get_calendar_by_division")
    try:
        games = client.get_calendar_by_division(division_external_id=0, year=2025)
        print_result("get_calendar_by_division", True, f"Got {len(games)} games")
        if games:
            print(f"   Sample game: {json.dumps(games[0], indent=2)[:200]}...")
    except Exception as e:
        print_result("get_calendar_by_division", False, f"Exception: {e}")

    # Test 2: get_competitions_by_player
    print_section("Test 2: get_competitions_by_player")
    try:
        comps = client.get_competitions_by_player(year=2025, person_external_id=3586)
        print_result("get_competitions_by_player", True, f"Got {len(comps)} competitions")
        if comps:
            print(f"   Sample comp: {json.dumps(comps[0], indent=2)[:200]}...")
    except Exception as e:
        print_result("get_competitions_by_player", False, f"Exception: {e}")

    # Test 3: get_player_performance
    print_section("Test 3: get_player_performance")
    try:
        perf = client.get_player_performance(
            competition_external_id=302, person_external_id=3586
        )
        print_result(
            "get_player_performance",
            True,
            f"Got player stats: {list(perf.keys())[:5] if isinstance(perf, dict) else 'N/A'}",
        )
        print(f"   Sample: {json.dumps(perf, indent=2)[:300]}...")
    except Exception as e:
        print_result("get_player_performance", False, f"Exception: {e}")

    # Test 4: get_standing
    print_section("Test 4: get_standing")
    try:
        standing = client.get_standing(competition_external_id=302)
        print_result(
            "get_standing",
            True,
            f"Got standings: {list(standing.keys())[:5] if isinstance(standing, dict) else 'N/A'}",
        )
        print(f"   Sample: {json.dumps(standing, indent=2)[:300]}...")
    except Exception as e:
        print_result("get_standing", False, f"Exception: {e}")


def main() -> None:
    """Run all tests."""
    print_section("LNB API New Endpoints Test Suite")
    print("Testing 4 newly integrated endpoints")
    print("Date: 2025-11-14")

    if USE_CLIENT:
        test_with_client()
    else:
        test_with_requests()

    print_section("Test Summary")
    print("\nIf all tests passed (✅):")
    print("  → Headers are working! Ready for parser integration")
    print("\nIf tests failed with 403 Forbidden (❌):")
    print("  → Step 1: Test cURL on host machine (not in container)")
    print("  → Step 2: Verify lnb_headers.json has all headers from working cURL")
    print("  → Step 3: Check if cookies are needed (see DEVTOOLS_CAPTURE_GUIDE.md)")
    print("  → Step 4: Try running Python on host (not in Docker)")
    print("\nNext steps:")
    print("  1. Create lnb_parsers.py (JSON → DataFrame)")
    print("  2. Update lnb.py (high-level fetchers)")
    print("  3. Add to dataset registry")
    print("  4. Add health_check_lnb()")


if __name__ == "__main__":
    main()
