"""LNB Name/ID Lookup and Resolution Utilities

Provides bidirectional lookup between IDs and human-readable names for:
- Teams (TEAM_ID <-> team name)
- Games (GAME_ID <-> date, teams)
- Players (PLAYER_ID <-> player name)

This enables querying by name instead of requiring UUIDs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Division to League mapping
DIVISION_TO_LEAGUE = {
    "1": "LNB_PROA",
    "2": "LNB_ELITE2",
    "3": "LNB_ESPOIRS_ELITE",
    "4": "LNB_ESPOIRS_PROB",
}

HISTORICAL_DIR = Path("data/lnb/historical")


class LNBLookup:
    """LNB name/ID lookup service

    Loads fixtures data to build lookup tables for teams, games, and players.
    Enables querying by human-readable names instead of UUIDs.

    Usage:
        lookup = LNBLookup("2024-2025")

        # Team lookups
        team_id = lookup.get_team_id("Lyon-Villeurbanne")
        team_name = lookup.get_team_name("25bcb29d-55bc-11f0-8037-fb553c4eab1b")

        # Game lookups
        game_ids = lookup.get_games_by_team("Lyon-Villeurbanne")
        game_ids = lookup.get_games_by_date("2024-11-15")
        game_info = lookup.get_game_info("bf01596f-67e5-11f0-b2bf-4b31bc5c544b")

        # Player lookups
        player_id = lookup.get_player_id("Victor Wembanyama")
        player_name = lookup.get_player_name("abc123...")
    """

    def __init__(self, season: str = "2024-2025"):
        """Initialize lookup service for a season

        Args:
            season: Season string (e.g., "2024-2025")
        """
        self.season = season
        self._fixtures_df: pd.DataFrame | None = None
        self._team_id_to_name: dict[str, str] = {}
        self._team_name_to_id: dict[str, str] = {}
        self._player_id_to_name: dict[str, str] = {}
        self._player_name_to_id: dict[str, str] = {}

        self._load_fixtures()

    def _load_fixtures(self) -> None:
        """Load all fixtures data for the season"""
        season_dir = HISTORICAL_DIR / self.season
        if not season_dir.exists():
            logger.warning(f"No historical directory for {self.season}")
            return

        fixtures_files = list(season_dir.glob("*fixtures*.parquet"))
        if not fixtures_files:
            logger.warning(f"No fixtures files found in {season_dir}")
            return

        dfs = []
        for f in fixtures_files:
            try:
                df = pd.read_parquet(f)
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to load {f}: {e}")

        if not dfs:
            return

        self._fixtures_df = pd.concat(dfs, ignore_index=True)
        self._build_team_lookup()
        logger.info(
            f"Loaded {len(self._fixtures_df)} fixtures, "
            f"{len(self._team_id_to_name)} teams for {self.season}"
        )

    def _build_team_lookup(self) -> None:
        """Build team ID <-> name lookup tables"""
        if self._fixtures_df is None or self._fixtures_df.empty:
            return

        # Collect all teams from home and away
        for _, row in self._fixtures_df.iterrows():
            # Home team
            if "home_team_id" in row and "home_team_name" in row:
                team_id = str(row["home_team_id"])
                team_name = str(row["home_team_name"])
                self._team_id_to_name[team_id] = team_name
                # Store both exact and normalized names
                self._team_name_to_id[team_name] = team_id
                self._team_name_to_id[team_name.lower()] = team_id

            # Away team
            if "away_team_id" in row and "away_team_name" in row:
                team_id = str(row["away_team_id"])
                team_name = str(row["away_team_name"])
                self._team_id_to_name[team_id] = team_name
                self._team_name_to_id[team_name] = team_id
                self._team_name_to_id[team_name.lower()] = team_id

    def load_player_lookup(self, player_game_df: pd.DataFrame) -> None:
        """Build player ID <-> name lookup from player_game data

        Args:
            player_game_df: DataFrame with PLAYER_ID and PLAYER_NAME columns
        """
        if "PLAYER_ID" not in player_game_df.columns or "PLAYER_NAME" not in player_game_df.columns:
            return

        for _, row in player_game_df.iterrows():
            player_id = str(row["PLAYER_ID"])
            player_name = str(row["PLAYER_NAME"])
            self._player_id_to_name[player_id] = player_name
            self._player_name_to_id[player_name] = player_id
            self._player_name_to_id[player_name.lower()] = player_id

        logger.info(f"Loaded {len(self._player_id_to_name)} player mappings")

    # -------------------------------------------------------------------------
    # Team Lookups
    # -------------------------------------------------------------------------

    def get_team_name(self, team_id: str) -> str | None:
        """Get team name from team ID

        Args:
            team_id: Team UUID

        Returns:
            Team name or None if not found
        """
        return self._team_id_to_name.get(str(team_id))

    def get_team_id(self, team_name: str) -> str | None:
        """Get team ID from team name (case-insensitive)

        Args:
            team_name: Team name (partial match supported)

        Returns:
            Team UUID or None if not found
        """
        # Try exact match first
        if team_name in self._team_name_to_id:
            return self._team_name_to_id[team_name]

        # Try case-insensitive
        if team_name.lower() in self._team_name_to_id:
            return self._team_name_to_id[team_name.lower()]

        # Try partial match
        team_lower = team_name.lower()
        for name, team_id in self._team_name_to_id.items():
            if team_lower in name.lower():
                return team_id

        return None

    def get_all_teams(self, league: str | None = None) -> list[dict[str, str]]:
        """Get all teams with their IDs

        Args:
            league: Filter by league (e.g., "LNB_ELITE2")

        Returns:
            List of dicts with team_id and team_name
        """
        if self._fixtures_df is None:
            return []

        teams = []
        seen = set()

        for _, row in self._fixtures_df.iterrows():
            # Filter by league if specified
            if league:
                division = str(row.get("division", "1"))
                row_league = DIVISION_TO_LEAGUE.get(division, "LNB_PROA")
                if row_league != league:
                    continue

            # Add home team
            home_id = str(row.get("home_team_id", ""))
            if home_id and home_id not in seen:
                teams.append(
                    {
                        "team_id": home_id,
                        "team_name": str(row.get("home_team_name", "")),
                    }
                )
                seen.add(home_id)

            # Add away team
            away_id = str(row.get("away_team_id", ""))
            if away_id and away_id not in seen:
                teams.append(
                    {
                        "team_id": away_id,
                        "team_name": str(row.get("away_team_name", "")),
                    }
                )
                seen.add(away_id)

        return sorted(teams, key=lambda x: x["team_name"])

    # -------------------------------------------------------------------------
    # Game Lookups
    # -------------------------------------------------------------------------

    def get_game_info(self, game_id: str) -> dict[str, Any] | None:
        """Get game information from game ID

        Args:
            game_id: Game/fixture UUID

        Returns:
            Dict with game info (date, teams, scores) or None
        """
        if self._fixtures_df is None:
            return None

        match = self._fixtures_df[self._fixtures_df["fixture_uuid"] == game_id]
        if match.empty:
            return None

        row = match.iloc[0]
        return {
            "game_id": str(row["fixture_uuid"]),
            "home_team": str(row.get("home_team_name", "")),
            "away_team": str(row.get("away_team_name", "")),
            "home_team_id": str(row.get("home_team_id", "")),
            "away_team_id": str(row.get("away_team_id", "")),
            "home_score": row.get("home_score"),
            "away_score": row.get("away_score"),
            "date": str(row.get("start_time_local", row.get("start_time_utc", "")))[:10],
            "venue": str(row.get("venue_name", "")),
            "league": DIVISION_TO_LEAGUE.get(str(row.get("division", "1")), "LNB_PROA"),
        }

    def get_games_by_team(
        self,
        team: str,
        league: str | None = None,
    ) -> list[str]:
        """Get game IDs for a team

        Args:
            team: Team name or ID
            league: Filter by league

        Returns:
            List of game IDs
        """
        if self._fixtures_df is None:
            return []

        # Resolve team name to ID if needed
        team_id = team
        if not self._is_uuid(team):
            resolved = self.get_team_id(team)
            if resolved:
                team_id = resolved
            else:
                # Try to match by name directly in fixtures
                team_id = team

        df = self._fixtures_df

        # Filter by league
        if league:
            df = df[
                df["division"].astype(str).map(lambda d: DIVISION_TO_LEAGUE.get(d, "LNB_PROA"))
                == league
            ]

        # Find games where team is home or away
        mask = (
            (df["home_team_id"].astype(str) == team_id)
            | (df["away_team_id"].astype(str) == team_id)
            | (df["home_team_name"].str.lower().str.contains(team.lower(), na=False))
            | (df["away_team_name"].str.lower().str.contains(team.lower(), na=False))
        )

        return df[mask]["fixture_uuid"].tolist()

    def get_games_by_date(
        self,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        league: str | None = None,
    ) -> list[str]:
        """Get game IDs by date or date range

        Args:
            date: Exact date (YYYY-MM-DD)
            start_date: Start of date range
            end_date: End of date range
            league: Filter by league

        Returns:
            List of game IDs
        """
        if self._fixtures_df is None:
            return []

        df = self._fixtures_df.copy()

        # Parse dates
        date_col = "start_time_local" if "start_time_local" in df.columns else "start_time_utc"
        df["_date"] = pd.to_datetime(df[date_col]).dt.date

        # Filter by league
        if league:
            df = df[
                df["division"].astype(str).map(lambda d: DIVISION_TO_LEAGUE.get(d, "LNB_PROA"))
                == league
            ]

        # Filter by date
        if date:
            target = pd.to_datetime(date).date()
            df = df[df["_date"] == target]
        elif start_date or end_date:
            if start_date:
                start = pd.to_datetime(start_date).date()
                df = df[df["_date"] >= start]
            if end_date:
                end = pd.to_datetime(end_date).date()
                df = df[df["_date"] <= end]

        return df["fixture_uuid"].tolist()

    def get_games_between_teams(
        self,
        team1: str,
        team2: str,
        league: str | None = None,
    ) -> list[str]:
        """Get game IDs for games between two teams

        Args:
            team1: First team name or ID
            team2: Second team name or ID
            league: Filter by league

        Returns:
            List of game IDs
        """
        if self._fixtures_df is None:
            return []

        # Get games for each team
        games1 = set(self.get_games_by_team(team1, league))
        games2 = set(self.get_games_by_team(team2, league))

        # Return intersection
        return list(games1 & games2)

    # -------------------------------------------------------------------------
    # Player Lookups
    # -------------------------------------------------------------------------

    def get_player_name(self, player_id: str) -> str | None:
        """Get player name from player ID

        Args:
            player_id: Player UUID

        Returns:
            Player name or None
        """
        return self._player_id_to_name.get(str(player_id))

    def get_player_id(self, player_name: str) -> str | None:
        """Get player ID from player name (case-insensitive)

        Args:
            player_name: Player name

        Returns:
            Player UUID or None
        """
        # Try exact match
        if player_name in self._player_name_to_id:
            return self._player_name_to_id[player_name]

        # Try case-insensitive
        if player_name.lower() in self._player_name_to_id:
            return self._player_name_to_id[player_name.lower()]

        # Try partial match
        name_lower = player_name.lower()
        for name, player_id in self._player_name_to_id.items():
            if name_lower in name.lower():
                return player_id

        return None

    # -------------------------------------------------------------------------
    # Schedule Generation
    # -------------------------------------------------------------------------

    def get_schedule(
        self,
        league: str | None = None,
        team: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Get schedule with human-readable names

        Args:
            league: Filter by league
            team: Filter by team name
            start_date: Start date filter
            end_date: End date filter

        Returns:
            DataFrame with schedule (dates, team names, scores)
        """
        if self._fixtures_df is None or self._fixtures_df.empty:
            return pd.DataFrame()

        df = self._fixtures_df.copy()

        # Parse dates
        date_col = "start_time_local" if "start_time_local" in df.columns else "start_time_utc"
        df["GAME_DATE"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")

        # Filter by league
        if league:
            df = df[
                df["division"].astype(str).map(lambda d: DIVISION_TO_LEAGUE.get(d, "LNB_PROA"))
                == league
            ]

        # Filter by team
        if team:
            team_lower = team.lower()
            mask = (df["home_team_name"].str.lower().str.contains(team_lower, na=False)) | (
                df["away_team_name"].str.lower().str.contains(team_lower, na=False)
            )
            df = df[mask]

        # Filter by date range
        if start_date:
            start = pd.to_datetime(start_date).strftime("%Y-%m-%d")
            df = df[df["GAME_DATE"] >= start]
        if end_date:
            end = pd.to_datetime(end_date).strftime("%Y-%m-%d")
            df = df[df["GAME_DATE"] <= end]

        # Build output DataFrame
        result = pd.DataFrame(
            {
                "GAME_ID": df["fixture_uuid"],
                "GAME_DATE": df["GAME_DATE"],
                "HOME_TEAM": df["home_team_name"],
                "AWAY_TEAM": df["away_team_name"],
                "HOME_TEAM_ID": df["home_team_id"],
                "AWAY_TEAM_ID": df["away_team_id"],
                "HOME_SCORE": df.get("home_score"),
                "AWAY_SCORE": df.get("away_score"),
                "VENUE": df.get("venue_name", ""),
                "LEAGUE": df["division"]
                .astype(str)
                .map(lambda d: DIVISION_TO_LEAGUE.get(d, "LNB_PROA")),
                "SEASON": self.season,
            }
        )

        return result.sort_values("GAME_DATE").reset_index(drop=True)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_uuid(value: str) -> bool:
        """Check if a value looks like a UUID"""
        # UUIDs are typically 36 chars with hyphens
        return len(value) == 36 and value.count("-") == 4


# Module-level convenience functions
_lookup_cache: dict[str, LNBLookup] = {}


def get_lnb_lookup(season: str = "2024-2025") -> LNBLookup:
    """Get or create LNB lookup instance for a season

    Args:
        season: Season string

    Returns:
        LNBLookup instance
    """
    if season not in _lookup_cache:
        _lookup_cache[season] = LNBLookup(season)
    return _lookup_cache[season]


def resolve_lnb_team(team: str, season: str = "2024-2025") -> str | None:
    """Resolve team name to ID

    Args:
        team: Team name (partial match supported)
        season: Season string

    Returns:
        Team UUID or None
    """
    return get_lnb_lookup(season).get_team_id(team)


def resolve_lnb_game(
    team: str | None = None,
    date: str | None = None,
    opponent: str | None = None,
    season: str = "2024-2025",
) -> list[str]:
    """Resolve game criteria to game IDs

    Args:
        team: Team name
        date: Game date (YYYY-MM-DD)
        opponent: Opponent team name
        season: Season string

    Returns:
        List of matching game IDs
    """
    lookup = get_lnb_lookup(season)

    if team and opponent:
        return lookup.get_games_between_teams(team, opponent)
    elif team:
        games = lookup.get_games_by_team(team)
        if date:
            date_games = set(lookup.get_games_by_date(date=date))
            games = [g for g in games if g in date_games]
        return games
    elif date:
        return lookup.get_games_by_date(date=date)

    return []


def get_lnb_schedule(
    season: str = "2024-2025",
    league: str | None = None,
    team: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Get LNB schedule with human-readable names

    Args:
        season: Season string
        league: Filter by league (e.g., "LNB_ELITE2")
        team: Filter by team name
        start_date: Start date filter
        end_date: End date filter

    Returns:
        DataFrame with schedule
    """
    return get_lnb_lookup(season).get_schedule(
        league=league,
        team=team,
        start_date=start_date,
        end_date=end_date,
    )


def get_lnb_teams(
    season: str = "2024-2025",
    league: str | None = None,
) -> list[dict[str, str]]:
    """Get list of all LNB teams

    Args:
        season: Season string
        league: Filter by league

    Returns:
        List of team dicts with team_id and team_name
    """
    return get_lnb_lookup(season).get_all_teams(league=league)
