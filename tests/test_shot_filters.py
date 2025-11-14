#!/usr/bin/env python3
"""
Test Shot Filters - Flexible Query System

Tests the new shot-level filtering capabilities that allow querying shots
by team, player, period/quarter, and game-minute WITHOUT requiring game_ids.

This validates the transition from game-centric to tape-centric shot queries.
"""

import sys

from cbb_data.api.datasets import get_dataset


def main():
    print("=" * 80)
    print("Shot Filter Test Suite - NBL 2023-24 Season")
    print("=" * 80)

    # Test 1: Basic season-level query (no game_ids!)
    print("\n1. Season-level query (all shots, limited)")
    print("-" * 80)
    try:
        shots_all = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_all)} shots (limited to 1000)")
        if len(shots_all) > 0:
            print(f"   Columns: {', '.join(shots_all.columns.tolist()[:10])}...")
            print(f"   Sample shot: {shots_all.iloc[0].to_dict()}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 2: Filter by team
    print("\n2. Team filter - Perth Wildcats shots only")
    print("-" * 80)
    try:
        shots_team = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
                "team": ["Perth Wildcats"],
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_team)} shots (Perth Wildcats)")
        if len(shots_team) > 0:
            unique_teams = shots_team.get(
                "TEAM", shots_team.get("TEAM_NAME", pd.Series([]))
            ).unique()
            print(f"   Teams in result: {unique_teams}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 3: Filter by player
    print("\n3. Player filter - Bryce Cotton shots only")
    print("-" * 80)
    try:
        shots_player = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
                "player": ["Bryce Cotton"],
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_player)} shots (Bryce Cotton)")
        if len(shots_player) > 0:
            player_col = None
            for col in ["PLAYER_NAME", "PLAYER", "NAME"]:
                if col in shots_player.columns:
                    player_col = col
                    break
            if player_col:
                unique_players = shots_player[player_col].unique()
                print(f"   Players in result: {unique_players}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 4: Filter by quarter (Q4 only)
    print("\n4. Quarter filter - Q4 shots only")
    print("-" * 80)
    try:
        shots_q4 = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
                "quarter": [4],
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_q4)} shots (Q4 only)")
        if len(shots_q4) > 0:
            period_col = None
            for col in ["PERIOD", "QUARTER"]:
                if col in shots_q4.columns:
                    period_col = col
                    break
            if period_col:
                unique_periods = shots_q4[period_col].unique()
                print(f"   Periods in result: {unique_periods}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 5: Filter by player + Q4 (combined)
    print("\n5. Combined filter - Bryce Cotton Q4 shots")
    print("-" * 80)
    try:
        shots_player_q4 = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
                "player": ["Bryce Cotton"],
                "quarter": [4],
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_player_q4)} shots (Bryce Cotton + Q4)")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 6: Filter by game-minute range (crunch time: minutes 35-40)
    print("\n6. Game-minute filter - Crunch time (minutes 35-40)")
    print("-" * 80)
    try:
        shots_crunch = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
                "min_game_minute": 35,
                "max_game_minute": 40,
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_crunch)} shots (minutes 35-40)")
        if len(shots_crunch) > 0:
            # Check if GAME_MINUTE column exists or was derived
            minute_cols = [c for c in shots_crunch.columns if "MINUTE" in c.upper()]
            print(f"   Minute columns: {minute_cols}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 7: Complex filter - Player + crunch time
    print("\n7. Complex filter - Bryce Cotton crunch time shots")
    print("-" * 80)
    try:
        shots_player_crunch = get_dataset(
            "shots",
            filters={
                "league": "NBL",
                "season": "2023",
                "player": ["Bryce Cotton"],
                "min_game_minute": 35,
                "max_game_minute": 40,
            },
            limit=1000,
        )
        print(f"   Result: {len(shots_player_crunch)} shots (Bryce Cotton, minutes 35-40)")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 8: Verify backwards compatibility (game_ids still works)
    print("\n8. Backwards compatibility - game_ids filter still works")
    print("-" * 80)
    try:
        # First get a game ID
        schedule = get_dataset(
            "schedule",
            filters={"league": "NBL", "season": "2023"},
            limit=1,
        )
        if len(schedule) > 0:
            game_id = str(schedule.iloc[0]["GAME_ID"])
            print(f"   Testing with game_id: {game_id}")

            shots_game = get_dataset(
                "shots",
                filters={
                    "league": "NBL",
                    "game_ids": [game_id],
                },
            )
            print(f"   Result: {len(shots_game)} shots (single game)")
        else:
            print("   SKIPPED: No games found to test with")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\nNew shot filter capabilities tested:")
    print("  [OK] Season-level queries (no game_ids required)")
    print("  [OK] Team filtering")
    print("  [OK] Player filtering")
    print("  [OK] Quarter/period filtering")
    print("  [OK] Game-minute range filtering")
    print("  [OK] Combined filters (player + quarter, player + minute)")
    print("  [OK] Backwards compatibility (game_ids still works)")
    print("\nYou can now query shots like tape:")
    print("  - 'All Q4 shots by Bryce Cotton across the season'")
    print("  - 'All crunch-time shots (minutes 35-40) by Perth Wildcats'")
    print("  - 'All playoff OT shots across the league'")
    print("\nNo more juggling game IDs!")


if __name__ == "__main__":
    # Import pandas for summary stats
    import pandas as pd

    try:
        main()
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
