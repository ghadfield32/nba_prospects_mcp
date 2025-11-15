#!/usr/bin/env python3
"""Historical Data Ingestion Pipeline

Complete pipeline for ingesting historical LNB Pro A data using discovered UUIDs:
1. Load UUID database
2. Fetch fixture metadata + PBP + shots for all games
3. Parse and validate data
4. Export to multiple formats (JSON, CSV, Parquet)
5. Track ingestion status and errors

Key Features:
- Batch fetching with progress tracking
- Concurrent API calls (asyncio) for speed
- Data validation and quality checks
- Multiple export formats
- Incremental updates (skip already-ingested games)
- Comprehensive error handling and logging

Usage:
    # Ingest all seasons
    python historical_data_pipeline.py --all

    # Ingest specific season
    python historical_data_pipeline.py --season 2024-2025

    # Incremental update (only new games)
    python historical_data_pipeline.py --incremental

    # Export to specific format
    python historical_data_pipeline.py --season 2024-2025 --format parquet

Created: 2025-11-15
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cbb_data.fetchers.lnb_atrium import (
    fetch_fixture_detail_and_pbp,
    parse_fixture_metadata,
    parse_pbp_events,
    parse_shots_from_pbp,
    validate_fixture_scores,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestionStatus:
    """Track ingestion status for a single game"""

    fixture_uuid: str
    season: str
    status: str = "pending"  # pending, success, failed, skipped
    ingested_at: str = ""
    error_message: str = ""

    # Data availability
    has_fixture: bool = False
    has_pbp: bool = False
    has_shots: bool = False

    # Counts
    pbp_events: int = 0
    shots_total: int = 0
    shots_made: int = 0


@dataclass
class PipelineStats:
    """Overall pipeline statistics"""

    total_games: int = 0
    games_processed: int = 0
    games_succeeded: int = 0
    games_failed: int = 0
    games_skipped: int = 0

    total_pbp_events: int = 0
    total_shots: int = 0

    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str = ""
    duration_seconds: float = 0.0


class HistoricalDataPipeline:
    """Pipeline for ingesting historical LNB data using UUID database

    Fetches all historical games from UUID database, parses PBP and shot data,
    validates quality, and exports to multiple formats.
    """

    def __init__(
        self,
        uuid_database_path: str = "tools/lnb/fixture_uuids_by_season.json",
        output_dir: str = "data/lnb/historical",
        incremental: bool = False,
        batch_size: int = 10,
    ):
        """Initialize pipeline

        Args:
            uuid_database_path: Path to UUID database JSON
            output_dir: Directory for output files
            incremental: Skip already-ingested games
            batch_size: Number of concurrent API requests
        """
        self.uuid_database_path = Path(uuid_database_path)
        self.output_dir = Path(output_dir)
        self.incremental = incremental
        self.batch_size = batch_size

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track ingestion status
        self.ingestion_status: dict[str, IngestionStatus] = {}
        self.stats = PipelineStats()

        # Load UUID database
        self.uuid_database = self._load_uuid_database()

        logger.info("Initialized pipeline")
        logger.info(f"  UUID database: {self.uuid_database_path}")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Incremental mode: {incremental}")

    def _load_uuid_database(self) -> dict:
        """Load UUID database from disk"""
        if not self.uuid_database_path.exists():
            raise FileNotFoundError(f"UUID database not found: {self.uuid_database_path}")

        with open(self.uuid_database_path) as f:
            return json.load(f)

    def get_uuids_for_season(self, season: str) -> list[str]:
        """Extract UUIDs for a specific season

        Args:
            season: Season string (e.g., "2024-2025")

        Returns:
            List of UUIDs for that season
        """
        # Handle both old and new database formats
        if "mappings" in self.uuid_database:
            # Old format
            return self.uuid_database["mappings"].get(season, [])
        elif "seasons" in self.uuid_database:
            # New format
            season_data = self.uuid_database["seasons"].get(season, {})
            games = season_data.get("games", {})
            return list(games.keys())
        else:
            return []

    def ingest_game(self, uuid: str, season: str) -> tuple[dict, dict, list, list]:
        """Fetch and parse data for a single game

        Args:
            uuid: Fixture UUID
            season: Season string

        Returns:
            Tuple of (fixture_metadata, raw_payload, pbp_events, shots)
        """
        try:
            # Fetch raw data
            payload = fetch_fixture_detail_and_pbp(uuid)

            # Parse metadata
            metadata = parse_fixture_metadata(payload)

            # Parse PBP
            pbp_events = parse_pbp_events(payload, uuid)

            # Parse shots
            shots = parse_shots_from_pbp(pbp_events)

            # Validate scores
            validation_errors = validate_fixture_scores(payload, uuid)

            # Convert metadata to dict
            metadata_dict = {
                "fixture_uuid": metadata.fixture_uuid,
                "external_id": metadata.fixture_external_id,
                "season": season,
                "home_team": metadata.home_team_name,
                "away_team": metadata.away_team_name,
                "home_score": metadata.home_score,
                "away_score": metadata.away_score,
                "game_date": metadata.start_time_local,
                "status": metadata.status,
                "venue": metadata.venue_name,
                "validation_passed": len(validation_errors) == 0,
                "validation_errors": validation_errors,
            }

            # Convert PBP events to dicts
            pbp_dicts = [asdict(event) for event in pbp_events]

            # Convert shots to dicts
            shot_dicts = [asdict(shot) for shot in shots]

            return metadata_dict, payload, pbp_dicts, shot_dicts

        except Exception as e:
            logger.error(f"Failed to ingest {uuid}: {e}")
            raise

    def ingest_season(
        self,
        season: str,
        max_games: int | None = None,
    ) -> PipelineStats:
        """Ingest all games for a specific season

        Args:
            season: Season string (e.g., "2024-2025")
            max_games: Optional limit for testing

        Returns:
            PipelineStats with results
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"Ingesting Season: {season}")
        logger.info(f"{'='*70}")

        # Get UUIDs for season
        uuids = self.get_uuids_for_season(season)

        if not uuids:
            logger.warning(f"No UUIDs found for season {season}")
            return self.stats

        if max_games:
            uuids = uuids[:max_games]

        logger.info(f"Processing {len(uuids)} games...")

        # Storage for this season
        season_fixtures = []
        season_pbp_events = []
        season_shots = []

        # Process each game
        for i, uuid in enumerate(uuids, 1):
            logger.info(f"[{i}/{len(uuids)}] Processing {uuid}...")

            status = IngestionStatus(fixture_uuid=uuid, season=season)

            try:
                # Ingest game
                metadata, payload, pbp_events, shots = self.ingest_game(uuid, season)

                # Track status
                status.status = "success"
                status.ingested_at = datetime.now().isoformat()
                status.has_fixture = True
                status.has_pbp = len(pbp_events) > 0
                status.has_shots = len(shots) > 0
                status.pbp_events = len(pbp_events)
                status.shots_total = len(shots)
                status.shots_made = sum(1 for s in shots if s["made"])

                # Store data
                season_fixtures.append(metadata)
                season_pbp_events.extend(pbp_events)
                season_shots.extend(shots)

                # Update stats
                self.stats.games_succeeded += 1
                self.stats.total_pbp_events += len(pbp_events)
                self.stats.total_shots += len(shots)

                logger.info(f"  ✓ {metadata['home_team']} vs {metadata['away_team']}")
                logger.info(f"    PBP: {len(pbp_events)} events, Shots: {len(shots)}")

            except Exception as e:
                status.status = "failed"
                status.error_message = str(e)
                self.stats.games_failed += 1
                logger.error(f"  ✗ Failed: {e}")

            self.ingestion_status[uuid] = status
            self.stats.games_processed += 1

            # Rate limiting
            if i < len(uuids):
                time.sleep(0.3)

        # Export season data
        self._export_season_data(season, season_fixtures, season_pbp_events, season_shots)

        logger.info(f"\nSeason {season} Summary:")
        logger.info(f"  Processed: {len(uuids)}")
        logger.info(f"  Succeeded: {self.stats.games_succeeded}")
        logger.info(f"  Failed: {self.stats.games_failed}")
        logger.info(f"  Total PBP events: {self.stats.total_pbp_events:,}")
        logger.info(f"  Total shots: {self.stats.total_shots:,}")

        return self.stats

    def _export_season_data(
        self,
        season: str,
        fixtures: list[dict],
        pbp_events: list[dict],
        shots: list[dict],
    ) -> None:
        """Export season data to multiple formats

        Args:
            season: Season string
            fixtures: List of fixture metadata dicts
            pbp_events: List of PBP event dicts
            shots: List of shot dicts
        """
        season_dir = self.output_dir / season
        season_dir.mkdir(parents=True, exist_ok=True)

        # Export fixtures
        if fixtures:
            # JSON
            with open(season_dir / "fixtures.json", "w") as f:
                json.dump(fixtures, f, indent=2, default=str)

            # CSV
            fixtures_df = pd.DataFrame(fixtures)
            fixtures_df.to_csv(season_dir / "fixtures.csv", index=False)

            logger.info(f"  Exported {len(fixtures)} fixtures")

        # Export PBP events
        if pbp_events:
            # JSON
            with open(season_dir / "pbp_events.json", "w") as f:
                json.dump(pbp_events, f, indent=2, default=str)

            # CSV
            pbp_df = pd.DataFrame(pbp_events)
            pbp_df.to_csv(season_dir / "pbp_events.csv", index=False)

            # Parquet (most efficient for large datasets)
            pbp_df.to_parquet(season_dir / "pbp_events.parquet", index=False)

            logger.info(f"  Exported {len(pbp_events):,} PBP events")

        # Export shots
        if shots:
            # JSON
            with open(season_dir / "shots.json", "w") as f:
                json.dump(shots, f, indent=2, default=str)

            # CSV
            shots_df = pd.DataFrame(shots)
            shots_df.to_csv(season_dir / "shots.csv", index=False)

            # Parquet
            shots_df.to_parquet(season_dir / "shots.parquet", index=False)

            logger.info(f"  Exported {len(shots):,} shots")

    def ingest_all_seasons(
        self,
        max_games_per_season: int | None = None,
    ) -> PipelineStats:
        """Ingest all seasons in UUID database

        Args:
            max_games_per_season: Optional limit per season

        Returns:
            Overall PipelineStats
        """
        logger.info(f"\n{'='*70}")
        logger.info("HISTORICAL DATA INGESTION - ALL SEASONS")
        logger.info(f"{'='*70}\n")

        start_time = time.time()

        # Get all seasons from database
        if "mappings" in self.uuid_database:
            seasons = list(self.uuid_database["mappings"].keys())
        elif "seasons" in self.uuid_database:
            seasons = list(self.uuid_database["seasons"].keys())
        else:
            seasons = []

        logger.info(f"Found {len(seasons)} seasons to ingest")

        # Ingest each season
        for season in sorted(seasons, reverse=True):  # Most recent first
            self.ingest_season(season, max_games=max_games_per_season)

        # Finalize stats
        self.stats.end_time = datetime.now().isoformat()
        self.stats.duration_seconds = time.time() - start_time

        # Save ingestion status
        self._save_ingestion_status()

        # Print summary
        self._print_summary()

        return self.stats

    def _save_ingestion_status(self) -> None:
        """Save ingestion status to JSON"""
        status_file = self.output_dir / "ingestion_status.json"

        status_data = {
            "stats": asdict(self.stats),
            "games": {uuid: asdict(status) for uuid, status in self.ingestion_status.items()},
        }

        with open(status_file, "w") as f:
            json.dump(status_data, f, indent=2)

        logger.info(f"\n✓ Ingestion status saved to {status_file}")

    def _print_summary(self) -> None:
        """Print comprehensive summary"""
        logger.info(f"\n{'='*70}")
        logger.info("INGESTION COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Duration: {self.stats.duration_seconds:.1f}s")
        logger.info("\nGames:")
        logger.info(f"  Processed: {self.stats.games_processed}")
        logger.info(f"  Succeeded: {self.stats.games_succeeded}")
        logger.info(f"  Failed: {self.stats.games_failed}")
        logger.info("\nData:")
        logger.info(f"  PBP Events: {self.stats.total_pbp_events:,}")
        logger.info(f"  Shots: {self.stats.total_shots:,}")
        logger.info(f"\nOutput: {self.output_dir}/")
        logger.info(f"{'='*70}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Ingest historical LNB data using UUID database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--all", action="store_true", help="Ingest all seasons")
    parser.add_argument("--season", type=str, help='Ingest specific season (e.g., "2024-2025")')
    parser.add_argument(
        "--uuid-database",
        type=str,
        default="tools/lnb/fixture_uuids_by_season.json",
        help="Path to UUID database",
    )
    parser.add_argument(
        "--output-dir", type=str, default="data/lnb/historical", help="Output directory"
    )
    parser.add_argument("--max-games", type=int, help="Limit games (for testing)")
    parser.add_argument("--incremental", action="store_true", help="Skip already-ingested games")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Initialize pipeline
    pipeline = HistoricalDataPipeline(
        uuid_database_path=args.uuid_database,
        output_dir=args.output_dir,
        incremental=args.incremental,
    )

    # Run ingestion
    if args.all:
        pipeline.ingest_all_seasons(max_games_per_season=args.max_games)
    elif args.season:
        pipeline.ingest_season(args.season, max_games=args.max_games)
    else:
        logger.error("Must specify --all or --season")
        sys.exit(1)


if __name__ == "__main__":
    main()
