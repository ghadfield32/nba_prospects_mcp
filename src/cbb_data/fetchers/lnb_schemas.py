"""LNB API Canonical Schemas

This module defines canonical schemas for all LNB data types, ensuring
consistency across the entire pipeline (API → DataFrame → DuckDB → filters).

Schema Design Principles:
1. Column names match global conventions (GAME_ID, PLAYER_ID, TEAM_ID, etc.)
2. All schemas include LEAGUE and SEASON for cross-league compatibility
3. Primary keys are clearly defined for joins and deduplication
4. All timestamps use consistent formats (ISO 8601)
5. Derived metrics (eFG%, TS%, etc.) are calculated consistently

Data Types:
- Schedule: Game-level metadata (teams, dates, scores)
- TeamGame: Per-team per-game aggregates (box score team totals)
- PlayerGame: Per-player per-game stats (box score player rows)
- PlayByPlay: Event-level data (period, clock, players, score)
- Shots: Shot-level data (x, y, made/missed, shooter)
- PlayerSeason: Aggregated season stats (from player_game or leaders API)
- TeamSeason: Aggregated season stats (from team_game or standings)

IDs and Keys:
- match_external_id: Primary match key from LNB API (integer)
- team_external_id: Team ID from LNB API (integer)
- player_id: Player ID from LNB API (integer or UUID, TBD from API response)
- competition_external_id: Competition ID (e.g., 302 = Betclic ÉLITE 2024-25)

Created: 2025-11-14
"""

from __future__ import annotations

from dataclasses import dataclass

# ==============================================================================
# Schedule Schema
# ==============================================================================


@dataclass
class LNBSchedule:
    """Game schedule (match-level metadata).

    Primary Keys: (GAME_ID,)
    Foreign Keys: None
    Filters: season, team_id, date_range, home_away, opponent
    """

    # Primary key
    GAME_ID: int  # match_external_id from API

    # League/Season
    LEAGUE: str  # "LNB" or "LNB_BETCLIC_ELITE"
    SEASON: int  # e.g., 2024 for 2024-25 season
    COMPETITION: str  # "Betclic ÉLITE", "ÉLITE 2", etc.
    COMPETITION_ID: int  # competition_external_id

    # Date/Time
    GAME_DATE: str  # ISO 8601 date: "2024-11-14"
    GAME_TIME_UTC: str  # ISO 8601 datetime: "2024-11-14T19:00:00Z"
    GAME_TIME_LOCAL: str | None  # Local time if available

    # Teams
    HOME_TEAM_ID: int  # team_external_id
    HOME_TEAM: str  # Team name
    AWAY_TEAM_ID: int
    AWAY_TEAM: str

    # Scores
    HOME_SCORE: int | None  # None if game not played yet
    AWAY_SCORE: int | None

    # Metadata
    VENUE: str | None  # Arena name
    ROUND: int | None  # Round number
    PHASE: str | None  # "Regular Season", "Playoffs", etc.
    STATUS: str  # "scheduled", "finished", "live", "postponed"


# ==============================================================================
# TeamGame Schema
# ==============================================================================


@dataclass
class LNBTeamGame:
    """Per-team per-game stats (team box score).

    Primary Keys: (GAME_ID, TEAM_ID)
    Foreign Keys: GAME_ID → LNBSchedule
    Filters: season, team_id, opponent, date_range, home_away, won
    """

    # Primary keys
    GAME_ID: int
    TEAM_ID: int  # team_external_id

    # League/Season
    LEAGUE: str
    SEASON: int

    # Game context
    GAME_DATE: str
    OPPONENT_ID: int
    HOME_AWAY: str  # "HOME" or "AWAY"
    WON: bool

    # Basic stats
    MIN: float  # Team minutes (usually 200 for full game)
    PTS: int
    FGM: int
    FGA: int
    FG_PCT: float
    FG3M: int
    FG3A: int
    FG3_PCT: float
    FTM: int
    FTA: int
    FT_PCT: float

    # Rebounds
    OREB: int
    DREB: int
    REB: int

    # Playmaking & Turnovers
    AST: int
    TOV: int
    STL: int
    BLK: int
    PF: int  # Personal fouls

    # Derived metrics
    PLUS_MINUS: int
    EFG_PCT: float  # (FGM + 0.5 * FG3M) / FGA
    TS_PCT: float  # PTS / (2 * (FGA + 0.44 * FTA))
    POSS: float  # Estimated possessions
    ORTG: float  # Offensive rating (points per 100 poss)
    DRTG: float  # Defensive rating (opp points per 100 poss)


# ==============================================================================
# PlayerGame Schema
# ==============================================================================


