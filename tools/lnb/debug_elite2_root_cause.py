#!/usr/bin/env python3
"""Deep Root Cause Analysis: Elite 2 Data Availability

This script performs systematic debugging to understand WHY Elite 2 data is not available.
We don't assume anything - we trace every step and log everything we find.

Investigation Areas:
1. HTML Structure Analysis: What's actually on the Elite 2 calendar page?
2. Network Request Analysis: What API calls does the page make?
3. JavaScript Variable Inspection: What data is embedded in the page?
4. API Response Deep Dive: What does the API actually return?
5. Competition ID Validation: Are our Elite 2 IDs even valid?

Created: 2025-11-18
"""

from __future__ import annotations

import io
import json
import re
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

from src.cbb_data.fetchers.browser_scraper import BrowserScraper
from src.cbb_data.fetchers.lnb_league_config import (
    BETCLIC_ELITE_SEASONS,
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
# INVESTIGATION 1: HTML STRUCTURE ANALYSIS
# ==============================================================================


def investigate_html_structure():
    """Analyze what's actually in the Elite 2 HTML"""
    print("=" * 80)
    print("  INVESTIGATION 1: HTML STRUCTURE ANALYSIS")
    print("=" * 80)
    print()
    print("Goal: Understand what data is embedded in the Elite 2 calendar page")
    print()

    urls_to_check = {
        "Betclic ELITE": "https://www.lnb.fr/pro-a/calendrier",
        "Elite 2": "https://www.lnb.fr/elite-2/calendrier",
    }

    for league, url in urls_to_check.items():
        print(f"\n[ANALYZING] {league}")
        print(f"  URL: {url}")

        try:
            with BrowserScraper(headless=True, timeout=30000) as scraper:
                html = scraper.get_rendered_html(url=url, wait_time=5.0)

                # 1. Look for competition IDs in HTML
                print("\n  [1] Searching for competition IDs in HTML...")
                comp_id_pattern = re.compile(
                    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                    re.IGNORECASE,
                )
                all_uuids = comp_id_pattern.findall(html)
                unique_uuids = list(set(all_uuids))
                print(f"      Found {len(unique_uuids)} unique UUIDs in page")

                # Check if our known competition IDs appear in the HTML
                if league == "Elite 2":
                    elite2_comp_id = ELITE_2_SEASONS["2024-2025"]["competition_id"]
                    elite2_season_id = ELITE_2_SEASONS["2024-2025"]["season_id"]

                    if elite2_comp_id in unique_uuids:
                        print("      ✓ Elite 2 competition ID FOUND in HTML!")
                    else:
                        print("      ✗ Elite 2 competition ID NOT in HTML")

                    if elite2_season_id in unique_uuids:
                        print("      ✓ Elite 2 season ID FOUND in HTML!")
                    else:
                        print("      ✗ Elite 2 season ID NOT in HTML")
                else:
                    betclic_comp_id = BETCLIC_ELITE_SEASONS["2024-2025"]["competition_id"]

                    if betclic_comp_id in unique_uuids:
                        print("      ✓ Betclic ELITE competition ID FOUND in HTML!")
                    else:
                        print("      ✗ Betclic ELITE competition ID NOT in HTML")

                # 2. Look for API endpoint calls in HTML/JavaScript
                print("\n  [2] Searching for API endpoint references...")
                api_patterns = [
                    r"eapi\.web\.prod\.cloud\.atriumsports\.com",
                    r"/v1/embed/\d+/fixtures",
                    r"/v1/embed/\d+/fixture_detail",
                    r"competitionId[\"']?\s*[:=]\s*[\"']?([0-9a-f-]+)",
                    r"seasonId[\"']?\s*[:=]\s*[\"']?([0-9a-f-]+)",
                ]

                for pattern_str in api_patterns:
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                    matches = pattern.findall(html)
                    if matches:
                        print(
                            f"      Found pattern '{pattern_str[:40]}...': {len(matches)} matches"
                        )
                        if "competitionId" in pattern_str or "seasonId" in pattern_str:
                            # Show first few matches
                            for match in matches[:3]:
                                print(f"        → {match}")

                # 3. Look for league/competition name mentions
                print("\n  [3] Searching for league name references...")
                league_patterns = {
                    "Betclic ELITE": r"Betclic\s+[EÉ]LITE",
                    "ELITE 2": r"[EÉ]LITE\s+2",
                    "Pro A": r"Pro\s+A",
                    "Pro B": r"Pro\s+B",
                }

                for name, pattern_str in league_patterns.items():
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                    matches = pattern.findall(html)
                    if matches:
                        print(f"      Found '{name}': {len(matches)} occurrences")

                # 4. Check for season selector / filter elements
                print("\n  [4] Searching for season/filter UI elements...")
                filter_patterns = [
                    r'class="[^"]*filter[^"]*"',
                    r'class="[^"]*season[^"]*"',
                    r'class="[^"]*dropdown[^"]*"',
                    r"<select[^>]*>",
                ]

                for pattern_str in filter_patterns:
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                    matches = pattern.findall(html)
                    if matches:
                        print(f"      Found '{pattern_str[:30]}...': {len(matches)} elements")

        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 80)


