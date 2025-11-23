#!/usr/bin/env python3
"""
Stress-test LNB coverage for play-by-play and shot data with seasonal coverage reports.

Goal:
- Test PBP and shots fetchers across multiple games
- Verify schema consistency (required columns present)
- Check data quality (non-null values, reasonable ranges)
- Generate seasonal coverage reports grouped by season and competition

Usage:
    # Test all seasons with auto-sampling
    uv run python tools/lnb/run_lnb_stress_tests.py

    # Test specific season
    uv run python tools/lnb/run_lnb_stress_tests.py --season 2024-2025

    # Limit sample size per season
    uv run python tools/lnb/run_lnb_stress_tests.py --max-games-per-season 20

Output:
    - Console summary (coverage %, schema validation, data quality)
    - Seasonal coverage reports: data/reports/lnb_pbp_shots_coverage_SEASON.csv
    - Detailed results: tools/lnb/stress_results/lnb_stress_results_YYYYMMDD_HHMMSS.csv
    - JSON report: tools/lnb/stress_results/lnb_stress_results_YYYYMMDD_HHMMSS.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

from src.cbb_data.fetchers.lnb import fetch_lnb_game_shots, fetch_lnb_play_by_play

# ==============================================================================
# CONFIG
# ==============================================================================

# Paths
DATA_DIR = Path("data/raw/lnb")
INDEX_FILE = DATA_DIR / "lnb_game_index.parquet"
REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path("tools/lnb/stress_results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# GAME LOADING FROM INDEX
# ==============================================================================


@dataclass
class GameMetadata:
    """Metadata for a game to test"""

    game_id: str
    season: str
    competition: str
    home_team: str
    away_team: str


def load_games_from_index(
    season: str | None = None, max_per_season: int = 20
) -> list[GameMetadata]:
    """Load games from game index with optional filtering and sampling

    Args:
        season: Specific season to test (None for all seasons)
        max_per_season: Maximum games to sample per season

    Returns:
        List of GameMetadata objects
    """
    if not INDEX_FILE.exists():
        print(f"[ERROR] Game index not found: {INDEX_FILE}")
        print("[ERROR] Run: uv run python tools/lnb/build_game_index.py")
        sys.exit(1)

    try:
        index_df = pd.read_parquet(INDEX_FILE)
        print(f"[INFO] Loaded game index: {len(index_df)} total games")

        # Filter by season if specified
        if season:
            index_df = index_df[index_df["season"] == season]
            print(f"[INFO] Filtered to season {season}: {len(index_df)} games")

        # Sample games per season
        games = []
        for season_name in index_df["season"].unique():
            season_games = index_df[index_df["season"] == season_name]

            # Sample up to max_per_season games
            if len(season_games) > max_per_season:
                season_games = season_games.sample(n=max_per_season, random_state=42)
                print(
                    f"[INFO] Sampled {max_per_season} games from {season_name} (out of {len(index_df[index_df['season'] == season_name])})"
                )
            else:
                print(f"[INFO] Using all {len(season_games)} games from {season_name}")

            # Create GameMetadata objects
            for _, row in season_games.iterrows():
                games.append(
                    GameMetadata(
                        game_id=row["game_id"],
                        season=row["season"],
                        competition=row["competition"],
                        home_team=row["home_team_name"],
                        away_team=row["away_team_name"],
                    )
                )

        print(f"[INFO] Total games to test: {len(games)}")
        return games

    except Exception as e:
        print(f"[ERROR] Failed to load game index: {e}")
        sys.exit(1)


# Required columns for schema validation (based on actual implementation)
PBP_REQUIRED_COLUMNS = [
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "EVENT_TYPE",
    "PLAYER_NAME",
    "TEAM_ID",
    "HOME_SCORE",
    "AWAY_SCORE",
    "LEAGUE",
]

SHOTS_REQUIRED_COLUMNS = [
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "SHOT_TYPE",
    "PLAYER_NAME",
    "TEAM_ID",
    "SUCCESS",
    "X_COORD",
    "Y_COORD",
    "LEAGUE",
]

# Data quality thresholds
MIN_PBP_EVENTS_PER_GAME = 200  # Expect at least 200 events per game
MIN_SHOTS_PER_GAME = 50  # Expect at least 50 shots per game
MAX_COORD_VALUE = 100.0  # Coordinates should be 0-100 scale

# ==============================================================================
# DATA MODELS
# ==============================================================================


@dataclass
class GameStressResult:
    """Results from stress testing a single game"""

    # Game metadata
    game_id: str
    season: str
    competition: str
    home_team: str
    away_team: str

    # Play-by-play results
    pbp_ok: bool = False
    pbp_rows: int = 0
    pbp_missing_columns: list[str] | None = None
    pbp_error: str | None = None
    pbp_event_types_count: int = 0
    pbp_has_nulls: bool = False

    # Shots results
    shots_ok: bool = False
    shots_rows: int = 0
    shots_missing_columns: list[str] | None = None
    shots_error: str | None = None
    shots_made: int = 0
    shots_missed: int = 0
    shots_fg_pct: float = 0.0
    shots_coords_valid: bool = False
    shots_has_nulls: bool = False


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def check_required_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    """Return list of missing required columns"""
    return [col for col in required if col not in df.columns]


def check_pbp_data_quality(df: pd.DataFrame) -> dict:
    """Check play-by-play data quality"""
    quality = {
        "event_types_count": df["EVENT_TYPE"].nunique() if "EVENT_TYPE" in df.columns else 0,
        "has_nulls": df[["EVENT_TYPE", "PERIOD_ID"]].isnull().any().any()
        if "EVENT_TYPE" in df.columns
        else False,
        "min_events": len(df) >= MIN_PBP_EVENTS_PER_GAME,
    }
    return quality


def check_shots_data_quality(df: pd.DataFrame) -> dict:
    """Check shot chart data quality"""
    quality = {
        "made": int(df["SUCCESS"].sum()) if "SUCCESS" in df.columns else 0,
        "missed": int((~df["SUCCESS"]).sum()) if "SUCCESS" in df.columns else 0,
        "fg_pct": float(df["SUCCESS"].mean()) if "SUCCESS" in df.columns and len(df) > 0 else 0.0,
        "coords_valid": False,
        "has_nulls": False,
    }

    # Check coordinate validity
    if "X_COORD" in df.columns and "Y_COORD" in df.columns:
        quality["has_nulls"] = df[["X_COORD", "Y_COORD"]].isnull().any().any()
        if not quality["has_nulls"]:
            quality["coords_valid"] = (
                (df["X_COORD"] >= 0).all()
                and (df["X_COORD"] <= MAX_COORD_VALUE).all()
                and (df["Y_COORD"] >= 0).all()
                and (df["Y_COORD"] <= MAX_COORD_VALUE).all()
            )

    return quality


# ==============================================================================
# STRESS TEST LOGIC
# ==============================================================================


def stress_test_game(game: GameMetadata) -> GameStressResult:
    """Run PBP + shots stress test for a single game"""
    res = GameStressResult(
        game_id=game.game_id,
        season=game.season,
        competition=game.competition,
        home_team=game.home_team,
        away_team=game.away_team,
    )

    # ===========================================================================
    # Test Play-by-Play
    # ===========================================================================
    print(f"[GAME {game.game_id[:16]}...] Testing play-by-play...", end=" ")
    try:
        pbp_df = fetch_lnb_play_by_play(game.game_id)
        res.pbp_rows = len(pbp_df)

        if res.pbp_rows > 0:
            # Schema validation
            missing = check_required_columns(pbp_df, PBP_REQUIRED_COLUMNS)
            res.pbp_missing_columns = missing or None

            # Data quality checks
            quality = check_pbp_data_quality(pbp_df)
            res.pbp_event_types_count = quality["event_types_count"]
            res.pbp_has_nulls = quality["has_nulls"]

            # Overall success
            res.pbp_ok = len(missing) == 0 and quality["min_events"] and not quality["has_nulls"]

            status = "✅ OK" if res.pbp_ok else "⚠️ WARN"
            print(f"{status} ({res.pbp_rows} events, {res.pbp_event_types_count} types)")
        else:
            res.pbp_ok = False
            res.pbp_error = "Empty PBP DataFrame"
            print("❌ EMPTY")

    except Exception as e:
        res.pbp_ok = False
        res.pbp_error = str(e)[:300]
        print(f"❌ ERROR: {str(e)[:50]}")

    # ===========================================================================
    # Test Shots
    # ===========================================================================
    print(f"[GAME {game.game_id[:16]}...] Testing shot chart...", end=" ")
    try:
        shots_df = fetch_lnb_game_shots(game.game_id)
        res.shots_rows = len(shots_df)

        if res.shots_rows > 0:
            # Schema validation
            missing = check_required_columns(shots_df, SHOTS_REQUIRED_COLUMNS)
            res.shots_missing_columns = missing or None

            # Data quality checks
            quality = check_shots_data_quality(shots_df)
            res.shots_made = quality["made"]
            res.shots_missed = quality["missed"]
            res.shots_fg_pct = quality["fg_pct"]
            res.shots_coords_valid = quality["coords_valid"]
            res.shots_has_nulls = quality["has_nulls"]

            # Overall success
            res.shots_ok = (
                len(missing) == 0
                and res.shots_rows >= MIN_SHOTS_PER_GAME
                and quality["coords_valid"]
                and not quality["has_nulls"]
            )

            status = "✅ OK" if res.shots_ok else "⚠️ WARN"
            print(f"{status} ({res.shots_rows} shots, FG%: {res.shots_fg_pct:.1%})")
        else:
            res.shots_ok = False
            res.shots_error = "Empty shots DataFrame"
            print("❌ EMPTY")

    except Exception as e:
        res.shots_ok = False
        res.shots_error = str(e)[:300]
        print(f"❌ ERROR: {str(e)[:50]}")

    return res


def run_stress_tests(games: list[GameMetadata]) -> list[GameStressResult]:
    """Run stress tests for all games"""
    results: list[GameStressResult] = []

    total = len(games)
    print(f"\n{'='*80}")
    print(f"  LNB STRESS TEST - Testing {total} games")
    print(f"{'='*80}\n")

    for i, game in enumerate(games, 1):
        print(f"\n[{i}/{total}] {game.season} - {game.competition}")
        print(f"  Game ID: {game.game_id}")
        print(f"  {game.home_team} vs {game.away_team}")
        print("-" * 80)

        result = stress_test_game(game)
        results.append(result)

    return results


# ==============================================================================
# REPORTING
# ==============================================================================


def generate_seasonal_coverage_reports(results: list[GameStressResult]) -> None:
    """Generate seasonal coverage reports grouped by season and competition

    Outputs CSV files to data/reports/lnb_pbp_shots_coverage_SEASON.csv
    """
    if not results:
        print("[INFO] No results to generate seasonal reports")
        return

    df = pd.DataFrame([asdict(r) for r in results])

    # Group by season
    seasons = df["season"].unique()

    for season in seasons:
        season_df = df[df["season"] == season]

        # Calculate coverage stats per competition
        coverage_stats = []
        for comp in season_df["competition"].unique():
            comp_df = season_df[season_df["competition"] == comp]

            total_games = len(comp_df)
            pbp_success = int(comp_df["pbp_ok"].sum())
            shots_success = int(comp_df["shots_ok"].sum())
            both_success = int((comp_df["pbp_ok"] & comp_df["shots_ok"]).sum())

            # Calculate averages for successful games
            pbp_successful = comp_df[comp_df["pbp_ok"]]
            shots_successful = comp_df[comp_df["shots_ok"]]

            avg_pbp_events = pbp_successful["pbp_rows"].mean() if len(pbp_successful) > 0 else 0
            avg_shots = shots_successful["shots_rows"].mean() if len(shots_successful) > 0 else 0
            avg_fg_pct = shots_successful["shots_fg_pct"].mean() if len(shots_successful) > 0 else 0

            coverage_stats.append(
                {
                    "season": season,
                    "competition": comp,
                    "total_games": total_games,
                    "pbp_success_count": pbp_success,
                    "pbp_success_pct": pbp_success / total_games if total_games > 0 else 0,
                    "shots_success_count": shots_success,
                    "shots_success_pct": shots_success / total_games if total_games > 0 else 0,
                    "both_success_count": both_success,
                    "both_success_pct": both_success / total_games if total_games > 0 else 0,
                    "avg_pbp_events_per_game": avg_pbp_events,
                    "avg_shots_per_game": avg_shots,
                    "avg_fg_pct": avg_fg_pct,
                    "generated_at": datetime.now().isoformat(),
                }
            )

        # Save seasonal coverage report
        coverage_df = pd.DataFrame(coverage_stats)
        report_file = REPORTS_DIR / f"lnb_pbp_shots_coverage_{season.replace('-', '_')}.csv"
        coverage_df.to_csv(report_file, index=False)
        print(f"[SAVED] Seasonal coverage report: {report_file}")


def summarize_results(results: list[GameStressResult]) -> None:
    """Print aggregate coverage stats and write CSV/JSON summaries"""
    if not results:
        print("[SUMMARY] No results to summarize.")
        return

    df = pd.DataFrame([asdict(r) for r in results])

    # Generate seasonal coverage reports
    print(f"\n{'='*80}")
    print("  GENERATING SEASONAL COVERAGE REPORTS")
    print(f"{'='*80}\n")
    generate_seasonal_coverage_reports(results)

    # Save raw results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"lnb_stress_results_{ts}.csv"
    json_path = OUTPUT_DIR / f"lnb_stress_results_{ts}.json"

    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, indent=2, ensure_ascii=False)

    print(f"\n\n{'='*80}")
    print("  STRESS TEST SUMMARY")
    print(f"{'='*80}\n")

    # Overall statistics
    total = len(results)
    pbp_success = int(df["pbp_ok"].sum())
    shots_success = int(df["shots_ok"].sum())
    both_success = int((df["pbp_ok"] & df["shots_ok"]).sum())

    print("OVERALL COVERAGE")
    print("-" * 80)
    print(f"Total games tested          : {total}")
    print(
        f"Seasons covered             : {df['season'].nunique()} ({', '.join(sorted(df['season'].unique()))})"
    )
    print(f"PBP success                 : {pbp_success:3d} / {total} ({pbp_success/total:.1%})")
    print(f"Shots success               : {shots_success:3d} / {total} ({shots_success/total:.1%})")
    print(f"Both PBP + Shots success    : {both_success:3d} / {total} ({both_success/total:.1%})")

    # Seasonal breakdown
    print("\nSEASONAL BREAKDOWN")
    print("-" * 80)
    for season in sorted(df["season"].unique()):
        season_df = df[df["season"] == season]
        season_total = len(season_df)
        season_both = int((season_df["pbp_ok"] & season_df["shots_ok"]).sum())
        print(
            f"{season:12s} : {season_both:3d} / {season_total:3d} both success ({season_both/season_total:.1%})"
        )
    print()

    # Data volume statistics
    if pbp_success > 0:
        print("\nPLAY-BY-PLAY DATA VOLUME")
        print("-" * 80)
        pbp_successful = df[df["pbp_ok"]]
        print(f"Total events captured       : {pbp_successful['pbp_rows'].sum():,}")
        print(f"Avg events per game         : {pbp_successful['pbp_rows'].mean():.0f}")
        print(f"Min events                  : {pbp_successful['pbp_rows'].min()}")
        print(f"Max events                  : {pbp_successful['pbp_rows'].max()}")
        print(f"Avg event types per game    : {pbp_successful['pbp_event_types_count'].mean():.1f}")

    if shots_success > 0:
        print("\nSHOT CHART DATA VOLUME")
        print("-" * 80)
        shots_successful = df[df["shots_ok"]]
        print(f"Total shots captured        : {shots_successful['shots_rows'].sum():,}")
        print(f"Avg shots per game          : {shots_successful['shots_rows'].mean():.0f}")
        print(f"Min shots                   : {shots_successful['shots_rows'].min()}")
        print(f"Max shots                   : {shots_successful['shots_rows'].max()}")
        print(f"Avg FG%                     : {shots_successful['shots_fg_pct'].mean():.1%}")

    # Schema validation issues
    print("\nSCHEMA VALIDATION")
    print("-" * 80)

    pbp_schema_issues = df[df["pbp_missing_columns"].notna()]
    shots_schema_issues = df[df["shots_missing_columns"].notna()]

    if len(pbp_schema_issues) > 0:
        print(f"⚠️  PBP schema issues in {len(pbp_schema_issues)} games:")
        for _, row in pbp_schema_issues.head(10).iterrows():
            print(f"    game_id={row['game_id']} missing={row['pbp_missing_columns']}")
    else:
        print("✅ No PBP schema issues detected")

    if len(shots_schema_issues) > 0:
        print(f"⚠️  Shots schema issues in {len(shots_schema_issues)} games:")
        for _, row in shots_schema_issues.head(10).iterrows():
            print(f"    game_id={row['game_id']} missing={row['shots_missing_columns']}")
    else:
        print("✅ No shots schema issues detected")

    # Data quality issues
    print("\nDATA QUALITY")
    print("-" * 80)

    pbp_nulls = df[df["pbp_has_nulls"]]["game_id"].tolist()
    shots_nulls = df[df["shots_has_nulls"]]["game_id"].tolist()
    shots_invalid_coords = df[~df["shots_coords_valid"] & (df["shots_rows"] > 0)][
        "game_id"
    ].tolist()

    if pbp_nulls:
        print(f"⚠️  PBP has null values in {len(pbp_nulls)} games: {pbp_nulls[:5]}")
    else:
        print("✅ No null values in PBP data")

    if shots_nulls:
        print(f"⚠️  Shots has null values in {len(shots_nulls)} games: {shots_nulls[:5]}")
    else:
        print("✅ No null values in shot coordinates")

    if shots_invalid_coords:
        print(
            f"⚠️  Invalid shot coordinates in {len(shots_invalid_coords)} games: {shots_invalid_coords[:5]}"
        )
    else:
        print("✅ All shot coordinates within valid range (0-100)")

    # Failures
    pbp_failures = df[~df["pbp_ok"] & df["pbp_error"].notna()]
    shots_failures = df[~df["shots_ok"] & df["shots_error"].notna()]

    if len(pbp_failures) > 0 or len(shots_failures) > 0:
        print("\nFAILURES")
        print("-" * 80)

        if len(pbp_failures) > 0:
            print(f"PBP failures ({len(pbp_failures)}):")
            for _, row in pbp_failures.head(5).iterrows():
                print(f"  game_id={row['game_id']}: {row['pbp_error'][:100]}")

        if len(shots_failures) > 0:
            print(f"\nShots failures ({len(shots_failures)}):")
            for _, row in shots_failures.head(5).iterrows():
                print(f"  game_id={row['game_id']}: {row['shots_error'][:100]}")

    # Output files
    print(f"\n{'='*80}")
    print("OUTPUT FILES")
    print(f"{'='*80}")
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")
    print()


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LNB stress test with seasonal coverage reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test all seasons (auto-sample 20 games per season)
    uv run python tools/lnb/run_lnb_stress_tests.py

    # Test specific season
    uv run python tools/lnb/run_lnb_stress_tests.py --season 2024-2025

    # Adjust sample size
    uv run python tools/lnb/run_lnb_stress_tests.py --max-games-per-season 50

Output:
    - Seasonal coverage: data/reports/lnb_pbp_shots_coverage_SEASON.csv
    - Detailed results: tools/lnb/stress_results/lnb_stress_results_YYYYMMDD_HHMMSS.csv
        """,
    )

    parser.add_argument(
        "--season",
        type=str,
        default=None,
        help='Specific season to test (e.g., "2024-2025"). If not specified, tests all seasons.',
    )

    parser.add_argument(
        "--max-games-per-season",
        type=int,
        default=20,
        help="Maximum games to sample per season (default: 20)",
    )

    args = parser.parse_args()

    # Load games from index
    games = load_games_from_index(season=args.season, max_per_season=args.max_games_per_season)

    if not games:
        print("ERROR: No games loaded from index!")
        print("Run: uv run python tools/lnb/build_game_index.py")
        return

    # Run stress tests
    results = run_stress_tests(games)

    # Summarize and generate reports
    summarize_results(results)


if __name__ == "__main__":
    main()
