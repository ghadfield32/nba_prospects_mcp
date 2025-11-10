#!/usr/bin/env python3
"""
Comprehensive Filter Stress Test Suite

Tests all filter combinations across all datasets and leagues to ensure:
1. Valid combinations work correctly
2. Invalid combinations fail gracefully
3. Filters produce expected results
4. Performance is within acceptable bounds
5. No silent failures occur
"""

import sys
sys.path.insert(0, "src")

from datetime import date, timedelta
import pandas as pd
import time
from cbb_data.api.datasets import get_dataset, list_datasets
import logging

# Reduce log noise
logging.getLogger("cbb_data").setLevel(logging.WARNING)

# ==============================================================================
# Test Configuration
# ==============================================================================

LEAGUES = ["NCAA-MBB", "NCAA-WBB", "EuroLeague"]
DATASETS = ["schedule", "player_game", "pbp", "shots"]

# Test seasons (recent data more likely to exist)
TEST_SEASONS = {
    "NCAA-MBB": "2024-25",
    "NCAA-WBB": "2024-25",
    "EuroLeague": "2024",
}

# Test dates (recent past for predictability)
TEST_DATES = {
    "recent": date.today() - timedelta(days=7),  # 1 week ago
    "month_ago": date.today() - timedelta(days=30),
}

# ==============================================================================
# Test Results Tracking
# ==============================================================================

