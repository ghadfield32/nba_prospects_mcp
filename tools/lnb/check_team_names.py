#!/usr/bin/env python3
"""Check team names in 'duplicate' files to determine if same/different games"""

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
# FILES TO CHECK
# ==============================================================================

FILES_TO_CHECK = [
    (
        "data/normalized/lnb/team_game/season=2021-2022/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "2021-2022",
    ),
    (
        "data/normalized/lnb/team_game/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet",
        "2023-2024",
    ),
    (
        "data/normalized/lnb/team_game/season=2022-2023/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "2022-2023",
    ),
    (
        "data/normalized/lnb/team_game/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet",
        "2023-2024",
    ),
]


def check_teams(file_path: str, folder_season: str) -> None:
    """Check team names and scores in file

    Args:
        file_path: Path to team_game parquet file
        folder_season: Season from folder name
    """
    file = Path(file_path)

    if not file.exists():
        print(f"❌ File not found: {file.name}")
        return

    try:
        df = pd.read_parquet(file)

        print(f"\n{'='*80}")
        print(f"File: {file.name}")
        print(f"Folder Season: {folder_season}")
        print(f"{'='*80}")

        # Extract key fields
        if len(df) >= 2:
            team1 = df.iloc[0]
            team2 = df.iloc[1]

            print("\nTeam 1:")
            print(f"  Name: {team1.get('TEAM_NAME', 'N/A')}")
            print(f"  Team ID: {team1.get('TEAM_ID', 'N/A')}")
            print(f"  Points: {team1.get('PTS', 'N/A')}")
            print(f"  FG%: {team1.get('FG_PCT', 'N/A')}")

            print("\nTeam 2:")
            print(f"  Name: {team2.get('TEAM_NAME', 'N/A')}")
            print(f"  Team ID: {team2.get('TEAM_ID', 'N/A')}")
            print(f"  Points: {team2.get('PTS', 'N/A')}")
            print(f"  FG%: {team2.get('FG_PCT', 'N/A')}")

            print("\nGame Info:")
            print(f"  Game ID: {team1.get('GAME_ID', 'N/A')}")
            print(f"  Season (in data): {team1.get('SEASON', 'N/A')}")

        print(f"\nAll Columns: {df.columns.tolist()}")

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    """Main checking workflow"""

    print(f"{'#'*80}")
    print("# CHECKING TEAM NAMES IN 'DUPLICATE' FILES")
    print("# To determine if these are different games or data errors")
    print(f"{'#'*80}\n")

    # Group by game ID
    print(f"\n{'#'*80}")
    print("# GAME ID: 7d414bce-f5da-11eb-b3fd-a23ac5ab90da")
    print(f"{'#'*80}")

    check_teams(FILES_TO_CHECK[0][0], FILES_TO_CHECK[0][1])
    check_teams(FILES_TO_CHECK[1][0], FILES_TO_CHECK[1][1])

    print(f"\n\n{'#'*80}")
    print("# GAME ID: cc7e470e-11a0-11ed-8ef5-8d12cdc95909")
    print(f"{'#'*80}")

    check_teams(FILES_TO_CHECK[2][0], FILES_TO_CHECK[2][1])
    check_teams(FILES_TO_CHECK[3][0], FILES_TO_CHECK[3][1])

    print(f"\n\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
