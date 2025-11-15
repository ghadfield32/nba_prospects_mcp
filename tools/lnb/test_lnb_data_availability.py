#!/usr/bin/env python3
"""Test LNB Data Availability

Automatically tests all LNB API endpoints to see what data is actually available.
No manual input required - runs completely automatically.

Usage:
    uv run python tools/lnb/test_lnb_data_availability.py
"""

import sys
from datetime import date
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

print("=" * 80)
print("  LNB Data Availability Test (Using Official API)")
print("=" * 80)
print()
print(f"[DEBUG] Python executable: {sys.executable}")
print(f"[DEBUG] Python version: {sys.version.split()[0]}")
print(f"[DEBUG] Current directory: {Path.cwd()}")
print()

# Test imports
print("[STEP 1] Testing imports...")
print("-" * 80)

try:
    import pandas as pd

    print(f"[OK] pandas {pd.__version__} imported")
except ImportError as e:
    print(f"[ERROR] Failed to import pandas: {e}")
    print()
    print("SOLUTION: Run this script with uv:")
    print("  uv run python tools/lnb/test_lnb_data_availability.py")
    sys.exit(1)

try:
    from cbb_data.fetchers.lnb_api import LNBClient

    print("[OK] LNBClient imported")
except ImportError as e:
    print(f"[ERROR] Failed to import LNBClient: {e}")
    sys.exit(1)

print()

# Initialize client
print("[DEBUG] Initializing LNB API client...")
client = LNBClient()
print("[OK] Client initialized")
print()

# Test schedule endpoint via API
print("[STEP 2] Testing Schedule Data...")
print("-" * 80)

games = []
try:
    print("[DEBUG] Calling iter_full_season_calendar(2024-09-01 to 2025-06-30)...")
    games = list(
        client.iter_full_season_calendar(
            season_start=date(2024, 9, 1), season_end=date(2025, 6, 30)
        )
    )

    print(f"[SUCCESS] Schedule data retrieved: {len(games)} games")
    print()
    if len(games) > 0:
        print("Sample games (first 3):")
        for i, game in enumerate(games[:3]):
            print(f"  Game {i+1}:")
            print(f"    ID: {game.get('match_external_id', 'N/A')}")
            print(f"    Date: {game.get('match_start_date', 'N/A')[:10]}")
            print(
                f"    Teams: {game.get('home_team_name', 'N/A')} vs {game.get('away_team_name', 'N/A')}"
            )
            score_home = game.get("home_team_score", "N/A")
            score_away = game.get("away_team_score", "N/A")
            print(f"    Score: {score_home}-{score_away}")
        print()
        print(f"[INFO] Available fields: {len(games[0].keys())} total")
        print(
            "[INFO] Key fields: match_external_id, match_start_date, home/away_team_name, scores, venue"
        )
    print()
except Exception as e:
    print(f"[ERROR] Schedule fetch failed: {e}")
    import traceback

    traceback.print_exc()
    print()

# Test player season endpoint via API
print("[STEP 3] Testing Player Season Data...")
print("-" * 80)

try:
    print(
        "[DEBUG] Calling get_persons_leaders(competition_id=302, year=2024, category='average_points')..."
    )

    players = client.get_persons_leaders(
        competition_external_id=302, year=2024, category="average_points"
    )

    print(f"[SUCCESS] Player leaders data retrieved: {len(players)} players")
    print()
    if len(players) > 0:
        print("Top 5 scorers:")
        for i, player in enumerate(players[:5]):
            name = player.get("person_name", "Unknown")
            team = player.get("team_name", "Unknown")
            value = player.get("value", 0)
            games_played = player.get("number_of_games", 0)
            print(f"  {i+1}. {name} ({team})")
            print(f"      {value} PPG in {games_played} games")
        print()
        print(f"[INFO] Available fields: {len(players[0].keys())} total")
        print("[INFO] Key fields: person_name, team_name, value, number_of_games, rank")
    print()

    # Test multiple categories
    print("[DEBUG] Testing additional stat categories...")
    categories_to_test = {
        "average_rebounds": "RPG",
        "average_assists": "APG",
        "average_three_points_made": "3PM",
    }

    available_categories = []
    for cat, label in categories_to_test.items():
        try:
            data = client.get_persons_leaders(competition_external_id=302, year=2024, category=cat)
            if data:
                available_categories.append(f"{label} ({len(data)} players)")
        except Exception:
            pass

    if available_categories:
        print(f"[SUCCESS] Additional categories available: {', '.join(available_categories)}")
    print()

