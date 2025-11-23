"""Filter compiler - converts FilterSpec to endpoint params and post-masks

The compiler takes a normalized FilterSpec and produces:
1. Endpoint-specific parameters (for API calls)
2. Post-processing masks (for filtering results after fetch)

This separation allows us to:
- Use native endpoint filters when available (more efficient)
- Apply additional filters client-side when endpoints don't support them
- Handle differences between ESPN, EuroLeague, Sports-Ref, etc.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .spec import FilterSpec

# Type alias for entity resolver function
# Takes (name, entity_type, league) and returns ID or None
ResolverFn = Callable[[str, str, str | None], int | None]


def _resolve_names_to_ids(
    names: list[str] | None,
    entity_type: str,
    league: str | None,
    resolver: ResolverFn | None,
) -> list[int] | None:
    """Resolve entity names to IDs using the provided resolver

    Args:
        names: List of entity names (team/player)
        entity_type: "team" or "player"
        league: League context for resolution (e.g., "NCAA-MBB")
        resolver: Function to resolve name -> ID

    Returns:
        List of resolved IDs, or None if no resolver or no names
    """
    if not names:
        return None
    if not resolver:
        # No resolver provided; post-mask will handle name matching
        return None

    ids = []
    for name in names:
        try:
            resolved_id = resolver(name, entity_type, league)
            if resolved_id is not None:
                ids.append(resolved_id)
        except Exception:
            # Resolver failed; skip this name
            continue

    return ids or None


def compile_params(
    dataset_id: str,
    f: FilterSpec,
    name_resolver: ResolverFn | None = None,
) -> dict[str, Any]:
    """Convert FilterSpec to endpoint params + post-mask dict

    This function is the core translation layer between our unified FilterSpec
    and the specific requirements of each data source (ESPN, EuroLeague, etc.)

    Args:
        dataset_id: Dataset being queried (affects param generation)
        f: The filter specification
        name_resolver: Optional function to resolve names -> IDs

    Returns:
        Dictionary with:
            - "params": endpoint-specific parameters for API call
            - "post_mask": filters to apply after fetching data
            - "meta": metadata about the query (league, season, etc.)

    Example:
        >>> spec = FilterSpec(
        ...     league="NCAA-MBB",
        ...     season="2024-25",
        ...     team=["Duke"],
        ...     last_n_games=5
        ... )
        >>> compile_params("player_game", spec)
        {
            "params": {"Season": "2024-25", "LastNGames": 5},
            "post_mask": {"TEAM_ID": [150], "LEAGUE": "NCAA-MBB"},
            "meta": {"league": "NCAA-MBB", "season": "2024-25"}
        }
    """
    params: dict[str, Any] = {}
    post_mask: dict[str, Any] = {}
    meta: dict[str, Any] = {}

    # Resolve names -> IDs (if resolver provided)
    team_ids = f.team_ids or _resolve_names_to_ids(f.team, "team", f.league, name_resolver)
    opp_ids = f.opponent_ids or _resolve_names_to_ids(f.opponent, "team", f.league, name_resolver)
    player_ids = f.player_ids or _resolve_names_to_ids(f.player, "player", f.league, name_resolver)

    # Store league/season in meta for logging/caching
    if f.league:
        meta["league"] = f.league
    if f.season:
        meta["season"] = f.season

    # --- Common parameters (supported by many endpoints) ---

    # Season
    if f.season:
        params["Season"] = f.season
        # Some sources want just the year (EuroLeague), others want YYYY-YY (ESPN)
        # The fetcher will adapt based on the source

    # Season type
    if f.season_type:
        params["SeasonType"] = f.season_type

    # Date range
    if f.date:
        if f.date.start:
            # ESPN format: MM/DD/YYYY
            params["DateFrom"] = f.date.start.strftime("%m/%d/%Y")
        if f.date.end:
            params["DateTo"] = f.date.end.strftime("%m/%d/%Y")
        # Also add to post_mask for sources that don't support date params
        post_mask["DATE_RANGE"] = f.date

    # Per-mode aggregation
    if f.per_mode:
        params["PerMode"] = f.per_mode

    # Last N games
    if f.last_n_games:
        params["LastNGames"] = f.last_n_games

    # --- Post-processing masks ---
    # These filters are applied after data is fetched, either because:
    # 1. The endpoint doesn't support native filtering, or
    # 2. We want to ensure consistent behavior across sources

    # IDs
    post_mask["TEAM_ID"] = team_ids
    post_mask["OPPONENT_TEAM_ID"] = opp_ids
    post_mask["PLAYER_ID"] = player_ids
    post_mask["GAME_ID"] = f.game_ids

    # Names (for sources that return names but not IDs)
    post_mask["TEAM_NAME"] = f.team
    post_mask["OPPONENT_NAME"] = f.opponent
    post_mask["PLAYER_NAME"] = f.player

    # Game location
    post_mask["HOME_AWAY"] = f.home_away
    post_mask["VENUE"] = f.venue

    # Statistical filters
    post_mask["MIN_MINUTES"] = f.min_minutes
    post_mask["QUARTER"] = f.quarter

    # Time-based filters (game minutes)
    post_mask["MIN_GAME_MINUTE"] = f.min_game_minute
    post_mask["MAX_GAME_MINUTE"] = f.max_game_minute

    # Shot/PBP filters
    post_mask["CONTEXT_MEASURE"] = f.context_measure

    # League filter (for multi-source queries)
    if f.league:
        post_mask["LEAGUE"] = f.league

    # Conference filter (post-mask if endpoint doesn't support it)
    if f.conference:
        post_mask["CONFERENCE"] = f.conference

    # Data quality
    post_mask["ONLY_COMPLETE"] = f.only_complete

    return {"params": params, "post_mask": post_mask, "meta": meta}


def apply_post_mask(df: Any, post_mask: dict[str, Any]) -> Any:
    """Apply post-processing filters to a DataFrame

    This function is used by fetchers to filter data after retrieval.
    Supports multiple data source schemas (NCAA uppercase, LNB lowercase/mixed).

    Column name handling:
    - Case-insensitive column matching (GAME_ID, game_id, or Game_Id all work)
    - Supports both uppercase (NCAA: TEAM_NAME) and lowercase (LNB: league)
    - Gracefully handles missing columns (filter skipped if column not found)

    Filter application order (optimized for performance):
    1. ID-based filters (most selective, fastest)
    2. League/Conference filters (categorical)
    3. Date/time filters (temporal range checks)
    4. Statistical filters (numeric comparisons)
    5. Name-based filters (slower string operations)

    Args:
        df: pandas DataFrame with data
        post_mask: Dictionary of filters from compile_params

    Returns:
        Filtered DataFrame

    Note:
        Early exits when DataFrame becomes empty to avoid unnecessary processing
    """

    import pandas as pd

    if df.empty:
        return df

    out = df.copy()

    # Helper: Find column by name (case-insensitive)
    def find_column(col_name: str) -> str | None:
        """Find column in DataFrame (case-insensitive)

        Returns actual column name if found, None otherwise
        """
        # Exact match first (fastest)
        if col_name in out.columns:
            return col_name
        # Case-insensitive search
        col_upper = col_name.upper()
        for col in out.columns:
            if col.upper() == col_upper:
                return col
        return None

    # --- Phase 1: ID-based filters (most selective, fastest) ---
    # These typically eliminate the most rows with O(n) complexity

    game_id_col = find_column("GAME_ID")
    if post_mask.get("GAME_ID") and game_id_col:
        out = out[out[game_id_col].isin(post_mask["GAME_ID"])]
        if out.empty:
            return out  # Early exit

    player_id_col = find_column("PLAYER_ID")
    if post_mask.get("PLAYER_ID") and player_id_col:
        out = out[out[player_id_col].isin(post_mask["PLAYER_ID"])]
        if out.empty:
            return out  # Early exit

    team_id_col = find_column("TEAM_ID")
    if post_mask.get("TEAM_ID") and team_id_col:
        out = out[out[team_id_col].isin(post_mask["TEAM_ID"])]
        if out.empty:
            return out  # Early exit

    opp_team_id_col = find_column("OPPONENT_TEAM_ID")
    if post_mask.get("OPPONENT_TEAM_ID") and opp_team_id_col:
        out = out[out[opp_team_id_col].isin(post_mask["OPPONENT_TEAM_ID"])]
        if out.empty:
            return out  # Early exit

    # --- Phase 2: Categorical filters (fast equality/membership checks) ---

    league_col = find_column("LEAGUE")
    if post_mask.get("LEAGUE") and league_col:
        out = out[out[league_col] == post_mask["LEAGUE"]]
        if out.empty:
            return out

    home_away_col = find_column("HOME_AWAY")
    if post_mask.get("HOME_AWAY") and home_away_col:
        out = out[out[home_away_col] == post_mask["HOME_AWAY"]]
        if out.empty:
            return out

    # Quarter/Period filtering (supports multiple column names)
    period_col = find_column("PERIOD") or find_column("PERIOD_ID") or find_column("QUARTER")
    if post_mask.get("QUARTER") and period_col:
        out = out[out[period_col].isin(post_mask["QUARTER"])]
        if out.empty:
            return out

    # --- Phase 3: Date/Time filters (temporal range checks) ---

    # Date range filtering (for game-level data)
    date_col = find_column("GAME_DATE") or find_column("DATE") or find_column("date")
    if post_mask.get("DATE_RANGE") and date_col:
        date_range = post_mask["DATE_RANGE"]

        # Convert column to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(out[date_col]):
            out[date_col] = pd.to_datetime(out[date_col], errors="coerce")

        # Apply start date filter
        if date_range.start:
            start_dt = pd.Timestamp(date_range.start)
            # Localize start_dt to match column timezone if needed
            if pd.api.types.is_datetime64_any_dtype(out[date_col]):
                if hasattr(out[date_col].dtype, "tz") and out[date_col].dtype.tz is not None:
                    # Column is timezone-aware, make comparison timezone-aware
                    start_dt = start_dt.tz_localize("UTC")
            out = out[out[date_col] >= start_dt]
            if out.empty:
                return out

        # Apply end date filter
        if date_range.end:
            end_dt = pd.Timestamp(date_range.end)
            # Localize end_dt to match column timezone if needed
            if pd.api.types.is_datetime64_any_dtype(out[date_col]):
                if hasattr(out[date_col].dtype, "tz") and out[date_col].dtype.tz is not None:
                    # Column is timezone-aware, make comparison timezone-aware
                    end_dt = end_dt.tz_localize("UTC")
            out = out[out[date_col] <= end_dt]
            if out.empty:
                return out

    # Game-minute filtering (for event-level data like PBP/shots)
    # Supports multiple column naming conventions
    game_minute_col = (
        find_column("GAME_MINUTE")
        or find_column("ELAPSED_TIME")
        or find_column("GAME_TIME")
        or find_column("game_minute")
    )

    if game_minute_col:
        # Min game minute filter
        if post_mask.get("MIN_GAME_MINUTE") is not None:
            min_minute = float(post_mask["MIN_GAME_MINUTE"])
            out = out[pd.to_numeric(out[game_minute_col], errors="coerce") >= min_minute]
            if out.empty:
                return out

        # Max game minute filter
        if post_mask.get("MAX_GAME_MINUTE") is not None:
            max_minute = float(post_mask["MAX_GAME_MINUTE"])
            out = out[pd.to_numeric(out[game_minute_col], errors="coerce") <= max_minute]
            if out.empty:
                return out

    # --- Phase 4: Statistical filters (numeric comparisons) ---

    min_col = find_column("MIN") or find_column("MINUTES")
    if post_mask.get("MIN_MINUTES") is not None and min_col:
        min_val = float(post_mask["MIN_MINUTES"])
        out = out[pd.to_numeric(out[min_col], errors="coerce") >= min_val]
        if out.empty:
            return out

    # --- Phase 5: String-based filters (slower, done last) ---
    # Uses case-insensitive regex matching for flexibility

    conf_col = find_column("CONFERENCE")
    if post_mask.get("CONFERENCE") and conf_col:
        conf = post_mask["CONFERENCE"]
        out = out[out[conf_col].str.contains(conf, case=False, na=False, regex=False)]
        if out.empty:
            return out

    venue_col = find_column("VENUE") or find_column("ARENA")
    if post_mask.get("VENUE") and venue_col:
        pattern = post_mask["VENUE"]
        out = out[out[venue_col].str.contains(pattern, case=False, na=False, regex=False)]
        if out.empty:
            return out

    # Name-based filtering with case-insensitive partial matching
    player_name_col = find_column("PLAYER_NAME") or find_column("player_name")
    if post_mask.get("PLAYER_NAME") and player_name_col:
        # Support list of names with OR logic
        pattern = "|".join(post_mask["PLAYER_NAME"])
        out = out[out[player_name_col].str.contains(pattern, case=False, na=False, regex=True)]
        if out.empty:
            return out

    team_name_col = find_column("TEAM_NAME") or find_column("team_name") or find_column("TEAM")
    if post_mask.get("TEAM_NAME") and team_name_col:
        pattern = "|".join(post_mask["TEAM_NAME"])
        out = out[out[team_name_col].str.contains(pattern, case=False, na=False, regex=True)]
        if out.empty:
            return out

    opp_name_col = (
        find_column("OPPONENT_NAME") or find_column("opponent_name") or find_column("OPPONENT")
    )
    if post_mask.get("OPPONENT_NAME") and opp_name_col:
        pattern = "|".join(post_mask["OPPONENT_NAME"])
        out = out[out[opp_name_col].str.contains(pattern, case=False, na=False, regex=True)]
        if out.empty:
            return out

    # --- Phase 6: Data completeness filter (last, as it's broad) ---

    if post_mask.get("ONLY_COMPLETE"):
        # Only keep rows with non-null key fields
        # Use case-insensitive column finding
        key_cols = []
        for key_name in ["GAME_ID", "PLAYER_ID", "TEAM_ID"]:
            col = find_column(key_name)
            if col:
                key_cols.append(col)

        if key_cols:
            out = out.dropna(subset=key_cols)

    return out
