#!/usr/bin/env python3
"""Debug script to investigate ALL LNB leagues and divisions

This script systematically queries LNB APIs to discover:
1. All competitions returned by calendar API
2. All division IDs and external IDs
3. League naming changes (Pro A/B -> Betclic Elite/Elite 2)
4. Youth leagues (Espoirs Elite, Espoirs Elite 2)
5. Any other competitions/divisions

Purpose: Root cause analysis for league discovery issues
Created: 2025-11-18
"""

from __future__ import annotations

import io
import sys
from collections import defaultdict

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print("=" * 80)
print("LNB LEAGUE STRUCTURE DEBUG INVESTIGATION")
print("=" * 80)
print()

# ==============================================================================
# TEST 1: Calendar API - What competitions are returned?
# ==============================================================================

print("[TEST 1] Querying LNB Calendar API...")
print("-" * 80)

try:
    url = "https://api-prod.lnb.fr/match/getCalenderByDivision"
    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        data = response.json()
        matches = data.get("data", [])

        print(f"✓ HTTP 200 - Retrieved {len(matches)} total matches")
        print()

        # Extract all unique competitions
        competitions = defaultdict(
            lambda: {"count": 0, "division_ids": set(), "sample_match": None}
        )

        for match in matches:
            comp_abbrev = match.get("competition_abbrev", "UNKNOWN")
            comp_name = match.get("competition_name", "UNKNOWN")
            division_id = match.get("division_external_id")
            division_name = match.get("division_name", "UNKNOWN")

            key = f"{comp_abbrev}|{comp_name}"
            competitions[key]["count"] += 1
            competitions[key]["division_ids"].add(division_id)

            if not competitions[key]["sample_match"]:
                competitions[key]["sample_match"] = {
                    "match_id": match.get("match_id", "")[:8] + "...",
                    "match_date": match.get("match_date"),
                    "home_team": match.get("home_team_name"),
                    "away_team": match.get("away_team_name"),
                    "division_name": division_name,
                }

        print(f"COMPETITIONS FOUND: {len(competitions)}")
        print("=" * 80)

        for idx, (comp_key, comp_data) in enumerate(sorted(competitions.items()), 1):
            comp_abbrev, comp_name = comp_key.split("|")

            print(f"\n[{idx}] Competition: {comp_abbrev}")
            print(f"    Full Name: {comp_name}")
            print(f"    Matches: {comp_data['count']}")
            print(f"    Division IDs: {sorted(comp_data['division_ids'])}")

            sample = comp_data["sample_match"]
            if sample:
                print("    Sample Match:")
                print(f"      - UUID: {sample['match_id']}")
                print(f"      - Date: {sample['match_date']}")
                print(f"      - Teams: {sample['home_team']} vs {sample['away_team']}")
                print(f"      - Division Name: {sample['division_name']}")
    else:
        print(f"✗ HTTP {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"✗ Error: {e}")

print()
print("=" * 80)

# ==============================================================================
# TEST 2: Sample match detail - Extract full competition metadata
# ==============================================================================

print("[TEST 2] Extracting metadata from sample matches...")
print("-" * 80)

if response.status_code == 200 and matches:
    # Get first match UUID
    for match in matches[:5]:  # Check first 5 matches
        match_uuid = match.get("match_id")
        comp_abbrev = match.get("competition_abbrev")

        if match_uuid:
            print(f"\nFetching details for: {comp_abbrev} match {match_uuid[:8]}...")

            try:
                detail_url = f"https://api-prod.lnb.fr/match/getMatchDetails/{match_uuid}"
                detail_resp = requests.get(detail_url, timeout=10)

                if detail_resp.status_code == 200:
                    detail_data = detail_resp.json()

                    # Extract competition metadata
                    match_data = detail_data.get("data", {})
                    competition = match_data.get("competition", {})

                    print(f"  Competition ID: {competition.get('id', 'N/A')}")
                    print(f"  Competition Name: {competition.get('name', 'N/A')}")
                    print(f"  Competition Abbrev: {competition.get('abbrev', 'N/A')}")
                    print(f"  Division: {match_data.get('division', {}).get('name', 'N/A')}")
                    print(f"  Division ID: {match_data.get('division', {}).get('id', 'N/A')}")

                else:
                    print(f"  ✗ HTTP {detail_resp.status_code}")

            except Exception as e:
                print(f"  ✗ Error: {e}")

print()
print("=" * 80)

# ==============================================================================
# TEST 3: Atrium API - Check fixture detail for competition metadata
# ==============================================================================

print("[TEST 3] Checking Atrium API for competition metadata...")
print("-" * 80)

if response.status_code == 200 and matches:
    # Test with first available match
    for match in matches[:3]:
        match_uuid = match.get("match_id")
        comp_abbrev = match.get("competition_abbrev")

        if match_uuid:
            print(f"\nAtrium API - {comp_abbrev} match {match_uuid[:8]}...")

            try:
                atrium_url = (
                    "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail"
                )
                params = {"fixtureId": match_uuid}
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Referer": "https://lnb.fr/",
                }

                atrium_resp = requests.get(atrium_url, params=params, headers=headers, timeout=10)

                if atrium_resp.status_code == 200:
                    atrium_data = atrium_resp.json()
                    banner = atrium_data.get("data", {}).get("banner", {})
                    competition = banner.get("competition", {})
                    season = banner.get("season", {})

                    print("  ✓ Atrium API accessible")
                    print(f"  Competition ID: {competition.get('id', 'N/A')}")
                    print(f"  Competition Name: {competition.get('name', 'N/A')}")
                    print(f"  Season ID: {season.get('id', 'N/A')}")
                    print(f"  Season Name: {season.get('name', 'N/A')}")

                else:
                    print(f"  ✗ Atrium HTTP {atrium_resp.status_code}")

            except Exception as e:
                print(f"  ✗ Error: {e}")

