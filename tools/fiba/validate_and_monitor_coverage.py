#!/usr/bin/env python3
"""FIBA Cluster Data Validation and Coverage Monitoring

Validates data coverage and quality for all 4 FIBA cluster leagues:
- LKL (Lithuania Basketball League)
- ABA (Adriatic League)
- BAL (Basketball Africa League)
- BCL (Basketball Champions League)

Provides:
1. Coverage validation (PBP, shots vs game index)
2. Season readiness assessment
3. Validation status file generation

Created: 2025-11-16
Pattern: Simplified from LNB validation, adapted for FIBA cluster
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# FIBA leagues configuration
FIBA_LEAGUES = {
    "LKL": {"name": "Lithuanian Basketball League", "code": "LKL"},
    "ABA": {"name": "Adriatic League", "code": "ABA"},
    "BAL": {"name": "Basketball Africa League", "code": "BAL"},
    "BCL": {"name": "Basketball Champions League", "code": "BCL"},
}

# Data directories (no centralized storage yet, data is ephemeral/cached)
GAME_INDEX_DIR = Path("data/game_indexes")
VALIDATION_OUTPUT = Path("data/raw/fiba/fiba_last_validation.json")

# Coverage thresholds
READINESS_THRESHOLD = 0.95  # 95% coverage required for "ready"


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def load_game_index(league: str, season: str) -> pd.DataFrame:
    """Load game index for a specific FIBA league and season

    Args:
        league: League code (LKL, ABA, BAL, BCL)
        season: Season string (e.g., "2023-24")

    Returns:
        Game index DataFrame or empty DataFrame if not found
    """
    # Game indexes are stored as: data/game_indexes/{LEAGUE}_{SEASON}.csv
    season_filename = season.replace("-", "_")
    index_file = GAME_INDEX_DIR / f"{league}_{season_filename}.csv"

    if not index_file.exists():
        print(f"[WARN] No game index found for {league} {season}: {index_file}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(index_file)
        print(f"[INFO] Loaded {league} {season} index: {len(df)} games")
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load {league} {season} index: {e}")
        return pd.DataFrame()


def estimate_coverage_from_cache(league: str, season: str, data_type: str) -> int:
    """Estimate data coverage from DuckDB storage

    Counts distinct games with data in DuckDB storage for a specific league/season.

    Args:
        league: League code (LKL, ABA, BAL, BCL)
        season: Season string (e.g., "2023-24")
        data_type: "pbp" or "shots"

    Returns:
        Number of games with data in storage
    """
    try:
        # Import storage helper
        sys.path.insert(0, str(project_root / "src"))
        from cbb_data.storage.duckdb_storage import get_storage

        storage = get_storage()

        # Convert season format: "2023-24" -> "2023" for storage queries
        # (Storage uses YYYY format, not YYYY-YY)
        season_year = season.split("-")[0]

        # Check if data exists for this league/season/type
        if not storage.has_data(data_type, league, season_year):
            return 0

        # Count unique games with data
        # Load minimal data just to count unique GAME_IDs
        df = storage.load(data_type, league, season_year, limit=None)

        if df.empty:
            return 0

        # Count distinct games
        if "GAME_ID" in df.columns:
            unique_games = df["GAME_ID"].nunique()
            print(f"  [{league} {season}] Found {unique_games} games with {data_type} in storage")
            return unique_games
        else:
            print(f"  [{league} {season}] WARNING: No GAME_ID column in {data_type} data")
            return 0

    except Exception as e:
        print(f"  [{league} {season}] ERROR checking storage for {data_type}: {e}")
        return 0


def check_season_readiness(
    league: str,
    season: str,
    expected_games: int,
    pbp_coverage: int,
    shots_coverage: int,
) -> dict[str, Any]:
    """Check if a season is ready for modeling

    Args:
        league: League code
        season: Season string
        expected_games: Total games in season (from index)
        pbp_coverage: Games with PBP data
        shots_coverage: Games with shots data

    Returns:
        Readiness dict with status and metrics
    """
    if expected_games == 0:
        return {
            "league": league,
            "season": season,
            "ready_for_modeling": False,
            "expected_games": 0,
            "pbp_coverage": 0,
            "pbp_coverage_pct": 0.0,
            "shots_coverage": 0,
            "shots_coverage_pct": 0.0,
            "reason": "No game index available",
        }

    pbp_pct = pbp_coverage / expected_games
    shots_pct = shots_coverage / expected_games

    # Ready if both PBP and shots >= 95% coverage
    ready = (pbp_pct >= READINESS_THRESHOLD) and (shots_pct >= READINESS_THRESHOLD)

    reason = "Ready" if ready else []
    if pbp_pct < READINESS_THRESHOLD:
        reason.append(f"PBP coverage {pbp_pct*100:.1f}% < {READINESS_THRESHOLD*100}%")
    if shots_pct < READINESS_THRESHOLD:
        reason.append(f"Shots coverage {shots_pct*100:.1f}% < {READINESS_THRESHOLD*100}%")

    return {
        "league": league,
        "season": season,
        "ready_for_modeling": ready,
        "expected_games": expected_games,
        "pbp_coverage": pbp_coverage,
        "pbp_coverage_pct": round(pbp_pct, 3),
        "shots_coverage": shots_coverage,
        "shots_coverage_pct": round(shots_pct, 3),
        "reason": "; ".join(reason) if isinstance(reason, list) else reason,
    }


# ==============================================================================
# MAIN VALIDATION
# ==============================================================================


def validate_fiba_cluster() -> dict[str, Any]:
    """Validate all FIBA cluster leagues

    Returns:
        Validation results dict
    """
    print("=" * 80)
    print("  FIBA CLUSTER VALIDATION")
    print("=" * 80)
    print()

    results = {
        "run_at": datetime.now().isoformat(),
        "leagues": [],
    }

    # Validate each league
    for league_code, league_info in FIBA_LEAGUES.items():
        print(f"\n{'-'*80}")
        print(f"  {league_info['name']} ({league_code})")
        print(f"{'-'*80}")

        # Check for 2023-24 season (most likely to have data)
        season = "2023-24"
        game_index = load_game_index(league_code, season)

        if game_index.empty:
            print(f"[SKIP] No game index for {league_code} {season}")
            results["leagues"].append(
                {
                    "league": league_code,
                    "season": season,
                    "ready_for_modeling": False,
                    "expected_games": 0,
                    "pbp_coverage": 0,
                    "pbp_coverage_pct": 0.0,
                    "shots_coverage": 0,
                    "shots_coverage_pct": 0.0,
                    "reason": "No game index",
                }
            )
            continue

        expected_games = len(game_index)

        # Estimate coverage (conservative: 0 until we have persistent storage)
        pbp_coverage = estimate_coverage_from_cache(league_code, season, "pbp")
        shots_coverage = estimate_coverage_from_cache(league_code, season, "shots")

        # Check readiness
        readiness = check_season_readiness(
            league_code,
            season,
            expected_games,
            pbp_coverage,
            shots_coverage,
        )

        results["leagues"].append(readiness)

        # Print summary
        status = "✅ READY" if readiness["ready_for_modeling"] else "⏳ NOT READY"
        print(f"\n{status}")
        print(f"  Expected games: {expected_games}")
        print(f"  PBP coverage: {pbp_coverage} ({readiness['pbp_coverage_pct']*100:.1f}%)")
        print(f"  Shots coverage: {shots_coverage} ({readiness['shots_coverage_pct']*100:.1f}%)")
        if not readiness["ready_for_modeling"]:
            print(f"  Reason: {readiness['reason']}")

    return results


def save_validation_status(results: dict[str, Any]):
    """Save validation results to JSON file

    Args:
        results: Validation results dict
    """
    output_file = VALIDATION_OUTPUT
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"  SAVED: {output_file}")
    print(f"{'='*80}")


def print_summary(results: dict[str, Any]):
    """Print validation summary

    Args:
        results: Validation results dict
    """
    print(f"\n{'='*80}")
    print("  SUMMARY")
    print(f"{'='*80}")

    ready_leagues = [
        league_data for league_data in results["leagues"] if league_data["ready_for_modeling"]
    ]
    not_ready = [
        league_data for league_data in results["leagues"] if not league_data["ready_for_modeling"]
    ]

    print(f"\n✅ Ready for modeling: {len(ready_leagues)}/{len(results['leagues'])} leagues")
    for league in ready_leagues:
        print(f"  - {league['league']} {league['season']}")

    print(f"\n⏳ Not ready: {len(not_ready)}/{len(results['leagues'])} leagues")
    for league in not_ready:
        print(f"  - {league['league']} {league['season']}: {league['reason']}")

    print("\n📊 Next Steps:")
    if not_ready:
        print("  1. Run browser scraping tests: python tools/fiba/test_browser_scraping.py")
        print("  2. Fetch data with Playwright: fetch_shot_chart(season, use_browser=True)")
        print("  3. Re-run validation to update coverage")
    else:
        print("  🎉 All FIBA leagues ready!")


def main():
    """Main validation entry point"""
    # Run validation
    results = validate_fiba_cluster()

    # Save results
    save_validation_status(results)

    # Print summary
    print_summary(results)

    # Return exit code
    not_ready = [
        league_data for league_data in results["leagues"] if not league_data["ready_for_modeling"]
    ]
    return 0 if len(not_ready) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
