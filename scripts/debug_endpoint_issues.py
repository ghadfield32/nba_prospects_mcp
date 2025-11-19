#!/usr/bin/env python
"""Debug script for endpoint test issues

Investigates root causes of skipped tests and errors systematically.

Run with: python scripts/debug_endpoint_issues.py
"""

import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, "src")


import pandas as pd


def debug_acb_schedule():
    """Debug ACB schedule issues - probe shows Err but tests pass"""
    print("=" * 70)
    print("DEBUG: ACB Schedule Issues")
    print("=" * 70)

    from cbb_data.fetchers import acb

    # Issue 1: Check what fetch_acb_schedule returns
    print("\n1. Testing fetch_acb_schedule('2024')...")
    try:
        df = acb.fetch_acb_schedule(season="2024")
        print(f"   Result: {len(df)} rows")
        print(f"   Columns: {list(df.columns)}")
        if not df.empty:
            print(f"   Sample data:\n{df.head(2)}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")

    # Issue 2: Check what the probe script is using
    # The probe uses acb.fetch_acb_game_index which doesn't exist!
    print("\n2. Checking if fetch_acb_game_index exists...")
    if hasattr(acb, "fetch_acb_game_index"):
        print("   fetch_acb_game_index: EXISTS")
    else:
        print("   fetch_acb_game_index: DOES NOT EXIST")
        print("   NOTE: The probe script uses this but it doesn't exist!")
        print("   Available ACB functions:")
        acb_funcs = [f for f in dir(acb) if f.startswith("fetch_acb")]
        for func in acb_funcs:
            print(f"     - {func}")

    # Issue 3: Check first game for PBP/shots availability
    print("\n3. Testing PBP/shots for first game...")
    try:
        df = acb.fetch_acb_schedule(season="2024")
        if not df.empty:
            # Find game ID column
            game_id_col = None
            for col in ["GAME_ID", "game_id", "game_code", "id"]:
                if col in df.columns:
                    game_id_col = col
                    break

            if game_id_col:
                game_id = str(df[game_id_col].iloc[0])
                print(f"   First game ID: {game_id} (column: {game_id_col})")

                # Test PBP
                print(f"   Testing fetch_acb_play_by_play('{game_id}')...")
                try:
                    pbp = acb.fetch_acb_play_by_play(game_id)
                    print(f"     PBP result: {len(pbp)} events")
                except Exception as e:
                    print(f"     PBP ERROR: {e}")

                # Test shots
                print(f"   Testing fetch_acb_shot_chart('{game_id}')...")
                try:
                    shots = acb.fetch_acb_shot_chart(game_id)
                    print(f"     Shots result: {len(shots)} shots")
                except Exception as e:
                    print(f"     Shots ERROR: {e}")
            else:
                print(f"   No game ID column found in: {list(df.columns)}")
        else:
            print("   Schedule is empty")
    except Exception as e:
        print(f"   ERROR: {e}")


def debug_lnb_schedule():
    """Debug LNB schedule - tests skip because 'No game ID column found'"""
    print("\n" + "=" * 70)
    print("DEBUG: LNB Schedule Issues")
    print("=" * 70)

    from cbb_data.fetchers import lnb

    print("\n1. Testing fetch_lnb_schedule('2024')...")
    try:
        df = lnb.fetch_lnb_schedule(season="2024")
        print(f"   Result: {len(df)} rows")
        print(f"   Columns: {list(df.columns)}")

        # Check which columns exist
        id_cols = ["game_id", "fixture_uuid", "external_id", "GAME_ID", "id"]
        found = [col for col in id_cols if col in df.columns]
        print(f"\n   Looking for game ID columns: {id_cols}")
        print(f"   Found: {found if found else 'NONE!'}")

        if not df.empty:
            print(f"\n   First 2 rows:\n{df.head(2)}")
            print("\n   All columns and dtypes:")
            for col in df.columns:
                print(f"     {col}: {df[col].dtype}")

        # Root cause: Tests look for game_id, fixture_uuid, external_id
        # but the actual column name might be different
        if not found:
            print("\n   ROOT CAUSE IDENTIFIED:")
            print("   The test looks for columns: game_id, fixture_uuid, external_id, id")
            print("   But LNB schedule has different column names!")
            print("   Need to update test to use actual column name.")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


