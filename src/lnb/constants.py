"""Canonical constants for LNB data infrastructure

This module defines the single source of truth for:
- League identifiers
- Expected schemas
- Valid enums for content validation

NO DRIFT ALLOWED: All LNB code must import from here.
"""

# ============================================================================
# LEAGUE IDENTIFIERS (canonical enum)
# ============================================================================

LNB_LEAGUES = ["betclic_elite", "elite_2", "espoirs_elite", "espoirs_prob"]

# Invariant: every row in any curated LNB dataset must have
# league ∈ LNB_LEAGUES


# ============================================================================
# SCHEMA REQUIREMENTS
# ============================================================================

# Game Index (master truth)
REQUIRED_INDEX_COLUMNS = {
    "season",
    "league",
    "competition",
    "game_id",
    "game_date",
    "home_team_name",
    "away_team_name",
    "has_pbp",
    "has_shots",
}

# Play-by-Play
REQUIRED_PBP_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "EVENT_TYPE",
    "HOME_SCORE",
    "AWAY_SCORE",
}

# Shots
REQUIRED_SHOTS_COLUMNS = {
    "GAME_ID",
    "EVENT_ID",
    "PERIOD_ID",
    "CLOCK",
    "SHOT_TYPE",
    "SUCCESS",
    "X_COORD",
    "Y_COORD",
}

# Boxscore (if implemented)
REQUIRED_BOX_COLUMNS = {
    "GAME_ID",
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
}


# ============================================================================
# VALID ENUMS (for content validation)
# ============================================================================

# Valid period IDs
# - 1-4: Regulation quarters
# - 11+: Overtime periods (LNB API uses 11 for OT1, 12 for OT2, etc.)
# NOTE: Empirically observed from raw data, not standard FIBA numbering
VALID_PERIOD_IDS = {1, 2, 3, 4, 11, 12, 13, 14, 15}  # regulation + up to 5 OTs

# Valid event types (camelCase as returned by LNB Atrium API)
# NOTE: These are empirically observed from raw data, not guessed
VALID_EVENT_TYPES = {
    "jumpBall",
    "2pt",
    "3pt",
    "freeThrow",
    "rebound",
    "assist",
    "turnover",
    "steal",
    "block",
    "foul",
    "substitution",
    "timeOut",
    "periodStart",
    "periodEnd",
    "gameEnd",
    # Add more as discovered in raw data
}

# Valid shot types (lowercase as returned by LNB API)
# NOTE: Empirically observed from raw data
VALID_SHOT_TYPES = {
    "2pt",  # Two-point shot
    "3pt",  # Three-point shot
    "ft",   # Free throw
}

# Court bounds (LNB API coordinate system, empirically observed)
# NOTE: Coordinates appear to be in a 0-100 scale system
# Valid range extends beyond physical court for edge shots
COURT_X_MIN = 0.0
COURT_X_MAX = 100.0
COURT_Y_MIN = 0.0
COURT_Y_MAX = 100.0


# ============================================================================
# METADATA COLUMNS TO ATTACH (from index to curated datasets)
# ============================================================================

METADATA_COLUMNS_TO_ATTACH = [
    "season",
    "league",
    "competition",
    "game_date",
    "home_team_name",
    "away_team_name",
]
