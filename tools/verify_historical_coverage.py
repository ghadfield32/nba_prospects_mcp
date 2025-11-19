#!/usr/bin/env python3
"""Historical Data Coverage Verification Tool

Audits historical data coverage across all supported leagues to identify gaps
and provide recommendations for backfilling.

Purpose:
- Verify which leagues have historical data support
- Identify coverage gaps (missing seasons/games)
- Generate backfill recommendations
- Assess data completeness

Supported Leagues:
- ACB (Spanish Liga ACB): 1983-84 to present via temporada parameter
- NZ-NBL: Via FIBA LiveStats game index
- LNB (French LNB): Historical coverage via game index
- NCAA MBB: Via ESPN/stats.ncaa.org
- And others...

Usage:
    # Full coverage audit
    python tools/verify_historical_coverage.py --all

    # Check specific league
    python tools/verify_historical_coverage.py --league ACB

    # Generate backfill recommendations
    python tools/verify_historical_coverage.py --all --recommend

    # Check data availability for season range
    python tools/verify_historical_coverage.py --league ACB --start-year 2020 --end-year 2025

Created: 2025-11-18
Purpose: Audit historical data coverage to ensure comprehensive dataset collection
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ==============================================================================
# League Coverage Definitions
# ==============================================================================

LEAGUE_COVERAGE = {
    "ACB": {
        "name": "Spanish Liga ACB",
        "earliest_season": "1983-84",
        "data_source": "acb.com scraping",
        "historical_access": "Full (42 years via temporada parameter)",
        "format": "YYYY-YY",
        "backfill_tool": "tools/acb/backfill_historical.py",
        "notes": "All historical seasons accessible via temporada=season_end_year-1936",
    },
    "NZ-NBL": {
        "name": "New Zealand NBL",
        "earliest_season": "Unknown",
        "data_source": "FIBA LiveStats HTML scraping",
        "historical_access": "Limited (requires manual game ID discovery)",
        "format": "YYYY",
        "backfill_tool": "tools/nz_nbl/discover_games.py",
        "notes": "Game index required; FIBA LiveStats has bot protection",
    },
    "LNB_BETCLIC_ELITE": {
        "name": "French LNB - Betclic ELITE (formerly Pro A)",
        "earliest_season": "2021-2022",
        "data_source": "Atrium Sports API + LNB Official API",
        "historical_access": "Full (API-based discovery)",
        "format": "YYYY-YYYY",
        "backfill_tool": "tools/lnb/bulk_discover_atrium_api.py",
        "notes": "Top-tier professional (16 teams) - 100% coverage for available seasons",
    },
    "LNB_ELITE2": {
        "name": "French LNB - ELITE 2 (formerly Pro B)",
        "earliest_season": "2022-2023",
        "data_source": "Atrium Sports API",
        "historical_access": "Full (272 fixtures discovered for 2024-2025)",
        "format": "YYYY-YYYY",
        "backfill_tool": "tools/lnb/bulk_discover_atrium_api.py",
        "notes": "Second-tier professional (20 teams) - Ready for ingestion",
    },
    "LNB_ESPOIRS_ELITE": {
        "name": "French LNB - Espoirs ELITE (U21 top-tier)",
        "earliest_season": "2023-2024",
        "data_source": "Atrium Sports API",
        "historical_access": "Metadata configured",
        "format": "YYYY-YYYY",
        "backfill_tool": "tools/lnb/bulk_discover_atrium_api.py",
        "notes": "U21 youth development league - Metadata ready for ingestion",
    },
    "LNB_ESPOIRS_PROB": {
        "name": "French LNB - Espoirs PROB (U21 second-tier)",
        "earliest_season": "2023-2024",
        "data_source": "Atrium Sports API",
        "historical_access": "Metadata configured",
        "format": "YYYY-YYYY",
        "backfill_tool": "tools/lnb/bulk_discover_atrium_api.py",
        "notes": "U21 youth development league - Metadata ready for ingestion",
    },
    "NCAA-MBB": {
        "name": "NCAA Men's Basketball",
        "earliest_season": "2002-03",
        "data_source": "ESPN/stats.ncaa.org",
        "historical_access": "Partial (varies by source)",
        "format": "YYYY",
        "backfill_tool": None,
        "notes": "Historical availability varies by data source",
    },
    "EUROLEAGUE": {
        "name": "EuroLeague",
        "earliest_season": "2000-01",
        "data_source": "EuroLeague API",
        "historical_access": "Full (official API)",
        "format": "YYYY-YYYY",
        "backfill_tool": None,
        "notes": "Comprehensive historical data via official API",
    },
}


# ==============================================================================
# Coverage Verification Functions
# ==============================================================================


def check_acb_coverage(
    start_year: int | None = None, end_year: int | None = None
) -> dict[str, Any]:
    """Check ACB historical coverage

    Args:
        start_year: Optional start year to check (default: 1983)
        end_year: Optional end year to check (default: current season)

    Returns:
        Dictionary with coverage report
    """
    from src.cbb_data.fetchers import acb

    # Determine year range
    if start_year is None:
        start_year = 1983
    if end_year is None:
        current_year = datetime.now().year
        end_year = current_year + 1 if datetime.now().month >= 9 else current_year

    print(f"\n{'='*60}")
    print("ACB COVERAGE VERIFICATION")
    print(f"{'='*60}")
    print(f"Checking seasons: {start_year}-{start_year+1} to {end_year-1}-{end_year}")

    available_seasons = []
    unavailable_seasons = []

    for year in range(start_year, end_year):
        season = f"{year}-{str(year+1)[-2:]}"

        try:
            df = acb.fetch_acb_schedule(season=season)
            game_count = len(df)

            if game_count > 0:
                available_seasons.append({"season": season, "games": game_count})
                print(f"  [OK] {season}: {game_count} games")
            else:
                unavailable_seasons.append({"season": season, "reason": "No games found"})
                print(f"  [WARN] {season}: No games found")

        except Exception as e:
            unavailable_seasons.append({"season": season, "reason": str(e)[:50]})
            print(f"  [FAIL] {season}: {str(e)[:50]}")

    # Summary
    total_seasons = len(available_seasons) + len(unavailable_seasons)
    coverage_pct = (len(available_seasons) / total_seasons * 100) if total_seasons > 0 else 0

    print(f"\n{'='*60}")
    print(f"ACB Coverage: {len(available_seasons)}/{total_seasons} seasons ({coverage_pct:.1f}%)")
    print(f"Total games available: {sum(s['games'] for s in available_seasons)}")

    return {
        "league": "ACB",
        "available_seasons": available_seasons,
        "unavailable_seasons": unavailable_seasons,
        "coverage_percentage": coverage_pct,
        "total_games": sum(s["games"] for s in available_seasons),
    }


def check_nznbl_coverage() -> dict[str, Any]:
    """Check NZ-NBL game index coverage

    Returns:
        Dictionary with coverage report
    """
    from src.cbb_data.fetchers.nz_nbl_fiba import load_game_index

    print(f"\n{'='*60}")
    print("NZ-NBL COVERAGE VERIFICATION")
    print(f"{'='*60}")

    try:
        index = load_game_index()

        if index.empty:
            print("  [WARN] Game index is empty")
            return {
                "league": "NZ-NBL",
                "game_count": 0,
                "seasons": [],
                "coverage_percentage": 0,
            }

        # Analyze coverage
        seasons = index["SEASON"].unique().tolist()
        game_count = len(index)
        games_per_season = index.groupby("SEASON").size().to_dict()

        print(f"  Game index loaded: {game_count} games")
        print(f"  Seasons covered: {', '.join(map(str, sorted(seasons)))}")
        print("\n  Games per season:")
        for season in sorted(seasons):
            print(f"    {season}: {games_per_season[season]} games")

        return {
            "league": "NZ-NBL",
            "game_count": game_count,
            "seasons": seasons,
            "games_per_season": games_per_season,
            "coverage_percentage": None,  # Can't determine without knowing total games
        }

    except FileNotFoundError:
        print("  [WARN] Game index file not found")
        print("  Use tools/nz_nbl/create_game_index.py to create index")
        return {
            "league": "NZ-NBL",
            "game_count": 0,
            "seasons": [],
            "coverage_percentage": 0,
        }
    except Exception as e:
        print(f"  [FAIL] Error loading game index: {e}")
        return {
            "league": "NZ-NBL",
            "game_count": 0,
            "seasons": [],
            "coverage_percentage": 0,
        }


def check_lnb_coverage(league: str = "LNB_BETCLIC_ELITE") -> dict[str, Any]:
    """Check LNB normalized data coverage for specific league

    Args:
        league: League identifier (LNB_PROA, LNB_ELITE2, LNB_ESPOIRS_ELITE, LNB_ESPOIRS_PROB)

    Returns:
        Dictionary with coverage report
    """
    league_names = {
        "LNB_BETCLIC_ELITE": "Betclic ELITE",
        "LNB_PROA": "Betclic ELITE",
        "LNB_ELITE2": "ELITE 2",
        "LNB_ESPOIRS_ELITE": "Espoirs ELITE",
        "LNB_ESPOIRS_PROB": "Espoirs PROB",
    }

    # Map to LEAGUE column values
    league_filter = "LNB_PROA" if league == "LNB_BETCLIC_ELITE" else league

    print(f"\n{'='*60}")
    print(f"LNB {league_names.get(league, league)} COVERAGE VERIFICATION")
    print(f"{'='*60}")

    normalized_path = Path("data/normalized/lnb/player_game")

    try:
        if not normalized_path.exists():
            print("  [WARN] LNB normalized data directory not found")
            return {
                "league": league,
                "game_count": 0,
                "file_count": 0,
                "seasons": [],
                "coverage_percentage": 0,
            }

        # Get all parquet files
        parquet_files = list(normalized_path.rglob("*.parquet"))

        if not parquet_files:
            print("  [WARN] No parquet files found")
            return {
                "league": league,
                "game_count": 0,
                "file_count": 0,
                "seasons": [],
                "coverage_percentage": 0,
            }

        # Analyze coverage by reading sample files
        seasons = set()
        games = set()
        file_count = 0

        for f in parquet_files:
            try:
                df = pd.read_parquet(f)
                if "LEAGUE" in df.columns and "SEASON" in df.columns:
                    # Filter for this specific league
                    league_data = df[df["LEAGUE"] == league_filter]
                    if not league_data.empty:
                        file_count += 1
                        seasons.update(league_data["SEASON"].unique())
                        if "GAME_ID" in league_data.columns:
                            games.update(league_data["GAME_ID"].unique())
            except Exception:
                continue

        seasons_list = sorted(seasons)
        game_count = len(games)

        print(f"  Parquet files with {league_names.get(league)} data: {file_count}")
        print(f"  Unique games: {game_count}")
        if seasons_list:
            print(f"  Seasons covered: {', '.join(seasons_list)}")
        else:
            print("  [WARN] No data found for this league")

        return {
            "league": league,
            "game_count": game_count,
            "file_count": file_count,
            "seasons": seasons_list,
            "coverage_percentage": None,
        }

    except Exception as e:
        print(f"  [FAIL] Error checking LNB coverage: {e}")
        return {
            "league": league,
            "game_count": 0,
            "file_count": 0,
            "seasons": [],
            "coverage_percentage": 0,
        }


def generate_recommendations(coverage_results: list[dict]) -> None:
    """Generate backfill recommendations based on coverage results

    Args:
        coverage_results: List of coverage check results
    """
    print(f"\n{'='*80}")
    print("BACKFILL RECOMMENDATIONS")
    print(f"{'='*80}\n")

    for result in coverage_results:
        league = result["league"]
        info = LEAGUE_COVERAGE.get(league, {})

        print(f"{league} ({info.get('name', 'Unknown')})")
        print("-" * 60)

        # ACB recommendations
        if league == "ACB":
            if result["coverage_percentage"] < 100:
                missing_count = len(result.get("unavailable_seasons", []))
                print(f"  Status: {result['coverage_percentage']:.1f}% coverage")
                print(f"  Missing: {missing_count} season(s)")
                print("\n  Recommendation:")
                print(f"    Run: python {info['backfill_tool']} --all")
                print("    This will backfill all 42 historical seasons (1983-84 to present)")
            else:
                print(f"  Status: [OK] COMPLETE - {result['coverage_percentage']:.1f}% coverage")
                print(f"  Total games: {result['total_games']}")

        # NZ-NBL recommendations
        elif league == "NZ-NBL":
            game_count = result.get("game_count", 0)
            if game_count == 0:
                print("  Status: [WARN] NO DATA - Game index empty or missing")
                print("\n  Recommendation:")
                print("    1. Manually discover game IDs from FIBA LiveStats")
                print(f"    2. Run: python {info['backfill_tool']} --scan-range START END")
                print("    3. Or use: python tools/nz_nbl/create_game_index.py")
            else:
                print(f"  Status: {game_count} games indexed")
                print(f"  Seasons: {', '.join(map(str, sorted(result['seasons'])))}")
                print("\n  Recommendation:")
                print("    Continue adding games using:")
                print(
                    f"    python {info['backfill_tool']} --add-from-range START END --season YYYY"
                )

        # LNB recommendations
        elif league == "LNB":
            game_count = result.get("game_count", 0)
            if game_count == 0:
                print("  Status: [WARN] NO DATA - Game index empty or missing")
            else:
                print(f"  Status: {game_count} games indexed")
                if result["seasons"]:
                    print(f"  Seasons: {', '.join(map(str, sorted(result['seasons'])))}")

        print()


# ==============================================================================
# Main Function
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Historical Data Coverage Verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all supported leagues",
    )

    parser.add_argument(
        "--league",
        choices=["ACB", "NZ-NBL", "LNB"],
        help="Check specific league",
    )

    parser.add_argument(
        "--start-year",
        type=int,
        help="Start year for coverage check (ACB only)",
    )

    parser.add_argument(
        "--end-year",
        type=int,
        help="End year for coverage check (ACB only)",
    )

    parser.add_argument(
        "--recommend",
        action="store_true",
        help="Generate backfill recommendations",
    )

    parser.add_argument(
        "--list-leagues",
        action="store_true",
        help="List all supported leagues and their coverage info",
    )

    args = parser.parse_args()

    # List leagues
    if args.list_leagues:
        print("\n" + "=" * 80)
        print("SUPPORTED LEAGUES - HISTORICAL COVERAGE")
        print("=" * 80 + "\n")

        for code, info in LEAGUE_COVERAGE.items():
            print(f"{code} - {info['name']}")
            print(f"  Earliest Season: {info['earliest_season']}")
            print(f"  Data Source: {info['data_source']}")
            print(f"  Historical Access: {info['historical_access']}")
            print(f"  Backfill Tool: {info['backfill_tool'] or 'N/A'}")
            print(f"  Notes: {info['notes']}")
            print()
        return

    # Check coverage
    results = []

    if args.all:
        print("\n" + "=" * 80)
        print("COMPREHENSIVE HISTORICAL COVERAGE AUDIT")
        print("=" * 80)

        results.append(check_acb_coverage(args.start_year, args.end_year))
        results.append(check_nznbl_coverage())

        # Check all 4 LNB leagues separately
        results.append(check_lnb_coverage("LNB_BETCLIC_ELITE"))
        results.append(check_lnb_coverage("LNB_ELITE2"))
        results.append(check_lnb_coverage("LNB_ESPOIRS_ELITE"))
        results.append(check_lnb_coverage("LNB_ESPOIRS_PROB"))

    elif args.league:
        if args.league == "ACB":
            results.append(check_acb_coverage(args.start_year, args.end_year))
        elif args.league == "NZ-NBL":
            results.append(check_nznbl_coverage())
        elif args.league == "LNB":
            # Check all 4 LNB leagues when LNB is specified
            results.append(check_lnb_coverage("LNB_BETCLIC_ELITE"))
            results.append(check_lnb_coverage("LNB_ELITE2"))
            results.append(check_lnb_coverage("LNB_ESPOIRS_ELITE"))
            results.append(check_lnb_coverage("LNB_ESPOIRS_PROB"))

    else:
        parser.print_help()
        return

    # Generate recommendations
    if args.recommend and results:
        generate_recommendations(results)

    # Final summary
    print(f"\n{'='*80}")
    print("COVERAGE AUDIT COMPLETE")
    print(f"{'='*80}")
    print(f"Leagues checked: {len(results)}")
    for result in results:
        league = result["league"]
        if result.get("coverage_percentage") is not None:
            print(f"  {league}: {result['coverage_percentage']:.1f}% coverage")
        else:
            game_count = result.get("game_count", result.get("total_games", 0))
            print(f"  {league}: {game_count} games")

    print("\nRun with --recommend to see backfill recommendations")


if __name__ == "__main__":
    main()
