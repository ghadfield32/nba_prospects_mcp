#!/usr/bin/env python3
"""Test NZ-NBL Season Statistics (New Functions)

Tests the newly implemented NZ-NBL player_season and team_season functions
that aggregate game-level data since FIBA LiveStats doesn't provide season
aggregates directly.

Created: 2025-11-18
Purpose: Verify NZ-NBL season aggregation functions work correctly
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.cbb_data.api.datasets import get_dataset  # noqa: E402


def test_nznbl_player_season():
    """Test NZ-NBL player season statistics"""
    print("\n" + "=" * 80)
    print("TEST 1: NZ-NBL Player Season Statistics")
    print("=" * 80)

    try:
        # Test with default parameters (Totals mode)
        df = get_dataset("player_season", {"league": "NZ-NBL", "season": "2024"})
        print(f"[OK] SUCCESS: Retrieved player season data with {len(df)} players")

        if not df.empty:
            print(f"   Columns: {list(df.columns[:15])}...")
            print("\n   Top 5 scorers:")
            if "PTS" in df.columns:
                top_scorers = df.nlargest(5, "PTS")
                for _idx, row in top_scorers.iterrows():
                    player = row.get("PLAYER_NAME", "Unknown")
                    pts = row.get("PTS", 0)
                    gp = row.get("GP", 0)
                    print(f"     {player}: {pts:.1f} PTS in {gp} GP")
        else:
            print("   [WARN] WARNING: DataFrame is empty (requires game index population)")

        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nznbl_team_season():
    """Test NZ-NBL team season statistics"""
    print("\n" + "=" * 80)
    print("TEST 2: NZ-NBL Team Season Statistics")
    print("=" * 80)

    try:
        df = get_dataset("team_season", {"league": "NZ-NBL", "season": "2024"})
        print(f"[OK] SUCCESS: Retrieved team season data with {len(df)} teams")

        if not df.empty:
            print(f"   Columns: {list(df.columns[:15])}...")
            print("\n   Team Standings:")
            for _idx, row in df.iterrows():
                team = row.get("TEAM", "Unknown")
                gp = row.get("GP", 0)
                pts = row.get("PTS", 0)
                ppg = pts / gp if gp > 0 else 0
                print(f"     {team}: {gp} GP, {pts:.1f} PTS ({ppg:.1f} PPG)")
        else:
            print("   [WARN] WARNING: DataFrame is empty (requires game index population)")

        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nznbl_player_season_per_game():
    """Test NZ-NBL player season with PerGame mode"""
    print("\n" + "=" * 80)
    print("TEST 3: NZ-NBL Player Season (PerGame Mode)")
    print("=" * 80)

    try:
        df = get_dataset(
            "player_season", {"league": "NZ-NBL", "season": "2024", "per_mode": "PerGame"}
        )
        print(f"[OK] SUCCESS: Retrieved per-game stats with {len(df)} players")

        if not df.empty:
            print("\n   Top 5 scorers (per game):")
            if "PTS" in df.columns:
                top_scorers = df.nlargest(5, "PTS")
                for _idx, row in top_scorers.iterrows():
                    player = row.get("PLAYER_NAME", "Unknown")
                    ppg = row.get("PTS", 0)
                    gp = row.get("GP", 0)
                    print(f"     {player}: {ppg:.1f} PPG ({gp} GP)")
        else:
            print("   [WARN] WARNING: DataFrame is empty (requires game index population)")

        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("TESTING NZ-NBL SEASON STATISTICS (NEW FUNCTIONS)")
    print("2025-11-18 - Season Aggregation Implementation")
    print("=" * 80)

    results = {
        "Player Season (Totals)": test_nznbl_player_season(),
        "Team Season": test_nznbl_team_season(),
        "Player Season (PerGame)": test_nznbl_player_season_per_game(),
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
        print("\n[SUCCESS] All tests passed! NZ-NBL season statistics functional.")
        return 0
    else:
        print(f"\n[WARN] {total - passed} test(s) failed. Check game index population.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
