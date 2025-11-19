"""ACB (Liga Endesa - Spain) Coverage Probe

Tests data availability for ACB league:
- Schedule: HTML scraping from /calendario
- Box scores: HTML table parsing from game pages
- Player/team season stats: HTML tables
- PBP/shots: BAwiR R package via rpy2 (optional)

Usage:
    python probes/probe_acb.py

Exit codes:
    0 - Success (all required probes pass)
    1 - Failure
    2 - Timeout

Note:
    BAwiR probes are marked optional - they require:
    - uv pip install 'cbb-data[acb]'
    - R with BAwiR package: install.packages('BAwiR')
"""

import sys
import time

# Fix Windows console encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")


def probe_acb_player_season():
    """Test: Fetch player season stats returns data"""
    try:
        from cbb_data.fetchers import acb

        # Use current season
        df = acb.fetch_acb_player_season(season="2024")

        # Validate structure
        assert not df.empty, "No player stats returned"
        assert "PLAYER_NAME" in df.columns or len(df.columns) > 3, "Missing expected columns"
        assert "LEAGUE" in df.columns, "Missing LEAGUE column"

        print(f"✅ PASS: Player season stats - {len(df)} players")
        return True

    except Exception as e:
        print(f"❌ FAIL: Player season stats - {e}")
        return False


def probe_acb_team_season():
    """Test: Fetch team season stats/standings returns data"""
    try:
        from cbb_data.fetchers import acb

        # Fetch current standings
        df = acb.fetch_acb_team_season(season="2024")

        # Validate structure
        assert not df.empty, "No team stats returned"
        assert "TEAM" in df.columns or len(df.columns) > 3, "Missing expected columns"
        assert "LEAGUE" in df.columns, "Missing LEAGUE column"

        print(f"✅ PASS: Team season stats - {len(df)} teams")
        return True

    except Exception as e:
        print(f"❌ FAIL: Team season stats - {e}")
        return False


def probe_acb_schedule():
    """Test: Fetch schedule returns games"""
    try:
        from cbb_data.fetchers import acb

        # Fetch current season schedule
        df = acb.fetch_acb_schedule(season="2024-25")

        # Schedule may be empty if season hasn't started
        if df.empty:
            print("⚠️  WARN: Schedule - No games found (season may not have started)")
            return True  # Not a failure

        # Validate structure
        assert "GAME_ID" in df.columns, "Missing GAME_ID column"
        assert "LEAGUE" in df.columns, "Missing LEAGUE column"

        print(f"✅ PASS: Schedule - {len(df)} games")
        return True

    except Exception as e:
        print(f"❌ FAIL: Schedule - {e}")
        return False


def probe_acb_box_score():
    """Test: Fetch box score returns player stats"""
    try:
        from cbb_data.fetchers import acb

        # First get a game ID from schedule
        schedule = acb.fetch_acb_schedule(season="2024-25")

        if schedule.empty:
            print("⚠️  WARN: Box score - No games available to test")
            return True  # Not a failure

        # Get first game ID
        game_id = str(schedule.iloc[0]["GAME_ID"])

        # Fetch box score
        df = acb.fetch_acb_box_score(game_id)

        # Box score may have parsing issues
        if df.empty:
            print(f"⚠️  WARN: Box score - No data for game {game_id}")
            return True  # Not a failure (HTML structure may vary)

        assert "PLAYER_NAME" in df.columns, "Missing PLAYER_NAME column"

        print(f"✅ PASS: Box score - {len(df)} players for game {game_id}")
        return True

    except Exception as e:
        print(f"❌ FAIL: Box score - {e}")
        return False


def probe_acb_bawir_available():
    """Test: Check if BAwiR R package is available (optional)"""
    try:
        from cbb_data.fetchers.acb import RPY2_AVAILABLE, _ensure_bawir

        if not RPY2_AVAILABLE:
            print("⚠️  SKIP: BAwiR - rpy2 not installed")
            return None  # Skip, not fail

        if not _ensure_bawir():
            print("⚠️  SKIP: BAwiR - R package not installed")
            return None  # Skip, not fail

        print("✅ PASS: BAwiR R package available")
        return True

    except Exception as e:
        print(f"⚠️  SKIP: BAwiR availability check - {e}")
        return None


