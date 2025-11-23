#!/usr/bin/env python3
"""Identify and optionally delete Espoirs files with incorrect LEAGUE values

This script finds Espoirs ELITE and Espoirs PROB games that have the wrong
LEAGUE column value due to being ingested before the fix.

Expected values:
- Espoirs ELITE games should have LEAGUE='LNB_ESPOIRS_ELITE'
- Espoirs PROB games should have LEAGUE='LNB_ESPOIRS_PROB'

Files with LEAGUE='LNB_PROA' need to be deleted and re-ingested.
"""

from __future__ import annotations

import argparse
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


def check_league_value(parquet_file: Path) -> str | None:
    """Check LEAGUE column value in a parquet file

    Returns:
        LEAGUE value if file exists and has LEAGUE column, None otherwise
    """
    try:
        df = pd.read_parquet(parquet_file)
        if "LEAGUE" in df.columns and len(df) > 0:
            return df["LEAGUE"].iloc[0]
        return None
    except Exception as e:
        print(f"ERROR reading {parquet_file.name}: {str(e)[:50]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Identify Espoirs files with wrong LEAGUE values")
    parser.add_argument(
        "--delete", action="store_true", help="Delete files with wrong LEAGUE values"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("  IDENTIFY ESPOIRS FILES WITH WRONG LEAGUE VALUES")
    print("=" * 80)

    # Load game index
    INDEX_FILE = Path("data/raw/lnb/lnb_game_index.parquet")
    PBP_DIR = Path("data/raw/lnb/pbp")
    SHOTS_DIR = Path("data/raw/lnb/shots")

    df_index = pd.read_parquet(INDEX_FILE)

    # Get Espoirs games
    espoirs_elite = df_index[df_index["competition"] == "Espoirs ELITE"]["game_id"].tolist()
    espoirs_prob = df_index[df_index["competition"] == "Espoirs PROB"]["game_id"].tolist()

    print(f"\nEspoirs ELITE games in index: {len(espoirs_elite)}")
    print(f"Espoirs PROB games in index: {len(espoirs_prob)}")

    # Check each Espoirs ELITE file
    print(f"\n{'-' * 80}")
    print("CHECKING ESPOIRS ELITE FILES")
    print(f"{'-' * 80}")

    wrong_files_elite_pbp = []
    wrong_files_elite_shots = []

    for game_id in espoirs_elite:
        # Check PBP file
        pbp_files = list(PBP_DIR.rglob(f"*{game_id}*.parquet"))
        if pbp_files:
            pbp_file = pbp_files[0]
            league_val = check_league_value(pbp_file)
            if league_val and league_val != "LNB_ESPOIRS_ELITE":
                wrong_files_elite_pbp.append((pbp_file, league_val))

        # Check shots file
        shots_files = list(SHOTS_DIR.rglob(f"*{game_id}*.parquet"))
        if shots_files:
            shots_file = shots_files[0]
            league_val = check_league_value(shots_file)
            if league_val and league_val != "LNB_ESPOIRS_ELITE":
                wrong_files_elite_shots.append((shots_file, league_val))

    # Check each Espoirs PROB file
    print(f"\n{'-' * 80}")
    print("CHECKING ESPOIRS PROB FILES")
    print(f"{'-' * 80}")

    wrong_files_prob_pbp = []
    wrong_files_prob_shots = []

    for game_id in espoirs_prob:
        # Check PBP file
        pbp_files = list(PBP_DIR.rglob(f"*{game_id}*.parquet"))
        if pbp_files:
            pbp_file = pbp_files[0]
            league_val = check_league_value(pbp_file)
            if league_val and league_val != "LNB_ESPOIRS_PROB":
                wrong_files_prob_pbp.append((pbp_file, league_val))

        # Check shots file
        shots_files = list(SHOTS_DIR.rglob(f"*{game_id}*.parquet"))
        if shots_files:
            shots_file = shots_files[0]
            league_val = check_league_value(shots_file)
            if league_val and league_val != "LNB_ESPOIRS_PROB":
                wrong_files_prob_shots.append((shots_file, league_val))

    # Report findings
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")

    print("\nEspoirs ELITE files with wrong LEAGUE value:")
    print(f"  PBP:   {len(wrong_files_elite_pbp)} files")
    print(f"  Shots: {len(wrong_files_elite_shots)} files")

    print("\nEspoirs PROB files with wrong LEAGUE value:")
    print(f"  PBP:   {len(wrong_files_prob_pbp)} files")
    print(f"  Shots: {len(wrong_files_prob_shots)} files")

    total_wrong = (
        len(wrong_files_elite_pbp)
        + len(wrong_files_elite_shots)
        + len(wrong_files_prob_pbp)
        + len(wrong_files_prob_shots)
    )

    if total_wrong == 0:
        print("\nOK: All Espoirs files have correct LEAGUE values!")
        return

    # Show details
    print(f"\n{'-' * 80}")
    print("DETAILS")
    print(f"{'-' * 80}")

    if wrong_files_elite_pbp:
        print("\nEspoirs ELITE PBP files with wrong LEAGUE:")
        for file, league_val in wrong_files_elite_pbp[:5]:
            print(f"  {file.name[:40]:40} -> LEAGUE='{league_val}'")
        if len(wrong_files_elite_pbp) > 5:
            print(f"  ... and {len(wrong_files_elite_pbp) - 5} more")

    if wrong_files_elite_shots:
        print("\nEspoirs ELITE shots files with wrong LEAGUE:")
        for file, league_val in wrong_files_elite_shots[:5]:
            print(f"  {file.name[:40]:40} -> LEAGUE='{league_val}'")
        if len(wrong_files_elite_shots) > 5:
            print(f"  ... and {len(wrong_files_elite_shots) - 5} more")

    if wrong_files_prob_pbp:
        print("\nEspoirs PROB PBP files with wrong LEAGUE:")
        for file, league_val in wrong_files_prob_pbp[:5]:
            print(f"  {file.name[:40]:40} -> LEAGUE='{league_val}'")
        if len(wrong_files_prob_pbp) > 5:
            print(f"  ... and {len(wrong_files_prob_pbp) - 5} more")

    if wrong_files_prob_shots:
        print("\nEspoirs PROB shots files with wrong LEAGUE:")
        for file, league_val in wrong_files_prob_shots[:5]:
            print(f"  {file.name[:40]:40} -> LEAGUE='{league_val}'")
        if len(wrong_files_prob_shots) > 5:
            print(f"  ... and {len(wrong_files_prob_shots) - 5} more")

    # Handle deletion
    if args.delete or args.dry_run:
        print(f"\n{'-' * 80}")
        if args.dry_run:
            print("DRY RUN: Would delete the following files:")
        else:
            print("DELETING FILES:")
        print(f"{'-' * 80}")

        all_wrong_files = (
            wrong_files_elite_pbp
            + wrong_files_elite_shots
            + wrong_files_prob_pbp
            + wrong_files_prob_shots
        )

        deleted = 0
        for file, league_val in all_wrong_files:
            if args.dry_run:
                print(f"  Would delete: {file.name}")
            else:
                try:
                    file.unlink()
                    deleted += 1
                    print(f"  Deleted: {file.name}")
                except Exception as e:
                    print(f"  ERROR deleting {file.name}: {e}")

        if args.dry_run:
            print(f"\nDRY RUN: Would delete {len(all_wrong_files)} files")
        else:
            print(f"\nDeleted {deleted} / {len(all_wrong_files)} files")
            print(
                f"\nNEXT STEP: Re-run bulk ingestion to fetch these {deleted} games with correct LEAGUE values"
            )

    else:
        print(f"\n{'-' * 80}")
        print("NEXT STEPS")
        print(f"{'-' * 80}")
        print("\n1. Run with --dry-run to see what would be deleted:")
        print("   python tools/lnb/identify_wrong_league_files.py --dry-run")
        print("\n2. Delete the files with wrong LEAGUE values:")
        print("   python tools/lnb/identify_wrong_league_files.py --delete")
        print("\n3. Re-run bulk ingestion to fetch corrected data:")
        print(
            "   python tools/lnb/bulk_ingest_pbp_shots.py --leagues espoirs_elite espoirs_prob --seasons 2023-2024"
        )

    print()


if __name__ == "__main__":
    main()
