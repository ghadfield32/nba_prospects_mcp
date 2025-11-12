"""Probe Template

Copy this file to create new probes for data sources.

Usage:
    python probes/probe_<league>.py

Exit codes:
    0 - Success
    1 - Failure
    2 - Timeout
"""

import sys
import time

# Add src to path
sys.path.insert(0, "src")


def probe_league_schedule():
    """Test: Fetch schedule returns at least 1 game"""
    try:
        # TODO: Import fetcher
        # from cbb_data.fetchers import <module>

        # TODO: Make single API call with known-good parameters
        # df = <module>.fetch_<league>_schedule(season="2024")

        # Validate structure
        # assert not df.empty, "No games returned"
        # assert "GAME_ID" in df.columns, "Missing GAME_ID column"
        # assert "LEAGUE" in df.columns, "Missing LEAGUE column"

        print("✅ PASS: Schedule endpoint accessible")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False


def probe_league_box_score():
    """Test: Fetch box score returns player stats"""
    try:
        # TODO: Import fetcher
        # from cbb_data.fetchers import <module>

        # TODO: Use known game ID
        # game_id = "KNOWN_GAME_ID"
        # df = <module>.fetch_<league>_box_score(game_id)

        # Validate structure
        # assert not df.empty, "No player stats returned"
        # assert "PLAYER_NAME" in df.columns, "Missing PLAYER_NAME column"
        # assert "PTS" in df.columns, "Missing PTS column"

        print("✅ PASS: Box score endpoint accessible")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("LEAGUE PROBE - <League Name>")
    print("=" * 60)

    start = time.time()

    try:
        results = [
            probe_league_schedule(),
            probe_league_box_score(),
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
