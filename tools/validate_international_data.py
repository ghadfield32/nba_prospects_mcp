#!/usr/bin/env python3
"""
International Basketball Data Validation Script

Tests actual data fetching from all international leagues to identify
what works vs what needs implementation/fixing.

Usage:
    python tools/validate_international_data.py
    python tools/validate_international_data.py --league BCL
    python tools/validate_international_data.py --detailed
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class LeagueValidator:
    """Validates data fetching capabilities for a league"""

    def __init__(self, league_name: str, league_module: Any, test_season: str = "2023-24"):
        self.league_name = league_name
        self.module = league_module
        self.test_season = test_season
        self.results: Dict[str, Dict[str, Any]] = {}

    def test_function(self, func_name: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Test a single fetch function and return results.

        Returns:
            Dict with keys: success, row_count, columns, error, data_source, sample
        """
        result = {
            "success": False,
            "row_count": 0,
            "columns": [],
            "error": None,
            "data_source": None,
            "sample": None,
        }

        try:
            func = getattr(self.module, func_name)
            logger.info(f"Testing {self.league_name}.{func_name}({args}, {kwargs})")

            df = func(*args, **kwargs)

            if isinstance(df, pd.DataFrame):
                result["success"] = True
                result["row_count"] = len(df)
                result["columns"] = list(df.columns)

                # Check for SOURCE column
                if "SOURCE" in df.columns and not df.empty:
                    result["data_source"] = df["SOURCE"].value_counts().to_dict()

                # Get sample row
                if not df.empty:
                    result["sample"] = df.head(1).to_dict(orient="records")[0]
            else:
                result["error"] = f"Unexpected return type: {type(df)}"

        except AttributeError:
            result["error"] = f"Function {func_name} not found in {self.league_name} module"
        except NotImplementedError as e:
            result["error"] = f"Not implemented: {e}"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"

        return result

    def validate_all(self) -> Dict[str, Dict[str, Any]]:
        """Validate all standard fetch functions for this league"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Validating {self.league_name}")
        logger.info(f"{'='*60}")

        # Standard functions to test
        tests = [
            ("fetch_schedule", [self.test_season]),
            ("fetch_player_game", [self.test_season]),
            ("fetch_team_game", [self.test_season]),
            ("fetch_pbp", [self.test_season]),
            ("fetch_shots", [self.test_season]),
            ("fetch_player_season", [self.test_season]),
            ("fetch_team_season", [self.test_season]),
        ]

        for func_name, args in tests:
            self.results[func_name] = self.test_function(func_name, *args)

        return self.results

    def print_summary(self, detailed: bool = False):
        """Print validation summary"""
        print(f"\n{self.league_name} Validation Summary")
        print(f"{'-'*60}")

        for func_name, result in self.results.items():
            status = "✅" if result["success"] else "❌"
            rows = result["row_count"]

            if result["success"]:
                source_info = ""
                if result["data_source"]:
                    sources = ", ".join([f"{k}:{v}" for k, v in result["data_source"].items()])
                    source_info = f" (sources: {sources})"

                print(f"{status} {func_name:25} {rows:6} rows{source_info}")

                if detailed and result["sample"]:
                    print(f"    Sample columns: {', '.join(list(result['sample'].keys())[:5])}")
            else:
                error = result["error"][:50] if result["error"] else "Unknown error"
                print(f"{status} {func_name:25} ERROR: {error}")

        # Overall stats
        total_tests = len(self.results)
        passed = sum(1 for r in self.results.values() if r["success"])
        print(f"\n{'-'*60}")
        print(f"Overall: {passed}/{total_tests} tests passed ({passed/total_tests*100:.1f}%)")


class ACBValidator(LeagueValidator):
    """Special validator for ACB with season format differences"""

    def validate_all(self) -> Dict[str, Dict[str, Any]]:
        """Validate ACB-specific functions"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Validating {self.league_name}")
        logger.info(f"{'='*60}")

        # ACB uses "2024" format instead of "2023-24"
        acb_season = self.test_season.split("-")[1]  # "2023-24" → "24"
        acb_season = f"20{acb_season}"  # "24" → "2024"

        tests = [
            ("fetch_acb_player_season", [acb_season]),
            ("fetch_acb_team_season", [acb_season]),
            ("fetch_acb_schedule", [self.test_season]),
            ("fetch_acb_box_score", ["12345"]),  # Placeholder game ID
        ]

        for func_name, args in tests:
            self.results[func_name] = self.test_function(func_name, *args)

        return self.results


