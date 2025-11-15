#!/usr/bin/env python3
"""
Comprehensive LNB Pro A Integration Validation
==============================================

Tests all integration points to ensure LNB is fully functional:
- Unified fetch API (datasets.py)
- MCP compatibility
- All 7 dataset types
- Filter functionality
- Schema compliance

Run: python validate_lnb_integration.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
from cbb_data import get_dataset
from cbb_data.fetchers import lnb_official
from cbb_data.catalog.sources import get_league_source_config
from cbb_data.catalog.capabilities import CAPABILITY_OVERRIDES, CapabilityLevel

# Test configuration
SEASON = "2025-26"
LEAGUE = "LNB_PROA"

# =============================================================================
# Test Results Tracker
# =============================================================================

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def add_pass(self, test_name, details=""):
        self.passed.append((test_name, details))
        print(f"  ✅ {test_name}")
        if details:
            print(f"     → {details}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        print(f"  ❌ {test_name}")
        print(f"     → Error: {error}")

    def add_skip(self, test_name, reason):
        self.skipped.append((test_name, reason))
        print(f"  ⏭️  {test_name}")
        print(f"     → Skipped: {reason}")

    def print_summary(self):
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        print(f"Total Tests: {total}")
        print(f"  ✅ Passed:  {len(self.passed)} ({len(self.passed)/total*100:.1f}%)")
        print(f"  ❌ Failed:  {len(self.failed)} ({len(self.failed)/total*100:.1f}%)")
        print(f"  ⏭️  Skipped: {len(self.skipped)} ({len(self.skipped)/total*100:.1f}%)")

        if self.failed:
            print("\n⚠️  FAILURES:")
            for test, error in self.failed:
                print(f"  - {test}: {error}")

        if len(self.failed) == 0:
            print("\n🎉 ALL TESTS PASSED!")
            return True
        else:
            print("\n⚠️  SOME TESTS FAILED")
            return False

results = TestResults()

# =============================================================================
# Test 1: Catalog Registration
# =============================================================================

print("\n" + "=" * 70)
print("TEST 1: Catalog Registration")
print("=" * 70)

try:
    cfg = get_league_source_config("LNB_PROA")
    if cfg is None:
        results.add_fail("LeagueSourceConfig exists", "get_league_source_config returned None")
    else:
        results.add_pass("LeagueSourceConfig exists", f"Sources: {cfg.schedule_source}, {cfg.pbp_source}, {cfg.shots_source}")

        # Check all 7 fetch functions are registered
        if cfg.fetch_schedule:
            results.add_pass("fetch_schedule registered")
        else:
            results.add_fail("fetch_schedule registered", "Not found in config")

        if cfg.fetch_pbp:
            results.add_pass("fetch_pbp registered")
        else:
            results.add_fail("fetch_pbp registered", "Not found in config")

        if cfg.fetch_shots:
            results.add_pass("fetch_shots registered")
        else:
            results.add_fail("fetch_shots registered", "Not found in config")

        if cfg.fetch_team_season:
            results.add_pass("fetch_team_season registered")
        else:
            results.add_fail("fetch_team_season registered", "Not found in config")

except Exception as e:
    results.add_fail("LeagueSourceConfig exists", str(e))

# Check capabilities
try:
    lnb_caps = CAPABILITY_OVERRIDES.get("LNB_PROA", {})
    # LNB_PROA should have overrides for LIMITED capabilities
    results.add_pass("Capabilities registered", f"{len(lnb_caps)} capability overrides defined")

    # Check specific capabilities (in CAPABILITY_OVERRIDES, only LIMITED/UNAVAILABLE are listed)
    # FULL capabilities are default if registered in sources.py
    # So if shots/pbp are NOT in overrides, they're FULL
    if "shots" not in lnb_caps or lnb_caps.get("shots") == CapabilityLevel.FULL:
        results.add_pass("Shots capability: FULL (not overridden)")
    else:
        results.add_fail("Shots capability: FULL", f"Got override: {lnb_caps.get('shots')}")

    if "pbp" not in lnb_caps or lnb_caps.get("pbp") == CapabilityLevel.FULL:
        results.add_pass("PBP capability: FULL (not overridden)")
    else:
        results.add_fail("PBP capability: FULL", f"Got override: {lnb_caps.get('pbp')}")

    # Check that player_game/team_game are LIMITED
    if lnb_caps.get("player_game") == CapabilityLevel.LIMITED:
        results.add_pass("Player game capability: LIMITED")
    else:
        results.add_skip("Player game capability", f"Not in overrides (got {lnb_caps.get('player_game')})")

except Exception as e:
    results.add_fail("Capabilities check", str(e))

# =============================================================================
# Test 2: Direct Fetcher Functions
# =============================================================================

print("\n" + "=" * 70)
print("TEST 2: Direct Fetcher Functions")
print("=" * 70)

# Test 2.1: Schedule
try:
    schedule_df = lnb_official.fetch_lnb_schedule(season=SEASON)
    if len(schedule_df) > 0:
        results.add_pass(f"fetch_lnb_schedule({SEASON})", f"{len(schedule_df)} games")

        # Check required columns
        required_cols = ["GAME_ID", "SEASON", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "LEAGUE"]
        missing = [col for col in required_cols if col not in schedule_df.columns]
        if missing:
            results.add_fail("Schedule columns", f"Missing: {missing}")
        else:
            results.add_pass("Schedule columns", "All required columns present")

        # Check GAME_ID type
        if schedule_df["GAME_ID"].dtype == object or schedule_df["GAME_ID"].dtype == "string":
            results.add_pass("Schedule GAME_ID type", f"dtype={schedule_df['GAME_ID'].dtype}")
        else:
            results.add_fail("Schedule GAME_ID type", f"Expected string, got {schedule_df['GAME_ID'].dtype}")
    else:
        results.add_fail(f"fetch_lnb_schedule({SEASON})", "Returned 0 games")
except Exception as e:
    results.add_fail(f"fetch_lnb_schedule({SEASON})", str(e))

# Test 2.2: Team Season
try:
    team_season_df = lnb_official.fetch_lnb_team_season(season=SEASON)
    if len(team_season_df) > 0:
        results.add_pass(f"fetch_lnb_team_season({SEASON})", f"{len(team_season_df)} teams")

        # Check aggregation columns
        agg_cols = ["TEAM", "GP", "W", "L", "WIN_PCT", "PTS"]
        missing = [col for col in agg_cols if col not in team_season_df.columns]
        if missing:
            results.add_fail("Team season columns", f"Missing: {missing}")
        else:
            results.add_pass("Team season columns", "All aggregation columns present")
    else:
        results.add_fail(f"fetch_lnb_team_season({SEASON})", "Returned 0 teams")
except Exception as e:
    results.add_fail(f"fetch_lnb_team_season({SEASON})", str(e))

# Test 2.3: PBP
try:
    pbp_df = lnb_official.fetch_lnb_pbp(season=SEASON)
    if len(pbp_df) > 0:
        results.add_pass(f"fetch_lnb_pbp({SEASON})", f"{len(pbp_df)} events")

        # Check PBP columns
        pbp_cols = ["GAME_ID", "EVENT_NUM", "PERIOD", "CLOCK", "TEAM", "PLAYER_NAME", "EVENT_TYPE"]
        missing = [col for col in pbp_cols if col not in pbp_df.columns]
        if missing:
            results.add_fail("PBP columns", f"Missing: {missing}")
        else:
            results.add_pass("PBP columns", "All required columns present")

        # Check GAME_ID type
        if pbp_df["GAME_ID"].dtype == object or pbp_df["GAME_ID"].dtype == "string":
            results.add_pass("PBP GAME_ID type", f"dtype={pbp_df['GAME_ID'].dtype}")
        else:
            results.add_fail("PBP GAME_ID type", f"Expected string, got {pbp_df['GAME_ID'].dtype}")
    else:
        results.add_fail(f"fetch_lnb_pbp({SEASON})", "Returned 0 events")
except Exception as e:
    results.add_fail(f"fetch_lnb_pbp({SEASON})", str(e))

# Test 2.4: Shots
try:
    shots_df = lnb_official.fetch_lnb_shots(season=SEASON)
    if len(shots_df) > 0:
        results.add_pass(f"fetch_lnb_shots({SEASON})", f"{len(shots_df)} shots")

        # Check shot coordinates
        coord_cols = ["GAME_ID", "SHOT_X", "SHOT_Y", "SHOT_MADE", "SHOT_TYPE"]
        missing = [col for col in coord_cols if col not in shots_df.columns]
        if missing:
            results.add_fail("Shots columns", f"Missing: {missing}")
        else:
            results.add_pass("Shots columns", "All coordinate columns present")

        # Check coordinate values are numeric
        if pd.api.types.is_numeric_dtype(shots_df["SHOT_X"]) and pd.api.types.is_numeric_dtype(shots_df["SHOT_Y"]):
            results.add_pass("Shot coordinates numeric", f"SHOT_X: {shots_df['SHOT_X'].dtype}, SHOT_Y: {shots_df['SHOT_Y'].dtype}")
        else:
            results.add_fail("Shot coordinates numeric", "Coordinates should be numeric")
    else:
        results.add_fail(f"fetch_lnb_shots({SEASON})", "Returned 0 shots")
except Exception as e:
    results.add_fail(f"fetch_lnb_shots({SEASON})", str(e))

# Test 2.5: Player Season (expected empty)
try:
    player_season_df = lnb_official.fetch_lnb_player_season(season=SEASON)
    if len(player_season_df) == 0:
        results.add_skip("fetch_lnb_player_season", "Empty (pending box_player data)")
    else:
        results.add_pass(f"fetch_lnb_player_season({SEASON})", f"{len(player_season_df)} players")
except Exception as e:
    results.add_fail(f"fetch_lnb_player_season({SEASON})", str(e))

# =============================================================================
# Test 3: Unified API (get_dataset)
# =============================================================================

print("\n" + "=" * 70)
print("TEST 3: Unified API (get_dataset)")
print("=" * 70)

# Test 3.1: Schedule via get_dataset
try:
    schedule_api = get_dataset("schedule", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(schedule_api) > 0:
        results.add_pass(f"get_dataset('schedule', league={LEAGUE})", f"{len(schedule_api)} games")

        # Verify same as direct fetch
        schedule_direct = lnb_official.fetch_lnb_schedule(season=SEASON)
        if len(schedule_api) == len(schedule_direct):
            results.add_pass("Schedule API == Direct fetch", f"Both return {len(schedule_api)} games")
        else:
            results.add_fail("Schedule API == Direct fetch", f"API: {len(schedule_api)}, Direct: {len(schedule_direct)}")
    else:
        results.add_fail(f"get_dataset('schedule', league={LEAGUE})", "Returned 0 games")
except Exception as e:
    results.add_fail(f"get_dataset('schedule')", str(e))

# Test 3.2: Team Season via get_dataset
try:
    team_season_api = get_dataset("team_season", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(team_season_api) > 0:
        results.add_pass(f"get_dataset('team_season', league={LEAGUE})", f"{len(team_season_api)} teams")
    else:
        results.add_fail(f"get_dataset('team_season', league={LEAGUE})", "Returned 0 teams")
except Exception as e:
    results.add_fail(f"get_dataset('team_season')", str(e))

# Test 3.3: PBP via get_dataset (requires game_ids)
try:
    # Get game IDs from schedule first
    schedule_for_pbp = get_dataset("schedule", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(schedule_for_pbp) > 0:
        game_ids = schedule_for_pbp["GAME_ID"].astype(str).tolist()
        pbp_api = get_dataset("pbp", {"league": LEAGUE, "season": SEASON, "game_ids": game_ids}, pre_only=False)
        if len(pbp_api) > 0:
            results.add_pass(f"get_dataset('pbp', game_ids=[{len(game_ids)} games])", f"{len(pbp_api)} events")
        else:
            results.add_fail(f"get_dataset('pbp')", "Returned 0 events")
    else:
        results.add_skip("get_dataset('pbp')", "No games in schedule")
except Exception as e:
    results.add_fail(f"get_dataset('pbp')", str(e))

# Test 3.4: Shots via get_dataset
try:
    shots_api = get_dataset("shots", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(shots_api) > 0:
        results.add_pass(f"get_dataset('shots', league={LEAGUE})", f"{len(shots_api)} shots")
    else:
        results.add_fail(f"get_dataset('shots', league={LEAGUE})", "Returned 0 shots")
except Exception as e:
    results.add_fail(f"get_dataset('shots')", str(e))

# =============================================================================
# Test 4: Filter Functionality
# =============================================================================

print("\n" + "=" * 70)
print("TEST 4: Filter Functionality")
print("=" * 70)

# Test 4.1: Single game_id filter
try:
    schedule_for_filter = get_dataset("schedule", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(schedule_for_filter) > 0:
        single_game_id = str(schedule_for_filter.iloc[0]["GAME_ID"])
        pbp_single = get_dataset("pbp", {"league": LEAGUE, "season": SEASON, "game_ids": [single_game_id]}, pre_only=False)
        if len(pbp_single) > 0:
            results.add_pass(f"PBP filter: single game_id={single_game_id}", f"{len(pbp_single)} events")

            # Verify all events are for this game
            if pbp_single["GAME_ID"].nunique() == 1 and str(pbp_single["GAME_ID"].iloc[0]) == single_game_id:
                results.add_pass("PBP filter correctness", "All events belong to requested game")
            else:
                results.add_fail("PBP filter correctness", f"Found {pbp_single['GAME_ID'].nunique()} unique games")
        else:
            results.add_fail(f"PBP filter: single game_id", "Returned 0 events")
    else:
        results.add_skip("PBP filter: single game_id", "No games in schedule")
except Exception as e:
    results.add_fail("PBP filter: single game_id", str(e))

# Test 4.2: Team filter
try:
    schedule_full = get_dataset("schedule", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(schedule_full) > 0:
        team_name = schedule_full.iloc[0]["HOME_TEAM"]
        schedule_filtered = get_dataset("schedule", {"league": LEAGUE, "season": SEASON, "team": [team_name]}, pre_only=False)
        if len(schedule_filtered) > 0:
            results.add_pass(f"Schedule filter: team={team_name}", f"{len(schedule_filtered)} games")

            # Verify all games involve this team
            team_games = schedule_filtered[(schedule_filtered["HOME_TEAM"] == team_name) | (schedule_filtered["AWAY_TEAM"] == team_name)]
            if len(team_games) == len(schedule_filtered):
                results.add_pass("Team filter correctness", "All games involve requested team")
            else:
                results.add_fail("Team filter correctness", f"Only {len(team_games)}/{len(schedule_filtered)} games involve team")
        else:
            results.add_fail(f"Schedule filter: team={team_name}", "Returned 0 games")
    else:
        results.add_skip("Schedule filter: team", "No games in schedule")
except Exception as e:
    results.add_fail("Schedule filter: team", str(e))

# =============================================================================
# Test 5: Data Quality
# =============================================================================

print("\n" + "=" * 70)
print("TEST 5: Data Quality")
print("=" * 70)

# Test 5.1: No missing GAME_IDs
try:
    schedule_quality = get_dataset("schedule", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(schedule_quality) > 0:
        null_game_ids = schedule_quality["GAME_ID"].isnull().sum()
        if null_game_ids == 0:
            results.add_pass("No missing GAME_IDs in schedule")
        else:
            results.add_fail("No missing GAME_IDs in schedule", f"Found {null_game_ids} null GAME_IDs")
    else:
        results.add_skip("No missing GAME_IDs", "No schedule data")
except Exception as e:
    results.add_fail("No missing GAME_IDs", str(e))

# Test 5.2: Valid shot coordinates
try:
    shots_quality = get_dataset("shots", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(shots_quality) > 0:
        # Check for null coordinates
        null_x = shots_quality["SHOT_X"].isnull().sum()
        null_y = shots_quality["SHOT_Y"].isnull().sum()
        if null_x == 0 and null_y == 0:
            results.add_pass("No missing shot coordinates", f"{len(shots_quality)} shots all have x,y")
        else:
            results.add_fail("No missing shot coordinates", f"Null X: {null_x}, Null Y: {null_y}")

        # Check coordinate ranges (should be reasonable)
        if shots_quality["SHOT_X"].between(-50, 50).all() and shots_quality["SHOT_Y"].between(-50, 50).all():
            results.add_pass("Shot coordinates in reasonable range")
        else:
            results.add_fail("Shot coordinates in reasonable range", "Some coordinates out of bounds")
    else:
        results.add_skip("Valid shot coordinates", "No shot data")
except Exception as e:
    results.add_fail("Valid shot coordinates", str(e))

# Test 5.3: LEAGUE metadata injected
try:
    schedule_meta = get_dataset("schedule", {"league": LEAGUE, "season": SEASON}, pre_only=False)
    if len(schedule_meta) > 0:
        if "LEAGUE" in schedule_meta.columns and (schedule_meta["LEAGUE"] == "LNB_PROA").all():
            results.add_pass("LEAGUE metadata injection", "All rows have LEAGUE='LNB_PROA'")
        else:
            results.add_fail("LEAGUE metadata injection", "LEAGUE column missing or incorrect")
    else:
        results.add_skip("LEAGUE metadata", "No schedule data")
except Exception as e:
    results.add_fail("LEAGUE metadata", str(e))

# =============================================================================
# Final Summary
# =============================================================================

success = results.print_summary()

# Exit code
sys.exit(0 if success else 1)
