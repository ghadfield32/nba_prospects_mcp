"""Compute Dataset Coverage

Scans parquet files to compute min/max dates for each (league, dataset) combination.
Generates coverage metadata used by the data availability matrix.

Usage:
    # Compute coverage for all leagues/datasets
    python tools/compute_coverage.py

    # Compute for specific leagues
    python tools/compute_coverage.py --leagues NCAA-MBB EuroLeague

    # Output to specific file
    python tools/compute_coverage.py --output data/metadata/coverage.json
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cbb_data.metadata.coverage import CoverageMap, DatasetCoverage, save_coverage

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Data directory
DATA_ROOT = Path(__file__).parent.parent / "data"

# Dataset types and their typical date columns
DATASET_CONFIGS = {
    "schedule": {
        "path_pattern": "raw/{league}/schedule",
        "date_columns": ["GAME_DATE", "game_date", "Date", "date", "DATE", "GAME_DATE_EST"],
        "alt_paths": ["schedules", "games"],
    },
    "player_game": {
        "path_pattern": "raw/{league}/box_scores",
        "date_columns": ["GAME_DATE", "game_date", "Date", "GAME_DATE_EST"],
        "alt_paths": ["player_game", "box_score"],
    },
    "team_game": {
        "path_pattern": "raw/{league}/team_game",
        "date_columns": ["GAME_DATE", "game_date", "Date", "GAME_DATE_EST"],
        "alt_paths": ["team_stats"],
    },
    "player_season": {
        "path_pattern": "raw/{league}/player_season",
        "date_columns": ["GAME_DATE", "game_date"],  # May not have dates
        "alt_paths": ["player_stats"],
    },
    "team_season": {
        "path_pattern": "raw/{league}/team_season",
        "date_columns": ["GAME_DATE", "game_date"],  # May not have dates
        "alt_paths": ["team_standings"],
    },
    "pbp": {
        "path_pattern": "raw/{league}/pbp",
        "date_columns": ["GAME_DATE", "game_date", "Date", "GAME_DATE_EST", "wctimestring"],
        "alt_paths": ["play_by_play", "pbp_events"],
    },
    "shots": {
        "path_pattern": "raw/{league}/shots",
        "date_columns": ["GAME_DATE", "game_date", "Date", "GAME_DATE_EST"],
        "alt_paths": ["shot_chart", "shot_data"],
    },
}

# Known coverage based on league source configurations
# Format: (league, dataset) -> (min_date, max_date, notes)
KNOWN_COVERAGE = {
    # NCAA - ESPN API (current season only)
    ("NCAA-MBB", "schedule"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-MBB", "player_game"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-MBB", "team_game"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-MBB", "pbp"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-MBB", "shots"): ("2024-11-01", "present", "cbbpy - current season"),
    ("NCAA-WBB", "schedule"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-WBB", "player_game"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-WBB", "team_game"): ("2024-11-01", "present", "ESPN API - current season"),
    ("NCAA-WBB", "pbp"): ("2024-11-01", "present", "ESPN API - current season"),
    # EuroLeague/EuroCup - Historical data 2000+
    ("EuroLeague", "schedule"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroLeague", "player_game"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroLeague", "team_game"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroLeague", "pbp"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroLeague", "shots"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroCup", "schedule"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroCup", "player_game"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroCup", "team_game"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroCup", "pbp"): ("2000-01-01", "present", "euroleague-api 2000+"),
    ("EuroCup", "shots"): ("2000-01-01", "present", "euroleague-api 2000+"),
    # G-League - NBA Stats API 2001+
    ("G-League", "schedule"): ("2001-01-01", "present", "NBA Stats API 2001+"),
    ("G-League", "player_game"): ("2001-01-01", "present", "NBA Stats API 2001+"),
    ("G-League", "team_game"): ("2001-01-01", "present", "NBA Stats API 2001+"),
    ("G-League", "pbp"): ("2001-01-01", "present", "NBA Stats API 2001+"),
    ("G-League", "shots"): ("2001-01-01", "present", "NBA Stats API 2001+"),
    # WNBA - NBA Stats API 1997+
    ("WNBA", "schedule"): ("1997-01-01", "present", "NBA Stats API 1997+"),
    ("WNBA", "player_game"): ("1997-01-01", "present", "NBA Stats API 1997+"),
    ("WNBA", "team_game"): ("1997-01-01", "present", "NBA Stats API 1997+"),
    ("WNBA", "pbp"): ("1997-01-01", "present", "NBA Stats API 1997+"),
    ("WNBA", "shots"): ("1997-01-01", "present", "NBA Stats API 1997+"),
    # NBL Australia - nblR 1979+ (detailed since 2015-16)
    ("NBL", "schedule"): ("1979-01-01", "present", "nblR 1979+"),
    ("NBL", "player_game"): ("2015-10-01", "present", "nblR 2015-16+"),
    ("NBL", "team_game"): ("2015-10-01", "present", "nblR 2015-16+"),
    ("NBL", "pbp"): ("2015-10-01", "present", "nblR 2015-16+"),
    ("NBL", "shots"): ("2015-10-01", "present", "nblR 2015-16+ (x,y coords)"),
    ("NBL", "player_season"): ("1979-01-01", "present", "nblR 1979+"),
    ("NBL", "team_season"): ("1979-01-01", "present", "nblR 1979+"),
    # OTE - Current season
    ("OTE", "schedule"): ("2021-01-01", "present", "Web scraping 2021+"),
    ("OTE", "player_game"): ("2021-01-01", "present", "Web scraping 2021+"),
    ("OTE", "team_game"): ("2021-01-01", "present", "Web scraping 2021+"),
    ("OTE", "pbp"): ("2021-01-01", "present", "Web scraping - full PBP!"),
    # LNB France - API + Historical parquet
    ("LNB_PROA", "schedule"): ("2021-01-01", "present", "LNB API 2021+"),
    ("LNB_PROA", "player_game"): ("2021-01-01", "present", "Normalized parquet 4 seasons"),
    ("LNB_PROA", "team_game"): ("2021-01-01", "present", "Normalized parquet 4 seasons"),
    ("LNB_PROA", "pbp"): ("2023-01-01", "present", "Historical parquet 2023+"),
    ("LNB_PROA", "shots"): ("2023-01-01", "present", "Historical parquet 2023+"),
    ("LNB_PROA", "player_season"): ("2021-01-01", "present", "LNB API 2021+"),
    ("LNB_PROA", "team_season"): ("2021-01-01", "present", "LNB API 2021+"),
    # ACB Spain - BAwiR
    ("ACB", "schedule"): ("2020-01-01", "present", "HTML scraping"),
    ("ACB", "player_game"): ("2020-01-01", "present", "HTML scraping"),
    ("ACB", "pbp"): ("2020-01-01", "present", "BAwiR R package"),
    ("ACB", "shots"): ("2020-01-01", "present", "BAwiR R package (x,y)"),
    # CEBL - ceblpy
    ("CEBL", "schedule"): ("2019-01-01", "present", "ceblpy 2019+"),
    ("CEBL", "player_game"): ("2019-01-01", "present", "ceblpy 2019+"),
    ("CEBL", "team_game"): ("2019-01-01", "present", "ceblpy 2019+"),
    # NZ NBL - FIBA LiveStats
    ("NZ-NBL", "schedule"): ("2020-01-01", "present", "Playwright/FIBA"),
    ("NZ-NBL", "player_game"): ("2020-01-01", "present", "FIBA HTML"),
    ("NZ-NBL", "team_game"): ("2020-01-01", "present", "FIBA HTML"),
    ("NZ-NBL", "pbp"): ("2020-01-01", "present", "FIBA HTML"),
    ("NZ-NBL", "shots"): ("2020-01-01", "present", "FIBA HTML"),
}

# All leagues to scan
ALL_LEAGUES = [
    "NCAA-MBB",
    "NCAA-WBB",
    "EuroLeague",
    "EuroCup",
    "G-League",
    "WNBA",
    "NBL",
    "NZ-NBL",
    "LNB_PROA",
    "LNB_ELITE2",
    "LNB_ESPOIRS_ELITE",
    "LNB_ESPOIRS_PROB",
    "ACB",
    "OTE",
    "CEBL",
    "NJCAA",
    "NAIA",
    "USPORTS",
    "CCAA",
    "LKL",
    "BAL",
    "BCL",
    "ABA",
]


def find_parquet_files(league: str, dataset: str) -> list[Path]:
    """Find all parquet files for a league/dataset combination"""
    config = DATASET_CONFIGS.get(dataset, {})
    files = []

    # Try main path pattern
    path_pattern = config.get("path_pattern", f"raw/{league}/{dataset}")
    main_path = path_pattern.format(league=league)
    main_dir = DATA_ROOT / main_path

    if main_dir.exists():
        files.extend(main_dir.glob("**/*.parquet"))

    # Try alternative paths
    for alt in config.get("alt_paths", []):
        alt_dir = DATA_ROOT / "raw" / league / alt
        if alt_dir.exists():
            files.extend(alt_dir.glob("**/*.parquet"))

    # Try partitioned paths (league=XXX format)
    for pattern in [
        f"raw/{dataset}/league={league}",
        f"{dataset}/league={league}",
        f"processed/{dataset}/league={league}",
    ]:
        part_dir = DATA_ROOT / pattern
        if part_dir.exists():
            files.extend(part_dir.glob("**/*.parquet"))

    # Check backups directory (actual data location)
    backup_dirs = list(DATA_ROOT.glob("backups/*"))
    for backup_dir in backup_dirs:
        # Check for dataset-specific folders in backups
        dataset_dir = backup_dir / dataset
        if dataset_dir.exists():
            files.extend(dataset_dir.glob("**/*.parquet"))
        # Also check timestamped backup folders
        for ts_dir in backup_dir.glob("*"):
            if ts_dir.is_dir():
                ds_dir = ts_dir / dataset
                if ds_dir.exists():
                    files.extend(ds_dir.glob("**/*.parquet"))

    # LNB-specific paths
    if league.startswith("LNB"):
        lnb_paths = [
            DATA_ROOT / "lnb" / "historical",
            DATA_ROOT / "raw" / "lnb",
            DATA_ROOT / "backups" / "lnb",
        ]
        for lnb_path in lnb_paths:
            if lnb_path.exists():
                # Look for dataset-specific folders
                ds_path = lnb_path / dataset
                if ds_path.exists():
                    files.extend(ds_path.glob("**/*.parquet"))
                # Also look in timestamped backups
                for ts_dir in lnb_path.glob("*"):
                    if ts_dir.is_dir():
                        ds_dir = ts_dir / dataset
                        if ds_dir.exists():
                            files.extend(ds_dir.glob("**/*.parquet"))

    # NZ NBL specific
    if league == "NZ-NBL":
        nz_file = DATA_ROOT / "nz_nbl_game_index.parquet"
        if nz_file.exists() and dataset == "schedule":
            files.append(nz_file)

    return list(set(files))  # Deduplicate


def extract_dates_from_parquet(
    file_path: Path, date_columns: list[str]
) -> tuple[str | None, str | None, int]:
    """Extract min/max dates from a parquet file

    Returns:
        (min_date, max_date, record_count) or (None, None, 0) if no dates found
    """
    try:
        # Read just the date columns to minimize memory usage
        df = None
        date_col = None

        for col in date_columns:
            try:
                df = pd.read_parquet(file_path, columns=[col])
                date_col = col
                break
            except Exception:
                continue

        if df is None or df.empty:
            # Try reading all columns and finding a date column
            df = pd.read_parquet(file_path)
            for col in df.columns:
                col_lower = col.lower()
                if "date" in col_lower or "time" in col_lower:
                    date_col = col
                    break

        if date_col is None or date_col not in df.columns:
            return None, None, len(df) if df is not None else 0

        # Convert to datetime
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()

        if dates.empty:
            return None, None, len(df)

        min_date = dates.min().strftime("%Y-%m-%d")
        max_date = dates.max().strftime("%Y-%m-%d")

        return min_date, max_date, len(df)

    except Exception as e:
        logger.debug(f"Error reading {file_path}: {e}")
        return None, None, 0


def compute_coverage_for_league_dataset(league: str, dataset: str) -> DatasetCoverage | None:
    """Compute coverage for a single league/dataset combination"""
    config = DATASET_CONFIGS.get(dataset, {})
    date_columns = config.get("date_columns", ["GAME_DATE", "game_date", "Date"])

    files = find_parquet_files(league, dataset)

    if not files:
        return None

    all_min_dates = []
    all_max_dates = []
    total_records = 0

    for file_path in files:
        min_date, max_date, count = extract_dates_from_parquet(file_path, date_columns)
        if min_date and max_date:
            all_min_dates.append(min_date)
            all_max_dates.append(max_date)
        total_records += count

    if not all_min_dates:
        # No dates found, but we have files
        if total_records > 0:
            return DatasetCoverage(
                min_date="N/A",
                max_date="N/A",
                record_count=total_records,
                last_updated=datetime.now().isoformat(),
            )
        return None

    return DatasetCoverage(
        min_date=min(all_min_dates),
        max_date=max(all_max_dates),
        record_count=total_records if total_records > 0 else None,
        last_updated=datetime.now().isoformat(),
    )


def compute_all_coverage(
    leagues: list[str] | None = None, include_known: bool = True
) -> CoverageMap:
    """Compute coverage for all leagues and datasets

    Args:
        leagues: List of leagues to process (default: all)
        include_known: Include known coverage from configuration (default: True)

    Returns:
        Coverage map
    """
    if leagues is None:
        leagues = ALL_LEAGUES

    datasets = list(DATASET_CONFIGS.keys())
    coverage: CoverageMap = {}

    logger.info(f"Computing coverage for {len(leagues)} leagues, " f"{len(datasets)} datasets...")
    logger.info("")

    for league in leagues:
        league_coverage = []
        for dataset in datasets:
            # First try to compute from actual files
            cov = compute_coverage_for_league_dataset(league, dataset)

            # Fall back to known coverage if no files found
            if cov is None and include_known:
                known = KNOWN_COVERAGE.get((league, dataset))
                if known:
                    min_date, max_date, notes = known
                    cov = DatasetCoverage(
                        min_date=min_date,
                        max_date=max_date,
                        record_count=None,
                        last_updated=datetime.now().isoformat(),
                        notes=notes,
                    )

            if cov:
                coverage[(league, dataset)] = cov
                date_range = f"{cov.min_date} to {cov.max_date}"
                records = ""
                if cov.record_count:
                    records = f"({cov.record_count:,} records)"
                source = ""
                if hasattr(cov, "notes") and cov.notes:
                    source = f" [{cov.notes}]"
                league_coverage.append(f"  {dataset}: {date_range} {records}{source}")

        if league_coverage:
            logger.info(f"{league}:")
            for line in league_coverage:
                logger.info(line)
            logger.info("")

    logger.info(f"Total: {len(coverage)} league/dataset combinations with coverage")
    return coverage


def main():
    parser = argparse.ArgumentParser(description="Compute dataset coverage metadata")
    parser.add_argument(
        "--leagues",
        nargs="+",
        help="Specific leagues to process (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/metadata/coverage.json"),
        help="Output file path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show debug output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Compute coverage
    coverage = compute_all_coverage(args.leagues)

    # Save results
    if coverage:
        save_coverage(coverage, args.output)
        logger.info(f"Coverage saved to {args.output}")
    else:
        logger.warning("No coverage data found")


if __name__ == "__main__":
    main()
