#!/usr/bin/env python3
"""Test how far back Atrium API has data available

Tests sample UUIDs from different seasons to determine data retention.
"""

import io
import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb import fetch_lnb_play_by_play, fetch_lnb_shots

# Sample UUIDs to test (need to collect these from LNB website for different years)
# These are placeholders - we'll need to manually collect real UUIDs
TEST_UUIDS = {
    # Format: season -> list of (uuid, description)
    "2024-2025": [
        ("0cac6e1b-6715-11f0-a9f3-27e6e78614e1", "Known valid"),
    ],
    "2023-2024": [
        ("3fcea9a1-1f10-11ee-a687-db190750bdda", "Known valid"),
    ],
    "2022-2023": [
        ("0d0504a0-6715-11f0-98ab-27e6e78614e1", "Known valid"),
    ],
    # Need to collect UUIDs for older seasons from LNB website
    # "2021-2022": [],
    # "2020-2021": [],
    # "2019-2020": [],
}

print("=" * 80)
print("LNB HISTORICAL DATA AVAILABILITY TEST")
print("=" * 80)
print()
print("Testing how far back Atrium API retains play-by-play and shot data...")
print()

results = {}

for season in sorted(TEST_UUIDS.keys(), reverse=True):  # Most recent first
    uuids = TEST_UUIDS[season]

    if not uuids:
        print(f"{season}: No test UUIDs available (need to collect from LNB website)")
        continue

    print(f"\n{season}:")
    print("-" * 80)

    season_results = []

    for uuid, description in uuids:
        print(f"  Testing {uuid[:30]}... ({description})")

        try:
            pbp = fetch_lnb_play_by_play(uuid)
            shots = fetch_lnb_shots(uuid)

            has_data = not pbp.empty and not shots.empty

            if has_data:
                print(f"    ✅ Data available: PBP={len(pbp)} events, Shots={len(shots)} shots")
                season_results.append(
                    {"uuid": uuid, "has_data": True, "pbp_events": len(pbp), "shots": len(shots)}
                )
            else:
                print(f"    ❌ No data: PBP={len(pbp)}, Shots={len(shots)}")
                season_results.append(
                    {"uuid": uuid, "has_data": False, "pbp_events": 0, "shots": 0}
                )
        except Exception as e:
            print(f"    ❌ Error: {str(e)[:60]}")
            season_results.append({"uuid": uuid, "has_data": False, "error": str(e)})

    results[season] = season_results

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print()

available_seasons = []
unavailable_seasons = []

for season in sorted(results.keys(), reverse=True):
    season_data = results[season]
    has_any_data = any(r.get("has_data", False) for r in season_data)

    if has_any_data:
        available_seasons.append(season)
        print(f"✅ {season}: Data available")
    else:
        unavailable_seasons.append(season)
        print(f"❌ {season}: No data found")

print()
print(
    f"Earliest confirmed season with data: {min(available_seasons) if available_seasons else 'Unknown'}"
)
print()
print("⚠️  NOTE: To test older seasons, manually collect UUIDs from:")
print("   https://www.lnb.fr/pro-a/calendrier")
print("   Select historical season and copy match-center URLs")
