#!/usr/bin/env python3
"""FIBA Cluster Health Check - Quick Status Overview

One-command health check for entire FIBA pipeline.
Checks: Playwright setup, game indexes, data storage, validation status, golden fixtures.

Usage:
    python tools/fiba/health_check.py
    python tools/fiba/health_check.py --verbose
    python tools/fiba/health_check.py --league LKL
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

FIBA_LEAGUES = ["LKL", "ABA", "BAL", "BCL"]
GAME_INDEX_DIR = Path("data/game_indexes")
VALIDATION_FILE = Path("data/raw/fiba/fiba_last_validation.json")
GOLDEN_FIXTURES_FILE = Path("tools/fiba/golden_fixtures_shots.json")


def check_playwright() -> dict:
    """Check if Playwright is installed and ready"""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()

        return {"status": "ok", "message": "Playwright ready"}
    except ImportError:
        return {
            "status": "missing",
            "message": "Playwright not installed (uv pip install playwright)",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Playwright error: {e} (run: playwright install chromium)",
        }


def check_game_indexes(league: str | None = None) -> dict:
    """Check if game indexes exist for FIBA leagues"""
    leagues_to_check = [league] if league else FIBA_LEAGUES
    results = {}

    for lg in leagues_to_check:
        # Check for 2023-24 season
        index_file = GAME_INDEX_DIR / f"{lg}_2023_24.csv"
        if index_file.exists():
            import pandas as pd

            try:
                df = pd.read_csv(index_file)
                results[lg] = {
                    "status": "ok",
                    "games": len(df),
                    "file": str(index_file),
                }
            except Exception as e:
                results[lg] = {
                    "status": "error",
                    "message": f"Failed to read: {e}",
                }
        else:
            results[lg] = {
                "status": "missing",
                "message": f"No index at {index_file}",
            }

    return results


def check_storage(league: str | None = None) -> dict:
    """Check DuckDB storage for FIBA data"""
    try:
        from cbb_data.storage.duckdb_storage import get_storage

        storage = get_storage()
        leagues_to_check = [league] if league else FIBA_LEAGUES
        results = {}

        for lg in leagues_to_check:
            pbp_exists = storage.has_data("pbp", lg, "2023")
            shots_exists = storage.has_data("shots", lg, "2023")

            if pbp_exists or shots_exists:
                # Count games
                pbp_count = 0
                shots_count = 0

                if pbp_exists:
                    pbp_df = storage.load("pbp", lg, "2023", limit=None)
                    if "GAME_ID" in pbp_df.columns:
                        pbp_count = pbp_df["GAME_ID"].nunique()

                if shots_exists:
                    shots_df = storage.load("shots", lg, "2023", limit=None)
                    if "GAME_ID" in shots_df.columns:
                        shots_count = shots_df["GAME_ID"].nunique()

                results[lg] = {
                    "status": "has_data",
                    "pbp_games": pbp_count,
                    "shots_games": shots_count,
                }
            else:
                results[lg] = {
                    "status": "empty",
                    "message": "No PBP or shots data in storage",
                }

        return results

    except Exception as e:
        return {"status": "error", "message": f"Storage error: {e}"}


def check_validation_status() -> dict:
    """Check validation status file"""
    if not VALIDATION_FILE.exists():
        return {
            "status": "missing",
            "message": "Run: python tools/fiba/validate_and_monitor_coverage.py",
        }

    try:
        with open(VALIDATION_FILE) as f:
            data = json.load(f)

        ready_count = sum(1 for l in data.get("leagues", []) if l.get("ready_for_modeling"))
        total_count = len(data.get("leagues", []))

        return {
            "status": "ok",
            "ready": f"{ready_count}/{total_count} leagues ready",
            "run_at": data.get("run_at", "unknown"),
            "details": data.get("leagues", []),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to read validation: {e}"}


def check_golden_fixtures() -> dict:
    """Check golden fixtures status"""
    if not GOLDEN_FIXTURES_FILE.exists():
        return {"status": "missing", "message": "Golden fixtures file not found"}

    try:
        with open(GOLDEN_FIXTURES_FILE) as f:
            fixtures = json.load(f)

        populated = 0
        total = 0

        for league, seasons in fixtures.get("fixtures", {}).items():
            for season, fixture in seasons.items():
                total += 1
                if fixture.get("expected", {}).get("total_shots") is not None:
                    populated += 1

        if populated == 0:
            status = "empty"
            message = "No fixtures populated yet (run browser tests first)"
        elif populated < total:
            status = "partial"
            message = f"{populated}/{total} fixtures populated"
        else:
            status = "complete"
            message = f"All {total} fixtures populated"

        return {"status": status, "message": message, "populated": f"{populated}/{total}"}

    except Exception as e:
        return {"status": "error", "message": f"Failed to read fixtures: {e}"}


def print_health_report(verbose: bool = False):
    """Print comprehensive health report"""
    print("=" * 80)
    print("  FIBA CLUSTER HEALTH CHECK")
    print("=" * 80)
    print()

    # 1. Playwright
    print("1. Playwright Setup")
    print("   " + "-" * 76)
    playwright = check_playwright()
    status_icon = "✅" if playwright["status"] == "ok" else "❌"
    print(f"   {status_icon} {playwright['message']}")
    print()

    # 2. Game Indexes
    print("2. Game Indexes (2023-24 season)")
    print("   " + "-" * 76)
    indexes = check_game_indexes()
    for league, result in indexes.items():
        if result["status"] == "ok":
            print(f"   ✅ {league}: {result['games']} games")
        elif result["status"] == "missing":
            print(f"   ❌ {league}: Missing game index")
        else:
            print(f"   ⚠️  {league}: {result.get('message', 'Error')}")
    print()

    # 3. Storage
    print("3. DuckDB Storage (2023 season)")
    print("   " + "-" * 76)
    storage = check_storage()
    if isinstance(storage, dict) and "status" in storage and storage["status"] == "error":
        print(f"   ❌ {storage['message']}")
    else:
        for league, result in storage.items():
            if result["status"] == "has_data":
                print(
                    f"   ✅ {league}: {result['pbp_games']} PBP games, "
                    f"{result['shots_games']} shots games"
                )
            elif result["status"] == "empty":
                print(f"   ⏳ {league}: No data yet")
    print()

    # 4. Validation Status
    print("4. Validation Status")
    print("   " + "-" * 76)
    validation = check_validation_status()
    if validation["status"] == "ok":
        print(f"   ✅ {validation['ready']}")
        print(f"   Last run: {validation['run_at']}")

        if verbose:
            print("\n   Details:")
            for league_data in validation["details"]:
                ready_icon = "✅" if league_data["ready_for_modeling"] else "⏳"
                print(
                    f"     {ready_icon} {league_data['league']} {league_data['season']}: "
                    f"PBP {league_data['pbp_coverage_pct']*100:.1f}%, "
                    f"Shots {league_data['shots_coverage_pct']*100:.1f}%"
                )
    elif validation["status"] == "missing":
        print(f"   ⏳ {validation['message']}")
    else:
        print(f"   ❌ {validation['message']}")
    print()

    # 5. Golden Fixtures
    print("5. Golden Fixtures")
    print("   " + "-" * 76)
    fixtures = check_golden_fixtures()
    if fixtures["status"] == "complete":
        print(f"   ✅ {fixtures['message']}")
    elif fixtures["status"] == "partial":
        print(f"   ⚠️  {fixtures['message']}")
    elif fixtures["status"] == "empty":
        print(f"   ⏳ {fixtures['message']}")
    else:
        print(f"   ❌ {fixtures['message']}")
    print()

    # Summary
    print("=" * 80)
    print("  SUMMARY")
    print("=" * 80)

    checks = [playwright, validation, fixtures]
    all_ok = all(c["status"] in ["ok", "complete"] for c in checks)

    if all_ok:
        print("\n✅ FIBA pipeline is fully operational!")
        print("\nReady for:")
        print("  - Data fetching (browser scraping)")
        print("  - Coverage validation")
        print("  - Golden fixture regression testing")
        print("  - MCP tool integration")
    else:
        print("\n⏳ FIBA pipeline is partially ready")
        print("\nNext steps:")

        if playwright["status"] != "ok":
            print("  1. Install Playwright:")
            print("     uv pip install playwright && playwright install chromium")

        if validation["status"] == "missing":
            print("  2. Run validation:")
            print("     python tools/fiba/validate_and_monitor_coverage.py")

        storage_results = check_storage()
        has_any_data = any(
            r.get("status") == "has_data" for r in storage_results.values() if isinstance(r, dict)
        )

        if not has_any_data:
            print("  3. Fetch data with browser scraping:")
            print("     python tools/fiba/test_browser_scraping.py --league LKL")

        if fixtures["status"] in ["empty", "partial"]:
            print("  4. Populate golden fixtures:")
            print("     # Update tools/fiba/golden_fixtures_shots.json with actual values")
            print("     python tools/fiba/validate_golden_fixtures.py")

    print()


def main():
    parser = argparse.ArgumentParser(description="FIBA Cluster Health Check")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument(
        "--league",
        choices=FIBA_LEAGUES,
        help="Check specific league only"
    )

    args = parser.parse_args()

    print_health_report(verbose=args.verbose)


if __name__ == "__main__":
    main()
