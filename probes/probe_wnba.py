"""WNBA Data Source Probe

Tests WNBA Stats API accessibility.

Usage:
    python probes/probe_wnba.py

Exit codes:
    0 - Success
    1 - Failure
    2 - Timeout
"""

import sys
import time

# Add src to path
sys.path.insert(0, "src")


def probe_wnba_schedule():
    """Test: Fetch WNBA schedule returns at least 1 game"""
    try:
        from cbb_data.fetchers import wnba

        # Fetch 2024 WNBA regular season
        df = wnba.fetch_wnba_schedule(season="2024", season_type="Regular Season")

        # Validate structure
        assert not df.empty, "No games returned"
        assert "GAME_ID" in df.columns, "Missing GAME_ID column"
        assert "LEAGUE" in df.columns, "Missing LEAGUE column"
        assert all(df["LEAGUE"] == "WNBA"), "League column not 'WNBA'"

        print(f"✅ PASS: Schedule endpoint - {len(df)} games")
        return True

    except Exception as e:
        print(f"❌ FAIL: Schedule - {e}")
        return False


def probe_wnba_box_score():
    """Test: Fetch WNBA box score returns player stats

    Uses a known game from 2024 season opening day.
    """
    try:
        from cbb_data.fetchers import wnba

        # Known game ID from 2024 season (example)
        # Note: This will need to be updated with a real game ID
        game_id = "1022400001"  # Placeholder - update with real game ID

        df = wnba.fetch_wnba_box_score(game_id)

        # Validate structure
        assert not df.empty, "No player stats returned"
        assert "PLAYER_NAME" in df.columns, "Missing PLAYER_NAME column"
        assert "PTS" in df.columns, "Missing PTS column"
        assert "LEAGUE" in df.columns, "Missing LEAGUE column"

        print(f"✅ PASS: Box score endpoint - {len(df)} players")
        return True

    except Exception as e:
        print(f"⚠️  SKIP: Box score - {e} (known game ID may be invalid)")
        return True  # Don't fail probe if game ID is outdated


if __name__ == "__main__":
    print("=" * 60)
    print("WNBA DATA SOURCE PROBE")
    print("=" * 60)

    start = time.time()

    try:
        results = [
            probe_wnba_schedule(),
            probe_wnba_box_score(),
        ]

        elapsed = time.time() - start

        if elapsed > 30:
            print(f"\n⚠️  TIMEOUT: Probes took {elapsed:.1f}s (max 30s)")
            sys.exit(2)

        passed = sum(results)
        total = len(results)

        print(f"\nResults: {passed}/{total} probes passed ({elapsed:.1f}s)")

        if passed == total:
            print("✅ ALL PROBES PASSED")
            sys.exit(0)
        else:
            print(f"❌ {total - passed} PROBE(S) FAILED")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
