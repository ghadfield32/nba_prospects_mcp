#!/usr/bin/env python3
"""Test newly discovered working LNB API endpoints

Tests the working endpoints found during exploration to see what data they return.
Focus: Finding play-by-play and shot chart data.

Usage:
    uv run python tools/lnb/test_working_endpoints.py
"""

import io
import json
import sys
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

print("=" * 80)
print("  Testing Working LNB API Endpoints")
print("  Searching for: Play-by-Play & Shot Chart Data")
print("=" * 80)
print()

# Create output directory
output_dir = Path(__file__).parent / "api_responses"
output_dir.mkdir(exist_ok=True)

BASE_URL = "https://api-prod.lnb.fr"

# Test 1: getLiveMatch - Check for play-by-play in live games
print("[TEST 1] Testing /match/getLiveMatch...")
print("-" * 80)

try:
    response = requests.get(f"{BASE_URL}/match/getLiveMatch", timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        # Save response
        with open(output_dir / "getLiveMatch.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[SAVED] getLiveMatch.json ({len(json.dumps(data))} chars)")

        # Analyze structure
        if isinstance(data, list):
            print(f"  Response type: List with {len(data)} items")
            if data:
                print(f"  First item keys: {list(data[0].keys())[:10]}")
        elif isinstance(data, dict):
            print("  Response type: Dict")
            print(f"  Top-level keys: {list(data.keys())}")

            # Look for play-by-play indicators
            data_str = json.dumps(data).lower()
            pbp_indicators = ["play", "event", "action", "quarter", "period", "timeline"]
            found = [ind for ind in pbp_indicators if ind in data_str]
            if found:
                print(f"  [FOUND] PBP indicators: {', '.join(found)}")

            # Look for shot indicators
            shot_indicators = ["shot", "x_coord", "y_coord", "location", "coordinates"]
            found_shots = [ind for ind in shot_indicators if ind in data_str]
            if found_shots:
                print(f"  [FOUND] Shot indicators: {', '.join(found_shots)}")
    else:
        print(f"  [ERROR] HTTP {response.status_code}")
except Exception as e:
    print(f"  [ERROR] {e}")

print()

# Test 2: getCalenderByDivision - Get recent games
print("[TEST 2] Testing /match/getCalenderByDivision...")
print("-" * 80)

try:
    # Division 0 = all, year = 2025 for 2024-25 season
    response = requests.get(
        f"{BASE_URL}/match/getCalenderByDivision",
        params={"division_external_id": 0, "year": 2025},
        timeout=10,
    )
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        # Save response
        with open(output_dir / "getCalenderByDivision.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[SAVED] getCalenderByDivision.json ({len(json.dumps(data))} chars)")

        if isinstance(data, list):
            print(f"  Found {len(data)} games")
            if data:
                game = data[0]
                print(f"  Sample game keys: {list(game.keys())[:15]}")

                # Check for match_external_id to use for detailed queries
                if "match_external_id" in game:
                    match_id = game["match_external_id"]
                    print(f"  [INFO] Sample match_external_id: {match_id}")

                    # Save match_id for next tests
                    with open(output_dir / "sample_match_id.txt", "w") as f:
                        f.write(str(match_id))
    else:
        print(f"  [ERROR] HTTP {response.status_code}")
except Exception as e:
    print(f"  [ERROR] {e}")

print()

# Test 3: Try to get detailed match data (guessing endpoint names)
print("[TEST 3] Testing potential match detail endpoints...")
print("-" * 80)

# Try to load a sample match_id
sample_match_id = None
match_id_file = output_dir / "sample_match_id.txt"
if match_id_file.exists():
    with open(match_id_file) as f:
        sample_match_id = f.read().strip()

if sample_match_id:
    print(f"Using match_id: {sample_match_id}")
    print()

    # Common endpoint patterns for match details
    endpoint_patterns = [
        ("/match/getMatchDetails", {"match_external_id": sample_match_id}),
        ("/match/getMatchStats", {"match_external_id": sample_match_id}),
        ("/match/getMatchBoxScore", {"match_external_id": sample_match_id}),
        ("/match/getMatchPlayByPlay", {"match_external_id": sample_match_id}),
        ("/match/getMatchEvents", {"match_external_id": sample_match_id}),
        ("/match/getMatchShots", {"match_external_id": sample_match_id}),
        ("/altrstats/getMatchStats", {"match_external_id": sample_match_id}),
        ("/altrstats/getMatchPlayByPlay", {"match_external_id": sample_match_id}),
        ("/altrstats/getMatchEvents", {"match_external_id": sample_match_id}),
        ("/altrstats/getMatchShots", {"match_external_id": sample_match_id}),
    ]

    for endpoint, params in endpoint_patterns:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=10)

            status_emoji = "✅" if response.status_code == 200 else "❌"
            print(f"  {status_emoji} {endpoint}: HTTP {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                filename = endpoint.split("/")[-1] + ".json"
                with open(output_dir / filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"      [SAVED] {filename} ({len(json.dumps(data))} chars)")

                # Check for PBP/shot indicators
                data_str = json.dumps(data).lower()
                if any(ind in data_str for ind in ["play", "event", "action", "quarter"]):
                    print("      [FOUND] Contains play-by-play indicators!")
                if any(ind in data_str for ind in ["shot", "x_coord", "y_coord", "location"]):
                    print("      [FOUND] Contains shot chart indicators!")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")
else:
    print("  [SKIP] No match_id available - run test 2 first")

print()

# Test 4: Check altrstats endpoints (the working ones we found)
print("[TEST 4] Testing /altrstats/ endpoints...")
print("-" * 80)

# Test getStanding
try:
    # POST request with competition_id
    payload = {"competition_external_id": 302}  # Betclic ELITE
    response = requests.post(
        f"{BASE_URL}/altrstats/getStanding",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    print(f"getStanding: HTTP {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        with open(output_dir / "getStanding.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("  [SAVED] getStanding.json")
except Exception as e:
    print(f"  [ERROR] {e}")

print()

# Test getPerformancePersonV2
try:
    # POST request with player and competition info
    payload = {
        "competition_external_id": 302,
        "person_external_id": 3586,  # Example player ID
    }
    response = requests.post(
        f"{BASE_URL}/altrstats/getPerformancePersonV2",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    print(f"getPerformancePersonV2: HTTP {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        with open(output_dir / "getPerformancePersonV2.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("  [SAVED] getPerformancePersonV2.json")
except Exception as e:
    print(f"  [ERROR] {e}")

print()

# Summary
print("=" * 80)
print("  TEST SUMMARY")
print("=" * 80)
print()

print(f"Results saved to: {output_dir}")
print()

print("Next steps:")
print("1. Review JSON files in api_responses/ folder")
print("2. Check which endpoints returned data")
print("3. Look for play-by-play and shot data in responses")
print("4. Update LNB fetchers with working endpoints")
print()

print("[COMPLETE] Endpoint testing finished")
print()
