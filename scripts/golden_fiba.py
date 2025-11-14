#!/usr/bin/env python3
"""
Golden Season Script for FIBA Leagues (BCL, BAL, ABA, LKL)

Pulls complete dataset for a FIBA league season:
- Schedule (from game index)
- Player game stats (JSON → HTML fallback)
- Team game stats
- Play-by-play
- Shot chart with coordinates
- Player season aggregates
- Team season aggregates

Runs QA checks and saves to Parquet.

Usage:
    python scripts/golden_fiba.py --league BCL --season 2023-24
    python scripts/golden_fiba.py --league BAL --season 2024
    python scripts/golden_fiba.py --league ABA --season 2023-24 --format parquet
    python scripts/golden_fiba.py --league LKL --season 2023-24 --no-qa
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.base_golden_season import GoldenSeasonScript
from src.cbb_data.fetchers import aba, bal, bcl, lkl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FIBAGoldenSeason(GoldenSeasonScript):
    """
    Golden season script for FIBA leagues.

    All FIBA leagues (BCL, BAL, ABA, LKL) use the same FIBA LiveStats backend,
    so this script works for all of them.
    """

    def __init__(self, league: str, season: str, **kwargs):
        super().__init__(league, season, **kwargs)

        # Map league code to fetcher module
        self.fetcher_map = {
            "BCL": bcl,
            "BAL": bal,
            "ABA": aba,
            "LKL": lkl,
        }

        if league not in self.fetcher_map:
            raise ValueError(
                f"Unknown FIBA league: {league}. Must be one of: {list(self.fetcher_map.keys())}"
            )

        self.fetcher = self.fetcher_map[league]
        logger.info(f"Using fetcher module: {self.fetcher.__name__}")

    def fetch_schedule(self) -> pd.DataFrame:
        """Fetch schedule from FIBA fetcher"""
        try:
            func_name = f"fetch_{self.league.lower()}_schedule"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} games from {func_name}")
            return df

        except AttributeError:
            # Fallback to generic fetch_schedule if exists
            try:
                df = self.fetcher.fetch_schedule(self.season)
                logger.info(f"Fetched {len(df)} games from fetch_schedule")
                return df
            except Exception as e:
                logger.error(f"Failed to fetch schedule: {e}")
                return pd.DataFrame()

    def fetch_player_game(self) -> pd.DataFrame:
        """Fetch player game stats"""
        try:
            func_name = f"fetch_{self.league.lower()}_player_game"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} player-games from {func_name}")

            # Check for SOURCE column (should have fiba_json or fiba_html)
            if 'SOURCE' in df.columns:
                source_counts = df['SOURCE'].value_counts()
                logger.info(f"  Sources: {source_counts.to_dict()}")

            return df

        except AttributeError:
            # Fallback
            try:
                df = self.fetcher.fetch_player_game(self.season)
                logger.info(f"Fetched {len(df)} player-games")
                return df
            except Exception as e:
                logger.error(f"Failed to fetch player_game: {e}")
                return pd.DataFrame()

    def fetch_team_game(self) -> pd.DataFrame:
        """Fetch team game stats"""
        try:
            func_name = f"fetch_{self.league.lower()}_team_game"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} team-games from {func_name}")
            return df

        except AttributeError:
            try:
                df = self.fetcher.fetch_team_game(self.season)
                logger.info(f"Fetched {len(df)} team-games")
                return df
            except Exception as e:
                logger.error(f"Failed to fetch team_game: {e}")
                return pd.DataFrame()

    def fetch_pbp(self) -> pd.DataFrame:
        """Fetch play-by-play data"""
        try:
            func_name = f"fetch_{self.league.lower()}_pbp"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} PBP events from {func_name}")

            # Check for score tracking
            if 'SCORE_HOME' in df.columns and 'SCORE_AWAY' in df.columns:
                # Show final score from last event
                if not df.empty:
                    final = df.iloc[-1]
                    logger.info(
                        f"  Sample final score: {final.get('SCORE_HOME')} - {final.get('SCORE_AWAY')}"
                    )

            return df

        except AttributeError:
            try:
                df = self.fetcher.fetch_pbp(self.season)
                logger.info(f"Fetched {len(df)} PBP events")
                return df
            except Exception as e:
                logger.error(f"Failed to fetch PBP: {e}")
                return pd.DataFrame()

    def fetch_shots(self) -> pd.DataFrame:
        """Fetch shot chart data with coordinates"""
        try:
            func_name = f"fetch_{self.league.lower()}_shots"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} shots from {func_name}")

            # Check for coordinates
            if 'X' in df.columns and 'Y' in df.columns:
                logger.info(f"  ✓ Shot coordinates present")

                # Sample coordinate range
                if not df.empty:
                    x_range = (df['X'].min(), df['X'].max())
                    y_range = (df['Y'].min(), df['Y'].max())
                    logger.info(f"  X range: [{x_range[0]:.1f}, {x_range[1]:.1f}]")
                    logger.info(f"  Y range: [{y_range[0]:.1f}, {y_range[1]:.1f}]")

            # Check for shot type breakdown
            if 'SHOT_VALUE' in df.columns:
                shot_types = df['SHOT_VALUE'].value_counts()
                logger.info(f"  Shot types: {shot_types.to_dict()}")

            return df

        except AttributeError:
            try:
                df = self.fetcher.fetch_shots(self.season)
                logger.info(f"Fetched {len(df)} shots")
                return df
            except Exception as e:
                logger.error(f"Failed to fetch shots: {e}")
                return pd.DataFrame()

    def fetch_player_season(self) -> pd.DataFrame:
        """
        Fetch player season aggregates.

        For FIBA leagues, this is typically aggregated from player_game data.
        """
        try:
            func_name = f"fetch_{self.league.lower()}_player_season"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} player season records from {func_name}")
            return df

        except AttributeError:
            # If no dedicated function, aggregate from player_game
            logger.info("No player_season function found, aggregating from player_game")

            if self.datasets.get('player_game') is None or self.datasets['player_game'].empty:
                logger.warning("Cannot aggregate player_season without player_game data")
                return pd.DataFrame()

            df_player_game = self.datasets['player_game']

            # Aggregate by league, season, team, player
            agg_cols = ['LEAGUE', 'SEASON', 'TEAM_ID', 'TEAM_NAME', 'PLAYER_ID', 'PLAYER_NAME']

            # Check which columns exist
            existing_agg_cols = [col for col in agg_cols if col in df_player_game.columns]

            if not existing_agg_cols:
                logger.error("Missing grouping columns for aggregation")
                return pd.DataFrame()

            # Stats to aggregate
            stat_cols = ['GP', 'MIN', 'PTS', 'FGM', 'FGA', 'FG3M', 'FG3A',
                        'FTM', 'FTA', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF']

            # Only aggregate columns that exist
            existing_stat_cols = [col for col in stat_cols if col in df_player_game.columns]

            if not existing_stat_cols:
                logger.error("No stat columns found for aggregation")
                return pd.DataFrame()

            # Perform aggregation
            df_agg = df_player_game.groupby(existing_agg_cols)[existing_stat_cols].sum().reset_index()

            logger.info(f"Aggregated to {len(df_agg)} player season records")
            return df_agg

    def fetch_team_season(self) -> pd.DataFrame:
        """
        Fetch team season aggregates.

        For FIBA leagues, this is typically aggregated from team_game data.
        """
        try:
            func_name = f"fetch_{self.league.lower()}_team_season"
            fetch_func = getattr(self.fetcher, func_name)
            df = fetch_func(self.season)

            logger.info(f"Fetched {len(df)} team season records from {func_name}")
            return df

        except AttributeError:
            # If no dedicated function, aggregate from team_game
            logger.info("No team_season function found, aggregating from team_game")

            if self.datasets.get('team_game') is None or self.datasets['team_game'].empty:
                logger.warning("Cannot aggregate team_season without team_game data")
                return pd.DataFrame()

            df_team_game = self.datasets['team_game']

            # Aggregate by league, season, team
            agg_cols = ['LEAGUE', 'SEASON', 'TEAM_ID', 'TEAM_NAME']
            existing_agg_cols = [col for col in agg_cols if col in df_team_game.columns]

            if not existing_agg_cols:
                logger.error("Missing grouping columns for aggregation")
                return pd.DataFrame()

            # Stats to aggregate
            stat_cols = ['GP', 'PTS', 'FGM', 'FGA', 'FG3M', 'FG3A',
                        'FTM', 'FTA', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF']

            existing_stat_cols = [col for col in stat_cols if col in df_team_game.columns]

            if not existing_stat_cols:
                logger.error("No stat columns found for aggregation")
                return pd.DataFrame()

            df_agg = df_team_game.groupby(existing_agg_cols)[existing_stat_cols].sum().reset_index()

            logger.info(f"Aggregated to {len(df_agg)} team season records")
            return df_agg

    def fetch_roster(self) -> pd.DataFrame:
        """
        Fetch team rosters/player bio from player_game data.

        Uses the FIBA optional upgrade function extract_roster_from_boxscore()
        to build a roster layer from player_game data.
        """
        try:
            # Import the roster extraction function
            from src.cbb_data.fetchers.fiba_html_common import extract_roster_from_boxscore

            # Check if player_game data exists
            if self.datasets.get('player_game') is None or self.datasets['player_game'].empty:
                logger.warning("Cannot extract roster without player_game data")
                return pd.DataFrame()

            logger.info(f"Extracting rosters from player_game data...")

            # Extract rosters using the implemented function
            df = extract_roster_from_boxscore(
                self.datasets['player_game'],
                self.league,
                self.season
            )

            logger.info(f"Extracted {len(df)} player-team roster entries")
            return df

        except Exception as e:
            logger.error(f"Failed to extract rosters: {e}")
            return pd.DataFrame()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Golden season script for FIBA leagues (BCL, BAL, ABA, LKL)"
    )
    parser.add_argument(
        "--league",
        required=True,
        choices=["BCL", "BAL", "ABA", "LKL"],
        help="FIBA league code"
    )
    parser.add_argument(
        "--season",
        required=True,
        help="Season (e.g., '2023-24' or '2024')"
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
    script = FIBAGoldenSeason(
        league=args.league,
        season=args.season,
        output_dir=args.output_dir
    )

    success = script.run(
        save_format=args.format,
        run_qa=not args.no_qa
    )

    if success:
        logger.info(f"\n✅ Golden season script completed successfully")
        logger.info(f"   Data saved to: {script.output_dir}")
        sys.exit(0)
    else:
        logger.error(f"\n❌ Golden season script failed (see errors above)")
        sys.exit(1)


if __name__ == "__main__":
    main()
