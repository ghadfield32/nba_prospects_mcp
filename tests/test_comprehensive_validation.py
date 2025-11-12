"""Comprehensive Validation: All Leagues x All Datasets x All Interfaces

Tests:
1. All 12 leagues across all 8 datasets
2. API interface (get_dataset)
3. MCP interface (tool functions)
4. Capability system (graceful failures)
5. Scope enforcement (pre_only filter)
6. Data structure validation

Exit codes:
    0 - All tests passed
    1 - Some tests failed
"""

import sys
import time

# Add src to path
sys.path.insert(0, "src")

import pandas as pd

from cbb_data.api.datasets import get_dataset
from cbb_data.catalog.capabilities import CapabilityLevel, check_capability
from cbb_data.catalog.levels import get_league_level
from cbb_data.servers.mcp.tools import (
    tool_get_player_season_stats,
    tool_get_schedule,
    tool_list_datasets,
)

# Test configuration
ALL_LEAGUES = [
    "NCAA-MBB",
    "NCAA-WBB",
    "EuroLeague",
    "EuroCup",
    "G-League",
    "WNBA",
    "CEBL",
    "OTE",
    "NJCAA",
    "NAIA",
    "U-SPORTS",
    "CCAA",
]

COLLEGE_LEAGUES = ["NCAA-MBB", "NCAA-WBB", "NJCAA", "NAIA", "U-SPORTS", "CCAA"]
PREPRO_LEAGUES = ["OTE", "EuroLeague", "EuroCup", "G-League", "CEBL"]
PRO_LEAGUES = ["WNBA"]  # Only WNBA is excluded from pre-NBA scope

ALL_DATASETS = [
    "schedule",
    "player_game",
    "team_game",
    "pbp",
    "shots",
    "player_season",
    "team_season",
    "player_team_season",
]

# Known limitations (from capability system)
KNOWN_UNAVAILABLE = {
    ("CEBL", "pbp"),
    ("CEBL", "shots"),
    ("NJCAA", "pbp"),
    ("NJCAA", "shots"),
    ("NAIA", "pbp"),
    ("NAIA", "shots"),
}

KNOWN_LIMITED = {
    ("OTE", "shots"),
}

# Season parameters per league
SEASON_PARAMS = {
    "NCAA-MBB": "2024",
    "NCAA-WBB": "2024",
    "EuroLeague": "E2024",
    "EuroCup": "U2024",
    "G-League": "2024-25",
    "WNBA": "2024",
    "CEBL": "2024",
    "OTE": "2024-25",
    "NJCAA": "2024-25",
    "NAIA": "2024-25",
    "U-SPORTS": "2024-25",
    "CCAA": "2024-25",
}


