#!/usr/bin/env python
"""LNB Backup to Game Index Converter

Converts existing LNB backup parquet data to standard game index format.
LNB backups exist in data/backups/lnb/ with game indexes and detailed data.

Usage:
    python scripts/lnb_backup_to_index.py
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, "src")

import pandas as pd

DATA_DIR = Path("data")
BACKUP_DIR = DATA_DIR / "backups" / "lnb"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
GAME_INDEX_DIR.mkdir(parents=True, exist_ok=True)


def find_latest_backup():
    """Find the most recent LNB backup directory."""
    if not BACKUP_DIR.exists():
        return None

    backup_dirs = sorted(BACKUP_DIR.glob("*"))
    if not backup_dirs:
        return None

    return backup_dirs[-1]  # Latest timestamp


def process_lnb_backup(backup_dir: Path):
    """Process LNB backup game index."""
    game_index_path = backup_dir / "lnb_game_index.parquet"

    if not game_index_path.exists():
        print(f"Game index not found: {game_index_path}")
        return

    print(f"Loading LNB game index from {game_index_path}")
    df = pd.read_parquet(game_index_path)

    print(f"Loaded {len(df)} games")
    print(f"Columns: {list(df.columns)}")

    # Map columns to standard format
    column_mapping = {
        "GAME_ID": "GAME_ID",
        "game_id": "GAME_ID",
        "GAME_DATE": "GAME_DATE",
        "game_date": "GAME_DATE",
        "date": "GAME_DATE",
        "HOME_TEAM": "HOME_TEAM",
        "home_team": "HOME_TEAM",
        "AWAY_TEAM": "AWAY_TEAM",
        "away_team": "AWAY_TEAM",
        "HOME_SCORE": "HOME_SCORE",
        "home_score": "HOME_SCORE",
        "AWAY_SCORE": "AWAY_SCORE",
        "away_score": "AWAY_SCORE",
        "SEASON": "SEASON",
        "season": "SEASON",
    }

    # Rename columns
    renamed = {}
    for old, new in column_mapping.items():
        if old in df.columns and new not in renamed:
            renamed[old] = new

    df = df.rename(columns=renamed)

    # Add league
    df["LEAGUE"] = "LNB"

    # Group by season and write separate files
    if "SEASON" in df.columns:
        for season in df["SEASON"].unique():
            season_df = df[df["SEASON"] == season].copy()

            # Format season for filename
            season_str = str(season).replace("-", "_").replace("/", "_")
            filename = f"LNB_{season_str}.csv"
            filepath = GAME_INDEX_DIR / filename

            # Ensure required columns
            required_cols = [
                "LEAGUE",
                "SEASON",
                "GAME_ID",
                "GAME_DATE",
                "HOME_TEAM",
                "AWAY_TEAM",
                "HOME_SCORE",
                "AWAY_SCORE",
            ]
            for col in required_cols:
                if col not in season_df.columns:
                    season_df[col] = None

            # Add team IDs if missing
            if "HOME_TEAM_ID" not in season_df.columns:
                season_df["HOME_TEAM_ID"] = season_df["HOME_TEAM"]
            if "AWAY_TEAM_ID" not in season_df.columns:
                season_df["AWAY_TEAM_ID"] = season_df["AWAY_TEAM"]

            season_df.to_csv(filepath, index=False)
            print(f"Wrote {len(season_df)} games to {filepath}")
    else:
        # No season column - write all to one file
        df.to_csv(GAME_INDEX_DIR / "LNB_all.csv", index=False)
        print(f"Wrote {len(df)} games to LNB_all.csv")


def main():
    print("=" * 70)
    print("LNB BACKUP TO GAME INDEX CONVERTER")
    print("=" * 70)
    print()

    if not BACKUP_DIR.exists():
        print(f"LNB backup directory not found: {BACKUP_DIR}")
        return

    # Find latest backup
    latest_backup = find_latest_backup()
    if not latest_backup:
        print("No LNB backups found")
        return

    print(f"Using latest backup: {latest_backup.name}")
    print()

    # List contents
    print("Backup contents:")
    for item in latest_backup.iterdir():
        if item.is_file():
            print(f"  - {item.name}")
        else:
            print(f"  - {item.name}/")
    print()

    # Process game index
    process_lnb_backup(latest_backup)

    print()
    print("Done!")


if __name__ == "__main__":
    main()
