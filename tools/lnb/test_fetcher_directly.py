#!/usr/bin/env python3
"""Direct test of LNB fetcher functions

Purpose: Determine if fetch_lnb_play_by_play() returns data correctly
for a known good game (2022-23 Betclic ELITE, status CONFIRMED)

This will tell us if the issue is:
- Option A: Fetcher returns data correctly → issue is downstream in ingestion
- Option B: Fetcher returns empty → bug in fetcher implementation
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cbb_data.fetchers.lnb import fetch_lnb_game_shots, fetch_lnb_play_by_play

# Known good game: 2022-2023 Betclic ELITE, status CONFIRMED
# Verified to have 130 events in period 1 via direct API call
TEST_GAME_ID = "d46eb4f5-11a0-11ed-b3a9-c5477c827e55"

print("=" * 80)
print("  DIRECT FETCHER TEST")
print("=" * 80)
print(f"\nTest game: {TEST_GAME_ID}")
print("Expected: 2022-2023 Betclic ELITE, status CONFIRMED")
print("API verification: 130 events in period 1\n")

# Test PBP fetcher
print("-" * 80)
print("Testing fetch_lnb_play_by_play()...")
print("-" * 80)

try:
    pbp_df = fetch_lnb_play_by_play(TEST_GAME_ID)

    if pbp_df is not None and len(pbp_df) > 0:
        print(f"✅ SUCCESS: Fetcher returned {len(pbp_df)} events")
        print(f"\nDataFrame shape: {pbp_df.shape}")
        print(f"Columns: {list(pbp_df.columns)}")
        print("\nFirst event:")
        print(pbp_df.iloc[0].to_dict())

        # Check period distribution
        if "PERIOD_ID" in pbp_df.columns:
            period_counts = pbp_df["PERIOD_ID"].value_counts().sort_index()
            print("\nEvents per period:")
            for period, count in period_counts.items():
                print(f"  Period {period}: {count} events")
    else:
        print("❌ FAIL: Fetcher returned empty DataFrame")
        print("This indicates a bug in the fetcher implementation")
        print("despite the API having data")

except Exception as e:
    print(f"❌ ERROR: Fetcher raised exception: {e}")
    import traceback

    traceback.print_exc()

# Test shots fetcher
print("\n" + "-" * 80)
print("Testing fetch_lnb_game_shots()...")
print("-" * 80)

try:
    shots_df = fetch_lnb_game_shots(TEST_GAME_ID)

    if shots_df is not None and len(shots_df) > 0:
        print(f"✅ SUCCESS: Fetcher returned {len(shots_df)} shots")
        print(f"\nDataFrame shape: {shots_df.shape}")
        print(f"Columns: {list(shots_df.columns)}")
        print("\nFirst shot:")
        print(shots_df.iloc[0].to_dict())
    else:
        print("⚠️  Fetcher returned empty DataFrame")
        print("Note: Some games may not have shot chart data")

except Exception as e:
    print(f"❌ ERROR: Fetcher raised exception: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)
print("  TEST COMPLETE")
print("=" * 80)
