#!/usr/bin/env python3
"""Known Players Validator - Curated Truth Set Testing

Non-blocking validator that tests specific known players against expected criteria.
Uses YAML fixture file with curated player test cases.

Exit code: 0 (always passes, warnings only)
"""

import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from typing import Any

import pandas as pd
import yaml

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GOLD_FILE = PROJECT_ROOT / "data" / "gold" / "player_career_unified_tier1.parquet"
PLAYER_MAP_FILE = PROJECT_ROOT / "data" / "identity" / "player_map.parquet"
FIXTURES_FILE = PROJECT_ROOT / "tests" / "fixtures" / "known_players.yaml"


def find_player_by_source_id(
    gold_df: pd.DataFrame, player_map: pd.DataFrame, league: str, source_id: str
) -> pd.DataFrame:
    """
    Find player by exact SOURCE_PLAYER_ID (NOT substring matching).

    Args:
        gold_df: Unified gold dataset
        player_map: Player identity map
        league: Source league code
        source_id: Source player ID

    Returns:
        DataFrame with all games for this player (empty if not found)
    """

    # Find mapping
    mapping = player_map[
        (player_map["SOURCE_LEAGUE"] == league) & (player_map["SOURCE_PLAYER_ID"] == source_id)
    ]

    if len(mapping) == 0:
        return pd.DataFrame()

    # Get PLAYER_UID
    player_uid = mapping.iloc[0]["PLAYER_UID"]

    # Return all games for this player
    return gold_df[gold_df["PLAYER_UID"] == player_uid].copy()


def validate_player(
    player_spec: dict[str, Any], gold_df: pd.DataFrame, player_map: pd.DataFrame
) -> dict[str, Any]:
    """
    Validate a single known player against expected criteria.

    Args:
        player_spec: Player specification from YAML
        gold_df: Unified gold dataset
        player_map: Player identity map

    Returns:
        dict with validation results
    """

    name = player_spec["name"]
    league = player_spec["source_id"]["league"]
    source_id = str(player_spec["source_id"]["id"])
    expected = player_spec.get("expected", {})

    # Find player
    player_games = find_player_by_source_id(gold_df, player_map, league, source_id)

    result = {
        "name": name,
        "league": league,
        "source_id": source_id,
        "found": len(player_games) > 0,
        "checks": [],
        "passed": False,
    }

    if not result["found"]:
        result["checks"].append(f"✗ Player not found in {league}")
        return result

    # Get actual stats
    total_games = len(player_games)
    unique_seasons = player_games["SEASON"].nunique()
    player_games["SOURCE_LEAGUE"].nunique()
    ppg = player_games["PTS"].mean() if "PTS" in player_games.columns else 0

    result["actual"] = {
        "total_games": total_games,
        "seasons": unique_seasons,
        "leagues": player_games["SOURCE_LEAGUE"].unique().tolist(),
        "ppg": round(ppg, 1),
    }

    # Run checks
    checks_passed = 0
    checks_total = 0

    # Check: minimum games
    if "games_min" in expected:
        checks_total += 1
        if total_games >= expected["games_min"]:
            result["checks"].append(f"✓ Games: {total_games} >= {expected['games_min']}")
            checks_passed += 1
        else:
            result["checks"].append(f"✗ Games: {total_games} < {expected['games_min']}")

    # Check: exact games
    if "games_exact" in expected:
        checks_total += 1
        if total_games == expected["games_exact"]:
            result["checks"].append(f"✓ Games: {total_games} = {expected['games_exact']}")
            checks_passed += 1
        else:
            result["checks"].append(f"✗ Games: {total_games} ≠ {expected['games_exact']}")

    # Check: minimum seasons
    if "seasons_min" in expected:
        checks_total += 1
        if unique_seasons >= expected["seasons_min"]:
            result["checks"].append(f"✓ Seasons: {unique_seasons} >= {expected['seasons_min']}")
            checks_passed += 1
        else:
            result["checks"].append(f"✗ Seasons: {unique_seasons} < {expected['seasons_min']}")

    # Check: exact seasons
    if "seasons_exact" in expected:
        checks_total += 1
        if unique_seasons == expected["seasons_exact"]:
            result["checks"].append(f"✓ Seasons: {unique_seasons} = {expected['seasons_exact']}")
            checks_passed += 1
        else:
            result["checks"].append(f"✗ Seasons: {unique_seasons} ≠ {expected['seasons_exact']}")

    # Check: minimum PPG
    if "ppg_min" in expected:
        checks_total += 1
        if ppg >= expected["ppg_min"]:
            result["checks"].append(f"✓ PPG: {ppg:.1f} >= {expected['ppg_min']}")
            checks_passed += 1
        else:
            result["checks"].append(f"✗ PPG: {ppg:.1f} < {expected['ppg_min']}")

    # Check: expected leagues
    if "leagues" in expected:
        checks_total += 1
        actual_leagues = set(result["actual"]["leagues"])
        expected_leagues = set(expected["leagues"])
        if expected_leagues.issubset(actual_leagues):
            result["checks"].append(
                f"✓ Leagues: {result['actual']['leagues']} contains {expected['leagues']}"
            )
            checks_passed += 1
        else:
            missing = expected_leagues - actual_leagues
            result["checks"].append(f"✗ Leagues: missing {list(missing)}")

    # Overall pass/fail
    result["passed"] = checks_passed == checks_total if checks_total > 0 else True
    result["checks_passed"] = checks_passed
    result["checks_total"] = checks_total

    return result


