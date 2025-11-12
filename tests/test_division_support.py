"""Test NCAA Division Support via ESPN groups parameter

This script verifies that the ESPN API correctly supports:
- Division I (groups="50")
- Division II + III (groups="51")
- All divisions (groups="")
"""

import sys

sys.path.insert(0, "src")

from cbb_data.fetchers.espn_mbb import fetch_espn_scoreboard, fetch_espn_teams
from cbb_data.fetchers.espn_wbb import fetch_espn_wbb_scoreboard, fetch_espn_wbb_teams


def test_mbb_divisions():
    """Test Men's Basketball division support"""
    print("=" * 80)
    print("TESTING NCAA MEN'S BASKETBALL DIVISION SUPPORT")
    print("=" * 80)

    # Test Division I (default)
    print("\n[1] Division I Teams (groups='50')...")
    di_teams = fetch_espn_teams(groups="50")
    print(f"    Found {len(di_teams)} Division I teams")
    if not di_teams.empty:
        print(f"    Sample: {di_teams['TEAM_DISPLAY_NAME'].head(3).tolist()}")

    # Test Division II + III
    print("\n[2] Division II + III Teams (groups='51')...")
    dii_diii_teams = fetch_espn_teams(groups="51")
    print(f"    Found {len(dii_diii_teams)} Division II + III teams")
    if not dii_diii_teams.empty:
        print(f"    Sample: {dii_diii_teams['TEAM_DISPLAY_NAME'].head(3).tolist()}")

    # Test All Divisions
    print("\n[3] All Divisions (groups='')...")
    all_teams = fetch_espn_teams(groups="")
    print(f"    Found {len(all_teams)} total teams")

    # Validation
    print("\n[VALIDATION]")
    expected_total = len(di_teams) + len(dii_diii_teams)
    actual_total = len(all_teams)
    print(f"    Division I teams: {len(di_teams)}")
    print(f"    Division II + III teams: {len(dii_diii_teams)}")
    print(f"    Expected total: {expected_total}")
    print(f"    Actual total (groups=''): {actual_total}")

    if actual_total >= expected_total * 0.95:  # Allow 5% margin for data inconsistencies
        print("    [OK] Division filtering works correctly!")
    else:
        print(f"    [WARNING] Total mismatch: {actual_total} vs {expected_total}")

    return di_teams, dii_diii_teams, all_teams


def test_wbb_divisions():
    """Test Women's Basketball division support"""
    print("\n" + "=" * 80)
    print("TESTING NCAA WOMEN'S BASKETBALL DIVISION SUPPORT")
    print("=" * 80)

    # Test Division I (default)
    print("\n[1] Division I Teams (groups='50')...")
    di_teams = fetch_espn_wbb_teams(groups="50")
    print(f"    Found {len(di_teams)} Division I teams")
    if not di_teams.empty:
        print(f"    Sample: {di_teams['TEAM_DISPLAY_NAME'].head(3).tolist()}")

    # Test Division II + III
    print("\n[2] Division II + III Teams (groups='51')...")
    dii_diii_teams = fetch_espn_wbb_teams(groups="51")
    print(f"    Found {len(dii_diii_teams)} Division II + III teams")
    if not dii_diii_teams.empty:
        print(f"    Sample: {dii_diii_teams['TEAM_DISPLAY_NAME'].head(3).tolist()}")

    # Test All Divisions
    print("\n[3] All Divisions (groups='')...")
    all_teams = fetch_espn_wbb_teams(groups="")
    print(f"    Found {len(all_teams)} total teams")

    # Validation
    print("\n[VALIDATION]")
    expected_total = len(di_teams) + len(dii_diii_teams)
    actual_total = len(all_teams)
    print(f"    Division I teams: {len(di_teams)}")
    print(f"    Division II + III teams: {len(dii_diii_teams)}")
    print(f"    Expected total: {expected_total}")
    print(f"    Actual total (groups=''): {actual_total}")

    if actual_total >= expected_total * 0.95:
        print("    [OK] Division filtering works correctly!")
    else:
        print(f"    [WARNING] Total mismatch: {actual_total} vs {expected_total}")

    return di_teams, dii_diii_teams, all_teams


def test_scoreboard_divisions():
    """Test scoreboard/schedule with division filtering"""
    print("\n" + "=" * 80)
    print("TESTING SCHEDULE/SCOREBOARD DIVISION FILTERING")
    print("=" * 80)

    # Use a recent date (today)
    from datetime import datetime

    date_str = datetime.now().strftime("%Y%m%d")

    print(f"\n[1] MBB Schedule for {date_str} (Division I only)...")
    mbb_di = fetch_espn_scoreboard(date=date_str, groups="50")
    print(f"    Found {len(mbb_di)} Division I games")

    print(f"\n[2] MBB Schedule for {date_str} (All divisions)...")
    mbb_all = fetch_espn_scoreboard(date=date_str, groups="")
    print(f"    Found {len(mbb_all)} total games")

    print(f"\n[3] WBB Schedule for {date_str} (Division I only)...")
    wbb_di = fetch_espn_wbb_scoreboard(date=date_str, groups="50")
    print(f"    Found {len(wbb_di)} Division I games")

    print(f"\n[4] WBB Schedule for {date_str} (All divisions)...")
    wbb_all = fetch_espn_wbb_scoreboard(date=date_str, groups="")
    print(f"    Found {len(wbb_all)} total games")

    print("\n[VALIDATION]")
    print(f"    MBB: {len(mbb_di)} DI games, {len(mbb_all)} total games")
    print(f"    WBB: {len(wbb_di)} DI games, {len(wbb_all)} total games")

    if len(mbb_all) >= len(mbb_di) and len(wbb_all) >= len(wbb_di):
        print("    [OK] Schedule filtering works correctly!")
    else:
        print("    [WARNING] Unexpected results in schedule filtering")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("NCAA DIVISION SUPPORT VALIDATION")
    print("=" * 80)
    print("\nThis test validates that ESPN API supports all NCAA divisions:")
    print("  - Division I (groups='50', default)")
    print("  - Division II + III (groups='51')")
    print("  - All divisions (groups='')")
    print("\n" + "=" * 80)

    try:
        # Test team fetching
        mbb_di, mbb_dii_diii, mbb_all = test_mbb_divisions()
        wbb_di, wbb_dii_diii, wbb_all = test_wbb_divisions()

        # Test schedule fetching
        test_scoreboard_divisions()

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("\nMen's Basketball:")
        print(f"  Division I: {len(mbb_di)} teams")
        print(f"  Division II + III: {len(mbb_dii_diii)} teams")
        print(f"  Total: {len(mbb_all)} teams")

        print("\nWomen's Basketball:")
        print(f"  Division I: {len(wbb_di)} teams")
        print(f"  Division II + III: {len(wbb_dii_diii)} teams")
        print(f"  Total: {len(wbb_all)} teams")

        print("\n" + "=" * 80)
        print("[SUCCESS] Division support test completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback

        traceback.print_exc()
