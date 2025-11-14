"""
Base Golden Season Script Template

Shared functionality for per-league golden season scripts.
Each league script extends this base class with league-specific logic.
"""

import logging
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cbb_data.storage import get_storage, save_to_disk
from src.cbb_data.utils.data_qa import (
    DataQAResults,
    run_cross_granularity_qa,
    run_player_game_qa,
    run_schedule_qa,
    run_team_game_qa,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GoldenSeasonScript(ABC):
    """
    Base class for golden season data pull scripts.

    Each league implements:
    - fetch_schedule()
    - fetch_player_game()
    - fetch_team_game()
    - fetch_pbp() [optional]
    - fetch_shots() [optional]
    - fetch_player_season() [optional]
    - fetch_team_season() [optional]
    """

    def __init__(self, league: str, season: str, output_dir: str = "data/golden"):
        self.league = league
        self.season = season
        self.output_dir = Path(output_dir) / league.lower() / season.replace("-", "_")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.datasets: Dict[str, pd.DataFrame] = {}
        self.qa_results: Dict[str, DataQAResults] = {}

        logger.info(f"Initialized {league} golden season script for {season}")
        logger.info(f"Output directory: {self.output_dir}")

    # Abstract methods that must be implemented by each league

    @abstractmethod
    def fetch_schedule(self) -> pd.DataFrame:
        """Fetch schedule data for this league/season"""
        pass

    @abstractmethod
    def fetch_player_game(self) -> pd.DataFrame:
        """Fetch player game data"""
        pass

    @abstractmethod
    def fetch_team_game(self) -> pd.DataFrame:
        """Fetch team game data"""
        pass

    # Optional methods (default to empty DataFrames)

    def fetch_pbp(self) -> pd.DataFrame:
        """Fetch play-by-play data (optional)"""
        logger.info(f"{self.league}: PBP not implemented, returning empty DataFrame")
        return pd.DataFrame()

    def fetch_shots(self) -> pd.DataFrame:
        """Fetch shot data (optional)"""
        logger.info(f"{self.league}: Shots not implemented, returning empty DataFrame")
        return pd.DataFrame()

    def fetch_player_season(self) -> pd.DataFrame:
        """Fetch player season aggregates (optional)"""
        logger.info(f"{self.league}: Player season not implemented, returning empty DataFrame")
        return pd.DataFrame()

    def fetch_team_season(self) -> pd.DataFrame:
        """Fetch team season aggregates (optional)"""
        logger.info(f"{self.league}: Team season not implemented, returning empty DataFrame")
        return pd.DataFrame()

    # Core workflow methods

    def fetch_all_data(self):
        """Fetch all data types"""
        logger.info(f"\n{'='*70}")
        logger.info(f"FETCHING DATA: {self.league} {self.season}")
        logger.info(f"{'='*70}\n")

        # Always fetch these
        logger.info("Fetching schedule...")
        self.datasets['schedule'] = self.fetch_schedule()
        logger.info(f"  ✓ {len(self.datasets['schedule'])} games\n")

        logger.info("Fetching player game...")
        self.datasets['player_game'] = self.fetch_player_game()
        logger.info(f"  ✓ {len(self.datasets['player_game'])} player-games\n")

        logger.info("Fetching team game...")
        self.datasets['team_game'] = self.fetch_team_game()
        logger.info(f"  ✓ {len(self.datasets['team_game'])} team-games\n")

        # Optional datasets
        logger.info("Fetching PBP...")
        self.datasets['pbp'] = self.fetch_pbp()
        if not self.datasets['pbp'].empty:
            logger.info(f"  ✓ {len(self.datasets['pbp'])} events\n")
        else:
            logger.info(f"  - Skipped (not available)\n")

        logger.info("Fetching shots...")
        self.datasets['shots'] = self.fetch_shots()
        if not self.datasets['shots'].empty:
            logger.info(f"  ✓ {len(self.datasets['shots'])} shots\n")
        else:
            logger.info(f"  - Skipped (not available)\n")

        logger.info("Fetching player season...")
        self.datasets['player_season'] = self.fetch_player_season()
        if not self.datasets['player_season'].empty:
            logger.info(f"  ✓ {len(self.datasets['player_season'])} players\n")
        else:
            logger.info(f"  - Skipped (not available)\n")

        logger.info("Fetching team season...")
        self.datasets['team_season'] = self.fetch_team_season()
        if not self.datasets['team_season'].empty:
            logger.info(f"  ✓ {len(self.datasets['team_season'])} teams\n")
        else:
            logger.info(f"  - Skipped (not available)\n")

    def run_qa_checks(self):
        """Run QA checks on all datasets"""
        logger.info(f"\n{'='*70}")
        logger.info(f"RUNNING QA CHECKS: {self.league} {self.season}")
        logger.info(f"{'='*70}\n")

        # Individual dataset checks
        if not self.datasets['schedule'].empty:
            self.qa_results['schedule'] = run_schedule_qa(
                self.datasets['schedule'], self.league, self.season
            )
            self.qa_results['schedule'].print_summary()

        if not self.datasets['player_game'].empty:
            self.qa_results['player_game'] = run_player_game_qa(
                self.datasets['player_game'], self.league, self.season
            )
            self.qa_results['player_game'].print_summary()

        if not self.datasets['team_game'].empty:
            self.qa_results['team_game'] = run_team_game_qa(
                self.datasets['team_game'], self.league, self.season
            )
            self.qa_results['team_game'].print_summary()

        # Cross-granularity checks
        if not self.datasets['schedule'].empty and not self.datasets['team_game'].empty:
            self.qa_results['cross_granularity'] = run_cross_granularity_qa(
                self.datasets['schedule'],
                self.datasets['player_game'],
                self.datasets['team_game'],
                self.league,
                self.season
            )
            self.qa_results['cross_granularity'].print_summary()

    def save_all_data(self, format: str = "parquet"):
        """
        Save all datasets to disk.

        Args:
            format: Output format ('parquet', 'csv', or 'duckdb')
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"SAVING DATA: {self.league} {self.season}")
        logger.info(f"{'='*70}\n")

        for dataset_name, df in self.datasets.items():
            if df.empty:
                logger.info(f"Skipping {dataset_name} (empty)")
                continue

            output_path = self.output_dir / f"{dataset_name}.{format}"

            logger.info(f"Saving {dataset_name} ({len(df):,} rows) to {output_path}")

            try:
                save_to_disk(
                    df,
                    str(output_path),
                    format=format,
                    league=self.league,
                    season=self.season,
                    data_type=dataset_name
                )
                logger.info(f"  ✓ Saved successfully\n")

            except Exception as e:
                logger.error(f"  ✗ Failed to save {dataset_name}: {e}\n")

    def generate_summary_report(self) -> str:
        """Generate summary report of the pull"""
        report = []
        report.append(f"\n{'='*70}")
        report.append(f"GOLDEN SEASON SUMMARY: {self.league} {self.season}")
        report.append(f"{'='*70}\n")

        # Dataset sizes
        report.append("Dataset Sizes:")
        for dataset_name, df in self.datasets.items():
            if df.empty:
                status = "❌ Empty"
            else:
                status = f"✅ {len(df):,} rows"
            report.append(f"  {dataset_name:20} {status}")

        report.append("")

        # QA Summary
        report.append("QA Results:")
        all_healthy = True
        for qa_name, qa_result in self.qa_results.items():
            if qa_result.is_healthy():
                report.append(f"  {qa_name:20} ✅ HEALTHY")
            else:
                report.append(f"  {qa_name:20} ❌ UNHEALTHY ({len(qa_result.errors)} errors)")
                all_healthy = False

        report.append("")

        # Overall status
        if all_healthy and all(not df.empty for name, df in self.datasets.items()
                               if name in ['schedule', 'player_game', 'team_game']):
            report.append("✅ OVERALL STATUS: HEALTHY & COMPLETE")
            report.append(f"   All core datasets present and passing QA checks")
        else:
            report.append("⚠️  OVERALL STATUS: ISSUES FOUND")
            if not all_healthy:
                report.append("   Some QA checks failed (see details above)")
            missing = [name for name in ['schedule', 'player_game', 'team_game']
                      if self.datasets.get(name, pd.DataFrame()).empty]
            if missing:
                report.append(f"   Missing core datasets: {missing}")

        report.append("")
        report.append(f"Output directory: {self.output_dir}")
        report.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"{'='*70}\n")

        return "\n".join(report)

    def run(self, save_format: str = "parquet", run_qa: bool = True) -> bool:
        """
        Run the complete golden season workflow.

        Args:
            save_format: Output format for saved data
            run_qa: Whether to run QA checks

        Returns:
            True if successful and healthy, False otherwise
        """
        try:
            # Step 1: Fetch all data
            self.fetch_all_data()

            # Step 2: Run QA
            if run_qa:
                self.run_qa_checks()

            # Step 3: Save data
            self.save_all_data(format=save_format)

            # Step 4: Print summary
            summary = self.generate_summary_report()
            print(summary)

            # Save summary to file
            summary_path = self.output_dir / "SUMMARY.txt"
            with open(summary_path, 'w') as f:
                f.write(summary)

            # Check if healthy
            if run_qa:
                all_healthy = all(qa.is_healthy() for qa in self.qa_results.values())
                core_present = all(not self.datasets.get(name, pd.DataFrame()).empty
                                  for name in ['schedule', 'player_game', 'team_game'])
                return all_healthy and core_present
            else:
                return True

        except Exception as e:
            logger.error(f"Golden season script failed: {e}", exc_info=True)
            return False