# ==============================================================================
# INVESTIGATION 2: API RESPONSE DEEP DIVE
# ==============================================================================


def investigate_api_responses():
    """Deep dive into what the API actually returns"""
    print("=" * 80)
    print("  INVESTIGATION 2: API RESPONSE DEEP DIVE")
    print("=" * 80)
    print()
    print("Goal: Understand the complete structure of API responses")
    print()

    # Test 1: Betclic ELITE (known to work)
    print("\n[TEST 1] Betclic ELITE /fixtures endpoint (BASELINE)")
    betclic_comp_id = BETCLIC_ELITE_SEASONS["2024-2025"]["competition_id"]
    betclic_season_id = BETCLIC_ELITE_SEASONS["2024-2025"]["season_id"]

    url = f"{ATRIUM_API_BASE}{FIXTURES_ENDPOINT}"
    params = {"competitionId": betclic_comp_id}

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {response.status_code} OK")
            print(f"  Response keys: {list(data.keys())}")

            data_obj = data.get("data", {})
            print(f"  data.keys(): {list(data_obj.keys())}")
            print(f"  data.competitionId: {data_obj.get('competitionId', 'N/A')}")
            print(f"  data.seasonId: {data_obj.get('seasonId', 'N/A')}")
            print(f"  data.rounds: {len(data_obj.get('rounds', {}))} rounds")

            # Check if there's any metadata about available competitions
            if "seasons" in data_obj:
                print("  data.seasons: FOUND (contains competition metadata)")
                seasons_obj = data_obj["seasons"]
                if isinstance(seasons_obj, dict):
                    print(f"    seasons.keys(): {list(seasons_obj.keys())}")
        else:
            print(f"  Status: {response.status_code} ERROR")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 2: Elite 2 (known to fail)
    print("\n\n[TEST 2] Elite 2 /fixtures endpoint (PROBLEM CASE)")
    elite2_comp_id = ELITE_2_SEASONS["2024-2025"]["competition_id"]
    elite2_season_id = ELITE_2_SEASONS["2024-2025"]["season_id"]

    params = {"competitionId": elite2_comp_id}

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {response.status_code} OK")
            print(f"  Response keys: {list(data.keys())}")

            data_obj = data.get("data", {})
            print(f"  data.keys(): {list(data_obj.keys())}")
            print(f"  data.competitionId: {data_obj.get('competitionId', 'N/A')}")
            print(f"  data.seasonId: {data_obj.get('seasonId', 'N/A')}")
            print(f"  data.rounds: {len(data_obj.get('rounds', {}))} rounds")

            # CRITICAL: Check what competition was actually returned
            returned_comp = data_obj.get("competitionId")
            returned_season = data_obj.get("seasonId")

            print("\n  [COMPARISON]")
            print(f"    Requested comp:  {elite2_comp_id}")
            print(f"    Returned comp:   {returned_comp}")
            print(f"    MATCH: {returned_comp == elite2_comp_id}")
            print(f"    Requested season: {elite2_season_id}")
            print(f"    Returned season:  {returned_season}")
            print(f"    MATCH: {returned_season == elite2_season_id}")

            # Check if returned IDs match Betclic ELITE
            if returned_comp == betclic_comp_id:
                print("\n  ⚠️  CRITICAL: API returned Betclic ELITE competition ID!")
            if returned_season == betclic_season_id:
                print("  ⚠️  CRITICAL: API returned Betclic ELITE season ID!")
        else:
            print(f"  Status: {response.status_code} ERROR")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 3: Try with BOTH competitionId AND seasonId
    print("\n\n[TEST 3] Elite 2 with BOTH competitionId AND seasonId parameters")
    params = {
        "competitionId": elite2_comp_id,
        "seasonId": elite2_season_id,
    }

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            data_obj = data.get("data", {})

            returned_comp = data_obj.get("competitionId")
            returned_season = data_obj.get("seasonId")

            print(f"  Returned comp:   {returned_comp}")
            print(f"  Returned season: {returned_season}")
            print(f"  Competition MATCH: {returned_comp == elite2_comp_id}")
            print(f"  Season MATCH: {returned_season == elite2_season_id}")
            print(f"  Rounds: {len(data_obj.get('rounds', {}))} rounds")
        else:
            print(f"  Status: {response.status_code} ERROR")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Test 4: Try without ANY parameters (default behavior)
    print("\n\n[TEST 4] /fixtures endpoint with NO parameters (default)")
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            data_obj = data.get("data", {})

            print(f"  Status: {response.status_code} OK")
            print(f"  Returned comp:   {data_obj.get('competitionId', 'N/A')}")
            print(f"  Returned season: {data_obj.get('seasonId', 'N/A')}")
            print(f"  Rounds: {len(data_obj.get('rounds', {}))} rounds")
            print(
                f"\n  → Default competition appears to be: {data_obj.get('competitionId', 'N/A')}"
            )
        else:
            print(f"  Status: {response.status_code} ERROR")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 80)


