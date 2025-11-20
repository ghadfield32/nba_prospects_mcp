"""Debug LNB Sub-League Dataset Issues

Deep investigation into why player_game, team_game, schedule, player_season,
team_season show as unavailable for LNB sub-leagues.

This script traces through the exact code paths to identify root causes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def debug_step_1_wiring():
    """Step 1: Verify what's wired in LeagueSourceConfig"""
    print("\n" + "=" * 70)
    print("STEP 1: LeagueSourceConfig Wiring Analysis")
    print("=" * 70)

    from cbb_data.catalog.sources import LEAGUE_SOURCES, _register_league_sources

    _register_league_sources()

    leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]
    all_fetch_attrs = [
        "fetch_schedule",
        "fetch_player_season",
        "fetch_team_season",
        "fetch_player_game",
        "fetch_team_game",
        "fetch_pbp",
        "fetch_shots",
    ]

    for league in leagues:
        print(f"\n{league}:")
        config = LEAGUE_SOURCES.get(league)
        if not config:
            print("  [X] NOT REGISTERED IN LEAGUE_SOURCES")
            continue

        for attr in all_fetch_attrs:
            func = getattr(config, attr, None)
            if func:
                print(f"  [Y] {attr}: {func.__name__}")
            else:
                print(f"  [X] {attr}: NOT WIRED (None)")


def debug_step_2_fetcher_returns():
    """Step 2: Test what the wired fetchers actually return"""
    print("\n" + "=" * 70)
    print("STEP 2: Direct Fetcher Return Analysis")
    print("=" * 70)

    from cbb_data.fetchers import lnb

    league = "LNB_ELITE2"
    print(f"\nTesting {league} fetchers with season='2025-2026':")

    # Test player_game
    print("\n  fetch_elite2_player_game():")
    try:
        df = lnb.fetch_elite2_player_game(season="2025-2026")
        print(f"    Returned: {len(df)} rows")
        if df.empty:
            print("    Why empty? Checking internal call...")
            # The function calls fetch_lnb_player_game_normalized
            # which calls get_lnb_normalized_player_game
            from cbb_data.api.lnb_historical import get_lnb_normalized_player_game

            inner_df = get_lnb_normalized_player_game(season="2025-2026", league=league)
            print(f"    Inner get_lnb_normalized_player_game: {len(inner_df)} rows")
    except Exception as e:
        print(f"    Error: {type(e).__name__}: {e}")

    # Test team_game
    print("\n  fetch_elite2_team_game():")
    try:
        df = lnb.fetch_elite2_team_game(season="2025-2026")
        print(f"    Returned: {len(df)} rows")
    except Exception as e:
        print(f"    Error: {type(e).__name__}: {e}")


def debug_step_3_api_fetch_player_game():
    """Step 3: Trace through _fetch_player_game code path"""
    print("\n" + "=" * 70)
    print("STEP 3: _fetch_player_game Code Path Analysis")
    print("=" * 70)

    from cbb_data.catalog.sources import _register_league_sources, get_league_source_config

    _register_league_sources()

    league = "LNB_ELITE2"
    print(f"\nTracing get_dataset('player_game', league='{league}'):")

    # Check LeagueSourceConfig
    src_cfg = get_league_source_config(league)
    print(f"\n  1. get_league_source_config('{league}'):")
    print(f"     Result: {src_cfg is not None}")
    if src_cfg:
        print(f"     fetch_player_game wired: {src_cfg.fetch_player_game is not None}")
        if src_cfg.fetch_player_game:
            print(f"     Function name: {src_cfg.fetch_player_game.__name__}")

    # Check what happens when we call it
    print("\n  2. Calling LeagueSourceConfig.fetch_player_game:")
    if src_cfg and src_cfg.fetch_player_game:
        try:
            df = src_cfg.fetch_player_game(season="2025-2026")
            print(f"     Returned: {len(df)} rows")
            print(f"     Is empty: {df.empty}")
        except Exception as e:
            print(f"     Error: {type(e).__name__}: {e}")
    else:
        print("     Not wired, would skip to hardcoded path")

    # Explain the fallback issue
    print("\n  3. Fallback behavior analysis:")
    print("     - LeagueSourceConfig returns empty DataFrame")
    print("     - Code logs warning and falls through to hardcoded paths")
    print("     - LNB_ELITE2 not in any elif branch")
    print("     - Reaches final 'else' clause")
    print("     - Raises 'Unsupported league for player_game'")