print()
print("=" * 80)

# ==============================================================================
# TEST 4: Try to discover fixtures endpoint with different parameters
# ==============================================================================

print("[TEST 4] Testing Atrium fixtures endpoint discovery...")
print("-" * 80)

# Known competition IDs for Pro A (now Betclic Elite)
known_competition_ids = [
    "a2262b45-2fab-11ef-8eb7-99149ebb5652",  # 2024-2025 Betclic Elite
    "2cd1ec93-19af-11ee-afb2-8125e5386866",  # 2023-2024 Betclic Elite
]

for comp_id in known_competition_ids:
    print(f"\nTrying competition ID: {comp_id[:8]}...")

    try:
        fixtures_url = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixtures"
        params = {"competitionId": comp_id}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://lnb.fr/",
        }

        fixtures_resp = requests.get(fixtures_url, params=params, headers=headers, timeout=10)

        if fixtures_resp.status_code == 200:
            fixtures_data = fixtures_resp.json()
            fixtures = fixtures_data.get("data", [])

            print(f"  ✓ Found {len(fixtures)} fixtures")

            # Check for different divisions in fixtures
            if fixtures:
                divisions = set()
                for fixture in fixtures:
                    div_name = fixture.get("divisionName", "UNKNOWN")
                    divisions.add(div_name)

                print(f"  Divisions found: {divisions}")

        else:
            print(f"  ✗ HTTP {fixtures_resp.status_code}")

    except Exception as e:
        print(f"  ✗ Error: {e}")

print()
print("=" * 80)
print("DEBUG INVESTIGATION COMPLETE")
print("=" * 80)
print()
print("NEXT STEPS:")
print("1. Review output above to identify all available leagues")
print("2. Check if naming changed (Pro A/B -> Betclic Elite/Elite 2)")
print("3. Look for youth leagues (Espoirs Elite, Espoirs Elite 2)")
print("4. Extract competition IDs for each league")
print("5. Update SEASON_METADATA with all discovered leagues")
