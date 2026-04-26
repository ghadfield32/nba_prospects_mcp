#!/usr/bin/env python
"""Validate Cross-League Player Tracking

Tests that we can track players across multiple leagues and capture their complete careers.
"""

from pathlib import Path

import pandas as pd

# Load unified dataset
gold_path = Path("data/gold/player_career_unified_tier1.parquet")
if not gold_path.exists():
    print(f"ERROR: Unified dataset not found at {gold_path}")
    exit(1)

gold = pd.read_parquet(gold_path)

# Players to validate
players = [
    {
        "name": "Karter Knox",
        "search": ["Karter", "Knox"],
        "expected_leagues": ["OTE"],
        "notes": "Current OTE player (2024-25)",
    },
    {
        "name": "Zion Williamson",
        "search": ["Zion", "Williamson"],
        "expected_leagues": ["NCAA_MBB"],
        "notes": "Duke 2018-19 → NBA",
    },
    {
        "name": "Alex Caruso",
        "search": ["Alex", "Caruso"],
        "expected_leagues": ["NCAA_MBB", "G_LEAGUE"],
        "notes": "NCAA → G-League → NBA",
    },
    {
        "name": "Sasha Vezenkov",
        "search": ["Sasha", "Vezenkov", "Saša", "Aleksandar"],
        "expected_leagues": ["EUROLEAGUE"],
        "notes": "EuroLeague → NBA → EuroLeague",
    },
    {
        "name": "Luka Dončić",
        "search": ["Luka", "Doncic"],
        "expected_leagues": ["ACB", "EUROLEAGUE"],
        "notes": "ACB + EuroLeague → NBA",
    },
    {
        "name": "Amen Thompson",
        "search": ["Amen", "Thompson"],
        "expected_leagues": ["OTE"],
        "notes": "OTE 2021-23 → NBA (4th pick 2023)",
    },
    {
        "name": "LaMelo Ball",
        "search": ["LaMelo", "Ball", "Lamelo"],
        "expected_leagues": ["NBL"],
        "notes": "NBL 2019-20 → NBA (3rd pick 2020)",
    },
    {
        "name": "Tazé Moore",
        "search": ["Tazé", "Taze", "Moore"],
        "expected_leagues": ["CEBL"],
        "notes": "CEBL → NBA two-way",
    },
    {
        "name": "David Thompson",
        "search": ["David", "Thompson"],
        "expected_leagues": ["ABA", "NCAA_MBB"],
        "notes": "ABA → NBA (historical)",
    },
]

print("=" * 80)
print("CROSS-LEAGUE PLAYER VALIDATION")
print("=" * 80)
print(f"Total players in dataset: {gold['PLAYER_UID'].nunique():,}")
print(f"Total records: {len(gold):,}")
print(f"Leagues: {sorted(gold['SOURCE_LEAGUE'].unique())}")
print("")

results = []