def debug_step_4_matrix_generator():
    """Step 4: Check how matrix generator determines availability"""
    print("\n" + "=" * 70)
    print("STEP 4: Matrix Generator Logic Analysis")
    print("=" * 70)

    # The matrix shows Y for box_sc (player_game), pbp, shots
    # But our API test shows X for player_game
    # Why the discrepancy?

    print("\n  Matrix generator checks:")
    print("    1. KNOWN_COVERAGE dictionary (static)")
    print("    2. LeagueSourceConfig wiring (not actual data)")
    print("    3. Presence of parquet files")

    # Check KNOWN_COVERAGE
    from tools.compute_coverage import KNOWN_COVERAGE

    leagues = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]
    print("\n  KNOWN_COVERAGE entries for LNB sub-leagues:")
    for league in leagues:
        entries = [k for k in KNOWN_COVERAGE.keys() if k[0] == league]
        if entries:
            print(f"    {league}: {len(entries)} entries")
            for k, v in KNOWN_COVERAGE.items():
                if k[0] == league:
                    print(f"      - {k[1]}: {v[0]} to {v[1]}")
        else:
            print(f"    {league}: NO ENTRIES")


def debug_step_5_identify_root_cause():
    """Step 5: Identify the root cause and propose solution"""
    print("\n" + "=" * 70)
    print("STEP 5: Root Cause Analysis")
    print("=" * 70)

    print("\n  PROBLEM:")
    print("    When LeagueSourceConfig.fetch_player_game returns an empty")
    print("    DataFrame, the code falls back to hardcoded league branches,")
    print("    but LNB sub-leagues are not in those branches.")

    print("\n  EXPECTED BEHAVIOR:")
    print("    If LeagueSourceConfig is wired and returns empty, that")
    print("    should be the final result (no data), not an error.")

    print("\n  ACTUAL BEHAVIOR:")
    print("    Empty result triggers fallback which then errors.")

    print("\n  ROOT CAUSE:")
    print("    In datasets.py _fetch_player_game(), lines 924-932:")
    print("    ```python")
    print("    if df is not None and not df.empty:")
    print("        # Apply post-mask filtering")
    print("        ...")
    print("        return df")
    print("    else:")
    print("        logger.warning('...falling back to hardcoded path')")
    print("    ```")
    print("    This should return the empty DataFrame, not fall back.")

    print("\n  SOLUTION:")
    print("    Modify the code to return the result from LeagueSourceConfig")
    print("    even if it's empty. The 'emptiness' is valid data (no games).")


def debug_step_6_check_normalized_data_exists():
    """Step 6: Check if normalized data files actually exist"""
    print("\n" + "=" * 70)
    print("STEP 6: Check if Normalized Data Files Exist")
    print("=" * 70)

    data_root = Path(__file__).parent.parent / "data"

    paths_to_check = [
        data_root / "normalized" / "lnb" / "player_game",
        data_root / "normalized" / "lnb" / "team_game",
        data_root / "lnb" / "historical" / "2025-2026",
    ]

    print("\n  Checking data directories:")
    for path in paths_to_check:
        exists = path.exists()
        print(f"    {path.relative_to(data_root)}: {'EXISTS' if exists else 'MISSING'}")
        if exists:
            parquet_files = list(path.glob("**/*.parquet"))
            print(f"      Parquet files: {len(parquet_files)}")
            for pf in parquet_files[:5]:
                print(f"        - {pf.name}")


def main():
    print("=" * 70)
    print("LNB SUB-LEAGUE DATASET DEBUG ANALYSIS")
    print("=" * 70)

    debug_step_1_wiring()
    debug_step_2_fetcher_returns()
    debug_step_3_api_fetch_player_game()
    debug_step_4_matrix_generator()
    debug_step_5_identify_root_cause()
    debug_step_6_check_normalized_data_exists()

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
