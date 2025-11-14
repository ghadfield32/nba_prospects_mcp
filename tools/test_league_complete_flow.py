#!/usr/bin/env python3
"""
Complete Flow Test for International Basketball Leagues

Tests the complete data fetching pipeline for a league:
1. Load game index
2. Fetch schedule
3. Fetch player_game, team_game, pbp, shots
4. Validate data quality
5. Generate report

Usage:
    python tools/test_league_complete_flow.py --league BCL --season 2023-24
    python tools/test_league_complete_flow.py --league ACB --season 2024 --season-only
    python tools/test_league_complete_flow.py --league ALL --quick
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cbb_data.fetchers import aba, acb, bal, bcl, lkl, lnb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LeagueFlowTester:
    """Tests complete data fetching flow for a league"""

    def __init__(self, league: str, season: str, quick_mode: bool = False):
        self.league = league
        self.season = season
        self.quick_mode = quick_mode
        self.results = {}
        self.errors = []
        self.warnings = []

    def test_function(self, func_name: str, func, *args, **kwargs) -> Dict:
        """Test a single fetch function"""
        result = {
            "function": func_name,
            "success": False,
            "row_count": 0,
            "columns": [],
            "elapsed_sec": 0,
            "error": None,
            "data_quality": {},
        }

        start_time = time.time()

        try:
            logger.info(f"Testing {self.league}.{func_name}...")
            df = func(*args, **kwargs)

            result["elapsed_sec"] = time.time() - start_time

            if isinstance(df, pd.DataFrame):
                result["success"] = True
                result["row_count"] = len(df)
                result["columns"] = list(df.columns)

                # Data quality checks
                if not df.empty:
                    result["data_quality"] = self.check_data_quality(df, func_name)

            else:
                result["error"] = f"Unexpected return type: {type(df)}"

        except Exception as e:
            result["elapsed_sec"] = time.time() - start_time
            result["error"] = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error in {func_name}: {result['error']}")

        return result

    def check_data_quality(self, df: pd.DataFrame, func_name: str) -> Dict:
        """Perform data quality checks"""
        quality = {
            "has_nulls": df.isnull().any().any(),
            "null_columns": df.columns[df.isnull().any()].tolist(),
            "duplicate_rows": df.duplicated().sum(),
        }

        # Function-specific checks
        if "player_game" in func_name or "player_season" in func_name:
            # Check for duplicate player records
            id_cols = [col for col in ["GAME_ID", "TEAM_ID", "PLAYER_ID"] if col in df.columns]
            if id_cols:
                quality["duplicate_player_records"] = df.duplicated(subset=id_cols).sum()

            # Check for SOURCE column (FIBA leagues)
            if "SOURCE" in df.columns:
                quality["data_sources"] = df["SOURCE"].value_counts().to_dict()

            # Check numeric columns have reasonable values
            if "PTS" in df.columns:
                quality["pts_range"] = f"{df['PTS'].min():.0f} - {df['PTS'].max():.0f}"
                quality["pts_negative"] = (df["PTS"] < 0).sum()

        elif "team_game" in func_name or "team_season" in func_name:
            # Check team data
            if "PTS" in df.columns:
                quality["pts_range"] = f"{df['PTS'].min():.0f} - {df['PTS'].max():.0f}"

            if "TEAM" in df.columns:
                quality["unique_teams"] = df["TEAM"].nunique()

        elif func_name == "fetch_pbp":
            # Check PBP data
            if "PERIOD" in df.columns:
                quality["periods"] = df["PERIOD"].unique().tolist()

            if "EVENT_NUM" in df.columns:
                quality["total_events"] = df["EVENT_NUM"].max()

        elif func_name == "fetch_shots":
            # Check shot coordinates
            coord_cols = [col for col in ["X", "Y", "SHOT_X", "SHOT_Y"] if col in df.columns]
            if coord_cols:
                quality["has_coordinates"] = True
                quality["coordinate_columns"] = coord_cols

                # Check if coordinates are populated
                for col in coord_cols:
                    quality[f"{col}_null_count"] = df[col].isnull().sum()
            else:
                quality["has_coordinates"] = False

        return quality

    def test_fiba_league(self, module) -> Dict:
        """Test FIBA league (BCL, BAL, ABA, LKL)"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing {self.league} - Complete Flow")
        logger.info(f"{'='*70}")

        results = {}

        # Test schedule
        results["fetch_schedule"] = self.test_function(
            "fetch_schedule",
            module.fetch_schedule,
            self.season
        )

        if not self.quick_mode:
            # Test player game
            results["fetch_player_game"] = self.test_function(
                "fetch_player_game",
                module.fetch_player_game,
                self.season
            )

            # Test team game
            results["fetch_team_game"] = self.test_function(
                "fetch_team_game",
                module.fetch_team_game,
                self.season
            )

            # Test PBP
            results["fetch_pbp"] = self.test_function(
                "fetch_pbp",
                module.fetch_pbp,
                self.season
            )

            # Test shots
            results["fetch_shots"] = self.test_function(
                "fetch_shots",
                module.fetch_shots,
                self.season
            )

        # Test season aggregates
        results["fetch_player_season"] = self.test_function(
            "fetch_player_season",
            module.fetch_player_season,
            self.season
        )

        results["fetch_team_season"] = self.test_function(
            "fetch_team_season",
            module.fetch_team_season,
            self.season
        )

        return results

    def test_acb(self, module) -> Dict:
        """Test ACB (Spanish League)"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing ACB - Season Level")
        logger.info(f"{'='*70}")

        # ACB uses "2024" format instead of "2023-24"
        acb_season = self.season if len(self.season) == 4 else self.season.split("-")[1]
        if len(acb_season) == 2:
            acb_season = f"20{acb_season}"

        results = {}

        # Test player season
        results["fetch_acb_player_season"] = self.test_function(
            "fetch_acb_player_season",
            module.fetch_acb_player_season,
            acb_season
        )

        # Test team season
        results["fetch_acb_team_season"] = self.test_function(
            "fetch_acb_team_season",
            module.fetch_acb_team_season,
            acb_season
        )

        if not self.quick_mode:
            # Test schedule (may return empty - not implemented yet)
            results["fetch_acb_schedule"] = self.test_function(
                "fetch_acb_schedule",
                module.fetch_acb_schedule,
                self.season
            )

        return results

    def test_lnb(self, module) -> Dict:
        """Test LNB (French League)"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing LNB - Season Level")
        logger.info(f"{'='*70}")

        # LNB uses "2024" format
        lnb_season = self.season if len(self.season) == 4 else self.season.split("-")[1]
        if len(lnb_season) == 2:
            lnb_season = f"20{lnb_season}"

        results = {}

        # Test team season (should work)
        results["fetch_lnb_team_season"] = self.test_function(
            "fetch_lnb_team_season",
            module.fetch_lnb_team_season,
            lnb_season
        )

        if not self.quick_mode:
            # Test player season (may return empty - API not discovered yet)
            results["fetch_lnb_player_season"] = self.test_function(
                "fetch_lnb_player_season",
                module.fetch_lnb_player_season,
                lnb_season
            )

        return results

    def run_tests(self) -> Dict:
        """Run all tests for the league"""
        league_map = {
            "BCL": (bcl, self.test_fiba_league),
            "BAL": (bal, self.test_fiba_league),
            "ABA": (aba, self.test_fiba_league),
            "LKL": (lkl, self.test_fiba_league),
            "ACB": (acb, self.test_acb),
            "LNB": (lnb, self.test_lnb),
        }

        if self.league not in league_map:
            raise ValueError(f"Unknown league: {self.league}")

        module, test_func = league_map[self.league]
        self.results = test_func(module)

        return self.results

    def print_report(self):
        """Print test results report"""
        print(f"\n{'='*70}")
        print(f"{self.league} Test Results - {self.season}")
        print(f"{'='*70}")

        # Summary stats
        total_tests = len(self.results)
        passed = sum(1 for r in self.results.values() if r["success"])
        failed = total_tests - passed

        print(f"\nOverall: {passed}/{total_tests} tests passed ({passed/total_tests*100:.0f}%)")

        # Function results
        print(f"\n{'Function':<30} {'Status':<10} {'Rows':<10} {'Time':<10}")
        print(f"{'-'*70}")

        for func_name, result in self.results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            rows = result["row_count"]
            elapsed = f"{result['elapsed_sec']:.2f}s"

            print(f"{func_name:<30} {status:<10} {rows:<10} {elapsed:<10}")

            # Show error if failed
            if not result["success"] and result["error"]:
                print(f"  ↳ {result['error']}")

            # Show data quality issues
            if result["success"] and result["data_quality"]:
                quality = result["data_quality"]

                if quality.get("duplicate_player_records", 0) > 0:
                    print(f"  ⚠️  {quality['duplicate_player_records']} duplicate player records")

                if quality.get("pts_negative", 0) > 0:
                    print(f"  ⚠️  {quality['pts_negative']} negative point values")

                if "data_sources" in quality:
                    sources = ", ".join([f"{k}:{v}" for k, v in quality["data_sources"].items()])
                    print(f"  ℹ️  Sources: {sources}")

                if "has_coordinates" in quality:
                    if quality["has_coordinates"]:
                        cols = quality.get("coordinate_columns", [])
                        print(f"  ✅ Shot coordinates present: {cols}")
                    else:
                        print(f"  ❌ No shot coordinates found")

        # Recommendations
        print(f"\n{'='*70}")
        print("RECOMMENDATIONS")
        print(f"{'='*70}")

        if failed > 0:
            print(f"\n🔴 {failed} test(s) failed - see errors above")

        # FIBA-specific recommendations
        if self.league in ["BCL", "BAL", "ABA", "LKL"]:
            schedule_result = self.results.get("fetch_schedule", {})
            if schedule_result.get("success") and schedule_result.get("row_count", 0) < 10:
                print(f"\n⚠️  Only {schedule_result['row_count']} games in schedule")
                print(f"   → Check if game index has real FIBA game IDs")
                print(f"   → Run: python tools/fiba_game_index_validator.py --league {self.league} --verify-ids")

            player_game_result = self.results.get("fetch_player_game", {})
            if player_game_result.get("success"):
                quality = player_game_result.get("data_quality", {})
                if "data_sources" in quality:
                    if "fiba_html" in quality["data_sources"] and "fiba_json" not in quality["data_sources"]:
                        print(f"\n⚠️  All data from HTML fallback (no JSON API success)")
                        print(f"   → JSON API may be failing")
                        print(f"   → Check logs for JSON fetch errors")

        # ACB-specific recommendations
        elif self.league == "ACB":
            player_result = self.results.get("fetch_acb_player_season", {})
            if not player_result.get("success"):
                print(f"\n🔴 ACB player season failed")
                print(f"   → May be blocked (403 error)")
                print(f"   → Download Zenodo historical data")
                print(f"   → Try from local machine (not container)")

        # LNB-specific recommendations
        elif self.league == "LNB":
            player_result = self.results.get("fetch_lnb_player_season", {})
            if player_result and player_result.get("row_count", 0) == 0:
                print(f"\n⚠️  LNB player season returned empty")
                print(f"   → API endpoints not discovered yet")
                print(f"   → Use browser DevTools on lnb.fr/stats")
                print(f"   → See tools/lnb/README.md for guide")

        print(f"\n{'='*70}")

    def export_results(self, output_path: Path):
        """Export results to JSON"""
        import json

        # Make results JSON-serializable
        export_data = {
            "league": self.league,
            "season": self.season,
            "timestamp": pd.Timestamp.now().isoformat(),
            "results": {}
        }

        for func_name, result in self.results.items():
            export_data["results"][func_name] = {
                "success": result["success"],
                "row_count": result["row_count"],
                "elapsed_sec": result["elapsed_sec"],
                "error": result["error"],
                "data_quality": result["data_quality"],
            }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Results exported to {output_path}")


