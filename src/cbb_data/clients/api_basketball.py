"""API-Basketball Client (api-sports.io)

Thin wrapper around API-Basketball REST API with caching, rate limiting, and error handling.

API Documentation: https://api-sports.io/documentation/basketball/v1

**Coverage**: 426 basketball leagues worldwide including:
- NBA, EuroLeague, EuroCup, ACB (Spain), LNB (France)
- NBL (Australia), BAL (Africa), BCL (Champions League)
- Many other domestic and international leagues

**Pricing** (as of 2025):
- Free: 100 requests/day
- Basic ($10/mo): 3,000 requests/day
- Pro ($25/mo): 10,000 requests/day

**Design Principles**:
- Aggressive caching (reduce API calls)
- Rate limit management (stay within quotas)
- Graceful degradation (return empty DataFrame on failure, not crash)
- Source attribution (track which league came from API vs cache vs fallback)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..fetchers.base import cached_dataframe
from ..utils.rate_limiter import get_source_limiter

logger = logging.getLogger(__name__)

# Global rate limiter for API-Basketball
rate_limiter = get_source_limiter()


class APIBasketballClient:
    """Client for API-Basketball (api-sports.io)

    **Environment Variables**:
    - `API_BASKETBALL_KEY`: Your API key (required)
    - `API_BASKETBALL_BASE_URL`: Base URL (default: https://v1.basketball.api-sports.io)

    **Rate Limiting**:
    - Free tier: 100 requests/day
    - Basic tier: 3,000 requests/day (2.08 requests/minute sustained)
    - Client uses rate_limiter to stay within quotas

    **Caching Strategy**:
    - Player/team season stats: 24-hour TTL (stats don't change mid-season)
    - Standings: 6-hour TTL (updated after games)
    - Schedules: 1-hour TTL (game times occasionally change)
    - Cached in DuckDB or memory (see base.py @cached_dataframe)

    Example:
        >>> client = APIBasketballClient(api_key=os.getenv("API_BASKETBALL_KEY"))
        >>> df = client.get_league_player_stats(league_id=12, season=2024)
        >>> print(df.columns)
        Index(['player_id', 'player_name', 'team', 'games', 'points', ...])
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://v1.basketball.api-sports.io",
        timeout: int = 30,
    ):
        """Initialize API-Basketball client

        Args:
            api_key: API key (or set API_BASKETBALL_KEY env var)
            base_url: Base URL for API (default: official API-Basketball endpoint)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            ValueError: If api_key is None and API_BASKETBALL_KEY env var not set
        """
        self.api_key = api_key or os.getenv("API_BASKETBALL_KEY")
        if not self.api_key:
            raise ValueError(
                "API-Basketball API key required. Set API_BASKETBALL_KEY environment variable "
                "or pass api_key parameter. Get free key at https://api-sports.io/register"
            )

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Setup session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set headers
        self.session.headers.update(
            {
                "x-apisports-key": self.api_key,
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make GET request to API-Basketball

        Args:
            endpoint: API endpoint (e.g., "/leagues", "/standings")
            params: Query parameters

        Returns:
            JSON response as dict

        Raises:
            requests.HTTPError: If request fails after retries
        """
        rate_limiter.acquire("api_basketball")  # Respect rate limits

        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params or {}, timeout=self.timeout)
            response.raise_for_status()

            data: dict[str, Any] = response.json()

            # Log API quota usage
            if "errors" in data and data["errors"]:
                logger.warning(f"API-Basketball errors: {data['errors']}")

            if "requests" in data:
                remaining = data["requests"].get("current", "unknown")
                limit = data["requests"].get("limit_day", "unknown")
                logger.info(f"API-Basketball quota: {remaining}/{limit} requests today")

            return data

        except requests.HTTPError as e:
            logger.error(f"API-Basketball HTTP error: {e}")
            logger.error(f"URL: {url}, Params: {params}")
            if hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text[:500]}")
            raise

        except Exception as e:
            logger.error(f"API-Basketball request failed: {e}")
            raise

    # ==========================================================================
    # League Metadata
    # ==========================================================================

    @cached_dataframe
    def get_leagues(self, country: str | None = None, season: str | None = None) -> pd.DataFrame:
        """Get all available leagues

        Args:
            country: Filter by country (e.g., "USA", "Spain", "Australia")
            season: Filter by season (e.g., "2024")

        Returns:
            DataFrame with columns: league_id, league_name, country, logo, season

        Example:
            >>> client.get_leagues(country="Australia")
            # Returns NBL and other Australian leagues
        """
        params = {}
        if country:
            params["country"] = country
        if season:
            params["season"] = season

        data = self._get("/leagues", params=params)

        if "response" not in data or not data["response"]:
            logger.warning(f"No leagues found for country={country}, season={season}")
            return pd.DataFrame(columns=["league_id", "league_name", "country", "logo", "season"])

        leagues = []
        for item in data["response"]:
            league = item.get("league", {})
            leagues.append(
                {
                    "league_id": league.get("id"),
                    "league_name": league.get("name"),
                    "country": item.get("country", {}).get("name"),
                    "logo": league.get("logo"),
                    "season": item.get("seasons", [{}])[0].get("season")
                    if item.get("seasons")
                    else None,
                }
            )

        return pd.DataFrame(leagues)

    # ==========================================================================
    # Standings & Team Stats
    # ==========================================================================

    @cached_dataframe
    def get_standings(self, league_id: int, season: int) -> pd.DataFrame:
        """Get league standings

        Args:
            league_id: API-Basketball league ID (use get_leagues() to find)
            season: Season year (e.g., 2024)

        Returns:
            DataFrame with team standings (wins, losses, pct, etc.)

        Example:
            >>> client.get_standings(league_id=12, season=2024)  # NBL Australia
        """
        params = {"league": league_id, "season": season}
        data = self._get("/standings", params=params)

        if "response" not in data or not data["response"]:
            logger.warning(f"No standings for league_id={league_id}, season={season}")
            return pd.DataFrame()

        standings = []
        for group in data["response"]:
            for item in group:
                team = item.get("team", {})
                stats = item.get("games", {})
                standings.append(
                    {
                        "team_id": team.get("id"),
                        "team_name": team.get("name"),
                        "position": item.get("position"),
                        "games_played": stats.get("played"),
                        "wins": stats.get("win", {}).get("total"),
                        "losses": stats.get("lose", {}).get("total"),
                        "win_pct": stats.get("win", {}).get("percentage"),
                        "points_for": item.get("points", {}).get("for"),
                        "points_against": item.get("points", {}).get("against"),
                    }
                )

        return pd.DataFrame(standings)

    # ==========================================================================
    # Player Stats
    # ==========================================================================

    @cached_dataframe
    def get_league_player_stats(
        self, league_id: int, season: int, team_id: int | None = None
    ) -> pd.DataFrame:
        """Get player season statistics for a league

        Args:
            league_id: API-Basketball league ID
            season: Season year (e.g., 2024)
            team_id: Optional team filter

        Returns:
            DataFrame with player season stats (points, rebounds, assists, etc.)

        Example:
            >>> client.get_league_player_stats(league_id=12, season=2024)  # All NBL players
        """
        params = {"league": league_id, "season": season}
        if team_id:
            params["team"] = team_id

        data = self._get("/players/statistics", params=params)

        if "response" not in data or not data["response"]:
            logger.warning(f"No player stats for league_id={league_id}, season={season}")
            return pd.DataFrame()

        players = []
        for item in data["response"]:
            player = item.get("player", {})
            team = item.get("team", {})
            stats = item.get("statistics", [{}])[0] if item.get("statistics") else {}

            players.append(
                {
                    "player_id": player.get("id"),
                    "player_name": player.get("name"),
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "games_played": stats.get("games", {}).get("played"),
                    "minutes": stats.get("minutes"),
                    "points": stats.get("points"),
                    "rebounds": stats.get("rebounds"),
                    "assists": stats.get("assists"),
                    "steals": stats.get("steals"),
                    "blocks": stats.get("blocks"),
                    "turnovers": stats.get("turnovers"),
                    "field_goals_made": stats.get("fieldGoalsMade"),
                    "field_goals_attempted": stats.get("fieldGoalsAttempted"),
                    "field_goal_pct": stats.get("fieldGoalsPercentage"),
                    "three_pointers_made": stats.get("threePointsMade"),
                    "three_pointers_attempted": stats.get("threePointsAttempted"),
                    "three_point_pct": stats.get("threePointsPercentage"),
                    "free_throws_made": stats.get("freeThrowsMade"),
                    "free_throws_attempted": stats.get("freeThrowsAttempted"),
                    "free_throw_pct": stats.get("freeThrowsPercentage"),
                }
            )

        return pd.DataFrame(players)

    # ==========================================================================
    # Schedule & Games
    # ==========================================================================

    @cached_dataframe
    def get_games(
        self,
        league_id: int | None = None,
        season: int | None = None,
        date: str | None = None,
        team_id: int | None = None,
    ) -> pd.DataFrame:
        """Get game schedule/results

        Args:
            league_id: Filter by league
            season: Filter by season
            date: Filter by date (YYYY-MM-DD)
            team_id: Filter by team

        Returns:
            DataFrame with game schedule and results

        Example:
            >>> client.get_games(league_id=12, season=2024, date="2024-01-15")
        """
        params: dict[str, Any] = {}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        if date:
            params["date"] = date
        if team_id:
            params["team"] = team_id

        data = self._get("/games", params=params)

        if "response" not in data or not data["response"]:
            logger.warning(f"No games found for params: {params}")
            return pd.DataFrame()

        games = []
        for item in data["response"]:
            game = item.get("game", {})
            teams = item.get("teams", {})
            scores = item.get("scores", {})

            games.append(
                {
                    "game_id": game.get("id"),
                    "date": game.get("date"),
                    "status": game.get("status", {}).get("long"),
                    "home_team_id": teams.get("home", {}).get("id"),
                    "home_team_name": teams.get("home", {}).get("name"),
                    "away_team_id": teams.get("away", {}).get("id"),
                    "away_team_name": teams.get("away", {}).get("name"),
                    "home_score": scores.get("home", {}).get("total"),
                    "away_score": scores.get("away", {}).get("total"),
                }
            )

        return pd.DataFrame(games)

    # ==========================================================================
    # Game Box Scores
    # ==========================================================================

    @cached_dataframe
    def get_game_boxscore(self, game_id: int) -> pd.DataFrame:
        """Get detailed box score for a specific game

        Args:
            game_id: Game ID from get_games()

        Returns:
            DataFrame with player box scores for the game

        Columns:
            - game_id, player_id, player_name, team_id, team_name
            - minutes, points, rebounds, assists, steals, blocks, turnovers
            - field_goals_made, field_goals_attempted, field_goal_pct
            - three_pointers_made, three_pointers_attempted, three_point_pct
            - free_throws_made, free_throws_attempted, free_throw_pct

        Example:
            >>> game_box = client.get_game_boxscore(game_id=123456)
            >>> top_scorers = game_box.nlargest(5, 'points')
        """
        params = {"game": game_id}
        data = self._get("/statistics", params=params)

        if "response" not in data or not data["response"]:
            logger.warning(f"No box score data for game_id={game_id}")
            return pd.DataFrame()

        players = []
        for item in data["response"]:
            player = item.get("player", {})
            team = item.get("team", {})
            stats = item.get("statistics", [{}])[0] if item.get("statistics") else {}

            players.append(
                {
                    "game_id": game_id,
                    "player_id": player.get("id"),
                    "player_name": player.get("name"),
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "minutes": stats.get("minutes"),
                    "points": stats.get("points"),
                    "rebounds": stats.get("rebounds"),
                    "assists": stats.get("assists"),
                    "steals": stats.get("steals"),
                    "blocks": stats.get("blocks"),
                    "turnovers": stats.get("turnovers"),
                    "field_goals_made": stats.get("fieldGoalsMade"),
                    "field_goals_attempted": stats.get("fieldGoalsAttempted"),
                    "field_goal_pct": stats.get("fieldGoalsPercentage"),
                    "three_pointers_made": stats.get("threePointsMade"),
                    "three_pointers_attempted": stats.get("threePointsAttempted"),
                    "three_point_pct": stats.get("threePointsPercentage"),
                    "free_throws_made": stats.get("freeThrowsMade"),
                    "free_throws_attempted": stats.get("freeThrowsAttempted"),
                    "free_throw_pct": stats.get("freeThrowsPercentage"),
                }
            )

        return pd.DataFrame(players)

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    def find_league_id(self, league_name: str, country: str | None = None) -> int | None:
        """Find API-Basketball league ID by name

        Args:
            league_name: League name to search (e.g., "NBL", "ACB", "LNB")
            country: Optional country filter to narrow search

        Returns:
            League ID if found, None otherwise

        Example:
            >>> client.find_league_id("NBL", country="Australia")
            12  # NBL Australia league ID
        """
        leagues = self.get_leagues(country=country)

        if leagues.empty:
            return None

        # Exact match first
        match = leagues[leagues["league_name"].str.lower() == league_name.lower()]
        if not match.empty:
            return int(match.iloc[0]["league_id"])

        # Partial match fallback
        match = leagues[leagues["league_name"].str.contains(league_name, case=False, na=False)]
        if not match.empty:
            logger.info(f"Partial match for '{league_name}': {match.iloc[0]['league_name']}")
            return int(match.iloc[0]["league_id"])

        logger.warning(f"No league found for '{league_name}' (country={country})")
        return None


# ==============================================================================
# League ID Mappings (For Quick Reference)
# ==============================================================================
# These will be populated via testing with real API-Basketball data
# For now, these are placeholders - actual IDs need verification

LEAGUE_ID_MAP: dict[str, int] = {
    "LNB_PROA": 62,  # France - LNB Pro A (verified)
    # "NBL": 12,  # Australia - needs verification
    # "ACB": ??,  # Spain - needs verification
    # "LKL": ??,  # Lithuania - needs verification
    # "BAL": ??,  # Africa - needs verification
    # "BCL": ??,  # Basketball Champions League - needs verification
    # "ABA": ??,  # ABA League - needs verification
}


def get_api_basketball_league_id(league: str) -> int | None:
    """Get API-Basketball league ID for a cbb_data league

    Args:
        league: cbb_data league identifier (e.g., "NBL", "ACB")

    Returns:
        API-Basketball league ID if known, None if unknown

    Note:
        LEAGUE_ID_MAP must be populated by testing with real API data.
        Use APIBasketballClient.find_league_id() to discover IDs.
    """
    return LEAGUE_ID_MAP.get(league)
