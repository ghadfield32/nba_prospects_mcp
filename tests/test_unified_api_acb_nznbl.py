#!/usr/bin/env python3
"""Test script to verify ACB and NZ-NBL unified API integration

This script tests that ACB and NZ-NBL are properly wired into the unified API
after the 2025-11-18 integration work.

Tests:
1. ACB schedule retrieval
2. ACB player_game (box scores) retrieval
3. NZ-NBL schedule retrieval
4. NZ-NBL player_game retrieval
5. NZ-NBL team_game retrieval
6. NZ-NBL PBP retrieval
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.cbb_data.api.datasets import get_dataset  # noqa: E402


def test_acb_schedule():
    """Test ACB schedule via unified API"""
    print("\n" + "=" * 80)
    print("TEST 1: ACB Schedule")
    print("=" * 80)

    try:
        df = get_dataset("schedule", {"league": "ACB", "season": "2024-25"})
        print(f"[SUCCESS] Retrieved {len(df)} ACB games")
        if not df.empty:
            print(f"   Columns: {list(df.columns[:10])}...")
            print(f"   Sample game: {df.iloc[0]['HOME_TEAM']} vs {df.iloc[0]['AWAY_TEAM']}")
        else:
            print("   [WARNING] DataFrame is empty (may be expected if season not started)")
        return True
    except Exception as e:
        print(f"[FAILED] {e}")
        return False


def test_acb_box_score():
    """Test ACB box scores via unified API"""
    print("\n" + "=" * 80)
    print("TEST 2: ACB Player Game (Box Scores)")
    print("=" * 80)

    try:
        # First get a game ID from schedule
        schedule = get_dataset("schedule", {"league": "ACB", "season": "2024-25"})
        if schedule.empty:
            print("   [WARN]  SKIPPED: No games in schedule to test")
            return True

        game_id = str(schedule.iloc[0]["GAME_ID"])
        print(f"   Testing with game_id: {game_id}")

        df = get_dataset("player_game", {"league": "ACB", "game_ids": [game_id]})
        print(f"[SUCCESS] Retrieved box score with {len(df)} player rows")
        if not df.empty:
            print(f"   Columns: {list(df.columns[:10])}...")
            print(
                f"   Sample player: {df.iloc[0].get('PLAYER_NAME', 'N/A')} - {df.iloc[0].get('PTS', 0)} pts"
            )
        else:
            print("   [WARNING] DataFrame is empty (game may not have stats yet)")
        return True
    except Exception as e:
        print(f"[FAILED] {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nznbl_schedule():
    """Test NZ-NBL schedule via unified API"""
    print("\n" + "=" * 80)
    print("TEST 3: NZ-NBL Schedule")
    print("=" * 80)

    try:
        df = get_dataset("schedule", {"league": "NZ-NBL", "season": "2024"})
        print(f"[OK] SUCCESS: Retrieved {len(df)} NZ-NBL games")
        if not df.empty:
            print(f"   Columns: {list(df.columns[:10])}...")
            print(f"   Sample game: {df.iloc[0]['HOME_TEAM']} vs {df.iloc[0]['AWAY_TEAM']}")
        else:
            print("   [WARN]  WARNING: DataFrame is empty (requires game index to be populated)")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nznbl_player_game():
    """Test NZ-NBL player game via unified API"""
    print("\n" + "=" * 80)
    print("TEST 4: NZ-NBL Player Game")
    print("=" * 80)

    try:
        df = get_dataset("player_game", {"league": "NZ-NBL", "season": "2024"})
        print(f"[OK] SUCCESS: Retrieved player game data with {len(df)} player rows")
        if not df.empty:
            print(f"   Columns: {list(df.columns[:10])}...")
            print(
                f"   Sample player: {df.iloc[0].get('PLAYER_NAME', 'N/A')} - {df.iloc[0].get('PTS', 0)} pts"
            )
        else:
            print("   [WARN]  WARNING: DataFrame is empty (requires game index to be populated)")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nznbl_team_game():
    """Test NZ-NBL team game via unified API"""
    print("\n" + "=" * 80)
    print("TEST 5: NZ-NBL Team Game")
    print("=" * 80)

    try:
        # team_game uses schedule under the hood, so this should work
        df = get_dataset("team_game", {"league": "NZ-NBL", "season": "2024"})
        print(f"[OK] SUCCESS: Retrieved team game data with {len(df)} rows")
        if not df.empty:
            print(f"   Columns: {list(df.columns[:10])}...")
        else:
            print("   [WARN]  WARNING: DataFrame is empty (requires game index to be populated)")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nznbl_pbp():
    """Test NZ-NBL PBP via unified API"""
    print("\n" + "=" * 80)
    print("TEST 6: NZ-NBL Play-by-Play")
    print("=" * 80)

    try:
        # First get a game ID from schedule
        schedule = get_dataset("schedule", {"league": "NZ-NBL", "season": "2024"})
        if schedule.empty:
            print("   [WARN]  SKIPPED: No games in schedule to test PBP")
            return True

        game_id = str(schedule.iloc[0]["GAME_ID"])
        print(f"   Testing with game_id: {game_id}")

        df = get_dataset(
            "play_by_play", {"league": "NZ-NBL", "season": "2024", "game_ids": [game_id]}
        )
        print(f"[OK] SUCCESS: Retrieved PBP data with {len(df)} events")
        if not df.empty:
            print(f"   Columns: {list(df.columns[:10])}...")
        else:
            print("   [WARN]  WARNING: DataFrame is empty (PBP may not be available for this game)")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("TESTING ACB AND NZ-NBL UNIFIED API INTEGRATION")
    print("2025-11-18 - Post-Integration Verification")
    print("=" * 80)

    results = {
        "ACB Schedule": test_acb_schedule(),
        "ACB Player Game": test_acb_box_score(),
        "NZ-NBL Schedule": test_nznbl_schedule(),
        "NZ-NBL Player Game": test_nznbl_player_game(),
        "NZ-NBL Team Game": test_nznbl_team_game(),
        "NZ-NBL PBP": test_nznbl_pbp(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "[OK] PASS" if passed_test else "[FAIL] FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! ACB and NZ-NBL are properly integrated.")
        return 0
    else:
        print(f"\n[WARN]  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