def main():
    """Main test workflow"""
    parser = argparse.ArgumentParser(
        description="Test complete data fetching flow for international leagues"
    )
    parser.add_argument(
        "--league",
        choices=["BCL", "BAL", "ABA", "LKL", "ACB", "LNB", "ALL"],
        default="BCL",
        help="League to test"
    )
    parser.add_argument(
        "--season",
        default="2023-24",
        help="Season to test (default: 2023-24)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode - only test schedule and season aggregates"
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Export results to JSON file"
    )

    args = parser.parse_args()

    # Determine leagues to test
    if args.league == "ALL":
        leagues = ["BCL", "BAL", "ABA", "LKL", "ACB", "LNB"]
    else:
        leagues = [args.league]

    all_results = {}

    for league in leagues:
        tester = LeagueFlowTester(league, args.season, args.quick)

        try:
            results = tester.run_tests()
            all_results[league] = results
            tester.print_report()

            if args.export:
                export_path = args.export.parent / f"{league}_{args.export.name}"
                tester.export_results(export_path)

        except Exception as e:
            logger.error(f"Fatal error testing {league}: {e}")
            print(f"\n❌ {league}: Fatal error - {e}")

    # Overall summary if testing multiple leagues
    if len(leagues) > 1:
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print(f"{'='*70}")

        for league in leagues:
            if league in all_results:
                results = all_results[league]
                total = len(results)
                passed = sum(1 for r in results.values() if r["success"])
                pct = passed / total * 100 if total > 0 else 0

                status = "✅" if pct >= 70 else "⚠️" if pct >= 30 else "❌"
                print(f"{status} {league:5} {passed}/{total} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
