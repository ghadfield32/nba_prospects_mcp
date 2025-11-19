#!/usr/bin/env python3
"""ACB Historical Data Backfill Tool

Fetches ACB schedules and box scores for all historical seasons (1983-84 to present).

ACB provides 42 years of historical data accessible via temporada URL parameter:
- Formula: temporada = season_end_year - 1936
- Range: 1983-84 (temporada=48) to 2025-26 (temporada=90)

Usage:
    # Backfill all seasons
    python tools/acb/backfill_historical.py --all

    # Backfill specific seasons
    python tools/acb/backfill_historical.py --seasons 2023-24 2024-25

    # Backfill season range
    python tools/acb/backfill_historical.py --start-year 2020 --end-year 2025

    # Dry run (show what would be fetched)
    python tools/acb/backfill_historical.py --all --dry-run

Created: 2025-11-18
Purpose: Enable comprehensive ACB historical data collection (42 years)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cbb_data.fetchers import acb


def generate_season_list(start_year: int, end_year: int) -> list[str]:
    """Generate list of season strings

    Args:
        start_year: Start year (e.g., 2020 for 2020-21 season)
        end_year: End year (e.g., 2025 for 2024-25 season)

    Returns:
        List of season strings in "YYYY-YY" format
    """
    seasons = []
    for year in range(start_year, end_year + 1):
        next_year = year + 1
        season_str = f"{year}-{str(next_year)[-2:]}"
        seasons.append(season_str)
    return seasons


def get_all_acb_seasons() -> list[str]:
    """Get all ACB seasons from 1983-84 to current

    Returns:
        List of all ACB season strings
    """
    current_year = datetime.now().year
    # ACB starts in fall, so if we're past September, current season is current_year to current_year+1
    if datetime.now().month >= 9:
        end_year = current_year + 1
    else:
        end_year = current_year

    return generate_season_list(1983, end_year)


def backfill_schedule(season: str, dry_run: bool = False) -> int:
    """Backfill schedule for a season

    Args:
        season: Season string (e.g., "2024-25")
        dry_run: If True, don't actually fetch data

    Returns:
        Number of games found (or would be found if dry_run)
    """
    if dry_run:
        print(f"  [DRY RUN] Would fetch schedule for {season}")
        return 0

    try:
        df = acb.fetch_acb_schedule(season=season)
        num_games = len(df)
        print(f"  [OK] {season}: {num_games} games")
        return num_games
    except Exception as e:
        print(f"  [FAIL] {season}: ERROR - {e}")
        return 0


def backfill_box_scores(season: str, dry_run: bool = False, limit: int | None = None) -> int:
    """Backfill box scores for a season

    Args:
        season: Season string (e.g., "2024-25")
        dry_run: If True, don't actually fetch data
        limit: Max number of games to fetch box scores for (None = all)

    Returns:
        Number of box scores fetched
    """
    if dry_run:
        print(f"  [DRY RUN] Would fetch box scores for {season}")
        return 0

    try:
        # First get schedule to get game IDs
        schedule = acb.fetch_acb_schedule(season=season)
        if schedule.empty:
            print(f"  [WARN] {season}: No games in schedule")
            return 0

        game_ids = schedule["GAME_ID"].tolist()
        if limit:
            game_ids = game_ids[:limit]

        print(f"  Fetching box scores for {len(game_ids)} games in {season}...")

        success_count = 0
        for i, game_id in enumerate(game_ids, 1):
            try:
                box_score = acb.fetch_acb_box_score(game_id)
                if not box_score.empty:
                    success_count += 1
                    if i % 10 == 0:
                        print(
                            f"    Progress: {i}/{len(game_ids)} games ({success_count} successful)"
                        )
            except Exception as e:
                print(f"    [WARN] Game {game_id} failed: {e}")

        print(f"  [OK] {season}: {success_count}/{len(game_ids)} box scores fetched")
        return success_count

    except Exception as e:
        print(f"  [FAIL] {season}: ERROR - {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="ACB Historical Data Backfill (1983-84 to present)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--all", action="store_true", help="Backfill all seasons (1983-84 to present)"
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        metavar="SEASON",
        help='Specific seasons to backfill (e.g., "2023-24" "2024-25")',
    )

    parser.add_argument(
        "--start-year", type=int, help="Start year for season range (e.g., 2020 for 2020-21)"
    )

    parser.add_argument(
        "--end-year", type=int, help="End year for season range (e.g., 2025 for 2024-25)"
    )

    parser.add_argument(
        "--schedules-only",
        action="store_true",
        help="Only fetch schedules (skip box scores)",
    )

    parser.add_argument(
        "--box-scores-only",
        action="store_true",
        help="Only fetch box scores (requires schedules already exist)",
    )

    parser.add_argument(
        "--limit-games",
        type=int,
        metavar="N",
        help="Limit box score fetching to first N games per season (for testing)",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without fetching"
    )

    args = parser.parse_args()

    # Determine which seasons to process
    if args.all:
        seasons = get_all_acb_seasons()
        print(f"Backfilling ALL ACB seasons: {len(seasons)} seasons from 1983-84 to present\n")
    elif args.seasons:
        seasons = args.seasons
        print(f"Backfilling {len(seasons)} specified seasons\n")
    elif args.start_year and args.end_year:
        seasons = generate_season_list(args.start_year, args.end_year)
        print(
            f"Backfilling seasons from {args.start_year}-{args.start_year+1} to {args.end_year-1}-{args.end_year}\n"
        )
    else:
        print("Error: Must specify --all, --seasons, or --start-year/--end-year")
        parser.print_help()
        return 1

    # Execute backfill
    total_schedules = 0
    total_box_scores = 0

    if not args.box_scores_only:
        print("=" * 80)
        print("FETCHING SCHEDULES")
        print("=" * 80)
        for season in seasons:
            count = backfill_schedule(season, dry_run=args.dry_run)
            total_schedules += count

        print(f"\nTotal: {total_schedules} games across {len(seasons)} seasons")

    if not args.schedules_only and not args.dry_run:
        print("\n" + "=" * 80)
        print("FETCHING BOX SCORES")
        print("=" * 80)
        if args.limit_games:
            print(f"[Limiting to {args.limit_games} games per season]\n")

        for season in seasons:
            count = backfill_box_scores(season, dry_run=args.dry_run, limit=args.limit_games)
            total_box_scores += count

        print(f"\nTotal: {total_box_scores} box scores fetched")

    # Summary
    print("\n" + "=" * 80)
    print("BACKFILL SUMMARY")
    print("=" * 80)
    print(f"Seasons processed: {len(seasons)}")
    if not args.box_scores_only:
        print(f"Schedules fetched: {total_schedules} games")
    if not args.schedules_only and not args.dry_run:
        print(f"Box scores fetched: {total_box_scores}")

    if args.dry_run:
        print("\n[DRY RUN] No data was actually fetched")

    return 0


if __name__ == "__main__":
    sys.exit(main())