# ==============================================================================
# INVESTIGATION 3: FIXTURE DETAIL VALIDATION
# ==============================================================================


def investigate_fixture_detail():
    """Validate that scraped UUIDs are truly Betclic ELITE games"""
    print("=" * 80)
    print("  INVESTIGATION 3: FIXTURE DETAIL VALIDATION")
    print("=" * 80)
    print()
    print("Goal: Confirm scraped UUIDs are Betclic ELITE (not Elite 2)")
    print()

    # Load scraped Elite 2 UUIDs
    uuid_file = Path("tools/lnb/uuid_mappings/elite_2_2024_2025_uuids.json")

    if not uuid_file.exists():
        print("[SKIPPED] No UUID file found")
        return

    with open(uuid_file, encoding="utf-8") as f:
        uuid_data = json.load(f)

    uuids_to_test = uuid_data.get("uuids", [])[:3]  # Test first 3

    print(f"Testing {len(uuids_to_test)} UUIDs scraped from Elite 2 page...\n")

    betclic_comp_id = BETCLIC_ELITE_SEASONS["2024-2025"]["competition_id"]
    elite2_comp_id = ELITE_2_SEASONS["2024-2025"]["competition_id"]

    for i, uuid in enumerate(uuids_to_test, 1):
        print(f"[UUID {i}] {uuid}")

        url = f"{ATRIUM_API_BASE}{FIXTURE_DETAIL_ENDPOINT}"
        params = {"fixtureId": uuid}

        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                banner = data.get("data", {}).get("banner", {})

                competition = banner.get("competition", {})
                season = banner.get("season", {})
                home_team = banner.get("home", {})
                away_team = banner.get("away", {})

                comp_id = competition.get("id")
                comp_name = competition.get("name")
                season_name = season.get("name")

                print(f"  Competition: {comp_name}")
                print(f"  Competition ID: {comp_id}")
                print(f"  Season: {season_name}")
                print(
                    f"  Matchup: {home_team.get('name', 'N/A')} vs {away_team.get('name', 'N/A')}"
                )

                # CRITICAL CHECK
                if comp_id == betclic_comp_id:
                    print("  ✗ CONFIRMED: This is a Betclic ELITE game (not Elite 2)")
                elif comp_id == elite2_comp_id:
                    print("  ✓ SUCCESS: This is an Elite 2 game!")
                else:
                    print("  ? UNKNOWN: Competition ID doesn't match either league")
                    print(f"    Betclic ELITE ID: {betclic_comp_id}")
                    print(f"    Elite 2 ID: {elite2_comp_id}")
                    print(f"    Actual ID: {comp_id}")

                print()
            else:
                print(f"  ERROR: HTTP {response.status_code}\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")

    print("=" * 80)


