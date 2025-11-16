#!/usr/bin/env python3
"""Debug LNB coverage discrepancy - Investigate why we only see 1-2 games for early seasons

Purpose:
    - Examine actual parquet files in each season directory
    - Check raw historical data directories for additional data
    - Analyze game index to see what's been ingested
    - Compare across all data sources
    - Identify if data is missing or just not being counted correctly

This script adds extensive debugging to understand the data landscape.
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_ROOT = Path("data")
NORMALIZED_ROOT = DATA_ROOT / "normalized" / "lnb"
HISTORICAL_ROOT = DATA_ROOT / "lnb" / "historical"
TOOLS_ROOT = Path("tools/lnb")

SEASONS_TO_ANALYZE = ["2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"]

# ==============================================================================
# ANALYSIS FUNCTIONS
# ==============================================================================


def analyze_normalized_directory(dataset_name: str, season: str) -> dict:
    """Detailed analysis of a normalized dataset directory

    Args:
        dataset_name: "player_game" or "team_game"
        season: Season string (e.g., "2021-2022")

    Returns:
        Dict with detailed file-by-file analysis
    """
    season_dir = NORMALIZED_ROOT / dataset_name / f"season={season}"

    result = {
        "dataset": dataset_name,
        "season": season,
        "directory_exists": season_dir.exists(),
        "directory_path": str(season_dir),
        "parquet_files": [],
        "total_files": 0,
        "total_rows_all_files": 0,
        "unique_games_all_files": set(),
        "unique_players_or_teams": set(),
        "issues": [],
    }

    if not season_dir.exists():
        result["issues"].append(f"Directory does not exist: {season_dir}")
        return result

    # Find all parquet files
    parquet_files = sorted(season_dir.glob("*.parquet"))
    result["total_files"] = len(parquet_files)

    if not parquet_files:
        result["issues"].append("No parquet files found in directory")
        return result

    print(f"\n{'=' * 80}")
    print(f"ANALYZING: {dataset_name} / {season}")
    print(f"Directory: {season_dir}")
    print(f"Found {len(parquet_files)} parquet files")
    print(f"{'=' * 80}")

    # Analyze each file individually
    for file_path in parquet_files:
        print(f"\nFile: {file_path.name}")

        file_info = {
            "filename": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "rows": 0,
            "columns": [],
            "unique_games": [],
            "unique_players_or_teams": [],
            "sample_data": None,
            "issues": [],
        }

        try:
            df = pd.read_parquet(file_path)
            file_info["rows"] = len(df)
            file_info["columns"] = list(df.columns)

            print(f"  Rows: {len(df)}")
            print(f"  Columns: {len(df.columns)}")

            # Track unique games
            if "GAME_ID" in df.columns:
                unique_games = df["GAME_ID"].dropna().unique().tolist()
                file_info["unique_games"] = unique_games
                result["unique_games_all_files"].update(unique_games)
                print(f"  Unique Games: {len(unique_games)}")
                print(f"    Game IDs: {unique_games[:3]}{'...' if len(unique_games) > 3 else ''}")

            # Track unique players/teams
            if dataset_name == "player_game" and "PLAYER_ID" in df.columns:
                unique_entities = df["PLAYER_ID"].dropna().unique().tolist()
                file_info["unique_players_or_teams"] = unique_entities
                result["unique_players_or_teams"].update(unique_entities)
                print(f"  Unique Players: {len(unique_entities)}")
            elif dataset_name == "team_game" and "TEAM_ID" in df.columns:
                unique_entities = df["TEAM_ID"].dropna().unique().tolist()
                file_info["unique_players_or_teams"] = unique_entities
                result["unique_players_or_teams"].update(unique_entities)
                print(f"  Unique Teams: {len(unique_entities)}")

            # Get date range
            if "GAME_DATE" in df.columns:
                dates = pd.to_datetime(df["GAME_DATE"], errors="coerce").dropna()
                if not dates.empty:
                    print(f"  Date Range: {dates.min().date()} to {dates.max().date()}")

            # Sample first row
            if len(df) > 0:
                sample_row = df.iloc[0].to_dict()
                file_info["sample_data"] = {
                    k: str(v)[:50] if pd.notna(v) else None for k, v in sample_row.items()
                }
                print(f"  Sample Game ID: {sample_row.get('GAME_ID', 'N/A')}")
                print(f"  Sample Date: {sample_row.get('GAME_DATE', 'N/A')}")

            result["total_rows_all_files"] += len(df)

        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            file_info["issues"].append(error_msg)
            result["issues"].append(f"{file_path.name}: {error_msg}")
            print(f"  ERROR: {error_msg}")

        result["parquet_files"].append(file_info)

    print(f"\n{'=' * 80}")
    print(f"SUMMARY for {dataset_name} / {season}:")
    print(f"  Total Files: {result['total_files']}")
    print(f"  Total Rows: {result['total_rows_all_files']}")
    print(f"  Unique Games: {len(result['unique_games_all_files'])}")
    print(f"  Unique Players/Teams: {len(result['unique_players_or_teams'])}")
    print(f"{'=' * 80}")

    return result


def analyze_historical_directory(season: str) -> dict:
    """Detailed analysis of historical PBP/shots directory

    Args:
        season: Season string (e.g., "2025-2026")

    Returns:
        Dict with detailed analysis
    """
    season_dir = HISTORICAL_ROOT / season

    result = {
        "season": season,
        "directory_exists": season_dir.exists(),
        "directory_path": str(season_dir),
        "files_found": [],
        "fixtures": None,
        "pbp": None,
        "shots": None,
        "issues": [],
    }

    if not season_dir.exists():
        result["issues"].append(f"Directory does not exist: {season_dir}")
        return result

    print(f"\n{'=' * 80}")
    print(f"ANALYZING HISTORICAL: {season}")
    print(f"Directory: {season_dir}")
    print(f"{'=' * 80}")

    # Check all parquet files in directory
    all_files = sorted(season_dir.glob("*.parquet"))
    result["files_found"] = [f.name for f in all_files]
    print(f"Found {len(all_files)} parquet files: {result['files_found']}")

    # Analyze fixtures
    fixtures_path = season_dir / "fixtures.parquet"
    if fixtures_path.exists():
        print("\n--- FIXTURES ---")
        try:
            df = pd.read_parquet(fixtures_path)
            result["fixtures"] = {
                "exists": True,
                "rows": len(df),
                "columns": list(df.columns),
                "unique_games": df["GAME_ID"].nunique() if "GAME_ID" in df.columns else 0,
            }
            print(f"  Rows: {len(df)}")
            print(f"  Columns ({len(df.columns)}): {df.columns.tolist()[:10]}...")
            if "GAME_ID" in df.columns:
                print(f"  Unique Games: {df['GAME_ID'].nunique()}")
                print(f"  Sample Game IDs: {df['GAME_ID'].head(3).tolist()}")
        except Exception as e:
            result["fixtures"] = {"exists": True, "error": str(e)}
            print(f"  ERROR: {e}")

    # Analyze PBP
    pbp_path = season_dir / "pbp_events.parquet"
    if pbp_path.exists():
        print("\n--- PBP EVENTS ---")
        try:
            df = pd.read_parquet(pbp_path)
            result["pbp"] = {
                "exists": True,
                "rows": len(df),
                "columns": list(df.columns),
                "unique_games": df["GAME_ID"].nunique() if "GAME_ID" in df.columns else 0,
            }
            print(f"  Rows: {len(df)}")
            print(f"  Columns ({len(df.columns)}): {df.columns.tolist()[:10]}...")
            if "GAME_ID" in df.columns:
                print(f"  Unique Games: {df['GAME_ID'].nunique()}")
                print(f"  Sample Game IDs: {df['GAME_ID'].head(3).tolist()}")
        except Exception as e:
            result["pbp"] = {"exists": True, "error": str(e)}
            print(f"  ERROR: {e}")

    # Analyze shots
    shots_path = season_dir / "shots.parquet"
    if shots_path.exists():
        print("\n--- SHOTS ---")
        try:
            df = pd.read_parquet(shots_path)
            result["shots"] = {
                "exists": True,
                "rows": len(df),
                "columns": list(df.columns),
                "unique_games": df["GAME_ID"].nunique() if "GAME_ID" in df.columns else 0,
            }
            print(f"  Rows: {len(df)}")
            print(f"  Columns ({len(df.columns)}): {df.columns.tolist()[:10]}...")
            if "GAME_ID" in df.columns:
                print(f"  Unique Games: {df['GAME_ID'].nunique()}")
                print(f"  Sample Game IDs: {df['GAME_ID'].head(3).tolist()}")
        except Exception as e:
            result["shots"] = {"exists": True, "error": str(e)}
            print(f"  ERROR: {e}")

    print(f"{'=' * 80}")

    return result


def check_all_historical_directories() -> dict:
    """Check what historical directories exist beyond just the expected seasons"""

    print(f"\n{'=' * 80}")
    print("SCANNING ALL HISTORICAL DIRECTORIES")
    print(f"Root: {HISTORICAL_ROOT}")
    print(f"{'=' * 80}")

    result = {
        "root_exists": HISTORICAL_ROOT.exists(),
        "all_directories": [],
        "all_files": [],
    }

    if not HISTORICAL_ROOT.exists():
        print("Historical root directory does not exist!")
        return result

    # List all subdirectories
    all_dirs = sorted([d for d in HISTORICAL_ROOT.iterdir() if d.is_dir()])
    result["all_directories"] = [d.name for d in all_dirs]

    print(f"\nFound {len(all_dirs)} directories:")
    for d in all_dirs:
        parquet_count = len(list(d.glob("*.parquet")))
        print(f"  {d.name}: {parquet_count} parquet files")
        result["all_files"].extend([f"{d.name}/{f.name}" for f in d.glob("*.parquet")])

    return result


def analyze_game_index() -> dict:
    """Analyze the game index to see what games have been tracked"""

    game_index_path = DATA_ROOT / "lnb" / "game_index.parquet"

    result = {
        "exists": game_index_path.exists(),
        "path": str(game_index_path),
        "total_games": 0,
        "games_by_season": {},
        "games_with_pbp": 0,
        "games_with_shots": 0,
        "games_with_boxscore": 0,
    }

    if not game_index_path.exists():
        print(f"\nGame index does not exist: {game_index_path}")
        return result

    print(f"\n{'=' * 80}")
    print("ANALYZING GAME INDEX")
    print(f"Path: {game_index_path}")
    print(f"{'=' * 80}")

    try:
        df = pd.read_parquet(game_index_path)
        result["total_games"] = len(df)

        print(f"\nTotal games in index: {len(df)}")
        print(f"Columns: {df.columns.tolist()}")

        # Games by season
        if "season" in df.columns:
            season_counts = df["season"].value_counts().to_dict()
            result["games_by_season"] = season_counts
            print("\nGames by season:")
            for season, count in sorted(season_counts.items()):
                print(f"  {season}: {count} games")

        # Data availability flags
        if "has_pbp" in df.columns:
            result["games_with_pbp"] = int(df["has_pbp"].sum())
            print(f"\nGames with PBP: {result['games_with_pbp']}")

        if "has_shots" in df.columns:
            result["games_with_shots"] = int(df["has_shots"].sum())
            print(f"Games with shots: {result['games_with_shots']}")

        if "has_boxscore" in df.columns:
            result["games_with_boxscore"] = int(df["has_boxscore"].sum())
            print(f"Games with boxscore: {result['games_with_boxscore']}")

        # Show sample rows
        print("\nSample game index entries:")
        print(df.head(3).to_string())

    except Exception as e:
        result["error"] = str(e)
        print(f"ERROR reading game index: {e}")

    print(f"{'=' * 80}")

    return result


def generate_comprehensive_report(results: dict) -> None:
    """Generate comprehensive debug report"""

    print(f"\n\n{'#' * 80}")
    print("# COMPREHENSIVE COVERAGE ANALYSIS REPORT")
    print(f"# Generated: {datetime.now().isoformat()}")
    print(f"{'#' * 80}\n")

    # Section 1: Normalized Data Summary
    print(f"\n{'=' * 80}")
    print("SECTION 1: NORMALIZED DATA SUMMARY")
    print(f"{'=' * 80}")

    for dataset_name in ["player_game", "team_game"]:
        print(f"\n{dataset_name.upper()}:")
        print(f"{'Season':<15} {'Files':<8} {'Rows':<10} {'Games':<8} {'Players/Teams':<15}")
        print(f"{'-' * 80}")

        for season in SEASONS_TO_ANALYZE[:4]:  # Only normalized seasons
            if season in results["normalized"][dataset_name]:
                r = results["normalized"][dataset_name][season]
                print(
                    f"{season:<15} "
                    f"{r['total_files']:<8} "
                    f"{r['total_rows_all_files']:<10} "
                    f"{len(r['unique_games_all_files']):<8} "
                    f"{len(r['unique_players_or_teams']):<15}"
                )

    # Section 2: Historical Data Summary
    print(f"\n{'=' * 80}")
    print("SECTION 2: HISTORICAL DATA SUMMARY")
    print(f"{'=' * 80}")

    for season in SEASONS_TO_ANALYZE:
        if season in results["historical"]:
            r = results["historical"][season]
            print(f"\n{season}:")
            if r["directory_exists"]:
                print(f"  Files: {', '.join(r['files_found']) if r['files_found'] else 'None'}")
                if r["fixtures"]:
                    print(
                        f"  Fixtures: {r['fixtures'].get('rows', 0)} rows, {r['fixtures'].get('unique_games', 0)} games"
                    )
                if r["pbp"]:
                    print(
                        f"  PBP: {r['pbp'].get('rows', 0)} rows, {r['pbp'].get('unique_games', 0)} games"
                    )
                if r["shots"]:
                    print(
                        f"  Shots: {r['shots'].get('rows', 0)} rows, {r['shots'].get('unique_games', 0)} games"
                    )
            else:
                print("  Directory does not exist")

    # Section 3: Cross-Reference Analysis
    print(f"\n{'=' * 80}")
    print("SECTION 3: CROSS-REFERENCE ANALYSIS")
    print(f"{'=' * 80}")

    print("\nAll historical directories found:")
    print(f"  {results['all_historical_dirs']['all_directories']}")

    if results["game_index"]["exists"]:
        print("\nGame Index Summary:")
        print(f"  Total games tracked: {results['game_index']['total_games']}")
        print(f"  Games by season: {results['game_index']['games_by_season']}")

    # Section 4: Key Findings
    print(f"\n{'=' * 80}")
    print("SECTION 4: KEY FINDINGS & OBSERVATIONS")
    print(f"{'=' * 80}")

    # Identify discrepancies
    print("\nDiscrepancy Analysis:")

    for season in ["2021-2022", "2022-2023"]:
        pg_data = results["normalized"]["player_game"].get(season, {})
        tg_data = results["normalized"]["team_game"].get(season, {})

        if pg_data and tg_data:
            pg_games = len(pg_data.get("unique_games_all_files", set()))
            tg_games = len(tg_data.get("unique_games_all_files", set()))

            print(f"\n{season}:")
            print(f"  Player-game parquet files: {pg_data.get('total_files', 0)}")
            print(f"  Team-game parquet files: {tg_data.get('total_files', 0)}")
            print(f"  Player-game unique games: {pg_games}")
            print(f"  Team-game unique games: {tg_games}")

            if pg_games != tg_games:
                print("  ⚠️ WARNING: Mismatch between player-game and team-game counts!")

            if pg_games == 1:
                print("  ⚠️ OBSERVATION: Only 1 game found. This suggests:")
                print("     - Either only 1 game was ingested for this season")
                print("     - Or the parquet files only contain a subset of available data")
                print("     - Historical data may exist elsewhere that wasn't normalized")


def main():
    """Main debugging workflow"""

    print("Starting comprehensive LNB coverage analysis...")
    print("This will examine all data sources to understand actual coverage.\n")

    results = {
        "normalized": {
            "player_game": {},
            "team_game": {},
        },
        "historical": {},
        "all_historical_dirs": {},
        "game_index": {},
    }

    # Analyze normalized data
    for dataset_name in ["player_game", "team_game"]:
        for season in SEASONS_TO_ANALYZE[:4]:  # Only check seasons that should have normalized data
            result = analyze_normalized_directory(dataset_name, season)
            results["normalized"][dataset_name][season] = result

    # Analyze historical data
    for season in SEASONS_TO_ANALYZE:
        result = analyze_historical_directory(season)
        results["historical"][season] = result

    # Check all historical directories
    results["all_historical_dirs"] = check_all_historical_directories()

    # Analyze game index
    results["game_index"] = analyze_game_index()

    # Generate comprehensive report
    generate_comprehensive_report(results)

    # Save results
    output_file = TOOLS_ROOT / "debug_coverage_analysis.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert sets to lists for JSON serialization
    def convert_sets(obj):
        if isinstance(obj, set):
            return sorted(obj)
        elif isinstance(obj, dict):
            return {k: convert_sets(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_sets(item) for item in obj]
        return obj

    results_serializable = convert_sets(results)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results_serializable, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print("Analysis complete!")
    print(f"Results saved to: {output_file}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
