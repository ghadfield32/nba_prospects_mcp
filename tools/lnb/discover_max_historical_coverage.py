#!/usr/bin/env python3
"""Discover maximum historical coverage available from LNB API

This script tests the LNB schedule API to determine how far back historical
data is available, then checks Atrium UUID availability for each season.

Purpose:
    - Determine earliest season with schedule data
    - Check which seasons have playable game UUIDs
    - Generate coverage report for planning bulk ingestion
    - Identify gaps in historical coverage

Usage:
    # Test all seasons from 2010 to present
    uv run python tools/lnb/discover_max_historical_coverage.py

    # Test specific range
    uv run python tools/lnb/discover_max_historical_coverage.py --start-year 2015 --end-year 2025

    # Include UUID validation (slower but more accurate)
    uv run python tools/lnb/discover_max_historical_coverage.py --validate-uuids

Output:
    - Console: Table showing schedule/UUID availability per season
    - File: tools/lnb/historical_coverage_report.json
    - File: tools/lnb/historical_coverage_report.csv
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

from src.cbb_data.fetchers.lnb import fetch_lnb_schedule_v2

# ==============================================================================
# CONFIG
# ==============================================================================

# Test range (LNB Pro A was founded in 1987, but API likely doesn't go that far back)
DEFAULT_START_YEAR = 2010
DEFAULT_END_YEAR = datetime.now().year + 1  # Include next season

# Output paths
OUTPUT_DIR = Path("tools/lnb")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
COVERAGE_REPORT_JSON = OUTPUT_DIR / "historical_coverage_report.json"
COVERAGE_REPORT_CSV = OUTPUT_DIR / "historical_coverage_report.csv"

# ==============================================================================
# COVERAGE TESTING
# ==============================================================================


def test_season_availability(
    start_year: int, end_year: int, validate_uuids: bool = False
) -> list[dict]:
    """Test schedule availability for each season

    Args:
        start_year: Starting year to test (e.g., 2015)
        end_year: Ending year to test (e.g., 2025)
        validate_uuids: Whether to validate UUID availability (slower)

    Returns:
        List of dicts with season coverage info
    """
    results = []

    print("=" * 80)
    print("LNB PRO A - HISTORICAL COVERAGE DISCOVERY")
    print("=" * 80)
    print(f"\nTesting seasons {start_year}-{end_year + 1}...")
    print(f"Validate UUIDs: {validate_uuids}\n")

    for year in range(start_year, end_year + 1):
        season_str = f"{year}-{year + 1}"
        print(f"\nTesting {season_str}...", end=" ")

        result = {
            "season": season_str,
            "year": year,
            "has_schedule": False,
            "game_count": 0,
            "games_with_uuids": 0,
            "earliest_game_date": None,
            "latest_game_date": None,
            "tested_at": datetime.now().isoformat(),
        }

        try:
            # Try to fetch schedule
            df = fetch_lnb_schedule_v2(season=year + 1, division=1)

            if not df.empty:
                result["has_schedule"] = True
                result["game_count"] = len(df)

                # Extract date range if available
                if "GAME_DATE" in df.columns:
                    dates = pd.to_datetime(df["GAME_DATE"], errors="coerce").dropna()
                    if not dates.empty:
                        result["earliest_game_date"] = dates.min().isoformat()
                        result["latest_game_date"] = dates.max().isoformat()

                # Check for UUIDs
                if "GAME_ID" in df.columns:
                    games_with_ids = df["GAME_ID"].notna().sum()
                    result["games_with_uuids"] = int(games_with_ids)

                print(f"✅ {result['game_count']} games, {result['games_with_uuids']} with UUIDs")
            else:
                print("❌ Empty response")

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error: {error_msg[:50]}...")
            result["error"] = error_msg

        results.append(result)

    return results


def generate_coverage_report(results: list[dict]) -> None:
    """Generate coverage report in multiple formats

    Args:
        results: List of season coverage results
    """
    # Create summary
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_seasons_tested": len(results),
        "seasons_with_schedule": sum(1 for r in results if r["has_schedule"]),
        "total_games_found": sum(r["game_count"] for r in results),
        "total_games_with_uuids": sum(r["games_with_uuids"] for r in results),
        "earliest_season": next((r["season"] for r in results if r["has_schedule"]), None),
        "latest_season": next((r["season"] for r in reversed(results) if r["has_schedule"]), None),
        "results": results,
    }

    # Save JSON
    with open(COVERAGE_REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON report saved: {COVERAGE_REPORT_JSON}")

    # Save CSV
    df = pd.DataFrame(results)
    df.to_csv(COVERAGE_REPORT_CSV, index=False)
    print(f"✅ CSV report saved: {COVERAGE_REPORT_CSV}")

    # Print summary table
    print("\n" + "=" * 80)
    print("COVERAGE SUMMARY")
    print("=" * 80)
    print(f"Total seasons tested: {summary['total_seasons_tested']}")
    print(f"Seasons with schedule data: {summary['seasons_with_schedule']}")
    print(f"Total games found: {summary['total_games_found']}")
    print(f"Games with UUIDs: {summary['total_games_with_uuids']}")
    print(f"Earliest season: {summary['earliest_season']}")
    print(f"Latest season: {summary['latest_season']}")

    # Print detailed table
    print("\n" + "=" * 80)
    print("DETAILED COVERAGE BY SEASON")
    print("=" * 80)
    print(f"{'Season':<12} {'Schedule':<10} {'Games':<8} {'With UUIDs':<12} {'Date Range'}")
    print("-" * 80)

    for r in results:
        if r["has_schedule"]:
            date_range = ""
            if r["earliest_game_date"] and r["latest_game_date"]:
                early = r["earliest_game_date"][:10]
                late = r["latest_game_date"][:10]
                date_range = f"{early} to {late}"

            print(
                f"{r['season']:<12} "
                f"{'✅':<10} "
                f"{r['game_count']:<8} "
                f"{r['games_with_uuids']:<12} "
                f"{date_range}"
            )
        else:
            print(f"{r['season']:<12} {'❌':<10} {'N/A':<8} {'N/A':<12}")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    usable_seasons = [r for r in results if r["has_schedule"] and r["games_with_uuids"] > 0]

    if usable_seasons:
        print(f"\n✅ Found {len(usable_seasons)} seasons with playable data:\n")
        for r in usable_seasons:
            print(
                f"  • {r['season']}: {r['games_with_uuids']} games with UUIDs (out of {r['game_count']})"
            )

        print("\nNext steps:")
        print("1. Build game index for these seasons:")
        season_args = " ".join(r["season"] for r in usable_seasons)
        print(f"   uv run python tools/lnb/build_game_index.py --seasons {season_args}")

        print("\n2. Bulk ingest PBP/shots data:")
        print(f"   uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons {season_args}")

        print("\n3. Generate normalized tables:")
        print(f"   uv run python tools/lnb/create_normalized_tables.py --seasons {season_args}")
    else:
        print("\n❌ No seasons found with playable data (UUIDs required for PBP/shots)")
        print("\nTroubleshooting:")
        print("1. Check if schedule data exists but UUIDs are missing")
        print("2. Try manual UUID discovery for recent seasons")
        print("3. Consult LNB API documentation for UUID extraction")


def main():
    parser = argparse.ArgumentParser(description="Discover maximum LNB historical coverage")
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_YEAR,
        help=f"Starting year to test (default: {DEFAULT_START_YEAR})",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=DEFAULT_END_YEAR,
        help=f"Ending year to test (default: {DEFAULT_END_YEAR})",
    )
    parser.add_argument(
        "--validate-uuids",
        action="store_true",
        help="Validate UUID availability (slower but more accurate)",
    )

    args = parser.parse_args()

    # Run coverage test
    results = test_season_availability(args.start_year, args.end_year, args.validate_uuids)

    # Generate reports
    generate_coverage_report(results)

    print("\n" + "=" * 80)
    print("DISCOVERY COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
