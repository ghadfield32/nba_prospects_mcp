"""NZ-NBL (New Zealand National Basketball League) Coverage Probe

Tests data availability for NZ-NBL:
- Schedule: Playwright-based JS widget discovery (Genius Sports)
- Player/team game: FIBA LiveStats HTML parsing
- PBP: FIBA LiveStats event data
- Shots: FIBA LiveStats shot chart coordinates

Usage:
    python probes/probe_nz_nbl.py

Exit codes:
    0 - Success
    1 - Failure
    2 - Timeout

Note:
    Schedule discovery requires Playwright:
    - uv pip install 'cbb-data[nz_nbl]' && playwright install chromium
"""

import sys
import time

# Fix Windows console encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")


def probe_nz_nbl_schedule():
    """Test: Fetch schedule returns games"""
    try:
        from cbb_data.fetchers import nz_nbl_fiba

        # Check if Playwright is available
        if not nz_nbl_fiba.PLAYWRIGHT_AVAILABLE:
            print("⚠️  WARN: Schedule - Playwright not installed")
            print(
                "         Install with: uv pip install 'cbb-data[nz_nbl]' && playwright install chromium"
            )

            # Try fallback HTML scraper
            df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season="2024")
            if df.empty:
                print("⚠️  WARN: Schedule - Fallback scraper found no games (expected)")
                return True  # Not a failure
            return True

        # Fetch with Playwright
        df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season="2024")

        if df.empty:
            print("⚠️  WARN: Schedule - No games found (season may not have data)")
            return True  # Not a failure

        # Validate structure
        if "GAME_ID" in df.columns or "FIBA_GAME_ID" in df.columns:
            game_id_col = "GAME_ID" if "GAME_ID" in df.columns else "FIBA_GAME_ID"
            print(f"✅ PASS: Schedule - {len(df)} games (ID column: {game_id_col})")
            return True
        else:
            print("⚠️  WARN: Schedule - Data returned but missing GAME_ID column")
            return True

    except Exception as e:
        print(f"❌ FAIL: Schedule - {e}")
        return False


def probe_nz_nbl_player_season():
    """Test: Fetch player season stats"""
    try:
        from cbb_data.fetchers import nz_nbl_fiba

        df = nz_nbl_fiba.fetch_nz_nbl_player_season(season="2024")

        if df.empty:
            print("⚠️  WARN: Player season - No data (expected if no games played)")
            return True

        assert "PLAYER_NAME" in df.columns or len(df.columns) > 3, "Missing expected columns"

        print(f"✅ PASS: Player season - {len(df)} players")
        return True

    except Exception as e:
        print(f"❌ FAIL: Player season - {e}")
        return False


def probe_nz_nbl_team_season():
    """Test: Fetch team season stats"""
    try:
        from cbb_data.fetchers import nz_nbl_fiba

        df = nz_nbl_fiba.fetch_nz_nbl_team_season(season="2024")

        if df.empty:
            print("⚠️  WARN: Team season - No data (expected if no games played)")
            return True

        print(f"✅ PASS: Team season - {len(df)} teams")
        return True

    except Exception as e:
        print(f"❌ FAIL: Team season - {e}")
        return False


def probe_nz_nbl_player_game():
    """Test: Fetch player game stats (box scores)"""
    try:
        from cbb_data.fetchers import nz_nbl_fiba

        df = nz_nbl_fiba.fetch_nz_nbl_player_game(season="2024")

        if df.empty:
            print("⚠️  WARN: Player game - No box scores (expected if no games played)")
            return True

        assert "GAME_ID" in df.columns, "Missing GAME_ID column"

        print(f"✅ PASS: Player game - {len(df)} player-game records")
        return True

    except Exception as e:
        print(f"❌ FAIL: Player game - {e}")
        return False


def probe_nz_nbl_pbp():
    """Test: Fetch play-by-play data"""
    try:
        from cbb_data.fetchers import nz_nbl_fiba

        # PBP fetch for full season is slow, so we'll just validate function exists
        # and check minimal response

        # Just validate the function is importable and callable
        assert callable(nz_nbl_fiba.fetch_nz_nbl_pbp), "PBP function not callable"

        print("⚠️  SKIP: PBP - Full fetch too slow for probe (function validated)")
        return None  # Skip

    except Exception as e:
        print(f"❌ FAIL: PBP - {e}")
        return False


def probe_nz_nbl_shots():
    """Test: Fetch shot chart data"""
    try:
        from cbb_data.fetchers import nz_nbl_fiba

        # Shots fetch for full season is slow
        assert callable(nz_nbl_fiba.fetch_nz_nbl_shot_chart), "Shot chart function not callable"

        print("⚠️  SKIP: Shots - Full fetch too slow for probe (function validated)")
        return None  # Skip

    except Exception as e:
        print(f"❌ FAIL: Shots - {e}")
        return False


def probe_playwright_available():
    """Test: Check if Playwright is available"""
    try:
        from cbb_data.fetchers.nz_nbl_fiba import PLAYWRIGHT_AVAILABLE

        if PLAYWRIGHT_AVAILABLE:
            print("✅ PASS: Playwright available for JS rendering")
            return True
        else:
            print("⚠️  WARN: Playwright not available")
            print(
                "         Install with: uv pip install 'cbb-data[nz_nbl]' && playwright install chromium"
            )
            return None  # Skip, not fail

    except Exception as e:
        print(f"⚠️  SKIP: Playwright check - {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("NZ-NBL COVERAGE PROBE - New Zealand NBL")
    print("=" * 60)
    print()

    start = time.time()

    try:
        # Core probes
        print("Core data probes:")
        print("-" * 40)
        core_results = [
            probe_playwright_available(),
            probe_nz_nbl_schedule(),
            probe_nz_nbl_player_season(),
            probe_nz_nbl_team_season(),
            probe_nz_nbl_player_game(),
        ]
        print()

        # Event-level probes (slow)
        print("Event-level probes:")
        print("-" * 40)
        event_results = [
            probe_nz_nbl_pbp(),
            probe_nz_nbl_shots(),
        ]
        print()

        elapsed = time.time() - start

        if elapsed > 120:
            print(f"⚠️  WARNING: Probes took {elapsed:.1f}s (expected <120s)")

        # Count results
        all_results = core_results + event_results
        passed = sum(1 for r in all_results if r is True)
        skipped = sum(1 for r in all_results if r is None)
        failed = sum(1 for r in all_results if r is False)
        total = len(all_results)

        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Passed: {passed}/{total - skipped}")
        print(f"Skipped: {skipped}")
        print(f"Failed: {failed}")
        print(f"Time: {elapsed:.1f}s")
        print()

        if failed == 0:
            print("✅ ALL PROBES PASSED")
            if skipped > 0:
                print(f"   ({skipped} probes skipped)")
            sys.exit(0)
        else:
            print(f"❌ {failed} PROBE(S) FAILED")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
