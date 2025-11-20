"""LNB Atrium Sports API Integration

This module provides access to LNB Pro A data via the Atrium Sports API,
which is the third-party stats provider for LNB.

The Atrium API provides fixture detail + play-by-play data in a single endpoint,
making it the canonical source for:
- Fixture metadata (teams, venue, times, competition)
- Per-period scores
- Full play-by-play with coordinates
- Shot locations (derived from PBP filtering)

Key Advantages over deprecated LNB endpoints:
1. Single endpoint returns all data (no need for multiple calls)
2. Confirmed working and stable (verified 2025-11-15)
3. Includes shot coordinates in PBP (no separate shots endpoint needed)
4. Provides per-period scores for validation

Architecture:
- fetch_fixture_detail_and_pbp(): Main entry point - fetches raw JSON
- parse_fixture_metadata(): Extract fixture/competition/team metadata
- parse_pbp_events(): Extract all play-by-play events with coordinates
- parse_shots_from_pbp(): Filter PBP for shots (2pt, 3pt, FT)
- validate_fixture_scores(): Verify PBP scores match official scores

Created: 2025-11-15
Reference: Atrium Sports API fixture detail endpoint
"""

from __future__ import annotations

import base64
import json
import logging
import re
import zlib
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from ..utils.rate_limiter import get_source_limiter
from .base import cached_dataframe, retry_on_error

logger = logging.getLogger(__name__)

# Get rate limiter
rate_limiter = get_source_limiter()

# Atrium Sports API
ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
ATRIUM_FIXTURE_DETAIL_URL = f"{ATRIUM_API_BASE}/v1/embed/12/fixture_detail"


@dataclass
class FixtureMetadata:
    """Fixture metadata from Atrium API"""

    # Primary keys
    fixture_uuid: str  # Atrium UUID
    fixture_external_id: str  # LNB numeric ID
    season_id: str
    competition_id: str

    # Teams
    home_team_id: str
    away_team_id: str
    home_team_code: str
    away_team_code: str
    home_team_name: str
    away_team_name: str
    home_team_logo: str | None
    away_team_logo: str | None

    # Scores
    home_score: int
    away_score: int

    # Times
    start_time_utc: str
    start_time_local: str
    timezone: str

    # Venue
    venue_name: str
    venue_id: str

    # Status
    status: str
    status_label: str

    # Rules/Profile
    num_periods: int
    period_length_minutes: int
    overtime_length_minutes: int
    shot_clock_seconds: int

    # Additional metadata
    fixture_type: str  # REGULAR, PLAYOFF, etc.
    competition_name: str
    season_name: str
    division: str = ""  # Division ID (1=ProA, 2=Elite2, 3=Espoirs Elite, 4=Espoirs ProB)


@dataclass
class PBPEvent:
    """Single play-by-play event"""

    # Keys
    fixture_uuid: str
    event_id: str
    period_id: int

    # Time
    clock_iso: str  # ISO 8601 duration (PT9M46S)
    clock_seconds: int  # Seconds remaining in period

    # Entities
    team_id: str
    player_id: str | None
    player_bib: str | None
    player_name: str | None

    # Event details
    event_type: str  # 2pt, 3pt, freeThrow, turnover, etc.
    event_sub_type: str | None  # pullUpJumpShot, badPass, etc.
    description: str  # Human-readable French description
    success: bool | None  # For shots/FTs
    success_string: str | None  # réussi, raté

    # Location
    x: float | None
    y: float | None

    # Score state
    home_score: int
    away_score: int


@dataclass
class ShotEvent:
    """Shot event derived from PBP"""

    # Keys
    fixture_uuid: str
    event_id: str
    period_id: int

    # Time
    clock_seconds: int

    # Entities
    team_id: str
    player_id: str | None
    player_name: str | None

    # Shot details
    shot_value: int  # 1, 2, or 3
    shot_type: str  # From eventSubType
    made: bool
    x: float
    y: float

    # Context
    home_score: int
    away_score: int


