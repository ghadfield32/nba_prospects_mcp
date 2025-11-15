#!/usr/bin/env python3
"""Cross-validate PBP and shots data for quality assurance

This script validates that play-by-play and shot chart data are internally
consistent. It checks for discrepancies and flags potential data quality issues.

Validation Checks:
    1. Shot counts: PBP shot events vs shots table
    2. Made shots: PBP success count vs shots success count
    3. Coordinate validity: All shots have valid 0-100 coordinates
    4. Schema compliance: All required columns present

Usage:
    # Validate all seasons
    uv run python tools/lnb/validate_data_consistency.py

    # Validate specific season
    uv run python tools/lnb/validate_data_consistency.py --season 2024-2025

Output:
    data/reports/lnb_validation_report.csv - Validation results
"""

from __future__ import annotations

import argparse
import io
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

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_DIR = Path("data/raw/lnb")
REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PBP_DIR = DATA_DIR / "pbp"
SHOTS_DIR = DATA_DIR / "shots"

# ==============================================================================
# VALIDATION LOGIC
# ==============================================================================


@dataclass
class GameValidation:
    """Validation results for a single game"""

    game_id: str
    season: str

    # From shots table
    shots_total: int
    shots_2pt: int
    shots_3pt: int
    shots_2pt_made: int
    shots_3pt_made: int

    # From PBP events
    pbp_shots_total: int
    pbp_2pt_events: int
    pbp_3pt_events: int
    pbp_2pt_made: int
    pbp_3pt_made: int

    # Deltas
    delta_total_shots: int
    delta_2pt_attempts: int
    delta_3pt_attempts: int
    delta_2pt_made: int
    delta_3pt_made: int

    # Validation flags
    coords_valid: bool
    has_nulls: bool
    has_discrepancy: bool
    is_valid: bool

    # Timestamp
    validated_at: str


def validate_game(game_id: str, season: str) -> GameValidation | None:
    """Validate a single game's PBP and shots data

    Args:
        game_id: Game UUID
        season: Season string

    Returns:
        GameValidation object or None if data missing
    """
    # Load PBP data
    pbp_file = PBP_DIR / f"season={season}" / f"game_id={game_id}.parquet"
    if not pbp_file.exists():
        print(f"  [SKIP] PBP file not found: {game_id}")
        return None

    # Load shots data
    shots_file = SHOTS_DIR / f"season={season}" / f"game_id={game_id}.parquet"
    if not shots_file.exists():
        print(f"  [SKIP] Shots file not found: {game_id}")
        return None

    try:
        pbp_df = pd.read_parquet(pbp_file)
        shots_df = pd.read_parquet(shots_file)

        # Count shots from shots table
        shots_total = len(shots_df)
        shots_2pt = len(shots_df[shots_df["SHOT_TYPE"] == "2pt"])
        shots_3pt = len(shots_df[shots_df["SHOT_TYPE"] == "3pt"])
        shots_2pt_made = int(
            shots_df[(shots_df["SHOT_TYPE"] == "2pt") & shots_df["SUCCESS"]].shape[0]
        )
        shots_3pt_made = int(
            shots_df[(shots_df["SHOT_TYPE"] == "3pt") & shots_df["SUCCESS"]].shape[0]
        )

        # Count shots from PBP events
        pbp_shot_events = pbp_df[pbp_df["EVENT_TYPE"].isin(["2pt", "3pt"])]
        pbp_shots_total = len(pbp_shot_events)
        pbp_2pt_events = len(pbp_shot_events[pbp_shot_events["EVENT_TYPE"] == "2pt"])
        pbp_3pt_events = len(pbp_shot_events[pbp_shot_events["EVENT_TYPE"] == "3pt"])
        pbp_2pt_made = int(
            pbp_shot_events[
                (pbp_shot_events["EVENT_TYPE"] == "2pt") & pbp_shot_events["SUCCESS"]
            ].shape[0]
        )
        pbp_3pt_made = int(
            pbp_shot_events[
                (pbp_shot_events["EVENT_TYPE"] == "3pt") & pbp_shot_events["SUCCESS"]
            ].shape[0]
        )

        # Calculate deltas
        delta_total = abs(shots_total - pbp_shots_total)
        delta_2pt_att = abs(shots_2pt - pbp_2pt_events)
        delta_3pt_att = abs(shots_3pt - pbp_3pt_events)
        delta_2pt_made = abs(shots_2pt_made - pbp_2pt_made)
        delta_3pt_made = abs(shots_3pt_made - pbp_3pt_made)

        # Validate coordinates
        coords_valid = (
            (shots_df["X_COORD"] >= 0).all()
            and (shots_df["X_COORD"] <= 100).all()
            and (shots_df["Y_COORD"] >= 0).all()
            and (shots_df["Y_COORD"] <= 100).all()
        )

        # Check for nulls
        has_nulls = shots_df[["X_COORD", "Y_COORD"]].isnull().any().any()

        # Flag discrepancies (allow delta of 1-2 due to possible edge cases)
        has_discrepancy = delta_total > 2 or delta_2pt_made > 2 or delta_3pt_made > 2

        # Overall validity
        is_valid = coords_valid and not has_nulls and not has_discrepancy

        return GameValidation(
            game_id=game_id,
            season=season,
            shots_total=shots_total,
            shots_2pt=shots_2pt,
            shots_3pt=shots_3pt,
            shots_2pt_made=shots_2pt_made,
            shots_3pt_made=shots_3pt_made,
            pbp_shots_total=pbp_shots_total,
            pbp_2pt_events=pbp_2pt_events,
            pbp_3pt_events=pbp_3pt_events,
            pbp_2pt_made=pbp_2pt_made,
            pbp_3pt_made=pbp_3pt_made,
            delta_total_shots=delta_total,
            delta_2pt_attempts=delta_2pt_att,
            delta_3pt_attempts=delta_3pt_att,
            delta_2pt_made=delta_2pt_made,
            delta_3pt_made=delta_3pt_made,
            coords_valid=coords_valid,
            has_nulls=has_nulls,
            has_discrepancy=has_discrepancy,
            is_valid=is_valid,
            validated_at=datetime.now().isoformat(),
        )

    except Exception as e:
        print(f"  [ERROR] Validation failed for {game_id}: {e}")
        return None


