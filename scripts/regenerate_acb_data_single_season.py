#!/usr/bin/env python
# ruff: noqa: E402
"""Test ACB Data Regeneration with Single Season (Session 330d)

Test script to verify the new stable player ID format works correctly.
Tests with 2023-24 season only.
"""

import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
API_SRC = Path("/workspace/api/src/airflow_project")
sys.path.insert(0, str(API_SRC))

import pandas as pd
from eda.nba_prospects.cbb_data.fetchers.acb import fetch_acb_box_score, fetch_acb_schedule

DATA_DIR = PROJECT_ROOT / "data"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game"
CANONICAL_DIR.mkdir(parents=True, exist_ok=True)

# Test with just 2023-24 season
TEST_SEASON = "2023-24"


def test_acb_fix():
    """Test ACB data regeneration with single season."""
    print("=" * 80)
    print(f"TESTING ACB FIX: {TEST_SEASON}")
    print("=" * 80)

    try:
        # Step 1: Fetch schedule
        print(f"\nStep 1: Fetching ACB schedule for {TEST_SEASON}...")
        schedule = fetch_acb_schedule(season=TEST_SEASON)

        if schedule.empty:
            print(f"  ⚠️  No schedule found for {TEST_SEASON}")
            return

        print(f"  ✓ Found {len(schedule)} games")

        # Step 2: Fetch box scores for first 10 games only (test)
        print("\nStep 2: Fetching box scores for first 10 games (test)...")
        all_box_scores = []

        for i, row in schedule.head(10).iterrows():
            game_id = row.get("GAME_ID") or row.get("game_id")

            if not game_id:
                continue

            print(f"  Game {i+1}/10: {game_id}")

            try:
                box = fetch_acb_box_score(game_id=game_id)

                if not box.empty:
                    box["SEASON"] = TEST_SEASON
                    box["SOURCE_LEAGUE"] = "ACB"
                    all_box_scores.append(box)
                    print(f"    ✓ Got {len(box)} player records")

            except Exception as e:
                print(f"    ✗ Error: {e}")
                continue

        if not all_box_scores:
            print("\n  ⚠️  No box scores retrieved")
            return

        # Step 3: Analyze player IDs
        print("\nStep 3: Analyzing player ID format...")
        combined = pd.concat(all_box_scores, ignore_index=True)

        print(f"  Total player-game records: {len(combined)}")
        print(f"  Unique players (by SOURCE_PLAYER_ID): {combined['SOURCE_PLAYER_ID'].nunique()}")

        # Show sample SOURCE_PLAYER_IDs
        sample_ids = combined["SOURCE_PLAYER_ID"].dropna().head(10).tolist()
        print("\n  Sample SOURCE_PLAYER_IDs:")
        for pid in sample_ids:
            print(f"    - {pid}")

        # Check for old season-specific format
        has_season = combined["SOURCE_PLAYER_ID"].str.contains(r"\d{4}-\d{2}", na=False).sum()

        print("\n  Validation:")
        if has_season > 0:
            print(f"    ✗ FAIL: {has_season} IDs still contain season format (e.g., '2023-24')")
            # Show examples
            bad_ids = (
                combined[combined["SOURCE_PLAYER_ID"].str.contains(r"\d{4}-\d{2}", na=False)][
                    "SOURCE_PLAYER_ID"
                ]
                .head(3)
                .tolist()
            )
            print(f"    Examples: {bad_ids}")
        else:
            print("    ✓ PASS: All IDs use stable format (no season)")

        # Check for new format (acb:xxx)
        has_new_format = combined["SOURCE_PLAYER_ID"].str.startswith("acb:", na=False).sum()
        print(
            f"    {'✓' if has_new_format > 0 else '✗'} New format count: {has_new_format}/{len(combined)} ({has_new_format/len(combined)*100:.1f}%)"
        )

        # Look for Luka Doncic-like names (abbreviated)
        if "PLAYER_NAME" in combined.columns:
            sample_names = combined["PLAYER_NAME"].head(10).tolist()
            print("\n  Sample player names:")
            for name in sample_names:
                print(f"    - {name}")

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

        if has_season == 0 and has_new_format > 0:
            print("\n✓ FIX VERIFIED - Player IDs are stable across seasons!")
            print("\nReady to regenerate all seasons with:")
            print("  python scripts/regenerate_acb_data.py")
            return 0
        else:
            print("\n✗ FIX NOT WORKING - Player IDs still contain season")
            print("\nCheck acb.py line 2332 to ensure code was applied correctly")
            return 1

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_acb_fix())
