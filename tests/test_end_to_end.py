"""End-to-end test of all datasets with real data

This script tests the complete pipeline:
1. List available datasets
2. Fetch data from each dataset
3. Validate data quality
4. Check historical depth

Run: python tests/test_end_to_end.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, timedelta, date
import pandas as pd

from cbb_data import get_dataset, list_datasets


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70 + "\n")


def test_list_datasets():
    """Test listing all available datasets"""
    print_section("TEST 1: List Available Datasets")

    datasets = list_datasets()

    print(f"Found {len(datasets)} datasets:\n")

    for ds in datasets:
        print(f"  [{ds['id']}]")
        print(f"    Description: {ds['description']}")
        print(f"    Sources: {', '.join(ds['sources'])}")
        print(f"    Leagues: {', '.join(ds['leagues'])}")
        print(f"    Keys: {', '.join(ds['keys'])}")
        print(f"    Filters: {', '.join(ds['supports'][:5])}...")
        print(f"    Requires game_id: {ds['requires_game_id']}")
        print()

    return len(datasets) > 0


def test_espn_mbb_schedule():
    """Test ESPN MBB schedule"""
    print_section("TEST 2: ESPN Men's Basketball Schedule")

    try:
        # Today's games
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        print(f"Fetching schedule for {today}...")

        df = get_dataset(
            "schedule",
            {
                "league": "NCAA-MBB",
                "date": {"from": str(today), "to": str(tomorrow)}
            }
        )

        print(f"\nFound {len(df)} games")

        if not df.empty:
            print("\nSample games:")
            cols = ["GAME_DATE", "HOME_TEAM_NAME", "AWAY_TEAM_NAME", "STATUS"]
            print(df[cols].head(5).to_string(index=False))

            # Check historical depth
            print("\n\nChecking historical data depth...")
            old_date = date(2010, 1, 1)
            old_end = old_date + timedelta(days=7)

            hist_df = get_dataset(
                "schedule",
                {
                    "league": "NCAA-MBB",
                    "date": {"from": str(old_date), "to": str(old_end)}
                }
            )

            if not hist_df.empty:
                print(f"[OK] Historical data available (2010): {len(hist_df)} games")
                min_date = hist_df["GAME_DATE"].min()
                max_date = hist_df["GAME_DATE"].max()
                print(f"  Date range: {min_date} to {max_date}")
            else:
                print("[X] No historical data for 2010")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_espn_wbb_schedule():
    """Test ESPN WBB schedule"""
    print_section("TEST 3: ESPN Women's Basketball Schedule")

    try:
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        print(f"Fetching WBB schedule for {today}...")

        df = get_dataset(
            "schedule",
            {
                "league": "NCAA-WBB",
                "date": {"from": str(today), "to": str(tomorrow)}
            }
        )

        print(f"\nFound {len(df)} games")

        if not df.empty:
            print("\nSample games:")
            cols = ["GAME_DATE", "HOME_TEAM_NAME", "AWAY_TEAM_NAME", "STATUS"]
            print(df[cols].head(5).to_string(index=False))

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_espn_mbb_player_game():
    """Test ESPN MBB player/game data"""
    print_section("TEST 4: ESPN MBB Player Game Stats")

    try:
        # Get a recent completed game
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        print(f"Finding recent completed games...")

        schedule = get_dataset(
            "schedule",
            {
                "league": "NCAA-MBB",
                "date": {"from": str(week_ago), "to": str(today)}
            }
        )

        # Filter for completed games
        completed = schedule[schedule["STATUS"].str.contains("Final", case=False, na=False)]

        if completed.empty:
            print("No completed games found in last week")
            return False

        # Get box score for first game
        game_id = completed.iloc[0]["GAME_ID"]
        print(f"\nFetching player stats for game {game_id}...")

        df = get_dataset(
            "player_game",
            {
                "league": "NCAA-MBB",
                "game_ids": [game_id]
            }
        )

        print(f"\nFound {len(df)} player stats")

        if not df.empty:
            print("\nTop scorers:")
            cols = ["PLAYER_NAME", "TEAM_NAME", "PTS", "REB", "AST", "MIN"]
            print(df.nlargest(10, "PTS")[cols].to_string(index=False))

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_espn_pbp():
    """Test ESPN play-by-play"""
    print_section("TEST 5: ESPN MBB Play-by-Play")

    try:
        # Get a recent completed game
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        schedule = get_dataset(
            "schedule",
            {
                "league": "NCAA-MBB",
                "date": {"from": str(week_ago), "to": str(today)}
            }
        )

        completed = schedule[schedule["STATUS"].str.contains("Final", case=False, na=False)]

        if completed.empty:
            print("No completed games found")
            return False

        game_id = completed.iloc[0]["GAME_ID"]
        print(f"Fetching play-by-play for game {game_id}...")

        df = get_dataset(
            "pbp",
            {
                "league": "NCAA-MBB",
                "game_ids": [game_id]
            }
        )

        print(f"\nFound {len(df)} plays")

        if not df.empty:
            print("\nSample plays:")
            cols = ["PERIOD", "CLOCK", "PLAY_TYPE", "TEXT"]
            print(df[cols].head(10).to_string(index=False))

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_euroleague_schedule():
    """Test EuroLeague schedule"""
    print_section("TEST 6: EuroLeague Schedule")

    try:
        print("Fetching EuroLeague 2024 Regular Season schedule...")

        df = get_dataset(
            "schedule",
            {
                "league": "EuroLeague",
                "season": "E2024",
                "season_type": "Regular Season"
            }
        )

        print(f"\nFound {len(df)} games")

        if not df.empty:
            print("\nSample games:")
            cols = ["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE"]
            print(df[cols].head(10).to_string(index=False))

            # Check data depth
            print(f"\nSeason date range: {df['GAME_DATE'].min()} to {df['GAME_DATE'].max()}")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_euroleague_player_game():
    """Test EuroLeague player stats"""
    print_section("TEST 7: EuroLeague Player Game Stats")

    try:
        # Get schedule first
        schedule = get_dataset(
            "schedule",
            {
                "league": "EuroLeague",
                "season": "E2024",
                "season_type": "Regular Season"
            }
        )

        if schedule.empty:
            print("No games found")
            return False

        # Get box score for first game
        game_code = schedule.iloc[0]["GAME_CODE"]
        print(f"Fetching player stats for game {game_code}...")

        df = get_dataset(
            "player_game",
            {
                "league": "EuroLeague",
                "season": "E2024",
                "game_ids": [game_code]
            }
        )

        print(f"\nFound {len(df)} player stats")

        if not df.empty:
            print("\nTop performers (by Valuation):")
            cols = ["PLAYER_NAME", "TEAM", "PTS", "REB", "AST", "VALUATION"]
            if "VALUATION" in df.columns:
                print(df.nlargest(10, "VALUATION")[cols].to_string(index=False))
            else:
                print(df[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]].head(10).to_string(index=False))

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_euroleague_shots():
    """Test EuroLeague shot data"""
    print_section("TEST 8: EuroLeague Shot Data")

    try:
        # Get a game
        schedule = get_dataset(
            "schedule",
            {
                "league": "EuroLeague",
                "season": "E2024",
                "season_type": "Regular Season"
            }
        )

        if schedule.empty:
            print("No games found")
            return False

        game_code = schedule.iloc[0]["GAME_CODE"]
        print(f"Fetching shot data for game {game_code}...")

        df = get_dataset(
            "shots",
            {
                "league": "EuroLeague",
                "season": "E2024",
                "game_ids": [game_code]
            }
        )

        print(f"\nFound {len(df)} shots")

        if not df.empty:
            print("\nShot summary:")
            print(f"  Total shots: {len(df)}")
            print(f"  Made: {df['SHOT_MADE'].sum()}")
            print(f"  FG%: {df['SHOT_MADE'].sum() / len(df) * 100:.1f}%")

            print("\nSample shots:")
            cols = ["PLAYER_NAME", "SHOT_TYPE", "POINTS_VALUE", "SHOT_MADE", "LOC_X", "LOC_Y"]
            print(df[cols].head(10).to_string(index=False))

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print_section("COLLEGE & INTERNATIONAL BASKETBALL DATA PIPELINE TEST")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # Run tests
    results["List Datasets"] = test_list_datasets()
    results["ESPN MBB Schedule"] = test_espn_mbb_schedule()
    results["ESPN WBB Schedule"] = test_espn_wbb_schedule()
    results["ESPN MBB Player Stats"] = test_espn_mbb_player_game()
    results["ESPN MBB Play-by-Play"] = test_espn_pbp()
    results["EuroLeague Schedule"] = test_euroleague_schedule()
    results["EuroLeague Player Stats"] = test_euroleague_player_game()
    results["EuroLeague Shots"] = test_euroleague_shots()

    # Summary
    print_section("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status:8} {test}")

    print(f"\n{passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED")
        return 0
    else:
        print("\n[FAIL] SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
