"""Comprehensive stress test for LNB API endpoints.

This test suite validates all known LNB API endpoints and discovers
available data granularities. It's designed to be thorough and detailed,
testing every endpoint with various parameters and edge cases.

Test Categories:
1. Structure Discovery (years, competitions, divisions, teams)
2. Schedule/Calendar (date ranges, chunking, full seasons)
3. Match Context (team comparison, form, h2h, officials)
4. Season Statistics (player leaders by category)
5. Live Data (current/upcoming matches)
6. Boxscore/PBP/Shots (placeholders, expected to fail)

Usage:
    # Run all tests
    pytest tests/test_lnb_api_stress.py -v

    # Run with detailed output
    pytest tests/test_lnb_api_stress.py -v -s

    # Run specific test category
    pytest tests/test_lnb_api_stress.py::TestLNBStructure -v

    # Generate coverage report
    pytest tests/test_lnb_api_stress.py --cov=src.cbb_data.fetchers.lnb_api

Expected Results:
- ✅ Structure endpoints: Should all pass
- ✅ Calendar endpoints: Should all pass
- ✅ Match context endpoints: Should all pass (if match IDs valid)
- ✅ Live endpoints: Should pass
- ⚠️  Season leaders: May fail without extra_params
- ❌ Boxscore/PBP/Shots: Expected to fail (placeholders)

Created: 2025-11-14
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pytest

from src.cbb_data.fetchers.lnb_api import LNBAPIError, LNBClient, stress_test_lnb

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ========================================
# Fixtures
# ========================================


@pytest.fixture(scope="module")
def client() -> LNBClient:
    """Create shared LNBClient for all tests."""
    return LNBClient()


@pytest.fixture(scope="module")
def test_year() -> int:
    """Current season year for testing."""
    return datetime.utcnow().year


@pytest.fixture(scope="module")
def test_years(client: LNBClient, test_year: int) -> list[int]:
    """Discover available years for testing."""
    try:
        years_data = client.get_all_years(end_year=test_year)
        years = []
        for y in years_data:
            val = y.get("year") or y.get("end_year") or y.get("season")
            if isinstance(val, int):
                years.append(val)
        return sorted(set(years))[-3:]  # Last 3 seasons
    except Exception as e:
        logger.warning(f"Could not fetch years, using fallback: {e}")
        return [test_year - 2, test_year - 1, test_year]


@pytest.fixture(scope="module")
def test_competition(client: LNBClient, test_years: list[int]) -> dict[str, Any]:
    """Get a test competition for detailed testing."""
    for year in reversed(test_years):
        try:
            # Use working replacement for deprecated get_main_competitions (2025-11-15)
            comps = client.get_division_competitions_by_year(year, division_external_id=1)
            if comps:
                return {"year": year, "competition": comps[0]}
        except Exception:
            continue
    pytest.skip("No test competition available")


@pytest.fixture(scope="module")
def test_match_id(client: LNBClient, test_competition: dict[str, Any]) -> int:
    """Get a test match ID for match-level endpoint testing."""
    # year = test_competition["year"]  # Not currently needed
    # Try to get a recent match
    try:
        # Look for matches in the last 6 months
        end_date = date.today()
        start_date = end_date - timedelta(days=180)
        games = client.get_calendar(start_date, end_date)
        if games:
            match_id = games[0].get("match_external_id") or games[0].get("external_id")
            if match_id:
                return match_id
    except Exception as e:
        logger.warning(f"Could not fetch recent match: {e}")

    pytest.skip("No test match ID available")


# ========================================
# Test: Structure Discovery
# ========================================


class TestLNBStructure:
    """Test structure discovery endpoints (years, competitions, teams)."""

    def test_get_all_years(self, client: LNBClient, test_year: int):
        """Test GET /common/getAllYears"""
        logger.info("\n[TEST] getAllYears")

        years = client.get_all_years(end_year=test_year)

        assert isinstance(years, list), "Should return list"
        assert len(years) > 0, "Should return at least one year"

        # Validate structure
        for year_obj in years:
            assert isinstance(year_obj, dict), "Each year should be a dict"
            # Should have some year-related field
            has_year = any(k in year_obj for k in ["year", "end_year", "season", "season_year"])
            assert has_year, f"Year object missing year field: {year_obj}"

        logger.info(f"✅ getAllYears: Found {len(years)} seasons")

    def test_get_division_competitions(self, client: LNBClient, test_years: list[int]):
        """Test GET /common/getDivisionCompetitionByYear"""
        logger.info("\n[TEST] getDivisionCompetitionByYear")

        division_id = 1  # Betclic ÉLITE
        for year in test_years:
            comps = client.get_division_competitions_by_year(year, division_external_id=division_id)

            assert isinstance(comps, list), f"Should return list for year {year}"

            if comps:
                for comp in comps:
                    assert isinstance(comp, dict), "Each competition should be dict"

                logger.info(
                    f"✅ getDivisionCompetitionByYear({year}, div={division_id}): "
                    f"{len(comps)} competitions"
                )
            else:
                logger.info(
                    f"⚠️  getDivisionCompetitionByYear({year}, div={division_id}): "
                    f"No competitions"
                )

    def test_get_competition_teams(self, client: LNBClient, test_competition: dict[str, Any]):
        """Test GET /stats/getCompetitionTeams"""
        logger.info("\n[TEST] getCompetitionTeams")

        comp = test_competition["competition"]
        comp_ext_id = comp["external_id"]

        teams = client.get_competition_teams(comp_ext_id)

        assert isinstance(teams, list), "Should return list"
        assert len(teams) > 0, "Should return at least one team"

        # Validate team structure
        for team in teams:
            assert isinstance(team, dict), "Each team should be dict"
            # Should have either team_id or external_id
            has_id = "team_id" in team or "external_id" in team or "id" in team
            assert has_id, f"Team missing ID field: {team}"

        logger.info(f"✅ getCompetitionTeams(comp={comp_ext_id}): {len(teams)} teams")

        # Log sample team
        if teams:
            sample = teams[0]
            logger.info(
                f"   Sample team: {sample.get('name', 'Unknown')} "
                f"(ID: {sample.get('external_id', sample.get('id'))})"
            )


# ========================================
# Test: Schedule/Calendar
# ========================================


class TestLNBCalendar:
    """Test schedule and calendar endpoints."""

    def test_get_calendar_single_month(self, client: LNBClient):
        """Test POST /stats/getCalendar for a single month"""
        logger.info("\n[TEST] getCalendar (single month)")

        # Test November 2024 (known season)
        from_date = date(2024, 11, 1)
        to_date = date(2024, 11, 30)

        games = client.get_calendar(from_date, to_date)

        assert isinstance(games, list), "Should return list"
        # May be empty if off-season, but should not error
        logger.info(f"✅ getCalendar({from_date} to {to_date}): {len(games)} games")

        if games:
            # Validate game structure
            sample = games[0]
            assert isinstance(sample, dict), "Each game should be dict"
            # Should have match ID
            has_match_id = "match_external_id" in sample or "external_id" in sample
            assert has_match_id, f"Game missing match ID: {sample}"

            logger.info(
                f"   Sample game: match_id={sample.get('match_external_id', sample.get('external_id'))}"
            )

    def test_get_calendar_date_range(self, client: LNBClient):
        """Test POST /stats/getCalendar with various date ranges"""
        logger.info("\n[TEST] getCalendar (various date ranges)")

        test_ranges = [
            (date(2024, 9, 1), date(2024, 9, 30), "September 2024"),
            (date(2024, 10, 1), date(2024, 12, 31), "Q4 2024"),
            (date(2024, 1, 1), date(2024, 3, 31), "Q1 2024"),
        ]

        for from_date, to_date, label in test_ranges:
            games = client.get_calendar(from_date, to_date)
            assert isinstance(games, list), f"Should return list for {label}"
            logger.info(f"✅ getCalendar {label}: {len(games)} games")

    def test_iter_full_season_calendar(self, client: LNBClient, test_competition: dict[str, Any]):
        """Test full season calendar with chunking"""
        logger.info("\n[TEST] iter_full_season_calendar")

        year = test_competition["year"]
        season_start = date(year, 8, 1)
        season_end = date(year + 1, 7, 31)

        games = client.iter_full_season_calendar(season_start, season_end, step_days=31)

        assert isinstance(games, list), "Should return list"
        logger.info(f"✅ iter_full_season_calendar({year}-{year+1}): " f"{len(games)} total games")

        if games:
            # Validate deduplication (no duplicate match_external_ids)
            match_ids = []
            for g in games:
                mid = g.get("match_external_id") or g.get("external_id")
                if mid:
                    match_ids.append(mid)

            unique_ids = set(match_ids)
            assert len(match_ids) == len(unique_ids), "Should deduplicate match IDs"
            logger.info(f"   ✅ Deduplication verified: {len(unique_ids)} unique games")


# ========================================
# Test: Match Context
# ========================================


class TestLNBMatchContext:
    """Test match-level context endpoints."""

    def test_get_team_comparison(self, client: LNBClient, test_match_id: int):
        """Test GET /stats/getTeamComparison"""
        logger.info("\n[TEST] getTeamComparison")

        comp = client.get_team_comparison(test_match_id)

        assert isinstance(comp, dict), "Should return dict"
        logger.info(f"✅ getTeamComparison(match={test_match_id})")
        logger.info(f"   Keys: {list(comp.keys())[:10]}...")  # Show sample keys

    def test_get_last_five_home_away(self, client: LNBClient, test_match_id: int):
        """Test GET /stats/getLastFiveMatchesHomeAway"""
        logger.info("\n[TEST] getLastFiveMatchesHomeAway")

        form = client.get_last_five_home_away(test_match_id)

        assert isinstance(form, dict), "Should return dict"
        logger.info(f"✅ getLastFiveMatchesHomeAway(match={test_match_id})")
        logger.info(f"   Keys: {list(form.keys())[:10]}...")

    def test_get_last_five_h2h(self, client: LNBClient, test_match_id: int):
        """Test GET /stats/getLastFiveMatchesHeadToHead"""
        logger.info("\n[TEST] getLastFiveMatchesHeadToHead")

        h2h = client.get_last_five_h2h(test_match_id)

        assert isinstance(h2h, dict), "Should return dict"
        logger.info(f"✅ getLastFiveMatchesHeadToHead(match={test_match_id})")
        logger.info(f"   Keys: {list(h2h.keys())[:10]}...")

    def test_get_match_officials_pregame(self, client: LNBClient, test_match_id: int):
        """Test GET /stats/getMatchOfficialsPreGame"""
        logger.info("\n[TEST] getMatchOfficialsPreGame")

        officials = client.get_match_officials_pregame(test_match_id)

        assert isinstance(officials, dict), "Should return dict"
        logger.info(f"✅ getMatchOfficialsPreGame(match={test_match_id})")

        # Check for referees
        if "referees" in officials:
            refs = officials["referees"]
            logger.info(f"   Found {len(refs)} referees")
            if refs:
                sample = refs[0]
                logger.info(
                    f"   Sample referee: {sample.get('name', 'Unknown')} "
                    f"({sample.get('role', 'Unknown role')})"
                )


# ========================================
# Test: Season Statistics
# ========================================


class TestLNBSeasonStats:
    """Test season statistics endpoints."""

    def test_get_persons_leaders_minimal(self, client: LNBClient, test_competition: dict[str, Any]):
        """Test GET /stats/getPersonsLeaders (may fail without extra params)"""
        logger.info("\n[TEST] getPersonsLeaders (minimal params)")

        comp = test_competition["competition"]
        year = test_competition["year"]
        comp_ext_id = comp["external_id"]

        try:
            # Try with minimal params (may fail)
            leaders = client.get_persons_leaders(
                competition_external_id=comp_ext_id,
                year=year,
            )
            assert isinstance(leaders, dict), "Should return dict"
            logger.info(f"✅ getPersonsLeaders(comp={comp_ext_id}, year={year})")
            logger.info(f"   Keys: {list(leaders.keys())[:10]}...")

        except LNBAPIError as e:
            logger.warning(f"⚠️  getPersonsLeaders failed (expected - needs extra_params): {e}")
            pytest.skip("getPersonsLeaders requires extra_params (category, page, etc.)")

    @pytest.mark.parametrize(
        "category",
        ["points", "rebounds", "assists"],
        ids=["points", "rebounds", "assists"],
    )
    def test_get_persons_leaders_with_category(
        self,
        client: LNBClient,
        test_competition: dict[str, Any],
        category: str,
    ):
        """Test GET /stats/getPersonsLeaders with category parameter"""
        logger.info(f"\n[TEST] getPersonsLeaders (category={category})")

        comp = test_competition["competition"]
        year = test_competition["year"]
        comp_ext_id = comp["external_id"]

        try:
            leaders = client.get_persons_leaders(
                competition_external_id=comp_ext_id,
                year=year,
                extra_params={"category": category, "page": 1, "limit": 10},
            )
            assert isinstance(leaders, dict), "Should return dict"
            logger.info(
                f"✅ getPersonsLeaders(comp={comp_ext_id}, year={year}, " f"category={category})"
            )

        except LNBAPIError as e:
            logger.warning(f"⚠️  getPersonsLeaders({category}) failed: {e}")
            pytest.skip(f"getPersonsLeaders category={category} not working")


# ========================================
# Test: Live Data
# ========================================


class TestLNBLive:
    """Test live data endpoints."""

    def test_get_live_match(self, client: LNBClient):
        """Test GET /stats/getLiveMatch"""
        logger.info("\n[TEST] getLiveMatch")

        live = client.get_live_match()

        assert isinstance(live, list), "Should return list"
        logger.info(f"✅ getLiveMatch: {len(live)} live/upcoming games")

        if live:
            sample = live[0]
            logger.info(
                f"   Sample: {sample.get('home_team', 'Unknown')} vs "
                f"{sample.get('away_team', 'Unknown')} "
                f"({sample.get('match_date', 'Unknown date')})"
            )


# ========================================
# Test: Placeholder Endpoints (Expected to Fail)
# ========================================


class TestLNBPlaceholders:
    """Test placeholder endpoints (boxscore, PBP, shots) - expected to fail."""

    def test_get_match_boxscore_placeholder(self, client: LNBClient, test_match_id: int):
        """Test boxscore placeholder (expected to fail)"""
        logger.info("\n[TEST] getMatchBoxScore (PLACEHOLDER - expected to fail)")

        with pytest.raises(LNBAPIError):
            _ = client.get_match_boxscore(test_match_id)

        logger.info("❌ getMatchBoxScore failed as expected (placeholder, needs DevTools path)")

    def test_get_match_play_by_play_placeholder(self, client: LNBClient, test_match_id: int):
        """Test play-by-play placeholder (expected to fail)"""
        logger.info("\n[TEST] getMatchPlayByPlay (PLACEHOLDER - expected to fail)")

        with pytest.raises(LNBAPIError):
            _ = client.get_match_play_by_play(test_match_id)

        logger.info("❌ getMatchPlayByPlay failed as expected (placeholder, needs DevTools path)")

    def test_get_match_shot_chart_placeholder(self, client: LNBClient, test_match_id: int):
        """Test shot chart placeholder (expected to fail)"""
        logger.info("\n[TEST] getMatchShots (PLACEHOLDER - expected to fail)")

        with pytest.raises(LNBAPIError):
            _ = client.get_match_shot_chart(test_match_id)

        logger.info("❌ getMatchShots failed as expected (placeholder, needs DevTools path)")


# ========================================
# Test: Comprehensive Stress Test
# ========================================


class TestLNBStressHarness:
    """Test the comprehensive stress_test_lnb() harness."""

    def test_stress_test_lnb_quick(self):
        """Test stress_test_lnb with quick settings"""
        logger.info("\n[TEST] stress_test_lnb (quick run)")

        results = stress_test_lnb(
            seasons_back=1,  # Just 1 season
            max_matches_per_season=2,  # Just 2 matches
        )

        # Validate structure
        assert "target_years" in results
        assert "per_year" in results
        assert "endpoint_stats" in results
        assert "live_matches_sample" in results

        # Log summary
        logger.info("\n" + "=" * 60)
        logger.info("Stress Test Results Summary")
        logger.info("=" * 60)

        for endpoint, counts in sorted(results["endpoint_stats"].items()):
            ok = counts["ok"]
            failed = counts["failed"]
            total = ok + failed
            status = "✅" if failed == 0 else "⚠️" if ok > 0 else "❌"
            logger.info(
                f"{status} {endpoint:40s} {ok:3d} OK / {failed:3d} FAIL " f"({total:3d} total)"
            )

        logger.info("=" * 60)

        # Ensure critical endpoints passed
        critical_endpoints = [
            "getAllYears",
            "getMainCompetition",
            "getCompetitionTeams",
            "getCalendar",
        ]

        for endpoint in critical_endpoints:
            if endpoint in results["endpoint_stats"]:
                counts = results["endpoint_stats"][endpoint]
                assert (
                    counts["ok"] > 0
                ), f"Critical endpoint {endpoint} should have at least 1 success"

        logger.info("✅ Stress test harness validated")


# ========================================
# Test: Error Handling
# ========================================


class TestLNBErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_year(self, client: LNBClient):
        """Test with invalid year (should handle gracefully)"""
        logger.info("\n[TEST] Error handling - invalid year")

        # Try year far in the future
        comps = client.get_main_competitions(year=2099)

        # Should return empty list, not error
        assert isinstance(comps, list), "Should return list even for invalid year"
        logger.info(f"✅ Invalid year handled gracefully: {len(comps)} competitions")

    def test_invalid_competition_id(self, client: LNBClient):
        """Test with invalid competition ID (should error)"""
        logger.info("\n[TEST] Error handling - invalid competition ID")

        with pytest.raises(LNBAPIError):
            _ = client.get_competition_teams(competition_external_id=999999)

        logger.info("✅ Invalid competition ID raised LNBAPIError as expected")

    def test_invalid_match_id(self, client: LNBClient):
        """Test with invalid match ID (should error)"""
        logger.info("\n[TEST] Error handling - invalid match ID")

        with pytest.raises(LNBAPIError):
            _ = client.get_team_comparison(match_external_id=999999999)

        logger.info("✅ Invalid match ID raised LNBAPIError as expected")

    def test_invalid_date_range(self, client: LNBClient):
        """Test with invalid date range (end before start)"""
        logger.info("\n[TEST] Error handling - invalid date range")

        # End date before start date
        from_date = date(2024, 12, 31)
        to_date = date(2024, 1, 1)

        # Should handle gracefully (return empty or error)
        try:
            games = client.get_calendar(from_date, to_date)
            assert isinstance(games, list), "Should return list"
            logger.info(f"✅ Invalid date range handled gracefully: {len(games)} games")
        except LNBAPIError:
            logger.info("✅ Invalid date range raised LNBAPIError as expected")


# ========================================
# Performance Benchmarks (Optional)
# ========================================


@pytest.mark.slow
class TestLNBPerformance:
    """Performance benchmarks for LNB API (marked as slow tests)."""

    def test_calendar_performance_full_season(self, client: LNBClient):
        """Benchmark full season calendar fetch"""
        logger.info("\n[BENCHMARK] Full season calendar")

        import time

        start = time.time()

        games = client.iter_full_season_calendar(
            season_start=date(2024, 8, 1),
            season_end=date(2025, 7, 31),
            step_days=31,
        )

        elapsed = time.time() - start

        logger.info(
            f"⏱️  Full season calendar: {len(games)} games in {elapsed:.2f}s "
            f"({len(games)/elapsed:.1f} games/sec)"
        )

    def test_match_context_batch_performance(self, client: LNBClient, test_match_id: int):
        """Benchmark batch match context fetches"""
        logger.info("\n[BENCHMARK] Match context batch")

        import time

        start = time.time()

        # Fetch all match context endpoints
        _ = client.get_team_comparison(test_match_id)
        _ = client.get_last_five_home_away(test_match_id)
        _ = client.get_last_five_h2h(test_match_id)
        _ = client.get_match_officials_pregame(test_match_id)

        elapsed = time.time() - start

        logger.info(
            f"⏱️  Match context batch (4 endpoints): {elapsed:.2f}s "
            f"({4/elapsed:.1f} requests/sec)"
        )


# ========================================
# Main Entry Point
# ========================================

if __name__ == "__main__":
    """Run tests as script (for quick validation)."""
    pytest.main([__file__, "-v", "-s"])
