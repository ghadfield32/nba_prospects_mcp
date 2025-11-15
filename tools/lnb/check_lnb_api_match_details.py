#!/usr/bin/env python3
"""Check LNB API for match details of invalid UUIDs

Goal: Determine if invalid UUIDs are:
1. Future games (not yet played)
2. Different competitions (not Pro A)
3. Invalid/non-existent games
4. Games outside Atrium's data coverage

This will help us understand if we should:
- Wait for games to be played
- Exclude non-Pro A games
- Remove invalid UUIDs entirely
- Expand to other data sources
"""

import io
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_endpoints import LNB_API

# Invalid UUIDs from 2022-2023
INVALID_UUIDS = [
    "1515cca4-67e6-11f0-908d-9d1d3a927139",
    "0d346b41-6715-11f0-b247-27e6e78614e1",
    "0d2989af-6715-11f0-b609-27e6e78614e1",
    "0d0c88fe-6715-11f0-9d9c-27e6e78614e1",
    "14fa0584-67e6-11f0-8cb3-9d1d3a927139",
    "0d225fad-6715-11f0-810f-27e6e78614e1",
    "0cfdeaf9-6715-11f0-87bc-27e6e78614e1",
    "0cf637f3-6715-11f0-b9ed-27e6e78614e1",
    "0d141f9e-6715-11f0-bf7e-27e6e78614e1",
]

# Valid UUID for comparison
VALID_UUID = "0d0504a0-6715-11f0-98ab-27e6e78614e1"


def get_match_details_from_lnb(uuid: str) -> dict:
    """Get match details from LNB official API

    Args:
        uuid: Match UUID

    Returns:
        Dict with match details or error info
    """
    url = LNB_API.match_details(uuid)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        result = {"uuid": uuid, "status_code": response.status_code, "url": url}

        if response.status_code == 200:
            try:
                data = response.json()
                result["success"] = True
                result["data"] = data

                # Extract key fields
                if isinstance(data, dict):
                    # Check for common fields
                    result["has_match_info"] = bool(data.get("match") or data.get("data"))

                    # Try to extract match date
                    match_data = data.get("data", {}) if "data" in data else data.get("match", {})
                    if match_data:
                        result["match_date"] = match_data.get("matchDate") or match_data.get("date")
                        result["status"] = match_data.get("status") or match_data.get("matchStatus")
                        result["competition"] = match_data.get("competition") or match_data.get(
                            "competitionName"
                        )
                        result["home_team"] = (
                            match_data.get("homeTeam", {}).get("name")
                            if isinstance(match_data.get("homeTeam"), dict)
                            else None
                        )
                        result["away_team"] = (
                            match_data.get("awayTeam", {}).get("name")
                            if isinstance(match_data.get("awayTeam"), dict)
                            else None
                        )

            except json.JSONDecodeError:
                result["success"] = False
                result["error"] = "Invalid JSON response"
        else:
            result["success"] = False
            result["error"] = f"HTTP {response.status_code}"

        return result

    except Exception as e:
        return {"uuid": uuid, "success": False, "error": str(e), "error_type": type(e).__name__}


print("=" * 80)
print("LNB API MATCH DETAILS CHECK")
print("=" * 80)
print()
print("Checking if invalid UUIDs have match details in LNB API...")
print("This will tell us if they're real games and why they might not have PBP data.")
print()

# Test valid UUID first (baseline)
print("BASELINE - Valid UUID:")
print(f"UUID: {VALID_UUID}")
print()

valid_result = get_match_details_from_lnb(VALID_UUID)
print(f"Status: {valid_result['status_code']}")
if valid_result.get("success"):
    print(f"Match Date: {valid_result.get('match_date', 'N/A')}")
    print(f"Status: {valid_result.get('status', 'N/A')}")
    print(f"Competition: {valid_result.get('competition', 'N/A')}")
    print(
        f"Teams: {valid_result.get('home_team', 'N/A')} vs {valid_result.get('away_team', 'N/A')}"
    )
else:
    print(f"Error: {valid_result.get('error')}")

print()
print("-" * 80)
print()

# Test invalid UUIDs
print("TESTING INVALID UUIDs:")
print()

results = []
for i, uuid in enumerate(INVALID_UUIDS, 1):
    print(f"[{i}/9] {uuid[:35]}... ", end="")

    result = get_match_details_from_lnb(uuid)

    if result.get("success"):
        match_date = result.get("match_date", "Unknown")
        status = result.get("status", "Unknown")
        competition = result.get("competition", "Unknown")

        print("✅ Found")
        print(f"      Date: {match_date}")
        print(f"      Status: {status}")
        print(f"      Competition: {competition}")

        # Check if game is in the future
        if match_date and match_date != "Unknown":
            try:
                # Try parsing date
                if isinstance(match_date, str):
                    # Common formats: "2023-10-15T19:00:00Z" or "2023-10-15"
                    match_dt = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
                    now = datetime.now()
                    if match_dt > now:
                        print("      ⚠️  FUTURE GAME (not yet played)")
                    else:
                        days_ago = (now - match_dt).days
                        print(f"      ℹ️  Played {days_ago} days ago")
            except Exception:
                pass

    elif result.get("status_code") == 404:
        print("❌ Not found (404) - UUID doesn't exist in LNB API")
    else:
        print(f"❌ Error: {result.get('error')}")

    results.append(result)
    print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

found_count = sum(1 for r in results if r.get("success"))
not_found_count = sum(1 for r in results if r.get("status_code") == 404)
error_count = len(results) - found_count - not_found_count

print(f"Total tested: {len(results)}")
print(f"Found in LNB API: {found_count}")
print(f"Not found (404): {not_found_count}")
print(f"Errors: {error_count}")
print()

if found_count > 0:
    print("Analysis of found games:")

    future_games = 0
    past_games = 0
    unknown_date = 0

    for result in results:
        if result.get("success"):
            match_date = result.get("match_date")
            if match_date and match_date != "Unknown":
                try:
                    match_dt = datetime.fromisoformat(str(match_date).replace("Z", "+00:00"))
                    if match_dt > datetime.now():
                        future_games += 1
                    else:
                        past_games += 1
                except Exception:
                    unknown_date += 1
            else:
                unknown_date += 1

    print(f"  Future games: {future_games} (not yet played)")
    print(f"  Past games: {past_games} (already played)")
    print(f"  Unknown date: {unknown_date}")
    print()

print("CONCLUSION:")
print()

if future_games > 0:
    print(f"✅ {future_games} UUIDs are FUTURE GAMES - wait for them to be played")
    print("   Action: Keep these UUIDs, check again after games are played")
elif past_games > 0:
    print(f"⚠️  {past_games} UUIDs are PAST GAMES but have no Atrium data")
    print("   Possible reasons:")
    print("   - Different competition (not Pro A)")
    print("   - Atrium doesn't cover these games")
    print("   - Data collection issue")
    print("   Action: Check competition type, may need to exclude")
elif not_found_count > 0:
    print(f"❌ {not_found_count} UUIDs NOT FOUND in LNB API")
    print("   These are invalid UUIDs")
    print("   Action: Remove from UUID file")

# Save results
output_file = Path(__file__).parent / "lnb_api_match_details_check.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(
        {
            "timestamp": datetime.now().isoformat(),
            "valid_baseline": valid_result,
            "invalid_uuids_results": results,
            "summary": {
                "total": len(results),
                "found": found_count,
                "not_found": not_found_count,
                "errors": error_count,
            },
        },
        f,
        indent=2,
        default=str,
    )

print()
print(f"Detailed results saved to: {output_file.name}")
