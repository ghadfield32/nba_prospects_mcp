#!/usr/bin/env python3
"""Test the new LNB play-by-play and shots fetchers"""

import io
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.cbb_data.fetchers.lnb import fetch_lnb_play_by_play, fetch_lnb_shots

# Test game ID (Nancy vs Saint-Quentin from our captures)
GAME_ID = "3522345e-3362-11f0-b97d-7be2bdc7a840"

print("=" * 80)
print("  TESTING LNB PLAY-BY-PLAY AND SHOTS FETCHERS")
print("=" * 80)
print()

# ==============================================================================
# TEST 1: Play-by-Play Fetcher
# ==============================================================================
print("=" * 80)
print("  TEST 1: fetch_lnb_play_by_play()")
print("=" * 80)
print()
print(f"Game ID: {GAME_ID}")
print()

try:
    df_pbp = fetch_lnb_play_by_play(GAME_ID)

    print(f"✅ SUCCESS! Retrieved {len(df_pbp)} play-by-play events")
    print()

    # Show column info
    print("Columns:")
    for col in df_pbp.columns:
        print(f"  - {col}")
    print()

    # Show sample events
    print("Sample events (first 5):")
    print(df_pbp.head()[["PERIOD_ID", "CLOCK", "EVENT_TYPE", "PLAYER_NAME", "DESCRIPTION"]])
    print()

    # Show event type breakdown
    print("Event type counts:")
    event_counts = df_pbp["EVENT_TYPE"].value_counts()
    for event_type, count in event_counts.items():
        print(f"  {event_type}: {count}")
    print()

except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback

    traceback.print_exc()
    print()

# ==============================================================================
# TEST 2: Shots Fetcher
# ==============================================================================
print("=" * 80)
print("  TEST 2: fetch_lnb_shots()")
print("=" * 80)
print()
print(f"Game ID: {GAME_ID}")
print()

try:
    df_shots = fetch_lnb_shots(GAME_ID)

    print(f"✅ SUCCESS! Retrieved {len(df_shots)} shots")
    print()

    # Show column info
    print("Columns:")
    for col in df_shots.columns:
        print(f"  - {col}")
    print()

    # Show sample shots
    print("Sample shots (first 5):")
    print(
        df_shots.head()[
            [
                "PERIOD_ID",
                "SHOT_TYPE",
                "SHOT_SUBTYPE",
                "PLAYER_NAME",
                "SUCCESS",
                "X_COORD",
                "Y_COORD",
            ]
        ]
    )
    print()

    # Show shooting percentages
    print("Shooting summary:")
    total_shots = len(df_shots)
    made_shots = df_shots["SUCCESS"].sum()
    missed_shots = total_shots - made_shots
    fg_pct = made_shots / total_shots if total_shots > 0 else 0

    print(f"  Total shots: {total_shots}")
    print(f"  Made: {made_shots}")
    print(f"  Missed: {missed_shots}")
    print(f"  FG%: {fg_pct:.1%}")
    print()

    # Show shot type breakdown
    print("Shot type counts:")
    shot_counts = df_shots["SHOT_TYPE"].value_counts()
    for shot_type, count in shot_counts.items():
        made = df_shots[df_shots["SHOT_TYPE"] == shot_type]["SUCCESS"].sum()
        pct = made / count if count > 0 else 0
        print(f"  {shot_type}: {count} attempts, {made} made ({pct:.1%})")
    print()

except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback

    traceback.print_exc()
    print()

print("=" * 80)
print("  TESTS COMPLETE")
print("=" * 80)
print()
