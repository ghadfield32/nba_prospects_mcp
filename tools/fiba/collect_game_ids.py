#!/usr/bin/env python3
"""
Interactive Game ID Collection Helper for FIBA Leagues

This script helps manually collect real FIBA LiveStats game IDs from league websites.
It provides:
- Step-by-step instructions per league
- URL templates for finding games
- CSV template generation
- Automatic validation of collected IDs

Usage:
    python tools/fiba/collect_game_ids.py --league BCL --season 2023-24
    python tools/fiba/collect_game_ids.py --league BAL --season 2024-25 --interactive
"""

import argparse
import csv
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# League-specific URLs
LEAGUE_URLS = {
    "BCL": {
        "schedule": "https://www.championsleague.basketball/schedule",
        "archive": "https://www.championsleague.basketball/archive",
        "stats_pattern": r"fibalivestats\.dcd\.shared\.geniussports\.com/u/BCL/(\d+)",
        "instructions": """
BCL (Basketball Champions League) Game ID Collection:

1. Visit: https://www.championsleague.basketball/schedule
2. Select your season (e.g., "2023-24")
3. For each game, look for "Stats" or "Box Score" link
4. Right-click → "Copy Link Address"
5. Extract game ID from URL pattern: fibalivestats.../u/BCL/{GAME_ID}/bs.html
6. Also record: date, home team, away team, scores
7. Enter data when prompted below

Tips:
- Start with 20-30 games to test (1-2 rounds)
- Focus on completed games (have final scores)
- Archive page may have more complete data
        """
    },
    "BAL": {
        "schedule": "https://thebal.com/schedule/",
        "archive": "https://thebal.com/standings/",
        "stats_pattern": r"fibalivestats\.dcd\.shared\.geniussports\.com/u/BAL/(\d+)",
        "instructions": """
BAL (Basketball Africa League) Game ID Collection:

1. Visit: https://thebal.com/schedule/
2. Select your season
3. Click on individual games to see details
4. Look for "Stats" or "Game Stats" link
5. Extract game ID from FIBA LiveStats URL
6. Record: date, home team, away team, scores
7. Enter data when prompted below

Tips:
- BAL has fewer games than BCL (easier to collect)
- Focus on regular season first, then playoffs
        """
    },
    "ABA": {
        "schedule": "https://www.aba-liga.com/schedule.php",
        "archive": "https://www.aba-liga.com/",
        "stats_pattern": r"fibalivestats\.dcd\.shared\.geniussports\.com/u/ABA/(\d+)",
        "instructions": """
ABA (Adriatic League) Game ID Collection:

1. Visit: https://www.aba-liga.com/schedule.php
2. Select season and round
3. Click on games to see details/stats
4. Find FIBA LiveStats link (may be labeled "Live Stats")
5. Extract game ID from URL
6. Record game metadata
7. Enter data when prompted below

Tips:
- ABA website layout may vary by season
- Check both schedule page and individual game pages
        """
    },
    "LKL": {
        "schedule": "https://lkl.lt/en/schedule",
        "archive": "https://lkl.lt/en/",
        "stats_pattern": r"fibalivestats\.dcd\.shared\.geniussports\.com/u/LKL/(\d+)",
        "instructions": """
LKL (Lithuanian Basketball League) Game ID Collection:

1. Visit: https://lkl.lt/en/schedule
2. Select season (dropdown or URL parameter)
3. Click on individual games
4. Look for "Statistics" or similar link
5. Extract FIBA LiveStats game ID
6. Record game metadata
7. Enter data when prompted below

Tips:
- LKL site has English version (/en/)
- Stats links may be on game detail pages
        """
    },
}

FIBA_LIVESTATS_URL = "https://fibalivestats.dcd.shared.geniussports.com/u/{league}/{game_id}/bs.html"


