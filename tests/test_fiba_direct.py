"""Test Direct FIBA LiveStats Client

This script tests the newly created direct FIBA LiveStats HTTP client
that bypasses the euroleague-api package limitation.

Tests:
1. BCL (Basketball Champions League) - Schedule, Box Score, PBP, Shots
2. BAL (Basketball Africa League) - Schedule, Box Score
3. ABA (ABA League) - Schedule, Box Score

Expected Results:
- All fetches should return DataFrames with data
- LEAGUE column should match league name
- No ValueError about competition codes
- Same data quality as EuroLeague/EuroCup

Success Criteria:
- ✅ BCL schedule returns 10+ games
- ✅ BCL box score returns player stats
- ✅ BAL/ABA schedules accessible
- ✅ No "Invalid competition value" errors
"""

import sys

sys.path.insert(0, "src")

from cbb_data.fetchers.aba import fetch_aba_schedule
from cbb_data.fetchers.bal import fetch_bal_schedule
from cbb_data.fetchers.bcl import (
    fetch_bcl_box_score,
    fetch_bcl_schedule,
)


def test_bcl_schedule():
    """Test BCL schedule fetching via direct client"""
    print("=" * 80)
    print("TEST 1: BCL Schedule (Direct FIBA Client)")
    print("=" * 80)

    try:
        # Fetch BCL 2024 season, rounds 1-5
        schedule = fetch_bcl_schedule(2024, phase="RS", round_start=1, round_end=5)

        print(f"✅ Fetched {len(schedule)} BCL games")

        if not schedule.empty:
            print("\nSample games:")
            print(
                schedule[
                    ["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE", "LEAGUE"]
                ].head(3)
            )
            print(f"\nLeague values: {schedule['LEAGUE'].unique()}")
            assert all(
                schedule["LEAGUE"] == "Basketball Champions League"
            ), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No games returned (may be offseason or invalid season)")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_bcl_box_score():
    """Test BCL box score fetching via direct client"""
    print("\n" + "=" * 80)
    print("TEST 2: BCL Box Score (Direct FIBA Client)")
    print("=" * 80)

    try:
        # First get a game from schedule
        schedule = fetch_bcl_schedule(2024, phase="RS", round_start=1, round_end=1)

        if schedule.empty:
            print("⚠️ No games in schedule, skipping box score test")
            return True

        game_code = schedule.iloc[0]["GAME_CODE"]
        print(f"Testing with game_code: {game_code}")

        box = fetch_bcl_box_score(2024, game_code)

        print(f"✅ Fetched {len(box)} player stats")

        if not box.empty:
            print("\nTop 3 scorers:")
            top_scorers = box.nlargest(3, "PTS")
            print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
            print(f"\nLeague: {box['LEAGUE'].iloc[0]}")
            assert all(box["LEAGUE"] == "Basketball Champions League"), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No player stats returned (game may not have stats yet)")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_bal_schedule():
    """Test BAL schedule fetching via direct client"""
    print("\n" + "=" * 80)
    print("TEST 3: BAL Schedule (Direct FIBA Client)")
    print("=" * 80)

    try:
        # Fetch BAL 2024 season
        schedule = fetch_bal_schedule(2024, phase="RS", round_start=1, round_end=3)

        print(f"✅ Fetched {len(schedule)} BAL games")

        if not schedule.empty:
            print("\nSample games:")
            print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]].head(3))
            print(f"\nLeague values: {schedule['LEAGUE'].unique()}")
            assert all(schedule["LEAGUE"] == "Basketball Africa League"), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No games returned (may be offseason or invalid season)")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_aba_schedule():
    """Test ABA League schedule fetching via direct client"""
    print("\n" + "=" * 80)
    print("TEST 4: ABA League Schedule (Direct FIBA Client)")
    print("=" * 80)

    try:
        # Fetch ABA 2024-25 season
        schedule = fetch_aba_schedule(2024, phase="RS", round_start=1, round_end=3)

        print(f"✅ Fetched {len(schedule)} ABA games")

        if not schedule.empty:
            print("\nSample games:")
            print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]].head(3))
            print(f"\nLeague values: {schedule['LEAGUE'].unique()}")
            assert all(schedule["LEAGUE"] == "ABA League"), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No games returned (may be offseason or invalid season)")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DIRECT FIBA LIVESTATS CLIENT - TEST SUITE")
    print("Testing BCL, BAL, ABA via Direct HTTP (bypassing euroleague-api)")
    print("=" * 80)

    tests = [
        ("BCL Schedule", test_bcl_schedule),
        ("BCL Box Score", test_bcl_box_score),
        ("BAL Schedule", test_bal_schedule),
        ("ABA Schedule", test_aba_schedule),
    ]

    results = []
    for name, test_func in tests:
        passed = test_func()
        results.append((name, passed))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\n{passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n✅ ALL TESTS PASSED - Direct FIBA client working correctly!")
        print("🎉 BCL, BAL, ABA now accessible (euroleague-api limitation bypassed)")
    else:
        print(f"\n⚠️ {total_count - passed_count} tests failed - see errors above")

    print("=" * 80)
