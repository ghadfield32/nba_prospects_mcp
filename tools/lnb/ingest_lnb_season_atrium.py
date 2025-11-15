#!/usr/bin/env python3
"""
LNB Season Ingest via Atrium API

Full-season data ingestion driver for LNB Pro A using the Atrium Sports API.
This script replaces the broken LNB API endpoints with the working Atrium
fixture detail endpoint that provides fixture metadata + PBP + shots in a
single response.

Features:
---------
1. Fetches all fixtures for a season via get_calendar_by_division()
2. Maps external IDs → fixture UUIDs (if needed)
3. For each fixture, fetches detail + PBP from Atrium API
4. Parses and validates all data
5. Saves to Parquet/DuckDB with proper partitioning
6. Validates coverage and score consistency

Workflow:
---------
1. Get season fixture list (from working LNB endpoint)
2. For each fixture:
   - Fetch detail + PBP from Atrium
   - Parse fixture metadata
   - Parse PBP events
   - Extract shots from PBP
   - Validate scores
3. Concatenate all data into DataFrames
4. Write to Parquet with partitioning by season/competition
5. Generate coverage report

Usage:
------
    # Ingest full 2024-25 Betclic ÉLITE season
    python tools/lnb/ingest_lnb_season_atrium.py --year 2025 --division 1

    # Ingest with validation only (no write)
    python tools/lnb/ingest_lnb_season_atrium.py --year 2025 --division 1 --validate-only

    # Ingest specific fixture UUIDs
    python tools/lnb/ingest_lnb_season_atrium.py --fixture-uuids uuid1,uuid2,uuid3

Created: 2025-11-15
Reference: Atrium Sports API integration
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_api import LNBClient
from src.cbb_data.fetchers.lnb_atrium import (
    fetch_fixture_detail_and_pbp,
    parse_fixture_metadata,
    parse_pbp_events,
    parse_shots_from_pbp,
    validate_fixture_scores,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestStats:
    """Statistics for the ingest run"""

    fixtures_total: int = 0
    fixtures_fetched: int = 0
    fixtures_failed: int = 0
    fixtures_validated: int = 0
    fixtures_validation_failed: int = 0
    pbp_events_total: int = 0
    shots_total: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def map_external_id_to_uuid(external_id: str, season_year: int, division: int) -> str | None:
    """
    [DEPRECATED] Map LNB external ID to Atrium fixture UUID.

    NOTE: This function is no longer needed! The LNB calendar API response
    (from get_calendar_by_division) now includes the 'match_id' field which
    contains the Atrium fixture UUID directly. No mapping file is required.

    This function is kept for backwards compatibility but should not be used
    in new code.

    Discovery:
    ----------
    As of 2025-11-15, the calendar API returns games with:
    - external_id: 28910 (LNB numeric ID)
    - match_id: "0d0504a0-6715-11f0-98ab-27e6e78614e1" (Atrium UUID)

    The ingest script now extracts match_id directly from the calendar response.

    Args:
        external_id: LNB numeric game ID (e.g., "28914")
        season_year: Season year (2025 for 2024-25 season)
        division: Division ID (1 = Betclic ÉLITE)

    Returns:
        Fixture UUID or None if not found
    """
    logger.warning(
        f"[DEPRECATED] map_external_id_to_uuid() called for external_id={external_id}. "
        "This function is no longer needed - calendar API includes match_id directly."
    )

    # Fallback: check if mapping file exists (legacy support)
    mapping_file = Path(f"tools/lnb/fixture_uuids_{season_year}_div{division}.json")

    if mapping_file.exists():
        with open(mapping_file) as f:
            mapping = json.load(f)
        return mapping.get(str(external_id))

    return None


def ingest_season(
    year: int,
    division: int,
    fixture_uuids: list[str] | None = None,
    output_dir: str = "data/lnb",
    validate_only: bool = False,
    verbose: bool = False,
) -> IngestStats:
    """
    Ingest full season of LNB data via Atrium API.

    Args:
        year: Season year (e.g., 2025 for 2024-25 season)
        division: Division ID (1 = Betclic ÉLITE)
        fixture_uuids: Optional list of specific fixture UUIDs to ingest
        output_dir: Output directory for Parquet files
        validate_only: If True, validate but don't write files
        verbose: Enable verbose logging

    Returns:
        IngestStats with summary of ingest run

    Example:
        >>> stats = ingest_season(year=2025, division=1)
        >>> print(f"Ingested {stats.fixtures_fetched} fixtures")
    """
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logger.info(f"\n{'='*70}")
    logger.info("LNB Season Ingest via Atrium API")
    logger.info(f"{'='*70}")
    logger.info(f"Year: {year}")
    logger.info(f"Division: {division}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Validate only: {validate_only}")
    logger.info(f"{'='*70}\n")

    stats = IngestStats()

    # Step 1: Get fixture list
    if fixture_uuids is None:
        logger.info("[1/5] Fetching fixture list from get_calendar_by_division...")

        try:
            client = LNBClient()
            games = client.get_calendar_by_division(division_external_id=division, year=year)
            logger.info(f"   [OK] Found {len(games)} games")

            # Extract fixture UUIDs from games
            # The calendar response includes 'match_id' which is the Atrium fixture UUID
            fixture_uuids = []
            for game in games:
                # Try multiple possible field names for UUID
                uuid = game.get("match_id") or game.get("fixture_id") or game.get("fixture_uuid")

                if uuid:
                    fixture_uuids.append(uuid)
                else:
                    # Log warning if UUID is missing
                    external_id = game.get("external_id") or game.get("match_external_id")
                    logger.warning(
                        f"No fixture UUID found for game (external_id={external_id}). "
                        f"Available fields: {list(game.keys())}"
                    )

            logger.info(f"   [OK] Extracted {len(fixture_uuids)} fixture UUIDs")

        except Exception as e:
            logger.error(f"   [FAIL] Failed to fetch fixture list: {e}")
            stats.errors.append(f"Fixture list fetch failed: {e}")
            return stats
    else:
        logger.info(f"[1/5] Using provided fixture UUIDs: {len(fixture_uuids)} fixtures")

    stats.fixtures_total = len(fixture_uuids)

    # Step 2: Fetch and parse all fixtures
    logger.info("\n[2/5] Fetching fixture details from Atrium API...")

    fixtures_data = []
    pbp_data = []
    shots_data = []

    for idx, fixture_uuid in enumerate(fixture_uuids, 1):
        logger.info(f"   [{idx}/{stats.fixtures_total}] Fetching {fixture_uuid}...")

        try:
            # Fetch raw payload
            payload = fetch_fixture_detail_and_pbp(fixture_uuid)

            # Parse fixture metadata
            metadata = parse_fixture_metadata(payload)
            fixtures_data.append(asdict(metadata))

            # Parse PBP events
            pbp_events = parse_pbp_events(payload, fixture_uuid)
            pbp_data.extend(
                [
                    {
                        "fixture_uuid": e.fixture_uuid,
                        "event_id": e.event_id,
                        "period_id": e.period_id,
                        "clock_iso": e.clock_iso,
                        "clock_seconds": e.clock_seconds,
                        "team_id": e.team_id,
                        "player_id": e.player_id,
                        "player_bib": e.player_bib,
                        "player_name": e.player_name,
                        "event_type": e.event_type,
                        "event_sub_type": e.event_sub_type,
                        "description": e.description,
                        "success": e.success,
                        "x": e.x,
                        "y": e.y,
                        "home_score": e.home_score,
                        "away_score": e.away_score,
                    }
                    for e in pbp_events
                ]
            )

            # Parse shots
            shots = parse_shots_from_pbp(pbp_events)
            shots_data.extend(
                [
                    {
                        "fixture_uuid": s.fixture_uuid,
                        "event_id": s.event_id,
                        "period_id": s.period_id,
                        "clock_seconds": s.clock_seconds,
                        "team_id": s.team_id,
                        "player_id": s.player_id,
                        "player_name": s.player_name,
                        "shot_value": s.shot_value,
                        "shot_type": s.shot_type,
                        "made": s.made,
                        "x": s.x,
                        "y": s.y,
                        "home_score": s.home_score,
                        "away_score": s.away_score,
                    }
                    for s in shots
                ]
            )

            # Validate scores
            is_valid, errors = validate_fixture_scores(payload, pbp_events)

            if is_valid:
                stats.fixtures_validated += 1
            else:
                stats.fixtures_validation_failed += 1
                logger.warning(f"   [WARN] Score validation failed: {errors}")
                stats.errors.append(f"Fixture {fixture_uuid}: Score validation failed - {errors}")

            stats.fixtures_fetched += 1
            stats.pbp_events_total += len(pbp_events)
            stats.shots_total += len(shots)

        except Exception as e:
            stats.fixtures_failed += 1
            error_msg = f"Fixture {fixture_uuid}: {str(e)}"
            logger.error(f"   [FAIL] {error_msg}")
            stats.errors.append(error_msg)

    # Step 3: Create DataFrames
    logger.info("\n[3/5] Creating DataFrames...")

    df_fixtures = pd.DataFrame(fixtures_data)
    df_pbp = pd.DataFrame(pbp_data)
    df_shots = pd.DataFrame(shots_data)

    logger.info(f"   Fixtures: {len(df_fixtures)} rows")
    logger.info(f"   PBP Events: {len(df_pbp)} rows")
    logger.info(f"   Shots: {len(df_shots)} rows")

    # Step 4: Validate coverage
    logger.info("\n[4/5] Validating coverage...")

    coverage_report = {
        "fixtures_expected": stats.fixtures_total,
        "fixtures_fetched": stats.fixtures_fetched,
        "fixtures_failed": stats.fixtures_failed,
        "coverage_pct": round(stats.fixtures_fetched / stats.fixtures_total * 100, 1)
        if stats.fixtures_total > 0
        else 0,
        "pbp_events_total": stats.pbp_events_total,
        "shots_total": stats.shots_total,
        "validation_passed": stats.fixtures_validated,
        "validation_failed": stats.fixtures_validation_failed,
    }

    logger.info(f"   Coverage: {coverage_report['coverage_pct']:.1f}%")
    logger.info(f"   Validated: {stats.fixtures_validated}/{stats.fixtures_fetched}")

    # Step 5: Write to Parquet (if not validate-only)
    if not validate_only:
        logger.info("\n[5/5] Writing to Parquet...")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Write fixtures
        fixtures_file = output_path / f"lnb_fixtures_{year}_div{division}.parquet"
        df_fixtures.to_parquet(fixtures_file, index=False)
        logger.info(f"   Fixtures: {fixtures_file}")

        # Write PBP
        pbp_file = output_path / f"lnb_pbp_{year}_div{division}.parquet"
        df_pbp.to_parquet(pbp_file, index=False)
        logger.info(f"   PBP: {pbp_file}")

        # Write shots
        shots_file = output_path / f"lnb_shots_{year}_div{division}.parquet"
        df_shots.to_parquet(shots_file, index=False)
        logger.info(f"   Shots: {shots_file}")

        # Write coverage report
        report_file = output_path / f"lnb_coverage_{year}_div{division}.json"
        with open(report_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "year": year,
                    "division": division,
                    "coverage": coverage_report,
                    "errors": stats.errors,
                },
                f,
                indent=2,
            )
        logger.info(f"   Coverage report: {report_file}")
    else:
        logger.info("\n[5/5] Skipping write (validate-only mode)")

    # Final summary
    logger.info(f"\n{'='*70}")
    logger.info("Ingest Complete")
    logger.info(f"{'='*70}")
    logger.info(f"Fixtures fetched: {stats.fixtures_fetched}/{stats.fixtures_total}")
    logger.info(f"PBP events: {stats.pbp_events_total}")
    logger.info(f"Shots: {stats.shots_total}")
    logger.info(f"Validation passed: {stats.fixtures_validated}")
    logger.info(f"Errors: {len(stats.errors)}")
    logger.info(f"{'='*70}\n")

    return stats


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Ingest full LNB season via Atrium API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest full 2024-25 Betclic ÉLITE season
  python tools/lnb/ingest_lnb_season_atrium.py --year 2025 --division 1

  # Validate only (no write)
  python tools/lnb/ingest_lnb_season_atrium.py --year 2025 --division 1 --validate-only

  # Ingest specific fixtures
  python tools/lnb/ingest_lnb_season_atrium.py --fixture-uuids uuid1,uuid2,uuid3
        """,
    )

    parser.add_argument("--year", type=int, help="Season year (e.g., 2025 for 2024-25 season)")
    parser.add_argument(
        "--division", type=int, default=1, help="Division ID (1=Betclic ÉLITE, 2=Pro B)"
    )
    parser.add_argument(
        "--fixture-uuids", type=str, help="Comma-separated list of fixture UUIDs to ingest"
    )
    parser.add_argument(
        "--output-dir", default="data/lnb", help="Output directory for Parquet files"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Validate but don't write files"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Parse fixture UUIDs if provided
    fixture_uuids = None
    if args.fixture_uuids:
        fixture_uuids = [uuid.strip() for uuid in args.fixture_uuids.split(",")]

    # Validate inputs
    if args.year is None and fixture_uuids is None:
        parser.error("Must provide either --year or --fixture-uuids")

    # Run ingest
    stats = ingest_season(
        year=args.year or datetime.now().year,
        division=args.division,
        fixture_uuids=fixture_uuids,
        output_dir=args.output_dir,
        validate_only=args.validate_only,
        verbose=args.verbose,
    )

    # Exit with error code if too many failures
    if stats.fixtures_failed > stats.fixtures_fetched * 0.1:  # >10% failure rate
        print(f"\n[ERROR] High failure rate: {stats.fixtures_failed}/{stats.fixtures_total}")
        sys.exit(1)

    print("\n[OK] Ingest complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
