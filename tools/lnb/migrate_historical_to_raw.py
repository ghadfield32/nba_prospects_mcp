#!/usr/bin/env python3
"""Migrate LNB Historical Data to Raw Format

Converts the 2025-2026 historical format (consolidated parquet files)
to the raw format (per-game parquet files) expected by create_normalized_tables.py

Historical format: data/lnb/historical/YYYY-YYYY/pbp_events.parquet (all games in one file)
Raw format: data/raw/lnb/pbp/season=YYYY-YYYY/game_id=<uuid>.parquet (one file per game)

Usage:
    python tools/lnb/migrate_historical_to_raw.py
    python tools/lnb/migrate_historical_to_raw.py --season 2025-2026
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

# Division to League mapping
DIVISION_TO_LEAGUE = {
    "1": "LNB_PROA",
    "2": "LNB_ELITE2",
    "3": "LNB_ESPOIRS_ELITE",
    "4": "LNB_ESPOIRS_PROB",
}

# Directories
HISTORICAL_DIR = Path("data/lnb/historical")
RAW_DIR = Path("data/raw/lnb")
PBP_DIR = RAW_DIR / "pbp"
SHOTS_DIR = RAW_DIR / "shots"


def load_game_league_mapping(season: str) -> dict[str, str]:
    """Load fixtures and build game_id -> league mapping

    Args:
        season: Season string (e.g., "2025-2026")

    Returns:
        Dict mapping game_id (fixture_uuid) to league name
    """
    game_to_league: dict[str, str] = {}
    season_dir = HISTORICAL_DIR / season

    if not season_dir.exists():
        return game_to_league

    # Look for fixtures files
    fixtures_files = list(season_dir.glob("*fixtures*.parquet"))

    for fixtures_file in fixtures_files:
        try:
            fixtures_df = pd.read_parquet(fixtures_file)

            # Check for division column
            if "division" not in fixtures_df.columns:
                continue

            # Map each game to its league
            id_col = "fixture_uuid" if "fixture_uuid" in fixtures_df.columns else "GAME_ID"

            for _, row in fixtures_df.iterrows():
                game_id = str(row[id_col])
                division = str(row.get("division", "1"))
                league = DIVISION_TO_LEAGUE.get(division, "LNB_PROA")
                game_to_league[game_id] = league

            print(f"  [INFO] Loaded {len(game_to_league)} game->league mappings")

        except Exception as e:
            print(f"  [WARN] Failed to load {fixtures_file}: {e}")

    return game_to_league


def migrate_pbp(season: str) -> int:
    """Migrate PBP data from historical to raw format

    Returns number of games migrated
    """
    season_dir = HISTORICAL_DIR / season

    if not season_dir.exists():
        print(f"  [SKIP] No directory at {season_dir}")
        return 0

    # Find all PBP files (consolidated or per-division)
    pbp_files = list(season_dir.glob("pbp_events*.parquet"))
    if not pbp_files:
        print(f"  [SKIP] No PBP files in {season_dir}")
        return 0

    # Read and combine all PBP files
    dfs = []
    for pbp_file in pbp_files:
        df = pd.read_parquet(pbp_file)
        # Extract division from filename if present (e.g., pbp_events_div2.parquet)
        if "_div" in pbp_file.stem:
            div_num = pbp_file.stem.split("_div")[-1]
            df["_division"] = div_num
        dfs.append(df)
        print(f"  [READ] {len(df)} PBP events from {pbp_file.name}")

    hist_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    print(f"  [TOTAL] {len(hist_df)} PBP events combined")

    # Get unique games
    game_col = "fixture_uuid" if "fixture_uuid" in hist_df.columns else "GAME_ID"
    games = hist_df[game_col].unique()
    print(f"  [INFO] Found {len(games)} unique games")

    # Load game -> league mapping
    game_to_league = load_game_league_mapping(season)

    # Create output directory
    out_dir = PBP_DIR / f"season={season}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Column mapping: historical -> raw
    # Supports both old LNB API format and new Atrium API format
    column_map = {
        # Common
        "fixture_uuid": "GAME_ID",
        "event_id": "EVENT_ID",
        "event_type": "EVENT_TYPE",
        "x": "X_COORD",
        "y": "Y_COORD",
        # Old format
        "quarter": "PERIOD_ID",
        "clock": "CLOCK",
        "event_description": "DESCRIPTION",
        "team": "TEAM_ID",
        "player": "PLAYER_NAME",
        "score_home": "HOME_SCORE",
        "score_away": "AWAY_SCORE",
        # New Atrium format
        "period_id": "PERIOD_ID",
        "clock_iso": "CLOCK",
        "description": "DESCRIPTION",
        "team_id": "TEAM_ID",
        "player_id": "PLAYER_ID",
        "player_name": "PLAYER_NAME",
        "player_bib": "PLAYER_JERSEY",
        "event_sub_type": "EVENT_SUBTYPE",
        "success": "SUCCESS",
        "home_score": "HOME_SCORE",
        "away_score": "AWAY_SCORE",
    }

    # Process each game
    migrated = 0
    for game_id in games:
        game_df = hist_df[hist_df[game_col] == game_id].copy()

        # Rename columns
        game_df = game_df.rename(columns=column_map)

        # Add missing required columns
        if "EVENT_SUBTYPE" not in game_df.columns:
            game_df["EVENT_SUBTYPE"] = ""
        if "PLAYER_ID" not in game_df.columns:
            game_df["PLAYER_ID"] = ""  # Will need to be populated from roster data
        if "PLAYER_JERSEY" not in game_df.columns:
            game_df["PLAYER_JERSEY"] = ""
        if "SUCCESS" not in game_df.columns:
            game_df["SUCCESS"] = False
        if "LEAGUE" not in game_df.columns:
            # Get league from _division column or mapping
            if "_division" in hist_df.columns:
                game_rows = hist_df[hist_df[game_col] == game_id]
                if len(game_rows) > 0:
                    game_div = game_rows["_division"].iloc[0]
                    league = DIVISION_TO_LEAGUE.get(str(game_div), "LNB_PROA")
                else:
                    league = "LNB_PROA"
            else:
                league = game_to_league.get(str(game_id), "LNB_PROA")
            game_df["LEAGUE"] = league

        # Reorder columns to match expected schema
        expected_cols = [
            "GAME_ID",
            "EVENT_ID",
            "PERIOD_ID",
            "CLOCK",
            "EVENT_TYPE",
            "EVENT_SUBTYPE",
            "PLAYER_ID",
            "PLAYER_NAME",
            "PLAYER_JERSEY",
            "TEAM_ID",
            "DESCRIPTION",
            "SUCCESS",
            "X_COORD",
            "Y_COORD",
            "HOME_SCORE",
            "AWAY_SCORE",
            "LEAGUE",
        ]

        # Only include columns that exist
        final_cols = [c for c in expected_cols if c in game_df.columns]
        game_df = game_df[final_cols]

        # Save per-game file
        out_file = out_dir / f"game_id={game_id}.parquet"
        game_df.to_parquet(out_file, index=False)
        migrated += 1

    print(f"  [MIGRATED] {migrated} PBP game files to {out_dir}")
    return migrated


def migrate_shots(season: str) -> int:
    """Migrate shots data from historical to raw format

    Returns number of games migrated
    """
    season_dir = HISTORICAL_DIR / season

    if not season_dir.exists():
        print(f"  [SKIP] No directory at {season_dir}")
        return 0

    # Find all shots files (consolidated or per-division)
    shots_files = list(season_dir.glob("shots*.parquet"))
    if not shots_files:
        print(f"  [SKIP] No shots files in {season_dir}")
        return 0

    # Read and combine all shots files
    dfs = []
    for shots_file in shots_files:
        df = pd.read_parquet(shots_file)
        # Extract division from filename if present
        if "_div" in shots_file.stem:
            div_num = shots_file.stem.split("_div")[-1]
            df["_division"] = div_num
        dfs.append(df)
        print(f"  [READ] {len(df)} shots from {shots_file.name}")

    hist_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    print(f"  [TOTAL] {len(hist_df)} shots combined")

    # Get unique games
    game_col = "fixture_uuid" if "fixture_uuid" in hist_df.columns else "GAME_ID"
    games = hist_df[game_col].unique()
    print(f"  [INFO] Found {len(games)} unique games")

    # Load game -> league mapping
    game_to_league = load_game_league_mapping(season)

    # Create output directory
    out_dir = SHOTS_DIR / f"season={season}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Column mapping: historical -> raw
    # Supports both old LNB API format and new Atrium API format
    column_map = {
        # Common
        "fixture_uuid": "GAME_ID",
        "event_id": "EVENT_ID",
        "shot_type": "SHOT_TYPE",
        "x": "X_COORD",
        "y": "Y_COORD",
        "made": "SUCCESS",
        # Old format
        "shot_id": "EVENT_ID",
        "quarter": "PERIOD_ID",
        "clock": "CLOCK",
        "shot_subtype": "SHOT_SUBTYPE",
        "shot_description": "DESCRIPTION",
        "team": "TEAM_ID",
        "player": "PLAYER_NAME",
        "success": "SUCCESS",
        # New Atrium format
        "period_id": "PERIOD_ID",
        "clock_seconds": "CLOCK",
        "team_id": "TEAM_ID",
        "player_id": "PLAYER_ID",
        "player_name": "PLAYER_NAME",
        "home_score": "HOME_SCORE",
        "away_score": "AWAY_SCORE",
    }

    # Process each game
    migrated = 0
    for game_id in games:
        game_df = hist_df[hist_df[game_col] == game_id].copy()

        # Rename columns
        game_df = game_df.rename(columns=column_map)

        # Add missing required columns
        if "EVENT_ID" not in game_df.columns:
            game_df["EVENT_ID"] = range(len(game_df))  # Generate if missing
        if "SHOT_SUBTYPE" not in game_df.columns:
            game_df["SHOT_SUBTYPE"] = ""
        if "DESCRIPTION" not in game_df.columns:
            # Generate description from shot type
            game_df["DESCRIPTION"] = game_df.apply(
                lambda r: f"{r.get('SHOT_TYPE', '')} shot by {r.get('PLAYER_NAME', '')}", axis=1
            )
        if "PLAYER_ID" not in game_df.columns:
            game_df["PLAYER_ID"] = ""
        if "PLAYER_JERSEY" not in game_df.columns:
            game_df["PLAYER_JERSEY"] = ""
        if "SUCCESS_STRING" not in game_df.columns:
            game_df["SUCCESS_STRING"] = game_df["SUCCESS"].apply(
                lambda x: "made" if x else "missed"
            )
        if "LEAGUE" not in game_df.columns:
            # Get league from _division column or mapping
            if "_division" in hist_df.columns:
                game_rows = hist_df[hist_df[game_col] == game_id]
                if len(game_rows) > 0:
                    game_div = game_rows["_division"].iloc[0]
                    league = DIVISION_TO_LEAGUE.get(str(game_div), "LNB_PROA")
                else:
                    league = "LNB_PROA"
            else:
                league = game_to_league.get(str(game_id), "LNB_PROA")
            game_df["LEAGUE"] = league

        # Reorder columns to match expected schema
        expected_cols = [
            "GAME_ID",
            "EVENT_ID",
            "PERIOD_ID",
            "CLOCK",
            "SHOT_TYPE",
            "SHOT_SUBTYPE",
            "PLAYER_ID",
            "PLAYER_NAME",
            "PLAYER_JERSEY",
            "TEAM_ID",
            "DESCRIPTION",
            "SUCCESS",
            "SUCCESS_STRING",
            "X_COORD",
            "Y_COORD",
            "LEAGUE",
        ]

        # Only include columns that exist
        final_cols = [c for c in expected_cols if c in game_df.columns]
        game_df = game_df[final_cols]

        # Save per-game file
        out_file = out_dir / f"game_id={game_id}.parquet"
        game_df.to_parquet(out_file, index=False)
        migrated += 1

    print(f"  [MIGRATED] {migrated} shots game files to {out_dir}")
    return migrated


def main():
    parser = argparse.ArgumentParser(description="Migrate LNB historical data to raw format")
    parser.add_argument(
        "--season", type=str, default="2025-2026", help="Season to migrate (default: 2025-2026)"
    )

    args = parser.parse_args()

    print(f"{'='*70}")
    print("  LNB DATA MIGRATION: Historical -> Raw Format")
    print(f"{'='*70}\n")

    print(f"Season: {args.season}")
    print(f"From: {HISTORICAL_DIR / args.season}")
    print(f"To: {RAW_DIR}\n")

    # Migrate PBP
    print("[PBP Migration]")
    pbp_count = migrate_pbp(args.season)

    # Migrate Shots
    print("\n[Shots Migration]")
    shots_count = migrate_shots(args.season)

    print(f"\n{'='*70}")
    print("  MIGRATION COMPLETE")
    print(f"{'='*70}\n")

    print(f"PBP games migrated: {pbp_count}")
    print(f"Shots games migrated: {shots_count}")

    if pbp_count > 0:
        print(f"\nNow run: python tools/lnb/create_normalized_tables.py --season {args.season}")


if __name__ == "__main__":
    main()
