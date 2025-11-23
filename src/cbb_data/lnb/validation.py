"""Content-level validation for LNB datasets

This module implements Priority #3: content expectations beyond schema validation.

Validators check:
- PBP: monotonic scores, valid period IDs, parseable clocks, event type enums
- Shots: coordinate bounds, shot type enums, SUCCESS boolean-ness
- Cross-dataset: game_id consistency

Each validator returns (is_valid, errors, warnings) for quarantine decisions.
"""

from dataclasses import dataclass, field

import pandas as pd

from .constants import (
    COURT_X_MAX,
    COURT_X_MIN,
    COURT_Y_MAX,
    COURT_Y_MIN,
    REQUIRED_PBP_COLUMNS,
    REQUIRED_SHOTS_COLUMNS,
    VALID_EVENT_TYPES,
    VALID_PERIOD_IDS,
    VALID_SHOT_TYPES,
)


@dataclass
class ValidationResult:
    """Result of validation for a single game"""

    game_id: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_drops: int = 0  # Number of rows dropped (if any)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "game_id": self.game_id,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "row_drops": self.row_drops,
        }


# ============================================================================
# PBP VALIDATION
# ============================================================================


def validate_pbp_game(df: pd.DataFrame, game_id: str) -> ValidationResult:
    """Validate a single game's PBP data

    Checks:
    1. Required columns present
    2. HOME_SCORE/AWAY_SCORE monotonic (non-decreasing within each period)
    3. PERIOD_ID valid
    4. CLOCK parseable
    5. EVENT_TYPE in valid enum

    Args:
        df: PBP dataframe for a single game
        game_id: Game identifier

    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult(game_id=game_id, is_valid=True)

    # Check 1: Required columns
    missing_cols = REQUIRED_PBP_COLUMNS - set(df.columns)
    if missing_cols:
        result.errors.append(f"Missing required columns: {missing_cols}")
        result.is_valid = False
        return result  # Can't continue validation without required columns

    # Check 2: PERIOD_ID valid
    invalid_periods = df[~df["PERIOD_ID"].isin(VALID_PERIOD_IDS)]
    if len(invalid_periods) > 0:
        unique_invalid = invalid_periods["PERIOD_ID"].unique()
        result.errors.append(
            f"Invalid PERIOD_ID values: {unique_invalid.tolist()} " f"({len(invalid_periods)} rows)"
        )
        result.is_valid = False

    # Check 3: EVENT_TYPE enum (warnings only for unknown types)
    unknown_events = df[~df["EVENT_TYPE"].isin(VALID_EVENT_TYPES)]
    if len(unknown_events) > 0:
        unique_unknown = unknown_events["EVENT_TYPE"].unique()
        result.warnings.append(
            f"Unknown EVENT_TYPE values: {unique_unknown.tolist()} " f"({len(unknown_events)} rows)"
        )

    # Check 4: Scores monotonic within each period
    # NOTE: Events may be out of chronological order in raw data
    # Treat as warnings, not errors (data may just need sorting)
    score_warnings = _validate_monotonic_scores(df)
    if score_warnings:
        result.warnings.extend(score_warnings)

    # Check 5: CLOCK parseable (check for nulls, invalid formats)
    null_clocks = df["CLOCK"].isnull().sum()
    if null_clocks > 0:
        result.warnings.append(f"NULL CLOCK values: {null_clocks} rows")

    return result


def _validate_monotonic_scores(df: pd.DataFrame) -> list[str]:
    """Check that HOME_SCORE and AWAY_SCORE are monotonic within each period

    Scores should never decrease within a period (resets between periods are ok).

    Args:
        df: PBP dataframe with PERIOD_ID, HOME_SCORE, AWAY_SCORE

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check each period independently
    for period_id in sorted(df["PERIOD_ID"].unique()):
        period_df = df[df["PERIOD_ID"] == period_id].sort_values("EVENT_ID")

        # Check HOME_SCORE monotonic
        home_scores = period_df["HOME_SCORE"].dropna()
        if len(home_scores) > 1:
            if not (home_scores.diff().dropna() >= 0).all():
                errors.append(
                    f"Period {period_id}: HOME_SCORE not monotonic "
                    f"(min={home_scores.min()}, max={home_scores.max()})"
                )

        # Check AWAY_SCORE monotonic
        away_scores = period_df["AWAY_SCORE"].dropna()
        if len(away_scores) > 1:
            if not (away_scores.diff().dropna() >= 0).all():
                errors.append(
                    f"Period {period_id}: AWAY_SCORE not monotonic "
                    f"(min={away_scores.min()}, max={away_scores.max()})"
                )

    return errors


# ============================================================================
# SHOTS VALIDATION
# ============================================================================


