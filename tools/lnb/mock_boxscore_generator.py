#!/usr/bin/env python3
"""Mock LNB Boxscore Data Generator

Generates realistic mock boxscore data for testing the parser before endpoint discovery.
Creates multiple response structures to validate parser flexibility.

Usage:
    python tools/lnb/mock_boxscore_generator.py
"""

import json
import random
from typing import Any


class MockBoxscoreGenerator:
    """Generate realistic mock LNB boxscore data."""

    # French player names for realism
    FRENCH_FIRST_NAMES = [
        "Antoine",
        "Mathias",
        "Théo",
        "Louis",
        "Alexandre",
        "Nicolas",
        "Pierre",
        "Thomas",
        "Vincent",
        "Julien",
        "Maxime",
        "Hugo",
        "Lucas",
        "Nathan",
        "Arthur",
    ]

    FRENCH_LAST_NAMES = [
        "Diot",
        "Lessort",
        "Maledon",
        "Hifi",
        "Ouattara",
        "Begarin",
        "Yabusele",
        "Lighty",
        "Hayes",
        "Batum",
        "Gobert",
        "Fournier",
        "Ntilikina",
        "Fall",
        "Diaw",
    ]

    TEAM_NAMES = [
        "Paris",
        "Monaco",
        "Lyon-Villeurbanne",
        "Strasbourg",
        "Nanterre",
        "Boulazac",
        "Cholet",
        "Le Mans",
    ]

    def generate_player_stats(
        self,
        player_id: int,
        team_id: int,
        opponent_id: int,
        is_starter: bool = None,
        minutes_range: tuple = (0, 35),
    ) -> dict[str, Any]:
        """Generate realistic player stats."""

        if is_starter is None:
            is_starter = random.random() < 0.4  # 40% starters

        # Generate minutes
        if is_starter:
            minutes = random.randint(20, 35)
        else:
            minutes = random.randint(0, 25)

        minutes_str = self._format_french_time(minutes)

        # Generate shooting stats
        fga = random.randint(0, 20)
        fgm = random.randint(0, min(fga, int(fga * 0.6)))  # ~45% FG%

        fg3a = random.randint(0, min(fga, 10))
        fg3m = random.randint(0, min(fg3a, int(fg3a * 0.4)))  # ~35% 3P%

        fta = random.randint(0, 10)
        ftm = random.randint(0, min(fta, int(fta * 0.8)))  # ~75% FT%

        # Calculate points
        pts = (fgm - fg3m) * 2 + fg3m * 3 + ftm

        # Generate other stats
        reb = random.randint(0, 12)
        ast = random.randint(0, 8)
        stl = random.randint(0, 4)
        blk = random.randint(0, 3)
        tov = random.randint(0, 5)
        pf = random.randint(0, 5)

        # Plus/minus (random but realistic)
        plus_minus = random.randint(-15, 15)

        return {
            "person_external_id": player_id,
            "first_name": random.choice(self.FRENCH_FIRST_NAMES),
            "family_name": random.choice(self.FRENCH_LAST_NAMES),
            "team_external_id": team_id,
            "opponent_external_id": opponent_id,
            "minutes": minutes_str,
            "starter": is_starter,
            "points": pts,
            "field_goals_made": fgm,
            "field_goals_attempted": fga,
            "three_pointers_made": fg3m,
            "three_pointers_attempted": fg3a,
            "free_throws_made": ftm,
            "free_throws_attempted": fta,
            "rebounds": reb,
            "offensive_rebounds": random.randint(0, reb // 2),
            "defensive_rebounds": reb - random.randint(0, reb // 2),
            "assists": ast,
            "steals": stl,
            "blocks": blk,
            "turnovers": tov,
            "fouls": pf,
            "plus_minus": plus_minus,
        }

    def _format_french_time(self, minutes: int) -> str:
        """Format minutes in French format: "18' 46''"."""
        mins = minutes
        secs = random.randint(0, 59)
        return f"{mins}' {secs:02d}''"

    def generate_pattern_1_simple_list(
        self, game_id: int = 28931, num_players_per_team: int = 10
    ) -> list[dict[str, Any]]:
        """Pattern 1: Direct list of players."""
        players = []

        team_1_id = 1794
        team_2_id = 1786

        for i in range(num_players_per_team):
            # Team 1 players
            players.append(
                self.generate_player_stats(
                    player_id=3000 + i, team_id=team_1_id, opponent_id=team_2_id, is_starter=i < 5
                )
            )

        for i in range(num_players_per_team):
            # Team 2 players
            players.append(
                self.generate_player_stats(
                    player_id=4000 + i, team_id=team_2_id, opponent_id=team_1_id, is_starter=i < 5
                )
            )

        return players

    def generate_pattern_2_with_players_key(
        self, game_id: int = 28931, num_players_per_team: int = 10
    ) -> dict[str, Any]:
        """Pattern 2: Dict with "players" key."""
        players = self.generate_pattern_1_simple_list(game_id, num_players_per_team)

        return {
            "match_external_id": game_id,
            "match_date": "2025-11-11",
            "players": players,
            "teams": [
                {"team_external_id": 1794, "team_name": "Paris", "score": 97},
                {"team_external_id": 1786, "team_name": "Gravelines", "score": 67},
            ],
        }

    def generate_pattern_3_home_away_split(
        self, game_id: int = 28931, num_players_per_team: int = 10
    ) -> dict[str, Any]:
        """Pattern 3: Separate home/away player lists."""
        team_1_id = 1794
        team_2_id = 1786

        home_players = []
        for i in range(num_players_per_team):
            home_players.append(
                self.generate_player_stats(
                    player_id=3000 + i, team_id=team_1_id, opponent_id=team_2_id, is_starter=i < 5
                )
            )

        away_players = []
        for i in range(num_players_per_team):
            away_players.append(
                self.generate_player_stats(
                    player_id=4000 + i, team_id=team_2_id, opponent_id=team_1_id, is_starter=i < 5
                )
            )

        return {
            "match_external_id": game_id,
            "match_date": "2025-11-11",
            "home_team": {"team_external_id": team_1_id, "team_name": "Paris", "score": 97},
            "away_team": {"team_external_id": team_2_id, "team_name": "Gravelines", "score": 67},
            "home_players": home_players,
            "away_players": away_players,
        }

    def generate_pattern_4_nested_teams(
        self, game_id: int = 28931, num_players_per_team: int = 10
    ) -> dict[str, Any]:
        """Pattern 4: Teams with nested players."""
        team_1_id = 1794
        team_2_id = 1786

        team_1_players = []
        for i in range(num_players_per_team):
            team_1_players.append(
                self.generate_player_stats(
                    player_id=3000 + i, team_id=team_1_id, opponent_id=team_2_id, is_starter=i < 5
                )
            )

        team_2_players = []
        for i in range(num_players_per_team):
            team_2_players.append(
                self.generate_player_stats(
                    player_id=4000 + i, team_id=team_2_id, opponent_id=team_1_id, is_starter=i < 5
                )
            )

        return {
            "match_external_id": game_id,
            "match_date": "2025-11-11",
            "teams": [
                {
                    "team_external_id": team_1_id,
                    "team_name": "Paris",
                    "score": 97,
                    "players": team_1_players,
                },
                {
                    "team_external_id": team_2_id,
                    "team_name": "Gravelines",
                    "score": 67,
                    "players": team_2_players,
                },
            ],
        }

    def save_all_patterns(self, output_dir: str = "tools/lnb/mock_data"):
        """Generate and save all patterns to JSON files."""
        import os

        os.makedirs(output_dir, exist_ok=True)

        patterns = {
            "pattern_1_simple_list.json": self.generate_pattern_1_simple_list(),
            "pattern_2_players_key.json": self.generate_pattern_2_with_players_key(),
            "pattern_3_home_away.json": self.generate_pattern_3_home_away_split(),
            "pattern_4_nested_teams.json": self.generate_pattern_4_nested_teams(),
        }

        for filename, data in patterns.items():
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[OK] Generated: {filepath}")

        return patterns


def main():
    """Generate mock data for all patterns."""
    print("=" * 70)
    print("  LNB Mock Boxscore Data Generator")
    print("=" * 70)
    print()

    generator = MockBoxscoreGenerator()

    print("Generating mock data for all 4 response patterns...")
    print()

    patterns = generator.save_all_patterns()

    print()
    print("=" * 70)
    print("  Generated Files")
    print("=" * 70)
    for filename in patterns.keys():
        print(f"  - tools/lnb/mock_data/{filename}")

    print()
    print("[OK] Mock data generation complete!")
    print()
    print("Use these files to test the parser before endpoint discovery:")
    print("  python test_lnb_parser_with_mocks.py")


if __name__ == "__main__":
    main()
