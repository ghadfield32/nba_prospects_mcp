"""Smoke test for NZ-NBL FIBA expansion features

Tests the newly implemented functions:
- fetch_nz_nbl_schedule_full() - Schedule discovery from nznbl.basketball
- fetch_nz_nbl_shot_chart() - Shot chart extraction from FIBA LiveStats
- Existing fetch_nz_nbl_pbp() - PBP fetcher (validation only)

Usage:
    uv run python test_nz_nbl_expansion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_schedule_discovery():
    """Test schedule discovery from nznbl.basketball"""
    print("=" * 60)
    print("TEST 1: Schedule Discovery (fetch_nz_nbl_schedule_full)")
    print("=" * 60)

    try:
        from cbb_data.fetchers.nz_nbl_fiba import fetch_nz_nbl_schedule_full

        # Test with 2024 season
        print("\nFetching 2024 season schedule...")
        schedule = fetch_nz_nbl_schedule_full("2024")

        if schedule.empty:
            print("[WARNING] No games found (this may be expected for future seasons)")
            return False

        print(f"[SUCCESS] Found {len(schedule)} games")
        print(f"   Columns: {list(schedule.columns)}")

        # Check for required columns
        required_cols = ["GAME_ID", "FIBA_GAME_ID", "SEASON", "LEAGUE"]
        missing_cols = [col for col in required_cols if col not in schedule.columns]

        if missing_cols:
            print(f"[ERROR] Missing required columns: {missing_cols}")
            return False

        # Show sample
        if len(schedule) > 0:
            print("\n   Sample game:")
            print(f"   - Game ID: {schedule.iloc[0]['GAME_ID']}")
            print(f"   - FIBA ID: {schedule.iloc[0]['FIBA_GAME_ID']}")
            print(f"   - Home: {schedule.iloc[0].get('HOME_TEAM', 'N/A')}")
            print(f"   - Away: {schedule.iloc[0].get('AWAY_TEAM', 'N/A')}")

        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return False


def test_shot_chart():
    """Test shot chart fetcher from FIBA LiveStats"""
    print("\n" + "=" * 60)
    print("TEST 2: Shot Chart Fetcher (fetch_nz_nbl_shot_chart)")
    print("=" * 60)

    try:
        from cbb_data.fetchers.nz_nbl_fiba import fetch_nz_nbl_shot_chart

        # Test with a specific game ID (use one from pre-built index if available)
        print("\nFetching shot chart for 2024 season...")
        print("NOTE: This may take a while as it scrapes multiple games")

        # Try with season (limit to first game if available)
        shots = fetch_nz_nbl_shot_chart("2024")

        if shots.empty:
            print("[WARNING] No shot data found")
            print("   This could mean:")
            print("   - No games have shot chart data yet")
            print("   - FIBA shot chart format changed")
            print("   - Games don't have FIBA LiveStats coverage")
            return False

        print(f"[SUCCESS] Found {len(shots)} shots")
        print(f"   Columns: {list(shots.columns)}")

        # Check for required columns
        required_cols = ["SHOT_ID", "GAME_ID", "X", "Y", "SHOT_TYPE", "SHOT_RESULT"]
        missing_cols = [col for col in required_cols if col not in shots.columns]

        if missing_cols:
            print(f"[ERROR] Missing required columns: {missing_cols}")
            return False

        # Show statistics
        if len(shots) > 0:
            made_shots = shots[shots["SHOT_RESULT"] == "MADE"]
            fg_pct = (len(made_shots) / len(shots)) * 100 if len(shots) > 0 else 0

            print("\n   Statistics:")
            print(f"   - Total shots: {len(shots)}")
            print(f"   - Made shots: {len(made_shots)}")
            print(f"   - FG%: {fg_pct:.1f}%")
            print(f"   - Unique games: {shots['GAME_ID'].nunique()}")

            # Show shot type breakdown
            if "SHOT_TYPE" in shots.columns:
                shot_types = shots["SHOT_TYPE"].value_counts()
                print("\n   Shot types:")
                for shot_type, count in shot_types.items():
                    print(f"   - {shot_type}: {count}")

        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return False


def test_pbp_validation():
    """Validate existing PBP fetcher still works"""
    print("\n" + "=" * 60)
    print("TEST 3: PBP Validation (fetch_nz_nbl_pbp)")
    print("=" * 60)

    try:
        from cbb_data.fetchers.nz_nbl_fiba import fetch_nz_nbl_pbp

        # Test with 2024 season
        print("\nValidating PBP fetcher for 2024 season...")
        print("NOTE: This may take a while as it scrapes multiple games")

        pbp = fetch_nz_nbl_pbp("2024")

        if pbp.empty:
            print("[WARNING] No PBP data found")
            print("   This is expected if no games have been played yet")
            return False

        print(f"[SUCCESS] Found {len(pbp)} PBP events")
        print(f"   Columns: {list(pbp.columns)}")

        # Check for required columns
        required_cols = ["GAME_ID", "EVENT_NUM", "PERIOD", "EVENT_TYPE"]
        missing_cols = [col for col in required_cols if col not in pbp.columns]

        if missing_cols:
            print(f"[ERROR] Missing required columns: {missing_cols}")
            return False

        # Show statistics
        if len(pbp) > 0:
            print("\n   Statistics:")
            print(f"   - Total events: {len(pbp)}")
            print(f"   - Unique games: {pbp['GAME_ID'].nunique()}")

            # Show event type breakdown
            if "EVENT_TYPE" in pbp.columns:
                event_types = pbp["EVENT_TYPE"].value_counts()
                print("\n   Top event types:")
                for event_type, count in list(event_types.items())[:5]:
                    print(f"   - {event_type}: {count}")

        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all smoke tests"""
    print("\n" + "=" * 60)
    print("NZ-NBL FIBA EXPANSION SMOKE TESTS")
    print("=" * 60)
    print("\nTesting newly implemented features:")
    print("1. Schedule discovery from nznbl.basketball website")
    print("2. Shot chart extraction from FIBA LiveStats")
    print("3. PBP fetcher validation (existing feature)")
    print("\n" + "=" * 60)

    results = {
        "Schedule Discovery": test_schedule_discovery(),
        "Shot Chart": test_shot_chart(),
        "PBP Validation": test_pbp_validation(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}  {test_name}")

    total_tests = len(results)
    passed_tests = sum(results.values())

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed or returned warnings")
        print("This may be expected if:")
        print("- 2024 season hasn't started yet")
        print("- FIBA LiveStats doesn't have coverage")
        print("- Website structure has changed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
