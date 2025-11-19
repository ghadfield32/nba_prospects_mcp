#!/usr/bin/env python3
"""Validate FIBA Shot Chart Data Against Golden Fixtures

Regression testing to detect:
- Schema changes in shot chart data
- Data quality degradation
- Upstream API changes

Usage:
    python tools/fiba/validate_golden_fixtures.py
    python tools/fiba/validate_golden_fixtures.py --league LKL
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from cbb_data.fetchers import aba, bal, bcl, lkl


def load_golden_fixtures() -> dict:
    """Load golden fixtures from JSON file"""
    fixtures_file = Path(__file__).parent / "golden_fixtures_shots.json"

    with open(fixtures_file) as f:
        return json.load(f)


def validate_fixture(
    league: str,
    season: str,
    fixture: dict,
    fetch_function,
) -> dict:
    """Validate actual data against golden fixture

    Args:
        league: League code
        season: Season string
        fixture: Golden fixture dict
        fetch_function: League's fetch_shot_chart function

    Returns:
        Validation result dict
    """
    print(f"\n{'='*80}")
    print(f"Validating {league} {season} - Game {fixture['game_id']}")
    print(f"{'='*80}")

    # Check if fixture has expected values
    expected = fixture.get("expected", {})
    if expected.get("total_shots") is None:
        print("⚠️  SKIPPED - No expected values set yet")
        print("   Run browser scraping test first to populate golden fixtures")
        return {
            "league": league,
            "season": season,
            "game_id": fixture["game_id"],
            "status": "skipped",
            "reason": "No expected values",
        }

    # Fetch actual data
    try:
        print("Fetching shot chart (use_browser=True)...")
        shots_df = fetch_function(season, force_refresh=True, use_browser=True)

        # Filter to specific game
        game_shots = shots_df[shots_df["GAME_ID"] == fixture["game_id"]]

        if game_shots.empty:
            print(f"❌ FAILED - No shots found for game {fixture['game_id']}")
            return {
                "league": league,
                "season": season,
                "game_id": fixture["game_id"],
                "status": "failed",
                "reason": "No shots data found",
            }

        # Calculate actual metrics
        total_shots = len(game_shots)
        made_shots = game_shots["SHOT_MADE"].sum()
        three_pointers = len(game_shots[game_shots["SHOT_TYPE"] == "3PT"])
        two_pointers = len(game_shots[game_shots["SHOT_TYPE"] == "2PT"])
        fg_pct = made_shots / total_shots if total_shots > 0 else 0
        threes_made = game_shots[(game_shots["SHOT_TYPE"] == "3PT") & game_shots["SHOT_MADE"]]
        three_pct = len(threes_made) / three_pointers if three_pointers > 0 else 0

        actual = {
            "total_shots": total_shots,
            "made_shots": made_shots,
            "three_pointers": three_pointers,
            "two_pointers": two_pointers,
            "fg_pct": round(fg_pct, 3),
            "three_pct": round(three_pct, 3),
        }

        # Compare against expected (with tolerance)
        tolerance = 0.05  # 5% tolerance
        issues = []

        for metric, actual_val in actual.items():
            expected_val = expected.get(metric)
            if expected_val is None:
                continue

            # Calculate difference
            if isinstance(actual_val, int | float):
                diff_pct = abs(actual_val - expected_val) / expected_val if expected_val != 0 else 0

                if diff_pct > tolerance:
                    issues.append(
                        f"{metric}: expected {expected_val}, got {actual_val} ({diff_pct*100:.1f}% diff)"
                    )

        # Determine status
        if issues:
            print("\n⚠️  VALIDATION WARNINGS:")
            for issue in issues:
                print(f"  - {issue}")
            status = "warning"
        else:
            print("\n✅ VALIDATION PASSED")
            status = "passed"

        # Print comparison
        print("\nComparison:")
        print(f"  {'Metric':<20} {'Expected':<15} {'Actual':<15} {'Status':<10}")
        print(f"  {'-'*60}")

        for metric in ["total_shots", "made_shots", "three_pointers", "fg_pct", "three_pct"]:
            exp_val = expected.get(metric, "N/A")
            act_val = actual.get(metric, "N/A")

            if isinstance(exp_val, int | float) and isinstance(act_val, int | float):
                diff = abs(act_val - exp_val) / exp_val if exp_val != 0 else 0
                status_symbol = "✅" if diff <= tolerance else "⚠️"
            else:
                status_symbol = "  "

            print(f"  {metric:<20} {str(exp_val):<15} {str(act_val):<15} {status_symbol}")

        return {
            "league": league,
            "season": season,
            "game_id": fixture["game_id"],
            "status": status,
            "issues": issues if issues else None,
            "actual": actual,
        }

    except Exception as e:
        print(f"\n❌ FAILED - {e}")
        import traceback

        traceback.print_exc()

        return {
            "league": league,
            "season": season,
            "game_id": fixture["game_id"],
            "status": "error",
            "reason": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Validate FIBA shot data against golden fixtures")
    parser.add_argument(
        "--league",
        choices=["LKL", "ABA", "BAL", "BCL", "all"],
        default="all",
        help="League to validate (default: all)",
    )

    args = parser.parse_args()

    # Load golden fixtures
    fixtures_data = load_golden_fixtures()
    fixtures = fixtures_data["fixtures"]

    # Map leagues to fetch functions
    fetch_functions = {
        "LKL": lkl.fetch_shot_chart,
        "ABA": aba.fetch_shot_chart,
        "BAL": bal.fetch_shot_chart,
        "BCL": bcl.fetch_shot_chart,
    }

    # Filter leagues
    if args.league != "all":
        fixtures = {args.league: fixtures[args.league]}

    # Validate each fixture
    results = []
    for league, seasons in fixtures.items():
        for season, fixture in seasons.items():
            result = validate_fixture(
                league,
                season,
                fixture,
                fetch_functions[league],
            )
            results.append(result)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    passed = [r for r in results if r["status"] == "passed"]
    warnings = [r for r in results if r["status"] == "warning"]
    failed = [r for r in results if r["status"] in ["failed", "error"]]
    skipped = [r for r in results if r["status"] == "skipped"]

    print(f"\n✅ Passed: {len(passed)}/{len(results)}")
    print(f"⚠️  Warnings: {len(warnings)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    print(f"⏭️  Skipped: {len(skipped)}/{len(results)}")

    if warnings:
        print("\nWarnings:")
        for r in warnings:
            print(f"  - {r['league']} {r['season']} game {r['game_id']}")
            if r.get("issues"):
                for issue in r["issues"]:
                    print(f"    • {issue}")

    if failed:
        print("\nFailures:")
        for r in failed:
            print(
                f"  - {r['league']} {r['season']} game {r['game_id']}: {r.get('reason', 'Unknown')}"
            )

    # Return exit code
    return 1 if (failed or warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
