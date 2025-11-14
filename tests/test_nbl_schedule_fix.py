#!/usr/bin/env python3
"""
Test NBL Schedule Routing Fix

Tests that get_dataset("schedule") now correctly routes to fetch_nbl_schedule
after adding the missing fetch function registration in catalog/sources.py.

Expected Results:
- BEFORE: get_dataset("schedule", filters={"league": "NBL"}) returned 0 games
- AFTER: Should return 140 games for 2023-24 season
"""

import sys


def test_schedule_routing():
    """Test that schedule routing works through get_dataset"""
    print("=" * 80)
    print("TEST: NBL Schedule Routing Fix")
    print("=" * 80)

    try:
        from cbb_data.api.datasets import get_dataset
        from cbb_data.fetchers.nbl_official import fetch_nbl_schedule

        season = "2023"

        # Test 1: Direct fetcher (should work - baseline)
        print(f"\n1. Testing direct fetcher: fetch_nbl_schedule(season='{season}')")
        direct_schedule = fetch_nbl_schedule(season=season)
        print(f"   Result: {len(direct_schedule)} games")

        # Test 2: get_dataset API (this was broken, should now work)
        print(
            f"\n2. Testing get_dataset API: get_dataset('schedule', filters={{'league': 'NBL', 'season': '{season}'}})"
        )
        api_schedule = get_dataset("schedule", filters={"league": "NBL", "season": season})
        print(f"   Result: {len(api_schedule)} games")

        # Compare results
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)

        if len(direct_schedule) == 0:
            print("ERROR: Direct fetcher returned 0 games - data may not be available")
            return False

        if len(api_schedule) == 0:
            print("FAIL: get_dataset still returns 0 games")
            print("      The fetch_schedule registration may not have taken effect")
            print("      Check that catalog/sources.py was reloaded")
            return False

        if len(api_schedule) == len(direct_schedule):
            print(f"SUCCESS: Both methods return {len(api_schedule)} games")
            print("         Schedule routing is now working correctly!")
            return True
        else:
            print(
                f"WARNING: Different results - Direct: {len(direct_schedule)}, API: {len(api_schedule)}"
            )
            print("         May indicate filtering differences")
            return False

    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_all_datasets():
    """Test all NBL datasets through get_dataset to ensure nothing broke"""
    print("\n" + "=" * 80)
    print("TEST: All NBL Datasets via get_dataset")
    print("=" * 80)

    from cbb_data.api.datasets import get_dataset

    season = "2023"
    tests = []

    # Schedule
    print("\n1. Schedule...")
    try:
        schedule = get_dataset("schedule", filters={"league": "NBL", "season": season})
        print(f"   Result: {len(schedule)} games")
        tests.append(("schedule", len(schedule) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("schedule", False))

    # Player Season - Totals
    print("\n2. Player Season (Totals)...")
    try:
        players = get_dataset(
            "player_season", filters={"league": "NBL", "season": season, "per_mode": "Totals"}
        )
        print(f"   Result: {len(players)} players")
        tests.append(("player_season_totals", len(players) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("player_season_totals", False))

    # Player Season - PerGame
    print("\n3. Player Season (PerGame)...")
    try:
        players = get_dataset(
            "player_season", filters={"league": "NBL", "season": season, "per_mode": "PerGame"}
        )
        print(f"   Result: {len(players)} players")
        tests.append(("player_season_pergame", len(players) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("player_season_pergame", False))

    # Player Season - Per40
    print("\n4. Player Season (Per40)...")
    try:
        players = get_dataset(
            "player_season", filters={"league": "NBL", "season": season, "per_mode": "Per40"}
        )
        print(f"   Result: {len(players)} players")
        tests.append(("player_season_per40", len(players) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("player_season_per40", False))

    # Team Season
    print("\n5. Team Season...")
    try:
        teams = get_dataset("team_season", filters={"league": "NBL", "season": season})
        print(f"   Result: {len(teams)} teams")
        tests.append(("team_season", len(teams) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("team_season", False))

    # Player Game
    print("\n6. Player Game...")
    try:
        player_games = get_dataset(
            "player_game", filters={"league": "NBL", "season": season}, limit=100
        )
        print(f"   Result: {len(player_games)} player-games (limited to 100)")
        tests.append(("player_game", len(player_games) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("player_game", False))

    # Team Game
    print("\n7. Team Game...")
    try:
        team_games = get_dataset(
            "team_game", filters={"league": "NBL", "season": season}, limit=100
        )
        print(f"   Result: {len(team_games)} team-games (limited to 100)")
        tests.append(("team_game", len(team_games) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("team_game", False))

    # Shots
    print("\n8. Shots...")
    try:
        shots = get_dataset("shots", filters={"league": "NBL", "season": season}, limit=1000)
        print(f"   Result: {len(shots)} shots (limited to 1000)")
        tests.append(("shots", len(shots) > 0))
    except Exception as e:
        print(f"   ERROR: {e}")
        tests.append(("shots", False))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in tests if result)
    total = len(tests)

    for name, result in tests:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {name}")

    print(f"\nResult: {passed}/{total} datasets working")

    return passed == total


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("NBL Schedule Routing Fix - Validation Tests")
    print("=" * 80)

    # Test 1: Schedule routing fix
    schedule_fixed = test_schedule_routing()

    # Test 2: All datasets still work
    all_working = test_all_datasets()

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    if schedule_fixed and all_working:
        print("\nSUCCESS: NBL schedule routing is fixed and all datasets work!")
        print("\nThe registry now correctly routes:")
        print("  - get_dataset('schedule') -> fetch_nbl_schedule")
        print("  - get_dataset('player_season') -> fetch_nbl_player_season")
        print("  - get_dataset('team_season') -> fetch_nbl_team_season")
        print("  - get_dataset('player_game') -> fetch_nbl_player_game")
        print("  - get_dataset('team_game') -> fetch_nbl_team_game")
        print("  - get_dataset('shots') -> fetch_nbl_shots")
        return 0
    elif schedule_fixed:
        print("\nPARTIAL SUCCESS: Schedule routing is fixed but some datasets failed")
        return 1
    else:
        print("\nFAILURE: Schedule routing is still broken")
        print("\nTroubleshooting:")
        print("  1. Check that catalog/sources.py has fetch_schedule registered")
        print("  2. Restart Python to reload the module")
        print("  3. Check for import errors in catalog/sources.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
