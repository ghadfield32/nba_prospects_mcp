"""LNB Endpoint Configuration - Centralized API & Web URLs

This module centralizes ALL known endpoints for LNB Pro A data sources:
- LNB official API (api-prod.lnb.fr)
- LNB web scraping URLs (www.lnb.fr)
- Atrium Sports API (eapi.web.prod.cloud.atriumsports.com) - Third-party stats provider

**Purpose**:
- Single source of truth for all endpoints
- Easy maintenance when URLs change
- Template-based URL generation for dynamic parameters
- Clear separation between API domains

**Usage**:
    from cbb_data.fetchers.lnb_endpoints import LNB_API, ATRIUM_API, LNB_WEB

    # API endpoint
    url = LNB_API.match_details(uuid="3522345e-3362-11f0-b97d-7be2bdc7a840")

    # Atrium endpoint
    url = ATRIUM_API.fixture_detail_url

    # Web scraping
    url = LNB_WEB.match_center(uuid="3522345e-3362-11f0-b97d-7be2bdc7a840")

**Endpoint Discovery Status**:
✅ Confirmed: LNB API structure endpoints (years, competitions, teams)
✅ Confirmed: LNB API schedule endpoints (calendar, live)
✅ Confirmed: LNB API match context endpoints (comparison, form, officials)
✅ Confirmed: Atrium Sports PBP/shots endpoints (fixture_detail with state parameter)
⚠️  Partial: LNB API boxscore/stats endpoints (need DevTools discovery)
⏳ Unknown: LNB API historical season navigation endpoints

Created: 2025-11-15
"""

from __future__ import annotations

from typing import Any

# ==============================================================================
# LNB Official API (api-prod.lnb.fr)
# ==============================================================================


class LNBAPIEndpoints:
    """LNB Official API endpoint templates

    Base URL: https://api-prod.lnb.fr

    Endpoint Categories:
    - Global/Structure: Years, competitions, divisions, teams
    - Schedule: Calendars, live games
    - Match Context: Team comparison, form, head-to-head, officials
    - Season Stats: Player leaders
    - Match Details: Boxscore, play-by-play, shot chart (partial discovery)
    """

    BASE_URL = "https://api-prod.lnb.fr"

    # ==========================================================================
    # Global / Season Structure
    # ==========================================================================

    # Get all available years/seasons
    ALL_YEARS = BASE_URL + "/common/getAllYears"

    # Get main competitions for a year
    # ⚠️  DEPRECATED: This endpoint returns 404 (removed from LNB API)
    # Use DIVISION_COMPETITIONS instead
    MAIN_COMPETITIONS = BASE_URL + "/common/getMainCompetition"  # BROKEN - returns 404

    # Get competitions filtered by division
    DIVISION_COMPETITIONS = BASE_URL + "/common/getDivisionCompetitionByYear"

    # Get teams in a competition
    COMPETITION_TEAMS = BASE_URL + "/stats/getCompetitionTeams"

    # Get competitions a player participated in
    COMPETITIONS_BY_PLAYER = BASE_URL + "/competition/getCompetitionByPlayer"

    # ==========================================================================
    # Schedule / Calendar
    # ==========================================================================

    # Get games by date range (POST with {from: date, to: date})
    CALENDAR = BASE_URL + "/stats/getCalendar"

    # Get calendar by division (alternative to date range)
    # NOTE: LNB API has a typo - "Calender" not "Calendar"
    CALENDAR_BY_DIVISION = BASE_URL + "/match/getCalenderByDivision"

    # Get current/upcoming live games
    # NOTE: This endpoint uses /match/ prefix, not /stats/ (verified working 2025-11-15)
    LIVE_MATCHES = BASE_URL + "/match/getLiveMatch"

    # ==========================================================================
    # Match Context (Pre-Game Analysis)
    # ==========================================================================

    # Get team comparison for a match
    TEAM_COMPARISON = BASE_URL + "/stats/getTeamComparison"

    # Get last 5 games (home/away) for teams in a match
    LAST_FIVE_HOME_AWAY = BASE_URL + "/stats/getLastFiveMatchesHomeAway"

    # Get last 5 head-to-head games between teams
    LAST_FIVE_HEAD_TO_HEAD = BASE_URL + "/stats/getLastFiveMatchesHeadToHead"

    # Get match officials (referees) for pre-game
    MATCH_OFFICIALS_PREGAME = BASE_URL + "/stats/getMatchOfficialsPreGame"

    # ==========================================================================
    # Season Stats / Leaders
    # ==========================================================================

    # Get player leaders for a competition (by category: points, rebounds, etc.)
    PLAYER_LEADERS = BASE_URL + "/stats/getPersonsLeaders"

    # Get team standings for a competition
    TEAM_STANDINGS = BASE_URL + "/stats/getStanding"

    # Get player performance stats for a competition
    PLAYER_PERFORMANCE = BASE_URL + "/stats/getPlayersPerformances"

    # ==========================================================================
    # Match Details (⚠️ Partial Discovery)
    # ==========================================================================

    # Get match details (metadata, teams, basic stats)
    # Status: ✅ Confirmed working
    @staticmethod
    def match_details(uuid: str) -> str:
        """Get match details by UUID

        Args:
            uuid: Match UUID (36-character hex string)

        Returns:
            Full endpoint URL

        Example:
            >>> url = LNB_API.match_details("3522345e-3362-11f0-b97d-7be2bdc7a840")
        """
        return f"{LNBAPIEndpoints.BASE_URL}/match/getMatchDetails/{uuid}"

    # Get event list (potentially season-scoped)
    # Status: ✅ Confirmed working
    EVENT_LIST = BASE_URL + "/event/getEventList"

    # Get match boxscore (player game stats)
    # Status: ⚠️ Placeholder - Path unknown, needs DevTools discovery
    # Once discovered, update this path and set `try_endpoint=True` in fetcher
    MATCH_BOXSCORE = BASE_URL + "/stats/getMatchBoxScore"  # Placeholder

    # Get play-by-play events
    # Status: ⚠️ Placeholder - Use Atrium API instead (confirmed working)
    MATCH_PBP = BASE_URL + "/stats/getPlayByPlay"  # Placeholder

    # Get shot chart
    # Status: ⚠️ Placeholder - Use Atrium API instead (confirmed working)
    MATCH_SHOT_CHART = BASE_URL + "/stats/getShotChart"  # Placeholder

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    @staticmethod
    def build_url(path: str, **params: Any) -> str:
        """Build full URL with query parameters

        Args:
            path: Endpoint path (with or without BASE_URL)
            **params: Query parameters to append

        Returns:
            Full URL with query string

        Example:
            >>> url = LNB_API.build_url(LNB_API.ALL_YEARS, end_year=2025)
            >>> # Returns: "https://api-prod.lnb.fr/common/getAllYears?end_year=2025"
        """
        # Ensure path starts with BASE_URL
        if not path.startswith("http"):
            path = f"{LNBAPIEndpoints.BASE_URL}{path}"

        # Build query string if params provided
        if params:
            query_parts = []
            for key, value in params.items():
                if value is not None:
                    query_parts.append(f"{key}={value}")

            if query_parts:
                path += "?" + "&".join(query_parts)

        return path