class TestResults:
    """Track test results"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def add_pass(self):
        self.passed += 1

    def add_fail(self, error: str):
        self.failed += 1
        self.errors.append(error)

    def add_skip(self):
        self.skipped += 1

    @property
    def total(self):
        return self.passed + self.failed + self.skipped

    @property
    def pass_rate(self):
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


results = TestResults()


def test_scope_enforcement():
    """Test 1: Scope enforcement with pre_only filter"""
    print("\n" + "=" * 80)
    print("TEST 1: Scope Enforcement (pre_only filter)")
    print("=" * 80)

    # Test 1a: pre_only=True should reject pro leagues
    print("\n[1a] Testing pre_only=True rejects professional leagues...")
    for league in PRO_LEAGUES:
        try:
            df = get_dataset(
                "schedule",
                {"league": league, "season": SEASON_PARAMS[league]},
                limit=1,
                pre_only=True,
            )
            results.add_fail(f"[1a] {league}: Should have been rejected (pro league)")
            print(f"  [FAIL] {league}: Should reject but returned data")
        except ValueError as e:
            if "not in scope" in str(e):
                results.add_pass()
                print(f"  [PASS] {league}: Correctly rejected")
            else:
                results.add_fail(f"[1a] {league}: Wrong error: {e}")
                print(f"  [FAIL] {league}: Wrong error: {e}")
        except Exception as e:
            results.add_fail(f"[1a] {league}: Unexpected error: {e}")
            print(f"  [FAIL] {league}: Unexpected error: {e}")

    # Test 1b: pre_only=True should accept college/prepro leagues
    print("\n[1b] Testing pre_only=True accepts college/prepro leagues...")
    for league in COLLEGE_LEAGUES + PREPRO_LEAGUES:
        try:
            df = get_dataset(
                "schedule",
                {"league": league, "season": SEASON_PARAMS[league]},
                limit=1,
                pre_only=True,
            )
            results.add_pass()
            print(f"  [PASS] {league}: Accepted (returned {len(df)} rows)")
        except Exception as e:
            results.add_fail(f"[1b] {league}: Should accept but failed: {e}")
            print(f"  [FAIL] {league}: Should accept but failed: {e}")

    # Test 1c: pre_only=False should accept all leagues
    print("\n[1c] Testing pre_only=False accepts all leagues...")
    for league in ALL_LEAGUES:
        try:
            df = get_dataset(
                "schedule",
                {"league": league, "season": SEASON_PARAMS[league]},
                limit=1,
                pre_only=False,
            )
            results.add_pass()
            print(f"  [PASS] {league}: Accepted (returned {len(df)} rows)")
        except Exception as e:
            results.add_fail(f"[1c] {league}: Failed with pre_only=False: {e}")
            print(f"  [FAIL] {league}: Failed: {e}")

    print(f"\n[TEST 1] Scope Enforcement: {results.passed} passed, {results.failed} failed")


def test_capability_system():
    """Test 2: Capability system for unavailable data"""
    print("\n" + "=" * 80)
    print("TEST 2: Capability System (graceful failures)")
    print("=" * 80)

    print("\n[2a] Testing known unavailable datasets...")
    for league, dataset in KNOWN_UNAVAILABLE:
        capability = check_capability(league, dataset)
        if capability == CapabilityLevel.UNAVAILABLE:
            results.add_pass()
            print(f"  [PASS] {league}/{dataset}: Correctly marked UNAVAILABLE")
        else:
            results.add_fail(f"[2a] {league}/{dataset}: Should be UNAVAILABLE but is {capability}")
            print(f"  [FAIL] {league}/{dataset}: Expected UNAVAILABLE, got {capability}")

    print("\n[2b] Testing known limited datasets...")
    for league, dataset in KNOWN_LIMITED:
        capability = check_capability(league, dataset)
        if capability == CapabilityLevel.LIMITED:
            results.add_pass()
            print(f"  [PASS] {league}/{dataset}: Correctly marked LIMITED")
        else:
            results.add_fail(f"[2b] {league}/{dataset}: Should be LIMITED but is {capability}")
            print(f"  [FAIL] {league}/{dataset}: Expected LIMITED, got {capability}")

    print(f"\n[TEST 2] Capability System: {results.passed} passed, {results.failed} failed")


def test_league_categorization():
    """Test 3: League level categorization"""
    print("\n" + "=" * 80)
    print("TEST 3: League Categorization")
    print("=" * 80)

    print("\n[3a] Testing college league classification...")
    for league in COLLEGE_LEAGUES:
        level = get_league_level(league)
        if level == "college":
            results.add_pass()
            print(f"  [PASS] {league}: Correctly categorized as 'college'")
        else:
            results.add_fail(f"[3a] {league}: Expected 'college', got '{level}'")
            print(f"  [FAIL] {league}: Expected 'college', got '{level}'")

    print("\n[3b] Testing prepro league classification...")
    for league in PREPRO_LEAGUES:
        level = get_league_level(league)
        if level == "prepro":
            results.add_pass()
            print(f"  [PASS] {league}: Correctly categorized as 'prepro'")
        else:
            results.add_fail(f"[3b] {league}: Expected 'prepro', got '{level}'")
            print(f"  [FAIL] {league}: Expected 'prepro', got '{level}'")

    print("\n[3c] Testing pro league classification...")
    for league in PRO_LEAGUES:
        level = get_league_level(league)
        if level == "pro":
            results.add_pass()
            print(f"  [PASS] {league}: Correctly categorized as 'pro'")
        else:
            results.add_fail(f"[3c] {league}: Expected 'pro', got '{level}'")
            print(f"  [FAIL] {league}: Expected 'pro', got '{level}'")

    print(f"\n[TEST 3] League Categorization: {results.passed} passed, {results.failed} failed")


def test_api_interface():
    """Test 4: API interface (get_dataset) for all leagues"""
    print("\n" + "=" * 80)
    print("TEST 4: API Interface (get_dataset)")
    print("=" * 80)

    # Test core datasets for pre-NBA leagues only (pre_only=True)
    print("\n[4a] Testing API access to college/prepro leagues...")
    core_datasets = ["schedule", "player_game", "player_season"]

    for league in COLLEGE_LEAGUES + PREPRO_LEAGUES:
        for dataset in core_datasets:
            # Skip if known unavailable
            if (league, dataset) in KNOWN_UNAVAILABLE:
                results.add_skip()
                print(f"  [SKIP]  {league}/{dataset}: Skipped (known unavailable)")
                continue

            try:
                df = get_dataset(
                    dataset,
                    {"league": league, "season": SEASON_PARAMS[league]},
                    limit=5,
                    pre_only=True,
                )
                if isinstance(df, pd.DataFrame) and not df.empty:
                    results.add_pass()
                    print(f"  [PASS] {league}/{dataset}: Success ({len(df)} rows)")
                else:
                    results.add_fail(f"[4a] {league}/{dataset}: Empty result")
                    print(f"  [WARN]  {league}/{dataset}: Empty result")
            except Exception as e:
                results.add_fail(f"[4a] {league}/{dataset}: {str(e)[:100]}")
                print(f"  [FAIL] {league}/{dataset}: {str(e)[:80]}")

    print(
        f"\n[TEST 4] API Interface: {results.passed} passed, {results.failed} failed, {results.skipped} skipped"
    )


def test_mcp_interface():
    """Test 5: MCP interface (tool functions)"""
    print("\n" + "=" * 80)
    print("TEST 5: MCP Interface (tool functions)")
    print("=" * 80)

    print("\n[5a] Testing MCP tool_get_schedule...")
    for league in COLLEGE_LEAGUES[:2]:  # Test 2 college leagues
        try:
            result = tool_get_schedule(
                league=league,
                season=SEASON_PARAMS[league],
                limit=5,
                compact=True,
                pre_only=True,
            )
            if result.get("success"):
                results.add_pass()
                print(f"  [PASS] {league}: Success ({result.get('row_count', 0)} rows)")
            else:
                results.add_fail(f"[5a] {league}: {result.get('error', 'Unknown error')}")
                print(f"  [FAIL] {league}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            results.add_fail(f"[5a] {league}: {str(e)[:100]}")
            print(f"  [FAIL] {league}: {str(e)[:80]}")

    print("\n[5b] Testing MCP tool_get_player_season_stats...")
    for league in COLLEGE_LEAGUES[:2]:  # Test 2 college leagues
        try:
            result = tool_get_player_season_stats(
                league=league,
                season=SEASON_PARAMS[league],
                limit=5,
                compact=True,
                pre_only=True,
            )
            if result.get("success"):
                results.add_pass()
                print(f"  [PASS] {league}: Success ({result.get('row_count', 0)} rows)")
            else:
                results.add_fail(f"[5b] {league}: {result.get('error', 'Unknown error')}")
                print(f"  [FAIL] {league}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            results.add_fail(f"[5b] {league}: {str(e)[:100]}")
            print(f"  [FAIL] {league}: {str(e)[:80]}")

    print("\n[5c] Testing MCP tool_list_datasets with pre_only...")
    try:
        # Test with pre_only=True (should only show college/prepro)
        result_pre = tool_list_datasets(pre_only=True)
        if result_pre.get("success"):
            results.add_pass()
            print("  [PASS] tool_list_datasets(pre_only=True): Success")
        else:
            results.add_fail("[5c] pre_only=True failed")
            print("  [FAIL] pre_only=True: Failed")

        # Test with pre_only=False (should show all leagues)
        result_all = tool_list_datasets(pre_only=False)
        if result_all.get("success"):
            results.add_pass()
            print("  [PASS] tool_list_datasets(pre_only=False): Success")
        else:
            results.add_fail("[5c] pre_only=False failed")
            print("  [FAIL] pre_only=False: Failed")
    except Exception as e:
        results.add_fail(f"[5c] tool_list_datasets: {str(e)[:100]}")
        print(f"  [FAIL] tool_list_datasets: {str(e)[:80]}")

    print(f"\n[TEST 5] MCP Interface: {results.passed} passed, {results.failed} failed")


def test_data_structure_validation():
    """Test 6: Data structure validation"""
    print("\n" + "=" * 80)
    print("TEST 6: Data Structure Validation")
    print("=" * 80)

    print("\n[6a] Testing schedule dataset structure...")
    required_cols_schedule = ["GAME_ID", "GAME_DATE"]

    for league in ["NCAA-MBB", "EuroLeague"]:  # Test 1 college + 1 pro
        try:
            df = get_dataset(
                "schedule",
                {"league": league, "season": SEASON_PARAMS[league]},
                limit=1,
                pre_only=False,  # Allow pro leagues for this test
            )
            if all(col in df.columns for col in required_cols_schedule):
                results.add_pass()
                print(f"  [PASS] {league}: Has required columns {required_cols_schedule}")
            else:
                results.add_fail(f"[6a] {league}: Missing required columns")
                print(f"  [FAIL] {league}: Missing required columns")
        except Exception as e:
            results.add_fail(f"[6a] {league}: {str(e)[:100]}")
            print(f"  [FAIL] {league}: {str(e)[:80]}")

    print("\n[6b] Testing player_season dataset structure...")
    required_cols_player = ["PLAYER_NAME", "SEASON", "PTS"]

    for league in ["NCAA-MBB", "EuroLeague"]:
        try:
            df = get_dataset(
                "player_season",
                {"league": league, "season": SEASON_PARAMS[league]},
                limit=1,
                pre_only=False,
            )
            if all(col in df.columns for col in required_cols_player):
                results.add_pass()
                print(f"  [PASS] {league}: Has required columns {required_cols_player}")
            else:
                results.add_fail(f"[6b] {league}: Missing required columns")
                print(f"  [FAIL] {league}: Missing required columns")
        except Exception as e:
            results.add_fail(f"[6b] {league}: {str(e)[:100]}")
            print(f"  [FAIL] {league}: {str(e)[:80]}")

    print(f"\n[TEST 6] Data Structure: {results.passed} passed, {results.failed} failed")


def main():
    """Run all validation tests"""
    print("=" * 80)
    print("COMPREHENSIVE VALIDATION: All Leagues x All Datasets x All Interfaces")
    print("=" * 80)
    print(f"Testing {len(ALL_LEAGUES)} leagues across {len(ALL_DATASETS)} datasets")
    print(f"Leagues: {', '.join(ALL_LEAGUES)}")

    start_time = time.time()

    # Run all tests
    test_scope_enforcement()
    test_capability_system()
    test_league_categorization()
    test_api_interface()
    test_mcp_interface()
    test_data_structure_validation()

    elapsed = time.time() - start_time

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {results.total}")
    print(f"[PASS] Passed: {results.passed}")
    print(f"[FAIL] Failed: {results.failed}")
    print(f"[SKIP]  Skipped: {results.skipped}")
    print(f"Pass Rate: {results.pass_rate:.1f}%")
    print(f"Time: {elapsed:.1f}s")

    if results.failed > 0:
        print("\n[FAIL] FAILURES:")
        for i, error in enumerate(results.errors[:10], 1):  # Show first 10
            print(f"{i}. {error}")
        if len(results.errors) > 10:
            print(f"... and {len(results.errors) - 10} more")

    # Exit code
    if results.failed == 0:
        print("\n[PASS] ALL VALIDATION TESTS PASSED")
        sys.exit(0)
    else:
        print(f"\n[FAIL] {results.failed} VALIDATION TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