class LNBValidator(LeagueValidator):
    """Special validator for LNB with different function names"""

    def validate_all(self) -> Dict[str, Dict[str, Any]]:
        """Validate LNB-specific functions"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Validating {self.league_name}")
        logger.info(f"{'='*60}")

        # LNB uses "2024" format
        lnb_season = self.test_season.split("-")[1]  # "2023-24" → "24"
        lnb_season = f"20{lnb_season}"  # "24" → "2024"

        tests = [
            ("fetch_lnb_player_season", [lnb_season]),
            ("fetch_lnb_team_season", [lnb_season]),
            ("fetch_lnb_schedule", [lnb_season]),
            ("fetch_lnb_box_score", ["12345"]),  # Placeholder game ID
        ]

        for func_name, args in tests:
            self.results[func_name] = self.test_function(func_name, *args)

        return self.results


def validate_game_index_quality(league: str, season: str) -> Dict[str, Any]:
    """
    Validate game index CSV file quality.

    Returns:
        Dict with: exists, row_count, has_game_ids, sample_game_id, issues
    """
    result = {
        "exists": False,
        "row_count": 0,
        "has_game_ids": False,
        "sample_game_id": None,
        "issues": [],
    }

    # Build expected path
    season_safe = season.replace("-", "_")
    index_path = Path(f"data/game_indexes/{league}_{season_safe}.csv")

    if not index_path.exists():
        result["issues"].append(f"Game index file not found: {index_path}")
        return result

    result["exists"] = True

    try:
        df = pd.read_csv(index_path)
        result["row_count"] = len(df)

        # Check for GAME_ID column
        if "GAME_ID" in df.columns:
            result["has_game_ids"] = True
            if not df.empty:
                result["sample_game_id"] = df["GAME_ID"].iloc[0]
        else:
            result["issues"].append("Missing GAME_ID column")

        # Check for required columns
        required_cols = ["LEAGUE", "SEASON", "GAME_ID", "GAME_DATE"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            result["issues"].append(f"Missing columns: {missing}")

        # Check if LEAGUE matches
        if "LEAGUE" in df.columns and not df.empty:
            league_values = df["LEAGUE"].unique()
            if len(league_values) != 1 or league_values[0] != league:
                result["issues"].append(f"LEAGUE column mismatch: {league_values}")

        # Check if rows seem realistic
        if result["row_count"] < 10:
            result["issues"].append(f"Very few games ({result['row_count']}) - may be placeholder")

    except Exception as e:
        result["issues"].append(f"Error reading CSV: {e}")

    return result


def main():
    """Main validation workflow"""
    parser = argparse.ArgumentParser(
        description="Validate international basketball data sources"
    )
    parser.add_argument(
        "--league",
        choices=["BCL", "BAL", "ABA", "LKL", "ACB", "LNB", "ALL"],
        default="ALL",
        help="League to validate (default: ALL)",
    )
    parser.add_argument(
        "--season",
        default="2023-24",
        help="Season to test (default: 2023-24)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed output including sample data",
    )
    parser.add_argument(
        "--check-indexes",
        action="store_true",
        help="Also validate game index CSV files",
    )

    args = parser.parse_args()

    # Define leagues to test
    if args.league == "ALL":
        fiba_leagues = [
            ("BCL", bcl),
            ("BAL", bal),
            ("ABA", aba),
            ("LKL", lkl),
        ]
        other_leagues = [
            ("ACB", acb, ACBValidator),
            ("LNB", lnb, LNBValidator),
        ]
    else:
        league_map = {
            "BCL": bcl,
            "BAL": bal,
            "ABA": aba,
            "LKL": lkl,
            "ACB": acb,
            "LNB": lnb,
        }
        if args.league in ["BCL", "BAL", "ABA", "LKL"]:
            fiba_leagues = [(args.league, league_map[args.league])]
            other_leagues = []
        else:
            fiba_leagues = []
            validator_map = {
                "ACB": ACBValidator,
                "LNB": LNBValidator,
            }
            other_leagues = [(args.league, league_map[args.league], validator_map[args.league])]

    # Validate FIBA leagues
    fiba_results = {}
    for league_name, league_module in fiba_leagues:
        validator = LeagueValidator(league_name, league_module, args.season)
        fiba_results[league_name] = validator.validate_all()
        validator.print_summary(detailed=args.detailed)

        # Check game index if requested
        if args.check_indexes:
            print(f"\nGame Index Check for {league_name}:")
            index_result = validate_game_index_quality(league_name, args.season)
            if index_result["exists"]:
                print(f"  ✅ File exists: {index_result['row_count']} games")
                print(f"  Sample Game ID: {index_result['sample_game_id']}")
            else:
                print(f"  ❌ File not found")

            if index_result["issues"]:
                for issue in index_result["issues"]:
                    print(f"  ⚠️  {issue}")

    # Validate other leagues
    other_results = {}
    for league_tuple in other_leagues:
        if len(league_tuple) == 3:
            league_name, league_module, validator_class = league_tuple
            validator = validator_class(league_name, league_module, args.season)
        else:
            league_name, league_module = league_tuple
            validator = LeagueValidator(league_name, league_module, args.season)

        other_results[league_name] = validator.validate_all()
        validator.print_summary(detailed=args.detailed)

    # Overall summary
    print(f"\n{'='*60}")
    print("OVERALL VALIDATION SUMMARY")
    print(f"{'='*60}")

    all_results = {**fiba_results, **other_results}

    for league_name, results in all_results.items():
        total = len(results)
        passed = sum(1 for r in results.values() if r["success"])
        pct = passed / total * 100 if total > 0 else 0

        status = "✅" if pct >= 70 else "⚠️" if pct >= 30 else "❌"
        print(f"{status} {league_name:5} {passed}/{total} ({pct:5.1f}%)")

    # Export results to JSON for tracking
    output_path = Path("validation_results.json")
    import json
    with open(output_path, "w") as f:
        # Convert to serializable format
        serializable_results = {}
        for league, results in all_results.items():
            serializable_results[league] = {}
            for func, result in results.items():
                serializable_results[league][func] = {
                    "success": result["success"],
                    "row_count": result["row_count"],
                    "columns": result["columns"],
                    "error": result["error"],
                    "data_source": result["data_source"],
                }

        json.dump({
            "season": args.season,
            "timestamp": pd.Timestamp.now().isoformat(),
            "results": serializable_results,
        }, f, indent=2)

    print(f"\nResults exported to: {output_path}")


if __name__ == "__main__":
    main()
