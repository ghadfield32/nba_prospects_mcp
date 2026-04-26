#!/usr/bin/env python3
"""OTE Historical Data Backfill Script

Fetches all OTE seasons (2021-2025) to populate missing historical data.

Thompson twins played 2021-2022 season - this data is currently missing!

Usage:
    python scripts/backfill_ote_historical.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Add airflow project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "api" / "src" / "airflow_project"))

from eda.nba_prospects.cbb_data.fetchers import ote


def backfill_ote_season(season: str, dry_run: bool = False) -> pd.DataFrame:
    """Backfill OTE data for a single season.

    Args:
        season: Season string (e.g., "2021-22")
        dry_run: If True, fetch but don't save

    Returns:
        DataFrame with all player-game records for the season
    """
    print(f"\n{'='*80}")
    print(f"BACKFILLING OTE SEASON: {season}")
    print(f"{'='*80}")

    try:
        # Step 1: Fetch schedule
        print("\nStep 1: Fetching schedule...")
        schedule_df = ote.fetch_ote_schedule(season=season)
        print(f"  Found {len(schedule_df)} games")

        if len(schedule_df) == 0:
            print(f"  WARNING: No games found for {season}")
            return pd.DataFrame()

        # Step 2: Fetch box scores for all games
        print(f"\nStep 2: Fetching box scores for {len(schedule_df)} games...")
        all_box_scores = []
        failed_games = []

        for idx, game_id in enumerate(schedule_df["GAME_ID"], 1):
            try:
                print(f"  [{idx}/{len(schedule_df)}] Fetching game {game_id}...", end="")
                box_df = ote.fetch_ote_box_score(game_id)

                if len(box_df) > 0:
                    # Add season and game date metadata
                    box_df["SEASON"] = season
                    box_df["LEAGUE"] = "OTE"

                    # Try to get game date from schedule
                    game_date = (
                        schedule_df[schedule_df["GAME_ID"] == game_id]["GAME_DATE"].iloc[0]
                        if "GAME_DATE" in schedule_df.columns
                        else None
                    )
                    if game_date:
                        box_df["GAME_DATE"] = game_date

                    all_box_scores.append(box_df)
                    print(f" {len(box_df)} players")
                else:
                    print(" No data")
                    failed_games.append(game_id)

            except Exception as e:
                print(f" ERROR: {e}")
                failed_games.append(game_id)
                continue

        if len(failed_games) > 0:
            print(f"\n  WARNING: {len(failed_games)} games failed to fetch")

        if len(all_box_scores) == 0:
            print(f"\n  ERROR: No box scores fetched for {season}")
            return pd.DataFrame()

        # Step 3: Combine all box scores
        print("\nStep 3: Combining box scores...")
        season_df = pd.concat(all_box_scores, ignore_index=True)
        print(f"  Total records: {len(season_df)}")
        print(f"  Unique players: {season_df['PLAYER_ID'].nunique()}")

        # Step 4: Standardize column names
        print("\nStep 4: Standardizing columns...")

        # Rename to canonical schema (OTE fetcher already has most columns right)
        rename_map = {
            "TEAM_ID": "TEAM_KEY",
            "TEAM": "TEAM_NAME_RAW",
        }

        for old_col, new_col in rename_map.items():
            if old_col in season_df.columns and new_col not in season_df.columns:
                season_df.rename(columns={old_col: new_col}, inplace=True)

        # Add NAME_KEY (normalized name) if not present
        if "NAME_KEY" not in season_df.columns:
            import re
            import unicodedata

            def normalize_name(name):
                """Normalize player name for matching."""
                if pd.isna(name) or not name:
                    return ""
                normalized = unicodedata.normalize("NFD", str(name))
                normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
                normalized = re.sub(r"\s+", "_", normalized.strip())
                return normalized

            season_df["NAME_KEY"] = season_df["PLAYER_NAME_RAW"].apply(normalize_name)

        # Ensure required columns exist
        required_cols = [
            "SOURCE_PLAYER_ID",
            "PLAYER_NAME_RAW",
            "NAME_KEY",
            "TEAM_KEY",
            "TEAM_NAME_RAW",
            "GAME_ID",
            "SEASON",
            "LEAGUE",
        ]
        for col in required_cols:
            if col not in season_df.columns:
                print(f"    WARNING: Missing column {col}, adding as None")
                season_df[col] = None

        # Step 5: Save to canonical directory
        if not dry_run:
            print("\nStep 5: Saving to canonical directory...")

            # Create directory path
            output_dir = Path("data/canonical/box_player_game/league=OTE") / f"season={season}"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = output_dir / "data.parquet"

            season_df.to_parquet(output_path, index=False, compression="snappy")

            file_size_kb = output_path.stat().st_size / 1024
            print(f"  ✓ Saved to {output_path}")
            print(f"  File size: {file_size_kb:.1f} KB")
        else:
            print(f"\nStep 5: [DRY RUN] Would save {len(season_df)} records to:")
            print(f"  data/canonical/box_player_game/league=OTE/season={season}/data.parquet")

        # Step 6: Sample data quality check
        print("\nStep 6: Data quality check...")

        # Check for jersey numbers as names
        jersey_mask = season_df["PLAYER_NAME_RAW"].astype(str).str.match(r"^\d+$", na=False)
        jersey_pct = jersey_mask.mean() * 100

        if jersey_pct > 5:
            print(f"  ⚠ WARNING: {jersey_pct:.1f}% of names are jersey numbers!")
        else:
            print(f"  ✓ Clean names: {jersey_pct:.1f}% jersey numbers")

        # Sample players
        print("\n  Sample players:")
        sample_df = (
            season_df.groupby("SOURCE_PLAYER_ID")
            .agg({"PLAYER_NAME_RAW": "first", "GAME_ID": "count", "PTS": "mean"})
            .reset_index()
        )
        sample_df.columns = ["SOURCE_PLAYER_ID", "PLAYER_NAME", "GAMES", "PPG"]
        sample_df = sample_df.sort_values("GAMES", ascending=False).head(10)

        for _idx, row in sample_df.iterrows():
            print(f"    - {row['PLAYER_NAME']}: {row['GAMES']} games, {row['PPG']:.1f} PPG")

        return season_df

    except Exception as e:
        print(f"\n  ERROR: Failed to backfill {season}: {e}")
        import traceback

        traceback.print_exc()
        return pd.DataFrame()


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Backfill OTE historical data")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't save")
    parser.add_argument(
        "--seasons", nargs="+", help="Specific seasons to backfill (e.g., 2021-22 2022-23)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("OTE HISTORICAL DATA BACKFILL")
    print("=" * 80)

    # Default: All OTE seasons
    seasons = args.seasons or [
        "2021-22",  # Thompson twins era!
        "2022-23",
        "2023-24",
        "2024-25",  # Re-fetch to ensure completeness
    ]

    print(f"\nSeasons to backfill: {', '.join(seasons)}")
    if args.dry_run:
        print("MODE: DRY RUN (will not save data)")
    else:
        print("MODE: LIVE (will save to canonical directory)")

    # Confirm before proceeding
    if not args.dry_run:
        response = input("\nProceed with backfill? (yes/no): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return 0

    # Backfill each season
    all_results = {}
    for season in seasons:
        season_df = backfill_ote_season(season, dry_run=args.dry_run)
        all_results[season] = len(season_df)

    # Summary
    print("\n" + "=" * 80)
    print("BACKFILL SUMMARY")
    print("=" * 80)

    total_records = sum(all_results.values())

    for season, record_count in all_results.items():
        status = "✓" if record_count > 0 else "✗"
        print(f"  {status} {season}: {record_count:,} records")

    print(f"\n  TOTAL: {total_records:,} records")

    if not args.dry_run:
        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("1. Re-run multi-gate matcher:")
        print("   python scripts/multi_gate_player_matcher.py")
        print("\n2. Re-run unified career dataset builder:")
        print("   python scripts/build_unified_career_gold_chunked.py")
        print("\n3. Validate Thompson twins pathway:")
        print("   python scripts/validate_multi_league_players.py --player 'thompson'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
