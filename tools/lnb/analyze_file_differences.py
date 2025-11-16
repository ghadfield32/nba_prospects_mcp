#!/usr/bin/env python3
"""Analyze differences between 'duplicate' files to understand discrepancies

This script investigates WHAT differs between files with same game IDs
to determine if they represent:
1. Different games (same teams, different competitions/dates)
2. Data quality updates
3. Different roster configurations
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

# Files to compare (from verification results)
FILE_PAIRS = [
    (
        "data/normalized/lnb/player_game/season=2021-2022/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "data/normalized/lnb/player_game/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "7d414bce... (2021 vs 2023)",
    ),
    (
        "data/normalized/lnb/player_game/season=2022-2023/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "data/normalized/lnb/player_game/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "cc7e470e... (2022 vs 2023)",
    ),
]

# ==============================================================================
# ANALYSIS FUNCTIONS
# ==============================================================================


def analyze_differences(file1_path: str, file2_path: str, label: str) -> dict:
    """Analyze detailed differences between two parquet files

    Args:
        file1_path: First file
        file2_path: Second file
        label: Description label

    Returns:
        Dict with detailed analysis
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING: {label}")
    print(f"{'='*80}\n")

    file1 = Path(file1_path)
    file2 = Path(file2_path)

    if not file1.exists() or not file2.exists():
        print("❌ One or both files missing")
        return {}

    try:
        df1 = pd.read_parquet(file1)
        df2 = pd.read_parquet(file2)

        print(f"File 1: {file1.name}")
        print(f"  Rows: {len(df1)}, Columns: {len(df1.columns)}")
        print(f"  Shape: {df1.shape}")

        print(f"\nFile 2: {file2.name}")
        print(f"  Rows: {len(df2)}, Columns: {len(df2.columns)}")
        print(f"  Shape: {df2.shape}")

        # Compare key fields
        print("\n--- KEY FIELD COMPARISON ---")

        key_fields = ["GAME_ID", "SEASON", "PLAYER_ID", "PLAYER_NAME", "PTS", "MIN"]

        for field in key_fields:
            if field in df1.columns and field in df2.columns:
                val1 = (
                    df1[field].iloc[0]
                    if len(df1) > 0 and field in ["GAME_ID", "SEASON"]
                    else df1[field].unique()
                )
                val2 = (
                    df2[field].iloc[0]
                    if len(df2) > 0 and field in ["GAME_ID", "SEASON"]
                    else df2[field].unique()
                )

                if field in ["GAME_ID", "SEASON"]:
                    print(f"{field}:")
                    print(f"  File 1: {val1}")
                    print(f"  File 2: {val2}")
                    print(f"  Match: {val1 == val2}")
                else:
                    print(f"{field}: File1={len(val1)} unique, File2={len(val2)} unique")

        # Check if players differ
        print("\n--- PLAYER COMPARISON ---")

        if "PLAYER_ID" in df1.columns and "PLAYER_ID" in df2.columns:
            players1 = set(df1["PLAYER_ID"].dropna())
            players2 = set(df2["PLAYER_ID"].dropna())

            only_in_1 = players1 - players2
            only_in_2 = players2 - players1
            common = players1 & players2

            print(f"Players only in File 1: {len(only_in_1)}")
            if only_in_1:
                print(f"  IDs: {list(only_in_1)[:5]}...")

            print(f"Players only in File 2: {len(only_in_2)}")
            if only_in_2:
                print(f"  IDs: {list(only_in_2)[:5]}...")

            print(f"Common players: {len(common)}")

        # Check if stats differ for common players
        if "PLAYER_ID" in df1.columns and "PLAYER_ID" in df2.columns:
            print("\n--- STATS COMPARISON (Common Players) ---")

            common_players = set(df1["PLAYER_ID"].dropna()) & set(df2["PLAYER_ID"].dropna())

            if common_players:
                sample_player = list(common_players)[0]
                player1_stats = df1[df1["PLAYER_ID"] == sample_player].iloc[0]
                player2_stats = df2[df2["PLAYER_ID"] == sample_player].iloc[0]

                print(
                    f"\nSample player: {sample_player} ({player1_stats.get('PLAYER_NAME', 'Unknown')})"
                )

                stat_cols = ["PTS", "REB", "AST", "MIN", "FGM", "FGA"]
                for col in stat_cols:
                    if col in player1_stats and col in player2_stats:
                        val1 = player1_stats[col]
                        val2 = player2_stats[col]
                        match = "✅" if val1 == val2 else "❌"
                        print(f"  {col}: {val1} vs {val2} {match}")

        # Show first few rows
        print("\n--- FIRST 3 ROWS FILE 1 ---")
        print(
            df1[["PLAYER_NAME", "PTS", "REB", "AST", "MIN"]].head(3).to_string()
            if "PLAYER_NAME" in df1.columns
            else df1.head(3).to_string()
        )

        print("\n--- FIRST 3 ROWS FILE 2 ---")
        print(
            df2[["PLAYER_NAME", "PTS", "REB", "AST", "MIN"]].head(3).to_string()
            if "PLAYER_NAME" in df2.columns
            else df2.head(3).to_string()
        )

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()

    return {}


def main():
    """Main analysis workflow"""

    print(f"{'#'*80}")
    print("# ANALYZING 'DUPLICATE' FILE DIFFERENCES")
    print("# Purpose: Understand why files with same game IDs differ")
    print(f"{'#'*80}\n")

    for file1, file2, label in FILE_PAIRS:
        analyze_differences(file1, file2, label)

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