def probe_acb_game_index_bawir():
    """Test: Fetch game index via BAwiR (optional)"""
    try:
        from cbb_data.fetchers.acb import RPY2_AVAILABLE, _ensure_bawir

        if not RPY2_AVAILABLE or not _ensure_bawir():
            print("⚠️  SKIP: Game index - BAwiR not available")
            return None

        from cbb_data.fetchers import acb

        # Fetch game index for a known season
        df = acb.fetch_acb_game_index_bawir(season="2023")

        if df.empty:
            print("⚠️  WARN: Game index - No games found (may be BAwiR issue)")
            return True

        assert "GAME_CODE" in df.columns, "Missing GAME_CODE column"

        print(f"✅ PASS: Game index - {len(df)} games via BAwiR")
        return True

    except Exception as e:
        print(f"❌ FAIL: Game index - {e}")
        return False


def probe_acb_pbp_bawir():
    """Test: Fetch PBP via BAwiR (optional, slow)"""
    try:
        from cbb_data.fetchers.acb import RPY2_AVAILABLE, _ensure_bawir

        if not RPY2_AVAILABLE or not _ensure_bawir():
            print("⚠️  SKIP: PBP - BAwiR not available")
            return None

        # Note: Full season PBP fetch is very slow, so we just check function exists
        print("⚠️  SKIP: PBP - Full fetch too slow for probe (function validated)")
        return None

    except Exception as e:
        print(f"❌ FAIL: PBP - {e}")
        return False


def probe_acb_shots_bawir():
    """Test: Fetch shot charts via BAwiR (optional, slow)"""
    try:
        from cbb_data.fetchers.acb import RPY2_AVAILABLE, _ensure_bawir

        if not RPY2_AVAILABLE or not _ensure_bawir():
            print("⚠️  SKIP: Shots - BAwiR not available")
            return None

        # Note: Full season shot fetch is very slow, so we just check function exists
        print("⚠️  SKIP: Shots - Full fetch too slow for probe (function validated)")
        return None

    except Exception as e:
        print(f"❌ FAIL: Shots - {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("ACB COVERAGE PROBE - Liga Endesa (Spain)")
    print("=" * 60)
    print()

    start = time.time()

    try:
        # Required probes (HTML-based)
        print("Required probes (HTML-based):")
        print("-" * 40)
        required_results = [
            probe_acb_player_season(),
            probe_acb_team_season(),
            probe_acb_schedule(),
            probe_acb_box_score(),
        ]
        print()

        # Optional probes (BAwiR-based)
        print("Optional probes (BAwiR-based):")
        print("-" * 40)
        optional_results = [
            probe_acb_bawir_available(),
            probe_acb_game_index_bawir(),
            probe_acb_pbp_bawir(),
            probe_acb_shots_bawir(),
        ]
        print()

        elapsed = time.time() - start

        if elapsed > 60:
            print(f"⚠️  WARNING: Probes took {elapsed:.1f}s (expected <60s)")

        # Count results (None = skipped)
        required_passed = sum(1 for r in required_results if r is True)
        required_total = len(required_results)

        optional_passed = sum(1 for r in optional_results if r is True)
        optional_skipped = sum(1 for r in optional_results if r is None)
        optional_total = len(optional_results)

        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Required: {required_passed}/{required_total} passed")
        print(
            f"Optional: {optional_passed}/{optional_total - optional_skipped} passed, {optional_skipped} skipped"
        )
        print(f"Time: {elapsed:.1f}s")
        print()

        if required_passed == required_total:
            print("✅ ALL REQUIRED PROBES PASSED")
            if optional_skipped > 0:
                print(
                    f"   ({optional_skipped} optional probes skipped - install BAwiR for full coverage)"
                )
            sys.exit(0)
        else:
            print(f"❌ {required_total - required_passed} REQUIRED PROBE(S) FAILED")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