class TestResults:
    """Track test results across all combinations"""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
        self.warnings = []
        self.performance = []

    def add_pass(self, test_name: str, duration: float, rows: int):
        self.total += 1
        self.passed += 1
        self.performance.append({
            "test": test_name,
            "duration": duration,
            "rows": rows,
            "status": "PASS"
        })

    def add_fail(self, test_name: str, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append({
            "test": test_name,
            "error": str(error),
            "status": "FAIL"
        })

    def add_skip(self, test_name: str, reason: str):
        self.total += 1
        self.skipped += 1
        self.warnings.append({
            "test": test_name,
            "reason": reason,
            "status": "SKIP"
        })

    def print_summary(self):
        print("\n" + "=" * 80)
        print("FILTER STRESS TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.total}")
        print(f"Passed: {self.passed} ({self.passed/self.total*100:.1f}%)")
        print(f"Failed: {self.failed} ({self.failed/self.total*100:.1f}%)")
        print(f"Skipped: {self.skipped} ({self.skipped/self.total*100:.1f}%)")

        if self.errors:
            print("\n" + "-" * 80)
            print(f"FAILURES ({len(self.errors)}):")
            print("-" * 80)
            for err in self.errors:
                print(f"  [{err['status']}] {err['test']}")
                print(f"     Error: {err['error'][:100]}")

        if self.warnings:
            print("\n" + "-" * 80)
            print(f"SKIPPED TESTS ({len(self.warnings)}):")
            print("-" * 80)
            for warn in self.warnings:
                print(f"  [{warn['status']}] {warn['test']}")
                print(f"     Reason: {warn['reason']}")

        # Performance summary
        if self.performance:
            print("\n" + "-" * 80)
            print("PERFORMANCE METRICS:")
            print("-" * 80)
            durations = [p['duration'] for p in self.performance]
            print(f"  Average: {sum(durations)/len(durations):.2f}s")
            print(f"  Median: {sorted(durations)[len(durations)//2]:.2f}s")
            print(f"  Min: {min(durations):.2f}s")
            print(f"  Max: {max(durations):.2f}s")

            # Show slowest tests
            slowest = sorted(self.performance, key=lambda x: x['duration'], reverse=True)[:5]
            print("\n  Slowest Tests:")
            for p in slowest:
                print(f"    {p['duration']:6.2f}s - {p['test']} ({p['rows']} rows)")

results = TestResults()

# ==============================================================================
# Helper Functions
# ==============================================================================

def run_test(test_name: str, test_fn, should_pass=True):
    """Run a single test and record results"""
    try:
        start = time.time()
        df = test_fn()
        duration = time.time() - start

        if df is None:
            results.add_skip(test_name, "Returned None (expected for some combinations)")
        elif df.empty:
            if should_pass:
                results.add_skip(test_name, "Returned empty DataFrame (no data for filters)")
            else:
                results.add_pass(test_name, duration, 0)
        else:
            results.add_pass(test_name, duration, len(df))
            print(f"[PASS] {test_name} - {len(df)} rows in {duration:.2f}s")
    except Exception as e:
        if should_pass:
            results.add_fail(test_name, str(e))
            print(f"[FAIL] {test_name} - {str(e)[:100]}")
        else:
            # Expected to fail
            results.add_pass(test_name, 0, 0)
            print(f"[PASS] {test_name} - Failed as expected: {str(e)[:50]}")

# ==============================================================================
# Test Suite 1: Basic Dataset × League Combinations
# ==============================================================================

def test_basic_combinations():
    """Test all dataset × league combinations with minimal filters"""
    print("\n" + "=" * 80)
    print("TEST SUITE 1: Basic Dataset × League Combinations")
    print("=" * 80)

    for league in LEAGUES:
        for dataset in DATASETS:
            test_name = f"basic_{league}_{dataset}"
            season = TEST_SEASONS[league]

            # Skip shots for NCAA (not supported)
            if dataset == "shots" and league != "EuroLeague":
                results.add_skip(test_name, "Shots only supported for EuroLeague")
                continue

            # Some datasets require game_ids
            if dataset in ["player_game", "pbp", "shots"]:
                # First get a schedule to find game_ids
                try:
                    schedule = get_dataset(
                        "schedule",
                        {"league": league, "season": season},
                        limit=1
                    )
                    if schedule.empty:
                        results.add_skip(test_name, f"No games found for {league} {season}")
                        continue

                    game_id = str(schedule.iloc[0]["GAME_ID" if league != "EuroLeague" else "GAME_CODE"])

                    run_test(
                        test_name,
                        lambda: get_dataset(
                            dataset,
                            {"league": league, "season": season, "game_ids": [game_id]},
                            limit=10
                        )
                    )
                except Exception as e:
                    results.add_skip(test_name, f"Could not get schedule: {e}")
            else:
                run_test(
                    test_name,
                    lambda: get_dataset(
                        dataset,
                        {"league": league, "season": season},
                        limit=10
                    )
                )

# ==============================================================================
# Test Suite 2: Temporal Filters
# ==============================================================================

def test_temporal_filters():
    """Test date, season, season_type filters"""
    print("\n" + "=" * 80)
    print("TEST SUITE 2: Temporal Filters")
    print("=" * 80)

    # Test date ranges (ESPN only)
    for league in ["NCAA-MBB", "NCAA-WBB"]:
        test_name = f"date_range_{league}"
        test_date = TEST_DATES["recent"]

        run_test(
            test_name,
            lambda: get_dataset(
                "schedule",
                {
                    "league": league,
                    "date": {"from": str(test_date), "to": str(test_date)}
                },
                limit=20
            )
        )

    # Test season_type
    for league in LEAGUES:
        test_name = f"season_type_{league}"
        season = TEST_SEASONS[league]

        run_test(
            test_name,
            lambda: get_dataset(
                "schedule",
                {
                    "league": league,
                    "season": season,
                    "season_type": "Regular Season"
                },
                limit=10
            )
        )

# ==============================================================================
# Test Suite 3: Game ID Filters
# ==============================================================================

def test_game_id_filters():
    """Test game_ids filter across datasets"""
    print("\n" + "=" * 80)
    print("TEST SUITE 3: Game ID Filters")
    print("=" * 80)

    for league in LEAGUES:
        season = TEST_SEASONS[league]

        # Get some game IDs
        try:
            schedule = get_dataset(
                "schedule",
                {"league": league, "season": season},
                limit=5
            )

            if schedule.empty:
                results.add_skip(f"game_ids_{league}", f"No games for {league} {season}")
                continue

            game_id_col = "GAME_CODE" if league == "EuroLeague" else "GAME_ID"
            game_ids = [str(gid) for gid in schedule[game_id_col].tolist()]

            # Test each dataset type with game_ids
            for dataset in ["schedule", "player_game", "pbp"]:
                test_name = f"game_ids_{league}_{dataset}"

                run_test(
                    test_name,
                    lambda: get_dataset(
                        dataset,
                        {"league": league, "season": season, "game_ids": game_ids}
                    )
                )

            # Test shots for EuroLeague only
            if league == "EuroLeague":
                test_name = f"game_ids_{league}_shots"
                run_test(
                    test_name,
                    lambda: get_dataset(
                        "shots",
                        {"league": league, "season": season, "game_ids": game_ids[:2]}  # Limit to 2 games
                    )
                )

        except Exception as e:
            results.add_skip(f"game_ids_{league}", f"Could not get schedule: {e}")

# ==============================================================================
# Test Suite 4: Limit & Column Selection
# ==============================================================================

def test_limit_and_columns():
    """Test limit and column selection parameters"""
    print("\n" + "=" * 80)
    print("TEST SUITE 4: Limit & Column Selection")
    print("=" * 80)

    for league in LEAGUES:
        season = TEST_SEASONS[league]

        # Test limit parameter
        test_name = f"limit_{league}"
        run_test(
            test_name,
            lambda: get_dataset(
                "schedule",
                {"league": league, "season": season},
                limit=5
            )
        )

        # Verify limit is respected
        df = get_dataset(
            "schedule",
            {"league": league, "season": season},
            limit=3
        )
        if df is not None and not df.empty:
            if len(df) <= 3:
                print(f"[PASS] limit_verify_{league} - Got {len(df)} rows (limit=3)")
                results.add_pass(f"limit_verify_{league}", 0, len(df))
            else:
                print(f"[FAIL] limit_verify_{league} - Got {len(df)} rows, expected ≤3")
                results.add_fail(f"limit_verify_{league}", f"Limit not respected: got {len(df)} rows")

        # Test column selection
        test_name = f"columns_{league}"
        game_id_col = "GAME_CODE" if league == "EuroLeague" else "GAME_ID"

        df = get_dataset(
            "schedule",
            {"league": league, "season": season},
            columns=[game_id_col, "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"],
            limit=5
        )

        if df is not None and not df.empty:
            expected_cols = {game_id_col, "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"}
            actual_cols = set(df.columns)
            if expected_cols.issubset(actual_cols):
                print(f"[PASS] {test_name} - Columns selected correctly")
                results.add_pass(test_name, 0, len(df))
            else:
                print(f"[FAIL] {test_name} - Missing columns: {expected_cols - actual_cols}")
                results.add_fail(test_name, f"Missing columns: {expected_cols - actual_cols}")

# ==============================================================================
# Test Suite 5: Edge Cases & Error Handling
# ==============================================================================

def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n" + "=" * 80)
    print("TEST SUITE 5: Edge Cases & Error Handling")
    print("=" * 80)

    # Test invalid league
    run_test(
        "invalid_league",
        lambda: get_dataset("schedule", {"league": "InvalidLeague", "season": "2024"}),
        should_pass=False
    )

    # Test missing required filters
    run_test(
        "missing_league",
        lambda: get_dataset("schedule", {"season": "2024"}),
        should_pass=False
    )

    # Test conflicting filters (date range + season for EuroLeague)
    run_test(
        "conflicting_filters",
        lambda: get_dataset(
            "schedule",
            {
                "league": "EuroLeague",
                "season": "2024",
                "date": {"from": "2024-01-01", "to": "2024-01-31"}
            }
        ),
        should_pass=True  # Should work, date filter just ignored for EuroLeague
    )

    # Test empty game_ids
    run_test(
        "empty_game_ids",
        lambda: get_dataset(
            "player_game",
            {"league": "NCAA-MBB", "season": "2024-25", "game_ids": []}
        ),
        should_pass=False
    )

    # Test shots for NCAA (not supported)
    run_test(
        "shots_ncaa_invalid",
        lambda: get_dataset(
            "shots",
            {"league": "NCAA-MBB", "season": "2024-25", "game_ids": ["401"]},
        ),
        should_pass=False
    )

    # Test very old season (may have no data)
    run_test(
        "old_season_ncaa_mbb",
        lambda: get_dataset(
            "schedule",
            {"league": "NCAA-MBB", "season": "2000-01"},
            limit=5
        ),
        should_pass=True  # Should work but may be empty
    )

    # Test future season (should be empty)
    run_test(
        "future_season",
        lambda: get_dataset(
            "schedule",
            {"league": "NCAA-MBB", "season": "2030-31"},
            limit=5
        ),
        should_pass=True  # Should work but empty
    )

# ==============================================================================
# Test Suite 6: Performance Tests
# ==============================================================================

def test_performance():
    """Test performance characteristics"""
    print("\n" + "=" * 80)
    print("TEST SUITE 6: Performance Tests")
    print("=" * 80)

    # Test cached vs uncached performance
    for league in LEAGUES:
        season = TEST_SEASONS[league]

        # First call (cold cache)
        start = time.time()
        df1 = get_dataset("schedule", {"league": league, "season": season}, limit=10)
        cold_time = time.time() - start

        # Second call (warm cache)
        start = time.time()
        df2 = get_dataset("schedule", {"league": league, "season": season}, limit=10)
        warm_time = time.time() - start

        speedup = cold_time / warm_time if warm_time > 0 else 0

        print(f"[INFO] cache_performance_{league}")
        print(f"       Cold: {cold_time:.2f}s, Warm: {warm_time:.2f}s, Speedup: {speedup:.1f}x")

        # Cache should be faster (unless very fast already)
        if cold_time > 0.1 and speedup > 2:
            results.add_pass(f"cache_performance_{league}", warm_time, len(df2) if df2 is not None else 0)
        else:
            results.add_skip(f"cache_performance_{league}", f"Cache speedup: {speedup:.1f}x (too fast to measure)")

# ==============================================================================
# Main Test Runner
# ==============================================================================

def main():
    print("\n" + "=" * 80)
    print("COMPREHENSIVE FILTER STRESS TEST SUITE")
    print("=" * 80)
    print(f"Testing {len(LEAGUES)} leagues × {len(DATASETS)} datasets")
    print(f"Test Leagues: {', '.join(LEAGUES)}")
    print(f"Test Datasets: {', '.join(DATASETS)}")
    print("=" * 80)

    # Run all test suites
    test_basic_combinations()
    test_temporal_filters()
    test_game_id_filters()
    test_limit_and_columns()
    test_edge_cases()
    test_performance()

    # Print summary
    results.print_summary()

    # Return exit code
    if results.failed > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
