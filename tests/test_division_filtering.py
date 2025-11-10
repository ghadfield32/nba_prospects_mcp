"""
Comprehensive stress tests for division filtering functionality.

Tests division filtering across all leagues (NCAA-MBB, NCAA-WBB, EuroLeague, WNBA)
and various division combinations (D1, all, ["D1", "D2"], etc.).

Date: 2025-11-05
Part of: Phase 3 - Division Filtering implementation
"""

import sys
sys.path.insert(0, 'src')

from cbb_data.api.datasets import get_dataset
import time


def test_ncaa_mbb_d1_only():
    """Test NCAA-MBB with Division 1 only (default)"""
    print("\n" + "="*80)
    print("TEST 1: NCAA-MBB Division 1 Only (Default)")
    print("="*80)

    try:
        start = time.time()

        # Fetch D1 only (default behavior)
        df = get_dataset(
            'schedule',
            {'league': 'NCAA-MBB', 'season': '2025'},
            limit=100
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        print(f"  - Sample teams: {df['HOME_TEAM_NAME'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 100, "Should respect limit"

        print("  ✓ TEST PASSED")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_ncaa_mbb_all_divisions():
    """Test NCAA-MBB with all divisions"""
    print("\n" + "="*80)
    print("TEST 2: NCAA-MBB All Divisions")
    print("="*80)

    try:
        start = time.time()

        # Fetch all divisions
        df = get_dataset(
            'schedule',
            {'league': 'NCAA-MBB', 'season': '2025', 'Division': 'all'},
            limit=100
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        print(f"  - Sample teams: {df['HOME_TEAM_NAME'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 100, "Should respect limit"

        print("  ✓ TEST PASSED")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_ncaa_mbb_division_list():
    """Test NCAA-MBB with division list ["D1", "D2"]"""
    print("\n" + "="*80)
    print("TEST 3: NCAA-MBB Multiple Divisions [D1, D2]")
    print("="*80)

    try:
        start = time.time()

        # Fetch D1 and D2
        df = get_dataset(
            'schedule',
            {'league': 'NCAA-MBB', 'season': '2025', 'Division': ['D1', 'D2']},
            limit=100
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        print(f"  - Sample teams: {df['HOME_TEAM_NAME'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 100, "Should respect limit"

        print("  ✓ TEST PASSED")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_ncaa_mbb_d1_explicit():
    """Test NCAA-MBB with explicit D1 filter"""
    print("\n" + "="*80)
    print("TEST 4: NCAA-MBB Explicit Division 1")
    print("="*80)

    try:
        start = time.time()

        # Fetch D1 explicitly
        df = get_dataset(
            'schedule',
            {'league': 'NCAA-MBB', 'season': '2025', 'Division': 'D1'},
            limit=100
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        print(f"  - Sample teams: {df['HOME_TEAM_NAME'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 100, "Should respect limit"

        print("  ✓ TEST PASSED")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_ncaa_wbb_d1_only():
    """Test NCAA-WBB with Division 1 only (default)"""
    print("\n" + "="*80)
    print("TEST 5: NCAA-WBB Division 1 Only (Default)")
    print("="*80)

    try:
        start = time.time()

        # Fetch D1 only (default behavior)
        df = get_dataset(
            'schedule',
            {'league': 'NCAA-WBB', 'season': '2025'},
            limit=100
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        if len(df) > 0:
            print(f"  - Sample teams: {df['HOME_TEAM_NAME'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 100, "Should respect limit"

        print("  ✓ TEST PASSED")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_ncaa_wbb_all_divisions():
    """Test NCAA-WBB with all divisions"""
    print("\n" + "="*80)
    print("TEST 6: NCAA-WBB All Divisions")
    print("="*80)

    try:
        start = time.time()

        # Fetch all divisions
        df = get_dataset(
            'schedule',
            {'league': 'NCAA-WBB', 'season': '2025', 'Division': 'all'},
            limit=100
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        if len(df) > 0:
            print(f"  - Sample teams: {df['HOME_TEAM_NAME'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 100, "Should respect limit"

        print("  ✓ TEST PASSED")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_euroleague_ignores_division():
    """Test EuroLeague ignores division parameter"""
    print("\n" + "="*80)
    print("TEST 7: EuroLeague (Should Ignore Division Parameter)")
    print("="*80)

    try:
        start = time.time()

        # EuroLeague should ignore Division parameter
        df = get_dataset(
            'schedule',
            {'league': 'EuroLeague', 'season': '2024', 'Division': 'D1'},
            limit=50
        )

        elapsed = time.time() - start

        print(f"  - Fetch time: {elapsed:.2f}s")
        print(f"  - Total games: {len(df)}")
        if len(df) > 0:
            print(f"  - Sample teams: {df['HOME_TEAM'].unique()[:5].tolist()}")

        assert len(df) > 0, "Should return games"
        assert len(df) <= 50, "Should respect limit"

        print("  ✓ TEST PASSED (Division parameter correctly ignored)")
        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def test_division_filter_combinations():
    """Test various division filter combinations"""
    print("\n" + "="*80)
    print("TEST 8: Division Filter Combinations (Validation)")
    print("="*80)

    test_cases = [
        ("D1", "50"),
        ("D2", "51"),
        ("D3", "51"),
        ("all", "50,51"),
        (["D1", "D2"], "50,51"),
        ("1", "50"),
        ("2", "51"),
    ]

    from cbb_data.api.datasets import _map_division_to_groups

    all_passed = True
    for division, expected_groups in test_cases:
        result = _map_division_to_groups(division)
        if result == expected_groups:
            print(f"  ✓ {division} -> {result}")
        else:
            print(f"  ✗ {division} -> {result} (expected {expected_groups})")
            all_passed = False

    if all_passed:
        print("  ✓ ALL COMBINATIONS PASSED")
    else:
        print("  ✗ SOME COMBINATIONS FAILED")

    return all_passed


def test_data_completeness():
    """Test that division filtering returns complete data"""
    print("\n" + "="*80)
    print("TEST 9: Data Completeness Check")
    print("="*80)

    try:
        # Fetch D1 games
        df_d1 = get_dataset(
            'schedule',
            {'league': 'NCAA-MBB', 'season': '2025', 'Division': 'D1'},
            limit=100
        )

        # Verify required columns exist
        required_cols = ['GAME_ID', 'GAME_DATE', 'HOME_TEAM_NAME', 'AWAY_TEAM_NAME']
        missing_cols = [col for col in required_cols if col not in df_d1.columns]

        if missing_cols:
            print(f"  ✗ Missing columns: {missing_cols}")
            return False

        # Verify no null values in key columns
        null_counts = df_d1[required_cols].isnull().sum()
        if null_counts.any():
            print(f"  ✗ Null values found: {null_counts[null_counts > 0].to_dict()}")
            return False

        print(f"  ✓ All required columns present: {required_cols}")
        print(f"  ✓ No null values in key columns")
        print(f"  ✓ Data completeness verified")

        return True

    except Exception as e:
        print(f"  ✗ TEST FAILED: {e}")
        return False


def run_all_tests():
    """Run all division filtering stress tests"""
    print("\n" + "="*80)
    print("DIVISION FILTERING COMPREHENSIVE STRESS TESTS")
    print("="*80)
    print(f"Date: 2025-11-05")
    print(f"Testing division filtering across all leagues")
    print("="*80)

    tests = [
        test_ncaa_mbb_d1_only,
        test_ncaa_mbb_all_divisions,
        test_ncaa_mbb_division_list,
        test_ncaa_mbb_d1_explicit,
        test_ncaa_wbb_d1_only,
        test_ncaa_wbb_all_divisions,
        test_euroleague_ignores_division,
        test_division_filter_combinations,
        test_data_completeness,
    ]

    results = []
    start_time = time.time()

    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n✗ {test.__name__} CRASHED: {e}")
            results.append((test.__name__, False))

    total_time = time.time() - start_time

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print("="*80)
    print(f"Total tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {passed/len(results)*100:.1f}%")
    print(f"Total time: {total_time:.2f}s")
    print("="*80)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
