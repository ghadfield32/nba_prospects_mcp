#!/usr/bin/env python3
"""Reconciliation Gate for Elite 2 Historical Data

Validates data quality and completeness for 2021-22 and 2022-23 Elite 2 seasons.

Invariants checked:
1. Coverage: All indexed games have PBP and shots data
2. Correctness: No duplicate game IDs, valid date ranges
3. Schema: Required columns present, valid data types
4. Reconciliation: Index ↔ PBP ↔ Shots alignment

Usage:
    python tools/lnb/reconcile_elite2.py
"""

import io
import sys
from pathlib import Path

import pandas as pd

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Expected data for Elite 2
EXPECTED_GAMES = {
    "2021-2022": 306,
    "2022-2023": 306,
}

EXPECTED_DATE_RANGES = {
    "2021-2022": ("2021-10-01", "2022-06-01"),
    "2022-2023": ("2022-10-01", "2023-06-01"),
}

# Schema requirements
REQUIRED_INDEX_COLUMNS = {
    "season",
    "league",
    "competition",
    "game_id",
    "game_date",
    "home_team_name",
    "away_team_name",
    "has_pbp",
    "has_shots",
}

REQUIRED_PBP_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "EVENT_TYPE",
    "HOME_SCORE",
    "AWAY_SCORE",
}

REQUIRED_SHOTS_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "SHOT_TYPE",
    "SUCCESS",
    "X_COORD",
    "Y_COORD",
}


class ReconciliationError(Exception):
    """Raised when reconciliation invariant fails"""

    pass


def load_game_index() -> pd.DataFrame:
    """Load game index and filter to Elite 2"""
    index_path = Path("data/raw/lnb/lnb_game_index.parquet")
    if not index_path.exists():
        raise ReconciliationError(f"Game index not found: {index_path}")

    df = pd.read_parquet(index_path)

    # Filter to Elite 2 2021-22 and 2022-23
    df = df[(df["league"] == "elite_2") & (df["season"].isin(["2021-2022", "2022-2023"]))]

    return df


def check_coverage(index_df: pd.DataFrame) -> dict:
    """Check that all indexed games have PBP and shots data"""
    print("\n" + "=" * 80)
    print("  COVERAGE CHECK")
    print("=" * 80)

    results = {}

    # Check game counts per season
    for season, expected_count in EXPECTED_GAMES.items():
        actual_count = len(index_df[index_df["season"] == season])
        status = "✅" if actual_count == expected_count else "❌"
        print(f"{status} {season}: {actual_count}/{expected_count} games")

        if actual_count != expected_count:
            raise ReconciliationError(
                f"Season {season} has {actual_count} games, expected {expected_count}"
            )

        results[f"{season}_games"] = actual_count

    # Check PBP coverage
    pbp_coverage = index_df["has_pbp"].sum()
    pbp_pct = pbp_coverage / len(index_df) * 100
    status = "✅" if pbp_coverage == len(index_df) else "❌"
    print(f"\n{status} PBP coverage: {pbp_coverage}/{len(index_df)} ({pbp_pct:.1f}%)")

    if pbp_coverage < len(index_df):
        missing = index_df[~index_df["has_pbp"]]
        print(f"   Missing PBP for {len(missing)} games:")
        for _, row in missing.head(5).iterrows():
            print(f"     - {row['season']} {row['game_id'][:20]}...")

    # Check shots coverage
    shots_coverage = index_df["has_shots"].sum()
    shots_pct = shots_coverage / len(index_df) * 100
    status = "✅" if shots_coverage == len(index_df) else "❌"
    print(f"{status} Shots coverage: {shots_coverage}/{len(index_df)} ({shots_pct:.1f}%)")

    if shots_coverage < len(index_df):
        missing = index_df[~index_df["has_shots"]]
        print(f"   Missing shots for {len(missing)} games:")
        for _, row in missing.head(5).iterrows():
            print(f"     - {row['season']} {row['game_id'][:20]}...")

    results["pbp_coverage"] = pbp_coverage
    results["shots_coverage"] = shots_coverage

    if pbp_coverage < len(index_df) or shots_coverage < len(index_df):
        raise ReconciliationError("Incomplete PBP or shots coverage")

    return results


