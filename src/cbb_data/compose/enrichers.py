"""Data composition and enrichment utilities

This module provides functions to:
1. Normalize column names across different sources
2. Add derived fields (e.g., HOME_AWAY from MATCHUP)
3. Compose multi-source datasets (e.g., player + team data)
"""

from __future__ import annotations

import pandas as pd


def coerce_common_columns(df: pd.DataFrame, source: str = "generic") -> pd.DataFrame:
    """Normalize column names and types across data sources

    Different sources use different naming conventions:
    - ESPN: PLAYER_NAME, TEAM_ABBREVIATION, etc.
    - EuroLeague: Dorsal, Player_ID, Team, etc.
    - Sports-Ref: varies by page

    This function maps source-specific names to our standard schema.

    Args:
        df: Input DataFrame
        source: Data source identifier ("espn", "euroleague", "sportsref", etc.)

    Returns:
        DataFrame with standardized column names
    """
    if df.empty:
        return df

    out = df.copy()

    # Source-specific rename maps
    rename_maps = {
        "espn": {
            "PLAYER_NAME": "PLAYER_NAME",
            "TEAM_ABBREVIATION": "TEAM_ABBREVIATION",
            "TEAM_ID": "TEAM_ID",
            "PLAYER_ID": "PLAYER_ID",
            "GAME_ID": "GAME_ID",
            "GAME_DATE": "GAME_DATE",
            "MATCHUP": "MATCHUP",
            # Schedule-specific columns (standardize ESPN → common schema)
            "HOME_TEAM_NAME": "HOME_TEAM",
            "AWAY_TEAM_NAME": "AWAY_TEAM",
        },
        "euroleague": {
            "Player_ID": "PLAYER_ID",
            "Player": "PLAYER_NAME",
            "Team": "TEAM_NAME",
            "Gamecode": "GAME_ID",
            "Phase": "SEASON_TYPE",
            "Season": "SEASON",
            "Round": "ROUND",
            "Dorsal": "JERSEY",
        },
        "sportsref": {
            "Player": "PLAYER_NAME",
            "School": "TEAM_NAME",
            "Date": "GAME_DATE",
            "Opp": "OPPONENT_NAME",
            # Sports-Ref varies; add more as needed
        },
    }

    # Apply rename if we have a map for this source
    if source in rename_maps:
        # Only rename columns that exist
        rename_map = {k: v for k, v in rename_maps[source].items() if k in out.columns}
        out = out.rename(columns=rename_map)

    # Coerce ID columns to Int64 (nullable integer)
    id_cols = ["TEAM_ID", "PLAYER_ID", "OPPONENT_TEAM_ID", "OPPONENT_ID"]
    for col in id_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # Coerce date columns
    if "GAME_DATE" in out.columns and out["GAME_DATE"].dtype == "object":
        out["GAME_DATE"] = pd.to_datetime(out["GAME_DATE"], errors="coerce")

    return out


def add_home_away(df: pd.DataFrame) -> pd.DataFrame:
    """Add HOME_AWAY column derived from MATCHUP

    ESPN uses MATCHUP format: "TEAM vs. OPP" (home) or "TEAM @ OPP" (away)
    EuroLeague and others may use different conventions.

    Args:
        df: DataFrame with MATCHUP column

    Returns:
        DataFrame with added HOME_AWAY column
    """
    if df.empty:
        return df

    # Already has HOME_AWAY
    if "HOME_AWAY" in df.columns:
        return df

    # No MATCHUP to derive from
    if "MATCHUP" not in df.columns:
        return df

    out = df.copy()

    # ESPN MATCHUP format: "DUK vs. UNC" (home) or "DUK @ UNC" (away)
    # Use "vs." as home indicator (more robust than "@")
    out["HOME_AWAY"] = (
        out["MATCHUP"]
        .str.contains(" vs. ", case=False, na=False)
        .map({True: "Home", False: "Away"})
    )

    return out


def extract_opponent(df: pd.DataFrame) -> pd.DataFrame:
    """Extract opponent information from MATCHUP

    Args:
        df: DataFrame with MATCHUP column

    Returns:
        DataFrame with added OPPONENT_ABBREVIATION column
    """
    if df.empty:
        return df

    if "MATCHUP" not in df.columns:
        return df

    if "OPPONENT_ABBREVIATION" in df.columns:
        return df

    out = df.copy()

    # Extract opponent from MATCHUP
    # Format: "DUK vs. UNC" or "DUK @ UNC"
    out["OPPONENT_ABBREVIATION"] = (
        out["MATCHUP"].str.replace(r"^.+?\s+(?:vs\.|@)\s+", "", regex=True).str.strip()
    )

    return out