@dataclass
class LNBPlayerGame:
    """Per-player per-game stats (player box score).

    Primary Keys: (GAME_ID, PLAYER_ID)
    Foreign Keys: GAME_ID → LNBSchedule, TEAM_ID → team
    Filters: season, player_id, team_id, opponent, date_range, starter
    """

    # Primary keys
    GAME_ID: int
    PLAYER_ID: int  # TBD: int or UUID from API

    # Player info
    PLAYER_NAME: str
    TEAM_ID: int
    OPPONENT_ID: int

    # League/Season
    LEAGUE: str
    SEASON: int

    # Game context
    GAME_DATE: str
    HOME_AWAY: str
    STARTER: bool  # True if started game
    WON: bool

    # Basic stats
    MIN: float  # Minutes played
    PTS: int
    FGM: int
    FGA: int
    FG_PCT: float | None  # None if FGA=0
    FG3M: int
    FG3A: int
    FG3_PCT: float | None
    FTM: int
    FTA: int
    FT_PCT: float | None

    # Rebounds
    OREB: int
    DREB: int
    REB: int

    # Playmaking & Defense
    AST: int
    TOV: int
    STL: int
    BLK: int
    PF: int

    # Derived
    PLUS_MINUS: int
    EFG_PCT: float | None
    TS_PCT: float | None


# ==============================================================================
# PlayByPlay Schema
# ==============================================================================


@dataclass
class LNBPlayByPlayEvent:
    """Play-by-play event (one row per event).

    Primary Keys: (GAME_ID, EVENT_ID) or (GAME_ID, PERIOD, CLOCK_TIME, SEQ)
    Foreign Keys: GAME_ID → LNBSchedule, PLAYER1_ID → player, TEAM_ID → team
    Filters: season, game_id, team_id, player_id, event_type, period
    """

    # Primary keys
    GAME_ID: int
    EVENT_ID: int | None  # If API provides unique event ID
    PERIOD: int  # Quarter (1-4, 5+ for OT)
    CLOCK_TIME: str  # Game clock: "10:25" or "MM:SS"
    SEQUENCE: int  # Event order within game (for deterministic sorting)

    # League/Season
    LEAGUE: str
    SEASON: int

    # Event type
    EVENT_TYPE: str  # "SHOT", "FOUL", "TURNOVER", "REBOUND", "SUB", etc.
    EVENT_SUBTYPE: str | None  # "3PT_JUMP", "OFFENSIVE_FOUL", "BAD_PASS", etc.
    DESCRIPTION: str  # Human-readable description (French or English)

    # Actors
    TEAM_ID: int | None  # Team performing action
    PLAYER1_ID: int | None  # Primary player (shooter, fouler, etc.)
    PLAYER1_NAME: str | None
    PLAYER2_ID: int | None  # Secondary player (assist, fouled, etc.)
    PLAYER2_NAME: str | None

    # Score
    SCORE_HOME: int
    SCORE_AWAY: int

    # Shot details (if event_type = "SHOT")
    SHOT_MADE: bool | None
    SHOT_VALUE: int | None  # 2 or 3
    SHOT_TYPE: str | None  # "LAYUP", "DUNK", "JUMP", etc.

    # Foul details (if event_type = "FOUL")
    FOUL_TYPE: str | None  # "PERSONAL", "OFFENSIVE", "TECHNICAL", etc.

    # Turnover details (if event_type = "TURNOVER")
    TURNOVER_TYPE: str | None  # "BAD_PASS", "LOST_BALL", "TRAVEL", etc.


# ==============================================================================
# Shots Schema
# ==============================================================================


@dataclass
class LNBShotEvent:
    """Shot-level data with court coordinates.

    Primary Keys: (GAME_ID, SHOT_ID) or (GAME_ID, PERIOD, CLOCK_TIME, PLAYER_ID)
    Foreign Keys: GAME_ID → LNBSchedule, PLAYER_ID → player, TEAM_ID → team
    Filters: season, game_id, team_id, player_id, shot_made, shot_value, zone
    """

    # Primary keys
    GAME_ID: int
    SHOT_ID: int | None  # If API provides
    PERIOD: int
    CLOCK_TIME: str
    SEQUENCE: int

    # League/Season
    LEAGUE: str
    SEASON: int

    # Shooter
    PLAYER_ID: int
    PLAYER_NAME: str
    TEAM_ID: int

    # Shot details
    SHOT_MADE: bool
    SHOT_VALUE: int  # 2 or 3
    SHOT_TYPE: str | None  # "LAYUP", "DUNK", "JUMP", "HOOK", etc.

    # Court location
    X_COORD: float  # X coordinate (court positioning)
    Y_COORD: float  # Y coordinate
    DISTANCE: float | None  # Distance from basket (feet or meters)
    ZONE: str | None  # Shot zone: "PAINT", "MID_RANGE", "3PT", etc.

    # Context
    SCORE_BEFORE: int  # Shooting team's score before shot
    SCORE_AFTER: int  # After shot (increases if made)
    ASSIST_PLAYER_ID: int | None
    ASSIST_PLAYER_NAME: str | None


