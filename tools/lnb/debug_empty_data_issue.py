#!/usr/bin/env python3
"""Debug script to investigate why games return empty PBP/shots data

Investigation points:
1. Are the fixture UUIDs valid?
2. What are the actual game dates?
3. What league/competition do they belong to?
4. Does the API have data for these games?
5. Are we using the correct API endpoints?

Created: 2025-11-20
Purpose: Root cause analysis for empty data issue
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests

# Sample game IDs from ingestion output that returned empty data
SAMPLE_GAME_IDS = [
    "152b2122-67e6-11f0-a6bf-9d1d3a927139",  # ELITE 2 2024-2025
    "5a0f5857-67e6-11f0-80e9-79e23488fb37",  # Espoirs 2024-2025
    "542b0576-6715-11f0-8a29-9ffadebc148f",  # Betclic ELITE 2024-2025
]

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURE_DETAIL_ENDPOINT = "/v1/embed/12/fixture_detail"
PBP_ENDPOINT = "/v1/embed/12/live_data"
SHOTS_ENDPOINT = "/v1/embed/12/shot_chart"

print("=" * 80)
print("  DEBUG: EMPTY DATA INVESTIGATION")
print("=" * 80)
print(f"\nCurrent date (from system): {datetime.now().strftime('%Y-%m-%d')}")
print("Expected: 2024-25 season COMPLETE, 2025-26 season IN PROGRESS\n")

for game_id in SAMPLE_GAME_IDS:
    print("\n" + "=" * 80)
    print(f"  GAME: {game_id}")
    print("=" * 80)

    # Step 1: Get fixture metadata
    print("\n[STEP 1] Fetching fixture metadata...")
    try:
        url = f"{ATRIUM_API_BASE}{FIXTURE_DETAIL_ENDPOINT}"
        response = requests.get(url, params={"fixtureId": game_id}, timeout=15)
        response.raise_for_status()
        fixture_data = response.json()

        # Extract key details
        banner = fixture_data.get("data", {}).get("banner", {})
        competition = banner.get("competition", {})
        season = banner.get("season", {})
        competitors = banner.get("competitors", [])

        print("✅ Fixture metadata retrieved:")
        print(f"   Competition: {competition.get('name', 'Unknown')}")
        print(f"   Season: {season.get('name', 'Unknown')}")
        print(f"   Competition ID: {competition.get('id', 'Unknown')[:16]}...")
        print(f"   Season ID: {season.get('id', 'Unknown')[:16]}...")

        # Get game date
        start_time = banner.get("startTimeLocal")
        if start_time:
            game_date = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            print(f"   Game date: {game_date.strftime('%Y-%m-%d %H:%M')}")

            # Calculate days ago
            days_ago = (datetime.now(game_date.tzinfo) - game_date).days
            if days_ago > 0:
                print(f"   ⏰ {days_ago} days ago (SHOULD HAVE DATA)")
            elif days_ago == 0:
                print("   ⏰ TODAY")
            else:
                print(f"   ⏰ {abs(days_ago)} days in future (NO DATA EXPECTED)")
        else:
            print("   ⚠️  No game date found")

        # Get teams
        if competitors:
            home_team = next((c for c in competitors if c.get("isHome")), None)
            away_team = next((c for c in competitors if not c.get("isHome")), None)
            if home_team and away_team:
                print(f"   Teams: {home_team.get('name', '?')} vs {away_team.get('name', '?')}")

        # Get status
        status = banner.get("status", {}).get("name", "Unknown")
        print(f"   Status: {status}")

    except Exception as e:
        print(f"❌ Failed to fetch fixture metadata: {e}")
        continue

    # Step 2: Try to fetch PBP data
    print("\n[STEP 2] Attempting to fetch play-by-play data...")
    try:
        url = f"{ATRIUM_API_BASE}{PBP_ENDPOINT}"
        response = requests.get(url, params={"fixtureId": game_id}, timeout=15)
        response.raise_for_status()
        pbp_data = response.json()

        # Check what we got
        data_section = pbp_data.get("data", {})
        events = data_section.get("events", [])

        if events:
            print(f"✅ PBP data found: {len(events)} events")
            print(
                f"   First event: {events[0].get('type', 'Unknown')} at {events[0].get('clock', 'Unknown')}"
            )
        else:
            print("⚠️  PBP endpoint returned data but events array is empty")
            print(f"   Response keys: {list(data_section.keys())}")
            print(f"   Full response sample: {str(pbp_data)[:200]}...")

    except requests.HTTPError as e:
        print(f"❌ HTTP Error fetching PBP: {e.response.status_code}")
        print(f"   Response: {e.response.text[:200]}...")
    except Exception as e:
        print(f"❌ Error fetching PBP: {e}")

    # Step 3: Try to fetch shots data
    print("\n[STEP 3] Attempting to fetch shot chart data...")
    try:
        url = f"{ATRIUM_API_BASE}{SHOTS_ENDPOINT}"
        response = requests.get(url, params={"fixtureId": game_id}, timeout=15)
        response.raise_for_status()
        shots_data = response.json()

        # Check what we got
        data_section = shots_data.get("data", {})
        shots = data_section.get("shotChart", [])

        if shots:
            print(f"✅ Shot chart data found: {len(shots)} shots")
        else:
            print("⚠️  Shots endpoint returned data but shotChart array is empty")
            print(f"   Response keys: {list(data_section.keys())}")
            print(f"   Full response sample: {str(shots_data)[:200]}...")

    except requests.HTTPError as e:
        print(f"❌ HTTP Error fetching shots: {e.response.status_code}")
        print(f"   Response: {e.response.text[:200]}...")
    except Exception as e:
        print(f"❌ Error fetching shots: {e}")

print("\n" + "=" * 80)
print("  DIAGNOSIS SUMMARY")
print("=" * 80)
print("\n💡 KEY QUESTIONS TO ANSWER:")
print("1. Are the game dates in the past (should have data)?")
print("2. Do the API endpoints return any data at all?")
print("3. Is the game status 'completed' or still 'scheduled'?")
print("4. Are we querying the correct competition/league?")
print("\n📊 NEXT STEPS:")
print("1. Check if issue is API-side (no data) or code-side (wrong query)")
print("2. Verify we're discovering the correct fixtures for each league")
print("3. Check if league metadata (competition_id/season_id) is correct")
print()
