#!/usr/bin/env python3
"""Test match detail endpoints for play-by-play and shot data

Uses a completed game (external_id: 28910) to test various endpoint patterns.

Usage:
    uv run python tools/lnb/test_match_details.py
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

print("=" * 80)
print("  Testing Match Detail Endpoints")
print("  Target: Game 28910 (Cholet vs Nanterre - COMPLETE)")
print("=" * 80)
print()

# Create output directory
output_dir = Path(__file__).parent / "api_responses"
output_dir.mkdir(exist_ok=True)

BASE_URL = "https://api-prod.lnb.fr"
MATCH_ID = 28910  # Completed game

print(f"Testing match_external_id: {MATCH_ID}")
print()

# Comprehensive list of endpoint patterns to test
endpoints_to_test = [
    # Match endpoints
    ("/match/getMatchDetails", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchStats", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchBoxScore", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchPlayByPlay", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchEvents", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchShots", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchTimeline", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchActions", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchQuarters", "GET", {"match_external_id": MATCH_ID}),
    ("/match/getMatchSummary", "GET", {"match_external_id": MATCH_ID}),
    # Altrstats endpoints
    ("/altrstats/getMatchStats", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchBoxScore", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchPlayByPlay", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchEvents", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchShots", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchTimeline", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchDetails", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchData", "GET", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchSummary", "GET", {"match_external_id": MATCH_ID}),
    # Stats endpoints
    ("/stats/getMatchBoxScore", "GET", {"match_external_id": MATCH_ID}),
    ("/stats/getMatchPlayByPlay", "GET", {"match_external_id": MATCH_ID}),
    ("/stats/getMatchShots", "GET", {"match_external_id": MATCH_ID}),
    ("/stats/getMatchEvents", "GET", {"match_external_id": MATCH_ID}),
    # Try with POST as well
    ("/altrstats/getMatchBoxScore", "POST", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchPlayByPlay", "POST", {"match_external_id": MATCH_ID}),
    ("/altrstats/getMatchShots", "POST", {"match_external_id": MATCH_ID}),
]

successful_endpoints = []
failed_endpoints = []

print("Testing endpoints...")
print("-" * 80)

for endpoint, method, params in endpoints_to_test:
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=10)
        else:  # POST
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json=params,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

        status = response.status_code

        if status == 200:
            # Success!
            data = response.json()

            # Save response
            filename = f"{endpoint.replace('/', '_')}_{method}.json"
            filepath = output_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Check for PBP/shot indicators
            data_str = json.dumps(data).lower()
            pbp_found = any(
                ind in data_str
                for ind in ["play", "event", "action", "quarter", "period", "timeline"]
            )
            shot_found = any(
                ind in data_str for ind in ["shot", "x_coord", "y_coord", "location", "position"]
            )

            indicators = []
            if pbp_found:
                indicators.append("PBP")
            if shot_found:
                indicators.append("SHOTS")

            indicator_str = f" [{', '.join(indicators)}]" if indicators else ""

            print(f"✅ {method:4} {endpoint:45} - HTTP {status}{indicator_str}")
            print(f"   Saved: {filename} ({len(data_str)} chars)")

            successful_endpoints.append((endpoint, method, indicators))
        elif status == 404:
            print(f"❌ {method:4} {endpoint:45} - HTTP 404 (Not Found)")
            failed_endpoints.append((endpoint, method, status))
        else:
            print(f"⚠️  {method:4} {endpoint:45} - HTTP {status}")
            failed_endpoints.append((endpoint, method, status))

    except requests.exceptions.Timeout:
        print(f"⏱️  {method:4} {endpoint:45} - TIMEOUT")
        failed_endpoints.append((endpoint, method, "TIMEOUT"))
    except Exception as e:
        print(f"❌ {method:4} {endpoint:45} - ERROR: {str(e)[:30]}")
        failed_endpoints.append((endpoint, method, str(e)[:20]))

print()
print("=" * 80)
print("  RESULTS SUMMARY")
print("=" * 80)
print()

print(f"✅ Successful endpoints: {len(successful_endpoints)}")
for endpoint, method, indicators in successful_endpoints:
    ind_str = f" - Contains: {', '.join(indicators)}" if indicators else ""
    print(f"   {method:4} {endpoint}{ind_str}")

print()
print(f"❌ Failed endpoints: {len(failed_endpoints)}")

print()
if successful_endpoints:
    print("🎯 KEY FINDINGS:")
    print()

    pbp_endpoints = [e for e in successful_endpoints if "PBP" in e[2]]
    shot_endpoints = [e for e in successful_endpoints if "SHOTS" in e[2]]

    if pbp_endpoints:
        print("Play-by-Play Data Found In:")
        for endpoint, method, _ in pbp_endpoints:
            print(f"  - {method} {endpoint}")
        print()

    if shot_endpoints:
        print("Shot Chart Data Found In:")
        for endpoint, method, _ in shot_endpoints:
            print(f"  - {method} {endpoint}")
        print()

    if not pbp_endpoints and not shot_endpoints:
        print("⚠️  No PBP or Shot data detected in successful responses")
        print("   (Data may exist but not match keyword patterns)")
        print()

print(f"Results saved to: {output_dir}")
print()

print("[COMPLETE] Match detail testing finished")
print()