def debug_nz_nbl_issues():
    """Debug NZ-NBL 403 errors and empty schedule"""
    print("\n" + "=" * 70)
    print("DEBUG: NZ-NBL Issues")
    print("=" * 70)

    from cbb_data.fetchers import nz_nbl_fiba

    # Issue 1: Check schedule discovery
    print("\n1. Testing schedule discovery for 2024...")
    try:
        df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season="2024")
        print(f"   Result: {len(df)} games")
        if not df.empty:
            print(f"   Columns: {list(df.columns)}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Issue 2: Check local game index
    print("\n2. Checking local game index...")
    try:
        # Try to load from local parquet
        import os

        index_path = "data/raw/nz_nbl/nz_nbl_game_index.parquet"
        if os.path.exists(index_path):
            df = pd.read_parquet(index_path)
            print(f"   Local index exists: {len(df)} games")
            print(f"   Seasons: {df['season'].unique() if 'season' in df.columns else 'N/A'}")
        else:
            print(f"   Local index NOT found at: {index_path}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Issue 3: Test direct FIBA LiveStats URL
    print("\n3. Testing direct FIBA LiveStats access...")
    import requests

    test_urls = [
        "https://fibalivestats.dcd.shared.geniussports.com/u/NZN/301234/bs.html",
        "https://fibalivestats.dcd.shared.geniussports.com/u/NZN/1/bs.html",  # Try game 1
    ]

    for url in test_urls:
        print(f"   Testing: {url}")
        try:
            resp = requests.get(url, timeout=10)
            print(f"     Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"     Content length: {len(resp.text)}")
        except Exception as e:
            print(f"     ERROR: {e}")

    # Issue 4: Check Playwright availability
    print("\n4. Checking Playwright status...")
    print(f"   PLAYWRIGHT_AVAILABLE: {nz_nbl_fiba.PLAYWRIGHT_AVAILABLE}")

    if nz_nbl_fiba.PLAYWRIGHT_AVAILABLE:
        print("   Playwright is available but finding 0 games")
        print("   Possible causes:")
        print("   - Season 2024 hasn't started (NZ-NBL typically runs May-August)")
        print("   - Website structure changed")
        print("   - JavaScript rendering issue")


def debug_probe_script():
    """Debug the probe script specifically"""
    print("\n" + "=" * 70)
    print("DEBUG: Probe Script Function Calls")
    print("=" * 70)

    # The probe script probe_historical_coverage.py has a bug
    # It calls acb.fetch_acb_game_index which doesn't exist
    # Let me check the probe script

    print("\n1. Checking probe_historical_coverage.py...")

    try:
        with open("scripts/probe_historical_coverage.py") as f:
            content = f.read()

        # Check what ACB functions it calls
        if "fetch_acb_game_index" in content:
            print("   BUG FOUND: Script uses 'fetch_acb_game_index' which doesn't exist!")
            print("   Should use 'fetch_acb_schedule' instead")

        if "fetch_acb_player_game" in content:
            print("   BUG FOUND: Script uses 'fetch_acb_player_game' which doesn't exist!")
            print("   ACB uses per-game fetching: fetch_acb_box_score(game_id)")

        if "fetch_acb_team_game" in content:
            print("   BUG FOUND: Script uses 'fetch_acb_team_game' which doesn't exist!")

    except Exception as e:
        print(f"   ERROR reading probe script: {e}")


if __name__ == "__main__":
    print("ENDPOINT DEBUG ANALYSIS")
    print("=" * 70)
    print()

    debug_acb_schedule()
    debug_lnb_schedule()
    debug_nz_nbl_issues()
    debug_probe_script()

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Fix probe_historical_coverage.py to use correct function names")
    print("2. Update LNB tests to use actual column names from schedule")
    print("3. Investigate NZ-NBL 403 errors (may need different game IDs)")
    print("4. Check if ACB game 104459 is actually played and has data")
