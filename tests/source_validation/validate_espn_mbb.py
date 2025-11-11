"""Quick validation script for ESPN MBB data source

Run this to quickly test if ESPN MBB data is accessible and complete.
This is a simpler alternative to the full pytest suite.

Usage: python tests/source_validation/validate_espn_mbb.py
"""

import sys
from datetime import datetime


def validate_espn_mbb():
    """Validate ESPN Men's College Basketball data source"""

    print("=" * 70)
    print("ESPN MBB DATA SOURCE VALIDATION")
    print("=" * 70)
    print()

    # Check if sportsdataverse is available
    try:
        from sportsdataverse.mbb import mbb_game_all, mbb_schedule, mbb_teams

        print("✓ sportsdataverse package installed")
    except ImportError as e:
        print(f"[X] sportsdataverse not available: {e}")
        print("\nInstall with: uv pip install sportsdataverse")
        return False

    results = {
        "free": False,
        "easy": False,
        "complete": False,
        "coverage": False,
    }

    # Test 1: Free access (no API keys)
    print("\n[1/6] Testing free access (no API keys required)...")
    try:
        teams_df = mbb_teams()
        if teams_df is not None and not teams_df.empty:
            print(f"    ✓ Fetched {len(teams_df)} teams without API keys")
            results["free"] = True
        else:
            print("    ✗ No team data returned")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # Test 2: Ease of pull (programmatic access)
    print("\n[2/6] Testing ease of programmatic access...")
    try:
        today = datetime.now()
        season = today.year + 1 if today.month >= 10 else today.year

        schedule_df = mbb_schedule(season=season)
        if schedule_df is not None and not schedule_df.empty:
            print(f"    ✓ Fetched schedule for {season} season ({len(schedule_df)} games)")
            results["easy"] = True
        else:
            print(f"    ⚠ No schedule data for {season}")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # Test 3: Data completeness (box scores, PBP)
    print("\n[3/6] Testing data completeness (box scores, PBP)...")
    try:
        # Get a game ID
        if not schedule_df.empty:
            game_id_col = [
                c for c in schedule_df.columns if "game" in c.lower() and "id" in c.lower()
            ][0]
            game_id = schedule_df.iloc[0][game_id_col]

            game_data = mbb_game_all(game_id=int(game_id))

            has_box = "BoxScore" in game_data or "boxScore" in game_data
            has_pbp = "Plays" in game_data or "PlayByPlay" in game_data or "plays" in game_data

            if has_box:
                print("    ✓ Box scores available")
            else:
                print("    ⚠ Box scores not found")

            if has_pbp:
                print("    ✓ Play-by-play available")
            else:
                print("    ⚠ Play-by-play not found")

            if has_box and has_pbp:
                results["complete"] = True
                print("    ✓ Data is complete")
            else:
                print(f"    Available keys: {list(game_data.keys())}")
        else:
            print("    ⚠ No games to test")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    # Test 4: Coverage (D-I teams, current + historical)
    print("\n[4/6] Testing coverage (D-I teams, historical data)...")
    try:
        # Try historical season
        hist_schedule = mbb_schedule(season=2023)
        if hist_schedule is not None and not hist_schedule.empty:
            print(f"    ✓ Historical data available (2023: {len(hist_schedule)} games)")
            results["coverage"] = True
        else:
            print("    ⚠ Limited historical data")
    except Exception as e:
        print(f"    ⚠ Historical data error: {e}")

    # Test 5: Rate limits
    print("\n[5/6] Testing rate limits...")
    try:
        import time

        start = time.time()
        for _ in range(3):
            mbb_teams()
        elapsed = time.time() - start
        rate = 3 / elapsed
        print(f"    ✓ Rate: ~{rate:.1f} req/s (3 requests in {elapsed:.2f}s)")
        if elapsed < 1.0:
            print("    ✓ No strict rate limiting (burst allowed)")
    except Exception as e:
        print(f"    ⚠ Rate limit test error: {e}")

    # Test 6: Error handling
    print("\n[6/6] Testing error handling...")
    try:
        invalid_game = mbb_game_all(game_id=999999999)
        if invalid_game is None or (isinstance(invalid_game, dict) and not invalid_game):
            print("    ✓ Invalid requests handled gracefully (returns None/empty)")
        else:
            print("    ⚠ Unexpected behavior for invalid game ID")
    except Exception:
        print("    ✓ Invalid requests raise exceptions (handled)")

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    criteria = [
        ("FREE ACCESS", results["free"], "No API keys required"),
        ("EASE OF USE", results["easy"], "Programmatic Python API"),
        ("DATA COMPLETE", results["complete"], "Box scores + play-by-play"),
        ("GOOD COVERAGE", results["coverage"], "Historical seasons available"),
    ]

    all_pass = True
    for name, passed, desc in criteria:
        status = "✓" if passed else "✗"
        print(f"{status} {name:15} - {desc}")
        if not passed:
            all_pass = False

    print("=" * 70)

    if all_pass:
        print("\n✅ RECOMMENDATION: USE ESPN MBB (via sportsdataverse)")
        print("   This source is free, easy to use, and provides complete data.")
        return True
    else:
        print("\n⚠ RECOMMENDATION: REVIEW ISSUES ABOVE")
        print("   Some criteria not met; investigate further.")
        return False


if __name__ == "__main__":
    success = validate_espn_mbb()
    sys.exit(0 if success else 1)
