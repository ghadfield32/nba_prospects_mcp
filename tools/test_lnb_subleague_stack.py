"""LNB Sub-League Stack Test

Comprehensive test to validate LNB sub-leagues at all levels:
1. Fetcher level - Direct function calls
2. API level - get_dataset calls
3. MCP level - Tool availability

Usage:
    python tools/test_lnb_subleague_stack.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime


def test_fetcher_level():
    """Test 1: Direct fetcher function calls"""
    print("\n" + "=" * 70)
    print("TEST 1: FETCHER LEVEL - Direct Function Calls")
    print("=" * 70)

    from cbb_data.fetchers import lnb

    results = {}
    leagues = {
        "LNB_ELITE2": {
            "player_game": lnb.fetch_elite2_player_game,
            "team_game": lnb.fetch_elite2_team_game,
            "pbp": lnb.fetch_elite2_pbp,
            "shots": lnb.fetch_elite2_shots,
        },
        "LNB_ESPOIRS_ELITE": {
            "player_game": lnb.fetch_espoirs_elite_player_game,
            "team_game": lnb.fetch_espoirs_elite_team_game,
            "pbp": lnb.fetch_espoirs_elite_pbp,
            "shots": lnb.fetch_espoirs_elite_shots,
        },
        "LNB_ESPOIRS_PROB": {
            "player_game": lnb.fetch_espoirs_prob_player_game,
            "team_game": lnb.fetch_espoirs_prob_team_game,
            "pbp": lnb.fetch_espoirs_prob_pbp,
            "shots": lnb.fetch_espoirs_prob_shots,
        },
    }

    for league, funcs in leagues.items():
        print(f"\n{league}:")
        results[league] = {}

        for dataset, func in funcs.items():
            try:
                # Try 2025-2026 season format (LNB historical uses this)
                df = func(season="2025-2026")
                rows = len(df) if df is not None else 0
                status = "[Y]" if rows > 0 else "[~]"  # ~ means empty but no error
                print(f"  {status} {dataset}: {rows} rows")
                results[league][dataset] = {"status": "ok", "rows": rows}
            except Exception as e:
                print(f"  [X] {dataset}: {type(e).__name__}: {str(e)[:60]}")
                results[league][dataset] = {"status": "error", "error": str(e)}

    return results


def test_api_level():
    """Test 2: API-level get_dataset calls"""
    print("\n" + "=" * 70)
    print("TEST 2: API LEVEL - get_dataset() Calls")
    print("=" * 70)

    from cbb_data.api.datasets import get_dataset
    from cbb_data.catalog.sources import _register_league_sources

    # Ensure sources are registered
    _register_league_sources()

    results = {}
    leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]
    datasets = ["player_game", "team_game", "pbp", "shots"]

    for league in leagues:
        print(f"\n{league}:")
        results[league] = {}

        for dataset in datasets:
            try:
                # Build appropriate filters
                if dataset in ["pbp", "shots"]:
                    # These need game_ids or will use season
                    filters = {"league": league, "season": "2025-2026"}
                else:
                    filters = {"league": league, "season": "2025-2026"}

                df = get_dataset(
                    grouping=dataset,
                    filters=filters,
                    limit=100,
                    pre_only=True,
                )

                rows = len(df) if df is not None and not df.empty else 0
                status = "[Y]" if rows > 0 else "[~]"
                print(f"  {status} {dataset}: {rows} rows")
                results[league][dataset] = {"status": "ok", "rows": rows}

            except Exception as e:
                error_msg = str(e)[:80]
                print(f"  [X] {dataset}: {error_msg}")
                results[league][dataset] = {"status": "error", "error": error_msg}

    return results


def test_mcp_level():
    """Test 3: MCP tool availability"""
    print("\n" + "=" * 70)
    print("TEST 3: MCP LEVEL - Tool Availability")
    print("=" * 70)

    from typing import get_args

    from cbb_data.servers.mcp.tools import TOOLS as MCP_TOOLS
    from cbb_data.servers.mcp_models import LeagueType

    # Check if LNB sub-leagues are in MCP LeagueType
    mcp_leagues = get_args(LeagueType)
    target_leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]

    print("\nLeagueType validation:")
    for league in target_leagues:
        if league in mcp_leagues:
            print(f"  [Y] {league} in LeagueType")
        else:
            print(f"  [X] {league} NOT in LeagueType")

    # Check relevant MCP tools
    print("\nMCP Tools that support these leagues:")
    relevant_tools = [
        "get_player_game_stats",
        "get_team_game_stats",
        "get_play_by_play",
        "get_shot_chart",
    ]

    for tool_name in relevant_tools:
        tool = next((t for t in MCP_TOOLS if t["name"] == tool_name), None)
        if tool:
            print(f"  [Y] {tool_name}")
        else:
            print(f"  [X] {tool_name} NOT FOUND")

    return {"leagues_in_type": [league for league in target_leagues if league in mcp_leagues]}


def test_filter_spec_validation():
    """Test 4: FilterSpec validation"""
    print("\n" + "=" * 70)
    print("TEST 4: FILTER SPEC VALIDATION")
    print("=" * 70)

    from typing import get_args

    from cbb_data.filters.spec import FilterSpec, League

    # Check League Literal
    valid_leagues = get_args(League)
    target_leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]

    print("\nLeague Literal validation:")
    for league in target_leagues:
        if league in valid_leagues:
            print(f"  [Y] {league} in League Literal")
        else:
            print(f"  [X] {league} NOT in League Literal")

    # Test FilterSpec creation
    print("\nFilterSpec creation:")
    for league in target_leagues:
        try:
            FilterSpec(league=league, season="2025")
            print(f"  [Y] FilterSpec({league}) created successfully")
        except Exception as e:
            print(f"  [X] FilterSpec({league}): {e}")

    return {"valid": [league for league in target_leagues if league in valid_leagues]}


def test_league_levels():
    """Test 5: League levels configuration"""
    print("\n" + "=" * 70)
    print("TEST 5: LEAGUE LEVELS CONFIGURATION")
    print("=" * 70)

    from cbb_data.catalog.levels import LEAGUE_LEVELS, is_pre_nba_league

    target_leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]

    print("\nLEAGUE_LEVELS map:")
    for league in target_leagues:
        if league in LEAGUE_LEVELS:
            level = LEAGUE_LEVELS[league]
            pre_nba = is_pre_nba_league(league)
            print(f"  [Y] {league}: level={level}, pre_nba={pre_nba}")
        else:
            print(f"  [X] {league} NOT in LEAGUE_LEVELS")

    return {"configured": [league for league in target_leagues if league in LEAGUE_LEVELS]}


def test_sources_wiring():
    """Test 6: Sources wiring verification"""
    print("\n" + "=" * 70)
    print("TEST 6: SOURCES WIRING VERIFICATION")
    print("=" * 70)

    from cbb_data.catalog.sources import LEAGUE_SOURCES, _register_league_sources

    # Ensure sources are registered
    _register_league_sources()

    target_leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]
    datasets = ["fetch_player_game", "fetch_team_game", "fetch_pbp", "fetch_shots"]

    results = {}
    for league in target_leagues:
        print(f"\n{league}:")
        config = LEAGUE_SOURCES.get(league)

        if not config:
            print("  [X] NOT REGISTERED in LEAGUE_SOURCES")
            results[league] = {"registered": False}
            continue

        results[league] = {"registered": True, "wired": {}}
        for ds in datasets:
            func = getattr(config, ds, None)
            if func:
                print(f"  [Y] {ds}: {func.__name__}")
                results[league]["wired"][ds] = func.__name__
            else:
                print(f"  [X] {ds}: NOT WIRED")
                results[league]["wired"][ds] = None

    return results


def generate_summary(all_results):
    """Generate summary of all tests"""
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Count successes
    fetcher_ok = sum(
        1
        for league in all_results.get("fetcher", {}).values()
        for ds in league.values()
        if ds.get("status") == "ok" and ds.get("rows", 0) > 0
    )

    api_ok = sum(
        1
        for league in all_results.get("api", {}).values()
        for ds in league.values()
        if ds.get("status") == "ok" and ds.get("rows", 0) > 0
    )

    print(f"\nFetcher Level: {fetcher_ok}/12 datasets returning data")
    print(f"API Level: {api_ok}/12 datasets returning data")

    # Note issues
    print("\nKey Issues:")
    print("  - player_game: Normalized data not yet created for 2025-2026")
    print("  - fixtures.parquet: Missing division column for filtering")

    print("\nRecommended Actions:")
    print("  1. Run: python tools/lnb/create_normalized_tables.py --season 2025-2026")
    print("  2. Update LNB scraper to include division in fixtures")
    print("  3. Re-ingest historical data with division tagging")


def main():
    print("=" * 70)
    print("LNB SUB-LEAGUE COMPREHENSIVE STACK TEST")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    all_results = {}

    # Run all tests
    all_results["sources"] = test_sources_wiring()
    all_results["levels"] = test_league_levels()
    all_results["filter_spec"] = test_filter_spec_validation()
    all_results["mcp"] = test_mcp_level()
    all_results["fetcher"] = test_fetcher_level()
    all_results["api"] = test_api_level()

    # Generate summary
    generate_summary(all_results)

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    return all_results


if __name__ == "__main__":
    main()