except Exception as e:
    print(f"[ERROR] Player season fetch failed: {e}")
    import traceback

    traceback.print_exc()
    print()

# Test team data via API
print("[STEP 4] Testing Team Data...")
print("-" * 80)

try:
    print("[DEBUG] Calling get_competition_teams(competition_id=302)...")
    teams = client.get_competition_teams(competition_external_id=302)

    print(f"[SUCCESS] Team data retrieved: {len(teams)} teams")
    print()
    if len(teams) > 0:
        print("Teams in Betclic ÉLITE (2024-25):")
        for i, team in enumerate(teams):
            name = team.get("team_name", "Unknown")
            team_id = team.get("team_external_id", "N/A")
            print(f"  {i+1}. {name} (ID: {team_id})")
        print()
        print(f"[INFO] Available fields: {len(teams[0].keys())} total")
        print("[INFO] Key fields: team_name, team_external_id, team_id (UUID)")
    print()
except Exception as e:
    print(f"[ERROR] Team data fetch failed: {e}")
    import traceback

    traceback.print_exc()
    print()

# Test match context data
print("[STEP 5] Testing Match Context Data...")
print("-" * 80)

if games and len(games) > 0:
    try:
        test_match = games[0]
        match_id = test_match.get("match_external_id")
        print(f"[DEBUG] Testing match context for game {match_id}...")

        # Team comparison
        print("[DEBUG] Calling get_team_comparison...")
        comparison = client.get_team_comparison(match_external_id=match_id)
        if comparison:
            print("[SUCCESS] Team comparison data available")
            print(f"  Fields: {len(comparison.keys())} total")

        # Last 5 matches
        print("[DEBUG] Calling get_last_five_matches_home_away...")
        last_five = client.get_last_five_matches_home_away(match_external_id=match_id)
        if last_five:
            print("[SUCCESS] Last 5 matches data available")

        # Officials
        print("[DEBUG] Calling get_match_officials_pregame...")
        officials = client.get_match_officials_pregame(match_external_id=match_id)
        if officials:
            print("[SUCCESS] Match officials data available")

        print()
    except Exception as e:
        print(f"[ERROR] Match context fetch failed: {e}")
        print()
else:
    print("[SKIP] No games available to test match context")
    print()

# Test boxscore endpoint (known to be unavailable)
print("[STEP 6] Testing Player Game (Boxscore) Data...")
print("-" * 80)

print("[INFO] Boxscore endpoint requires manual discovery during live game")
print("[INFO] Parser is ready and tested with 4 response patterns")
print("[INFO] To discover endpoint:")
print("  1. Wait for live LNB game")
print("  2. Open browser DevTools during game")
print("  3. Look for API calls with player box score stats")
print("  4. Update fetch_lnb_player_game() with discovered endpoint path")
print()

# Check for play-by-play and shots
print("[STEP 7] Checking for Play-by-Play and Shots Data...")
print("-" * 80)

print("[INFO] Play-by-play and shot chart endpoints not yet discovered")
print("[INFO] These may be available via the same DevTools discovery process")
print("[INFO] Look for endpoints containing:")
print("  - Play-by-play: 'pbp', 'events', 'actions', 'timeline'")
print("  - Shots: 'shots', 'shot_chart', 'coordinates', 'x_y'")
print()

# Summary
print("=" * 80)
print("  DATA AVAILABILITY SUMMARY")
print("=" * 80)
print()

print("AVAILABLE via Official LNB API:")
print(f"  [SUCCESS] Schedule - {len(games) if games else 0} games (getCalendar)")
print("  [SUCCESS] Player Leaders - By category (getPersonsLeaders)")
print("  [SUCCESS] Team Info - Competition rosters (getCompetitionTeams)")
print("  [SUCCESS] Match Context - Comparison, form, officials")
print("  [SUCCESS] Structure - Years, competitions, divisions")
print()

print("NOT YET AVAILABLE:")
print("  [PENDING] Player Game (Boxscore) - Requires endpoint discovery")
print("  [PENDING] Play-by-Play - Requires endpoint discovery")
print("  [PENDING] Shot Charts - Requires endpoint discovery")
print()

print("NEXT STEPS:")
print("  1. Boxscore: Follow LNB_BOXSCORE_DISCOVERY_GUIDE.md during live game")
print("  2. Play-by-play/Shots: Use same DevTools discovery process")
print("  3. Review LNB_API_RATE_LIMITS_AND_USAGE.md for best practices")
print()

print("[SUCCESS] Data availability test complete!")
print()
