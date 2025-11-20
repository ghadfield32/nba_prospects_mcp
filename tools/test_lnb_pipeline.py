"""Test LNB Pipeline - Verify Data Flows Through All Paths

Tests that data for all LNB divisions correctly flows through:
1. Normalized tables (player_game, team_game)
2. Unified fetchers
3. API get_dataset calls
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd


def test_normalized_data():
    """Check what's in the normalized tables"""
    print("=" * 70)
    print("TEST 1: Normalized Data Tables")
    print("=" * 70)

    normalized_dir = Path("data/normalized/lnb")

    # Check player_game
    player_game_dir = normalized_dir / "player_game"
    if player_game_dir.exists():
        files = list(player_game_dir.glob("**/*.parquet"))
        print(f"\n  player_game: {len(files)} files")

        if files:
            # Load and check leagues
            dfs = []
            for f in files[:100]:  # Sample first 100
                try:
                    df = pd.read_parquet(f)
                    dfs.append(df)
                except Exception as e:
                    print(f"    [ERROR] {f.name}: {e}")

            if dfs:
                combined = pd.concat(dfs, ignore_index=True)
                if "LEAGUE" in combined.columns:
                    league_counts = combined["LEAGUE"].value_counts()
                    print("    Leagues found:")
                    for league, count in league_counts.items():
                        print(f"      {league}: {count} rows")
                else:
                    print("    [WARN] No LEAGUE column found")
    else:
        print(f"\n  player_game: [NOT FOUND] {player_game_dir}")

    # Check team_game
    team_game_dir = normalized_dir / "team_game"
    if team_game_dir.exists():
        files = list(team_game_dir.glob("**/*.parquet"))
        print(f"\n  team_game: {len(files)} files")
    else:
        print("\n  team_game: [NOT FOUND]")


def test_unified_fetchers():
    """Test the unified fetcher functions"""
    print("\n" + "=" * 70)
    print("TEST 2: Unified Fetchers")
    print("=" * 70)

    from cbb_data.fetchers import lnb

    leagues_to_test = [
        ("LNB_PROA", lnb.fetch_lnb_player_game_normalized),
        ("LNB_ELITE2", lnb.fetch_elite2_player_game),
        ("LNB_ESPOIRS_ELITE", lnb.fetch_espoirs_elite_player_game),
        ("LNB_ESPOIRS_PROB", lnb.fetch_espoirs_prob_player_game),
    ]

    for league_name, fetcher in leagues_to_test:
        print(f"\n  {league_name}:")
        try:
            df = fetcher(season="2024-2025")
            print(f"    player_game: {len(df)} rows")
            if not df.empty and "LEAGUE" in df.columns:
                leagues = df["LEAGUE"].unique()
                print(f"    LEAGUE values: {list(leagues)}")
        except Exception as e:
            print(f"    [ERROR] {type(e).__name__}: {e}")


def test_api_get_dataset():
    """Test API-level get_dataset calls"""
    print("\n" + "=" * 70)
    print("TEST 3: API get_dataset() Calls")
    print("=" * 70)

    from cbb_data.api.datasets import get_dataset

    leagues_to_test = ["LNB_PROA", "LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]
    datasets_to_test = ["player_game", "team_game", "pbp", "shots"]

    for league in leagues_to_test:
        print(f"\n  {league}:")
        for dataset in datasets_to_test:
            try:
                df = get_dataset(dataset, league=league, season="2024-2025")
                status = f"{len(df)} rows" if not df.empty else "empty"
                print(f"    {dataset}: {status}")
            except Exception as e:
                print(f"    {dataset}: [ERROR] {type(e).__name__}")


def test_raw_data():
    """Check what's in raw data directories"""
    print("\n" + "=" * 70)
    print("TEST 4: Raw Data (PBP/Shots)")
    print("=" * 70)

    raw_dir = Path("data/raw/lnb")

    for data_type in ["pbp", "shots"]:
        type_dir = raw_dir / data_type
        if type_dir.exists():
            season_dirs = list(type_dir.glob("season=*"))
            for season_dir in season_dirs:
                files = list(season_dir.glob("*.parquet"))
                print(f"\n  {data_type}/{season_dir.name}: {len(files)} files")

                if files:
                    # Check leagues in first few files
                    leagues_found = set()
                    for f in files[:10]:
                        try:
                            df = pd.read_parquet(f)
                            if "LEAGUE" in df.columns:
                                leagues_found.update(df["LEAGUE"].unique())
                        except Exception:
                            pass
                    if leagues_found:
                        print(f"    Leagues: {sorted(leagues_found)}")
        else:
            print(f"\n  {data_type}: [NOT FOUND]")


def main():
    print("=" * 70)
    print("LNB PIPELINE VERIFICATION TEST")
    print("=" * 70)

    test_raw_data()
    test_normalized_data()
    test_unified_fetchers()
    test_api_get_dataset()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
