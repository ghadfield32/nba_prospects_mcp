"""Test suite for Phase 3.3: Season Aggregate Datasets

Tests the 3 new season-level datasets:
1. player_season - Player season totals/averages
2. team_season - Team season totals/averages
3. player_team_season - Player × Team season stats (captures transfers)

Each dataset is tested across all 3 leagues:
- NCAA-MBB
- NCAA-WBB
- EuroLeague
"""

import sys

sys.path.insert(0, "src")

from cbb_data.api.datasets import get_dataset


def test_player_season() -> bool:
    """Test player_season dataset across all leagues"""
    print("\n" + "=" * 70)
    print("TEST 1: player_season Dataset")
    print("=" * 70)

    # Test 1.1: NCAA-MBB - Get top scorers for 2024-25 season
    print("\n1.1 NCAA-MBB: Top scorers 2024-25 (Totals)")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_season",
            {
                "league": "NCAA-MBB",
                "season": "2025",
                "per_mode": "Totals",
                "min_minutes": 100,  # Players with at least 100 total minutes
            },
            limit=10,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} players")
        print(f"[OK] Columns: {list(df.columns)}")

        # Verify expected columns
        required_cols = ["PLAYER_NAME", "GP", "PTS", "REB", "AST", "MIN"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            print(f"[FAIL] FAIL: Missing columns: {missing}")
            return False

        # Show top 5 scorers
        if "PTS" in df.columns:
            top_scorers = df.nlargest(5, "PTS")[["PLAYER_NAME", "GP", "PTS", "REB", "AST", "MIN"]]
            print("\nTop 5 Scorers:")
            print(top_scorers.to_string(index=False))

        print("\n[OK] PASS: NCAA-MBB player_season (Totals)")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 1.2: NCAA-MBB - Per-game averages
    print("\n1.2 NCAA-MBB: Top scorers 2024-25 (PerGame)")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_season",
            {"league": "NCAA-MBB", "season": "2025", "per_mode": "PerGame", "min_minutes": 100},
            limit=10,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} players")

        # Show top 5 scorers by PPG
        if "PTS" in df.columns:
            top_scorers = df.nlargest(5, "PTS")[["PLAYER_NAME", "GP", "PTS", "REB", "AST"]]
            print("\nTop 5 Scorers (PPG):")
            print(top_scorers.to_string(index=False))

        print("\n[OK] PASS: NCAA-MBB player_season (PerGame)")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 1.3: NCAA-WBB
    print("\n1.3 NCAA-WBB: Top scorers 2024-25")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_season",
            {"league": "NCAA-WBB", "season": "2025", "per_mode": "PerGame", "min_minutes": 50},
            limit=5,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} players")
        print(f"[OK] Columns: {list(df.columns)}")

        if "PTS" in df.columns:
            print("\nTop 5 Scorers:")
            print(df[["PLAYER_NAME", "GP", "PTS", "REB", "AST"]].to_string(index=False))

        print("\n[OK] PASS: NCAA-WBB player_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 1.4: EuroLeague
    print("\n1.4 EuroLeague: Top scorers 2024")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_season",
            {"league": "EuroLeague", "season": "2024", "per_mode": "PerGame"},
            limit=10,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} players")
        print(f"[OK] Columns: {list(df.columns)}")

        if "PTS" in df.columns:
            print("\nTop 5 Scorers:")
            print(
                df.nlargest(5, "PTS")[["PLAYER_NAME", "GP", "PTS", "REB", "AST"]].to_string(
                    index=False
                )
            )

        print("\n[OK] PASS: EuroLeague player_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    return True


def test_team_season() -> bool:
    """Test team_season dataset across all leagues"""
    print("\n" + "=" * 70)
    print("TEST 2: team_season Dataset")
    print("=" * 70)

    # Test 2.1: NCAA-MBB
    print("\n2.1 NCAA-MBB: Team season stats 2024-25")
    print("-" * 70)
    try:
        df = get_dataset("team_season", {"league": "NCAA-MBB", "season": "2025"}, limit=20)

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} teams")
        print(f"[OK] Columns: {list(df.columns)}")

        # Show top 5 teams by points
        if "PTS" in df.columns:
            top_teams = df.nlargest(5, "PTS")[["TEAM_NAME", "GP", "PTS"]]
            print("\nTop 5 Teams by Total Points:")
            print(top_teams.to_string(index=False))

        print("\n[OK] PASS: NCAA-MBB team_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 2.2: NCAA-WBB
    print("\n2.2 NCAA-WBB: Team season stats 2024-25")
    print("-" * 70)
    try:
        df = get_dataset("team_season", {"league": "NCAA-WBB", "season": "2025"}, limit=10)

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} teams")
        print(f"[OK] Columns: {list(df.columns)}")

        print("\n[OK] PASS: NCAA-WBB team_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 2.3: EuroLeague
    print("\n2.3 EuroLeague: Team season stats 2024")
    print("-" * 70)
    try:
        df = get_dataset("team_season", {"league": "EuroLeague", "season": "2024"}, limit=18)

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} teams")
        print(f"[OK] Columns: {list(df.columns)}")

        # Show top teams
        if "PTS" in df.columns:
            print("\nTop 5 Teams by Total Points:")
            print(df.nlargest(5, "PTS")[["TEAM_NAME", "GP", "PTS"]].to_string(index=False))

        print("\n[OK] PASS: EuroLeague team_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    return True


def test_player_team_season() -> bool:
    """Test player_team_season dataset (captures mid-season transfers)"""
    print("\n" + "=" * 70)
    print("TEST 3: player_team_season Dataset (Transfer Portal Tracking)")
    print("=" * 70)

    # Test 3.1: NCAA-MBB
    print("\n3.1 NCAA-MBB: Player × Team × Season stats")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_team_season",
            {"league": "NCAA-MBB", "season": "2025", "per_mode": "Totals", "min_minutes": 50},
            limit=20,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} player-team combinations")
        print(f"[OK] Columns: {list(df.columns)}")

        # Verify TEAM_ID or TEAM_NAME is in columns (key difference from player_season)
        has_team_col = any(col in df.columns for col in ["TEAM_ID", "TEAM_NAME"])
        if not has_team_col:
            print("[FAIL] FAIL: Missing team column (TEAM_ID or TEAM_NAME)")
            return False

        print("[OK] Contains team context (tracks transfers)")

        # Show sample
        if "PLAYER_NAME" in df.columns and "PTS" in df.columns:
            print("\nSample Player-Team-Season Stats:")
            sample_cols = [
                c
                for c in ["PLAYER_NAME", "TEAM_NAME", "GP", "PTS", "REB", "AST"]
                if c in df.columns
            ]
            print(df.head(5)[sample_cols].to_string(index=False))

        print("\n[OK] PASS: NCAA-MBB player_team_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 3.2: NCAA-WBB
    print("\n3.2 NCAA-WBB: Player × Team × Season stats")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_team_season",
            {"league": "NCAA-WBB", "season": "2025", "per_mode": "PerGame"},
            limit=10,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} player-team combinations")

        print("\n[OK] PASS: NCAA-WBB player_team_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    # Test 3.3: EuroLeague
    print("\n3.3 EuroLeague: Player × Team × Season stats")
    print("-" * 70)
    try:
        df = get_dataset(
            "player_team_season",
            {"league": "EuroLeague", "season": "2024", "per_mode": "PerGame"},
            limit=20,
        )

        if df.empty:
            print("[FAIL] FAIL: No data returned")
            return False

        print(f"[OK] Returned {len(df)} player-team combinations")

        print("\n[OK] PASS: EuroLeague player_team_season")
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False

    return True


def test_dataset_registry() -> bool:
    """Verify the 3 new datasets are properly registered by attempting to call them"""
    print("\n" + "=" * 70)
    print("TEST 4: Dataset Registry Verification")
    print("=" * 70)

    datasets_to_check = [
        ("player_season", {"league": "NCAA-MBB", "season": "2025"}),
        ("team_season", {"league": "NCAA-MBB", "season": "2025"}),
        ("player_team_season", {"league": "NCAA-MBB", "season": "2025"}),
    ]

    for dataset_id, filters in datasets_to_check:
        print(f"\nChecking '{dataset_id}' can be called...")

        # Try to call the dataset (this verifies registration)
        try:
            _ = get_dataset(dataset_id, filters, limit=1)
            print(f"[OK] '{dataset_id}' is registered and callable")
        except KeyError as e:
            print(f"[FAIL] '{dataset_id}' not found in registry: {e}")
            return False
        except Exception as e:
            print(f"[FAIL] Error calling '{dataset_id}': {e}")
            return False

    print("\n[PASS] All 3 datasets properly registered")
    return True


def main() -> int:
    """Run all tests"""
    print("\n" + "=" * 70)
    print("PHASE 3.3: SEASON AGGREGATE DATASETS - TEST SUITE")
    print("=" * 70)
    print("\nTesting 3 new datasets:")
    print("  1. player_season - Player season totals/averages")
    print("  2. team_season - Team season totals/averages")
    print("  3. player_team_season - Player × Team season stats (transfers)")
    print("\nAcross 3 leagues: NCAA-MBB, NCAA-WBB, EuroLeague")

    results = []

    # Run tests
    results.append(("Dataset Registry", test_dataset_registry()))
    results.append(("player_season", test_player_season()))
    results.append(("team_season", test_team_season()))
    results.append(("player_team_season", test_player_team_season()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED - Phase 3.3 Complete!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
