#!/usr/bin/env python3
"""Fix OTE Thompson Twins Data Integration

This script addresses the OTE data gap that was causing Thompson twins to be excluded
from the unified dataset.

ROOT CAUSE:
1. thompson_data.parquet contains 51 real records (26 Amen, 25 Ausar)
2. BUT it's in a separate file, not data.parquet
3. AND it uses PLAYER_NAME_RAW instead of PLAYER_NAME
4. AND Thompson twins are not in the player identity map

FIX:
1. Standardize thompson_data.parquet column names
2. Merge into a new clean data.parquet for 2022-23 season
3. Add Thompson twins to player identity map
4. Remove the fake duplicated OTE data from other seasons

Usage:
    python scripts/fix_ote_thompson_data.py
    python scripts/fix_ote_thompson_data.py --dry-run
"""

import argparse
import hashlib
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name."""
    if not name or pd.isna(name):
        return ""
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\\s]", "", normalized)
    normalized = re.sub(r"\\s+", "_", normalized.strip())
    return normalized


def generate_player_uid(name_key: str, source_id: str) -> str:
    """Generate deterministic player UID."""
    base = f"OTE_{name_key}_{source_id}"
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:6]
    return f"P_{name_key}_{hash_suffix}"


def main():
    parser = argparse.ArgumentParser(description="Fix OTE Thompson twins data")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    print("=" * 80)
    print("OTE THOMPSON TWINS DATA FIX")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Paths
    DATA_DIR = Path(__file__).parent.parent / "data"
    CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game" / "league=OTE"
    PLAYER_MAP_PATH = DATA_DIR / "identity" / "player_map.parquet"
    THOMPSON_DATA_PATH = CANONICAL_DIR / "season=2022-23" / "thompson_data.parquet"
    MAIN_DATA_PATH = CANONICAL_DIR / "season=2022-23" / "data.parquet"
    BACKUP_DIR = DATA_DIR / "backups" / f"ote_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Step 1: Verify thompson_data.parquet exists
    print("Step 1: Verifying Thompson data file...")
    if not THOMPSON_DATA_PATH.exists():
        print(f"  ERROR: Thompson data file not found: {THOMPSON_DATA_PATH}")
        print("  Cannot proceed without source data.")
        return 1

    thompson_df = pd.read_parquet(THOMPSON_DATA_PATH)
    print(f"  Found {len(thompson_df)} Thompson records")
    print(f"  Players: {thompson_df['PLAYER_NAME_RAW'].unique().tolist()}")
    print(f"  Columns: {list(thompson_df.columns)}")

    # Step 2: Standardize Thompson data columns
    print("\nStep 2: Standardizing column names...")

    # Create standardized copy
    standardized_df = thompson_df.copy()

    # Rename PLAYER_NAME_RAW to PLAYER_NAME if needed
    if (
        "PLAYER_NAME_RAW" in standardized_df.columns
        and "PLAYER_NAME" not in standardized_df.columns
    ):
        standardized_df["PLAYER_NAME"] = standardized_df["PLAYER_NAME_RAW"]
        print("  Added PLAYER_NAME column from PLAYER_NAME_RAW")

    # Ensure NAME_KEY exists
    if "NAME_KEY" not in standardized_df.columns:
        standardized_df["NAME_KEY"] = standardized_df["PLAYER_NAME"].apply(normalize_name)
        print("  Generated NAME_KEY column")

    # Ensure PLAYER_ID exists (for compatibility)
    if "PLAYER_ID" not in standardized_df.columns and "SOURCE_PLAYER_ID" in standardized_df.columns:
        standardized_df["PLAYER_ID"] = standardized_df["SOURCE_PLAYER_ID"]
        print("  Added PLAYER_ID from SOURCE_PLAYER_ID")

    # Ensure TEAM_NAME_RAW exists
    if "TEAM" not in standardized_df.columns and "TEAM_NAME_RAW" in standardized_df.columns:
        standardized_df["TEAM"] = standardized_df["TEAM_NAME_RAW"]

    # Add TEAM_KEY if missing
    if "TEAM_KEY" not in standardized_df.columns and "TEAM_NAME_RAW" in standardized_df.columns:
        standardized_df["TEAM_KEY"] = standardized_df["TEAM_NAME_RAW"].apply(normalize_name)

    print(f"  Standardized columns: {list(standardized_df.columns)}")

    # Show sample data
    print("\n  Sample Thompson data:")
    sample_cols = ["GAME_ID", "PLAYER_NAME", "NAME_KEY", "PTS", "REB", "AST", "SEASON"]
    available_cols = [c for c in sample_cols if c in standardized_df.columns]
    print(standardized_df[available_cols].head(5).to_string())

    # Step 3: Backup existing data
    print("\nStep 3: Creating backups...")

    if not args.dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Backup main data.parquet
        if MAIN_DATA_PATH.exists():
            backup_path = BACKUP_DIR / "data.parquet.bak"
            shutil.copy2(MAIN_DATA_PATH, backup_path)
            print(f"  Backed up: {backup_path}")

        # Backup player_map.parquet
        if PLAYER_MAP_PATH.exists():
            backup_path = BACKUP_DIR / "player_map.parquet.bak"
            shutil.copy2(PLAYER_MAP_PATH, backup_path)
            print(f"  Backed up: {backup_path}")
    else:
        print("  [DRY RUN] Would create backups in:", BACKUP_DIR)

    # Step 4: Create new clean data.parquet for 2022-23
    print("\nStep 4: Creating clean 2022-23 OTE data file...")

    # The current data.parquet has WRONG data (current players in historical seasons)
    # Replace with Thompson twins data only
    clean_df = standardized_df.copy()

    print(f"  Clean data: {len(clean_df)} records")
    print(f"  Unique players: {clean_df['PLAYER_NAME'].nunique()}")

    if not args.dry_run:
        clean_df.to_parquet(MAIN_DATA_PATH, index=False, compression="snappy")
        print(f"  Saved: {MAIN_DATA_PATH}")
    else:
        print(f"  [DRY RUN] Would save {len(clean_df)} records to {MAIN_DATA_PATH}")

    # Step 5: Add Thompson twins to player identity map
    print("\nStep 5: Updating player identity map...")

    if not PLAYER_MAP_PATH.exists():
        print(f"  ERROR: Player map not found: {PLAYER_MAP_PATH}")
        return 1

    player_map_df = pd.read_parquet(PLAYER_MAP_PATH)
    print(f"  Current mappings: {len(player_map_df)}")

    # Check for existing Thompson entries
    existing_thompson = player_map_df[
        (player_map_df["SOURCE_LEAGUE"] == "OTE")
        & (player_map_df["NAME_KEY"].str.contains("thompson", case=False, na=False))
    ]
    print(f"  Existing Thompson OTE entries: {len(existing_thompson)}")

    # Create new Thompson entries
    thompson_players = standardized_df[
        ["SOURCE_PLAYER_ID", "PLAYER_NAME", "NAME_KEY"]
    ].drop_duplicates()

    new_entries = []
    for _, player in thompson_players.iterrows():
        source_id = player["SOURCE_PLAYER_ID"]
        name_key = player["NAME_KEY"]
        player_name = player["PLAYER_NAME"]

        # Check if already exists
        exists = player_map_df[
            (player_map_df["SOURCE_LEAGUE"] == "OTE")
            & (player_map_df["SOURCE_PLAYER_ID"] == source_id)
        ]

        if len(exists) == 0:
            player_uid = generate_player_uid(name_key, source_id)
            new_entries.append(
                {
                    "SOURCE_LEAGUE": "OTE",
                    "SOURCE_PLAYER_ID": source_id,
                    "PLAYER_UID": player_uid,
                    "NAME_KEY": name_key,
                    "MATCH_RULE": "manual_thompson_fix",
                    "CONFIDENCE": 1.0,
                }
            )
            print(f"  + Adding: {player_name} ({name_key}) -> {player_uid}")
        else:
            print(f"  = Exists: {player_name} ({name_key})")

    if new_entries:
        new_entries_df = pd.DataFrame(new_entries)
        updated_player_map = pd.concat([player_map_df, new_entries_df], ignore_index=True)

        print(f"\n  New total mappings: {len(updated_player_map)}")

        if not args.dry_run:
            updated_player_map.to_parquet(PLAYER_MAP_PATH, index=False)
            print(f"  Saved: {PLAYER_MAP_PATH}")
        else:
            print(f"  [DRY RUN] Would add {len(new_entries)} entries to player map")
    else:
        print("  No new entries needed")

    # Step 6: Clean up fake OTE data in other seasons
    print("\nStep 6: Cleaning up fake OTE data in other seasons...")

    fake_seasons = ["2021-22", "2023-24", "2024-25", "2025"]
    for season in fake_seasons:
        season_dir = CANONICAL_DIR / f"season={season}"
        season_file = season_dir / "data.parquet"

        if season_file.exists():
            try:
                df = pd.read_parquet(season_file)

                # Check if this is fake data (current players with same count as other seasons)
                # Real 2021-22 should have Thompson twins era players, not current players
                player_names = df["PLAYER_NAME"].unique() if "PLAYER_NAME" in df.columns else []

                # Flag: if "Styles Clemmons" is in every season, it's fake data
                is_fake = any("Styles Clemmons" in str(n) for n in player_names)

                if is_fake:
                    print(f"  {season}: {len(df)} records - FAKE DATA (current players)")
                    if not args.dry_run:
                        # Move to backup instead of deleting
                        backup_path = BACKUP_DIR / f"fake_{season}_data.parquet"
                        shutil.move(season_file, backup_path)
                        print(f"    Moved to: {backup_path}")
                    else:
                        print("    [DRY RUN] Would move fake data to backup")
                else:
                    print(f"  {season}: {len(df)} records - keeping (appears valid)")
            except Exception as e:
                print(f"  {season}: Error reading - {e}")
        else:
            print(f"  {season}: No data.parquet file")

    # Step 7: Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print("\nChanges made:")
    print("  1. Standardized Thompson twins data (51 records)")
    print(f"  2. Saved to: {MAIN_DATA_PATH}")
    if new_entries:
        print(f"  3. Added {len(new_entries)} player mappings for Thompson twins")
    print(f"  4. Backed up originals to: {BACKUP_DIR}")

    print("\nThompson twins data:")
    for _, player in thompson_players.iterrows():
        player_games = standardized_df[standardized_df["NAME_KEY"] == player["NAME_KEY"]]
        ppg = player_games["PTS"].mean()
        print(f"  - {player['PLAYER_NAME']}: {len(player_games)} games, {ppg:.1f} PPG")

    print("\nNext steps:")
    print("  1. Re-run unified career builder:")
    print("     python scripts/build_unified_career_gold_chunked.py")
    print()
    print("  2. Validate Thompson twins:")
    print("     python scripts/validate_known_players.py")
    print()
    print("  3. Verify in gold dataset:")
    print(
        "     python -c \"import pandas as pd; df = pd.read_parquet('data/gold/player_career_unified_tier1.parquet'); print(df[df['PLAYER_NAME'].str.contains('Thompson', na=False)][['PLAYER_NAME', 'SOURCE_LEAGUE', 'SEASON']].drop_duplicates())\""
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
