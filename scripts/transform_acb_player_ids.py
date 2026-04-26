#!/usr/bin/env python
# ruff: noqa: E402
"""Transform Existing ACB Player IDs to Stable Format (Session 330d)

Since we can't re-fetch ACB data due to Playwright issues, this script
transforms the existing canonical ACB data to use stable player IDs.

OLD FORMAT: acb:2015-16:Team1:l_doncic  (season-specific)
NEW FORMAT: acb:l_doncic                 (stable across seasons)

Usage:
    python scripts/transform_acb_player_ids.py
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path("/workspace/api/src/airflow_project")))

import pandas as pd
from eda.nba_prospects.cbb_data.canonical_keys import CanonicalPlayerKey

DATA_DIR = PROJECT_ROOT / "data"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=ACB"

# Seasons with data
ACB_SEASONS = [
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


def extract_stable_player_id(old_id: str, player_name: str) -> str:
    """Extract stable player ID from season-specific ID.

    OLD: acb:2015-16:Team1:l_doncic
    NEW: acb:l_doncic

    If the format doesn't match expected pattern, use normalized name.
    """
    if pd.isna(old_id) or not old_id:
        # No ID - use normalized name
        normalized = CanonicalPlayerKey._normalize_player_name(player_name)
        return f"acb:{normalized}"

    # Check if it's already in new format (acb:xxx without season pattern)
    if old_id.startswith("acb:") and not re.search(r"\d{4}-\d{2}", old_id):
        # Already in new format
        return old_id

    # Extract the last component (player key) from old format
    # Pattern: acb:SEASON:TEAM:player_key
    parts = old_id.split(":")

    if len(parts) >= 4 and re.match(r"\d{4}-\d{2}", parts[1]):
        # Old format detected - extract player_key (last part)
        player_key = parts[-1]
        return f"acb:{player_key}"
    elif len(parts) == 2:
        # Already simplified format: acb:player_key
        return old_id
    else:
        # Unrecognized format - use normalized name
        normalized = CanonicalPlayerKey._normalize_player_name(player_name)
        return f"acb:{normalized}"


def transform_season(season: str):
    """Transform ACB data for a single season."""
    print(f"\n{'='*80}")
    print(f"TRANSFORMING ACB DATA: {season}")
    print(f"{'='*80}")

    season_dir = CANONICAL_DIR / f"season={season}"
    data_file = season_dir / "data.parquet"

    if not data_file.exists():
        print(f"  ⚠️  File not found: {data_file}")
        return

    try:
        # Load data
        df = pd.read_parquet(data_file)
        print(f"  Loaded {len(df)} records")

        # Show sample IDs before transformation
        sample_old = df["SOURCE_PLAYER_ID"].dropna().head(5).tolist()
        print("\n  Sample OLD SOURCE_PLAYER_IDs:")
        for pid in sample_old:
            print(f"    {pid}")

        # Transform player IDs
        print("\n  Transforming player IDs...")
        df["SOURCE_PLAYER_ID_OLD"] = df["SOURCE_PLAYER_ID"]  # Backup
        df["SOURCE_PLAYER_ID"] = df.apply(
            lambda row: extract_stable_player_id(
                row["SOURCE_PLAYER_ID"], row.get("PLAYER_NAME") or row.get("PLAYER_NAME_RAW", "")
            ),
            axis=1,
        )

        # Show sample IDs after transformation
        sample_new = df["SOURCE_PLAYER_ID"].dropna().head(5).tolist()
        print("\n  Sample NEW SOURCE_PLAYER_IDs:")
        for pid in sample_new:
            print(f"    {pid}")

        # Validation checks
        has_season_pattern = df["SOURCE_PLAYER_ID"].str.contains(r"\d{4}-\d{2}", na=False).sum()
        has_acb_prefix = df["SOURCE_PLAYER_ID"].str.startswith("acb:", na=False).sum()

        print("\n  Validation:")
        print(
            f"    {'✗' if has_season_pattern > 0 else '✓'} IDs with season pattern: {has_season_pattern}/{len(df)}"
        )
        print(
            f"    {'✓' if has_acb_prefix == len(df) else '✗'} IDs with 'acb:' prefix: {has_acb_prefix}/{len(df)}"
        )
        print(f"    ✓ Unique players: {df['SOURCE_PLAYER_ID'].nunique()}")

        # Save transformed data
        print("\n  Saving transformed data...")
        # Drop backup column
        df = df.drop(columns=["SOURCE_PLAYER_ID_OLD"])
        df.to_parquet(data_file, index=False, compression="snappy")
        print(f"  ✓ Saved to {data_file}")

    except Exception as e:
        print(f"  ✗ Error transforming {season}: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main execution."""
    print("=" * 80)
    print("ACB PLAYER ID TRANSFORMATION - Session 330d")
    print("=" * 80)
    print(f"Transforming {len(ACB_SEASONS)} seasons")
    print(f"Seasons: {', '.join(ACB_SEASONS)}")

    if not CANONICAL_DIR.exists():
        print(f"\n✗ ACB canonical directory not found: {CANONICAL_DIR}")
        return 1

    for season in ACB_SEASONS:
        try:
            transform_season(season)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            return 1
        except Exception as e:
            print(f"\n✗ Fatal error on {season}: {e}")
            import traceback

            traceback.print_exc()
            continue

    print("\n" + "=" * 80)
    print("TRANSFORMATION COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Run: python scripts/multi_gate_player_matcher.py")
    print("2. Run: python scripts/build_unified_career_gold_chunked.py")
    print("3. Validate Luka Doncic has single PLAYER_UID")

    return 0


if __name__ == "__main__":
    sys.exit(main())
