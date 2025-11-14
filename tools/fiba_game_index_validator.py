#!/usr/bin/env python3
"""
FIBA Game Index Validator and Builder

Validates existing game indexes and provides tools to build/update them with real data.
Includes validation against FIBA LiveStats to confirm game IDs are real.

Usage:
    # Validate existing indexes
    python tools/fiba_game_index_validator.py --validate-all

    # Check specific league
    python tools/fiba_game_index_validator.py --league BCL --validate

    # Build from sample games (for testing)
    python tools/fiba_game_index_validator.py --league BCL --create-sample

    # Validate game IDs against FIBA
    python tools/fiba_game_index_validator.py --league BCL --verify-ids
"""

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
REPO_ROOT = Path(__file__).parent.parent
INDEX_DIR = REPO_ROOT / "data" / "game_indexes"
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# FIBA LiveStats URL pattern for validation
FIBA_HTML_URL = "https://fibalivestats.dcd.shared.geniussports.com/u/{league}/{game_id}/bs.html"

# Headers for validation requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class GameIndexEntry:
    """Single game entry"""
    league: str
    season: str
    game_id: int
    game_date: str
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_team_id: Optional[str] = None
    away_team_id: Optional[str] = None
    fiba_competition: Optional[str] = None
    fiba_phase: Optional[str] = None


