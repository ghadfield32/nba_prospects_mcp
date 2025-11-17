#!/usr/bin/env python3
"""Test FIBA shot chart scraping with browser rendering

This script tests the FIBA shot chart implementation using Playwright browser
rendering to bypass HTTP 403 blocking. It verifies that shot data can be
successfully retrieved for all 4 FIBA cluster leagues.

NEW DEBUG FEATURES:
    --debug-html: Save raw HTML when parsing fails (for inspecting page structure)
    --capture-responses: Capture network JSON responses (for finding shot data endpoints)
    --debug-dir: Custom directory for debug artifacts

Usage:
    # Test all leagues
    python tools/fiba/test_browser_scraping.py

    # Test specific league
    python tools/fiba/test_browser_scraping.py --league LKL

    # Test with HTML debug (saves HTML when shots not found)
    python tools/fiba/test_browser_scraping.py --league LKL --debug-html

    # Test with network capture (saves XHR/JSON responses)
    python tools/fiba/test_browser_scraping.py --league LKL --capture-responses

    # Full debug mode
    python tools/fiba/test_browser_scraping.py --league LKL --debug-html --capture-responses

    # Dry run (check setup only)
    python tools/fiba/test_browser_scraping.py --dry-run

Requirements:
    uv pip install playwright
    playwright install chromium
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from cbb_data.fetchers import lkl, aba, bal, bcl
from cbb_data.fetchers.browser_scraper import BrowserScraper


def check_playwright_installed() -> bool:
    """Check if Playwright is installed and configured"""
    try:
        from playwright.sync_api import sync_playwright

        print("✅ Playwright package installed")

        # Try to launch browser
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            print("✅ Chromium browser available")
            return True
        except Exception as e:
            print(f"❌ Chromium browser not found: {e}")
            print("\nInstall with: playwright install chromium")
            return False

    except ImportError:
        print("❌ Playwright not installed")
        print("\nInstall with: uv pip install playwright")
        return False


def test_league_shots(
    league_name: str,
    fetch_function,
    season: str = "2023-24",
    max_games: int = 1,
    debug_html: bool = False,
    capture_responses: bool = False,
    debug_dir: str = "data/raw/fiba/debug",
) -> dict:
    """Test shot chart fetching for a single league

    Args:
        league_name: League name (e.g., "LKL")
        fetch_function: League's fetch_shot_chart function
        season: Season to test
        max_games: Maximum number of games to test (for speed)
        debug_html: Enable HTML debug dumps
        capture_responses: Enable network response capturing
        debug_dir: Base directory for debug artifacts

    Returns:
        dict with test results
    """
    print(f"\n{'='*80}")
    print(f"Testing {league_name} - Season {season}")
    print(f"{'='*80}")

    try:
        # Get schedule first to see what games are available
        if league_name == "LKL":
            schedule = lkl.fetch_schedule(season)
        elif league_name == "ABA":
            schedule = aba.fetch_schedule(season)
        elif league_name == "BAL":
            schedule = bal.fetch_schedule(season)
        elif league_name == "BCL":
            schedule = bcl.fetch_schedule(season)

        if schedule.empty:
            return {
                "league": league_name,
                "success": False,
                "error": "No schedule available",
                "shots": 0,
            }

        total_games = len(schedule)
        print(f"  Schedule has {total_games} games, testing first {max_games}")

        # Get first N game IDs for testing
        test_game_ids = schedule["GAME_ID"].head(max_games).tolist()

        # Network response capture (if enabled)
        if capture_responses and test_game_ids:
            print(f"\n  🔍 Network Response Capture Mode Enabled")
            print(f"  Testing game: {test_game_ids[0]}")

            debug_path = Path(debug_dir) / league_name / season / f"{test_game_ids[0]}_responses"

            with BrowserScraper(headless=True, timeout=30000) as scraper:
                url = f"https://fibalivestats.dcd.shared.geniussports.com/u/{league_name}/{test_game_ids[0]}/shotchart.html"
                html, responses = scraper.get_rendered_html_with_responses(
                    url,
                    wait_time=3.0,
                    response_filter_keywords=("shots", "shotchart", ".json", "data"),
                    debug_dir=debug_path,
                )

                json_responses = [r for r in responses if r["content_type"] and "json" in r["content_type"]]
                print(f"  📦 Captured {len(responses)} total responses, {len(json_responses)} JSON-like")

                if json_responses:
                    print(f"\n  JSON Responses Found:")
                    for i, resp in enumerate(json_responses[:3]):  # Show first 3
                        url_short = resp["url"][-60:] if len(resp["url"]) > 60 else resp["url"]
                        size = len(resp["text"]) if resp["text"] else 0
                        print(f"    {i+1}. {url_short}")
                        print(f"       Status: {resp['status']}, Size: {size} bytes")

        # Fetch shots with browser rendering (standard test)
        print(f"\n  Fetching shot chart (use_browser=True, debug_html={debug_html})...")

        # Call fetch with appropriate debug flags
        shots_df = fetch_function(season, force_refresh=True, use_browser=True, debug_html=debug_html)

        if shots_df.empty:
            print(f"\n  ❌ No shots data retrieved")
            if debug_html:
                print(f"  💾 HTML debug files saved to: {debug_dir}/{league_name}/{season}/")
            return {
                "league": league_name,
                "success": False,
                "error": "No shots data retrieved",
                "shots": 0,
                "games_attempted": len(test_game_ids),
            }

        # Analyze results
        total_shots = len(shots_df)
        unique_games = shots_df["GAME_ID"].nunique() if "GAME_ID" in shots_df.columns else 0
        made_shots = shots_df["SHOT_MADE"].sum() if "SHOT_MADE" in shots_df.columns else 0
        three_pointers = len(shots_df[shots_df["SHOT_TYPE"] == "3PT"]) if "SHOT_TYPE" in shots_df.columns else 0

        print(f"\n✅ SUCCESS!")
        print(f"  Total shots: {total_shots}")
        print(f"  Unique games: {unique_games}")
        print(f"  Made shots: {made_shots} ({made_shots/total_shots*100:.1f}%)")
        print(f"  3-pointers: {three_pointers} ({three_pointers/total_shots*100:.1f}%)")

        # Show sample data
        if total_shots > 0:
            print(f"\nSample data (first 3 shots):")
            sample_cols = ["GAME_ID", "PLAYER_NAME", "SHOT_TYPE", "SHOT_MADE", "SHOT_X", "SHOT_Y"]
            available_cols = [c for c in sample_cols if c in shots_df.columns]
            print(shots_df.head(3)[available_cols].to_string())

        return {
            "league": league_name,
            "success": True,
            "shots": total_shots,
            "games": unique_games,
            "made": made_shots,
            "threes": three_pointers,
            "pct_made": made_shots / total_shots if total_shots > 0 else 0,
        }

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

        return {
            "league": league_name,
            "success": False,
            "error": str(e),
            "shots": 0,
        }


def main():
    parser = argparse.ArgumentParser(description="Test FIBA shot chart scraping with browser")
    parser.add_argument(
        "--league",
        choices=["LKL", "ABA", "BAL", "BCL", "all"],
        default="all",
        help="League to test (default: all)"
    )
    parser.add_argument(
        "--season",
        default="2023-24",
        help="Season to test (default: 2023-24)"
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=1,
        help="Maximum games to test per league (default: 1 for speed)"
    )
    parser.add_argument(
        "--debug-html",
        action="store_true",
        help="Dump raw HTML for games with no parsed shots (for debugging page structure)"
    )
    parser.add_argument(
        "--capture-responses",
        action="store_true",
        help="Capture network responses (shots/shotchart JSON) via Playwright (for finding data endpoints)"
    )
    parser.add_argument(
        "--debug-dir",
        default="data/raw/fiba/debug",
        help="Base directory for debug artifacts (default: data/raw/fiba/debug)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check if Playwright is installed, don't fetch data"
    )

    args = parser.parse_args()

    print("="*80)
    print("FIBA Shot Chart Browser Scraping Test")
    print("="*80)

    # Check Playwright installation
    if not check_playwright_installed():
        print("\n⚠️  Playwright setup incomplete. Please run:")
        print("    uv pip install playwright")
        print("    playwright install chromium")
        return 1

    if args.dry_run:
        print("\n✅ Dry run complete - Playwright is ready")
        return 0

    # Show debug mode status
    if args.debug_html or args.capture_responses:
        print("\n🔧 DEBUG MODE ENABLED:")
        if args.debug_html:
            print("  ✓ HTML debug dumps: ON")
            print(f"    → Saves to: {args.debug_dir}/<LEAGUE>/<SEASON>/<GAME_ID>/")
        if args.capture_responses:
            print("  ✓ Network response capture: ON")
            print(f"    → Saves to: {args.debug_dir}/<LEAGUE>/<SEASON>/<GAME_ID>_responses/")
        print()

    # Define leagues to test
    leagues = {
        "LKL": lkl.fetch_shot_chart,
        "ABA": aba.fetch_shot_chart,
        "BAL": bal.fetch_shot_chart,
        "BCL": bcl.fetch_shot_chart,
    }

    if args.league != "all":
        leagues = {args.league: leagues[args.league]}

    # Test each league
    results = []
    for league_name, fetch_fn in leagues.items():
        result = test_league_shots(
            league_name,
            fetch_fn,
            season=args.season,
            max_games=args.max_games,
            debug_html=args.debug_html,
            capture_responses=args.capture_responses,
            debug_dir=args.debug_dir,
        )
        results.append(result)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\n✅ Successful: {len(successful)}/{len(results)} leagues")
    for r in successful:
        print(f"  - {r['league']}: {r['shots']} shots from {r['games']} games ({r['pct_made']*100:.1f}% made)")

    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)} leagues")
        for r in failed:
            print(f"  - {r['league']}: {r.get('error', 'Unknown error')}")

        if args.debug_html or args.capture_responses:
            print(f"\n💡 DEBUG ARTIFACTS SAVED TO: {args.debug_dir}/")
            print("   Inspect HTML and JSON responses to understand why scraping failed.")
            print("   Look for:")
            print("     • shotData, shots, or shotChart variables in JavaScript")
            print("     • Network responses containing shot coordinates (x,y or LOC_X,LOC_Y)")
            print("     • JSON endpoints returning shot arrays")

    # Return code
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
