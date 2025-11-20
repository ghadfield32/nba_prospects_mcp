"""Team and Player Identity Resolution

Provides canonical identity mappings for teams and players across all leagues.
Enables filtering by human-readable names (e.g., "Duke", "LeBron James") instead
of requiring users to know internal IDs.

Usage:
    from cbb_data.dimensions import get_identity_resolver

    resolver = get_identity_resolver()

    # Resolve team name to IDs
    team_ids = resolver.resolve_team("NCAA-MBB", "Duke")

    # Resolve player name to IDs
    player_ids = resolver.resolve_player("G-League", "Scoot Henderson")

Design:
- Identity data is lazily loaded from team_season/player_season tables
- Cached per league to avoid repeated fetches
- Supports aliases and fuzzy matching
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeamIdentity:
    """Canonical team identity with aliases

    Attributes:
        league: League identifier
        team_id: Canonical ID as stored in datasets
        team_code: Short code if available (e.g., LAL, DUKE)
        name: Full display name
        aliases: Alternative names (e.g., ["Duke Blue Devils", "Duke"])
    """

    league: str
    team_id: str
    team_code: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlayerIdentity:
    """Canonical player identity with aliases

    Attributes:
        league: League identifier
        player_id: Canonical player ID
        name: Primary name ("First Last")
        aliases: Alternative names (nicknames, accented forms)
    """

    league: str
    player_id: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


class IdentityResolver:
    """Resolves human-readable names to canonical IDs

    Supports fuzzy matching through aliases and case-insensitive comparison.

    Example:
        resolver = IdentityResolver()
        resolver.load_league("NCAA-MBB")

        # These all resolve to the same team
        resolver.resolve_team("NCAA-MBB", "Duke")
        resolver.resolve_team("NCAA-MBB", "duke")
        resolver.resolve_team("NCAA-MBB", "Duke Blue Devils")
    """

    def __init__(self) -> None:
        self._teams: dict[str, list[TeamIdentity]] = {}
        self._players: dict[str, list[PlayerIdentity]] = {}
        self._loaded_leagues: set[str] = set()

    def load_league(self, league: str) -> None:
        """Load identity data for a league

        Attempts to load from dimension tables or existing season data.

        Args:
            league: League identifier
        """
        if league in self._loaded_leagues:
            return

        try:
            teams = self._load_teams_for_league(league)
            players = self._load_players_for_league(league)

            self._teams[league] = teams
            self._players[league] = players
            self._loaded_leagues.add(league)

            logger.debug(f"Loaded {len(teams)} teams and {len(players)} players for {league}")

        except Exception as e:
            logger.warning(f"Failed to load identity data for {league}: {e}")
            self._teams[league] = []
            self._players[league] = []
            self._loaded_leagues.add(league)

    def _load_teams_for_league(self, league: str) -> list[TeamIdentity]:
        """Load team identities from available data sources"""
        teams = []

        # Try to load from dimension parquet if available
        dim_path = Path(f"data/dim/league={league}/teams.parquet")
        if dim_path.exists():
            df = pd.read_parquet(dim_path)
            for _, row in df.iterrows():
                teams.append(
                    TeamIdentity(
                        league=league,
                        team_id=str(row.get("TEAM_ID", row.get("team_id", ""))),
                        team_code=str(row.get("TEAM_CODE", row.get("team_code", ""))),
                        name=str(row.get("TEAM_NAME", row.get("name", ""))),
                        aliases=tuple(row.get("aliases", [])) if "aliases" in row else (),
                    )
                )
            return teams

        # Try to extract from team_season data
        season_path = Path(f"data/team_season/league={league}")
        if season_path.exists():
            for pq_file in season_path.glob("*.parquet"):
                try:
                    df = pd.read_parquet(pq_file)

                    # Find team ID and name columns
                    id_col = None
                    name_col = None

                    for col in df.columns:
                        col_lower = col.lower()
                        if "team_id" in col_lower or col_lower == "team_id":
                            id_col = col
                        elif "team" in col_lower and "name" in col_lower:
                            name_col = col
                        elif col_lower == "team" and name_col is None:
                            name_col = col

                    if id_col and name_col:
                        unique_teams = df[[id_col, name_col]].drop_duplicates()
                        for _, row in unique_teams.iterrows():
                            team_id = str(row[id_col])
                            team_name = str(row[name_col])

                            # Generate aliases
                            aliases = self._generate_team_aliases(team_name)

                            teams.append(
                                TeamIdentity(
                                    league=league,
                                    team_id=team_id,
                                    team_code=team_id[:3].upper() if len(team_id) >= 3 else team_id,
                                    name=team_name,
                                    aliases=tuple(aliases),
                                )
                            )

                except Exception as e:
                    logger.debug(f"Error loading team data from {pq_file}: {e}")

        return teams

    def _load_players_for_league(self, league: str) -> list[PlayerIdentity]:
        """Load player identities from available data sources"""
        players = []

        # Try to load from dimension parquet if available
        dim_path = Path(f"data/dim/league={league}/players.parquet")
        if dim_path.exists():
            df = pd.read_parquet(dim_path)
            for _, row in df.iterrows():
                players.append(
                    PlayerIdentity(
                        league=league,
                        player_id=str(row.get("PLAYER_ID", row.get("player_id", ""))),
                        name=str(row.get("PLAYER_NAME", row.get("name", ""))),
                        aliases=tuple(row.get("aliases", [])) if "aliases" in row else (),
                    )
                )
            return players

        # Try to extract from player_season data
        season_path = Path(f"data/player_season/league={league}")
        if season_path.exists():
            for pq_file in season_path.glob("*.parquet"):
                try:
                    df = pd.read_parquet(pq_file)

                    # Find player ID and name columns
                    id_col = None
                    name_col = None

                    for col in df.columns:
                        col_lower = col.lower()
                        if "player_id" in col_lower:
                            id_col = col
                        elif "player" in col_lower and "name" in col_lower:
                            name_col = col

                    if id_col and name_col:
                        unique_players = df[[id_col, name_col]].drop_duplicates()
                        for _, row in unique_players.iterrows():
                            player_id = str(row[id_col])
                            player_name = str(row[name_col])

                            # Generate aliases
                            aliases = self._generate_player_aliases(player_name)

                            players.append(
                                PlayerIdentity(
                                    league=league,
                                    player_id=player_id,
                                    name=player_name,
                                    aliases=tuple(aliases),
                                )
                            )

                except Exception as e:
                    logger.debug(f"Error loading player data from {pq_file}: {e}")

        return players

    def _generate_team_aliases(self, name: str) -> list[str]:
        """Generate common aliases for a team name"""
        aliases = []

        # Add without common suffixes
        for suffix in [
            " University",
            " College",
            " State",
            " Blue Devils",
            " Wildcats",
            " Tigers",
            " Bears",
            " Lions",
            " Eagles",
        ]:
            if name.endswith(suffix):
                aliases.append(name[: -len(suffix)])

        # Add abbreviation if long name
        if len(name) > 10:
            words = name.split()
            if len(words) >= 2:
                aliases.append("".join(w[0].upper() for w in words))

        return aliases

    def _generate_player_aliases(self, name: str) -> list[str]:
        """Generate common aliases for a player name"""
        aliases = []

        # Add last name only
        parts = name.split()
        if len(parts) >= 2:
            aliases.append(parts[-1])  # Last name
            # First initial + last name
            aliases.append(f"{parts[0][0]}. {parts[-1]}")

        return aliases

    def resolve_team(self, league: str, query: str) -> list[str]:
        """Resolve team name/code to canonical team IDs

        Args:
            league: League identifier
            query: Team name, code, or alias to search for

        Returns:
            List of matching team IDs (usually 1, but may be more for ambiguous queries)
        """
        self.load_league(league)

        q = query.strip().lower()
        matches = []

        for team in self._teams.get(league, []):
            if (
                q == team.name.lower()
                or q == team.team_code.lower()
                or q == team.team_id.lower()
                or q in (a.lower() for a in team.aliases)
            ):
                matches.append(team.team_id)

        # If no exact match, try partial matching
        if not matches:
            for team in self._teams.get(league, []):
                if q in team.name.lower() or team.name.lower() in q:
                    matches.append(team.team_id)

        return matches

    def resolve_player(self, league: str, query: str) -> list[str]:
        """Resolve player name to canonical player IDs

        Args:
            league: League identifier
            query: Player name or alias to search for

        Returns:
            List of matching player IDs
        """
        self.load_league(league)

        q = query.strip().lower()
        matches = []

        for player in self._players.get(league, []):
            if (
                q == player.name.lower()
                or q == player.player_id.lower()
                or q in (a.lower() for a in player.aliases)
            ):
                matches.append(player.player_id)

        # If no exact match, try partial matching
        if not matches:
            for player in self._players.get(league, []):
                if q in player.name.lower() or player.name.lower() in q:
                    matches.append(player.player_id)

        return matches

    def get_all_teams(self, league: str) -> list[TeamIdentity]:
        """Get all team identities for a league"""
        self.load_league(league)
        return self._teams.get(league, [])

    def get_all_players(self, league: str) -> list[PlayerIdentity]:
        """Get all player identities for a league"""
        self.load_league(league)
        return self._players.get(league, [])


# Global resolver instance (lazy-loaded)
_resolver: IdentityResolver | None = None


def get_identity_resolver() -> IdentityResolver:
    """Get the global identity resolver instance

    Returns:
        IdentityResolver singleton
    """
    global _resolver
    if _resolver is None:
        _resolver = IdentityResolver()
    return _resolver
