#!/usr/bin/env python3
"""Helper function to fetch fixture metadata from Atrium API

This module provides a reusable function to fetch detailed fixture metadata
including game dates, team names, and status from the Atrium Sports API.

Created: 2025-11-16
Purpose: Populate game_date field in game index to enable date-based filtering
"""

from __future__ import annotations

from typing import Any

import requests


def fetch_fixtures_metadata(
    competition_id: str, season_id: str, timeout: int = 15
) -> list[dict[str, Any]]:
    """Fetch fixture metadata from Atrium API

    This function retrieves detailed information about all fixtures for a given
    season, including game dates, team names, scores, and status.

    Args:
        competition_id: Atrium competition UUID
        season_id: Atrium season UUID
        timeout: Request timeout in seconds

    Returns:
        List of fixture metadata dicts with keys:
            - fixture_id: Game UUID
            - game_date: ISO format date string (from startTimeLocal)
            - home_team_name: Home team name
            - away_team_name: Away team name
            - status: Game status (CONFIRMED, SCHEDULED, etc.)
            - home_score: Final home score (if available)
            - away_score: Final away score (if available)

    Raises:
        requests.RequestException: If API call fails
        ValueError: If response format is invalid

    Example:
        >>> metadata = fetch_fixtures_metadata(comp_id, season_id)
        >>> for fixture in metadata:
        ...     print(f"{fixture['game_date']}: {fixture['home_team_name']} vs {fixture['away_team_name']}")
    """
    url = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixtures"
    params = {
        "competitionId": competition_id,
        "seasonId": season_id,
    }

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        fixtures = data.get("data", {}).get("fixtures", [])

        if not isinstance(fixtures, list):
            raise ValueError(f"Expected fixtures array, got {type(fixtures)}")

        # Extract metadata from each fixture
        fixtures_metadata = []

        for fixture in fixtures:
            # Extract competitor data (home/away teams)
            competitors = fixture.get("competitors", [])
            home_team = next((c for c in competitors if c.get("isHome")), {})
            away_team = next((c for c in competitors if not c.get("isHome")), {})

            # Parse game date from startTimeLocal (format: "2023-05-16T20:00:00")
            # We only need the date part for filtering
            start_time_local = fixture.get("startTimeLocal", "")
            game_date = (
                start_time_local.split("T")[0] if "T" in start_time_local else start_time_local
            )

            # Extract status
            status_obj = fixture.get("status", {})
            status = status_obj.get("value", "UNKNOWN")

            fixture_meta = {
                "fixture_id": fixture.get("fixtureId", ""),
                "game_date": game_date,  # ISO format date: "2023-05-16"
                "home_team_name": home_team.get("name", ""),
                "away_team_name": away_team.get("name", ""),
                "home_team_id": home_team.get("entityId", ""),
                "away_team_id": away_team.get("entityId", ""),
                "status": status,
                "home_score": home_team.get("score", ""),
                "away_score": away_team.get("score", ""),
            }

            fixtures_metadata.append(fixture_meta)

        return fixtures_metadata

    except requests.Timeout as exc:
        raise requests.RequestException(f"Request timeout after {timeout}s") from exc

    except requests.RequestException as exc:
        raise requests.RequestException(f"API request failed: {exc}") from exc

    except (KeyError, ValueError) as exc:
        raise ValueError(f"Failed to parse response: {exc}") from exc