# ==============================================================================
# INVESTIGATION 4: COMPETITION ID VALIDATION
# ==============================================================================


def investigate_competition_ids():
    """Verify our Elite 2 competition IDs are actually valid"""
    print("=" * 80)
    print("  INVESTIGATION 4: COMPETITION ID VALIDATION")
    print("=" * 80)
    print()
    print("Goal: Verify Elite 2 competition IDs exist in Atrium API")
    print()

    # Our known competition IDs
    test_cases = {
        "Betclic ELITE 2024-2025": BETCLIC_ELITE_SEASONS["2024-2025"]["competition_id"],
        "Elite 2 2024-2025": ELITE_2_SEASONS["2024-2025"]["competition_id"],
        "Elite 2 2023-2024": ELITE_2_SEASONS["2023-2024"]["competition_id"],
        "Elite 2 2022-2023": ELITE_2_SEASONS["2022-2023"]["competition_id"],
    }

    print("Testing if each competition ID returns valid data...\n")

    for league_season, comp_id in test_cases.items():
        print(f"[{league_season}]")
        print(f"  Competition ID: {comp_id}")

        url = f"{ATRIUM_API_BASE}{FIXTURES_ENDPOINT}"
        params = {"competitionId": comp_id}

        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            print(f"  HTTP Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                data_obj = data.get("data", {})

                returned_comp = data_obj.get("competitionId")
                returned_season = data_obj.get("seasonId")
                rounds_count = len(data_obj.get("rounds", {}))

                print(f"  Returned Competition: {returned_comp}")
                print(f"  Returned Season: {returned_season}")
                print(f"  Fixtures Found: {rounds_count} rounds")

                # Check if IDs match
                if returned_comp == comp_id:
                    print("  ✓ Competition ID accepted by API")
                else:
                    print("  ✗ Competition ID NOT accepted (returned different ID)")

            elif response.status_code == 404:
                print("  ✗ Competition ID not found (404)")
            else:
                print("  ? Unexpected status code")

            print()
        except Exception as e:
            print(f"  ERROR: {e}\n")

    print("=" * 80)


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    print("\n")
    print("█" * 80)
    print("  ELITE 2 ROOT CAUSE ANALYSIS - DEEP DEBUGGING")
    print("█" * 80)
    print()
    print("This investigation will:")
    print("  1. Analyze HTML structure of Elite 2 calendar page")
    print("  2. Deep dive into API response structures")
    print("  3. Validate scraped UUID league assignments")
    print("  4. Test if Elite 2 competition IDs are valid")
    print()
    print("Duration: ~2-3 minutes")
    print()

    input("Press ENTER to begin investigation...")
    print()

    # Run all investigations
    investigate_html_structure()
    print("\n")

    investigate_api_responses()
    print("\n")

    investigate_fixture_detail()
    print("\n")

    investigate_competition_ids()
    print("\n")

    print("█" * 80)
    print("  INVESTIGATION COMPLETE")
    print("█" * 80)
    print()
    print("Review the output above to understand:")
    print("  - What data is actually on the Elite 2 calendar page")
    print("  - How the API responds to Elite 2 competition IDs")
    print("  - Whether scraped UUIDs are truly Betclic ELITE games")
    print("  - If Elite 2 competition IDs are recognized by the API")
    print()


if __name__ == "__main__":
    main()