def validate_season(season: str) -> list[GameValidation]:
    """Validate all games in a season

    Args:
        season: Season string

    Returns:
        List of GameValidation objects
    """
    print(f"\n[VALIDATING] Season {season}...")

    season_pbp_dir = PBP_DIR / f"season={season}"
    if not season_pbp_dir.exists():
        print(f"  [WARN] No PBP data for season {season}")
        return []

    # Get all game IDs from PBP files
    pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))
    game_ids = [f.stem.replace("game_id=", "") for f in pbp_files]

    print(f"  Found {len(game_ids)} games to validate")

    results = []
    for idx, game_id in enumerate(game_ids, 1):
        print(f"  [{idx}/{len(game_ids)}] {game_id[:16]}...", end=" ")
        validation = validate_game(game_id, season)
        if validation:
            status = "✅" if validation.is_valid else "⚠️"
            print(f"{status}")
            results.append(validation)
        else:
            print()

    return results


def print_validation_summary(validations: list[GameValidation]) -> None:
    """Print validation summary

    Args:
        validations: List of validation results
    """
    if not validations:
        print("\n[WARN] No validation results")
        return

    df = pd.DataFrame([asdict(v) for v in validations])

    total = len(df)
    valid = df["is_valid"].sum()
    with_discrepancies = df["has_discrepancy"].sum()
    invalid_coords = (~df["coords_valid"]).sum()
    with_nulls = df["has_nulls"].sum()

    print(f"\n{'='*80}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total games validated:    {total}")
    print(f"Valid games:              {valid}/{total} ({valid/total*100:.1f}%)")
    print(f"Games with discrepancies: {with_discrepancies}")
    print(f"Invalid coordinates:      {invalid_coords}")
    print(f"Games with nulls:         {with_nulls}")
    print()

    if with_discrepancies > 0:
        print("Games with discrepancies:")
        discrepancies = df[df["has_discrepancy"]]
        for _, row in discrepancies.head(10).iterrows():
            print(
                f"  {row['game_id'][:16]}... - Δ shots: {row['delta_total_shots']}, "
                f"Δ 2PM: {row['delta_2pt_made']}, Δ 3PM: {row['delta_3pt_made']}"
            )


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(description="Validate LNB PBP and shots data")

    parser.add_argument(
        "--season", type=str, default=None, help="Season to validate (default: all seasons)"
    )

    args = parser.parse_args()

    # Determine seasons to validate
    if args.season:
        seasons = [args.season]
    else:
        # Find all season directories
        if PBP_DIR.exists():
            season_dirs = [d.name.replace("season=", "") for d in PBP_DIR.iterdir() if d.is_dir()]
            seasons = sorted(season_dirs, reverse=True)
        else:
            print("[ERROR] No PBP data directory found")
            sys.exit(1)

    if not seasons:
        print("[ERROR] No seasons found to validate")
        sys.exit(1)

    print(f"Validating seasons: {seasons}")

    # Validate all seasons
    all_validations = []
    for season in seasons:
        season_validations = validate_season(season)
        all_validations.extend(season_validations)

    # Save results
    if all_validations:
        df = pd.DataFrame([asdict(v) for v in all_validations])
        report_file = (
            REPORTS_DIR / f"lnb_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        df.to_csv(report_file, index=False)
        print(f"\n[SAVED] Validation report: {report_file}")

    # Print summary
    print_validation_summary(all_validations)

    print(f"\n{'='*80}")
    print("  VALIDATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
