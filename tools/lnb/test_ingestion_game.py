#!/usr/bin/env python3
"""Test a specific game that returned empty during ingestion

Purpose: Determine WHY game 152b2122-67e6-11f0-a6bf-9d1d3a927139 returns empty data
- Check game status (SCHEDULED vs CONFIRMED)
- Check game date (past vs future)
- Check if API actually has data
"""

from __future__ import annotations

import base64
import io
import json
import sys
import zlib
from datetime import datetime
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Game from ingestion that returned empty
TEST_GAME_ID = "152b2122-67e6-11f0-a6bf-9d1d3a927139"  # ELITE 2 2024-2025

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURE_DETAIL_ENDPOINT = "/v1/embed/12/fixture_detail"

print("=" * 80)
print("  TEST GAME THAT RETURNED EMPTY DURING INGESTION")
print("=" * 80)
print(f"\nGame ID: {TEST_GAME_ID}")
print("This game returned empty PBP/shots during bulk ingestion\n")


def create_state(fixture_id: str, view: str) -> str:
    """Create state parameter for Atrium API"""
    state_obj = {"z": view, "f": fixture_id}
    json_str = json.dumps(state_obj, separators=(",", ":"))
    compressed = zlib.compress(json_str.encode("utf-8"))
    return base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")


# Step 1: Get fixture metadata
print("-" * 80)
print("STEP 1: Check game metadata")
print("-" * 80)

url = f"{ATRIUM_API_BASE}{FIXTURE_DETAIL_ENDPOINT}"
response = requests.get(url, params={"fixtureId": TEST_GAME_ID}, timeout=15)
response.raise_for_status()
fixture_data = response.json()

banner = fixture_data.get("data", {}).get("banner", {})
status_obj = banner.get("status", {})
competition = banner.get("competition", {})
season = banner.get("season", {})

status = status_obj.get("name", "Unknown")
start_time = banner.get("startTimeLocal")

print(f"Competition: {competition.get('name', 'Unknown')}")
print(f"Season: {season.get('name', 'Unknown')}")
print(f"Status: {status}")

if start_time:
    game_date = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    print(f"Game date: {game_date.strftime('%Y-%m-%d %H:%M')}")

    # Calculate days from now
    days_diff = (datetime.now(game_date.tzinfo) - game_date).days
    if days_diff > 0:
        print(f"⏰ {days_diff} days ago (PAST - should have data)")
    elif days_diff == 0:
        print("⏰ TODAY")
    else:
        print(f"⏰ {abs(days_diff)} days in future (FUTURE - no data expected)")
        print(f"   📅 Scheduled for: {game_date.strftime('%Y-%m-%d')}")

# Step 2: Check if PBP data exists
print("\n" + "-" * 80)
print("STEP 2: Check PBP data availability")
print("-" * 80)

state_param = create_state(TEST_GAME_ID, "pbp")
url = f"{ATRIUM_API_BASE}{FIXTURE_DETAIL_ENDPOINT}"
response = requests.get(url, params={"state": state_param}, timeout=15)
response.raise_for_status()
pbp_response = response.json()

data = pbp_response.get("data", {})
pbp_data = data.get("pbp", {})

if pbp_data:
    total_events = 0
    for period_id, period_data in pbp_data.items():
        events = period_data.get("events", [])
        total_events += len(events)
        if events:
            print(f"✅ Period {period_id}: {len(events)} events")

    if total_events > 0:
        print(f"\n✅ TOTAL: {total_events} events found")
        print("   This game DOES have data! Issue is in game selection logic.")
    else:
        print("\n⚠️  PBP data structure exists but all periods are empty")
else:
    print("❌ No PBP data found - game likely hasn't been played yet")
    print(f"   API response keys: {list(data.keys())}")

print("\n" + "=" * 80)
print("  DIAGNOSIS")
print("=" * 80)

if status != "CONFIRMED":
    print(f"\n🔍 ROOT CAUSE: Game status is '{status}' (not CONFIRMED)")
    print("   This game hasn't been played yet or data isn't published")
    print("\n💡 FIX NEEDED: Game index filter logic should exclude non-CONFIRMED games")
elif start_time:
    if days_diff < 0:
        print(f"\n🔍 ROOT CAUSE: Game is scheduled for {abs(days_diff)} days in future")
        print("   Future game filter should have caught this but didn't")
        print("\n💡 FIX NEEDED: Check future game filtering logic in bulk_ingest_pbp_shots.py")
    else:
        print(f"\n🔍 MYSTERY: Game is {days_diff} days in past with status '{status}'")
        print("   But API returns no data - this is unexpected")
        print("\n💡 INVESTIGATE: Check Atrium API data availability")