def compose_player_team_game(
    df_player_game: pd.DataFrame,
    df_team_game: pd.DataFrame,
) -> pd.DataFrame:
    """Compose player/game data with team/game context

    Enriches player game logs with team-level information:
    - Home/Away status
    - Team matchup
    - Opponent ID/name
    - Team-level stats (optional)

    Args:
        df_player_game: Per-player per-game data
        df_team_game: Per-team per-game data

    Returns:
        Merged DataFrame with player + team context
    """
    if df_player_game.empty:
        return df_player_game

    if df_team_game.empty:
        # Can't enrich; return as-is
        return df_player_game

    # Normalize both DataFrames
    pg = coerce_common_columns(df_player_game)
    tg = add_home_away(coerce_common_columns(df_team_game))
    tg = extract_opponent(tg)

    # Join keys
    keys = ["TEAM_ID", "GAME_ID"]

    # Select team columns to add (avoid duplicates)
    team_cols = [
        c
        for c in tg.columns
        if c in keys  # join keys
        or c
        in [
            "MATCHUP",
            "HOME_AWAY",
            "TEAM_ABBREVIATION",
            "OPPONENT_ABBREVIATION",
            "OPPONENT_TEAM_ID",
            "OPPONENT_ID",
        ]
        or c.endswith("_PCT")  # team shooting percentages
    ]

    # Drop duplicates on join keys
    tg_subset = tg[team_cols].drop_duplicates(subset=keys)

    # Left join (keep all player data)
    merged = pg.merge(tg_subset, on=keys, how="left", suffixes=("", "_TEAM"))

    return merged


def add_season_context(df: pd.DataFrame, season: str) -> pd.DataFrame:
    """Add SEASON column if not present

    Args:
        df: Input DataFrame
        season: Season identifier (e.g., "2024-25")

    Returns:
        DataFrame with SEASON column
    """
    if df.empty:
        return df

    out = df.copy()

    if "SEASON" not in out.columns:
        out["SEASON"] = season

    return out


def add_league_context(df: pd.DataFrame, league: str) -> pd.DataFrame:
    """Add LEAGUE column if not present

    Args:
        df: Input DataFrame
        league: League identifier (e.g., "NCAA-MBB")

    Returns:
        DataFrame with LEAGUE column
    """
    if df.empty:
        return df

    out = df.copy()

    if "LEAGUE" not in out.columns:
        out["LEAGUE"] = league

    return out


