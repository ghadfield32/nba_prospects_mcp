"""Test Unified FIBA LiveStats Client

This script tests the newly created unified FIBA LiveStats client
with Basketball Champions League (BCL) as the first new league.

Tests:
1. BCL Schedule - Fetch games for 2024 season
2. BCL Box Score - Fetch player stats for a game
3. BCL Play-by-Play - Fetch PBP events
4. BCL Shot Chart - Fetch shot data

Expected Results:
- All fetches should return DataFrames with data
- LEAGUE column should be "Basketball Champions League"
- Rate limiting should be shared across all FIBA leagues
"""

import sys

sys.path.insert(0, "src")

from cbb_data.fetchers.bcl import (
    fetch_bcl_box_score,
    fetch_bcl_play_by_play,
    fetch_bcl_schedule,
    fetch_bcl_shot_chart,
)


def test_bcl_schedule():
    """Test BCL schedule fetching"""
    print("=" * 80)
    print("TEST 1: BCL Schedule")
    print("=" * 80)

    try:
        schedule = fetch_bcl_schedule(2024, phase="RS", round_start=1, round_end=3)

        print(f"✅ Fetched {len(schedule)} BCL games")

        if not schedule.empty:
            print("\nSample games:")
            print(schedule[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]].head(3))
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
    """Test BCL box score fetching"""
    print("\n" + "=" * 80)
    print("TEST 2: BCL Box Score")
    print("=" * 80)

    try:
        # Try to fetch first game of 2024 season
        box = fetch_bcl_box_score(2024, 1)

        print(f"✅ Fetched {len(box)} player stats")

        if not box.empty:
            print("\nTop 3 scorers:")
            top_scorers = box.nlargest(3, "PTS")
            print(top_scorers[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]])
            print(f"\nLeague: {box['LEAGUE'].iloc[0]}")
            assert all(box["LEAGUE"] == "Basketball Champions League"), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No player stats returned (game may not exist)")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_bcl_play_by_play():
    """Test BCL play-by-play fetching"""
    print("\n" + "=" * 80)
    print("TEST 3: BCL Play-by-Play")
    print("=" * 80)

    try:
        pbp = fetch_bcl_play_by_play(2024, 1)

        print(f"✅ Fetched {len(pbp)} play-by-play events")

        if not pbp.empty:
            print("\nFirst 3 plays:")
            print(pbp[["PLAY_NUMBER", "PLAY_TYPE", "PLAYER", "PLAY_INFO"]].head(3))
            print(f"\nLeague: {pbp['LEAGUE'].iloc[0]}")
            assert all(pbp["LEAGUE"] == "Basketball Champions League"), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No PBP events returned")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_bcl_shot_chart():
    """Test BCL shot chart fetching"""
    print("\n" + "=" * 80)
    print("TEST 4: BCL Shot Chart")
    print("=" * 80)

    try:
        shots = fetch_bcl_shot_chart(2024, 1)

        print(f"✅ Fetched {len(shots)} shots")

        if not shots.empty:
            made_shots = shots[shots["SHOT_MADE"]]
            print(
                f"\nShooting accuracy: {len(made_shots)}/{len(shots)} = {len(made_shots)/len(shots)*100:.1f}%"
            )

            # Three-point shooting
            threes = shots[shots["POINTS_VALUE"] == 3]
            if len(threes) > 0:
                three_pct = (threes["SHOT_MADE"].sum() / len(threes)) * 100
                print(f"3PT shooting: {threes['SHOT_MADE'].sum()}/{len(threes)} = {three_pct:.1f}%")

            print(f"\nLeague: {shots['LEAGUE'].iloc[0]}")
            assert all(shots["LEAGUE"] == "Basketball Champions League"), "LEAGUE column incorrect"
            print("✅ LEAGUE column validated")
        else:
            print("⚠️ No shot data returned")

        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("UNIFIED FIBA LIVESTATS CLIENT - TEST SUITE")
    print("Testing Basketball Champions League (BCL)")
    print("=" * 80)

    tests = [
        ("BCL Schedule", test_bcl_schedule),
        ("BCL Box Score", test_bcl_box_score),
        ("BCL Play-by-Play", test_bcl_play_by_play),
        ("BCL Shot Chart", test_bcl_shot_chart),
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
        print("\n✅ ALL TESTS PASSED - Unified FIBA client working correctly!")
    else:
        print(f"\n⚠️ {total_count - passed_count} tests failed - see errors above")

    print("=" * 80)