for player_info in players:
    name = player_info["name"]
    search_terms = player_info["search"]
    expected_leagues = player_info["expected_leagues"]
    notes = player_info["notes"]

    print(f"\n{'='*80}")
    print(f"SEARCHING: {name}")
    print(f"Expected leagues: {', '.join(expected_leagues)}")
    print(f"Notes: {notes}")
    print("-" * 80)

    # Search for player (try multiple search terms)
    player_data = None
    for term in search_terms:
        matches = gold[gold["PLAYER_NAME_RAW"].str.contains(term, case=False, na=False)]
        if len(matches) > 0:
            # Refine search - look for all search terms
            for other_term in search_terms:
                if other_term != term:
                    matches = matches[
                        matches["PLAYER_NAME_RAW"].str.contains(other_term, case=False, na=False)
                    ]

            if len(matches) > 0:
                player_data = matches
                break

    if player_data is None or len(player_data) == 0:
        print("❌ NOT FOUND in unified dataset")
        print(f"   Search terms tried: {search_terms}")

        # Check if they exist in canonical data
        print("\n   Checking canonical data for presence...")
        found_in_canonical = False
        for league in expected_leagues:
            league_dir = Path(f"data/canonical/box_player_game/league={league}")
            if league_dir.exists():
                # Sample first season
                season_dirs = sorted([d for d in league_dir.iterdir() if d.is_dir()])
                for season_dir in season_dirs[:3]:  # Check first 3 seasons
                    data_file = season_dir / "data.parquet"
                    if data_file.exists():
                        try:
                            canon = pd.read_parquet(data_file)
                            for term in search_terms:
                                if (
                                    canon["PLAYER_NAME_RAW"]
                                    .str.contains(term, case=False, na=False)
                                    .any()
                                ):
                                    print(f"   ✓ FOUND in canonical {league}/{season_dir.name}")
                                    found_in_canonical = True
                                    # Show sample
                                    sample = canon[
                                        canon["PLAYER_NAME_RAW"].str.contains(
                                            term, case=False, na=False
                                        )
                                    ]
                                    print(
                                        f"     Sample names: {sample['PLAYER_NAME_RAW'].unique()[:3].tolist()}"
                                    )
                                    print(
                                        f"     SOURCE_PLAYER_ID: {sample['SOURCE_PLAYER_ID'].unique()[:3].tolist()}"
                                    )
                                    break
                        except Exception:
                            pass
                    if found_in_canonical:
                        break
                if found_in_canonical:
                    break

        if not found_in_canonical:
            print("   ✗ Not found in canonical data either")

        results.append(
            {
                "player": name,
                "status": "NOT_FOUND",
                "games": 0,
                "leagues": [],
                "uids": 0,
                "in_canonical": found_in_canonical,
            }
        )
        continue

    # Found player - analyze
    total_games = len(player_data)
    unique_uids = player_data["PLAYER_UID"].nunique()
    leagues_found = sorted(player_data["SOURCE_LEAGUE"].unique())

    print(f"✅ FOUND: {total_games} games across {len(leagues_found)} league(s)")
    print(f"   Unique PLAYER_UIDs: {unique_uids}")
    print(f"   Leagues: {', '.join(leagues_found)}")

    # Show breakdown by league and season
    print("\n   Career Breakdown:")
    summary = (
        player_data.groupby(["SOURCE_LEAGUE", "SEASON"])
        .agg({"PLAYER_NAME_RAW": "first", "PLAYER_UID": "first", "GAME_ID": "count"})
        .rename(columns={"GAME_ID": "games"})
        .reset_index()
    )

    for _, row in summary.iterrows():
        print(
            f"     {row['SOURCE_LEAGUE']:12} {row['SEASON']:8} - {row['games']:3} games (UID: {row['PLAYER_UID'][:20]}...)"
        )

    # Check if all expected leagues are present
    missing_leagues = set(expected_leagues) - set(leagues_found)
    if missing_leagues:
        print(f"\n   ⚠️  WARNING: Missing expected leagues: {', '.join(missing_leagues)}")

    # Check if unified under single UID
    if unique_uids == 1:
        print("\n   🎉 SUCCESS: Unified under single PLAYER_UID")
    else:
        print(f"\n   ⚠️  WARNING: Split across {unique_uids} UIDs")

    results.append(
        {
            "player": name,
            "status": "FOUND",
            "games": total_games,
            "leagues": leagues_found,
            "uids": unique_uids,
            "missing_leagues": list(missing_leagues) if missing_leagues else None,
        }
    )

# Summary report
print("\n" + "=" * 80)
print("SUMMARY REPORT")
print("=" * 80)

found_count = sum(1 for r in results if r["status"] == "FOUND")
not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")

print(f"\nPlayers found: {found_count}/{len(players)}")
print(f"Players missing: {not_found_count}/{len(players)}")

if not_found_count > 0:
    print("\nMissing players:")
    for r in results:
        if r["status"] == "NOT_FOUND":
            in_canon = "✓ In canonical" if r.get("in_canonical") else "✗ Not in canonical"
            print(f"  - {r['player']:20} ({in_canon})")

print("\nPlayers by league coverage:")
league_coverage = {}
for r in results:
    if r["status"] == "FOUND":
        for league in r["leagues"]:
            if league not in league_coverage:
                league_coverage[league] = []
            league_coverage[league].append(r["player"])

for league in sorted(league_coverage.keys()):
    players_list = league_coverage[league]
    print(f"  {league:12} - {len(players_list)} players: {', '.join(players_list)}")

# Multi-UID warnings
multi_uid_players = [r for r in results if r["status"] == "FOUND" and r["uids"] > 1]
if multi_uid_players:
    print("\n⚠️  Players with multiple UIDs (need investigation):")
    for r in multi_uid_players:
        print(f"  - {r['player']:20} - {r['uids']} UIDs across {len(r['leagues'])} leagues")

print("\n" + "=" * 80)
