"""LNB API Client - Official API for French Basketball (Betclic ÉLITE, LNB Pro A)

This module provides a complete Python client for api-prod.lnb.fr, the official
API for France's top professional basketball leagues (Betclic ÉLITE / LNB Pro A).

**Architecture**:
- LNBClient: Low-level HTTP client with retry logic and envelope unwrapping
- Endpoint methods: One method per API endpoint
- Stress test harness: Validates all endpoints and discovers data granularities

**Data Coverage**:
✅ Structure: Years, competitions, divisions, teams
✅ Schedule: Full season calendars via date-range queries
✅ Match Context: Team comparison, form, head-to-head, officials
✅ Season Stats: Player leaders by category
✅ Live: Current/upcoming games
⚠️  Boxscore: Placeholder (needs DevTools path discovery)
⚠️  Play-by-Play: Placeholder (needs DevTools path discovery)
⚠️  Shot Chart: Placeholder (needs DevTools path discovery)

**Key Features**:
- Shared requests.Session for connection pooling
- Automatic retry with exponential backoff
- Response envelope unwrapping ({"status": true, "data": ...} → data)
- Calendar chunking for full-season pulls
- Game deduplication by match_external_id
- Browser-like headers to avoid bot detection
- Comprehensive stress test for validation

**Usage**:
    # Basic client usage
    from cbb_data.fetchers.lnb_api import LNBClient

    client = LNBClient()

    # Discover available seasons
    years = client.get_all_years(end_year=2025)

    # Get competitions for a year
    comps = client.get_main_competitions(year=2024)

    # Get teams for a competition
    teams = client.get_competition_teams(competition_external_id=302)

    # Get full season schedule
    from datetime import date
    games = client.iter_full_season_calendar(
        season_start=date(2024, 9, 1),
        season_end=date(2025, 6, 30)
    )

    # Get match context
    match_id = 28910
    comparison = client.get_team_comparison(match_id)
    officials = client.get_match_officials_pregame(match_id)

    # Run comprehensive stress test
    from cbb_data.fetchers.lnb_api import stress_test_lnb
    results = stress_test_lnb(
        seasons_back=2,
        max_matches_per_season=10
    )
    print(results["endpoint_stats"])

**API Base URL**: https://api-prod.lnb.fr

**Endpoint Catalog**:

Global/Structure:
- GET /common/getAllYears?end_year=YYYY
- GET /common/getMainCompetition?year=YYYY
- GET /common/getDivisionCompetitionByYear?year=YYYY&division_external_id=N
- GET /stats/getCompetitionTeams?competition_external_id=N

Schedule:
- POST /stats/getCalendar (JSON body: {from: date, to: date})

Match Context:
- GET /stats/getTeamComparison?match_external_id=N
- GET /stats/getLastFiveMatchesHomeAway?match_external_id=N
- GET /stats/getLastFiveMatchesHeadToHead?match_external_id=N
- GET /stats/getMatchOfficialsPreGame?match_external_id=N

Season Stats:
- GET /stats/getPersonsLeaders?competition_external_id=N&year=YYYY&...

Live:
- GET /stats/getLiveMatch

Boxscore/PBP/Shots (TODO - need DevTools discovery):
- Boxscore: Unknown path (contains player_game stats)
- Play-by-Play: Unknown path (contains event stream)
- Shot Chart: Unknown path (contains x,y coordinates)

**Implementation Notes**:
- Season format: Integer year (2024 for 2024-25 season)
- Team IDs: Both UUID (team_id) and integer (external_id) used
- Match IDs: Primary key is match_external_id (integer)
- Competition IDs: competition_external_id (integer, e.g. 302, 303)
- Division IDs: division_external_id (1 = Betclic ÉLITE)
- Calendar chunking: API accepts date ranges; we chunk by 31 days
- Rate limiting: Built-in retry_sleep between requests

**Related Files**:
- lnb.py: High-level DataFrame interface (uses lnb_api.py internally)
- html_tables.py: Legacy HTML scraping (being phased out)

**External References**:
- Official site: https://www.lnb.fr/
- Stats center: https://www.lnb.fr/statistiques
- API discovered via browser DevTools network inspection

Created: 2025-11-14
Author: Generated for nba_prospects_mcp
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://api-prod.lnb.fr"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    # Browser-like User-Agent to avoid bot detection
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # Referer expected by LNB API
    "Referer": "https://www.lnb.fr/",
}


class LNBAPIError(RuntimeError):
    """Raised when the LNB API returns an error or invalid response."""

    pass


@dataclass
class LNBRequestStats:
    """Statistics for stress test endpoint validation.

    Attributes:
        ok: Number of successful requests
        failed: Number of failed requests
    """

    ok: int = 0
    failed: int = 0

    def record_ok(self) -> None:
        """Record a successful request."""
        self.ok += 1

    def record_failed(self) -> None:
        """Record a failed request."""
        self.failed += 1

    def as_dict(self) -> Dict[str, int]:
        """Convert to dictionary for JSON serialization."""
        return {"ok": self.ok, "failed": self.failed}


class LNBClient:
    """Low-level HTTP client for api-prod.lnb.fr.

    This client handles:
    - Connection pooling via shared Session
    - Retry logic with exponential backoff
    - Response envelope unwrapping ({"status": true, "data": ...})
    - Browser-like headers to avoid detection
    - Error handling and logging

    All methods return parsed JSON data (envelope unwrapped).

    Args:
        base_url: API base URL (default: https://api-prod.lnb.fr)
        timeout: Request timeout in seconds (default: 15.0)
        max_retries: Maximum retry attempts per request (default: 3)
        retry_sleep: Base sleep duration between retries in seconds (default: 0.25)

    Example:
        >>> client = LNBClient()
        >>> years = client.get_all_years(end_year=2025)
        >>> comps = client.get_main_competitions(year=2024)
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 15.0,
        max_retries: int = 3,
        retry_sleep: float = 0.25,
    ) -> None:
        """Initialize LNB API client.

        Args:
            base_url: API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_sleep: Base sleep duration between retries
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep

        # Shared session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        logger.debug(
            f"Initialized LNBClient: base_url={base_url}, "
            f"timeout={timeout}s, max_retries={max_retries}"
        )

    # ========================================
    # Low-level HTTP helpers
    # ========================================

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute HTTP request with retry logic and envelope unwrapping.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/common/getAllYears")
            params: Query parameters for GET requests
            json: JSON body for POST requests

        Returns:
            Parsed response data (envelope unwrapped)

        Raises:
            LNBAPIError: If request fails after all retries or API returns error
        """
        url = f"{self.base_url}{path}"
        last_exc: Optional[BaseException] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    f"Request attempt {attempt}/{self.max_retries}: "
                    f"{method} {path} (params={params}, json={json})"
                )

                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    timeout=self.timeout,
                )
                resp.raise_for_status()

                data = resp.json()

                # Check for API-level error ({"status": false, "message": "..."})
                if isinstance(data, dict):
                    if "status" in data and not data.get("status", True):
                        error_msg = data.get("message", "Unknown API error")
                        raise LNBAPIError(f"API error at {path}: {error_msg!r}")

                    # Unwrap common envelope: {"status": true, "data": ...} → data
                    if "data" in data:
                        logger.debug(f"Success: {method} {path} (unwrapped 'data' key)")
                        return data["data"]

                # Return raw response if no envelope
                logger.debug(f"Success: {method} {path} (no envelope)")
                return data

            except (requests.RequestException, ValueError, LNBAPIError) as exc:
                last_exc = exc
                logger.warning(
                    f"Request failed (attempt {attempt}/{self.max_retries}): "
                    f"{method} {path} - {exc!r}"
                )

                if attempt >= self.max_retries:
                    logger.error(
                        f"Request exhausted retries: {method} {path} - {exc!r}"
                    )
                    raise LNBAPIError(f"Request failed for {path}: {exc!r}") from exc

                # Exponential backoff
                sleep_duration = self.retry_sleep * (2 ** (attempt - 1))
                logger.debug(f"Retrying in {sleep_duration:.2f}s...")
                time.sleep(sleep_duration)

        # Should be unreachable (mypy safety)
        raise LNBAPIError(f"Request failed for {path}: {last_exc!r}")

    def _get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Parsed response data
        """
        return self._request("GET", path, params=params)

    def _post(
        self,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute POST request.

        Args:
            path: API path
            json: JSON body

        Returns:
            Parsed response data
        """
        return self._request("POST", path, json=json)

    # ========================================
    # Global / Season Structure Endpoints
    # ========================================

    def get_all_years(self, end_year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all available seasons/years.

        Endpoint: GET /common/getAllYears?end_year=YYYY

        Args:
            end_year: Latest year to return (default: current year)

        Returns:
            List of season objects (fields vary, typically include 'year')

        Example:
            >>> client = LNBClient()
            >>> years = client.get_all_years(end_year=2025)
            >>> print([y.get('year') for y in years])
            [2020, 2021, 2022, 2023, 2024, 2025]
        """
        if end_year is None:
            end_year = datetime.utcnow().year

        logger.info(f"Fetching all years (end_year={end_year})")
        return self._get("/common/getAllYears", params={"end_year": end_year})

    def get_main_competitions(self, year: int) -> List[Dict[str, Any]]:
        """Get main competitions for a given year.

        Endpoint: GET /common/getMainCompetition?year=YYYY

        Args:
            year: Season year (e.g., 2024 for 2024-25 season)

        Returns:
            List of competition objects with fields:
            - id: Internal database ID
            - competition_id: UUID
            - external_id: Integer ID (e.g., 302, 303)
            - name: Competition name
            - division: Division details
            - etc.

        Example:
            >>> comps = client.get_main_competitions(year=2024)
            >>> for c in comps:
            ...     print(f"{c['name']}: external_id={c['external_id']}")
            Betclic ÉLITE: external_id=302
        """
        logger.info(f"Fetching main competitions for year={year}")
        return self._get("/common/getMainCompetition", params={"year": year})

    def get_division_competitions_by_year(
        self,
        year: int,
        division_external_id: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get competitions for a specific division and year.

        Endpoint: GET /common/getDivisionCompetitionByYear

        Useful for filtering to Betclic ÉLITE (division_external_id=1) vs
        lower divisions.

        Args:
            year: Season year
            division_external_id: Division ID (1=Betclic ÉLITE)

        Returns:
            List of competition objects for the specified division

        Example:
            >>> # Get only Betclic ÉLITE competitions
            >>> elite = client.get_division_competitions_by_year(
            ...     year=2024, division_external_id=1
            ... )
        """
        params = {
            "year": year,
            "division_external_id": division_external_id,
        }
        logger.info(
            f"Fetching division competitions: year={year}, "
            f"division_external_id={division_external_id}"
        )
        return self._get("/common/getDivisionCompetitionByYear", params=params)

    def get_competition_teams(
        self,
        competition_external_id: int,
    ) -> List[Dict[str, Any]]:
        """Get team roster for a competition.

        Endpoint: GET /stats/getCompetitionTeams?competition_external_id=N

        Args:
            competition_external_id: Competition ID (e.g., 302)

        Returns:
            List of team objects with fields:
            - team_id: UUID
            - external_id: Integer team ID
            - name: Team name
            - short_name: Abbreviated name
            - city: City/location
            - logo_url: Team logo
            - etc.

        Example:
            >>> teams = client.get_competition_teams(competition_external_id=302)
            >>> for t in teams:
            ...     print(f"{t['name']} (ID: {t['external_id']})")
        """
        params = {"competition_external_id": competition_external_id}
        logger.info(
            f"Fetching teams for competition_external_id={competition_external_id}"
        )
        return self._get("/stats/getCompetitionTeams", params=params)

    # ========================================
    # Schedule / Calendar Endpoints
    # ========================================

    def get_calendar(
        self,
        from_date: date,
        to_date: date,
    ) -> List[Dict[str, Any]]:
        """Get game schedule for a date range.

        Endpoint: POST /stats/getCalendar

        Args:
            from_date: Start date (inclusive)
            to_date: End date (inclusive)

        Returns:
            List of game objects with fields:
            - match_external_id: Match ID (primary key)
            - match_time_utc: Kickoff time (UTC)
            - match_date: Date string
            - home_team_id / away_team_id: Team IDs
            - competition_external_id: Competition ID
            - round / phase: Stage info
            - status: scheduled, finished, live, etc.

        Example:
            >>> from datetime import date
            >>> games = client.get_calendar(
            ...     from_date=date(2024, 11, 1),
            ...     to_date=date(2024, 11, 30)
            ... )
            >>> print(f"Found {len(games)} games in November 2024")
        """
        payload = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        logger.info(f"Fetching calendar: from={from_date}, to={to_date}")
        return self._post("/stats/getCalendar", json=payload)

    def iter_full_season_calendar(
        self,
        season_start: date,
        season_end: date,
        step_days: int = 31,
    ) -> List[Dict[str, Any]]:
        """Get full season schedule by chunking date ranges.

        Convenience method that repeatedly calls get_calendar() over the
        season interval in chunks to avoid API limits. Automatically
        deduplicates games by match_external_id.

        Args:
            season_start: Season start date
            season_end: Season end date
            step_days: Chunk size in days (default: 31)

        Returns:
            List of all games in the season (deduplicated)

        Example:
            >>> # Get full 2024-25 season
            >>> games = client.iter_full_season_calendar(
            ...     season_start=date(2024, 9, 1),
            ...     season_end=date(2025, 6, 30)
            ... )
            >>> print(f"Full season: {len(games)} games")
        """
        logger.info(
            f"Fetching full season calendar: {season_start} to {season_end} "
            f"(chunk_size={step_days} days)"
        )

        games_by_id: Dict[Any, Dict[str, Any]] = {}
        cursor = season_start

        while cursor <= season_end:
            chunk_end = min(cursor + timedelta(days=step_days), season_end)

            try:
                chunk = self.get_calendar(cursor, chunk_end)
                logger.debug(
                    f"Calendar chunk: {cursor} to {chunk_end} → {len(chunk)} games"
                )

                for g in chunk:
                    # Use match_external_id as primary key for deduplication
                    match_id = g.get("match_external_id") or g.get("external_id")
                    if match_id is None:
                        # Fallback: composite key if IDs missing
                        match_id = (
                            g.get("id"),
                            g.get("match_date"),
                            g.get("home_team_id"),
                            g.get("away_team_id"),
                        )
                    games_by_id[match_id] = g

            except LNBAPIError as e:
                logger.warning(f"Calendar chunk failed: {cursor} to {chunk_end} - {e}")
                # Continue to next chunk even if one fails

            cursor = chunk_end + timedelta(days=1)

            # Be polite: sleep between chunks
            time.sleep(self.retry_sleep)

        logger.info(
            f"Full season calendar complete: {len(games_by_id)} unique games "
            f"(from {season_start} to {season_end})"
        )
        return list(games_by_id.values())

    # ========================================
    # Match Context Endpoints
    # ========================================

    def get_team_comparison(
        self,
        match_external_id: int,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get pre-match team comparison stats.

        Endpoint: GET /stats/getTeamComparison?match_external_id=N

        Args:
            match_external_id: Match ID
            extra_params: Additional query parameters (discovered in DevTools)

        Returns:
            Team comparison object with aggregate stats for home vs away:
            - Offensive/defensive ratings
            - Field goal percentages
            - Rebounds, turnovers, etc.

        Example:
            >>> comp = client.get_team_comparison(match_external_id=28910)
            >>> print(comp['home_team']['offensive_rating'])
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.info(f"Fetching team comparison for match_external_id={match_external_id}")
        return self._get("/stats/getTeamComparison", params=params)

    def get_last_five_home_away(
        self,
        match_external_id: int,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get last 5 home/away games for each team.

        Endpoint: GET /stats/getLastFiveMatchesHomeAway?match_external_id=N

        Args:
            match_external_id: Match ID
            extra_params: Additional query parameters

        Returns:
            Form stats: last 5 home games for home team, last 5 away for away

        Example:
            >>> form = client.get_last_five_home_away(match_external_id=28910)
            >>> print(form['home_team_last_five_home'])
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.info(
            f"Fetching last five home/away for match_external_id={match_external_id}"
        )
        return self._get("/stats/getLastFiveMatchesHomeAway", params=params)

    def get_last_five_h2h(
        self,
        match_external_id: int,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get head-to-head history between two teams.

        Endpoint: GET /stats/getLastFiveMatchesHeadToHead?match_external_id=N

        Args:
            match_external_id: Match ID
            extra_params: Additional query parameters

        Returns:
            Head-to-head history for the matchup

        Example:
            >>> h2h = client.get_last_five_h2h(match_external_id=28910)
            >>> print(h2h['matches'])
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.info(f"Fetching head-to-head for match_external_id={match_external_id}")
        return self._get("/stats/getLastFiveMatchesHeadToHead", params=params)

    def get_match_officials_pregame(
        self,
        match_external_id: int,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get referee crew and officials for a match.

        Endpoint: GET /stats/getMatchOfficialsPreGame?match_external_id=N

        Args:
            match_external_id: Match ID
            extra_params: Additional query parameters

        Returns:
            Officials object with:
            - referees: List of referee objects (name, role, etc.)
            - table_officials: Scorer, timekeeper, etc.

        Example:
            >>> officials = client.get_match_officials_pregame(match_external_id=28910)
            >>> for ref in officials.get('referees', []):
            ...     print(f"{ref['name']}: {ref['role']}")
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.info(f"Fetching officials for match_external_id={match_external_id}")
        return self._get("/stats/getMatchOfficialsPreGame", params=params)

    # ========================================
    # Season Stats / Leaders Endpoints
    # ========================================

    def get_persons_leaders(
        self,
        competition_external_id: int,
        year: int,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get season leaders by stat category.

        Endpoint: GET /stats/getPersonsLeaders

        NOTE: This endpoint requires additional parameters beyond competition
        and year (e.g., category="points", page=1, limit=100). Pass these
        via extra_params after discovering them in DevTools.

        Args:
            competition_external_id: Competition ID
            year: Season year
            extra_params: Required parameters like category, page, limit

        Returns:
            Leaders object with:
            - leaders: List of player stat objects
            - pagination info (if applicable)

        Example:
            >>> leaders = client.get_persons_leaders(
            ...     competition_external_id=302,
            ...     year=2024,
            ...     extra_params={"category": "points", "page": 1, "limit": 50}
            ... )
            >>> for p in leaders.get('leaders', []):
            ...     print(f"{p['name']}: {p['points']}")
        """
        params: Dict[str, Any] = {
            "competition_external_id": competition_external_id,
            "year": year,
        }
        if extra_params:
            params.update(extra_params)

        logger.info(
            f"Fetching persons leaders: competition={competition_external_id}, "
            f"year={year}, extra_params={extra_params}"
        )
        return self._get("/stats/getPersonsLeaders", params=params)

    # ========================================
    # Live Data Endpoints
    # ========================================

    def get_live_match(
        self,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Get current and upcoming live matches.

        Endpoint: GET /stats/getLiveMatch

        Returns:
            List of live/upcoming match objects with fields:
            - match_time_utc: Kickoff time
            - match_date: Date string
            - match_external_id: Match ID
            - status: live, scheduled, etc.
            - score info (if live)

        Example:
            >>> live = client.get_live_match()
            >>> for match in live:
            ...     print(f"{match['home_team']} vs {match['away_team']}")
        """
        params = extra_params or {}
        logger.info("Fetching live matches")
        return self._get("/stats/getLiveMatch", params=params)

    # ========================================
    # Placeholder Endpoints (TODO: DevTools Discovery)
    # ========================================

    def get_match_boxscore(
        self,
        match_external_id: int,
        path: str = "/stats/getMatchBoxScore",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get match boxscore (player_game and team_game stats).

        ⚠️  PLACEHOLDER: Real path unknown until DevTools discovery.

        Once the correct path is discovered (by clicking Boxscore tab in
        Stats Center and inspecting XHR requests), update the `path` parameter.

        Args:
            match_external_id: Match ID
            path: API path (update after DevTools discovery)
            extra_params: Additional query parameters

        Returns:
            Boxscore object with player and team stats

        TODO:
            - Capture real path from DevTools
            - Map response to player_game and team_game schemas
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.warning(
            f"get_match_boxscore is a PLACEHOLDER (path={path}). "
            "Update path after DevTools discovery."
        )
        return self._get(path, params=params)

    def get_match_play_by_play(
        self,
        match_external_id: int,
        path: str = "/stats/getMatchPlayByPlay",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get match play-by-play event stream.

        ⚠️  PLACEHOLDER: Real path unknown until DevTools discovery.

        Once the correct path is discovered (by clicking Play By Play tab
        and inspecting XHR requests), update the `path` parameter.

        Args:
            match_external_id: Match ID
            path: API path (update after DevTools discovery)
            extra_params: Additional query parameters

        Returns:
            Play-by-play object with event list

        TODO:
            - Capture real path from DevTools
            - Map response to pbp_event schema
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.warning(
            f"get_match_play_by_play is a PLACEHOLDER (path={path}). "
            "Update path after DevTools discovery."
        )
        return self._get(path, params=params)

    def get_match_shot_chart(
        self,
        match_external_id: int,
        path: str = "/stats/getMatchShots",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get match shot chart (shot-level x,y coordinates).

        ⚠️  PLACEHOLDER: Real path unknown until DevTools discovery.

        Once the correct path is discovered (by clicking Positions Tirs tab
        and inspecting XHR requests), update the `path` parameter.

        Args:
            match_external_id: Match ID
            path: API path (update after DevTools discovery)
            extra_params: Additional query parameters

        Returns:
            Shot chart object with shot list (x, y, made/missed, etc.)

        TODO:
            - Capture real path from DevTools
            - Map response to shot_event schema
        """
        params: Dict[str, Any] = {"match_external_id": match_external_id}
        if extra_params:
            params.update(extra_params)

        logger.warning(
            f"get_match_shot_chart is a PLACEHOLDER (path={path}). "
            "Update path after DevTools discovery."
        )
        return self._get(path, params=params)


# ========================================
# Stress Test Harness
# ========================================


def stress_test_lnb(
    *,
    end_year: Optional[int] = None,
    seasons_back: int = 3,
    division_external_id: int = 1,
    max_matches_per_season: int = 10,
    persons_leaders_extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Comprehensive stress test for all LNB API endpoints.

    Validates data availability and discovers granularities by:
    1. Fetching available years (getAllYears)
    2. For each recent season:
       - Main competitions (getMainCompetition)
       - Division competitions (getDivisionCompetitionByYear)
       - Teams per competition (getCompetitionTeams)
       - Full season calendar (getCalendar chunked)
       - Sample match context for N games (team comparison, form, h2h, officials)
       - Boxscore/PBP/shots placeholders (expected to fail until paths discovered)
    3. Live matches (getLiveMatch)
    4. Season leaders if extra_params provided (getPersonsLeaders)

    Returns detailed per-endpoint success/failure counts and sample data.

    Args:
        end_year: Latest year to fetch (default: current year)
        seasons_back: How many recent seasons to test (default: 3)
        division_external_id: Division to filter (1=Betclic ÉLITE)
        max_matches_per_season: Sample size for match-level endpoints
        persons_leaders_extra_params: Extra params for getPersonsLeaders
            (e.g., {"category": "points", "page": 1, "limit": 50})

    Returns:
        Dictionary with:
        - target_years: List of years tested
        - per_year: Detailed results per season
        - endpoint_stats: {endpoint_name: {ok: N, failed: M}}
        - live_matches_sample: Sample of live matches

    Example:
        >>> results = stress_test_lnb(
        ...     seasons_back=2,
        ...     max_matches_per_season=5,
        ...     persons_leaders_extra_params={"category": "points", "page": 1}
        ... )
        >>> print(results["endpoint_stats"])
        {
            "getAllYears": {"ok": 1, "failed": 0},
            "getMainCompetition": {"ok": 2, "failed": 0},
            ...
        }

    Usage:
        Run as script: python -m cbb_data.fetchers.lnb_api
    """
    logger.info("=" * 60)
    logger.info("LNB API Stress Test - Starting")
    logger.info("=" * 60)

    client = LNBClient()
    stats: Dict[str, LNBRequestStats] = {}

    def record(endpoint: str, success: bool) -> None:
        """Record endpoint success/failure."""
        s = stats.setdefault(endpoint, LNBRequestStats())
        if success:
            s.record_ok()
        else:
            s.record_failed()

    # 1) Discover available years
    if end_year is None:
        end_year = datetime.utcnow().year

    logger.info(f"\n[1/4] Discovering available years (end_year={end_year})...")
    try:
        years_raw = client.get_all_years(end_year=end_year)
        record("getAllYears", True)
        logger.info(f"✅ getAllYears: {len(years_raw)} seasons")
    except Exception as e:
        years_raw = []
        record("getAllYears", False)
        logger.error(f"❌ getAllYears failed: {e}")

    # Extract integer years
    discovered_years: List[int] = []
    for y in years_raw:
        val = y.get("year") or y.get("end_year") or y.get("season")
        if isinstance(val, int):
            discovered_years.append(val)

    if not discovered_years:
        # Fallback: naive range if API fails
        discovered_years = list(range(end_year - seasons_back + 1, end_year + 1))
        logger.warning(f"Using fallback years: {discovered_years}")

    discovered_years = sorted(set(discovered_years))
    target_years = [y for y in discovered_years if y <= end_year][-seasons_back:]

    results: Dict[str, Any] = {
        "target_years": target_years,
        "per_year": {},
        "endpoint_stats": {},
    }

    logger.info(f"Target years for testing: {target_years}")

    # 2) Loop through years → competitions → teams → games
    logger.info(f"\n[2/4] Testing competitions, teams, and games...")
    for year_idx, year in enumerate(target_years, 1):
        logger.info(f"\n--- Year {year} ({year_idx}/{len(target_years)}) ---")

        year_summary: Dict[str, Any] = {
            "competitions": [],
            "teams_per_competition": {},
            "matches_sampled": 0,
        }

        # 2A) Main competitions
        try:
            main_comps = client.get_main_competitions(year)
            record("getMainCompetition", True)
            logger.info(f"✅ getMainCompetition: {len(main_comps)} competitions")
        except Exception as e:
            main_comps = []
            record("getMainCompetition", False)
            logger.error(f"❌ getMainCompetition failed: {e}")

        # 2B) Division competitions
        try:
            div_comps = client.get_division_competitions_by_year(
                year, division_external_id=division_external_id
            )
            record("getDivisionCompetitionByYear", True)
            logger.info(
                f"✅ getDivisionCompetitionByYear: {len(div_comps)} competitions"
            )
        except Exception as e:
            div_comps = []
            record("getDivisionCompetitionByYear", False)
            logger.error(f"❌ getDivisionCompetitionByYear failed: {e}")

        year_summary["competitions"] = {
            "main": main_comps,
            "division": div_comps,
        }

        # 2C) Teams + games for each competition
        for comp_idx, comp in enumerate(main_comps, 1):
            comp_ext = comp.get("external_id")
            comp_name = comp.get("name", "Unknown")
            if comp_ext is None:
                logger.warning(f"Skipping competition (no external_id): {comp}")
                continue

            logger.info(
                f"\n  Competition {comp_idx}/{len(main_comps)}: "
                f"{comp_name} (external_id={comp_ext})"
            )

            # Teams
            try:
                teams = client.get_competition_teams(comp_ext)
                record("getCompetitionTeams", True)
                logger.info(f"  ✅ getCompetitionTeams: {len(teams)} teams")
            except Exception as e:
                teams = []
                record("getCompetitionTeams", False)
                logger.error(f"  ❌ getCompetitionTeams failed: {e}")

            year_summary["teams_per_competition"][comp_ext] = {
                "competition": comp,
                "teams_count": len(teams),
            }

            # Calendar (assume typical European season: Aug-Jul)
            season_start = date(year, 8, 1)
            season_end = date(year + 1, 7, 31)

            try:
                games = client.iter_full_season_calendar(season_start, season_end)
                record("getCalendar", True)
                logger.info(f"  ✅ getCalendar: {len(games)} games")
            except Exception as e:
                games = []
                record("getCalendar", False)
                logger.error(f"  ❌ getCalendar failed: {e}")

            # Sample K matches per competition for match-level endpoints
            sample_games = games[:max_matches_per_season]
            year_summary["teams_per_competition"][comp_ext]["sample_games_count"] = len(
                sample_games
            )
            year_summary["matches_sampled"] += len(sample_games)

            logger.info(
                f"  Testing match-level endpoints on {len(sample_games)} sample games..."
            )

            for game_idx, g in enumerate(sample_games, 1):
                match_external_id = g.get("match_external_id") or g.get("external_id")
                if match_external_id is None:
                    logger.warning(f"  Skipping game (no match_external_id): {g}")
                    continue

                logger.debug(
                    f"    Game {game_idx}/{len(sample_games)}: "
                    f"match_external_id={match_external_id}"
                )

                # Team comparison
                try:
                    _ = client.get_team_comparison(match_external_id)
                    record("getTeamComparison", True)
                except Exception as e:
                    record("getTeamComparison", False)
                    logger.debug(f"    ❌ getTeamComparison failed: {e}")

                # Last five home/away
                try:
                    _ = client.get_last_five_home_away(match_external_id)
                    record("getLastFiveMatchesHomeAway", True)
                except Exception as e:
                    record("getLastFiveMatchesHomeAway", False)
                    logger.debug(f"    ❌ getLastFiveMatchesHomeAway failed: {e}")

                # Last five H2H
                try:
                    _ = client.get_last_five_h2h(match_external_id)
                    record("getLastFiveMatchesHeadToHead", True)
                except Exception as e:
                    record("getLastFiveMatchesHeadToHead", False)
                    logger.debug(f"    ❌ getLastFiveMatchesHeadToHead failed: {e}")

                # Officials
                try:
                    _ = client.get_match_officials_pregame(match_external_id)
                    record("getMatchOfficialsPreGame", True)
                except Exception as e:
                    record("getMatchOfficialsPreGame", False)
                    logger.debug(f"    ❌ getMatchOfficialsPreGame failed: {e}")

                # Placeholders (expected to fail until paths discovered)
                try:
                    _ = client.get_match_boxscore(match_external_id)
                    record("getMatchBoxScore", True)
                except Exception:
                    record("getMatchBoxScore", False)

                try:
                    _ = client.get_match_play_by_play(match_external_id)
                    record("getMatchPlayByPlay", False)
                except Exception:
                    record("getMatchPlayByPlay", False)

                try:
                    _ = client.get_match_shot_chart(match_external_id)
                    record("getMatchShots", False)
                except Exception:
                    record("getMatchShots", False)

            logger.info(
                f"  Completed {len(sample_games)} sample games for {comp_name}"
            )

        # 2D) Person leaders (once per year)
        if persons_leaders_extra_params is not None and main_comps:
            comp_ext = main_comps[0].get("external_id")
            if comp_ext is not None:
                logger.info(
                    f"\n  Testing getPersonsLeaders for year={year}, "
                    f"competition={comp_ext}..."
                )
                try:
                    _ = client.get_persons_leaders(
                        competition_external_id=comp_ext,
                        year=year,
                        extra_params=persons_leaders_extra_params,
                    )
                    record("getPersonsLeaders", True)
                    logger.info(f"  ✅ getPersonsLeaders")
                except Exception as e:
                    record("getPersonsLeaders", False)
                    logger.error(f"  ❌ getPersonsLeaders failed: {e}")

        results["per_year"][year] = year_summary
        logger.info(f"--- Year {year} complete ---")

    # 3) Live matches
    logger.info(f"\n[3/4] Testing live matches...")
    try:
        live = client.get_live_match()
        results["live_matches_sample"] = live[:5]
        record("getLiveMatch", True)
        logger.info(f"✅ getLiveMatch: {len(live)} live/upcoming games")
    except Exception as e:
        results["live_matches_sample"] = []
        record("getLiveMatch", False)
        logger.error(f"❌ getLiveMatch failed: {e}")

    # 4) Finalize stats
    logger.info(f"\n[4/4] Finalizing results...")
    results["endpoint_stats"] = {name: s.as_dict() for name, s in stats.items()}

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("LNB API Stress Test - COMPLETE")
    logger.info("=" * 60)
    logger.info("\nEndpoint Health Summary:")
    logger.info("-" * 60)

    for endpoint, counts in sorted(results["endpoint_stats"].items()):
        ok = counts["ok"]
        failed = counts["failed"]
        total = ok + failed
        status = "✅" if failed == 0 else "⚠️" if ok > 0 else "❌"
        logger.info(f"{status} {endpoint:40s} {ok:3d} OK / {failed:3d} FAIL ({total:3d} total)")

    logger.info("-" * 60)
    logger.info(f"Target years tested: {results['target_years']}")
    logger.info(f"Total matches sampled: {sum(y.get('matches_sampled', 0) for y in results['per_year'].values())}")
    logger.info("=" * 60)

    return results


# ========================================
# CLI Entry Point
# ========================================

if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 60)
    print("LNB API Stress Test - Standalone Execution")
    print("=" * 60)
    print("\nThis will test all known LNB API endpoints across multiple seasons.")
    print("Placeholder endpoints (boxscore, PBP, shots) are expected to fail.\n")

    # Run stress test with reasonable defaults
    summary = stress_test_lnb(
        seasons_back=2,  # Test last 2 seasons
        division_external_id=1,  # Betclic ÉLITE only
        max_matches_per_season=5,  # Sample 5 games per season
        # Uncomment to test getPersonsLeaders (requires extra params from DevTools):
        # persons_leaders_extra_params={"category": "points", "page": 1, "limit": 50},
    )

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    print(f"\nTarget years: {summary['target_years']}")
    print(f"\nEndpoint statistics:")
    for endpoint, counts in sorted(summary["endpoint_stats"].items()):
        print(f"  {endpoint}: {counts}")

    print(f"\nLive matches sample: {len(summary['live_matches_sample'])} games")

    print("\n" + "=" * 60)
    print("Stress test complete! See logs above for details.")
    print("=" * 60)
