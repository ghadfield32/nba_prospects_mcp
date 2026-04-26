#!/usr/bin/env python
"""Test BCL Playwright workaround for 403 Forbidden issue.

This script demonstrates that BCL blocks HTTP requests (403 Forbidden)
but allows Playwright browser rendering to succeed.

Usage:
    uv run python nba_prospects_mcp/scripts/test_bcl_playwright.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the enhanced FIBA scraper
from cbb_data.fetchers.fiba_html_common import scrape_fiba_box_score  # noqa: E402


def test_http_fetch(game_id: str):
    """Test HTTP fetching (expected to fail with 403)."""
    print("\nTest 1: HTTP Request (expected to fail with 403)")
    print("-" * 60)

    try:
        df = scrape_fiba_box_score(
            league_code="BCL",
            game_id=game_id,
            league="BCL",
            season="2023-24",
            use_browser=False,
        )

        if df.empty:
            print("  [FAIL] RESULT: Empty DataFrame (likely 403 Forbidden)")
            return False
        else:
            print(f"  [SUCCESS] Fetched {len(df)} player records")
            return True

    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
        return False


def test_playwright_fetch(game_id: str):
    """Test Playwright browser fetching (expected to succeed)."""
    print("\nTest 2: Playwright Browser Rendering (expected to succeed)")
    print("-" * 60)

    try:
        df = scrape_fiba_box_score(
            league_code="BCL",
            game_id=game_id,
            league="BCL",
            season="2023-24",
            use_browser=True,
        )

        if df.empty:
            print("  [FAIL] RESULT: Empty DataFrame")
            return False

        print(f"  [SUCCESS] Fetched {len(df)} player records")
        source_method = df["SOURCE_METHOD"].iloc[0] if "SOURCE_METHOD" in df.columns else "unknown"
        print(f"  Source method: {source_method}")

        # Show sample data
        if len(df) > 0:
            print("\n  Sample player stats:")
            cols = ["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]
            sample = df.head(3)[cols].to_string(index=False)
            print("  " + sample.replace("\n", "\n  "))

        return True

    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
        return False


def main():
    """Run BCL Playwright workaround tests."""
    print("=" * 70)
    print("BCL PLAYWRIGHT WORKAROUND TEST")
    print("=" * 70)
    print()
    print("Purpose: Demonstrate that BCL blocks HTTP (403 Forbidden)")
    print("         but allows Playwright browser rendering.")
    print()

    # Use a known BCL game ID from 2023-24 season
    # This is from the BCL game index: BCL_2023_24.csv
    test_game_id = "119854-VEF-DSK"  # VEF vs DSK from 2023-24 season

    print(f"Test game ID: {test_game_id}")
    print("League: BCL (Basketball Champions League)")
    print("Season: 2023-24")

    # Test 1: HTTP (expected to fail)
    http_success = test_http_fetch(test_game_id)

    # Test 2: Playwright (expected to succeed)
    playwright_success = test_playwright_fetch(test_game_id)

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    if not http_success and playwright_success:
        print("  [EXPECTED] HTTP blocked (403), Playwright succeeded")
        print()
        print("CONCLUSION:")
        print("  The Playwright workaround successfully bypasses")
        print("  BCL's 403 Forbidden error.")
        print("  Use use_browser=True when fetching BCL data.")
        print()
        print("USAGE:")
        print("  # BCL fetcher with Playwright")
        print("  from cbb_data.fetchers.bcl import fetch_player_game")
        print("  player_stats = fetch_player_game(")
        print("      season='2023-24', use_browser=True)")
        print()
        print("  # fill_bcl_gap.py (Playwright is default)")
        print("  uv run python nba_prospects_mcp/scripts/")
        print("    fill_bcl_gap.py --seasons 2023-24 --max-games 5")
        return 0

    if http_success and playwright_success:
        print("  [UNEXPECTED] Both HTTP and Playwright succeeded")
        print("  (BCL may have changed access policy)")
        return 0

    if not http_success and not playwright_success:
        print("  [FAILURE] Both HTTP and Playwright failed")
        print("  Check if:")
        print("    1. Playwright installed:")
        print("       uv run playwright install chromium")
        print("    2. Internet connection is working")
        print("    3. Game ID valid: data/game_indexes/BCL_2023_24.csv")
        return 1

    print("  [UNEXPECTED] HTTP succeeded but Playwright failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