def check_correctness(index_df: pd.DataFrame) -> dict:
    """Check data correctness: no duplicates, valid dates"""
    print("\n" + "=" * 80)
    print("  CORRECTNESS CHECK")
    print("=" * 80)

    results = {}

    # Check for duplicate game IDs
    duplicates = index_df[index_df["game_id"].duplicated()]
    status = "✅" if len(duplicates) == 0 else "❌"
    print(f"{status} No duplicate game IDs: {len(duplicates)} duplicates found")

    if len(duplicates) > 0:
        print("   Duplicate game IDs:")
        for game_id in duplicates["game_id"].head(5):
            print(f"     - {game_id}")
        raise ReconciliationError(f"Found {len(duplicates)} duplicate game IDs")

    # Check date ranges per season
    for season, (min_date, max_date) in EXPECTED_DATE_RANGES.items():
        season_df = index_df[index_df["season"] == season]

        # Convert game_date to datetime if needed
        if season_df["game_date"].dtype == "object":
            season_df = season_df.copy()
            season_df["game_date"] = pd.to_datetime(season_df["game_date"])

        actual_min = season_df["game_date"].min()
        actual_max = season_df["game_date"].max()

        in_range = pd.to_datetime(min_date) <= actual_min and actual_max <= pd.to_datetime(max_date)
        status = "✅" if in_range else "⚠️"
        print(
            f"{status} {season} dates: {actual_min.date()} to {actual_max.date()} "
            f"(expected {min_date} to {max_date})"
        )

        results[f"{season}_date_range"] = (
            str(actual_min.date()),
            str(actual_max.date()),
        )

    # Check competition names
    competitions = index_df["competition"].unique()
    expected_comp = "ELITE 2 (PROB)"
    status = "✅" if len(competitions) == 1 and competitions[0] == expected_comp else "❌"
    print(
        f"{status} Competition name: {competitions[0] if len(competitions) == 1 else competitions}"
    )

    if not (len(competitions) == 1 and competitions[0] == expected_comp):
        raise ReconciliationError(
            f"Expected competition '{expected_comp}', got {list(competitions)}"
        )

    # Check league values
    leagues = index_df["league"].unique()
    expected_league = "elite_2"
    status = "✅" if len(leagues) == 1 and leagues[0] == expected_league else "❌"
    print(f"{status} League value: {leagues[0] if len(leagues) == 1 else leagues}")

    if not (len(leagues) == 1 and leagues[0] == expected_league):
        raise ReconciliationError(f"Expected league '{expected_league}', got {list(leagues)}")

    return results


def check_schema(index_df: pd.DataFrame) -> dict:
    """Check schema requirements"""
    print("\n" + "=" * 80)
    print("  SCHEMA CHECK")
    print("=" * 80)

    results = {}

    # Check index columns
    missing_cols = REQUIRED_INDEX_COLUMNS - set(index_df.columns)
    status = "✅" if len(missing_cols) == 0 else "❌"
    print(f"{status} Index has all required columns")

    if missing_cols:
        print(f"   Missing columns: {missing_cols}")
        raise ReconciliationError(f"Index missing columns: {missing_cols}")

    # Check data types
    type_checks = {
        "has_pbp": "bool",
        "has_shots": "bool",
        "has_boxscore": "bool",
    }

    for col, expected_type in type_checks.items():
        if col in index_df.columns:
            actual_type = str(index_df[col].dtype)
            status = "✅" if expected_type in actual_type else "⚠️"
            print(f"{status} {col}: {actual_type} (expected {expected_type})")

    # Sample PBP file and check schema
    pbp_dir = Path("data/raw/lnb/pbp/season=2021-2022")
    pbp_files = list(pbp_dir.glob("*.parquet"))

    if len(pbp_files) > 0:
        sample_pbp = pd.read_parquet(pbp_files[0])
        missing_pbp_cols = REQUIRED_PBP_COLUMNS - set(sample_pbp.columns)
        status = "✅" if len(missing_pbp_cols) == 0 else "❌"
        print(f"\n{status} PBP has all required columns")

        if missing_pbp_cols:
            print(f"   Missing PBP columns: {missing_pbp_cols}")
            raise ReconciliationError(f"PBP missing columns: {missing_pbp_cols}")

        results["pbp_sample_rows"] = len(sample_pbp)
    else:
        print("\n⚠️  No PBP files found for schema check")

    # Sample shots file and check schema
    shots_dir = Path("data/raw/lnb/shots/season=2021-2022")
    shots_files = list(shots_dir.glob("*.parquet"))

    if len(shots_files) > 0:
        sample_shots = pd.read_parquet(shots_files[0])
        missing_shots_cols = REQUIRED_SHOTS_COLUMNS - set(sample_shots.columns)
        status = "✅" if len(missing_shots_cols) == 0 else "❌"
        print(f"{status} Shots has all required columns")

        if missing_shots_cols:
            print(f"   Missing shots columns: {missing_shots_cols}")
            raise ReconciliationError(f"Shots missing columns: {missing_shots_cols}")

        results["shots_sample_rows"] = len(sample_shots)
    else:
        print("⚠️  No shots files found for schema check")

    return results


