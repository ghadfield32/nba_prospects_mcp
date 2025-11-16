#!/usr/bin/env python3
"""Analyze game season assignments - Check if games are correctly partitioned

Purpose:
    - Read SEASON and GAME_DATE columns from parquet files
    - Identify if games are duplicated across season folders
    - Determine the TRUE season for each game
    - Find misassigned or duplicate games

This addresses the finding that the same game UUIDs appear in multiple season folders.
"""

from __future__ import annotations

import io
import sys
from collections import defaultdict
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_ROOT = Path("data")
NORMALIZED_ROOT = DATA_ROOT / "normalized" / "lnb"

SEASONS_TO_ANALYZE = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]

# ==============================================================================
# ANALYSIS FUNCTIONS
# ==============================================================================


def read_game_metadata(file_path: Path) -> dict | None:
    """Read key metadata from a parquet file

    Args:
        file_path: Path to parquet file

    Returns:
        Dict with game metadata or None if error
    """
    try:
        df = pd.read_parquet(file_path)

        if len(df) == 0:
            return None

        # Get first row (all rows should have same game metadata)
        first_row = df.iloc[0]

        metadata = {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "rows": len(df),
            "game_id": first_row.get("GAME_ID"),
            "season_in_data": first_row.get("SEASON"),
            "game_date": first_row.get("GAME_DATE"),
            "home_team": first_row.get("HOME_TEAM_NAME") or first_row.get("TEAM_NAME"),
            "away_team": first_row.get("AWAY_TEAM_NAME"),
        }

        # Also check column names to see if SEASON or GAME_DATE exist
        metadata["has_season_column"] = "SEASON" in df.columns
        metadata["has_game_date_column"] = "GAME_DATE" in df.columns

        return metadata

    except Exception as e:
        print(f"ERROR reading {file_path.name}: {e}")
        return None


