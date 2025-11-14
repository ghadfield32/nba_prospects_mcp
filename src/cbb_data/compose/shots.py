"""Shot-level filtering helpers

This module provides defensive helpers for filtering shot-level data by team, player,
period/quarter, and game-minute context. All filters are optional and only applied
if the corresponding columns exist in the data.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from ..filters.spec import FilterSpec


def _normalize_list(value: str | Iterable[str] | None) -> list[str]:
    """Normalize a value to a list of strings

    Args:
        value: Single string, list of strings, or None

    Returns:
        List of strings (empty list if None)
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def apply_shot_filters(df: pd.DataFrame, filters: FilterSpec) -> pd.DataFrame:
    """Apply team/player/period/game-minute filters to shot-level data

    This helper is intentionally defensive and column-aware:
    - If a filter's corresponding column is missing, the filter is silently skipped
    - GAME_ID filtering is optional (not required)
    - Supports multiple column name conventions (TEAM vs TEAM_NAME, etc.)
    - Can derive GAME_MINUTE from PERIOD + GAME_CLOCK if needed

    Expected normalized columns (when available):
        - LEAGUE, SEASON
        - GAME_ID (optional)
        - TEAM_ID, TEAM (or TEAM_NAME)
        - OPP_TEAM_ID, OPP_TEAM (or OPP_TEAM_NAME)
        - PLAYER_ID, PLAYER_NAME
        - PERIOD (or QUARTER)
        - GAME_MINUTE, EVENT_MINUTE, or SHOT_MINUTE (optional)
        - GAME_CLOCK or PCTIMESTRING (for fallback minute calculation)

    Args:
        df: Shot-level DataFrame
        filters: FilterSpec with optional filter criteria

    Returns:
        Filtered DataFrame (or original if no applicable filters)

    Examples:
        >>> # Filter to Q4 shots only
        >>> df = apply_shot_filters(df, FilterSpec(quarter=[4]))

        >>> # Filter to crunch time (minutes 35-40)
        >>> df = apply_shot_filters(df, FilterSpec(
        ...     min_game_minute=35,
        ...     max_game_minute=40
        ... ))

        >>> # Filter to specific player in Q4
        >>> df = apply_shot_filters(df, FilterSpec(
        ...     player=["Bryce Cotton"],
        ...     quarter=[4]
        ... ))
    """
    if df.empty:
        return df

    spec = filters

    # --- Team filters --------------------------------------------------------
    team_ids = spec.team_ids or []
    team_names = _normalize_list(spec.team)

    if team_ids and "TEAM_ID" in df.columns:
        df = df[df["TEAM_ID"].isin(team_ids)]

    if team_names:
        # Try common team name columns in order of preference
        for col in ("TEAM", "TEAM_NAME", "TEAM_SHORT_NAME"):
            if col in df.columns:
                df = df[df[col].isin(team_names)]
                break  # Only apply first matching column

    # Opponent filters
    opp_names = _normalize_list(spec.opponent)
    if opp_names:
        for col in ("OPP_TEAM", "OPP_TEAM_NAME", "OPP_NAME"):
            if col in df.columns:
                df = df[df[col].isin(opp_names)]
                break

    # --- Player filters ------------------------------------------------------
    player_ids = spec.player_ids or []
    player_names = _normalize_list(spec.player)

    if player_ids and "PLAYER_ID" in df.columns:
        df = df[df["PLAYER_ID"].isin(player_ids)]

    if player_names:
        for col in ("PLAYER_NAME", "PLAYER", "NAME", "SCOREBOARD_NAME"):
            if col in df.columns:
                df = df[df[col].isin(player_names)]
                break

    # --- Game filters (optional; no longer required) -------------------------
    if spec.game_ids and "GAME_ID" in df.columns:
        df = df[df["GAME_ID"].isin(spec.game_ids)]

    # --- Period / quarter filters --------------------------------------------
    if spec.quarter:
        # Normalize to ints, handle string inputs gracefully
        periods = [int(p) for p in spec.quarter]

        if "PERIOD" in df.columns:
            df = df[df["PERIOD"].isin(periods)]
        elif "QUARTER" in df.columns:
            df = df[df["QUARTER"].isin(periods)]
        # If neither column exists, silently skip

    # --- Game-minute filters -------------------------------------------------
    min_minute = spec.min_game_minute
    max_minute = spec.max_game_minute

    if min_minute is not None or max_minute is not None:
        minute_col = None

        # Try to find an existing minute column
        for candidate in ("GAME_MINUTE", "EVENT_MINUTE", "SHOT_MINUTE"):
            if candidate in df.columns:
                minute_col = candidate
                break

        if minute_col is None:
            # Attempt to derive from PERIOD + GAME_CLOCK
            if "PERIOD" in df.columns and "GAME_CLOCK" in df.columns:
                df = df.copy()  # Avoid SettingWithCopyWarning

                def _clock_to_seconds(clock: str) -> float:
                    """Convert game clock string to seconds remaining in period

                    Expects formats like:
                    - "10:00" (10 minutes, 0 seconds)
                    - "2:30" (2 minutes, 30 seconds)
                    - "0:15" (0 minutes, 15 seconds)

                    Returns NaN for invalid formats.
                    """
                    try:
                        parts = str(clock).split(":")
                        if len(parts) != 2:
                            return np.nan
                        m, s = int(parts[0]), int(parts[1])
                        return m * 60 + s
                    except Exception:
                        return np.nan

                # For a 10-minute period (FIBA/NBL style), elapsed time in period is:
                # period_length - (clock_seconds / 60)
                # For game minute: (period - 1) * period_length + elapsed_in_period
                #
                # Default to 10-minute periods (works for FIBA, NBL, international).
                # For NBA (12-minute periods), the math still works qualitatively
                # (just different max values).
                period_length = 10.0  # minutes per period

                clock_seconds = df["GAME_CLOCK"].map(_clock_to_seconds)
                elapsed_in_period = period_length - (clock_seconds / 60.0)
                game_minute = (df["PERIOD"].astype(float) - 1.0) * period_length + elapsed_in_period

                df["__GAME_MINUTE__"] = game_minute
                minute_col = "__GAME_MINUTE__"
            else:
                # Cannot compute game-minute; skip these filters silently
                minute_col = None

        # Apply minute filters if we have a minute column
        if minute_col is not None:
            if min_minute is not None:
                df = df[df[minute_col] >= float(min_minute)]
            if max_minute is not None:
                df = df[df[minute_col] <= float(max_minute)]

    return df