# ==============================================================================
# Atrium Sports API (Third-Party Stats Provider)
# ==============================================================================


class AtriumAPIEndpoints:
    """Atrium Sports API endpoint templates

    Base URL: https://eapi.web.prod.cloud.atriumsports.com

    Atrium Sports provides detailed PBP and shot chart data for LNB games.
    This is a third-party stats provider contracted by LNB.

    **Authentication**: Requires browser-like headers (User-Agent, Referer)
    **State Parameter**: PBP and shot requests require compressed state parameter
    """

    BASE_URL = "https://eapi.web.prod.cloud.atriumsports.com"

    # Fixture detail endpoint (used for PBP and shot chart)
    # Requires query params: fixtureId={uuid}, state={compressed_state}
    FIXTURE_DETAIL = BASE_URL + "/v1/embed/12/fixture_detail"

    # Required headers for Atrium API
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    @staticmethod
    def fixture_detail(fixture_id: str, state: str) -> str:
        """Build fixture detail URL with query parameters

        Args:
            fixture_id: Game UUID (36-character hex string)
            state: Compressed state parameter (view type: "pbp" or "shot_chart")

        Returns:
            Full endpoint URL with query string

        Example:
            >>> from cbb_data.fetchers.lnb import _create_atrium_state
            >>> state = _create_atrium_state(fixture_id, "pbp")
            >>> url = ATRIUM_API.fixture_detail(fixture_id, state)
        """
        return f"{AtriumAPIEndpoints.FIXTURE_DETAIL}?fixtureId={fixture_id}&state={state}"


# ==============================================================================
# LNB Web Scraping URLs (www.lnb.fr)
# ==============================================================================


