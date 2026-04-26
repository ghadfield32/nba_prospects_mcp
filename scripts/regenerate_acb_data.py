#!/usr/bin/env python
# ruff: noqa: E402
"""Regenerate ACB Data with Stable Player IDs (Session 330d)

This script regenerates ACB canonical data with the new stable player ID format:
- OLD: acb:2015-16:Team1:l_doncic (season-specific)
- NEW: acb:{player_id} OR acb:{normalized_name} (stable across seasons)

Usage:
    python scripts/regenerate_acb_data.py
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

# Seasons to regenerate (2015-16 through 2023-24)
SEASONS = [
    "2015-16",
    "2016-17",
    "2017-18",
    "2018-19",
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
]


def regenerate_acb_season(season: str):
    """Regenerate ACB data for a single season."""
    print(f"\n{'='*80}")
    print(f"REGENERATING ACB DATA: {season}")
    print(f"{'='*80}")

    try:
        # Step 1: Fetch schedule
        print(f"Step 1: Fetching ACB schedule for {season}...")
        schedule = fetch_acb_schedule(season=season)

        if schedule.empty:
            print(f"  ⚠️  No schedule found for {season}")
            return

        print(f"  ✓ Found {len(schedule)} games")

        # Step 2: Fetch box scores for each game
        print(f"Step 2: Fetching box scores for {len(schedule)} games...")
        all_box_scores = []

        for i, row in schedule.iterrows():
            game_id = row.get("GAME_ID") or row.get("game_id")

            if not game_id:
                continue

            if i % 10 == 0:
                print(f"  Progress: {i+1}/{len(schedule)} games")

            try:
                box = fetch_acb_box_score(game_id=game_id)

                if not box.empty:
                    # Add season column
                    box["SEASON"] = season
                    box["SOURCE_LEAGUE"] = "ACB"
                    all_box_scores.append(box)

            except Exception as e:
                print(f"    Error fetching game {game_id}: {e}")
                continue

        if not all_box_scores:
            print(f"  ⚠️  No box scores retrieved for {season}")
            return

        # Step 3: Combine and save
        print("Step 3: Combining and saving data...")
        combined = pd.concat(all_box_scores, ignore_index=True)

        print(f"  Total player-game records: {len(combined)}")
        print(f"  Unique players (by SOURCE_PLAYER_ID): {combined['SOURCE_PLAYER_ID'].nunique()}")

        # Check SOURCE_PLAYER_ID format
        sample_ids = combined["SOURCE_PLAYER_ID"].dropna().head(5).tolist()
        print(f"  Sample SOURCE_PLAYER_IDs: {sample_ids}")

        # Verify new format (should NOT contain season like "2015-16")
        has_season = combined["SOURCE_PLAYER_ID"].str.contains(r"\d{4}-\d{2}", na=False).sum()
        if has_season > 0:
            print(f"  ⚠️  WARNING: {has_season} IDs still contain season format!")
        else:
            print("  ✓ All IDs use stable format (no season)")

        # Save to canonical directory
        output_dir = CANONICAL_DIR / "league=ACB" / f"season={season}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "data.parquet"
        combined.to_parquet(output_file, index=False, compression="snappy")

        print(f"  ✓ Saved to {output_file}")
        print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")

    except Exception as e:
        print(f"  ✗ Error regenerating {season}: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main execution."""
    print("=" * 80)
    print("ACB DATA REGENERATION - Session 330d")
    print("=" * 80)
    print(f"Regenerating {len(SEASONS)} seasons with new stable player IDs")
    print(f"Seasons: {', '.join(SEASONS)}")

    for season in SEASONS:
        try:
            regenerate_acb_season(season)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            return 1
        except Exception as e:
            print(f"\n✗ Fatal error on {season}: {e}")
            import traceback

            traceback.print_exc()
            continue

    print("\n" + "=" * 80)
    print("REGENERATION COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Run: python scripts/multi_gate_player_matcher.py")
    print("2. Run: python scripts/build_unified_career_gold_chunked.py")
    print("3. Validate Luka Doncic has single PLAYER_UID")

    return 0


if __name__ == "__main__":
    sys.exit(main())