def main():
    print("=" * 80)
    print("KNOWN PLAYERS VALIDATOR")
    print("=" * 80)
    print()

    # Check files exist
    if not GOLD_FILE.exists():
        print(f"✗ Gold file not found: {GOLD_FILE}")
        return 0  # Non-blocking

    if not PLAYER_MAP_FILE.exists():
        print(f"✗ Player map not found: {PLAYER_MAP_FILE}")
        return 0  # Non-blocking

    if not FIXTURES_FILE.exists():
        print(f"✗ Fixtures file not found: {FIXTURES_FILE}")
        return 0  # Non-blocking

    # Load data
    print("Loading data...")
    gold_df = pd.read_parquet(GOLD_FILE)
    player_map = pd.read_parquet(PLAYER_MAP_FILE)
    print(f"  Gold: {len(gold_df):,} records")
    print(f"  Player map: {len(player_map):,} mappings")

    # Load fixtures
    with open(FIXTURES_FILE, encoding="utf-8") as f:
        fixtures = yaml.safe_load(f)

    known_players = fixtures.get("players", [])
    print(f"  Known players: {len(known_players)}")
    print()

    # Validate each player
    results = []

    for player_spec in known_players:
        result = validate_player(player_spec, gold_df, player_map)
        results.append(result)

        # Print result
        "✓ PASS" if result["passed"] else "✗ FAIL"
        symbol = "✓" if result["passed"] else "✗"

        print(f"{symbol} {result['name']:25} ({result['league']:12})")

        if result["found"]:
            print(
                f"  Games: {result['actual']['total_games']:3}  Seasons: {result['actual']['seasons']:2}  "
                + f"PPG: {result['actual']['ppg']:5.1f}  Leagues: {result['actual']['leagues']}"
            )
            for check in result["checks"]:
                print(f"  {check}")
        else:
            print(f"  ⚠️  NOT FOUND - Check source_id: {result['source_id']}")

        # Show notes if present
        if "notes" in player_spec:
            print(f"  Notes: {player_spec['notes']}")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_players = len(results)
    found_players = sum(1 for r in results if r["found"])
    passed_players = sum(1 for r in results if r["passed"])
    not_found = total_players - found_players

    print(f"\nPlayers tested: {total_players}")
    print(f"  Found: {found_players} ({found_players/total_players*100:.1f}%)")
    print(f"  Not found: {not_found} ({not_found/total_players*100:.1f}%)")
    print(f"  Passed validation: {passed_players} ({passed_players/total_players*100:.1f}%)")

    if not_found > 0:
        print("\nNot found players:")
        for r in results:
            if not r["found"]:
                print(f"  - {r['name']} ({r['league']}, ID: {r['source_id']})")

    print()

    if passed_players == total_players:
        print("✓✓✓ ALL KNOWN PLAYERS VALIDATED")
    elif passed_players >= total_players * 0.8:
        print("⚠️  MOST KNOWN PLAYERS VALIDATED (some issues)")
    else:
        print("⚠️  MANY KNOWN PLAYERS FAILED VALIDATION")

    print("\nNote: This is a non-blocking validator (exit code 0)")
    return 0  # Always pass (non-blocking)


if __name__ == "__main__":
    sys.exit(main())
