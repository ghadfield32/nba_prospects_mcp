#!/usr/bin/env python3
"""
Golden Season Script for ACB (Spanish League)

Pulls dataset for ACB season:
- Player season stats (HTML/Zenodo - PRIMARY)
- Team season stats (HTML/aggregated - PRIMARY)
- Schedule (HTML - if available)
- Player/Team game stats (HTML - if available for recent seasons)

Note: PBP and shot data are NOT reliably available for ACB and are skipped.

Usage:
    python scripts/golden_acb.py --season 2023-24
    python scripts/golden_acb.py --season 2022 --use-zenodo
    python scripts/golden_acb.py --season 2023-24 --include-games
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.base_golden_season import GoldenSeasonScript
from src.cbb_data.fetchers import acb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ACBGoldenSeason(GoldenSeasonScript):
    """
    Golden season script for ACB (Spanish League).

    Focus: Season-level data (player/team season stats)
    Optional: Game-level data for recent seasons where available
    """

    def __init__(self, season: str, include_games: bool = False,
                use_zenodo: bool = False, **kwargs):
        super().__init__("ACB", season, **kwargs)

        self.include_games = include_games
        self.use_zenodo = use_zenodo

        logger.info(f"ACB Golden Season Configuration:")
        logger.info(f"  Season: {season}")
        logger.info(f"  Include games: {include_games}")
        logger.info(f"  Use Zenodo: {use_zenodo}")

    def fetch_schedule(self) -> pd.DataFrame:
        """
        Fetch ACB schedule.

        This is optional/best-effort for ACB.
        """
        if not self.include_games:
            logger.info("Game-level data disabled, skipping schedule")
            return pd.DataFrame()

        try:
            df = acb.fetch_acb_schedule(self.season)
            logger.info(f"Fetched {len(df)} games from ACB schedule")

            if df.empty:
                logger.warning("Schedule returned empty - ACB may not have data for this season")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch ACB schedule: {e}")
            logger.info("This may be expected for older seasons or if ACB blocks container IPs")
            return pd.DataFrame()

    def fetch_player_game(self) -> pd.DataFrame:
        """
        Fetch ACB player game stats.

        This is optional/best-effort for recent seasons only.
        """
        if not self.include_games:
            logger.info("Game-level data disabled, skipping player_game")
            return pd.DataFrame()

        try:
            # ACB player_game requires either game_ids or schedule data
            schedule_df = self.datasets.get('schedule')

            if schedule_df is None or schedule_df.empty:
                logger.warning("No schedule available, cannot fetch player_game")
                return pd.DataFrame()

            game_ids = schedule_df['GAME_ID'].tolist()

            logger.info(f"Fetching player_game for {len(game_ids)} games...")

            # Note: This function may not exist yet - it's on the TODO list
            # If it doesn't exist, this will return empty DataFrame gracefully
            df = acb.fetch_acb_player_game(self.season, game_ids=game_ids)

            logger.info(f"Fetched {len(df)} player-game records")
            return df

        except AttributeError:
            logger.warning("fetch_acb_player_game not implemented yet - skipping")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to fetch ACB player_game: {e}")
            return pd.DataFrame()

    def fetch_team_game(self) -> pd.DataFrame:
        """
        Fetch ACB team game stats.

        This is optional/best-effort for recent seasons only.
        """
        if not self.include_games:
            logger.info("Game-level data disabled, skipping team_game")
            return pd.DataFrame()

        try:
            schedule_df = self.datasets.get('schedule')

            if schedule_df is None or schedule_df.empty:
                logger.warning("No schedule available, cannot fetch team_game")
                return pd.DataFrame()

            game_ids = schedule_df['GAME_ID'].tolist()

            logger.info(f"Fetching team_game for {len(game_ids)} games...")

            df = acb.fetch_acb_team_game(self.season, game_ids=game_ids)

            logger.info(f"Fetched {len(df)} team-game records")
            return df

        except AttributeError:
            logger.warning("fetch_acb_team_game not implemented yet - skipping")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to fetch ACB team_game: {e}")
            return pd.DataFrame()

    def fetch_pbp(self) -> pd.DataFrame:
        """
        PBP not available for ACB.

        ACB doesn't consistently expose play-by-play data for free.
        """
        logger.info("ACB PBP not available (expected)")
        return pd.DataFrame()

    def fetch_shots(self) -> pd.DataFrame:
        """
        Shot data not available for ACB.

        ACB doesn't consistently expose shot chart data for free.
        """
        logger.info("ACB shots not available (expected)")
        return pd.DataFrame()

    def fetch_player_season(self) -> pd.DataFrame:
        """
        Fetch ACB player season stats.

        PRIMARY DATA SOURCE for ACB.

        Uses HTML scraping or Zenodo historical data.
        """
        try:
            logger.info(f"Fetching ACB player season stats...")

            if self.use_zenodo:
                logger.info("  Using Zenodo historical data")
                # TODO: Wire in Zenodo data path
                # For now, fall back to HTML
                logger.warning("  Zenodo integration not wired yet, falling back to HTML")

            df = acb.fetch_acb_player_season(self.season)

            logger.info(f"Fetched {len(df)} player season records")

            # Check for SOURCE column
            if 'SOURCE' in df.columns:
                sources = df['SOURCE'].value_counts()
                logger.info(f"  Sources: {sources.to_dict()}")

            if df.empty:
                logger.warning("Player season returned empty!")
                logger.warning("  Possible reasons:")
                logger.warning("  - ACB blocking container IP (403)")
                logger.warning("  - Season format incorrect")
                logger.warning("  - Website structure changed")
                logger.warning("  Try running from local machine or using Zenodo data")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch ACB player_season: {e}")
            logger.info("  This is CRITICAL as player_season is primary ACB data source")
            return pd.DataFrame()

    def fetch_team_season(self) -> pd.DataFrame:
        """
        Fetch ACB team season stats.

        PRIMARY DATA SOURCE for ACB.

        Uses HTML scraping or aggregation from player data.
        """
        try:
            logger.info(f"Fetching ACB team season stats...")

            df = acb.fetch_acb_team_season(self.season)

            logger.info(f"Fetched {len(df)} team season records")

            # Check for SOURCE column
            if 'SOURCE' in df.columns:
                sources = df['SOURCE'].value_counts()
                logger.info(f"  Sources: {sources.to_dict()}")

            if df.empty:
                logger.warning("Team season returned empty!")
                logger.warning("  Same issues as player_season (403, format, etc.)")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch ACB team_season: {e}")
            logger.info("  This is CRITICAL as team_season is primary ACB data source")
            return pd.DataFrame()

    def generate_summary_report(self) -> str:
        """
        Generate ACB-specific summary report.

        Overrides base class to add ACB-specific guidance.
        """
        base_summary = super().generate_summary_report()

        # Add ACB-specific notes
        acb_notes = []
        acb_notes.append("\nACB-SPECIFIC NOTES:")
        acb_notes.append("-" * 70)

        # Check if primary data sources are present
        player_season_ok = not self.datasets.get('player_season', pd.DataFrame()).empty
        team_season_ok = not self.datasets.get('team_season', pd.DataFrame()).empty

        if player_season_ok and team_season_ok:
            acb_notes.append("✅ PRIMARY DATA SOURCES HEALTHY")
            acb_notes.append("   Player season and team season data successfully fetched")
        else:
            acb_notes.append("❌ PRIMARY DATA SOURCES MISSING")
            if not player_season_ok:
                acb_notes.append("   ❌ Player season: EMPTY")
            if not team_season_ok:
                acb_notes.append("   ❌ Team season: EMPTY")

            acb_notes.append("\n   TROUBLESHOOTING:")
            acb_notes.append("   1. Check if running from container (may get 403)")
            acb_notes.append("      → Try from local machine")
            acb_notes.append("   2. Verify season format (e.g., '2023-24' not '2023')")
            acb_notes.append("   3. Use Zenodo data for historical seasons:")
            acb_notes.append("      → python tools/acb/setup_zenodo_data.py --download")
            acb_notes.append("      → python scripts/golden_acb.py --season 2022 --use-zenodo")

        # Game-level status
        if self.include_games:
            schedule_ok = not self.datasets.get('schedule', pd.DataFrame()).empty
            player_game_ok = not self.datasets.get('player_game', pd.DataFrame()).empty

            acb_notes.append("\nGAME-LEVEL DATA (OPTIONAL):")
            if schedule_ok or player_game_ok:
                acb_notes.append("   ⚠️  Partial game-level data available")
                if schedule_ok:
                    acb_notes.append(f"   ✓ Schedule: {len(self.datasets['schedule'])} games")
                if player_game_ok:
                    acb_notes.append(f"   ✓ Player game: {len(self.datasets['player_game'])} records")
            else:
                acb_notes.append("   ❌ Game-level data not available for this season")
                acb_notes.append("   This is expected for most ACB seasons")
        else:
            acb_notes.append("\nGAME-LEVEL DATA: Disabled (use --include-games to enable)")

        acb_notes.append("\nKNOWN LIMITATIONS:")
        acb_notes.append("   • PBP data: Not available for ACB")
        acb_notes.append("   • Shot data: Not available for ACB")
        acb_notes.append("   • Game-level: Best-effort for recent seasons only")
        acb_notes.append("   • IP blocking: ACB may block container/cloud IPs")

        return base_summary + "\n" + "\n".join(acb_notes) + "\n"


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Golden season script for ACB (Spanish League)"
    )
    parser.add_argument(
        "--season",
        required=True,
        help="Season (e.g., '2023-24')"
    )
    parser.add_argument(
        "--include-games",
        action="store_true",
        help="Attempt to fetch game-level data (schedule, player_game, team_game)"
    )
    parser.add_argument(
        "--use-zenodo",
        action="store_true",
        help="Use Zenodo historical data (for older seasons)"
    )
    parser.add_argument(
        "--format",
        default="parquet",
        choices=["parquet", "csv", "duckdb"],
        help="Output format (default: parquet)"
    )
    parser.add_argument(
        "--output-dir",
        default="data/golden",
        help="Output directory (default: data/golden)"
    )
    parser.add_argument(
        "--no-qa",
        action="store_true",
        help="Skip QA checks (faster)"
    )

    args = parser.parse_args()

    # Create and run script
    script = ACBGoldenSeason(
        season=args.season,
        include_games=args.include_games,
        use_zenodo=args.use_zenodo,
        output_dir=args.output_dir
    )

    success = script.run(
        save_format=args.format,
        run_qa=not args.no_qa
    )

    if success:
        logger.info(f"\n✅ ACB golden season script completed successfully")
        logger.info(f"   Data saved to: {script.output_dir}")

        # Give specific guidance based on results
        if script.datasets.get('player_season', pd.DataFrame()).empty:
            logger.warning("\n⚠️  PRIMARY DATA MISSING - See SUMMARY.txt for troubleshooting")

        sys.exit(0)
    else:
        logger.error(f"\n❌ ACB golden season script failed")
        logger.error("   Check errors above and SUMMARY.txt for details")
        sys.exit(1)


if __name__ == "__main__":
    main()