def parse_iso_duration_to_seconds(iso_duration: str) -> int:
    """
    Convert ISO 8601 duration to seconds.

    Examples:
        "PT9M46S" -> 586 seconds
        "PT1M23S" -> 83 seconds
        "PT45S" -> 45 seconds
        "PT10M" -> 600 seconds

    Args:
        iso_duration: ISO 8601 duration string (PTnMnS format)

    Returns:
        Total seconds
    """
    if not iso_duration or iso_duration == "PT0S":
        return 0

    # Remove PT prefix
    duration = iso_duration.replace("PT", "")

    # Extract minutes and seconds
    minutes = 0
    seconds = 0

    # Match patterns like "9M46S", "1M23S", "45S", "10M"
    m_match = re.search(r"(\d+)M", duration)
    s_match = re.search(r"(\d+)S", duration)

    if m_match:
        minutes = int(m_match.group(1))
    if s_match:
        seconds = int(s_match.group(1))

    return minutes * 60 + seconds


def _create_atrium_state(fixture_id: str, view: str = "pbp") -> str:
    """Create compressed state parameter for Atrium Sports API

    Args:
        fixture_id: Game UUID from LNB's getMatchDetails API
        view: View type ("pbp" for play-by-play, "shot_chart" for shots)

    Returns:
        Base64url-encoded, zlib-compressed state parameter

    Example:
        >>> state = _create_atrium_state("3522345e-3362-11f0-b97d-7be2bdc7a840", "pbp")
        >>> # Returns: "eJyrVqpSslIqSCpQ0lFKA7KMTY2..."
    """
    state_obj = {
        "z": view,  # View type: "pbp" or "shot_chart"
        "f": fixture_id,  # Fixture ID (game UUID)
    }

    # Convert to JSON and compress
    json_str = json.dumps(state_obj, separators=(",", ":"))
    compressed = zlib.compress(json_str.encode("utf-8"))

    # Base64url encode (replace + with -, / with _, remove padding)
    encoded = base64.b64encode(compressed).decode("ascii")
    encoded = encoded.replace("+", "-").replace("/", "_").rstrip("=")

    return encoded


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
def fetch_fixture_detail_and_pbp(fixture_uuid: str) -> dict[str, Any]:
    """
    Fetch complete fixture detail + PBP from Atrium API.

    This is the canonical source for all LNB fixture data, returning:
    - Fixture metadata (teams, venue, times, competition)
    - Per-period scores
    - Full play-by-play with coordinates
    - Shot locations (embedded in PBP)

    Args:
        fixture_uuid: Atrium fixture UUID (e.g., "0d2989af-6715-11f0-b609-27e6e78614e1")

    Returns:
        Complete fixture detail JSON payload

    Raises:
        requests.HTTPError: If API returns non-200 status
        ValueError: If response is not valid JSON

    Example:
        >>> fixture_data = fetch_fixture_detail_and_pbp("0d2989af-6715-11f0-b609-27e6e78614e1")
        >>> fixture_id = fixture_data["fixture"]["id"]
        >>> pbp_periods = fixture_data["pbp"]
    """
    rate_limiter.acquire("lnb_atrium")

    logger.info(f"Fetching fixture detail from Atrium API: {fixture_uuid}")

    # Create state parameter for PBP view
    # NOTE: This is required to get PBP data (as of November 2025)
    state = _create_atrium_state(fixture_uuid, view="pbp")

    # Fixed: Use "fixtureId" not "fid" + added required "state" parameter
    params = {"fixtureId": fixture_uuid, "state": state}

    # Use headers from working test script
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    response = requests.get(
        ATRIUM_FIXTURE_DETAIL_URL,
        params=params,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    # Verify response structure
    # The API returns: {"data": {"banner": {"fixture": ..., "competition": ...}, "pbp": ..., "shotChart": ...}}
    if "data" not in payload:
        raise ValueError("Invalid Atrium API response (missing 'data' key)")

    data = payload["data"]

    # Check for fixture data in banner
    if "banner" in data and "fixture" in data["banner"]:
        fixture_id = data["banner"]["fixture"].get("id", fixture_uuid)
        logger.info(f"Successfully fetched fixture {fixture_id}")
    else:
        # Log warning but don't fail - might still have pbp/shotChart
        logger.warning("Response missing banner.fixture structure")

    return data  # Return data (not payload) for easier parsing


def parse_fixture_metadata(payload: dict[str, Any], division: str = "") -> FixtureMetadata:
    """
    Extract fixture metadata from Atrium API payload.

    Parses:
    - Competition and season info
    - Team details (IDs, names, codes, logos)
    - Venue and timing
    - Game rules (periods, shot clock, etc.)
    - Final scores

    Args:
        payload: Raw JSON from fetch_fixture_detail_and_pbp()
        division: Division ID (1=ProA, 2=Elite2, 3=Espoirs Elite, 4=Espoirs ProB)

    Returns:
        FixtureMetadata object with all parsed fields

    Example:
        >>> payload = fetch_fixture_detail_and_pbp("...")
        >>> metadata = parse_fixture_metadata(payload, division="2")
        >>> print(f"{metadata.home_team_name} vs {metadata.away_team_name}")
    """
    fixture = payload["fixture"]
    banner = payload.get("banner", {})
    # banner_fixture = banner.get("fixture", {})  # Not currently used
    competition = banner.get("competition", {})
    season = banner.get("season", {})

    # Extract competitors (teams)
    competitors = fixture.get("competitors", [])
    home_team: dict = next((c for c in competitors if c.get("isHome")), {})
    away_team: dict = next((c for c in competitors if not c.get("isHome")), {})

    # Extract profile/rules (from data.fixture.profile, not banner)
    profile = fixture.get("profile", {})

    return FixtureMetadata(
        # Primary keys (fixtureId not id)
        fixture_uuid=fixture["fixtureId"],
        fixture_external_id=str(fixture.get("externalId", "")),
        season_id=fixture.get("seasonId", ""),
        competition_id=competition.get("id", ""),
        # Teams
        home_team_id=home_team.get("entityId", ""),
        away_team_id=away_team.get("entityId", ""),
        home_team_code=home_team.get("code", ""),
        away_team_code=away_team.get("code", ""),
        home_team_name=home_team.get("name", ""),
        away_team_name=away_team.get("name", ""),
        home_team_logo=home_team.get("logo"),
        away_team_logo=away_team.get("logo"),
        # Scores (handle None for scheduled games)
        home_score=int(home_team.get("score") or 0),
        away_score=int(away_team.get("score") or 0),
        # Times
        start_time_utc=fixture.get("startTimeUTC", ""),
        start_time_local=fixture.get("startTimeLocal", ""),
        timezone=fixture.get("timezone", ""),
        # Venue
        venue_name=fixture.get("venue", ""),
        venue_id=fixture.get("venueId", ""),
        # Status
        status=fixture.get("status", ""),
        status_label=fixture.get("statusLabel", ""),
        # Rules
        num_periods=profile.get("numberOfPeriods", 4),
        period_length_minutes=profile.get("periodLength", 10),
        overtime_length_minutes=profile.get("overtimeLength", 5),
        shot_clock_seconds=profile.get("shotClock", 24),
        # Additional
        fixture_type=fixture.get("fixtureType", ""),
        competition_name=competition.get("name", ""),
        season_name=season.get("name", ""),
        division=division,
    )


def parse_pbp_events(payload: dict[str, Any], fixture_uuid: str) -> list[PBPEvent]:
    """
    Extract all play-by-play events from Atrium API payload.

    Parses PBP structure:
    - Each period has a list of events
    - Events include type, subtype, player, team, coordinates
    - Score state captured at each event

    Args:
        payload: Raw JSON from fetch_fixture_detail_and_pbp()
        fixture_uuid: Fixture UUID for event keys

    Returns:
        List of PBPEvent objects (one per event)

    Example:
        >>> payload = fetch_fixture_detail_and_pbp("...")
        >>> events = parse_pbp_events(payload, "...")
        >>> shots = [e for e in events if e.event_type in ("2pt", "3pt")]
    """
    pbp_data = payload.get("pbp", {})
    fixture = payload["fixture"]

    # Get team IDs for score mapping
    competitors = fixture.get("competitors", [])
    home_team: dict = next((c for c in competitors if c.get("isHome")), {})
    away_team: dict = next((c for c in competitors if not c.get("isHome")), {})
    home_team_id = home_team.get("entityId", "")
    away_team_id = away_team.get("entityId", "")

    events = []

    for period_key, period_obj in pbp_data.items():
        period_id = int(period_key)
        period_events = period_obj.get("events", [])

        for event_data in period_events:
            # Parse clock to seconds
            clock_iso = event_data.get("clock", "PT0S")
            clock_seconds = parse_iso_duration_to_seconds(clock_iso)

            # Extract scores
            scores = event_data.get("scores", {})
            home_score = int(scores.get(home_team_id, 0))
            away_score = int(scores.get(away_team_id, 0))

            # Create event
            event = PBPEvent(
                fixture_uuid=fixture_uuid,
                event_id=event_data.get("eventId", ""),
                period_id=period_id,
                clock_iso=clock_iso,
                clock_seconds=clock_seconds,
                team_id=event_data.get("entityId", ""),
                player_id=event_data.get("personId"),
                player_bib=event_data.get("bib"),
                player_name=event_data.get("name"),
                event_type=event_data.get("eventType", ""),
                event_sub_type=event_data.get("eventSubType"),
                description=event_data.get("desc", ""),
                success=event_data.get("success"),
                success_string=event_data.get("successString"),
                x=event_data.get("x"),
                y=event_data.get("y"),
                home_score=home_score,
                away_score=away_score,
            )

            events.append(event)

    logger.info(f"Parsed {len(events)} PBP events from fixture {fixture_uuid}")

    return events


def parse_shots_from_pbp(events: list[PBPEvent]) -> list[ShotEvent]:
    """
    Extract shot events from PBP events.

    Filters PBP for shot events (2pt, 3pt, freeThrow) and converts
    to dedicated shot records with location data.

    Args:
        events: List of PBPEvent objects from parse_pbp_events()

    Returns:
        List of ShotEvent objects (one per shot attempt)

    Example:
        >>> pbp_events = parse_pbp_events(payload, fixture_uuid)
        >>> shots = parse_shots_from_pbp(pbp_events)
        >>> made_threes = [s for s in shots if s.shot_value == 3 and s.made]
    """
    shots = []

    for event in events:
        # Only process shot events
        if event.event_type not in ("2pt", "3pt", "freeThrow"):
            continue

        # Determine shot value
        if event.event_type == "freeThrow":
            shot_value = 1
        elif event.event_type == "2pt":
            shot_value = 2
        elif event.event_type == "3pt":
            shot_value = 3
        else:
            continue  # Skip non-shot events

        # For FTs without coordinates, skip or use default
        if event.x is None and event.event_type == "freeThrow":
            # FTs typically don't have coordinates
            x, y = 0.0, 0.0
        elif event.x is None or event.y is None:
            # Skip shots without coordinates
            continue
        else:
            x, y = event.x, event.y

        shot = ShotEvent(
            fixture_uuid=event.fixture_uuid,
            event_id=event.event_id,
            period_id=event.period_id,
            clock_seconds=event.clock_seconds,
            team_id=event.team_id,
            player_id=event.player_id,
            player_name=event.player_name,
            shot_value=shot_value,
            shot_type=event.event_sub_type or "",
            made=event.success or False,
            x=x,
            y=y,
            home_score=event.home_score,
            away_score=event.away_score,
        )

        shots.append(shot)

    logger.info(f"Extracted {len(shots)} shots from {len(events)} PBP events")

    return shots


def validate_fixture_scores(
    payload: dict[str, Any], pbp_events: list[PBPEvent]
) -> tuple[bool, list[str]]:
    """
    Validate that PBP-derived scores match official fixture scores.

    Checks:
    1. Final scores from PBP match competitor scores
    2. Per-period scores from PBP match periodData
    3. Sum of period scores equals final score

    Args:
        payload: Raw fixture detail payload
        pbp_events: Parsed PBP events

    Returns:
        (is_valid, list of error messages)

    Example:
        >>> payload = fetch_fixture_detail_and_pbp("...")
        >>> events = parse_pbp_events(payload, "...")
        >>> valid, errors = validate_fixture_scores(payload, events)
        >>> if not valid:
        ...     print(f"Score validation failed: {errors}")
    """
    errors = []

    fixture = payload["fixture"]
    # periodData is in data.fixture, not banner.fixture
    period_data = fixture.get("periodData", {})

    # Get official scores
    competitors = fixture.get("competitors", [])
    home_team: dict = next((c for c in competitors if c.get("isHome")), {})
    away_team: dict = next((c for c in competitors if not c.get("isHome")), {})

    # Handle None scores for scheduled games
    official_home_score = int(home_team.get("score") or 0)
    official_away_score = int(away_team.get("score") or 0)

    home_team_id = home_team.get("entityId", "")
    # away_team_id = away_team.get("entityId", "")  # Not currently used

    # Get final scores from PBP (last event's score state)
    if pbp_events:
        last_event = pbp_events[-1]
        pbp_home_score = last_event.home_score
        pbp_away_score = last_event.away_score

        # Check final score match
        if pbp_home_score != official_home_score:
            errors.append(
                f"Home score mismatch: PBP={pbp_home_score}, Official={official_home_score}"
            )

        if pbp_away_score != official_away_score:
            errors.append(
                f"Away score mismatch: PBP={pbp_away_score}, Official={official_away_score}"
            )

    # Check per-period scores
    team_scores = period_data.get("teamScores", {})

    for team_id, period_scores in team_scores.items():
        team_name = "Home" if team_id == home_team_id else "Away"

        # Sum period scores
        total_from_periods = sum(int(ps.get("score", 0)) for ps in period_scores)

        # Compare with official
        official_score = official_home_score if team_id == home_team_id else official_away_score

        if total_from_periods != official_score:
            errors.append(
                f"{team_name} period sum mismatch: Sum={total_from_periods}, Official={official_score}"
            )

    is_valid = len(errors) == 0

    if is_valid:
        logger.info("Score validation passed")
    else:
        logger.warning(f"Score validation failed with {len(errors)} errors: {errors}")

    return is_valid, errors


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_fixture_metadata_df(fixture_uuid: str) -> pd.DataFrame:
    """
    Fetch and parse fixture metadata as DataFrame.

    Wrapper around fetch_fixture_detail_and_pbp() and parse_fixture_metadata()
    that returns a single-row DataFrame for easy concatenation.

    Args:
        fixture_uuid: Atrium fixture UUID

    Returns:
        DataFrame with one row containing fixture metadata

    Example:
        >>> df = fetch_lnb_fixture_metadata_df("0d2989af-6715-11f0-b609-27e6e78614e1")
        >>> print(df[["home_team_name", "away_team_name", "home_score", "away_score"]])
    """
    payload = fetch_fixture_detail_and_pbp(fixture_uuid)
    metadata = parse_fixture_metadata(payload)

    # Convert to DataFrame
    return pd.DataFrame(
        [
            {
                "fixture_uuid": metadata.fixture_uuid,
                "fixture_external_id": metadata.fixture_external_id,
                "season_id": metadata.season_id,
                "competition_id": metadata.competition_id,
                "home_team_id": metadata.home_team_id,
                "away_team_id": metadata.away_team_id,
                "home_team_code": metadata.home_team_code,
                "away_team_code": metadata.away_team_code,
                "home_team_name": metadata.home_team_name,
                "away_team_name": metadata.away_team_name,
                "home_score": metadata.home_score,
                "away_score": metadata.away_score,
                "start_time_utc": metadata.start_time_utc,
                "start_time_local": metadata.start_time_local,
                "timezone": metadata.timezone,
                "venue_name": metadata.venue_name,
                "venue_id": metadata.venue_id,
                "status": metadata.status,
                "status_label": metadata.status_label,
                "num_periods": metadata.num_periods,
                "period_length_minutes": metadata.period_length_minutes,
                "fixture_type": metadata.fixture_type,
                "competition_name": metadata.competition_name,
                "season_name": metadata.season_name,
            }
        ]
    )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_pbp_df(fixture_uuid: str) -> pd.DataFrame:
    """
    Fetch and parse play-by-play events as DataFrame.

    Wrapper around fetch_fixture_detail_and_pbp() and parse_pbp_events()
    that returns a DataFrame of all PBP events for the fixture.

    Args:
        fixture_uuid: Atrium fixture UUID

    Returns:
        DataFrame with one row per PBP event

    Example:
        >>> df = fetch_lnb_pbp_df("0d2989af-6715-11f0-b609-27e6e78614e1")
        >>> print(df[["period_id", "clock_seconds", "event_type", "player_name"]])
    """
    payload = fetch_fixture_detail_and_pbp(fixture_uuid)
    events = parse_pbp_events(payload, fixture_uuid)

    # Convert to DataFrame
    return pd.DataFrame(
        [
            {
                "fixture_uuid": e.fixture_uuid,
                "event_id": e.event_id,
                "period_id": e.period_id,
                "clock_iso": e.clock_iso,
                "clock_seconds": e.clock_seconds,
                "team_id": e.team_id,
                "player_id": e.player_id,
                "player_bib": e.player_bib,
                "player_name": e.player_name,
                "event_type": e.event_type,
                "event_sub_type": e.event_sub_type,
                "description": e.description,
                "success": e.success,
                "success_string": e.success_string,
                "x": e.x,
                "y": e.y,
                "home_score": e.home_score,
                "away_score": e.away_score,
            }
            for e in events
        ]
    )


@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_shots_df(fixture_uuid: str) -> pd.DataFrame:
    """
    Fetch and parse shot events as DataFrame.

    Wrapper that fetches fixture detail, parses PBP, filters for shots,
    and returns a DataFrame of shot events.

    Args:
        fixture_uuid: Atrium fixture UUID

    Returns:
        DataFrame with one row per shot attempt

    Example:
        >>> df = fetch_lnb_shots_df("0d2989af-6715-11f0-b609-27e6e78614e1")
        >>> print(df[["player_name", "shot_value", "made", "x", "y"]])
    """
    payload = fetch_fixture_detail_and_pbp(fixture_uuid)
    pbp_events = parse_pbp_events(payload, fixture_uuid)
    shots = parse_shots_from_pbp(pbp_events)

    # Convert to DataFrame
    return pd.DataFrame(
        [
            {
                "fixture_uuid": s.fixture_uuid,
                "event_id": s.event_id,
                "period_id": s.period_id,
                "clock_seconds": s.clock_seconds,
                "team_id": s.team_id,
                "player_id": s.player_id,
                "player_name": s.player_name,
                "shot_value": s.shot_value,
                "shot_type": s.shot_type,
                "made": s.made,
                "x": s.x,
                "y": s.y,
                "home_score": s.home_score,
                "away_score": s.away_score,
            }
            for s in shots
        ]
    )
