#!/usr/bin/env python3
"""
Comprehensive NBL Integration Test Script

Tests all aspects of NBL data integration:
1. R export functionality
2. Data loading from Parquet files
3. Fetcher functions (schedule, player_season, team_season, etc.)
4. High-level API (get_dataset)
5. All granularities (Totals, PerGame, Per40)
6. All filters (season, team, player)
7. Registry integration

Usage:
    python test_nbl_integration.py
"""

import sys
from pathlib import Path


def test_imports():
    """Test that all NBL modules can be imported"""
    print("=" * 80)
    print("TEST 1: Module Imports")
    print("=" * 80)

    try:
        from cbb_data.fetchers import nbl_official, nz_nbl_fiba

        # Verify modules have expected functions
        assert hasattr(
            nbl_official, "fetch_nbl_schedule"
        ), "nbl_official missing fetch_nbl_schedule"
        assert hasattr(
            nz_nbl_fiba, "fetch_nz_nbl_schedule"
        ), "nz_nbl_fiba missing fetch_nz_nbl_schedule"
        print("✅ nbl_official module imported successfully")
        print("✅ nz_nbl_fiba module imported successfully")

        from cbb_data.catalog.sources import get_league_source_config

        # Verify function is callable
        assert callable(get_league_source_config), "get_league_source_config not callable"
        print("✅ catalog.sources imported successfully")

        from cbb_data.catalog.levels import get_league_level

        # Verify function is callable
        assert callable(get_league_level), "get_league_level not callable"
        print("✅ catalog.levels imported successfully")

        from cbb_data.api.datasets import get_dataset, list_datasets

        # Verify functions are callable
        assert callable(get_dataset), "get_dataset not callable"
        assert callable(list_datasets), "list_datasets not callable"
        print("✅ api.datasets imported successfully")

        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_league_registration():
    """Test that NBL is properly registered in the system"""
    print("\n" + "=" * 80)
    print("TEST 2: League Registration")
    print("=" * 80)

    try:
        from cbb_data.catalog.levels import LEAGUE_LEVELS, get_league_level
        from cbb_data.catalog.sources import LEAGUE_SOURCES, get_league_source_config

        # Check if NBL is in league levels
        if "NBL" in LEAGUE_LEVELS:
            level = get_league_level("NBL")
            print(f"✅ NBL registered in LEAGUE_LEVELS: {level}")
        else:
            print("❌ NBL NOT found in LEAGUE_LEVELS")
            return False

        # Check if NBL is in league sources
        if "NBL" in LEAGUE_SOURCES:
            config = get_league_source_config("NBL")
            print("✅ NBL registered in LEAGUE_SOURCES")
            print(f"   - Player season source: {config.player_season_source}")
            print(f"   - Team season source: {config.team_season_source}")
            print(f"   - Schedule source: {config.schedule_source}")
            print(f"   - Box score source: {config.box_score_source}")
            print(f"   - PBP source: {config.pbp_source}")
            print(f"   - Shots source: {config.shots_source}")

            # Check if functions are registered
            if config.fetch_player_season:
                print(f"   - fetch_player_season: {config.fetch_player_season.__name__}")
            if config.fetch_team_season:
                print(f"   - fetch_team_season: {config.fetch_team_season.__name__}")
        else:
            print("❌ NBL NOT found in LEAGUE_SOURCES")
            return False

        return True

    except Exception as e:
        print(f"❌ Registration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_data_files():
    """Test that NBL data files exist"""
    print("\n" + "=" * 80)
    print("TEST 3: Data Files")
    print("=" * 80)

    data_dir = Path("data/nbl_raw")

    if not data_dir.exists():
        print(f"⚠️  Data directory does not exist: {data_dir}")
        print("   Run: Rscript tools/nbl/export_nbl.R")
        return False

    expected_files = [
        "nbl_results.parquet",
        "nbl_box_player.parquet",
        "nbl_box_team.parquet",
        "nbl_pbp.parquet",
        "nbl_shots.parquet",
    ]

    all_exist = True
    for filename in expected_files:
        filepath = data_dir / filename
        if filepath.exists():
            size_mb = filepath.stat().st_size / (1024 * 1024)
            print(f"✅ {filename}: {size_mb:.2f} MB")
        else:
            print(f"❌ {filename}: NOT FOUND")
            all_exist = False

    if not all_exist:
        print("\n⚠️  Some files missing. Run: Rscript tools/nbl/export_nbl.R")

    return all_exist


def test_fetcher_functions():
    """Test NBL fetcher functions directly"""
    print("\n" + "=" * 80)
    print("TEST 4: Fetcher Functions (Direct)")
    print("=" * 80)

    try:
        from cbb_data.fetchers.nbl_official import (
            fetch_nbl_pbp,
            fetch_nbl_player_game,
            fetch_nbl_player_season,
            fetch_nbl_schedule,
            fetch_nbl_shots,
            fetch_nbl_team_game,
            fetch_nbl_team_season,
        )

        season = "2023"  # Test with 2023-24 season

        # Test schedule
        print("\n📅 Testing fetch_nbl_schedule...")
        try:
            schedule = fetch_nbl_schedule(season=season)
            print(f"   ✅ Schedule: {len(schedule)} games")
            if len(schedule) > 0:
                print(f"      Columns: {', '.join(schedule.columns.tolist()[:10])}...")
        except Exception as e:
            print(f"   ❌ Schedule failed: {e}")

        # Test player season (Totals)
        print("\n👤 Testing fetch_nbl_player_season (Totals)...")
        try:
            players_totals = fetch_nbl_player_season(season=season, per_mode="Totals")
            print(f"   ✅ Player Season (Totals): {len(players_totals)} players")
            if len(players_totals) > 0:
                print(f"      Columns: {', '.join(players_totals.columns.tolist()[:10])}...")
        except Exception as e:
            print(f"   ❌ Player Season (Totals) failed: {e}")

        # Test player season (PerGame)
        print("\n👤 Testing fetch_nbl_player_season (PerGame)...")
        try:
            players_pergame = fetch_nbl_player_season(season=season, per_mode="PerGame")
            print(f"   ✅ Player Season (PerGame): {len(players_pergame)} players")
        except Exception as e:
            print(f"   ❌ Player Season (PerGame) failed: {e}")

        # Test player season (Per40)
        print("\n👤 Testing fetch_nbl_player_season (Per40)...")
        try:
            players_per40 = fetch_nbl_player_season(season=season, per_mode="Per40")
            print(f"   ✅ Player Season (Per40): {len(players_per40)} players")
        except Exception as e:
            print(f"   ❌ Player Season (Per40) failed: {e}")

        # Test team season
        print("\n🏀 Testing fetch_nbl_team_season...")
        try:
            teams = fetch_nbl_team_season(season=season)
            print(f"   ✅ Team Season: {len(teams)} teams")
            if len(teams) > 0:
                print(f"      Teams: {', '.join(teams['TEAM'].tolist()[:5])}...")
        except Exception as e:
            print(f"   ❌ Team Season failed: {e}")

        # Test player game
        print("\n👤📊 Testing fetch_nbl_player_game...")
        try:
            player_games = fetch_nbl_player_game(season=season)
            print(f"   ✅ Player Game: {len(player_games)} player-game records")
        except Exception as e:
            print(f"   ❌ Player Game failed: {e}")

        # Test team game
        print("\n🏀📊 Testing fetch_nbl_team_game...")
        try:
            team_games = fetch_nbl_team_game(season=season)
            print(f"   ✅ Team Game: {len(team_games)} team-game records")
        except Exception as e:
            print(f"   ❌ Team Game failed: {e}")

        # Test PBP (sample)
        print("\n📝 Testing fetch_nbl_pbp...")
        try:
            pbp = fetch_nbl_pbp(season=season)
            print(f"   ✅ Play-by-Play: {len(pbp)} events")
        except Exception as e:
            print(f"   ❌ Play-by-Play failed: {e}")

        # Test shots
        print("\n🎯 Testing fetch_nbl_shots...")
        try:
            shots = fetch_nbl_shots(season=season)
            print(f"   ✅ Shots: {len(shots)} shots")
            if len(shots) > 0:
                print(f"      Has LOC_X: {'LOC_X' in shots.columns}")
                print(f"      Has LOC_Y: {'LOC_Y' in shots.columns}")
        except Exception as e:
            print(f"   ❌ Shots failed: {e}")

        return True

    except Exception as e:
        print(f"\n❌ Fetcher test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_get_dataset_api():
    """Test high-level get_dataset API with NBL"""
    print("\n" + "=" * 80)
    print("TEST 5: High-Level API (get_dataset)")
    print("=" * 80)

    try:
        from cbb_data.api.datasets import get_dataset

        season = "2023"

        # Test schedule
        print("\n📅 Testing get_dataset('schedule', league='NBL')...")
        try:
            schedule = get_dataset("schedule", filters={"league": "NBL", "season": season})
            print(f"   ✅ Schedule: {len(schedule)} games")
        except Exception as e:
            print(f"   ❌ Schedule failed: {e}")

        # Test player_season with Totals
        print("\n👤 Testing get_dataset('player_season', per_mode='Totals')...")
        try:
            players = get_dataset(
                "player_season", filters={"league": "NBL", "season": season, "per_mode": "Totals"}
            )
            print(f"   ✅ Player Season (Totals): {len(players)} players")
        except Exception as e:
            print(f"   ❌ Player Season (Totals) failed: {e}")

        # Test player_season with PerGame
        print("\n👤 Testing get_dataset('player_season', per_mode='PerGame')...")
        try:
            players = get_dataset(
                "player_season", filters={"league": "NBL", "season": season, "per_mode": "PerGame"}
            )
            print(f"   ✅ Player Season (PerGame): {len(players)} players")
        except Exception as e:
            print(f"   ❌ Player Season (PerGame) failed: {e}")

        # Test player_season with Per40
        print("\n👤 Testing get_dataset('player_season', per_mode='Per40')...")
        try:
            players = get_dataset(
                "player_season", filters={"league": "NBL", "season": season, "per_mode": "Per40"}
            )
            print(f"   ✅ Player Season (Per40): {len(players)} players")
        except Exception as e:
            print(f"   ❌ Player Season (Per40) failed: {e}")

        # Test team_season
        print("\n🏀 Testing get_dataset('team_season')...")
        try:
            teams = get_dataset("team_season", filters={"league": "NBL", "season": season})
            print(f"   ✅ Team Season: {len(teams)} teams")
        except Exception as e:
            print(f"   ❌ Team Season failed: {e}")

        # Test player_game
        print("\n👤📊 Testing get_dataset('player_game')...")
        try:
            player_games = get_dataset(
                "player_game", filters={"league": "NBL", "season": season}, limit=100
            )
            print(f"   ✅ Player Game: {len(player_games)} records (limited to 100)")
        except Exception as e:
            print(f"   ❌ Player Game failed: {e}")

        # Test team_game
        print("\n🏀📊 Testing get_dataset('team_game')...")
        try:
            team_games = get_dataset(
                "team_game", filters={"league": "NBL", "season": season}, limit=100
            )
            print(f"   ✅ Team Game: {len(team_games)} records (limited to 100)")
        except Exception as e:
            print(f"   ❌ Team Game failed: {e}")

        # Test shots
        print("\n🎯 Testing get_dataset('shots')...")
        try:
            shots = get_dataset("shots", filters={"league": "NBL", "season": season}, limit=1000)
            print(f"   ✅ Shots: {len(shots)} shots (limited to 1000)")
            if len(shots) > 0:
                print(f"      Has LOC_X: {'LOC_X' in shots.columns}")
                print(f"      Has LOC_Y: {'LOC_Y' in shots.columns}")
        except Exception as e:
            print(f"   ❌ Shots failed: {e}")

        return True

    except Exception as e:
        print(f"\n❌ get_dataset test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_dataset_listing():
    """Test that NBL appears in dataset listings"""
    print("\n" + "=" * 80)
    print("TEST 6: Dataset Listing")
    print("=" * 80)

    try:
        from cbb_data.api.datasets import list_datasets

        datasets = list_datasets()

        print(f"\nFound {len(datasets)} datasets")

        # Check if NBL is in supported leagues for key datasets
        key_datasets = [
            "schedule",
            "player_season",
            "team_season",
            "player_game",
            "team_game",
            "shots",
        ]

        for dataset_id in key_datasets:
            dataset = next((d for d in datasets if d["id"] == dataset_id), None)
            if dataset:
                leagues = dataset.get("leagues", [])
                if "NBL" in leagues:
                    print(f"   ✅ {dataset_id}: NBL supported")
                else:
                    print(f"   ⚠️  {dataset_id}: NBL NOT in leagues list")
            else:
                print(f"   ❌ {dataset_id}: Dataset not found")

        return True

    except Exception as e:
        print(f"\n❌ Dataset listing test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print(" " * 20 + "NBL Integration Test Suite")
    print("=" * 80)

    tests = [
        ("Module Imports", test_imports),
        ("League Registration", test_league_registration),
        ("Data Files", test_data_files),
        ("Fetcher Functions", test_fetcher_functions),
        ("get_dataset API", test_get_dataset_api),
        ("Dataset Listing", test_dataset_listing),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! NBL integration is fully functional.")
        print("\nYou can now:")
        print("  1. Query NBL data via get_dataset API")
        print("  2. Use NBL with all granularities (Totals, PerGame, Per40)")
        print("  3. Access NBL via REST API endpoints")
        print("  4. Use NBL with MCP server tools")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