def standardize_stats_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize common stats column names

    Ensures consistent naming across sources:
    - PTS, AST, REB, etc. (uppercase)
    - FG_PCT, FG3_PCT, FT_PCT (not FG%, 3P%, FT%)

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with standardized stat column names
    """
    if df.empty:
        return df

    out = df.copy()

    # Common stat renames
    stat_renames = {
        "Points": "PTS",
        "Assists": "AST",
        "Rebounds": "REB",
        "Steals": "STL",
        "Blocks": "BLK",
        "Turnovers": "TOV",
        "FG%": "FG_PCT",
        "3P%": "FG3_PCT",
        "FT%": "FT_PCT",
        "FGM": "FGM",
        "FGA": "FGA",
        "3PM": "FG3M",
        "3PA": "FG3A",
        "FTM": "FTM",
        "FTA": "FTA",
        "OREB": "OREB",
        "DREB": "DREB",
        "Minutes": "MIN",
    }

    # Only rename if column exists
    rename_map = {k: v for k, v in stat_renames.items() if k in out.columns}
    if rename_map:
        out = out.rename(columns=rename_map)

    return out


def aggregate_per_mode(
    df: pd.DataFrame, per_mode: str = "Totals", group_by: list[str] | None = None
) -> pd.DataFrame:
    """Aggregate player stats by per_mode

    Supports three aggregation modes:
    - "Totals": Sum all stats across games (default)
    - "PerGame": Average stats per game
    - "Per40": Normalize stats to per 40 minutes played

    Args:
        df: Player game data with stats columns
        per_mode: Aggregation mode ("Totals", "PerGame", "Per40")
        group_by: Columns to group by (default: ["PLAYER_ID", "PLAYER_NAME"])

    Returns:
        Aggregated DataFrame

    Examples:
        >>> # Get season totals
        >>> totals = aggregate_per_mode(player_games, "Totals")

        >>> # Get per-game averages
        >>> per_game = aggregate_per_mode(player_games, "PerGame")

        >>> # Get per-40-minute stats
        >>> per40 = aggregate_per_mode(player_games, "Per40")
    """
    if df.empty:
        return df

    # Default grouping: by player
    if group_by is None:
        # Try PLAYER_ID first, fall back to PLAYER_NAME
        if "PLAYER_ID" in df.columns:
            group_by = ["PLAYER_ID"]
            if "PLAYER_NAME" in df.columns:
                group_by.append("PLAYER_NAME")
        elif "PLAYER_NAME" in df.columns:
            group_by = ["PLAYER_NAME"]
        else:
            raise ValueError("DataFrame must have PLAYER_ID or PLAYER_NAME column")

    # Stat columns to aggregate (numeric only)
    stat_cols = [
        "PTS",
        "AST",
        "REB",
        "STL",
        "BLK",
        "TOV",
        "PF",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
        "MIN",
    ]

    # Filter to columns that exist
    agg_cols = [c for c in stat_cols if c in df.columns]

    if not agg_cols:
        raise ValueError(f"No stat columns found. Available: {list(df.columns)}")

    # Determine which game ID column exists (NCAA uses GAME_ID, EuroLeague uses GAME_CODE)
    game_id_col = None
    if "GAME_ID" in df.columns:
        game_id_col = "GAME_ID"
    elif "GAME_CODE" in df.columns:
        game_id_col = "GAME_CODE"
    else:
        raise ValueError(
            "DataFrame must have GAME_ID or GAME_CODE column for counting games played. "
            f"Available columns: {list(df.columns)}"
        )

    # Count games played using the detected column
    df_agg = df.groupby(group_by, as_index=False).agg(
        {
            **{col: "sum" for col in agg_cols},
            game_id_col: "nunique",  # Count unique games played
        }
    )

    # Rename game ID count to GP (games played)
    df_agg = df_agg.rename(columns={game_id_col: "GP"})

    # Apply per_mode transformation
    if per_mode == "Totals":
        # Already summed, no transformation needed
        pass

    elif per_mode == "PerGame":
        # Divide all stats by games played
        for col in agg_cols:
            if col in df_agg.columns:
                # FIX: Only divide if column is numeric (prevents TypeError for string columns)
                if pd.api.types.is_numeric_dtype(df_agg[col]):
                    df_agg[col] = df_agg[col] / df_agg["GP"]

    elif per_mode == "Per40":
        # Normalize to per 40 minutes
        if "MIN" not in df_agg.columns:
            raise ValueError("Per40 mode requires MIN (minutes) column")

        for col in agg_cols:
            if col != "MIN" and col in df_agg.columns:
                # FIX: Only divide if column is numeric (prevents TypeError for string columns)
                if pd.api.types.is_numeric_dtype(df_agg[col]):
                    # Avoid division by zero
                    df_agg[col] = df_agg[col] / df_agg["MIN"].replace(0, 1) * 40

        # Minutes per game (not per 40)
        df_agg["MIN"] = df_agg["MIN"] / df_agg["GP"]

    else:
        raise ValueError(f"Invalid per_mode: {per_mode}. Must be 'Totals', 'PerGame', or 'Per40'")

    # Calculate shooting percentages (if FGA/FG3A/FTA exist)
    if "FGM" in df_agg.columns and "FGA" in df_agg.columns:
        df_agg["FG_PCT"] = (df_agg["FGM"] / df_agg["FGA"].replace(0, 1)).fillna(0)

    if "FG3M" in df_agg.columns and "FG3A" in df_agg.columns:
        df_agg["FG3_PCT"] = (df_agg["FG3M"] / df_agg["FG3A"].replace(0, 1)).fillna(0)

    if "FTM" in df_agg.columns and "FTA" in df_agg.columns:
        df_agg["FT_PCT"] = (df_agg["FTM"] / df_agg["FTA"].replace(0, 1)).fillna(0)

    # Round numeric columns for readability
    numeric_cols = df_agg.select_dtypes(include=["float64"]).columns
    df_agg[numeric_cols] = df_agg[numeric_cols].round(1)

    return df_agg


# ============================================================================
# Guardrails: Decimal Rounding & Datetime Standardization
# ============================================================================


def apply_decimal_rounding(
    df: pd.DataFrame, precision: int = 4, compact: bool = False
) -> pd.DataFrame:
    """
    Round all float columns to specified precision for token stability.

    Rounding benefits:
        - Reduces token count (0.3333333333 → 0.3333)
        - Stabilizes LLM parsing (no floating point noise)
        - Improves readability

    Args:
        df: Input DataFrame
        precision: Decimal places to round to (default: 4)
        compact: If True, use reduced precision (1-2 decimals) for better token savings

    Returns:
        DataFrame with rounded float columns

    Examples:
        >>> df = pd.DataFrame({"PTS": [20.123456], "FG_PCT": [0.456789]})
        >>> rounded = apply_decimal_rounding(df, precision=2)
        >>> rounded["FG_PCT"].iloc[0]
        0.46

        >>> # Compact mode for aggressive token savings
        >>> compact = apply_decimal_rounding(df, compact=True)
        >>> compact["PTS"].iloc[0]
        20.1  # 1 decimal for counting stats
    """
    if df.empty:
        return df

    out = df.copy()

    # Determine precision based on mode
    if compact:
        # Compact mode: aggressive rounding
        # - Percentages: 3 decimals (0.456 = 45.6%)
        # - Counting stats: 1 decimal (20.1 points)
        # - Advanced stats: 2 decimals (110.25 ORTG)

        pct_cols = [c for c in out.columns if "PCT" in c.upper() or "_RATE" in c.upper()]
        counting_cols = ["PTS", "AST", "REB", "STL", "BLK", "TOV", "MIN"]
        advanced_cols = [c for c in out.columns if "RATING" in c.upper() or "USG" in c.upper()]

        for col in out.select_dtypes(include=["float", "float64"]).columns:
            if col in pct_cols:
                out[col] = out[col].round(3)
            elif col in counting_cols:
                out[col] = out[col].round(1)
            elif col in advanced_cols:
                out[col] = out[col].round(2)
            else:
                out[col] = out[col].round(2)  # Default: 2 decimals
    else:
        # Standard mode: uniform precision
        for col in out.select_dtypes(include=["float", "float64"]).columns:
            out[col] = out[col].round(precision)

    return out


def standardize_datetimes(
    df: pd.DataFrame, timezone: str = "UTC", format: str = "iso"
) -> pd.DataFrame:
    """
    Standardize all datetime columns to ISO-8601 UTC format.

    Benefits:
        - Consistent format across all datasets
        - Timezone-aware (prevents ambiguity)
        - LLM-friendly (ISO-8601 is widely recognized)
        - Sortable as strings

    Args:
        df: Input DataFrame
        timezone: Target timezone (default: "UTC")
        format: Output format - "iso" for ISO-8601, "unix" for Unix timestamp

    Returns:
        DataFrame with standardized datetime columns

    Examples:
        >>> df = pd.DataFrame({"GAME_DATE": [pd.Timestamp("2025-01-15 19:00:00")]})
        >>> standardized = standardize_datetimes(df)
        >>> standardized["GAME_DATE"].iloc[0]
        '2025-01-15T19:00:00+00:00'  # ISO-8601 UTC

        >>> # Unix timestamp format
        >>> unix = standardize_datetimes(df, format="unix")
        >>> unix["GAME_DATE"].iloc[0]
        1736967600  # Seconds since epoch
    """
    if df.empty:
        return df

    out = df.copy()

    # Find datetime columns
    datetime_cols = out.select_dtypes(include=["datetime64", "datetimetz"]).columns

    for col in datetime_cols:
        if format == "iso":
            # Convert to UTC and format as ISO-8601
            if out[col].dt.tz is None:
                # Localize to UTC if naive
                out[col] = out[col].dt.tz_localize("UTC")
            else:
                # Convert to UTC if already timezone-aware
                out[col] = out[col].dt.tz_convert("UTC")

            # Convert to ISO-8601 string
            out[col] = out[col].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        elif format == "unix":
            # Convert to Unix timestamp (seconds since epoch)
            out[col] = out[col].astype("int64") // 10**9  # nanoseconds → seconds

        else:
            raise ValueError(f"Invalid format: {format}. Must be 'iso' or 'unix'")

    return out


def apply_guardrails(
    df: pd.DataFrame,
    round_decimals: bool = True,
    precision: int = 4,
    compact: bool = False,
    standardize_dates: bool = True,
    timezone: str = "UTC",
) -> pd.DataFrame:
    """
    Apply all guardrails (rounding + datetime standardization) in one pass.

    This is the recommended function to use for LLM-friendly data preparation.

    Args:
        df: Input DataFrame
        round_decimals: Enable decimal rounding (default: True)
        precision: Decimal places (default: 4)
        compact: Use compact mode for aggressive token savings (default: False)
        standardize_dates: Standardize datetimes to ISO-8601 UTC (default: True)
        timezone: Target timezone (default: "UTC")

    Returns:
        DataFrame with all guardrails applied

    Examples:
        >>> df = pd.DataFrame({
        ...     "GAME_DATE": [pd.Timestamp("2025-01-15")],
        ...     "PTS": [20.123456],
        ...     "FG_PCT": [0.456789]
        ... })
        >>> clean = apply_guardrails(df, compact=True)
        >>> clean["PTS"].iloc[0]
        20.1
        >>> clean["FG_PCT"].iloc[0]
        0.457
        >>> clean["GAME_DATE"].iloc[0]
        '2025-01-15T00:00:00+00:00'
    """
    if df.empty:
        return df

    out = df.copy()

    # Apply decimal rounding
    if round_decimals:
        out = apply_decimal_rounding(out, precision=precision, compact=compact)

    # Standardize datetimes
    if standardize_dates:
        out = standardize_datetimes(out, timezone=timezone)

    return out