class LNBWebEndpoints:
    """LNB website URLs for web scraping (Playwright)

    Base URL: https://www.lnb.fr

    These URLs are used when API endpoints are unavailable or don't provide
    sufficient data. Requires Playwright for JavaScript rendering.
    """

    BASE_URL = "https://www.lnb.fr"

    # ==========================================================================
    # Static Pages (HTML Table Scraping)
    # ==========================================================================

    # Team standings and statistics
    STATISTICS = BASE_URL + "/pro-a/statistiques"

    # Schedule/calendar page
    CALENDAR = BASE_URL + "/pro-a/calendrier"

    # Stats center (live game stats, player stats)
    STATS_CENTER = BASE_URL + "/fr/stats-centre"

    # ==========================================================================
    # Dynamic Pages (Require Playwright)
    # ==========================================================================

    @staticmethod
    def match_center(uuid: str) -> str:
        """Match center page (game details, PBP, shots)

        Args:
            uuid: Match UUID (36-character hex string)

        Returns:
            Full match center URL

        Example:
            >>> url = LNB_WEB.match_center("3522345e-3362-11f0-b97d-7be2bdc7a840")
            >>> # Returns: "https://lnb.fr/fr/match-center/3522345e-3362-11f0-b97d-7be2bdc7a840"
        """
        return f"https://lnb.fr/fr/match-center/{uuid}"

    @staticmethod
    def pre_match_center(uuid: str) -> str:
        """Pre-match center page (pre-game information)

        Args:
            uuid: Match UUID (36-character hex string)

        Returns:
            Full pre-match center URL

        Example:
            >>> url = LNB_WEB.pre_match_center("3522345e-3362-11f0-b97d-7be2bdc7a840")
            >>> # Returns: "https://lnb.fr/fr/pre-match-center?mid=3522345e-3362-11f0-b97d-7be2bdc7a840"
        """
        return f"https://lnb.fr/fr/pre-match-center?mid={uuid}"

    @staticmethod
    def pro_a_match(uuid: str) -> str:
        """Pro A match page (alternative match detail page)

        Args:
            uuid: Match UUID (36-character hex string)

        Returns:
            Full Pro A match URL

        Example:
            >>> url = LNB_WEB.pro_a_match("3522345e-3362-11f0-b97d-7be2bdc7a840")
            >>> # Returns: "https://www.lnb.fr/pro-a/match/3522345e-3362-11f0-b97d-7be2bdc7a840"
        """
        return f"{LNBWebEndpoints.BASE_URL}/pro-a/match/{uuid}"


# ==============================================================================
# Convenience Exports
# ==============================================================================

# Create singleton instances for easy import
LNB_API = LNBAPIEndpoints()
ATRIUM_API = AtriumAPIEndpoints()
LNB_WEB = LNBWebEndpoints()


# ==============================================================================
# Endpoint Status Summary
# ==============================================================================

ENDPOINT_STATUS = {
    "LNB API": {
        "Global/Structure": "✅ Confirmed (getAllYears works, getMainCompetition deprecated)",
        "Schedule": "✅ Confirmed (/match/getCalenderByDivision - note typo)",
        "Match Context": "✅ Confirmed",
        "Season Stats": "✅ Confirmed",
        "Match Details": "✅ Confirmed (getMatchDetails, getEventList)",
        "Live Matches": "✅ Confirmed (/match/getLiveMatch works)",
        "Main Competitions": "❌ DEPRECATED (404 - use getDivisionCompetitionByYear)",
        "Boxscore": "⚠️ Placeholder (needs DevTools discovery)",
        "Play-by-Play": "⚠️ Placeholder (use Atrium instead)",
        "Shot Chart": "⚠️ Placeholder (use Atrium instead)",
    },
    "Atrium API": {
        "Fixture Detail": "✅ Confirmed",
        "Play-by-Play": "✅ Confirmed (via fixture_detail + state)",
        "Shot Chart": "✅ Confirmed (via fixture_detail + state)",
    },
    "LNB Web": {
        "Team Standings": "✅ Confirmed (static HTML)",
        "Schedule": "✅ Confirmed (Playwright)",
        "Match Center": "✅ Confirmed (Playwright)",
        "Player Stats": "✅ Confirmed (Playwright)",
    },
}


def print_endpoint_status() -> None:
    """Print current endpoint discovery status"""
    import io
    import sys

    # Fix Windows console encoding for emoji support
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("\n" + "=" * 80)
    print("LNB ENDPOINT STATUS SUMMARY")
    print("=" * 80 + "\n")

    for api_name, endpoints in ENDPOINT_STATUS.items():
        print(f"{api_name}:")
        for endpoint_name, status in endpoints.items():
            print(f"  {endpoint_name:25s} {status}")
        print()


if __name__ == "__main__":
    # Print endpoint status when run as script
    print_endpoint_status()

    # Example usage
    print("\nExample URLs:")
    print("-" * 80)

    uuid = "3522345e-3362-11f0-b97d-7be2bdc7a840"

    print("\n1. LNB API - Match Details:")
    print(f"   {LNB_API.match_details(uuid)}")

    print("\n2. LNB API - All Years:")
    print(f"   {LNB_API.build_url(LNB_API.ALL_YEARS, end_year=2025)}")

    print("\n3. Atrium API - Fixture Detail:")
    print(f"   {ATRIUM_API.FIXTURE_DETAIL}")
    print("   (requires fixtureId and state query params)")

    print("\n4. LNB Web - Match Center:")
    print(f"   {LNB_WEB.match_center(uuid)}")

    print("\n5. LNB Web - Schedule:")
    print(f"   {LNB_WEB.CALENDAR}")
    print()
