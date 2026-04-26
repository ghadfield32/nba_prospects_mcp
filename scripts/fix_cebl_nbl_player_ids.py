#!/usr/bin/env python3
"""Fix CEBL and NBL SOURCE_PLAYER_ID Issues

CEBL: All SOURCE_PLAYER_IDs are "None" - generate deterministic IDs
NBL: 84.8% SOURCE_PLAYER_IDs are "None" - generate IDs for missing

Strategy:
- Generate deterministic SOURCE_PLAYER_ID using: PLAYER_NAME_RAW + TEAM_KEY + SEASON
- Use MD5 hash to create unique IDs
- Preserve existing valid SOURCE_PLAYER_IDs

Usage:
    python scripts/fix_cebl_nbl_player_ids.py
"""

import hashlib
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name."""
    if not name or pd.isna(name):
        return ""

    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized.strip())

    return normalized


def generate_deterministic_id(player_name: str, team_key: str, season: str) -> str:
    """Generate deterministic player ID from player attributes.

    Args:
        player_name: Raw player name
        team_key: Team identifier
        season: Season identifier

    Returns:
        Deterministic player ID (MD5 hash)
    """
    # Create composite key
    composite = f"{normalize_name(player_name)}_{team_key}_{season}"

    # Generate MD5 hash (first 16 chars for readability)
    player_id = hashlib.md5(composite.encode()).hexdigest()[:16]

    return f"GEN_{player_id}"


def fix_league_player_ids(league: str, dry_run: bool = False):
    """Fix SOURCE_PLAYER_ID for a specific league.

    Args:
        league: League code (CEBL or NBL)
        dry_run: If True, only print statistics without modifying files
    """
    print(f"\n{'='*80}")
    print(f"FIXING {league} SOURCE_PLAYER_IDs")
    print(f"{'='*80}")

    base_path = Path(f"data/canonical/box_player_game/league={league}")

    if not base_path.exists():
        print(f"ERROR: {league} directory not found at {base_path}")
        return

    # Process each season
    season_dirs = sorted([d for d in base_path.iterdir() if d.is_dir()])

    total_records = 0
    total_fixed = 0

    for season_dir in season_dirs:
        data_file = season_dir / "data.parquet"

        if not data_file.exists():
            continue

        print(f"\n{season_dir.name}:")

        # Load data
        df = pd.read_parquet(data_file)

        print(f"  Records: {len(df):,}")

        # Count "None" IDs
        none_count = (df["SOURCE_PLAYER_ID"].astype(str) == "None").sum()
        none_pct = none_count / len(df) * 100

        print(f"  'None' SOURCE_PLAYER_IDs: {none_count:,} ({none_pct:.1f}%)")

        if none_count == 0:
            print("  ✓ All SOURCE_PLAYER_IDs valid, skipping")
            total_records += len(df)
            continue

        # Generate new IDs for "None" records
        mask = df["SOURCE_PLAYER_ID"].astype(str) == "None"

        # Extract season identifier
        season_id = season_dir.name.replace("season=", "")

        # Generate deterministic IDs
        new_ids = df[mask].apply(
            lambda row, season_id=season_id: generate_deterministic_id(
                row["PLAYER_NAME_RAW"], row["TEAM_KEY"], season_id
            ),
            axis=1,
        )

        if not dry_run:
            # Update SOURCE_PLAYER_IDs
            df.loc[mask, "SOURCE_PLAYER_ID"] = new_ids

            # Save back to file
            df.to_parquet(data_file, index=False, compression="snappy")

            print(f"  ✓ Fixed {none_count:,} SOURCE_PLAYER_IDs")
        else:
            print(f"  [DRY RUN] Would fix {none_count:,} SOURCE_PLAYER_IDs")

        # Show sample generated IDs
        print("  Sample generated IDs:")
        for i, (name, new_id) in enumerate(
            zip(df[mask]["PLAYER_NAME_RAW"].head(5), new_ids.head(5), strict=False), 1
        ):
            print(f"    {i}. {name} → {new_id}")

        total_records += len(df)
        total_fixed += none_count

    print(f"\n{'-'*80}")
    print("SUMMARY:")
    print(f"  Total records: {total_records:,}")
    print(f"  Total fixed: {total_fixed:,}")
    print(f"  Fix rate: {total_fixed/total_records*100:.1f}%")


def main():
    """Main execution."""
    print("=" * 80)
    print("FIX CEBL/NBL SOURCE_PLAYER_ID ISSUES")
    print("=" * 80)

    # Dry run first
    print("\n" + "=" * 80)
    print("DRY RUN MODE (no files modified)")
    print("=" * 80)

    fix_league_player_ids("CEBL", dry_run=True)
    fix_league_player_ids("NBL", dry_run=True)

    # Ask for confirmation
    print("\n" + "=" * 80)
    print("CONFIRMATION")
    print("=" * 80)
    response = input("Apply fixes? (yes/no): ").strip().lower()

    if response != "yes":
        print("Aborted. No changes made.")
        return 0

    # Apply fixes
    print("\n" + "=" * 80)
    print("APPLYING FIXES")
    print("=" * 80)

    fix_league_player_ids("CEBL", dry_run=False)
    fix_league_player_ids("NBL", dry_run=False)

    print("\n" + "=" * 80)
    print("FIX COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Re-run multi_gate_player_matcher.py to regenerate edges")
    print("2. Re-run build_unified_career_gold_chunked.py to rebuild gold dataset")

    return 0


if __name__ == "__main__":
    sys.exit(main())
