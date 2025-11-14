#!/usr/bin/env python3
"""
Golden Season Script for LNB Pro A (French League)

Pulls dataset for LNB season:
- Player season stats (Stats Centre API/HTML - PRIMARY)
- Team season stats (Stats Centre API/HTML - PRIMARY)

Note: Game-level, PBP, and shot data are NOT reliably available for free
and are skipped in this script.

Usage:
    python scripts/golden_lnb.py --season 2023-24
    python scripts/golden_lnb.py --season 2024-25 --format csv
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.base_golden_season import GoldenSeasonScript
from src.cbb_data.fetchers import lnb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LNBGoldenSeason(GoldenSeasonScript):
    """
    Golden season script for LNB Pro A (French League).

    Focus: Season-level data ONLY (player/team season stats)

    LNB's Stats Centre provides comprehensive season aggregates,
    which is the primary value for scouting purposes.

    Game-level data, PBP, and shots are not publicly available.
    """

    def __init__(self, season: str, **kwargs):
        super().__init__("LNB", season, **kwargs)

        logger.info(f"LNB Golden Season Configuration:")
        logger.info(f"  Season: {season}")
        logger.info(f"  Scope: Season-level data only")
        logger.info(f"  Competition: Betclic ÉLITE (Pro A)")

    def fetch_schedule(self) -> pd.DataFrame:
        """
        Schedule not implemented for LNB v1.

        LNB's primary value is season-level scouting data.
        Game-level data can be added later if API endpoints are discovered.
        """
        logger.info("LNB schedule not implemented (season-level focus)")
        return pd.DataFrame()

    def fetch_player_game(self) -> pd.DataFrame:
        """Player game not implemented for LNB v1"""
        logger.info("LNB player_game not implemented (season-level focus)")
        return pd.DataFrame()

    def fetch_team_game(self) -> pd.DataFrame:
        """Team game not implemented for LNB v1"""
        logger.info("LNB team_game not implemented (season-level focus)")
        return pd.DataFrame()

    def fetch_pbp(self) -> pd.DataFrame:
        """PBP not available for LNB"""
        logger.info("LNB PBP not available (expected)")
        return pd.DataFrame()

    def fetch_shots(self) -> pd.DataFrame:
        """Shot data not available for LNB"""
        logger.info("LNB shots not available (expected)")
        return pd.DataFrame()

    def fetch_player_season(self) -> pd.DataFrame:
        """
        Fetch LNB player season stats.

        PRIMARY DATA SOURCE for LNB.

        Uses Stats Centre API (once discovered) or HTML scraping.
        """
        try:
            logger.info(f"Fetching LNB player season stats...")

            df = lnb.fetch_lnb_player_season(self.season)

            logger.info(f"Fetched {len(df)} player season records")

            # Check for SOURCE column
            if 'SOURCE' in df.columns:
                sources = df['SOURCE'].value_counts()
                logger.info(f"  Sources: {sources.to_dict()}")

            if df.empty:
                logger.warning("Player season returned empty!")
                logger.warning("  Possible reasons:")
                logger.warning("  - API endpoints not discovered yet")
                logger.warning("    → Run: python tools/lnb/api_discovery_helper.py --discover")
                logger.warning("  - Season format incorrect")
                logger.warning("  - Stats Centre changed structure")
                logger.warning("\n  NEXT STEPS:")
                logger.warning("  1. Complete API discovery session (see tools/lnb/README.md)")
                logger.warning("  2. Update lnb.py fetchers with discovered endpoints")
                logger.warning("  3. Re-run this script")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch LNB player_season: {e}")
            logger.info("  This is CRITICAL as player_season is primary LNB data source")
            return pd.DataFrame()

    def fetch_team_season(self) -> pd.DataFrame:
        """
        Fetch LNB team season stats.

        PRIMARY DATA SOURCE for LNB.

        Uses Stats Centre API (once discovered) or HTML scraping.
        """
        try:
            logger.info(f"Fetching LNB team season stats...")

            df = lnb.fetch_lnb_team_season(self.season)

            logger.info(f"Fetched {len(df)} team season records")

            # Check for SOURCE column
            if 'SOURCE' in df.columns:
                sources = df['SOURCE'].value_counts()
                logger.info(f"  Sources: {sources.to_dict()}")

            if df.empty:
                logger.warning("Team season returned empty!")
                logger.warning("  Same issues as player_season - API discovery needed")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch LNB team_season: {e}")
            logger.info("  This is CRITICAL as team_season is primary LNB data source")
            return pd.DataFrame()

    def generate_summary_report(self) -> str:
        """
        Generate LNB-specific summary report.

        Overrides base class to add LNB-specific guidance.
        """
        base_summary = super().generate_summary_report()

        # Add LNB-specific notes
        lnb_notes = []
        lnb_notes.append("\nLNB-SPECIFIC NOTES:")
        lnb_notes.append("-" * 70)

        # Check if primary data sources are present
        player_season_ok = not self.datasets.get('player_season', pd.DataFrame()).empty
        team_season_ok = not self.datasets.get('team_season', pd.DataFrame()).empty

        if player_season_ok and team_season_ok:
            lnb_notes.append("✅ PRIMARY DATA SOURCES HEALTHY")
            lnb_notes.append("   Player season and team season data successfully fetched")
            lnb_notes.append("   API endpoints appear to be working correctly")
        else:
            lnb_notes.append("❌ PRIMARY DATA SOURCES MISSING")
            if not player_season_ok:
                lnb_notes.append("   ❌ Player season: EMPTY")
            if not team_season_ok:
                lnb_notes.append("   ❌ Team season: EMPTY")

            lnb_notes.append("\n   API DISCOVERY REQUIRED:")
            lnb_notes.append("   LNB data is available, but API endpoints must be discovered.")
            lnb_notes.append("")
            lnb_notes.append("   STEP-BY-STEP GUIDE:")
            lnb_notes.append("   1. Run API discovery helper:")
            lnb_notes.append("      python tools/lnb/api_discovery_helper.py --discover")
            lnb_notes.append("")
            lnb_notes.append("   2. Open https://lnb.fr/stats/ in browser")
            lnb_notes.append("      - Open DevTools (F12)")
            lnb_notes.append("      - Network tab → XHR filter")
            lnb_notes.append("      - Navigate to player/team stats pages")
            lnb_notes.append("      - Record JSON endpoints that load data")
            lnb_notes.append("")
            lnb_notes.append("   3. Document endpoints in:")
            lnb_notes.append("      tools/lnb/discovered_endpoints.json")
            lnb_notes.append("")
            lnb_notes.append("   4. Test endpoints:")
            lnb_notes.append("      python tools/lnb/api_discovery_helper.py --test-endpoint \"URL\"")
            lnb_notes.append("")
            lnb_notes.append("   5. Generate code skeleton:")
            lnb_notes.append("      python tools/lnb/api_discovery_helper.py --generate-code")
            lnb_notes.append("")
            lnb_notes.append("   6. Update src/cbb_data/fetchers/lnb.py with discovered endpoints")
            lnb_notes.append("")
            lnb_notes.append("   7. Re-run this script:")
            lnb_notes.append(f"      python scripts/golden_lnb.py --season {self.season}")

        lnb_notes.append("\nDATA SCOPE:")
        lnb_notes.append("   ✅ Player season: PRIMARY (scouting data)")
        lnb_notes.append("   ✅ Team season: PRIMARY (team analytics)")
        lnb_notes.append("   ❌ Schedule: Not implemented in v1")
        lnb_notes.append("   ❌ Player/Team game: Not implemented in v1")
        lnb_notes.append("   ❌ PBP: Not publicly available")
        lnb_notes.append("   ❌ Shots: Not publicly available")

        lnb_notes.append("\nUSE CASE:")
        lnb_notes.append("   LNB is optimized for SEASON-LEVEL SCOUTING")
        lnb_notes.append("   - Player season stats for prospect evaluation")
        lnb_notes.append("   - Team season stats for league analysis")
        lnb_notes.append("   - Game-level data can be added later if needed")

        return base_summary + "\n" + "\n".join(lnb_notes) + "\n"


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Golden season script for LNB Pro A (French League)"
    )
    parser.add_argument(
        "--season",
        required=True,
        help="Season (e.g., '2023-24' or '2024-25')"
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
    script = LNBGoldenSeason(
        season=args.season,
        output_dir=args.output_dir
    )

    success = script.run(
        save_format=args.format,
        run_qa=not args.no_qa
    )

    if success:
        logger.info(f"\n✅ LNB golden season script completed successfully")
        logger.info(f"   Data saved to: {script.output_dir}")

        # Give specific guidance based on results
        if script.datasets.get('player_season', pd.DataFrame()).empty:
            logger.warning("\n⚠️  PRIMARY DATA MISSING")
            logger.warning("   API discovery required - see SUMMARY.txt for steps")

        sys.exit(0)
    else:
        logger.error(f"\n❌ LNB golden season script failed")
        logger.error("   Check errors above and SUMMARY.txt for details")
        sys.exit(1)


if __name__ == "__main__":
    main()