class GameIndexValidator:
    """Validates and manages FIBA game indexes"""

    def __init__(self, league: str, season: str = "2023-24"):
        self.league = league
        self.season = season
        self.season_safe = season.replace("-", "_")
        self.index_path = INDEX_DIR / f"{league}_{self.season_safe}.csv"

    def load_index(self) -> pd.DataFrame:
        """Load game index CSV"""
        if not self.index_path.exists():
            logger.warning(f"Index file not found: {self.index_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(self.index_path)
            logger.info(f"Loaded {len(df)} games from {self.index_path}")
            return df
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            return pd.DataFrame()

    def validate_structure(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Validate index structure and return issues.

        Returns:
            Dict with keys: valid, issues, warnings
        """
        result = {
            "valid": True,
            "issues": [],
            "warnings": [],
        }

        # Check required columns
        required_cols = ["LEAGUE", "SEASON", "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            result["valid"] = False
            result["issues"].append(f"Missing required columns: {missing}")

        if df.empty:
            result["valid"] = False
            result["issues"].append("Index is empty")
            return result

        # Check LEAGUE consistency
        if "LEAGUE" in df.columns:
            league_values = df["LEAGUE"].unique()
            if len(league_values) != 1:
                result["issues"].append(f"Multiple LEAGUE values: {league_values}")
            elif league_values[0] != self.league:
                result["issues"].append(f"LEAGUE mismatch: expected {self.league}, got {league_values[0]}")

        # Check SEASON consistency
        if "SEASON" in df.columns:
            season_values = df["SEASON"].unique()
            if len(season_values) != 1:
                result["warnings"].append(f"Multiple SEASON values: {season_values}")
            elif season_values[0] != self.season:
                result["warnings"].append(f"SEASON mismatch: expected {self.season}, got {season_values[0]}")

        # Check for duplicate game IDs
        if "GAME_ID" in df.columns:
            dupes = df["GAME_ID"].duplicated().sum()
            if dupes > 0:
                result["issues"].append(f"{dupes} duplicate GAME_IDs found")

        # Check game count (warn if suspiciously low)
        if len(df) < 10:
            result["warnings"].append(f"Only {len(df)} games - may be placeholder data")

        # Check for placeholder-looking game IDs (e.g., 501234, 401234)
        if "GAME_ID" in df.columns:
            sample_ids = df["GAME_ID"].head(5).tolist()
            if any(str(gid).endswith("1234") or str(gid).endswith("234") for gid in sample_ids):
                result["warnings"].append("Game IDs may be placeholders (end with 234/1234)")

        return result

    def verify_game_id(self, game_id: int, timeout: int = 10) -> bool:
        """
        Verify a game ID exists on FIBA LiveStats.

        Args:
            game_id: FIBA game ID to verify
            timeout: Request timeout in seconds

        Returns:
            True if game ID is valid
        """
        url = FIBA_HTML_URL.format(league=self.league, game_id=game_id)

        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            is_valid = response.status_code == 200

            if is_valid:
                logger.debug(f"✓ Game ID {game_id} is valid")
            else:
                logger.warning(f"✗ Game ID {game_id} returned status {response.status_code}")

            return is_valid

        except requests.RequestException as e:
            logger.warning(f"✗ Could not verify game ID {game_id}: {e}")
            return False

    def verify_all_ids(self, df: pd.DataFrame, sample_size: Optional[int] = None) -> Dict[str, any]:
        """
        Verify game IDs against FIBA LiveStats.

        Args:
            df: DataFrame with GAME_ID column
            sample_size: If provided, only verify this many random games

        Returns:
            Dict with verification results
        """
        if "GAME_ID" not in df.columns:
            return {"error": "No GAME_ID column"}

        game_ids = df["GAME_ID"].tolist()

        if sample_size and sample_size < len(game_ids):
            import random
            game_ids = random.sample(game_ids, sample_size)
            logger.info(f"Verifying random sample of {sample_size} game IDs...")
        else:
            logger.info(f"Verifying all {len(game_ids)} game IDs...")

        verified = []
        failed = []

        for game_id in game_ids:
            if self.verify_game_id(game_id):
                verified.append(game_id)
            else:
                failed.append(game_id)

        result = {
            "total": len(game_ids),
            "verified": len(verified),
            "failed": len(failed),
            "success_rate": len(verified) / len(game_ids) * 100 if game_ids else 0,
            "failed_ids": failed,
        }

        return result

    def create_sample_index(self, num_games: int = 20) -> pd.DataFrame:
        """
        Create sample index structure (for testing).
        WARNING: This creates placeholder data - replace with real game IDs!

        Args:
            num_games: Number of sample games to create

        Returns:
            DataFrame with sample structure
        """
        import random
        from datetime import datetime, timedelta

        logger.warning("Creating SAMPLE index with PLACEHOLDER data!")
        logger.warning("You MUST replace these game IDs with real FIBA IDs from league websites!")

        base_date = datetime(2023, 10, 1)
        base_id = 500000 + random.randint(1000, 9000)

        games = []
        for i in range(num_games):
            game = GameIndexEntry(
                league=self.league,
                season=self.season,
                game_id=base_id + i,
                game_date=(base_date + timedelta(days=i * 3)).strftime("%Y-%m-%d"),
                home_team=f"Team {chr(65 + i % 26)}",
                away_team=f"Team {chr(66 + i % 26)}",
                home_score=random.randint(65, 95),
                away_score=random.randint(65, 95),
                home_team_id=f"{self.league[:3]}{i:03d}",
                away_team_id=f"{self.league[:3]}{(i+1):03d}",
                fiba_competition=self.league,
                fiba_phase="RS",
            )
            games.append(game.__dict__)

        df = pd.DataFrame(games)

        # Uppercase column names
        df.columns = df.columns.str.upper()

        return df

    def save_index(self, df: pd.DataFrame):
        """Save game index to CSV"""
        df.to_csv(self.index_path, index=False)
        logger.info(f"Saved {len(df)} games to {self.index_path}")

    def print_summary(self, df: pd.DataFrame, validation: Dict[str, any]):
        """Print validation summary"""
        print(f"\n{'='*70}")
        print(f"{self.league} Game Index Summary")
        print(f"{'='*70}")
        print(f"File: {self.index_path}")
        print(f"Games: {len(df)}")

        if not validation["valid"]:
            print(f"\n❌ VALIDATION FAILED")
        else:
            print(f"\n✅ Structure Valid")

        if validation["issues"]:
            print(f"\n🔴 ISSUES:")
            for issue in validation["issues"]:
                print(f"  - {issue}")

        if validation["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")

        if not df.empty and "GAME_ID" in df.columns:
            print(f"\nSample Game IDs: {df['GAME_ID'].head(3).tolist()}")
            print(f"Date Range: {df['GAME_DATE'].min()} to {df['GAME_DATE'].max()}")

        print(f"\n{'='*70}")


def main():
    """Main validation workflow"""
    parser = argparse.ArgumentParser(
        description="Validate and manage FIBA game indexes"
    )
    parser.add_argument(
        "--league",
        choices=["BCL", "BAL", "ABA", "LKL", "ALL"],
        default="ALL",
        help="League to validate"
    )
    parser.add_argument(
        "--season",
        default="2023-24",
        help="Season (default: 2023-24)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate index structure"
    )
    parser.add_argument(
        "--verify-ids",
        action="store_true",
        help="Verify game IDs against FIBA LiveStats"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        help="Number of game IDs to verify (default: all)"
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Create sample index (WARNING: placeholder data)"
    )
    parser.add_argument(
        "--num-games",
        type=int,
        default=20,
        help="Number of games for sample index (default: 20)"
    )

    args = parser.parse_args()

    # Determine leagues to process
    leagues = ["BCL", "BAL", "ABA", "LKL"] if args.league == "ALL" else [args.league]

    for league in leagues:
        validator = GameIndexValidator(league, args.season)

        if args.create_sample:
            # Create sample index
            df = validator.create_sample_index(args.num_games)
            validator.save_index(df)
            print(f"\n✅ Created sample index for {league}")
            print(f"⚠️  REMEMBER: Replace with real FIBA game IDs!")
            continue

        # Load existing index
        df = validator.load_index()
        if df.empty:
            print(f"\n❌ {league}: No index file found")
            print(f"   Create one with: --league {league} --create-sample")
            continue

        # Validate structure
        if args.validate or not args.verify_ids:
            validation = validator.validate_structure(df)
            validator.print_summary(df, validation)

        # Verify game IDs
        if args.verify_ids:
            print(f"\nVerifying {league} game IDs against FIBA LiveStats...")
            result = validator.verify_all_ids(df, args.sample_size)

            print(f"\n{'='*70}")
            print(f"{league} Game ID Verification Results")
            print(f"{'='*70}")
            print(f"Total IDs: {result['total']}")
            print(f"Verified: {result['verified']} ({result['success_rate']:.1f}%)")
            print(f"Failed: {result['failed']}")

            if result['failed_ids']:
                print(f"\nFailed IDs: {result['failed_ids'][:10]}")
                if len(result['failed_ids']) > 10:
                    print(f"... and {len(result['failed_ids']) - 10} more")

            print(f"{'='*70}")


if __name__ == "__main__":
    main()