class GameIDCollector:
    """Helper for collecting game IDs manually"""

    def __init__(self, league: str, season: str):
        self.league = league.upper()
        self.season = season
        self.games: List[Dict] = []

        if self.league not in LEAGUE_URLS:
            raise ValueError(f"Unknown league: {league}. Must be one of: {list(LEAGUE_URLS.keys())}")

        self.league_info = LEAGUE_URLS[self.league]

    def print_instructions(self):
        """Print collection instructions"""
        print("\n" + "=" * 70)
        print(f"Game ID Collection - {self.league} {self.season}")
        print("=" * 70)
        print(self.league_info["instructions"])
        print("\n" + "=" * 70)
        print(f"Schedule URL: {self.league_info['schedule']}")
        print(f"Archive URL:  {self.league_info['archive']}")
        print("=" * 70 + "\n")

    def validate_game_id(self, game_id: int) -> bool:
        """Validate a game ID by checking FIBA LiveStats"""
        url = FIBA_LIVESTATS_URL.format(league=self.league, game_id=game_id)

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ Game ID {game_id} validated successfully")
                return True
            else:
                logger.warning(f"⚠️  Game ID {game_id} returned status {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"❌ Could not validate game ID {game_id}: {e}")
            return False

    def extract_game_id_from_url(self, url: str) -> Optional[int]:
        """Extract game ID from FIBA LiveStats URL"""
        pattern = self.league_info["stats_pattern"]
        match = re.search(pattern, url)

        if match:
            return int(match.group(1))
        return None

    def interactive_collection(self):
        """Interactively collect game IDs from user"""
        self.print_instructions()

        print("Enter game data (or 'done' when finished):\n")

        while True:
            print("\n" + "-" * 70)
            game_num = len(self.games) + 1
            print(f"Game #{game_num}")
            print("-" * 70)

            # Get game ID
            game_id_input = input("FIBA LiveStats URL or Game ID (or 'done'): ").strip()

            if game_id_input.lower() == 'done':
                break

            # Extract game ID
            if game_id_input.startswith("http"):
                game_id = self.extract_game_id_from_url(game_id_input)
                if not game_id:
                    print("❌ Could not extract game ID from URL. Please try again.")
                    continue
            else:
                try:
                    game_id = int(game_id_input)
                except ValueError:
                    print("❌ Invalid game ID. Please enter a number or full URL.")
                    continue

            # Validate game ID
            print(f"Validating game ID {game_id}...")
            is_valid = self.validate_game_id(game_id)

            if not is_valid:
                retry = input("Game ID validation failed. Add anyway? (y/n): ").lower()
                if retry != 'y':
                    continue

            # Get game metadata
            game_date = input("Game date (YYYY-MM-DD): ").strip()
            home_team = input("Home team: ").strip()
            away_team = input("Away team: ").strip()
            home_score = input("Home score (or leave blank): ").strip()
            away_score = input("Away score (or leave blank): ").strip()
            round_num = input("Round number (or leave blank): ").strip()

            # Add game
            game = {
                "LEAGUE": self.league,
                "SEASON": self.season,
                "GAME_ID": game_id,
                "GAME_DATE": game_date,
                "HOME_TEAM": home_team,
                "AWAY_TEAM": away_team,
                "HOME_SCORE": home_score if home_score else "",
                "AWAY_SCORE": away_score if away_score else "",
                "COMPETITION_PHASE": "RS",  # Default to Regular Season
                "ROUND": round_num if round_num else "",
                "VERIFIED": is_valid,
            }

            self.games.append(game)
            print(f"✅ Added game {game_id} ({home_team} vs {away_team})")
            print(f"Total games collected: {len(self.games)}")

    def load_existing_index(self, index_path: Path) -> bool:
        """Load existing game index"""
        if not index_path.exists():
            return False

        try:
            with open(index_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.games = list(reader)

            logger.info(f"Loaded {len(self.games)} games from {index_path}")
            return True

        except Exception as e:
            logger.error(f"Could not load index: {e}")
            return False

    def save_to_csv(self, output_path: Path):
        """Save collected games to CSV"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "LEAGUE", "SEASON", "GAME_ID", "GAME_DATE",
            "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE",
            "COMPETITION_PHASE", "ROUND", "VERIFIED"
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.games)

        logger.info(f"Saved {len(self.games)} games to {output_path}")

    def print_summary(self):
        """Print collection summary"""
        print("\n" + "=" * 70)
        print(f"Collection Summary - {self.league} {self.season}")
        print("=" * 70)
        print(f"Total games collected: {len(self.games)}")

        verified_count = sum(1 for g in self.games if g.get("VERIFIED") == "True" or g.get("VERIFIED") is True)
        print(f"Verified games: {verified_count}/{len(self.games)}")

        if self.games:
            # Show first and last game
            print(f"\nFirst game: {self.games[0]['HOME_TEAM']} vs {self.games[0]['AWAY_TEAM']} ({self.games[0]['GAME_DATE']})")
            print(f"Last game:  {self.games[-1]['HOME_TEAM']} vs {self.games[-1]['AWAY_TEAM']} ({self.games[-1]['GAME_DATE']})")

        print("=" * 70 + "\n")


def main():
    """Main collection workflow"""
    parser = argparse.ArgumentParser(
        description="Interactive game ID collection helper for FIBA leagues"
    )
    parser.add_argument(
        "--league",
        choices=["BCL", "BAL", "ABA", "LKL"],
        required=True,
        help="League to collect game IDs for"
    )
    parser.add_argument(
        "--season",
        default="2023-24",
        help="Season (default: 2023-24)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode - prompt for each game"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path (default: data/game_indexes/{LEAGUE}_{SEASON}.csv)"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing index file"
    )

    args = parser.parse_args()

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        season_slug = args.season.replace("-", "_")
        output_path = Path(f"data/game_indexes/{args.league}_{season_slug}.csv")

    # Create collector
    collector = GameIDCollector(args.league, args.season)

    # Load existing if appending
    if args.append:
        collector.load_existing_index(output_path)

    # Interactive collection
    if args.interactive:
        collector.interactive_collection()
    else:
        # Just show instructions
        collector.print_instructions()
        print("\nTo start interactive collection, run with --interactive flag:\n")
        print(f"  python tools/fiba/collect_game_ids.py --league {args.league} --season {args.season} --interactive\n")
        return

    # Save results
    if collector.games:
        collector.save_to_csv(output_path)
        collector.print_summary()

        print(f"\n✅ Game index saved to: {output_path}")
        print(f"\nNext steps:")
        print(f"1. Validate the index:")
        print(f"   python tools/fiba_game_index_validator.py --league {args.league} --season {args.season} --verify-ids")
        print(f"\n2. Test data fetching:")
        print(f"   python tools/test_league_complete_flow.py --league {args.league} --season {args.season}")
    else:
        print("\n⚠️  No games collected")


if __name__ == "__main__":
    main()
