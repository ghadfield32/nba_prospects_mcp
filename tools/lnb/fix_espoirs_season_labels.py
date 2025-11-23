#!/usr/bin/env python3
"""Fix Espoirs season labels that are off by 1 year

Espoirs games have game dates from 2024-2025 season but are labeled as "2023-2024"
This script updates SEASON column values for Espoirs leagues only.

Expected fixes:
- "2023-2024" -> "2024-2025" (games from Sep 2024 - May 2025)
- "2024-2025" -> "2025-2026" (games from Sep 2025 - May 2026)
"""

from __future__ import annotations

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

import pandas as pd

print("=" * 80)
print("  FIX ESPOIRS SEASON LABELS")
print("=" * 80)

# Find all parquet files
ROOT = Path("data/raw/lnb")
PBP_FILES = list(ROOT.glob("pbp/**/*.parquet"))
SHOTS_FILES = list(ROOT.glob("shots/**/*.parquet"))
ALL_FILES = PBP_FILES + SHOTS_FILES

print(f"\nFound {len(PBP_FILES)} PBP files")
print(f"Found {len(SHOTS_FILES)} shots files")
print(f"Total: {len(ALL_FILES)} files to check")


def fix_season_label(p: Path) -> tuple[bool, str | None, str | None]:
    """Fix season label in a parquet file

    Returns:
        (changed, old_season, new_season)
    """
    try:
        df = pd.read_parquet(p)

        # Check if this is an Espoirs file
        if "LEAGUE" not in df.columns or len(df) == 0:
            return (False, None, None)

        league_val = df["LEAGUE"].iloc[0]
        if not league_val.startswith("LNB_ESPOIRS"):
            return (False, None, None)

        # Check if SEASON column exists
        if "SEASON" not in df.columns:
            return (False, None, None)

        old_season = df["SEASON"].iloc[0]

        # Parse and increment season
        try:
            y1, y2 = old_season.split("-")
            new_season = f"{int(y1)+1}-{int(y2)+1}"
        except ValueError:
            print(f"  [WARN] Could not parse season '{old_season}' in {p.name}")
            return (False, None, None)

        # Update and save
        df["SEASON"] = new_season
        df.to_parquet(p, index=False)

        return (True, old_season, new_season)

    except Exception as e:
        print(f"  [ERROR] {p.name}: {str(e)[:50]}")
        return (False, None, None)


# Process all files
print(f"\n{'-' * 80}")
print("PROCESSING FILES")
print(f"{'-' * 80}")

fixed_count = 0
season_changes = {}

for i, p in enumerate(ALL_FILES, 1):
    if i % 100 == 0:
        print(f"  Progress: {i}/{len(ALL_FILES)} files processed...")

    changed, old_season, new_season = fix_season_label(p)

    if changed:
        fixed_count += 1
        change_key = f"{old_season} -> {new_season}"
        season_changes[change_key] = season_changes.get(change_key, 0) + 1

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print(f"{'=' * 80}")

print(f"\nTotal files processed: {len(ALL_FILES)}")
print(f"Espoirs files updated: {fixed_count}")

if season_changes:
    print("\nSeason label changes:")
    for change, count in sorted(season_changes.items()):
        print(f"  {change}: {count} files")
else:
    print("\nNo Espoirs files found or no changes needed")

print(f"\n{'=' * 80}")
print("COMPLETE")
print(f"{'=' * 80}\n")
