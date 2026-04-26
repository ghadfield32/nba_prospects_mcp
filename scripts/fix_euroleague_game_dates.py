#!/usr/bin/env python3
"""Fix missing GAME_DATE values in EuroLeague canonical data.

The EuroLeague API box score endpoint doesn't include game dates, so all
GAME_DATE values are None in the canonical data. This script fetches the
schedule/calendar data and joins it to update the GAME_DATE values.

Usage:
    # Dry-run
    python fix_euroleague_game_dates.py --seasons 2007 2008 2009

    # Execute
    python fix_euroleague_game_dates.py --seasons 2007 2008 2009 --execute
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from euroleague_api.game_data import GameData

    HAS_EUROLEAGUE_API = True
except ImportError:
    HAS_EUROLEAGUE_API = False

# Paths
CANONICAL_BASE = Path(
    "c:/docker_projects/betts_basketball/unified_basketball_mcp/servers/nba_prospects_mcp/data/canonical/box_player_game"
)


def season_year_to_display(year: int) -> str:
    """Convert year to season string (e.g., 2007 -> '2007-08')."""
    return f"{year}-{str(year + 1)[-2:]}"


def fetch_schedule(season: int) -> pd.DataFrame:
    """Fetch EuroLeague schedule for a season.

    Args:
        season: Season start year (e.g., 2007 for 2007-08)

    Returns:
        DataFrame with columns: GAME_ID, GAME_DATE
    """
    if not HAS_EUROLEAGUE_API:
        raise ImportError(
            "euroleague_api package not installed. Install with: pip install euroleague-api"
        )

    print(f"  Fetching schedule for season {season} (EuroLeague API)...")

    # Fetch calendar data (contains game dates)
    game_data = GameData()
    calendar_df = game_data.get_game_metadata_season(season=season)

    if calendar_df.empty:
        print(f"  [WARNING] No schedule data found for season {season}")
        return pd.DataFrame()

    # Extract GAME_ID and GAME_DATE
    records = []
    for _, row in calendar_df.iterrows():
        game_code = row.get("Gamecode", "")
        date_str = row.get("Date", "")

        if not game_code or not date_str:
            continue

        # Parse date
        try:
            game_date = pd.to_datetime(date_str).strftime("%Y-%m-%d")
        except Exception:
            print(f"  [WARNING] Failed to parse date: {date_str}")
            continue

        records.append({"GAME_ID": f"EUROLEAGUE_{game_code}", "GAME_DATE": game_date})

    schedule_df = pd.DataFrame(records)
    print(f"  Found {len(schedule_df)} games with dates")

    return schedule_df


def fix_season_game_dates(season: int, dry_run: bool = True):
    """Fix GAME_DATE for a season.

    Args:
        season: Season start year (e.g., 2007 for 2007-08)
        dry_run: If True, only show what would be done
    """
    season_str = season_year_to_display(season)
    canonical_path = CANONICAL_BASE / "league=EUROLEAGUE" / f"season={season_str}" / "data.parquet"

    print(f"\n[SEASON {season_str}]")

    if not canonical_path.exists():
        print(f"  [ERROR] Canonical data not found: {canonical_path}")
        return False

    # Load canonical data
    canonical_df = pd.read_parquet(canonical_path)
    print(f"  Loaded {len(canonical_df):,} rows from canonical")

    # Check current GAME_DATE status
    null_dates = canonical_df["GAME_DATE"].isna().sum()
    print(
        f"  GAME_DATE null: {null_dates:,} / {len(canonical_df):,} ({null_dates / len(canonical_df) * 100:.1f}%)"
    )

    if null_dates == 0:
        print("  [OK] All GAME_DATE values already populated")
        return True

    # Fetch schedule
    schedule_df = fetch_schedule(season)

    if schedule_df.empty:
        print("  [ERROR] Cannot fix GAME_DATE without schedule data")
        return False

    # Join schedule to canonical (left join on GAME_ID)
    canonical_df = canonical_df.merge(
        schedule_df, on="GAME_ID", how="left", suffixes=("_old", "_new")
    )

    # Update GAME_DATE (prefer new value from schedule)
    if "GAME_DATE_new" in canonical_df.columns:
        canonical_df["GAME_DATE"] = canonical_df["GAME_DATE_new"].fillna(
            canonical_df["GAME_DATE_old"]
        )
        canonical_df = canonical_df.drop(columns=["GAME_DATE_old", "GAME_DATE_new"])

    # Check updated status
    null_dates_after = canonical_df["GAME_DATE"].isna().sum()
    fixed_count = null_dates - null_dates_after

    print(f"  Fixed {fixed_count:,} GAME_DATE values")
    print(f"  Remaining null: {null_dates_after:,}")

    if null_dates_after > 0:
        print(f"  [WARNING] {null_dates_after:,} games still have no date (not in schedule)")

    # Sample verification
    print("\n  Sample of updated data:")
    sample = canonical_df[canonical_df["GAME_DATE"].notna()].head(3)[
        ["GAME_ID", "GAME_DATE", "PLAYER_NAME_RAW", "PTS"]
    ]
    for _idx, row in sample.iterrows():
        print(
            f"    {row['GAME_ID']} | {row['GAME_DATE']} | {row['PLAYER_NAME_RAW']} | {row['PTS']} PTS"
        )

    if dry_run:
        print(f"  [DRY-RUN] Would update {canonical_path}")
        return True

    # Create backup
    backup_dir = canonical_path.parent / "_backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"data_backup_{timestamp}.parquet"
    pd.read_parquet(canonical_path).to_parquet(backup_path, index=False)
    print(f"  [BACKUP] {backup_path}")

    # Save updated canonical data
    canonical_df.to_parquet(canonical_path, index=False)
    print(f"  [SAVED] {canonical_path}")

    return True


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description="Fix missing GAME_DATE in EuroLeague canonical data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (shows what would happen)
  python fix_euroleague_game_dates.py --seasons 2007 2008 2009

  # Execute fix
  python fix_euroleague_game_dates.py --seasons 2007 2008 2009 --execute

Process:
  1. Fetch EuroLeague schedule/calendar data (has game dates)
  2. Join to canonical data by GAME_ID
  3. Update GAME_DATE column
  4. Save back to canonical (with backup)
""",
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        required=True,
        help="Seasons to fix (e.g., 2007 2008 2009)",
    )
    parser.add_argument("--execute", action="store_true", help="Execute fix (default is dry-run)")

    args = parser.parse_args()

    print("=" * 80)
    print("FIX EUROLEAGUE GAME_DATE VALUES")
    print("=" * 80)
    print(f"\nSeasons: {args.seasons}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")

    if not HAS_EUROLEAGUE_API:
        print("\n[ERROR] euroleague_api package not installed")
        print("Install with: pip install euroleague-api")
        return 1

    # Process each season
    success_count = 0
    for season in args.seasons:
        if fix_season_game_dates(season, dry_run=not args.execute):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"RESULTS: {success_count}/{len(args.seasons)} seasons processed successfully")
    print("=" * 80)

    if not args.execute:
        print("\nTo execute fixes:")
        print(
            f"  python scripts/fix_euroleague_game_dates.py --seasons {' '.join(map(str, args.seasons))} --execute"
        )

    return 0 if success_count == len(args.seasons) else 1


if __name__ == "__main__":
    sys.exit(main())
