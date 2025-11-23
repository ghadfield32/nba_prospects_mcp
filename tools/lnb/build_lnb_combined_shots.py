#!/usr/bin/env python3
"""Build combined LNB Shots dataset with content-level validation

This script implements Task #1 (Shots variant) from the unified architecture:
- Combines all leagues into one dataset with `league` as column
- Attaches metadata from game index
- Validates content (coordinate bounds, SHOT_TYPE enum, SUCCESS boolean)
- Quarantines invalid games
- Generates quality report

Usage:
    python tools/lnb/build_lnb_combined_shots.py --season 2023-2024
    python tools/lnb/build_lnb_combined_shots.py --season 2023-2024 --force
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.lnb.constants import (
    LNB_LEAGUES,
    METADATA_COLUMNS_TO_ATTACH,
)
from src.cbb_data.lnb.validation import ValidationResult, validate_shots_batch

# Paths
INDEX_PATH = Path("data/raw/lnb/lnb_game_index.parquet")
RAW_SHOTS_DIR = Path("data/raw/lnb/shots")
CURATED_DIR = Path("data/curated/lnb/shots")
QUARANTINE_DIR = Path("data/quarantine/lnb/shots")
REPORTS_DIR = Path("data/curated/lnb/reports")


def load_game_index(season: str) -> pd.DataFrame:
    """Load game index filtered by season and has_shots=True"""
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Game index not found: {INDEX_PATH}")

    df = pd.read_parquet(INDEX_PATH)

    # Filter to season and games with shots
    df = df[df["season"] == season]
    df = df[df["has_shots"] == True]  # noqa: E712

    # Validate leagues
    invalid_leagues = df[~df["league"].isin(LNB_LEAGUES)]
    if len(invalid_leagues) > 0:
        raise ValueError(f"Invalid league values in index: {invalid_leagues['league'].unique()}")

    return df


def load_raw_shots_game(game_id: str, season: str) -> pd.DataFrame:
    """Load raw shots data for a single game"""
    shots_file = RAW_SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"

    if not shots_file.exists():
        raise FileNotFoundError(f"Shots file not found: {shots_file}")

    return pd.read_parquet(shots_file)


def attach_metadata(
    shots_df: pd.DataFrame, game_row: pd.Series, metadata_cols: list[str]
) -> pd.DataFrame:
    """Attach metadata columns from game index to shots dataframe

    Args:
        shots_df: Raw shots dataframe
        game_row: Row from game index
        metadata_cols: List of column names to attach

    Returns:
        Shots dataframe with metadata columns added
    """
    result_df = shots_df.copy()

    for col in metadata_cols:
        if col in game_row.index:
            result_df[col] = game_row[col]
        else:
            print(f"[WARNING] Metadata column '{col}' not in game index")
            result_df[col] = None

    return result_df


def write_quarantine(
    game_id: str, season: str, df: pd.DataFrame, validation_result: ValidationResult
):
    """Write invalid game to quarantine with validation errors

    Args:
        game_id: Game identifier
        season: Season string
        df: Shots dataframe to quarantine
        validation_result: Validation result with errors
    """
    quarantine_season_dir = QUARANTINE_DIR / f"season={season}"
    quarantine_season_dir.mkdir(parents=True, exist_ok=True)

    # Write data
    quarantine_file = quarantine_season_dir / f"game_id={game_id}.parquet"
    df.to_parquet(quarantine_file, index=False)

    # Write validation errors
    errors_file = quarantine_season_dir / f"game_id={game_id}_errors.json"
    with open(errors_file, "w", encoding="utf-8") as f:
        json.dump(validation_result.to_dict(), f, indent=2)

    print(f"[QUARANTINE] {game_id}: {len(validation_result.errors)} errors")


def build_combined_shots(season: str, force: bool = False) -> dict:
    """Build combined shots dataset for a season

    Args:
        season: Season to build (e.g., "2023-2024")
        force: Overwrite existing curated data

    Returns:
        Quality report dictionary
    """
    print("=" * 80)
    print(f"  BUILD COMBINED LNB SHOTS: {season}")
    print("=" * 80)

    # Check if already built
    output_dir = CURATED_DIR / f"season={season}"
    if output_dir.exists() and not force:
        print(f"\n[ERROR] Output already exists: {output_dir}")
        print("Use --force to overwrite")
        return {}

    # Load game index
    print(f"\n[INFO] Loading game index for {season}...")
    index_df = load_game_index(season)
    print(f"[INFO] Found {len(index_df)} games with shots data")

    # Load raw shots for each game
    print("\n[INFO] Loading raw shots data...")
    games = {}
    load_errors = []

    for _, game_row in index_df.iterrows():
        game_id = game_row["game_id"]
        try:
            shots_df = load_raw_shots_game(game_id, season)

            # Attach metadata
            shots_df = attach_metadata(shots_df, game_row, METADATA_COLUMNS_TO_ATTACH)

            games[game_id] = shots_df

        except FileNotFoundError as e:
            load_errors.append({"game_id": game_id, "error": str(e)})
            print(f"[ERROR] Failed to load {game_id}: {e}")

    print(f"[INFO] Loaded {len(games)}/{len(index_df)} games")

    # Validate all games
    print(f"\n[INFO] Validating {len(games)} games...")
    valid_games, validation_results = validate_shots_batch(games)

    invalid_count = len(games) - len(valid_games)
    print(f"[INFO] Validation complete: {len(valid_games)} valid, {invalid_count} invalid")

    # Quarantine invalid games
    if invalid_count > 0:
        print(f"\n[INFO] Quarantining {invalid_count} invalid games...")
        for result in validation_results:
            if not result.is_valid:
                game_id = result.game_id
                write_quarantine(game_id, season, games[game_id], result)

    # Combine valid games
    if len(valid_games) == 0:
        print("\n[WARNING] No valid games to combine!")
        return _generate_quality_report(
            season, index_df, validation_results, load_errors, pd.DataFrame()
        )

    print(f"\n[INFO] Combining {len(valid_games)} valid games...")
    combined_df = pd.concat(valid_games.values(), ignore_index=True)

    # Enforce schema
    print(f"[INFO] Combined dataset: {len(combined_df)} rows")
    print(f"[INFO] Leagues: {combined_df['league'].value_counts().to_dict()}")

    # Write combined dataset (partitioned by league)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "lnb_shots.parquet"

    print(f"\n[INFO] Writing combined dataset to {output_file}...")
    combined_df.to_parquet(
        output_file,
        index=False,
        partition_cols=["league"],  # Critical for fast filtering
    )

    # Generate quality report
    report = _generate_quality_report(
        season, index_df, validation_results, load_errors, combined_df
    )

    # Write quality report
    reports_season_dir = REPORTS_DIR / f"season={season}"
    reports_season_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_season_dir / "shots_quality_report.json"

    print(f"\n[INFO] Writing quality report to {report_file}...")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("  BUILD COMPLETE")
    print("=" * 80)

    return report


def _generate_quality_report(
    season: str,
    index_df: pd.DataFrame,
    validation_results: list[ValidationResult],
    load_errors: list[dict],
    combined_df: pd.DataFrame,
) -> dict:
    """Generate quality report for the build

    Args:
        season: Season string
        index_df: Game index filtered to season
        validation_results: List of validation results
        load_errors: List of load error dicts
        combined_df: Final combined dataframe

    Returns:
        Quality report dictionary
    """
    # Count by status
    valid_count = sum(1 for r in validation_results if r.is_valid)
    invalid_count = sum(1 for r in validation_results if not r.is_valid)
    warning_count = sum(1 for r in validation_results if len(r.warnings) > 0)

    # Aggregate errors by type
    error_types = {}
    for result in validation_results:
        if not result.is_valid:
            for error in result.errors:
                error_key = error.split(":")[0]  # Get error prefix
                error_types[error_key] = error_types.get(error_key, 0) + 1

    # Per-league stats
    league_stats = {}
    if len(combined_df) > 0:
        for league in combined_df["league"].unique():
            league_df = combined_df[combined_df["league"] == league]
            league_stats[league] = {
                "games": len(league_df["GAME_ID"].unique()),
                "rows": len(league_df),
            }

    report = {
        "season": season,
        "build_timestamp": datetime.now().isoformat(),
        "expected_games": len(index_df),
        "loaded_games": len(index_df) - len(load_errors),
        "valid_games": valid_count,
        "invalid_games": invalid_count,
        "quarantined_games": invalid_count,
        "games_with_warnings": warning_count,
        "load_errors": len(load_errors),
        "total_rows": len(combined_df),
        "league_stats": league_stats,
        "error_types": error_types,
        "validation_details": [r.to_dict() for r in validation_results],
        "load_error_details": load_errors,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Build combined LNB shots dataset")
    parser.add_argument("--season", required=True, help="Season to build (e.g., 2023-2024)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing curated data")

    args = parser.parse_args()

    try:
        report = build_combined_shots(args.season, force=args.force)

        # Print summary
        if report:
            print("\n[SUMMARY]")
            print(f"  Season: {report['season']}")
            print(f"  Expected games: {report['expected_games']}")
            print(f"  Valid games: {report['valid_games']}")
            print(f"  Invalid/quarantined: {report['quarantined_games']}")
            print(f"  Total rows: {report['total_rows']:,}")
            print("  League breakdown:")
            for league, stats in report.get("league_stats", {}).items():
                print(f"    {league}: {stats['games']} games, {stats['rows']:,} rows")

        return 0

    except Exception as e:
        print(f"\n[ERROR] Build failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