def analyze_season_assignments(dataset_name: str) -> dict:
    """Analyze how games are assigned across season folders

    Args:
        dataset_name: "player_game" or "team_game"

    Returns:
        Dict with analysis results
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING SEASON ASSIGNMENTS: {dataset_name}")
    print(f"{'='*80}\n")

    # Track game IDs across all seasons
    game_id_to_folders = defaultdict(list)
    folder_to_games = {}

    # Collect all games from all season folders
    for season in SEASONS_TO_ANALYZE:
        season_dir = NORMALIZED_ROOT / dataset_name / f"season={season}"

        if not season_dir.exists():
            print(f"❌ {season}: Directory does not exist")
            continue

        parquet_files = sorted(season_dir.glob("*.parquet"))
        folder_to_games[season] = []

        print(f"📁 {season}: {len(parquet_files)} files")

        for file_path in parquet_files:
            metadata = read_game_metadata(file_path)

            if metadata:
                folder_to_games[season].append(metadata)

                game_id = metadata["game_id"]
                if game_id:
                    game_id_to_folders[game_id].append(
                        {
                            "folder_season": season,
                            "data_season": metadata["season_in_data"],
                            "game_date": metadata["game_date"],
                            "file_name": metadata["file_name"],
                        }
                    )

    # Identify duplicates and misassignments
    print(f"\n{'='*80}")
    print("DUPLICATE & MISASSIGNMENT DETECTION")
    print(f"{'='*80}\n")

    duplicates = []
    misassignments = []
    correct_assignments = []

    for game_id, folders in game_id_to_folders.items():
        if len(folders) > 1:
            # Game appears in multiple season folders - DUPLICATE
            duplicates.append(
                {
                    "game_id": game_id,
                    "appears_in": [f["folder_season"] for f in folders],
                    "data_season": folders[0]["data_season"],
                    "game_date": folders[0]["game_date"],
                }
            )

            print(f"🔴 DUPLICATE: {game_id}")
            print(f"   Appears in folders: {', '.join([f['folder_season'] for f in folders])}")
            print(f"   Data says season: {folders[0]['data_season']}")
            print(f"   Game date: {folders[0]['game_date']}")
            print()

        else:
            # Game appears in only one folder - check if correctly assigned
            folder_info = folders[0]
            folder_season = folder_info["folder_season"]
            data_season = folder_info["data_season"]

            if data_season and data_season != folder_season:
                # Season mismatch - MISASSIGNMENT
                misassignments.append(
                    {
                        "game_id": game_id,
                        "folder_season": folder_season,
                        "data_season": data_season,
                        "game_date": folder_info["game_date"],
                    }
                )

                print(f"🟡 MISASSIGNMENT: {game_id}")
                print(f"   In folder: {folder_season}")
                print(f"   Data says: {data_season}")
                print(f"   Game date: {folder_info['game_date']}")
                print()

            else:
                # Correctly assigned
                correct_assignments.append(
                    {
                        "game_id": game_id,
                        "season": folder_season,
                        "game_date": folder_info["game_date"],
                    }
                )

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY FOR {dataset_name}")
    print(f"{'='*80}")
    print(f"Total unique games: {len(game_id_to_folders)}")
    print(f"Duplicate games (appear in multiple folders): {len(duplicates)}")
    print(f"Misassigned games (folder ≠ data): {len(misassignments)}")
    print(f"Correctly assigned games: {len(correct_assignments)}")
    print()

    # Show breakdown by season folder
    print("Games per season folder:")
    for season in SEASONS_TO_ANALYZE:
        if season in folder_to_games:
            print(f"  {season}: {len(folder_to_games[season])} files")

    return {
        "dataset": dataset_name,
        "total_unique_games": len(game_id_to_folders),
        "duplicates": duplicates,
        "misassignments": misassignments,
        "correct_assignments": correct_assignments,
        "folder_to_games": folder_to_games,
    }


def check_game_date_patterns(dataset_name: str, season: str) -> None:
    """Check a specific season's game dates to verify correctness

    Args:
        dataset_name: "player_game" or "team_game"
        season: Season folder to check
    """
    season_dir = NORMALIZED_ROOT / dataset_name / f"season={season}"

    if not season_dir.exists():
        print(f"Season {season} does not exist")
        return

    print(f"\n{'='*80}")
    print(f"GAME DATE ANALYSIS: {dataset_name} / {season}")
    print(f"{'='*80}\n")

    parquet_files = sorted(season_dir.glob("*.parquet"))

    for file_path in parquet_files:
        metadata = read_game_metadata(file_path)

        if metadata:
            print(f"File: {metadata['file_name']}")
            print(f"  Game ID: {metadata['game_id']}")
            print(f"  Season in data: {metadata['season_in_data']}")
            print(f"  Game date: {metadata['game_date']}")
            print(f"  Has SEASON column: {metadata['has_season_column']}")
            print(f"  Has GAME_DATE column: {metadata['has_game_date_column']}")
            print()


def main():
    """Main analysis workflow"""

    print(f"{'#'*80}")
    print("# GAME SEASON ASSIGNMENT ANALYSIS")
    print("# Investigating duplicate games and season misassignments")
    print(f"{'#'*80}\n")

    # Analyze both datasets
    player_game_results = analyze_season_assignments("player_game")
    team_game_results = analyze_season_assignments("team_game")

    # Deep dive into problematic seasons
    print(f"\n\n{'#'*80}")
    print("# DEEP DIVE: 2021-2022 SEASON")
    print(f"{'#'*80}")
    check_game_date_patterns("player_game", "2021-2022")

    print(f"\n\n{'#'*80}")
    print("# DEEP DIVE: 2022-2023 SEASON")
    print(f"{'#'*80}")
    check_game_date_patterns("player_game", "2022-2023")

    # Final summary
    print(f"\n\n{'#'*80}")
    print("# FINAL SUMMARY")
    print(f"{'#'*80}\n")

    print("PLAYER_GAME:")
    print(f"  Total unique games: {player_game_results['total_unique_games']}")
    print(f"  Duplicates: {len(player_game_results['duplicates'])}")
    print(f"  Misassignments: {len(player_game_results['misassignments'])}")
    print()

    print("TEAM_GAME:")
    print(f"  Total unique games: {team_game_results['total_unique_games']}")
    print(f"  Duplicates: {len(team_game_results['duplicates'])}")
    print(f"  Misassignments: {len(team_game_results['misassignments'])}")
    print()

    # Critical finding
    if player_game_results["duplicates"]:
        print("⚠️ CRITICAL FINDING:")
        print("   The same games appear in multiple season folders!")
        print("   This explains why 2021-2022 and 2022-2023 only show 1 game each.")
        print("   Those games are DUPLICATED in the 2023-2024 folder.")
        print("   The actual unique game count across all seasons is:")
        print(
            f"   {player_game_results['total_unique_games']} games (not {sum(len(v) for v in player_game_results['folder_to_games'].values())} files)"
        )


if __name__ == "__main__":
    main()