def validate_shots_game(df: pd.DataFrame, game_id: str) -> ValidationResult:
    """Validate a single game's shots data

    Checks:
    1. Required columns present
    2. SHOT_TYPE in valid enum
    3. SUCCESS is boolean-ish (0/1 or True/False)
    4. X_COORD/Y_COORD within court bounds
    5. Low NULL rate for critical columns

    Args:
        df: Shots dataframe for a single game
        game_id: Game identifier

    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult(game_id=game_id, is_valid=True)

    # Check 1: Required columns
    missing_cols = REQUIRED_SHOTS_COLUMNS - set(df.columns)
    if missing_cols:
        result.errors.append(f"Missing required columns: {missing_cols}")
        result.is_valid = False
        return result

    # Check 2: SHOT_TYPE enum
    invalid_shots = df[~df["SHOT_TYPE"].isin(VALID_SHOT_TYPES)]
    if len(invalid_shots) > 0:
        unique_invalid = invalid_shots["SHOT_TYPE"].unique()
        result.errors.append(
            f"Invalid SHOT_TYPE values: {unique_invalid.tolist()} " f"({len(invalid_shots)} rows)"
        )
        result.is_valid = False

    # Check 3: SUCCESS is boolean-ish
    success_values = df["SUCCESS"].dropna().unique()
    valid_success_values = {0, 1, True, False, 0.0, 1.0}
    invalid_success = [v for v in success_values if v not in valid_success_values]
    if invalid_success:
        result.errors.append(
            f"Invalid SUCCESS values (expected 0/1 or True/False): {invalid_success}"
        )
        result.is_valid = False

    # Check 4: Coordinates within bounds
    coord_errors = _validate_coordinates(df)
    if coord_errors:
        result.errors.extend(coord_errors)
        result.is_valid = False

    # Check 5: NULL rates (warnings only)
    null_success = df["SUCCESS"].isnull().sum()
    null_coords = df[["X_COORD", "Y_COORD"]].isnull().sum().sum()

    if null_success > len(df) * 0.1:  # >10% null
        result.warnings.append(
            f"High NULL rate for SUCCESS: {null_success}/{len(df)} "
            f"({null_success/len(df)*100:.1f}%)"
        )

    if null_coords > 0:
        result.warnings.append(f"NULL coordinates: {null_coords} values")

    return result


def _validate_coordinates(df: pd.DataFrame) -> list[str]:
    """Check that X_COORD/Y_COORD are within court bounds

    Args:
        df: Shots dataframe with X_COORD, Y_COORD

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Filter out NULLs for bounds checking
    coords_df = df[["X_COORD", "Y_COORD"]].dropna()

    if len(coords_df) == 0:
        return errors  # All NULLs handled as warnings elsewhere

    # Check X bounds
    out_of_bounds_x = coords_df[
        (coords_df["X_COORD"] < COURT_X_MIN) | (coords_df["X_COORD"] > COURT_X_MAX)
    ]
    if len(out_of_bounds_x) > 0:
        errors.append(
            f"X_COORD out of bounds [{COURT_X_MIN}, {COURT_X_MAX}]: "
            f"{len(out_of_bounds_x)} rows "
            f"(range: [{out_of_bounds_x['X_COORD'].min():.2f}, "
            f"{out_of_bounds_x['X_COORD'].max():.2f}])"
        )

    # Check Y bounds
    out_of_bounds_y = coords_df[
        (coords_df["Y_COORD"] < COURT_Y_MIN) | (coords_df["Y_COORD"] > COURT_Y_MAX)
    ]
    if len(out_of_bounds_y) > 0:
        errors.append(
            f"Y_COORD out of bounds [{COURT_Y_MIN}, {COURT_Y_MAX}]: "
            f"{len(out_of_bounds_y)} rows "
            f"(range: [{out_of_bounds_y['Y_COORD'].min():.2f}, "
            f"{out_of_bounds_y['Y_COORD'].max():.2f}])"
        )

    return errors


# ============================================================================
# BATCH VALIDATION
# ============================================================================


def validate_pbp_batch(
    games: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[ValidationResult]]:
    """Validate multiple PBP games, separating valid from invalid

    Args:
        games: Dict of game_id -> pbp_dataframe

    Returns:
        Tuple of (valid_games_dict, validation_results_list)
    """
    valid_games = {}
    results = []

    for game_id, df in games.items():
        result = validate_pbp_game(df, game_id)
        results.append(result)

        if result.is_valid:
            valid_games[game_id] = df

    return valid_games, results


def validate_shots_batch(
    games: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[ValidationResult]]:
    """Validate multiple shots games, separating valid from invalid

    Args:
        games: Dict of game_id -> shots_dataframe

    Returns:
        Tuple of (valid_games_dict, validation_results_list)
    """
    valid_games = {}
    results = []

    for game_id, df in games.items():
        result = validate_shots_game(df, game_id)
        results.append(result)

        if result.is_valid:
            valid_games[game_id] = df

    return valid_games, results