# ==============================================================================
# PlayerSeason Schema
# ==============================================================================


@dataclass
class LNBPlayerSeason:
    """Aggregated player season stats.

    Can be derived from player_game or pulled from getPersonsLeaders endpoint.

    Primary Keys: (PLAYER_ID, SEASON, COMPETITION_ID)
    Foreign Keys: TEAM_ID → team
    Filters: season, player_id, team_id, per_mode
    """

    # Primary keys
    PLAYER_ID: int
    SEASON: int
    COMPETITION_ID: int

    # League/Team
    LEAGUE: str
    TEAM_ID: int
    TEAM_NAME: str

    # Player info
    PLAYER_NAME: str
    POSITION: str | None  # If API provides

    # Games
    GP: int  # Games played
    GS: int  # Games started
    MIN: float  # Total minutes

    # Totals (per_mode="Totals")
    PTS: int
    FGM: int
    FGA: int
    FG3M: int
    FG3A: int
    FTM: int
    FTA: int
    OREB: int
    DREB: int
    REB: int
    AST: int
    TOV: int
    STL: int
    BLK: int
    PF: int

    # Percentages (per_mode="PerGame" or derived)
    FG_PCT: float | None
    FG3_PCT: float | None
    FT_PCT: float | None
    PTS_PG: float  # Points per game
    REB_PG: float
    AST_PG: float
    EFG_PCT: float | None
    TS_PCT: float | None


# ==============================================================================
# TeamSeason Schema
# ==============================================================================


@dataclass
class LNBTeamSeason:
    """Aggregated team season stats (standings + aggregates).

    Primary Keys: (TEAM_ID, SEASON, COMPETITION_ID)
    Filters: season, team_id
    """

    # Primary keys
    TEAM_ID: int
    SEASON: int
    COMPETITION_ID: int

    # League
    LEAGUE: str
    TEAM_NAME: str

    # Record
    GP: int
    W: int
    L: int
    WIN_PCT: float
    RANK: int  # Standings rank

    # Totals/Averages
    PTS: int  # Total points scored
    OPP_PTS: int  # Total points allowed
    PTS_PG: float  # Points per game
    OPP_PTS_PG: float
    PTS_DIFF: int  # Point differential

    # Advanced
    ORTG: float  # Offensive rating
    DRTG: float  # Defensive rating
    NET_RTG: float  # Net rating

    # Home/Away splits
    HOME_W: int
    HOME_L: int
    AWAY_W: int
    AWAY_L: int

    # Streaks/Form
    STREAK: str | None  # "W3", "L2", etc.
    LAST_10: str | None  # "7-3", etc.


# ==============================================================================
# Helper Functions
# ==============================================================================


def calculate_efg(fgm: int, fg3m: int, fga: int) -> float | None:
    """Calculate Effective Field Goal Percentage.

    eFG% = (FGM + 0.5 * FG3M) / FGA

    Returns:
        eFG% as float [0.0, 1.0], or None if FGA=0
    """
    if fga == 0:
        return None
    return (fgm + 0.5 * fg3m) / fga


def calculate_ts(pts: int, fga: int, fta: int) -> float | None:
    """Calculate True Shooting Percentage.

    TS% = PTS / (2 * (FGA + 0.44 * FTA))

    Returns:
        TS% as float [0.0, ~1.0], or None if divisor=0
    """
    divisor = 2 * (fga + 0.44 * fta)
    if divisor == 0:
        return None
    return pts / divisor


def estimate_possessions(fga: int, fta: int, oreb: int, tov: int) -> float:
    """Estimate team possessions using basic formula.

    Poss ≈ FGA - OREB + TOV + 0.44 * FTA

    This is a simplified version; more complex formulas exist.

    Returns:
        Estimated possessions (float)
    """
    return fga - oreb + tov + 0.44 * fta


def calculate_rating(points: int, possessions: float) -> float | None:
    """Calculate offensive or defensive rating.

    Rating = (Points / Possessions) * 100

    Returns:
        Rating per 100 possessions, or None if poss=0
    """
    if possessions <= 0:
        return None
    return (points / possessions) * 100


# ==============================================================================
# Schema to Column Mapping (for DataFrame creation)
# ==============================================================================