def check_reconciliation(index_df: pd.DataFrame) -> dict:
    """Check reconciliation: index ↔ PBP ↔ shots alignment"""
    print("\n" + "=" * 80)
    print("  RECONCILIATION CHECK")
    print("=" * 80)

    results = {}

    for season in ["2021-2022", "2022-2023"]:
        season_df = index_df[index_df["season"] == season]
        indexed_games = set(season_df["game_id"])

        # Get PBP game IDs
        pbp_dir = Path(f"data/raw/lnb/pbp/season={season}")
        pbp_files = list(pbp_dir.glob("*.parquet"))
        pbp_games = set()

        for pbp_file in pbp_files:
            # Extract game_id from filename: game_id=UUID.parquet
            game_id = pbp_file.stem.replace("game_id=", "")
            pbp_games.add(game_id)

        # Get shots game IDs
        shots_dir = Path(f"data/raw/lnb/shots/season={season}")
        shots_files = list(shots_dir.glob("*.parquet"))
        shots_games = set()

        for shots_file in shots_files:
            # Extract game_id from filename: game_id=UUID.parquet
            game_id = shots_file.stem.replace("game_id=", "")
            shots_games.add(game_id)

        # Check alignment
        indexed_count = len(indexed_games)
        pbp_count = len(pbp_games)
        shots_count = len(shots_games)

        print(f"\n{season}:")
        print(f"  Indexed: {indexed_count} games")
        print(f"  PBP:     {pbp_count} files")
        print(f"  Shots:   {shots_count} files")

        # Check for missing PBP
        missing_pbp = indexed_games - pbp_games
        status = "✅" if len(missing_pbp) == 0 else "❌"
        print(f"  {status} Missing PBP: {len(missing_pbp)} games")

        if missing_pbp:
            for game_id in list(missing_pbp)[:3]:
                print(f"       - {game_id[:20]}...")

        # Check for missing shots
        missing_shots = indexed_games - shots_games
        status = "✅" if len(missing_shots) == 0 else "❌"
        print(f"  {status} Missing shots: {len(missing_shots)} games")

        if missing_shots:
            for game_id in list(missing_shots)[:3]:
                print(f"       - {game_id[:20]}...")

        # Check for orphaned PBP files
        orphaned_pbp = pbp_games - indexed_games
        status = "✅" if len(orphaned_pbp) == 0 else "⚠️"
        print(f"  {status} Orphaned PBP: {len(orphaned_pbp)} files")

        # Check for orphaned shots files
        orphaned_shots = shots_games - indexed_games
        status = "✅" if len(orphaned_shots) == 0 else "⚠️"
        print(f"  {status} Orphaned shots: {len(orphaned_shots)} files")

        results[f"{season}_indexed"] = indexed_count
        results[f"{season}_pbp"] = pbp_count
        results[f"{season}_shots"] = shots_count
        results[f"{season}_missing_pbp"] = len(missing_pbp)
        results[f"{season}_missing_shots"] = len(missing_shots)

        if len(missing_pbp) > 0 or len(missing_shots) > 0:
            raise ReconciliationError(
                f"Season {season} has missing PBP ({len(missing_pbp)}) "
                f"or shots ({len(missing_shots)}) files"
            )

    return results


def main():
    """Run reconciliation gate"""
    print("\n" + "=" * 80)
    print("  ELITE 2 RECONCILIATION GATE - 2021-22 & 2022-23")
    print("=" * 80)

    try:
        # Load index
        index_df = load_game_index()
        print(f"\nLoaded {len(index_df)} Elite 2 games from index")

        # Run checks
        coverage_results = check_coverage(index_df)
        correctness_results = check_correctness(index_df)
        schema_results = check_schema(index_df)
        reconciliation_results = check_reconciliation(index_df)

        # Summary
        print("\n" + "=" * 80)
        print("  RECONCILIATION SUMMARY")
        print("=" * 80)
        print("\n✅ ALL CHECKS PASSED")
        print(f"\nTotal games validated: {len(index_df)}")
        print(f"  2021-2022: {len(index_df[index_df['season'] == '2021-2022'])} games")
        print(f"  2022-2023: {len(index_df[index_df['season'] == '2022-2023'])} games")
        print(f"\nPBP coverage: {coverage_results['pbp_coverage']}/{len(index_df)}")
        print(f"Shots coverage: {coverage_results['shots_coverage']}/{len(index_df)}")

        print("\n" + "=" * 80)
        print("  INVARIANTS LOCKED ✅")
        print("=" * 80)

        return 0

    except ReconciliationError as e:
        print("\n" + "=" * 80)
        print("  RECONCILIATION FAILED ❌")
        print("=" * 80)
        print(f"\nError: {e}")
        return 1

    except Exception as e:
        print("\n" + "=" * 80)
        print("  UNEXPECTED ERROR ❌")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