def get_schedule_columns() -> list[str]:
    """Get column order for LNBSchedule DataFrame."""
    return [
        "GAME_ID",
        "LEAGUE",
        "SEASON",
        "COMPETITION",
        "COMPETITION_ID",
        "GAME_DATE",
        "GAME_TIME_UTC",
        "GAME_TIME_LOCAL",
        "HOME_TEAM_ID",
        "HOME_TEAM",
        "AWAY_TEAM_ID",
        "AWAY_TEAM",
        "HOME_SCORE",
        "AWAY_SCORE",
        "VENUE",
        "ROUND",
        "PHASE",
        "STATUS",
    ]


def get_team_game_columns() -> list[str]:
    """Get column order for LNBTeamGame DataFrame."""
    return [
        "GAME_ID",
        "TEAM_ID",
        "LEAGUE",
        "SEASON",
        "GAME_DATE",
        "OPPONENT_ID",
        "HOME_AWAY",
        "WON",
        "MIN",
        "PTS",
        "FGM",
        "FGA",
        "FG_PCT",
        "FG3M",
        "FG3A",
        "FG3_PCT",
        "FTM",
        "FTA",
        "FT_PCT",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "TOV",
        "STL",
        "BLK",
        "PF",
        "PLUS_MINUS",
        "EFG_PCT",
        "TS_PCT",
        "POSS",
        "ORTG",
        "DRTG",
    ]


def get_player_game_columns() -> list[str]:
    """Get column order for LNBPlayerGame DataFrame."""
    return [
        "GAME_ID",
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ID",
        "OPPONENT_ID",
        "LEAGUE",
        "SEASON",
        "GAME_DATE",
        "HOME_AWAY",
        "STARTER",
        "WON",
        "MIN",
        "PTS",
        "FGM",
        "FGA",
        "FG_PCT",
        "FG3M",
        "FG3A",
        "FG3_PCT",
        "FTM",
        "FTA",
        "FT_PCT",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "TOV",
        "STL",
        "BLK",
        "PF",
        "PLUS_MINUS",
        "EFG_PCT",
        "TS_PCT",
    ]


def get_pbp_columns() -> list[str]:
    """Get column order for LNBPlayByPlayEvent DataFrame."""
    return [
        "GAME_ID",
        "EVENT_ID",
        "PERIOD",
        "CLOCK_TIME",
        "SEQUENCE",
        "LEAGUE",
        "SEASON",
        "EVENT_TYPE",
        "EVENT_SUBTYPE",
        "DESCRIPTION",
        "TEAM_ID",
        "PLAYER1_ID",
        "PLAYER1_NAME",
        "PLAYER2_ID",
        "PLAYER2_NAME",
        "SCORE_HOME",
        "SCORE_AWAY",
        "SHOT_MADE",
        "SHOT_VALUE",
        "SHOT_TYPE",
        "FOUL_TYPE",
        "TURNOVER_TYPE",
    ]


def get_shots_columns() -> list[str]:
    """Get column order for LNBShotEvent DataFrame."""
    return [
        "GAME_ID",
        "SHOT_ID",
        "PERIOD",
        "CLOCK_TIME",
        "SEQUENCE",
        "LEAGUE",
        "SEASON",
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ID",
        "SHOT_MADE",
        "SHOT_VALUE",
        "SHOT_TYPE",
        "X_COORD",
        "Y_COORD",
        "DISTANCE",
        "ZONE",
        "SCORE_BEFORE",
        "SCORE_AFTER",
        "ASSIST_PLAYER_ID",
        "ASSIST_PLAYER_NAME",
    ]


def get_player_season_columns() -> list[str]:
    """Get column order for LNBPlayerSeason DataFrame."""
    return [
        "PLAYER_ID",
        "SEASON",
        "COMPETITION_ID",
        "LEAGUE",
        "TEAM_ID",
        "TEAM_NAME",
        "PLAYER_NAME",
        "POSITION",
        "GP",
        "GS",
        "MIN",
        "PTS",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "TOV",
        "STL",
        "BLK",
        "PF",
        "FG_PCT",
        "FG3_PCT",
        "FT_PCT",
        "PTS_PG",
        "REB_PG",
        "AST_PG",
        "EFG_PCT",
        "TS_PCT",
    ]


def get_team_season_columns() -> list[str]:
    """Get column order for LNBTeamSeason DataFrame."""
    return [
        "TEAM_ID",
        "SEASON",
        "COMPETITION_ID",
        "LEAGUE",
        "TEAM_NAME",
        "GP",
        "W",
        "L",
        "WIN_PCT",
        "RANK",
        "PTS",
        "OPP_PTS",
        "PTS_PG",
        "OPP_PTS_PG",
        "PTS_DIFF",
        "ORTG",
        "DRTG",
        "NET_RTG",
        "HOME_W",
        "HOME_L",
        "AWAY_W",
        "AWAY_L",
        "STREAK",
        "LAST_10",
    ]
